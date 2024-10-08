import json
import os
import boto3
import jwt
from datetime import datetime, timezone
from botocore.exceptions import ClientError
#use AWS powertools for logging
from aws_lambda_powertools import Logger, Metrics, Tracer
from llm_conversion_functions import (
    generate_random_string,
    process_message_history,
    process_message_history_mistral_large,
    process_message_history_converse,
    replace_user_bot,
    split_message,
    process_bedrock_converse_response,
    process_bedrock_response,
    send_websocket_message
)
logger = Logger(service="BedrockAsync")
metrics = Metrics()
tracer = Tracer()


# Initialize DynamoDB client
dynamodb = boto3.client('dynamodb')
config_table_name = os.environ.get('DYNAMODB_TABLE_CONFIG')
config_table = boto3.resource('dynamodb').Table(config_table_name)
s3 = boto3.client('s3')
conversation_history_bucket = os.environ['CONVERSATION_HISTORY_BUCKET']
WEBSOCKET_API_ENDPOINT = os.environ['WEBSOCKET_API_ENDPOINT']
table_name = os.environ['DYNAMODB_TABLE']
usage_table_name = os.environ['DYNAMODB_TABLE_USAGE']
region = os.environ['REGION']

# Initialize Bedrock client
bedrock = boto3.client(service_name="bedrock-runtime")

# AWS API Gateway Management API client
apigateway_management_api = boto3.client('apigatewaymanagementapi', endpoint_url=f"{WEBSOCKET_API_ENDPOINT.replace('wss', 'https')}/ws")

system_prompt = ''

@tracer.capture_lambda_handler
def lambda_handler(event, context):   
    """Lambda Hander Function"""
    # logger.info("Executing Bedrock Async Function")
    try:
        # Check if the event is a WebSocket event
        if event['requestContext']['eventType'] == 'MESSAGE':
            # Handle WebSocket message
            process_websocket_message(event)

        return {'statusCode': 200}

    except Exception as e:    
        logger.error("Error (766)")
        logger.exception(e)
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}

