import json
import os
import boto3
from boto3.dynamodb.conditions import Key
import jwt
import re
import sys
import base64
import copy
from chatbot_commons import commons
from conversations import conversations
from datetime import datetime, timezone
from botocore.exceptions import ClientError
#use AWS powertools for logging
from aws_lambda_powertools import Logger, Metrics, Tracer
from llm_conversion_functions import (
    process_message_history_converse,
    process_bedrock_converse_response,
    process_bedrock_converse_response_for_title,
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
conversations_table_name = os.environ['CONVERSATIONS_DYNAMODB_TABLE']
conversations_table = boto3.resource('dynamodb').Table(conversations_table_name)
usage_table_name = os.environ['DYNAMODB_TABLE_USAGE']
region = os.environ['REGION']
# models that do not support a system prompt (also includes all amazon models)
SYSTEM_PROMPT_EXCLUDED_MODELS = (
                    'cohere.command-text-v14',
                    'cohere.command-light-text-v14',
                    'mistral.mistral-7b-instruct-v0:2',
                    'mistral.mixtral-8x7b-instruct-v0:1'
                )

# Constants
MAX_DDB_SIZE = 400 * 1024  # 400KB
DDB_SIZE_THRESHOLD = 0.8
S3_KEY_FORMAT = "{prefix}/{session_id}.json"

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
    try:
        process_websocket_message(event)
        return {'statusCode': 200}

    except Exception as e:    
        logger.exception(e)
        logger.error("Error (766)")
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}

