import json
import os
import time
import random
import jwt
import copy
from datetime import datetime, timezone
import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from chatbot_commons import commons
from conversations import conversations

logger = Logger(service="BedrockVideo")
metrics = Metrics()
tracer = Tracer()

bedrock_runtime = boto3.client(service_name="bedrock-runtime")
WEBSOCKET_API_ENDPOINT = os.environ['WEBSOCKET_API_ENDPOINT']
s3_client = boto3.client('s3')
dynamodb = boto3.client('dynamodb')
video_bucket = os.environ['S3_IMAGE_BUCKET_NAME']
cloudfront_domain = os.environ['CLOUDFRONT_DOMAIN']
conversations_table_name = os.environ['CONVERSATIONS_DYNAMODB_TABLE']
conversations_table = boto3.resource('dynamodb').Table(conversations_table_name)
conversation_history_bucket = os.environ['CONVERSATION_HISTORY_BUCKET']

apigateway_management_api = boto3.client('apigatewaymanagementapi', 
                                         endpoint_url=f"{WEBSOCKET_API_ENDPOINT.replace('wss', 'https')}/ws")

SLEEP_TIME = 2

@tracer.capture_lambda_handler
def lambda_handler(event, context):
    """Lambda Handler Function"""
    try:
        request_body = json.loads(event['body'])
        prompt = request_body.get('prompt', '')
        id_token = request_body.get('idToken', 'none')
        decoded_token = jwt.decode(id_token, algorithms=["RS256"], options={"verify_signature": False})
        user_id = decoded_token['cognito:username']
        selected_mode = request_body.get('selectedMode', 'none')
        selected_model_category = selected_mode.get('category')
        message_type = request_body.get('type', '')
        session_id = request_body.get('session_id', 'XYZ')
        model_id = selected_mode.get('modelId', 'amazon.nova-reel-v1:0')
        
        if len(prompt) < 3:
            prompt = 'Video of ' + prompt
        
        chat_title = prompt[:16] if len(prompt) > 16 else prompt
        connection_id = event['requestContext']['connectionId']
        message_id = request_body.get('message_id', None)
        message_received_timestamp_utc = request_body.get('timestamp', datetime.now(timezone.utc).isoformat())
        if message_type == 'clear_conversation':
            commons.delete_s3_attachments_for_session(session_id,video_bucket,user_id,'videos',s3_client, logger)
            conversations.delete_conversation_history(dynamodb,conversations_table_name,logger,session_id)
            return
        elif message_type == 'load':
            # Load conversation history from DynamoDB
            conversations.load_and_send_conversation_history(session_id, connection_id, user_id, dynamodb,conversations_table_name,s3_client,conversation_history_bucket,logger, commons,apigateway_management_api)
            return
        duration_seconds = 6
        seed = random.randint(0, 2147483648)
        video_url, success_status, error_message = commons.generate_video(prompt, model_id,user_id,session_id,bedrock_runtime,s3_client,video_bucket,SLEEP_TIME,logger, cloudfront_domain,duration_seconds,seed)
        
        needs_load_from_s3, chat_title_loaded, original_existing_history = conversations.query_existing_history(dynamodb, conversations_table_name, logger, session_id)
        existing_history = copy.deepcopy(original_existing_history)
        new_conversation = bool(not existing_history or len(existing_history) == 0)
        persisted_chat_title = chat_title_loaded if chat_title_loaded and chat_title_loaded.strip() else chat_title
        
        if not success_status:
            commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                'type': 'message_start',
                'message': {"model": model_id},
                'session_id': session_id,
                'delta': {'text': error_message},
                'message_counter': 0
            })
            commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                'type': 'message_title',
                'message_id': message_id,
                'title': persisted_chat_title
            })
            message_end_timestamp_utc = datetime.now(timezone.utc).isoformat()
            commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                'type': 'message_stop',
                'session_id': session_id,
                'message_counter': 1,
                'new_conversation': True,
                'timestamp': message_end_timestamp_utc,
                'amazon_bedrock_invocation_metrics': {
                    'inputTokenCount': 0,
                    'outputTokenCount': 0
                },
            })
            return {'statusCode': 200, 'body': json.dumps(f"Video Generation failed due to: {error_message}")}
        
        commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
            'type': 'video_generated',
            'video_url': video_url,
            'prompt': prompt,
            'modelId': model_id,
            'message_id': message_id,
            'timestamp': message_received_timestamp_utc,
        })
        
        commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
            'type': 'message_title',
            'message_id': message_id,
            'title': persisted_chat_title
        })
        
        commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
            'type': 'message_stop',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'modelId': model_id,
            'new_conversation': new_conversation,
            'backend_type': 'video_generated',
            'message_id': message_id,
        })
        
        store_bedrock_videos_response(prompt, video_url, existing_history, message_id, session_id, user_id, model_id, selected_model_category, persisted_chat_title)

        return {'statusCode': 200, 'body': json.dumps('Video generated successfully')}

    except Exception as e:
        logger.exception(e)
        logger.error(f"Error generating video: {str(e)}", exc_info=True)
        commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
            'type': 'error',
            'error': str(e)
        })
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}

def store_bedrock_videos_response(prompt, video_url, existing_history, message_id, session_id, user_id, model_id, selected_model_category, chat_title):
    """Stores the bedrock video conversation """
    conversation_history = existing_history + [
        {
            'role': 'user',
            'content': [{'text': prompt}],
            'timestamp': datetime.now(tz=timezone.utc).isoformat(),
            'message_id': message_id
        },
        {
            "role": "assistant",
            "content": video_url,
            'timestamp': datetime.now(tz=timezone.utc).isoformat(),
            "model": model_id,
            "isVideo": True,
            "videoAlt": prompt,
            "prompt": prompt,
            "message_id": commons.generate_random_string()
        }
    ]
    conversation_json = json.dumps(conversation_history)
    current_timestamp = str(datetime.now(tz=timezone.utc).timestamp())
    item_value = {
            'session_id': {'S': session_id},
            'user_id': {'S': user_id},
            'title': {'S': chat_title},
            'last_modified_date': {'N': current_timestamp},
            'selected_model_id': {'S': model_id},
            'category': {'S': selected_model_category},
            'conversation_history': {'S': conversation_json},
            'conversation_history_in_s3': {'BOOL': False}
        }
    dynamodb.put_item(
        TableName=conversations_table_name,
        Item=item_value
    )