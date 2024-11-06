import random
import string
import json
import os
import boto3
from time import time
from collections import deque
from chatbot_commons import commons
from datetime import datetime, timezone
from aws_lambda_powertools import Logger
logger = Logger(service="BedrockAsyncLLMFunctions")
WEBSOCKET_API_ENDPOINT = os.environ['WEBSOCKET_API_ENDPOINT']
        
def process_message_history_converse(existing_history):
    """Function to process message history for converse"""
    normalized_history = []
    for message in existing_history:
        role = message.get('role')
        content = message.get('content')
        if role in ['user', 'assistant']:
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

from time import time
from collections import deque

def process_bedrock_converse_response(apigateway_management_api, response, selected_model_id, connection_id, converse_content_with_s3_pointers):
    """Function to process a bedrock response and send the messages back to the websocket for converse API"""
    result_text = ""
    current_input_tokens = 0
    current_output_tokens = 0
    counter = 0
    message_end_timestamp_utc = ''
    stream = response.get('stream')
    
    if stream:
        start_time = time()
        buffer = deque()
        last_send_time = start_time
        
        for event in stream:
            if 'contentBlockDelta' in event:
                current_time = time()
                msg_text = event['contentBlockDelta']['delta']['text']
                
                if counter == 0:
                    # Always send the first message immediately
                    commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                        'type': 'message_start',
                        'message': {"model": selected_model_id},
                        'delta': {'text': msg_text},
                        'message_id': counter
                    })
                else:
                    if current_time - start_time <= 5:  # First 5 seconds
                        # Send messages immediately
                        commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                            'type': 'content_block_delta',
                            'delta': {'text': msg_text},
                            'message_id': counter
                        })
                    else:  # After 5 seconds
                        buffer.append(msg_text)
                        # Send combined messages once per second
                        if current_time - last_send_time >= 1 and buffer:
                            combined_text = ''.join(buffer)
                            commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                                'type': 'content_block_delta',
                                'delta': {'text': combined_text},
                                'message_id': counter
                            })
                            buffer.clear()
                            last_send_time = current_time
                
                result_text += msg_text
                counter += 1
                
            if 'metadata' in event:
                metadata = event['metadata']
                if 'usage' in metadata:
                    current_input_tokens = metadata['usage']['inputTokens']
                    current_output_tokens = metadata['usage']['outputTokens']
        
        # Send any remaining buffered messages
        if buffer:
            combined_text = ''.join(buffer)
            commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                'type': 'content_block_delta',
                'delta': {'text': combined_text},
                'message_id': counter
            })
        
        logger.info(f"TokenCounts (Converse): {str(current_input_tokens)}/{str(current_output_tokens)}")
        # Send the message_stop event to the WebSocket client
        message_end_timestamp_utc = datetime.now(timezone.utc).isoformat()
        commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
            'type': 'message_stop',
            'message_id': counter,
            'timestamp': message_end_timestamp_utc,
            'converse_content_with_s3_pointers': converse_content_with_s3_pointers,
            'amazon-bedrock-invocationMetrics': {
                'inputTokenCount': current_input_tokens,
                'outputTokenCount': current_output_tokens
            },
        })
        
        return result_text, current_input_tokens, current_output_tokens, message_end_timestamp_utc
