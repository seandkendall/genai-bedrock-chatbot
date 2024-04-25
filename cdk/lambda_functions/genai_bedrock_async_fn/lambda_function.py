import json, datetime, os, boto3
from botocore.exceptions import ClientError
import jwt



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

def lambda_handler(event, context):   
    try:
        # Check if the event is a WebSocket event
        if event['requestContext']['eventType'] == 'MESSAGE':
            # Handle WebSocket message
            process_websocket_message(event)

        return {'statusCode': 200}

    except Exception as e:    
        print("Error (766): " + str(e))
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}

def process_websocket_message(event):
    global system_prompt
    # Extract the request body and session ID from the WebSocket event
    request_body = json.loads(event['body'])
    message_type = request_body.get('type', '')
    session_id = request_body.get('session_id', 'XYZ')
    connection_id = event['requestContext']['connectionId']
    # Check if the WebSocket connection is open
    try:
        connection = apigateway_management_api.get_connection(ConnectionId=connection_id)
        connection_state = connection.get('ConnectionStatus', 'OPEN')
        if connection_state != 'OPEN':
            print(f"WebSocket connection is not open (state: {connection_state})")
            return
    except apigateway_management_api.exceptions.GoneException:
        print(f"WebSocket connection is closed (connectionId: {connection_id})")
        return

    if message_type == 'clear_conversation':
        print(f'Action: Clear Conversation {session_id}')
        # Delete the conversation history from DynamoDB
        delete_conversation_history(session_id)
        return
    elif message_type == 'load':
        # Load conversation history from DynamoDB
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
        reload_prompt_config = bool(request_body.get('reloadPromptConfig', 'False'))
        system_prompt_user_or_system = request_body.get('systemPromptUserOrSystem', 'system')
        if not system_prompt or reload_prompt_config:
            print('reloading system config')
            system_prompt = load_system_prompt_config(system_prompt_user_or_system,user_id)
        selected_model = request_body.get('model')
        if isinstance(selected_model,str):
            selected_model_id = selected_model
        else:
            selected_model_id = selected_model.get('modelId').replace(' ','')
            
        bedrock_request= {}
        if 'anthropic' in selected_model_id.lower():
            bedrock_request = {
                'max_tokens': 4096,
                'system': system_prompt,
                'messages': existing_history + [{'role': 'user', 'content': [{'type': 'text', 'text': prompt}]}],
                'anthropic_version': 'bedrock-2023-05-31'
            }
        elif 'amazon' in selected_model_id.lower():
            bedrock_request = {
                'input_text': existing_history + ' ' +  prompt,
                'text_generation_config':{
                    'max_token_count': 4096,
                    'stop_sequences': ['User:']
                }
            }
        elif 'ai21' in selected_model_id.lower():
            bedrock_request = {
                'max_tokens': 4096,
                'prompt': existing_history + ' ' +  prompt
            }
        else:
            print(selected_model_id+' Not yet implemented')
            

        # Invoke the Bedrock API and get the response stream
        try:
            response = bedrock.invoke_model_with_response_stream(body=json.dumps(bedrock_request), modelId=selected_model_id)

            # Process the response stream and send the content to the WebSocket client
            if 'anthropic' in selected_model_id.lower():
                assistant_response, input_tokens, output_tokens = process_bedrock_response(iter(response['body']),json.dumps(bedrock_request), connection_id, user_id)
            elif 'amazon' in selected_model_id.lower():
                assistant_response, input_tokens, output_tokens = process_bedrock_response(iter(response['body']),json.dumps(bedrock_request), connection_id, user_id)
            elif 'ai21' in selected_model_id.lower():
                assistant_response, input_tokens, output_tokens = process_bedrock_response(iter(response['body']),json.dumps(bedrock_request), connection_id, user_id)

            # Store the updated conversation history in DynamoDB
            store_conversation_history(session_id, existing_history, prompt, assistant_response, user_id, input_tokens, output_tokens)
        except Exception as e:
            if 'have access to the model with the specified model ID.' in str(e):
                model_access_url = f'https://{region}.console.aws.amazon.com/bedrock/home?region={region}#/modelaccess'
                send_websocket_message(connection_id, {
                    'type': 'error',
                    'error': f'You have not enabled the selected model. Please visit the following link to request model access: [{model_access_url}]({model_access_url})'
                })
            print(f"Error calling bedrock model (912): {str(e)}")
        
        

def delete_conversation_history(session_id):
    try:
        dynamodb.delete_item(
            TableName=table_name,
            Key={'session_id': {'S': session_id}}
        )
        print(f"Conversation history deleted for session ID: {session_id}")
    except Exception as e:
        print(f"Error deleting conversation history (9781): {str(e)}")

