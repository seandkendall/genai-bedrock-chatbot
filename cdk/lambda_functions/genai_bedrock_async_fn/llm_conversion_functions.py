import random
import string
import json
import os
import boto3
from datetime import datetime, timezone
from aws_lambda_powertools import Logger
logger = Logger(service="BedrockAsyncLLMFunctions")
WEBSOCKET_API_ENDPOINT = os.environ['WEBSOCKET_API_ENDPOINT']
# AWS API Gateway Management API client
apigateway_management_api = boto3.client('apigatewaymanagementapi', endpoint_url=f"{WEBSOCKET_API_ENDPOINT.replace('wss', 'https')}/ws")

def send_websocket_message(connection_id, message):
    try:
        # Check if the WebSocket connection is open
        connection = apigateway_management_api.get_connection(ConnectionId=connection_id)
        connection_state = connection.get('ConnectionStatus', 'OPEN')
        if connection_state != 'OPEN':
            logger.warn(f"WebSocket connection is not open (state: {connection_state})")
            return

        apigateway_management_api.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(message).encode()
        )
    except apigateway_management_api.exceptions.GoneException:
        logger.info(f"WebSocket connection is closed (connectionId: {connection_id})")
    except Exception as e:
        logger.error(f"Error sending WebSocket message (9012): {str(e)}")
        logger.exception(e)
        
def process_message_history(existing_history):
    """Function to process message history for non-converse APIs"""
    normalized_history = []
    for message in existing_history:
        # Extract role and content
        role = message.get('role')
        content = message.get('content')

        # Ensure role is present and valid
        if not role or role not in ['user', 'assistant']:
            continue  # Skip messages with invalid or missing roles

        # Normalize content format
        if isinstance(content, str):
            content = [{'type': 'text', 'text': content}]
        elif isinstance(content, list):
            # Ensure each item in the list is correctly formatted
            content = [{'type': 'text', 'text': item['text']} if isinstance(item, dict) and 'text' in item else {'type': 'text', 'text': str(item)} for item in content]
        else:
            content = [{'type': 'text', 'text': str(content)}]

        # Create normalized message
        normalized_message = {'role': role, 'content': content}

        normalized_history.append(normalized_message)

    return normalized_history
def process_message_history_converse(existing_history):
    """Function to process message history for converse"""
    normalized_history = []

    for message in existing_history:
        role = message.get('role')
        content = message.get('content')

        if role in ['user', 'assistant']:
            # Ensure content is a string
            content = str(content) if content is not None else ''
            
            # Create normalized message
            normalized_message = {
                'role': role,
                'content': [{'text': content}]
            }
            
            normalized_history.append(normalized_message)

    return normalized_history
    
def process_message_history_mistral_large(existing_history):
    """Function to process message history for mistral models"""
    normalized_history = []

    for message in existing_history:
        role = message.get('role')
        content = message.get('content')

        if role in ['user', 'assistant']:
            # Ensure content is a string
            content = str(content) if content is not None else ''
            
            # Create normalized message
            normalized_message = {
                'role': role,
                'content': content
            }
            
            normalized_history.append(normalized_message)

    return normalized_history

def generate_random_string(length=8):
    """Function to generate a random String of length 8"""
    characters = string.ascii_lowercase + string.digits
    random_part = ''.join(random.choice(characters) for _ in range(length))
    return f"RES{random_part}"

def replace_user_bot(text):
    """Function to replace colons with semi-colons"""
    return text.replace('User:', 'User;').replace('Bot:', 'Bot;')

def split_message(message, max_chunk_size=30 * 1024):  # 30 KB chunk size
    """Function to split messages into 30Kb chunks to support websockets"""
    chunks = []
    current_chunk = []
    current_chunk_size = 0

    for msg in message:
        msg_json = json.dumps({'role': msg['role'], 'content': msg['content'], 'timestamp': msg['timestamp'], 'message_id': msg['message_id']})
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

