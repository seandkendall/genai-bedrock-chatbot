import json
import os
import boto3
import jwt
import re
import sys
import base64
import copy
from chatbot_commons import commons
from datetime import datetime, timezone
from botocore.exceptions import ClientError
#use AWS powertools for logging
from aws_lambda_powertools import Logger, Metrics, Tracer
from llm_conversion_functions import (
    generate_random_string,
    process_message_history_converse,
    split_message,
    process_bedrock_converse_response
)
logger = Logger(service="BedrockAsync")
metrics = Metrics()
tracer = Tracer()


# Initialize DynamoDB client
dynamodb = boto3.client('dynamodb')
config_table_name = os.environ.get('DYNAMODB_TABLE_CONFIG')
config_table = boto3.resource('dynamodb').Table(config_table_name)
s3_client = boto3.client('s3')
conversation_history_bucket = os.environ['CONVERSATION_HISTORY_BUCKET']
attachment_bucket = os.environ['ATTACHMENT_BUCKET']
image_bucket = os.environ['S3_IMAGE_BUCKET_NAME']
WEBSOCKET_API_ENDPOINT = os.environ['WEBSOCKET_API_ENDPOINT']
table_name = os.environ['DYNAMODB_TABLE']
usage_table_name = os.environ['DYNAMODB_TABLE_USAGE']
region = os.environ['REGION']

MAX_CONTENT_ITEMS = 20
MAX_IMAGES = 20
MAX_DOCUMENTS = 5
ALLOWED_DOCUMENT_TYPES = ['pdf', 'csv', 'doc', 'docx', 'xls', 'xlsx', 'html', 'txt', 'md', 'png','jpeg','gif','webp']

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
        logger.exception(e)
        logger.error("Error (766)")
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}