def process_bedrock_response(response_stream, prompt, connection_id, user_id):
    result_text = ""
    current_input_tokens = 0
    current_output_tokens = 0
    # new counter starting at 0
    counter = 0
    try:
        for event in response_stream:
            chunk = event.get('chunk', {})
            if chunk.get('bytes'):
                content_chunk = json.loads(chunk['bytes'].decode('utf-8'))

                if content_chunk['type'] == 'message_start':
                    # Send the message_start event to the WebSocket client
                    send_websocket_message(connection_id, {
                        'type': 'message_start',
                        'message': content_chunk['message']
                    })

                elif content_chunk['type'] == 'content_block_delta':
                    #increment counter by 1
                    counter += 1
                    if content_chunk['delta']['text']:
                        # Escape any HTML tags before sending
                        escaped_text = content_chunk['delta']['text']
                        # Append the text to the result_text string
                        result_text += escaped_text
                        # Send the content_block_delta event to the WebSocket client
                        send_websocket_message(connection_id, {
                            'type': 'content_block_delta',
                            'delta': {'text': escaped_text},
                            'message_id': counter
                        })

                elif content_chunk['type'] == 'message_stop':
                    amazon_bedrock_invocationMetrics =  content_chunk.get('amazon-bedrock-invocationMetrics', {})
                    current_input_tokens = amazon_bedrock_invocationMetrics.get('inputTokenCount', 0)
                    current_output_tokens = amazon_bedrock_invocationMetrics.get('outputTokenCount', 0)
                    print(f"TokenCounts: {str(current_input_tokens)}/{str(current_output_tokens)}")
                    # TODO: send update monthly usage tokens
                    # {monthly_input_tokens, monthly_output_tokens} = get_monthly_token_usage(user_id)
                    # Send the message_stop event to the WebSocket client
                    send_websocket_message(connection_id, {
                        'type': 'message_stop',
                        'amazon-bedrock-invocationMetrics': content_chunk.get('amazon-bedrock-invocationMetrics', {})
                    })

    except Exception as e:
        print(f"Error processing Bedrock response (9926): {str(e)}")
        print(f"Original Prompt: {prompt}")
        # Send an error message to the WebSocket client
        send_websocket_message(connection_id, {
            'type': 'error',
            'error': str(e)
        })

    # assistant_response,input_tokens, output_tokens
    return result_text, current_input_tokens, current_output_tokens


def send_websocket_message(connection_id, message):
    try:
        # Check if the WebSocket connection is open
        connection = apigateway_management_api.get_connection(ConnectionId=connection_id)
        connection_state = connection.get('ConnectionStatus', 'OPEN')
        if connection_state != 'OPEN':
            print(f"WebSocket connection is not open (state: {connection_state})")
            return

        apigateway_management_api.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(message).encode()
        )
    except apigateway_management_api.exceptions.GoneException:
        print(f"WebSocket connection is closed (connectionId: {connection_id})")
    except Exception as e:
        print(f"Error sending WebSocket message (9012): {str(e)}")

def query_existing_history(session_id):
    try:
        response = dynamodb.get_item(
            TableName=table_name,
            Key={'session_id': {'S': session_id}},
            ProjectionExpression='conversation_history'
        )

        if 'Item' in response:
            return json.loads(response['Item']['conversation_history']['S'])
        else:
            return []

    except Exception as e:
        print("Error querying existing history: " + str(e))
        return []

def get_monthly_token_usage(user_id):
    current_date_ym = datetime.datetime.now().strftime('%Y-%m')
    response = dynamodb.get_item(
        TableName=usage_table_name,
        Key={'user_id': user_id+'-'+current_date_ym},
        ProjectionExpression='input_tokens, output_tokens'
    )
    if 'Item' in response:
        return response['Item']['input_tokens']['N'], response['Item']['output_tokens']['N']
    
def save_token_usage(user_id, input_tokens,output_tokens):
    current_date_ymd = datetime.datetime.now().strftime('%Y-%m-%d')
    current_date_ym = datetime.datetime.now().strftime('%Y-%m')
    
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
    
def store_conversation_history(session_id, existing_history, user_message, assistant_message, user_id, input_tokens, output_tokens):
    if user_message.strip() and assistant_message.strip():
        # Prepare the updated conversation history
        conversation_history = existing_history + [
            {'role': 'user', 'content': user_message},
            {'role': 'assistant', 'content': assistant_message}
        ]
        conversation_history_size = len(json.dumps(conversation_history).encode('utf-8'))


        # Check if the conversation history size is greater than 80% of the 400KB limit (327,680)
        if conversation_history_size > (400 * 1024 * 0.8):
            print(f"Warning: Session ID {session_id} has reached 80% of the DynamoDB limit. Storing conversation history in S3.")
            # Store the conversation history in S3
            try:
                s3.put_object(
                    Bucket=conversation_history_bucket,
                    Key=f"{session_id}.json",
                    Body=json.dumps(conversation_history).encode('utf-8')
                )
            except ClientError as e:
                print(f"Error storing conversation history in S3: {e}")

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
            print(f"User message is empty, skipping storage for session ID: {session_id}")
        if not assistant_message.strip():
            print(f"Assistant response is empty, skipping storage for session ID: {session_id}")

def load_and_send_conversation_history(session_id, connection_id):
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
        print(f"Error loading conversation history: {str(e)}")
        return []
    

def split_message(message, max_chunk_size=30 * 1024):  # 30 KB chunk size
    chunks = []
    current_chunk = []
    current_chunk_size = 0

    for msg in message:
        msg_json = json.dumps({'role': msg['role'], 'content': msg['content']})
        msg_size = len(msg_json.encode('utf-8'))

        if current_chunk_size + msg_size > max_chunk_size:
            chunks.append(json.dumps(current_chunk))
            current_chunk = []
            current_chunk_size = 0

        current_chunk.append(msg)
        current_chunk_size += msg_size

    if current_chunk:
        chunks.append(json.dumps(current_chunk))

    return chunks

def load_system_prompt_config(system_prompt_user_or_system, user_id):
    try:
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
        system_prompt = config_item.get('systemPrompt', '')

        return system_prompt

    except Exception as e:
        raise e
