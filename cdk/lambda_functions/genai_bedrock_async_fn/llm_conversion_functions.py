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


def process_bedrock_converse_response(apigateway_management_api, response, selected_model_id, connection_id, converse_content_with_s3_pointers,new_conversation,session_id):
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
                        'session_id':session_id,
                        'delta': {'text': msg_text},
                        'message_counter': counter
                    })
                else:
                    if current_time - start_time <= 20:  # First 20 seconds
                        # Send messages immediately
                        commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                            'type': 'content_block_delta',
                            'session_id':session_id,
                            'delta': {'text': msg_text},
                            'message_counter': counter
                        })
                    else:  # After 20 seconds
                        buffer.append(msg_text)
                        # Send combined messages once per second
                        if current_time - last_send_time >= 1 and buffer:
                            combined_text = ''.join(buffer)
                            commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                                'type': 'content_block_delta',
                                'session_id':session_id,
                                'delta': {'text': combined_text},
                                'message_counter': counter
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
                'session_id':session_id,
                'delta': {'text': combined_text},
                'message_counter': counter
            })
        
        logger.info(f"TokenCounts (Converse): {str(current_input_tokens)}/{str(current_output_tokens)}")
        # Send the message_stop event to the WebSocket client
        message_end_timestamp_utc = datetime.now(timezone.utc).isoformat()
        commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
            'type': 'message_stop',
            'session_id':session_id,
            'message_counter': counter,
            'new_conversation': new_conversation,
            'timestamp': message_end_timestamp_utc,
            'converse_content_with_s3_pointers': converse_content_with_s3_pointers,
            'amazon-bedrock-invocationMetrics': {
                'inputTokenCount': current_input_tokens,
                'outputTokenCount': current_output_tokens
            },
        })
        
        return result_text, current_input_tokens, current_output_tokens, message_end_timestamp_utc
    
    
def process_bedrock_converse_response_for_title(response):
    """Function to process a bedrock title response for converse API"""
    result_text = ""
    stream = response.get('stream')
    if stream:
        for event in stream:
            if 'contentBlockDelta' in event:
                result_text += event['contentBlockDelta']['delta']['text']
                
        
    try:
        # Parse the JSON string into a Python dictionary
        json_result = json.loads(result_text)
        return json_result
    except json.JSONDecodeError as e:
        # Handle the case where the string is not valid JSON
        print(f"Error(0901) parsing JSON: {e}")
        print(f"Original result_text: {result_text}")
        return None