@tracer.capture_method
def process_websocket_message(event):
    """Function to process a websocket message"""
    global system_prompt
    # Extract the request body and session ID from the WebSocket event
    request_body = json.loads(event['body'])
    id_token = request_body.get('idToken', 'none')
    decoded_token = jwt.decode(id_token, algorithms=["RS256"], options={"verify_signature": False})
    user_id = decoded_token['cognito:username']
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
        delete_s3_attachments_for_session(session_id,attachment_bucket)
        delete_s3_attachments_for_session(session_id,image_bucket)
        delete_s3_attachments_for_session(session_id,conversation_history_bucket)
        delete_conversation_history(session_id)
        return
    elif message_type == 'load':
        # Load conversation history from DynamoDB
        load_and_send_conversation_history(session_id, connection_id)
        return
    else:
        # Handle other message types (e.g., prompt)
        prompt = request_body.get('prompt', '')
        attachments = request_body.get('attachments', [])
        # Validate attachments
        if len(attachments) > MAX_CONTENT_ITEMS:
            commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                'type': 'error',
                'error': f'Too many attachments. Maximum allowed is {MAX_CONTENT_ITEMS}.'
            })
            return {'statusCode': 400}

        image_count = sum(1 for a in attachments if a['type'].startswith('image/'))
        document_count = len(attachments) - image_count

        if image_count > MAX_IMAGES:
            commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                'type': 'error',
                'error': f'Too many images. Maximum allowed is {MAX_IMAGES}.'
            })
            return {'statusCode': 400}

        if document_count > MAX_DOCUMENTS:
            commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                'type': 'error',
                'error': f'Too many documents. Maximum allowed is {MAX_DOCUMENTS}.'
            })
            return {'statusCode': 400}
        processed_attachments = []
        for attachment in attachments:
            file_type = attachment['type'].split('/')[-1].lower()
            if not attachment['type'].startswith('image/') and file_type not in ALLOWED_DOCUMENT_TYPES:
                commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                    'type': 'error',
                    'error': f'Invalid file type: {file_type}. Allowed types are images and {", ".join(ALLOWED_DOCUMENT_TYPES)}.'
                })
                return {'statusCode': 400}

            # Download file from S3
            try:
                file_key = attachment['url'].split('/')[-1]
                response = s3_client.get_object(Bucket=os.environ['ATTACHMENT_BUCKET'], Key=f'{user_id}/{session_id}/{file_key}')
                file_content = response['Body'].read()
            except Exception as e:
                logger.exception(e)
                logger.error(f"Error downloading file from S3: {str(e)}")
                commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                    'type': 'error',
                    'error': f'Error processing attachment: {attachment["name"]}'
                })
                return {'statusCode': 500}

            processed_attachments.append({
                'type': attachment['type'],
                'name': attachment['name'],
                's3bucket': os.environ['ATTACHMENT_BUCKET'], 
                's3key': f'{user_id}/{session_id}/{file_key}',
                'content': file_content
            })

        # Query existing history for the session from DynamoDB
        needs_load_from_s3, original_existing_history = query_existing_history(session_id)
        if needs_load_from_s3:
            existing_history = load_documents_from_existing_history(original_existing_history)
        else:
            existing_history = copy.deepcopy(original_existing_history)
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
        converse_content_array = []
        converse_content_with_s3_pointers = []
        if prompt:
            converse_content_array.append({'text': prompt})
            converse_content_with_s3_pointers.append({'text': prompt})
        
        for attachment in processed_attachments:
            if attachment['type'].startswith('image/'):
                converse_content_array.append({'image':{'format': attachment['type'].split('/')[1],
                                                        'source': {'bytes': attachment['content']}
                                                        }
                                                })
                converse_content_with_s3_pointers.append({'image':{'format': attachment['type'].split('/')[1],
                                                        's3source': {'s3bucket': attachment['s3bucket'], 's3key': attachment['s3key']}
                                                        }
                                                })
            else:
                converse_content_array.append({'document':{'format': attachment['type'].split('/')[-1],
                                                            'name': sanitize_filename(attachment['name']),
                                                            'source': {'bytes': attachment['content']}
                                                            }
                                                })
                converse_content_with_s3_pointers.append({'document':{'format': attachment['type'].split('/')[-1],
                                                            'name': sanitize_filename(attachment['name']),
                                                            's3source': {'s3bucket': attachment['s3bucket'], 's3key': attachment['s3key']}
                                                            }
                                                })

        message_content = process_message_history_converse(existing_history) + [{
                'role': 'user',
                'content': converse_content_array,
            }]
        bedrock_request = {
            'messages': message_content
        }
        if model_provider == 'meta':
            bedrock_request['additionalModelRequestFields'] = {'max_gen_len':2048}
        
        if bedrock_request:
            try:
                tracer.put_annotation(key="Model", value=selected_model_id)
                system_prompt_array = []
                if system_prompt:
                    system_prompt_array.append({'text': system_prompt})
                response = bedrock.converse_stream(messages=bedrock_request.get('messages'),
                                                    modelId=selected_model_id,
                                                    system=system_prompt_array,
                                                    additionalModelRequestFields=bedrock_request.get('additionalModelRequestFields',{}))
                    
                assistant_response, input_tokens, output_tokens, message_end_timestamp_utc = process_bedrock_converse_response(apigateway_management_api,response,selected_model_id,connection_id,converse_content_with_s3_pointers)
                store_conversation_history_converse(session_id, original_existing_history,converse_content_with_s3_pointers, prompt, assistant_response, user_id, input_tokens, output_tokens, message_end_timestamp_utc, message_received_timestamp_utc, message_id)
            except Exception as e:
                logger.exception(e)
                logger.error(f"Error calling bedrock model (912): {str(e)}")
                if 'have access to the model with the specified model ID.' in str(e):
                    model_access_url = f'https://{region}.console.aws.amazon.com/bedrock/home?region={region}#/modelaccess'
                    commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                        'type': 'error',
                        'error': f'You have not enabled the selected model. Please visit the following link to request model access: [{model_access_url}]({model_access_url})'
                    })
                else:
                    commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                        'type': 'error',
                        'error': f'An Error has occurred, please try again: {str(e)}'
                    })
        else:
            logger.warn('No bedrock request')

@tracer.capture_method
def delete_s3_attachments_for_session(session_id,bucket):
    """Function to delete conversation attachments from s3"""
    deleted_objects = []
    errors = []
    sid, model = session_id.rsplit('-model-', 1)
    prefix = rf'{sid}/{session_id}'
    
    try:
        # List objects with the specified prefix
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket, Prefix=prefix)
        
        for page in pages:
            if 'Contents' in page:
                for obj in page['Contents']:
                    key = obj['Key']
                    try:
                        s3_client.delete_object(Bucket=bucket, Key=key)
                        deleted_objects.append(f"s3://{bucket}/{key}")
                    except Exception as e:
                        logger.exception(e)
                        errors.append(f"Error deleting s3://{bucket}/{key}: {str(e)}")
    
    except Exception as e:
        logger.exception(e)
        errors.append(f"Error listing objects in s3://{bucket}/{prefix}: {str(e)}")
    
    if errors:
        logger.error(f"Encountered {len(errors)} errors:")
        for error in errors:
            logger.error(f"- {error}")
            
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
        logger.exception(e)
        logger.error(f"Error deleting conversation history (9781): {str(e)}")

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
            conversation_history_string = response['Item']['conversation_history']['S']
            # if s3source exists in conversation_history_string then needs_load_from_s3 = true
            needs_load_from_s3 = 's3source' in conversation_history_string
            return needs_load_from_s3,json.loads(conversation_history_string)

        return False,[]

    except Exception as e:
        logger.exception(e)
        logger.error("Error querying existing history: " + str(e))
        return []
    