@tracer.capture_method
def process_websocket_message(request_body):
    """Function to process a websocket message"""
    global system_prompt
    access_token = request_body.get('access_token', {})
    session_id = request_body.get('session_id', 'XYZ')
    connection_id = request_body.get('connection_id', 'ZYX')
    user_id = access_token['payload']['sub']
    message_type = request_body.get('type', '')
    tracer.put_annotation(key="SessionID", value=session_id)
    tracer.put_annotation(key="UserID", value=user_id)
    tracer.put_annotation(key="MessageType", value=message_type)
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
        commons.delete_s3_attachments_for_session(session_id,attachment_bucket,user_id,None,s3_client, logger)
        commons.delete_s3_attachments_for_session(session_id,image_bucket,user_id,None,s3_client, logger)
        commons.delete_s3_attachments_for_session(session_id,conversation_history_bucket,user_id,None,s3_client, logger)
        conversations.delete_conversation_history(dynamodb,conversations_table_name,logger,session_id)
        return
    elif message_type == 'load':
        # Load conversation history from DynamoDB
        conversations.load_and_send_conversation_history(session_id, connection_id, user_id, dynamodb,conversations_table_name,s3_client,conversation_history_bucket,logger, commons,apigateway_management_api)
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
            if not attachment['type'].startswith('image/') and not attachment['type'].startswith('video/') and file_type not in ALLOWED_DOCUMENT_TYPES:
                commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                    'type': 'error',
                    'error': f'Invalid file type: {file_type}. Allowed types are images, videos and {", ".join(ALLOWED_DOCUMENT_TYPES)}.'
                })
                return {'statusCode': 400}

            # Download file from S3
            if attachment['type'].startswith('video/'):
                file_key = attachment['url'].split('/')[-1]
                file_content = None
            else:
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
        needs_load_from_s3, chat_title, original_existing_history = conversations.query_existing_history(dynamodb,conversations_table_name,logger,session_id)
        if needs_load_from_s3:
            existing_history = load_documents_from_existing_history(original_existing_history)
        else:
            existing_history = copy.deepcopy(original_existing_history)
        reload_prompt_config = bool(request_body.get('reloadPromptConfig', 'False'))
        system_prompt_user_or_system = request_body.get('systemPromptUserOrSystem', 'system')
        tracer.put_annotation(key="PromptUserOrSystem", value=system_prompt_user_or_system)
        if not system_prompt or reload_prompt_config:
            system_prompt = load_system_prompt_config(system_prompt_user_or_system,user_id)
        selected_mode = request_body.get('selected_mode', {})
        title_theme = request_body.get('titleGenTheme', '')
        title_gen_model = request_body.get('titleGenModel', '')
        if title_gen_model == 'DEFAULT' or not title_gen_model:
            title_gen_model = ''
        if '/' in title_gen_model:
            title_gen_model = title_gen_model.split('/')[1]
        
        selected_model_id = selected_mode.get('modelId','')
        selected_model_category = selected_mode.get('category','')
        model_provider = selected_model_id.split('.')[0]
        message_id = request_body.get('message_id', None)
        message_received_timestamp_utc = request_body.get('timestamp', datetime.now(tz=timezone.utc).isoformat())
        timestamp_local_timezone = request_body.get('timestamp_local_timezone')
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
            elif attachment['type'].startswith('video/'):
                video_format = attachment['type'].split('/')[1]
                if video_format == '3pg':
                    video_format = 'three_gp'
                
                converse_content_array.append({'video':{'format': video_format,
                                                        'source': {'s3Location': {
                                                                    'uri': f"s3://{attachment['s3bucket']}/{attachment['s3key']}"
                                                                }}
                                                        }
                                                })
                converse_content_with_s3_pointers.append({'video':{'format': video_format,
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
                if (not chat_title and len(bedrock_request.get('messages')) == 1) or (chat_title.startswith('New Conversation:')):
                    title_prompt_string = (
                        f'Generate a Title in under 16 characters, '
                        f'for a Chatbot conversation Header where the initial user prompt is: "{prompt}". '
                    )
                    if len(title_theme) > 0:
                        title_prompt_string = title_prompt_string + f' Be creative using the following theme: "{title_theme}" '
                    title_prompt_string = title_prompt_string +  'You MUST answer in RAW JSON format only matching this well defined json format: {"title":"title_value"}'
                    
                    title_prompt_request = [{'role': 'user','content': [{'text': title_prompt_string}]}]
                    try: 
                        chat_title = get_title_from_message(title_prompt_request, title_gen_model if title_gen_model else selected_model_id, connection_id, message_id)
                    except Exception:
                        chat_title = f'New Conversation: {hash(prompt) % 1000000:06x}'
                new_conversation = bool(not original_existing_history or len(original_existing_history) == 0)
                timezone_prompt = (
                    f"The Current Time in UTC is: {message_received_timestamp_utc}. "
                    f"Use the timezone of {timestamp_local_timezone} when making a reference to time. "
                    "ALWAYS use the date format of: Month DD, YYYY HH24:mm:ss. "
                    "ONLY include the time if needed. "
                    "NEVER reference this date randomly. "
                    "Use it to support high quality answers when the current date is NEEDED."
                )

                if system_prompt:
                    system_prompt = system_prompt + ' ' + timezone_prompt
                else:
                    system_prompt = timezone_prompt
                
                if system_prompt and selected_model_id not in SYSTEM_PROMPT_EXCLUDED_MODELS and model_provider != 'amazon':
                    system_prompt_array.append({'text': system_prompt})
                    response = bedrock.converse_stream(messages=bedrock_request.get('messages'),
                                                        modelId=selected_model_id,
                                                        system=system_prompt_array,
                                                        additionalModelRequestFields=bedrock_request.get('additionalModelRequestFields',{}))
                    #uncomment for prompt debugging
                    # commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                    #     'type': 'system_prompt_used',
                    #     'system_prompt': system_prompt,
                    #     'session_id':session_id,
                    # });
                else:
                    response = bedrock.converse_stream(messages=bedrock_request.get('messages'),
                                                    modelId=selected_model_id,
                                                    additionalModelRequestFields=bedrock_request.get('additionalModelRequestFields',{}))
                    
                assistant_response, input_tokens, output_tokens, message_end_timestamp_utc, message_stop_reason = process_bedrock_converse_response(apigateway_management_api,response,selected_model_id,connection_id,converse_content_with_s3_pointers,new_conversation,session_id)
                store_conversation_history_converse(session_id,selected_model_id, original_existing_history,converse_content_with_s3_pointers, prompt, assistant_response, user_id, input_tokens, output_tokens, message_end_timestamp_utc, message_received_timestamp_utc, message_id,chat_title,new_conversation,selected_model_category, message_stop_reason)
            except Exception as e:
                if 'ThrottlingException' not in str(e):
                    logger.exception(e)
                logger.warn(f"Error calling bedrock model (912): {str(e)}")
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
def get_title_from_message(messages: list, selected_model_id: str,connection_id: str, message_id: str) -> str:
    response = bedrock.converse_stream(messages=messages,
                                           modelId=selected_model_id,
                                           additionalModelRequestFields={})
    # chat_title is a json object
    chat_title = process_bedrock_converse_response_for_title(response)
    commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
        'type': 'message_title',
        'message_id': message_id,
        'title': chat_title['title']
    })
    return chat_title['title']

    

              
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
    status = False
    if 's3source' in content:
        s3_bucket = content['s3source']['s3bucket']
        s3_key = content['s3source']['s3key']
        try:
            response = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
            if response is not None and response['Body'] is not None:
                file_content = response['Body'].read()
                content['source'] = {'bytes': file_content}
                status = True
        except ClientError as e:
            logger.error(f"Error downloading content from S3: {e}")
            if e.response['Error']['Code'] == 'NoSuchKey':
                logger.error(f"Key {s3_key} not found in bucket {s3_bucket}")
            logger.exception(e)
        del content['s3source']
        return status

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
            add_item = True
            for key, value in content_item.items():
                if key in ['video']:
                    modified_content_item[key] = convert_video_s3_source_to_bedrock_format(value)
                elif key in ['text']:
                    modified_content_item[key] = value
                elif key in ['document', 'image']:
                    modified_content_item[key] = value
                    download_s3_content_worked = download_s3_content(modified_content_item, key)
                    if not download_s3_content_worked:
                        add_item = False
            if add_item:
                modified_item['content'].append(modified_content_item)
        modified_history.append(modified_item)
    return modified_history

@tracer.capture_method    
def store_conversation_history_converse(session_id, selected_model_id, existing_history,
    converse_content_array, user_message, assistant_message, user_id,
    input_tokens, output_tokens, message_end_timestamp_utc,
    message_received_timestamp_utc, message_id, title,new_conversation,selected_model_category,message_stop_reason):
    """Function to store conversation history in DDB or S3 in the converse format"""
    
    if not (user_message.strip() and assistant_message.strip()):
        if not user_message.strip():
            logger.info(f"User message is empty, skipping storage for session ID: {session_id}")
        if not assistant_message.strip():
            logger.info(f"Assistant response is empty, skipping storage for session ID: {session_id}")
        return

    prefix = rf'{user_id}/{session_id}'
    
    # Prepare the updated conversation history once
    conversation_history = existing_history + [
        {
            'role': 'user',
            'content': converse_content_array,
            'timestamp': message_received_timestamp_utc,
            'message_id': message_id
        },
        {
            'role': 'assistant',
            'content': [{'text': assistant_message}],
            'message_stop_reason': message_stop_reason,
            'timestamp': message_end_timestamp_utc,
            'message_id': commons.generate_random_string()
        }
    ]
    
    # Convert to JSON string once
    conversation_json = json.dumps(conversation_history)
    conversation_history_size = len(conversation_json.encode('utf-8'))
    current_timestamp = str(datetime.now(tz=timezone.utc).timestamp())
    
    try:
        if conversation_history_size > (MAX_DDB_SIZE * DDB_SIZE_THRESHOLD):
            logger.warn(f"Warning: Session ID {session_id} has reached 80% of the DynamoDB limit. Storing conversation history in S3.")
            
            # Store in S3
            s3_client.put_object(
                Bucket=conversation_history_bucket,
                Key=S3_KEY_FORMAT.format(prefix=prefix, session_id=session_id),
                Body=conversation_json.encode('utf-8')
            )
            
            # Update DynamoDB to indicate S3 storage
            dynamodb.update_item(
                TableName=conversations_table_name,
                Key={
                    'session_id': {'S': session_id} 
                },
                UpdateExpression="SET conversation_history_in_s3=:true, last_modified_date = :current_time",
                ExpressionAttributeValues={
                    ':true': {'BOOL': True}, 
                    ':current_time': {'N': current_timestamp}
                }
            )

        else:
            # Store in DynamoDB
            logger.info(f"Storing TITLE for conversation history in DynamoDB: {title}")
            if new_conversation:
                dynamodb.put_item(
                    TableName=conversations_table_name,
                    Item={
                        'session_id': {'S': session_id},
                        'user_id': {'S': user_id},
                        'title': {'S': title},
                        'last_modified_date': {'N': current_timestamp},
                        'selected_model_id': {'S': selected_model_id},
                        'category': {'S': selected_model_category},
                        'conversation_history': {'S': conversation_json},
                        'conversation_history_in_s3': {'BOOL': False}
                    }
                )
            else:
                dynamodb.update_item(
                    TableName=conversations_table_name,
                    Key={'session_id': {'S': session_id}},
                    UpdateExpression="SET last_modified_date = :current_time, title = :title, selected_model_id = :selected_model_id, conversation_history = :conversation_history, category = :category",
                    ExpressionAttributeValues={
                        ':current_time': {'N': current_timestamp},
                        ':title': {'S': title},
                        ':selected_model_id': {'S': selected_model_id},
                        ':conversation_history': {'S': conversation_json},
                        ':category': {'S': selected_model_category},
                    }
                )
        
        # Batch token usage update
        conversations.save_token_usage(user_id, input_tokens,output_tokens,dynamodb,usage_table_name)
        
    except (ClientError, Exception) as e:
        logger.error(f"Error storing conversation history: {e}")
        raise
    
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

def convert_video_s3_source_to_bedrock_format(input_json):
    # Extract the necessary information from the input dictionary
    videoformat = input_json['format']
    s3bucket = input_json['s3source']['s3bucket']
    s3key = input_json['s3source']['s3key']

    # Construct the S3 URI
    s3_uri = f"s3://{s3bucket}/{s3key}"

    # Create the new dictionary structure
    output_dict = {
        'format': videoformat,
        'source': {
            's3Location': {
                'uri': s3_uri
            }
        }
    }

    return output_dict