def process_bedrock_response(response_stream, prompt, connection_id, user_id, model_provider, model_name):
    """Function to process a bedrock response and send the messages back to the websocket"""
    result_text = ""
    current_input_tokens = 0
    current_output_tokens = 0
    counter = 0
    message_end_timestamp_utc = ''
    try:
        for event in response_stream:
            chunk = event.get('chunk', {})
            if chunk.get('bytes'):
                content_chunk = json.loads(chunk['bytes'].decode('utf-8'))

                if model_provider == 'amazon':
                    if 'outputText' in content_chunk:
                        msg_text = content_chunk['outputText']
                        result_text += msg_text
                        if counter == 0:
                            send_websocket_message(connection_id, {
                            'type': 'message_start',
                            'message': {"model": model_name},
                            'delta': {'text': msg_text},
                            'message_id': counter
                            })
                        else:
                            send_websocket_message(connection_id, {
                                'type': 'content_block_delta',
                                'delta': {'text': msg_text},
                                'message_id': counter
                            })
                    # if completionReason exists and is not null or not None
                    if 'completionReason' in content_chunk and content_chunk['completionReason'] is not None:
                        amazon_bedrock_invocation_metrics = content_chunk.get('amazon-bedrock-invocationMetrics', {})
                        current_input_tokens = amazon_bedrock_invocation_metrics.get('inputTokenCount', 0)
                        current_output_tokens = amazon_bedrock_invocation_metrics.get('outputTokenCount', 0)
                        logger.info(f"TokenCounts: {str(current_input_tokens)}/{str(current_output_tokens)}")
                        message_end_timestamp_utc = datetime.now(timezone.utc).isoformat()
                        send_websocket_message(connection_id, {
                            'type': 'message_stop',
                            'timestamp': message_end_timestamp_utc,
                            'message_id': counter,
                            'amazon-bedrock-invocationMetrics': amazon_bedrock_invocation_metrics
                        })
                elif model_provider == 'mistral':
                    iterator_element = 'outputs'
                    if content_chunk['choices']:
                        iterator_element = 'choices'
                    if counter == 0:
                        message_type = 'message_start'
                    else:
                        message_type = 'content_block_delta'
                    for element in content_chunk[iterator_element]:
                        if iterator_element == 'choices':
                            msg_text = element['message']['content']
                        else:    
                            msg_text = element['text']
                        if element['stop_reason']:
                            message_type = 'message_stop'
                    
                    if message_type == 'message_start':
                        result_text += msg_text
                        send_websocket_message(connection_id, {
                            'type': message_type,
                            'message': {"model": model_name},
                            'delta': {'text': msg_text},
                            'message_id': counter
                        })
                    elif message_type == 'content_block_delta':
                        result_text += msg_text
                        send_websocket_message(connection_id, {
                            'type': message_type,
                            'delta': {'text': msg_text},
                            'message_id': counter
                        })
                    elif message_type == 'message_stop':
                        amazon_bedrock_invocation_metrics =  content_chunk.get('amazon-bedrock-invocationMetrics', {})
                        current_input_tokens = amazon_bedrock_invocation_metrics.get('inputTokenCount', 0)
                        current_output_tokens = amazon_bedrock_invocation_metrics.get('outputTokenCount', 0)
                        logger.info(f"TokenCounts: {str(current_input_tokens)}/{str(current_output_tokens)}")
                        # TODO: send update monthly usage tokens
                        # {monthly_input_tokens, monthly_output_tokens} = get_monthly_token_usage(user_id)
                        # Send the message_stop event to the WebSocket client
                        message_end_timestamp_utc = datetime.now(timezone.utc).isoformat()
                        send_websocket_message(connection_id, {
                            'type': message_type,
                            'timestamp': message_end_timestamp_utc,
                            'message_id': counter,
                            'amazon-bedrock-invocationMetrics': content_chunk.get('amazon-bedrock-invocationMetrics', {})
                        })
                elif content_chunk['type'] == 'message_start':
                    # Send the message_start event to the WebSocket client
                    send_websocket_message(connection_id, {
                        'type': 'message_start',
                        'message_id': counter,
                        'message': content_chunk['message']
                    })

                elif content_chunk['type'] == 'content_block_delta':
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
                    amazon_bedrock_invocation_metrics =  content_chunk.get('amazon-bedrock-invocationMetrics', {})
                    current_input_tokens = amazon_bedrock_invocation_metrics.get('inputTokenCount', 0)
                    current_output_tokens = amazon_bedrock_invocation_metrics.get('outputTokenCount', 0)
                    logger.info(f"TokenCounts: {str(current_input_tokens)}/{str(current_output_tokens)}")
                    # TODO: send update monthly usage tokens
                    # {monthly_input_tokens, monthly_output_tokens} = get_monthly_token_usage(user_id)
                    # Send the message_stop event to the WebSocket client
                    message_end_timestamp_utc = datetime.now(timezone.utc).isoformat()
                    send_websocket_message(connection_id, {
                        'type': 'message_stop',
                        'timestamp': message_end_timestamp_utc,
                        'message_id': counter,
                        'amazon-bedrock-invocationMetrics': content_chunk.get('amazon-bedrock-invocationMetrics', {})
                    })
            counter += 1

    except Exception as e:
        logger.error(f"Error processing Bedrock response (9926)")
        logger.exception(e)
        # Send an error message to the WebSocket client
        send_websocket_message(connection_id, {
            'type': 'error',
            'error': str(e)
        })

    return result_text, current_input_tokens, current_output_tokens, message_end_timestamp_utc

def process_bedrock_converse_response(response,selected_model_id,connection_id):
    """Function to process a bedrock response and send the messages back to the websocket for converse API"""
    result_text = ""
    current_input_tokens = 0
    current_output_tokens = 0
    counter = 0
    message_end_timestamp_utc = ''
    stream = response.get('stream')
    if stream:
        for event in stream:
            if 'contentBlockDelta' in event:
                msg_text = event['contentBlockDelta']['delta']['text']
                if counter == 0:
                    send_websocket_message(connection_id, {
                    'type': 'message_start',
                    'message': {"model": selected_model_id},
                    'delta': {'text': msg_text},
                    'message_id': counter
                    })
                else:
                    send_websocket_message(connection_id, {
                        'type': 'content_block_delta',
                        'delta': {'text': msg_text},
                        'message_id': counter
                    })
                result_text += msg_text
                counter += 1
            if 'metadata' in event:
                metadata = event['metadata']
                if 'usage' in metadata:
                    current_input_tokens = metadata['usage']['inputTokens']
                    current_output_tokens = metadata['usage']['outputTokens']
                    
        logger.info(f"TokenCounts (Converse): {str(current_input_tokens)}/{str(current_output_tokens)}")
        # Send the message_stop event to the WebSocket client
        message_end_timestamp_utc = datetime.now(timezone.utc).isoformat()
        send_websocket_message(connection_id, {
            'type': 'message_stop',
            'message_id': counter,
            'timestamp': message_end_timestamp_utc,
            'amazon-bedrock-invocationMetrics': {'inputTokenCount':current_input_tokens,
                                                 'outputTokenCount':current_output_tokens},
        })
        return result_text, current_input_tokens, current_output_tokens, message_end_timestamp_utc
            