@tracer.capture_method
def download_s3_content(item, content_type):
    """
    Download content from S3 and update the item with the downloaded content.

    Args:
        item (dict): The item containing the content to be downloaded.
        content_type (str): The type of content, either 'document' or 'image'.

    Returns:
        None
    """
    content = item[content_type]
    if 's3source' in content:
        s3_bucket = content['s3source']['s3bucket']
        s3_key = content['s3source']['s3key']
        try:
            response = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
            file_content = response['Body'].read()
            content['source'] = {'bytes': file_content}
            del content['s3source']
        except ClientError as e:
            logger.exception(e)

@tracer.capture_method
def load_documents_from_existing_history(existing_history):
    """
    Load documents and images from the existing history, where the content is stored in S3.

    Args:
        existing_history (list): A list of dictionaries representing the existing history.

    Returns:
        list: The modified history with the downloaded content.
    """
    modified_history = []
    existing_history = copy.deepcopy(existing_history)
    for item in existing_history:
        modified_item = {}
        modified_item['role'] = item['role']
        modified_item['timestamp'] = item['timestamp']
        modified_item['message_id'] = item['message_id']
        modified_item['content'] = []
        for content_item in item['content']:
            modified_content_item = {}
            for key, value in content_item.items():
                if key in ['text']:
                    modified_content_item[key] = value
                elif key in ['document', 'image']:
                    modified_content_item[key] = value
                    download_s3_content(modified_content_item, key)
            modified_item['content'].append(modified_content_item)
        modified_history.append(modified_item)
    return modified_history
    
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
def store_conversation_history_converse(session_id, existing_history, converse_content_array, user_message, assistant_message, user_id, input_tokens, output_tokens, message_end_timestamp_utc, message_received_timestamp_utc, message_id):
    """Function to store conversation history in DDB or S3 in the converse format"""
    sid, model = session_id.rsplit('-model-', 1)
    prefix = rf'{sid}/{session_id}'
    if user_message.strip() and assistant_message.strip():
        # Prepare the updated conversation history
        conversation_history = existing_history + [
            {'role': 'user', 'content': converse_content_array, 'timestamp': message_received_timestamp_utc, 'message_id':message_id},
            {'role': 'assistant', 'content': [{'text':assistant_message}], 'timestamp': message_end_timestamp_utc, 'message_id':generate_random_string()}
        ]
        conversation_history_size = len(json.dumps(conversation_history).encode('utf-8'))
        
        # Check if the conversation history size is greater than 80% of the 400KB limit (327,680)
        if conversation_history_size > (400 * 1024 * 0.8):
            logger.warn(f"Warning: Session ID {session_id} has reached 80% of the DynamoDB limit. Storing conversation history in S3.")
            # Store the conversation history in S3
            try:
                s3_client.put_object(
                    Bucket=conversation_history_bucket,
                    Key=f"{prefix}/{session_id}.json",
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
                sid, model = session_id.rsplit('-model-', 1)
                prefix = rf'{sid}/{session_id}'
                # Load conversation history from S3
                response = s3_client.get_object(Bucket=conversation_history_bucket, Key=f"{prefix}/{session_id}.json")
                conversation_history = json.loads(response['Body'].read().decode('utf-8'))
            else:
                # Load conversation history from DynamoDB
                conversation_history_str = item['conversation_history']['S']
                conversation_history = json.loads(conversation_history_str)
            # Split the conversation history into chunks
            conversation_history_chunks = split_message(conversation_history)
            # Send the conversation history chunks to the WebSocket client
            for chunk in conversation_history_chunks:
                commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
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

def sanitize_filename(filename: str) -> str:
    """
    Sanitizes a filename to only contain alphanumeric characters, whitespace characters, hyphens, parentheses, and square brackets.
    Removes consecutive whitespace characters.
    """
    # Replace non-alphanumeric characters, non-whitespace, non-hyphens, non-parentheses, and non-square brackets with an underscore
    sanitized_filename = re.sub(r'[^a-zA-Z0-9\s\-()\[\]]', '_', filename)
    
    # Replace consecutive whitespace characters with a single space
    sanitized_filename = re.sub(r'\s+', ' ', sanitized_filename)
    
    # Remove leading and trailing whitespace characters
    sanitized_filename = sanitized_filename.strip()
    
    return sanitized_filename