@tracer.capture_method
def process_websocket_message(event):
    """Function to process a websocket message"""
    global system_prompt
    # Extract the request body and session ID from the WebSocket event
    request_body = json.loads(event['body'])
    message_type = request_body.get('type', '')
    tracer.put_annotation(key="MessageType", value=message_type)
    session_id = request_body.get('session_id', 'XYZ')
    tracer.put_annotation(key="SessionID", value=session_id)
    connection_id = event['requestContext']['connectionId']
    tracer.put_annotation(key="ConnectionID", value=connection_id)
    # Check if the WebSocket connection is open
    try:
        connection = apigateway_management_api.get_connection(ConnectionId=connection_id)
        connection_state = connection.get('ConnectionStatus', 'OPEN')
        if connection_state != 'OPEN':
            logger.info(f"WebSocket connection is not open (state: {connection_state})")
            return
    except apigateway_management_api.exceptions.GoneException:
        logger.error(f"WebSocket connection is closed (connectionId: {connection_id})")
        return

    if message_type == 'clear_conversation':
        # logger.info(f'Action: Clear Conversation {session_id}')
        # Delete the conversation history from DynamoDB
        delete_conversation_history(session_id)
        return
    elif message_type == 'load':
        # Load conversation history from DynamoDB
        # logger.info(f'Action: Loading Conversation for {session_id}')
        load_and_send_conversation_history(session_id, connection_id)
        return
    else:
        # Handle other message types (e.g., prompt)
        prompt = request_body.get('prompt', '')
        # Query existing history for the session from DynamoDB
        existing_history = query_existing_history(session_id)
        id_token = request_body.get('idToken', 'none')
        decoded_token = jwt.decode(id_token, algorithms=["RS256"], options={"verify_signature": False})
        user_id = decoded_token['cognito:username']
        tracer.put_annotation(key="UserID", value=user_id)
        reload_prompt_config = bool(request_body.get('reloadPromptConfig', 'False'))
        system_prompt_user_or_system = request_body.get('systemPromptUserOrSystem', 'system')
        tracer.put_annotation(key="PromptUserOrSystem", value=system_prompt_user_or_system)
        if not system_prompt or reload_prompt_config:
            system_prompt = load_system_prompt_config(system_prompt_user_or_system,user_id)
        selected_mode = request_body.get('selectedMode', '')
        selected_model_id = selected_mode.get('modelId','')
        model_provider = selected_model_id.split('.')[0]
        message_id = request_body.get('message_id', None)
        message_received_timestamp_utc = request_body.get('timestamp', datetime.now(tz=timezone.utc).isoformat())
        bedrock_request = None
        use_converse = False
        if 'anthropic' in model_provider.lower():
            filtered_history = process_message_history(existing_history)
            bedrock_request = {
                'max_tokens': 4096,
                'system': system_prompt,
                'messages': filtered_history + [{'role': 'user', 'content': [{'type': 'text', 'text': prompt}]}],
                'anthropic_version': 'bedrock-2023-05-31'
            }
        elif 'amazon' in model_provider.lower():
            formatted_text = ''
            if existing_history:
                for message in existing_history:
                    if message['role'] == 'user':
                        formatted_text += f'User: {replace_user_bot(message["content"])}\n'
                    elif message['role'] == 'assistant':
                        formatted_text += f'Bot: {replace_user_bot(message["content"])}\n'

            # Adding the latest prompt
            formatted_text += f'User: {replace_user_bot(prompt)}\nBot:'

            # Final formatted inputText
            formatted_text = formatted_text.strip()
            max_token_count = 4096
            #if model_id contains text 'premier' set max_token_count to  3072
            if 'premier' in selected_model_id.lower():
                max_token_count = 3072
            bedrock_request = {
                'inputText': formatted_text,
                'textGenerationConfig': {
                    'maxTokenCount': max_token_count,
                    'stopSequences': [],
                    'temperature': 0.7,
                    'topP': 1
                }
            }
        elif 'ai21' in model_provider.lower():
            # TODO: implement ai21 Labs
            logger.warn('TODO: Implement AI21 Labs')
        elif 'mistral' in model_provider.lower():
            max_tokens = 8192
            bedrock_request = {
                'max_tokens': max_tokens,
                'messages': process_message_history_mistral_large(existing_history)+[{'role': 'user', 'content': prompt}]
            }
        elif 'meta' in model_provider.lower():
            use_converse = True
            bedrock_request = {
                'messages': process_message_history_converse(existing_history)+[{'role': 'user', 'content': [{'text': prompt}]}],
                'max_gen_len': 2048
            }
        else:
            logger.warning(f"Model '{selected_model_id}' from provider '{model_provider}' is not yet implemented")
        
        if bedrock_request:
            try:
                tracer.put_annotation(key="Model", value=selected_model_id)
                if use_converse:
                    system_prompt_array = []
                    if system_prompt:
                        system_prompt_array.append({'text': system_prompt})
                    response = bedrock.converse_stream(messages=bedrock_request.get('messages'),
                                                       modelId=selected_model_id,
                                                       system=system_prompt_array,
                                                       additionalModelRequestFields={'max_gen_len':bedrock_request.get('max_gen_len')})
                else:
                    response = bedrock.invoke_model_with_response_stream(body=json.dumps(bedrock_request), modelId=selected_model_id)
                    

                # Process the response stream and send the content to the WebSocket client
                if 'meta' in model_provider.lower() or use_converse:
                    assistant_response, input_tokens, output_tokens, message_end_timestamp_utc = process_bedrock_converse_response(response,selected_model_id,connection_id)
                elif 'amazon' in model_provider.lower():
                    assistant_response, input_tokens, output_tokens, message_end_timestamp_utc = process_bedrock_response(iter(response['body']),json.dumps(bedrock_request),connection_id,user_id,model_provider,selected_model_id)
                elif 'ai21' in model_provider.lower():
                    assistant_response, input_tokens, output_tokens, message_end_timestamp_utc = process_bedrock_response(iter(response['body']),json.dumps(bedrock_request), connection_id, user_id, model_provider,selected_model_id)
                elif 'mistral' in model_provider.lower():
                    assistant_response, input_tokens, output_tokens, message_end_timestamp_utc = process_bedrock_response(iter(response['body']),json.dumps(bedrock_request), connection_id, user_id, model_provider,selected_model_id)
                elif 'anthropic' in model_provider.lower():
                    assistant_response, input_tokens, output_tokens, message_end_timestamp_utc = process_bedrock_response(iter(response['body']),json.dumps(bedrock_request), connection_id, user_id, model_provider,selected_model_id)

                # Store the updated conversation history in DynamoDB
                store_conversation_history(session_id, existing_history, prompt, assistant_response, user_id, input_tokens, output_tokens, message_end_timestamp_utc, message_received_timestamp_utc, message_id)
            except Exception as e:
                logger.error(f"Error calling bedrock model (912): {str(e)}")
                logger.exception(e)
                if 'have access to the model with the specified model ID.' in str(e):
                    model_access_url = f'https://{region}.console.aws.amazon.com/bedrock/home?region={region}#/modelaccess'
                    send_websocket_message(connection_id, {
                        'type': 'error',
                        'error': f'You have not enabled the selected model. Please visit the following link to request model access: [{model_access_url}]({model_access_url})'
                    })
                else:
                    send_websocket_message(connection_id, {
                        'type': 'error',
                        'error': f'An Error has occurred, please try again: {str(e)}'
                    })
        else:
            logger.warn('No bedrock request')
        
        
@tracer.capture_method
def delete_conversation_history(session_id):
    """Function to delete conversation history from DDB"""
    try:
        dynamodb.delete_item(
            TableName=table_name,
            Key={'session_id': {'S': session_id}}
        )
        logger.info(f"Conversation history deleted for session ID: {session_id}")
    except Exception as e:
        logger.error(f"Error deleting conversation history (9781): {str(e)}")
        logger.exception(e)

@tracer.capture_method
def query_existing_history(session_id):
    """Function to query existing history from DDB"""
    try:
        response = dynamodb.get_item(
            TableName=table_name,
            Key={'session_id': {'S': session_id}},
            ProjectionExpression='conversation_history'
        )

        if 'Item' in response:
            return json.loads(response['Item']['conversation_history']['S'])

        return []

    except Exception as e:
        logger.error("Error querying existing history: " + str(e))
        logger.exception(e)
        return []

@tracer.capture_method
def get_monthly_token_usage(user_id):
    """Function to get monthly token usage from DDB"""
    current_date_ym = datetime.now(tz=timezone.utc).strftime('%Y-%m')
    response = dynamodb.get_item(
        TableName=usage_table_name,
        Key={'user_id': user_id+'-'+current_date_ym},
        ProjectionExpression='input_tokens, output_tokens'
    )
    if 'Item' in response:
        return response['Item']['input_tokens']['N'], response['Item']['output_tokens']['N']

@tracer.capture_method    
def save_token_usage(user_id, input_tokens,output_tokens):
    """Function to save token usage in DDB"""
    current_date_ymd = datetime.now(tz=timezone.utc).strftime('%Y-%m-%d')
    current_date_ym = datetime.now(tz=timezone.utc).strftime('%Y-%m')
    
    dynamodb.update_item(
                    TableName=usage_table_name,
                    Key={'user_id': {'S': user_id }},
                    UpdateExpression=f"ADD input_tokens :input_tokens, output_tokens :output_tokens, message_count :message_count",
                    ExpressionAttributeValues={
                        ':input_tokens': {'N': str(input_tokens)},
                        ':output_tokens': {'N': str(output_tokens)},
                        ':message_count': {'N': str(1)}
                    }
                )
    dynamodb.update_item(
                    TableName=usage_table_name,
                    Key={'user_id': {'S': user_id + '-' + current_date_ym}},
                    UpdateExpression="ADD input_tokens :input_tokens, output_tokens :output_tokens, message_count :message_count",
                    ExpressionAttributeValues={
                        ':input_tokens': {'N': str(input_tokens)},
                        ':output_tokens': {'N': str(output_tokens)},
                        ':message_count': {'N': str(1)}
                    }
                )
    dynamodb.update_item(
                    TableName=usage_table_name,
                    Key={'user_id': {'S': user_id + '-' + current_date_ymd}},
                    UpdateExpression="ADD input_tokens :input_tokens, output_tokens :output_tokens, message_count :message_count",
                    ExpressionAttributeValues={
                        ':input_tokens': {'N': str(input_tokens)},
                        ':output_tokens': {'N': str(output_tokens)},
                        ':message_count': {'N': str(1)}
                    }
                )

@tracer.capture_method    
def store_conversation_history(session_id, existing_history, user_message, assistant_message, user_id, input_tokens, output_tokens, message_end_timestamp_utc, message_received_timestamp_utc, message_id):
    """Function to store conversation history in DDB or S3"""
    if user_message.strip() and assistant_message.strip():
        # Prepare the updated conversation history
        conversation_history = existing_history + [
            {'role': 'user', 'content': user_message, 'timestamp': message_received_timestamp_utc, 'message_id':message_id},
            {'role': 'assistant', 'content': assistant_message, 'timestamp': message_end_timestamp_utc, 'message_id':generate_random_string()}
        ]
        conversation_history_size = len(json.dumps(conversation_history).encode('utf-8'))


        # Check if the conversation history size is greater than 80% of the 400KB limit (327,680)
        if conversation_history_size > (400 * 1024 * 0.8):
            logger.warn(f"Warning: Session ID {session_id} has reached 80% of the DynamoDB limit. Storing conversation history in S3.")
            # Store the conversation history in S3
            try:
                s3.put_object(
                    Bucket=conversation_history_bucket,
                    Key=f"{session_id}.json",
                    Body=json.dumps(conversation_history).encode('utf-8')
                )
            except ClientError as e:
                logger.error(f"Error storing conversation history in S3: {e}")

            # Update the DynamoDB item to indicate that the conversation history is in S3
                dynamodb.update_item(
                    TableName=table_name,
                    Key={'session_id': session_id},
                    UpdateExpression="SET conversation_history_in_s3=:true",
                    ExpressionAttributeValues={':true': True}
                )
        else:
            # Store the updated conversation history in DynamoDB
            dynamodb.put_item(
                TableName=table_name,
                Item={
                    'session_id': {'S': session_id},
                    'conversation_history': {'S': json.dumps(conversation_history)},
                    'conversation_history_in_s3': {'BOOL': False}
                }
            )
        save_token_usage(user_id, input_tokens, output_tokens)
    else:
        if not user_message.strip():
            logger.info(f"User message is empty, skipping storage for session ID: {session_id}")
        if not assistant_message.strip():
            logger.info(f"Assistant response is empty, skipping storage for session ID: {session_id}")
@tracer.capture_method
def load_and_send_conversation_history(session_id, connection_id):
    """Function to load and send conversation history"""
    try:
        response = dynamodb.get_item(
            TableName=table_name,
            Key={'session_id': {'S': session_id}}
        )

        if 'Item' in response:
            item = response['Item']
            conversation_history_in_s3 = False
            conversation_history_in_s3_value = item.get('conversation_history_in_s3', False)
            if isinstance(conversation_history_in_s3_value, dict):
                conversation_history_in_s3 = conversation_history_in_s3_value.get('BOOL', False)
            if conversation_history_in_s3:
                # Load conversation history from S3
                response = s3.get_object(Bucket=conversation_history_bucket, Key=f"{session_id}.json")
                conversation_history = json.loads(response['Body'].read().decode('utf-8'))
            else:
                # Load conversation history from DynamoDB
                conversation_history_str = item['conversation_history']['S']
                conversation_history = json.loads(conversation_history_str)
            # Split the conversation history into chunks
            conversation_history_chunks = split_message(conversation_history)
            # Send the conversation history chunks to the WebSocket client
            for chunk in conversation_history_chunks:
                send_websocket_message(connection_id, {
                    'type': 'conversation_history',
                    'chunk': chunk
                })
        else:
            return []

    except Exception as e:
        logger.error("Error loading conversation history")
        logger.exception(e)
        return []
    
@tracer.capture_method
def load_system_prompt_config(system_prompt_user_or_system, user_id):
    """Function to load system prompt from DDB config"""
    user_key = 'system'
    if system_prompt_user_or_system == 'user':
        user_key = user_id if user_id else 'system'
    if system_prompt_user_or_system == 'global':
        system_prompt_user_or_system = 'system'
    # Get the configuration from DynamoDB
    response = config_table.get_item(
    Key={
        'user': user_key,
        'config_type': system_prompt_user_or_system
    }
)
    config = response.get('Item', {})
    config_item = config.get('config', {})
    return config_item.get('systemPrompt', '')