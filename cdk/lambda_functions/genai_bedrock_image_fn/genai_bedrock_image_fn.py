import json,boto3,base64,uuid,os
from datetime import datetime, timezone
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger, Metrics, Tracer
from botocore.config import Config
from chatbot_commons import commons
from conversations import conversations
import random
import copy
import jwt

logger = Logger(service="BedrockImage")
metrics = Metrics()
tracer = Tracer()

config = Config(
    retries={
        'total_max_attempts': 20,
        'mode': 'standard'
    }
)
bedrock_runtime = boto3.client('bedrock-runtime',config=config)
WEBSOCKET_API_ENDPOINT = os.environ['WEBSOCKET_API_ENDPOINT']
s3_client = boto3.client('s3')
dynamodb = boto3.client('dynamodb')
image_bucket = os.environ['S3_IMAGE_BUCKET_NAME']
conversations_table_name = os.environ['CONVERSATIONS_DYNAMODB_TABLE']
conversations_table = boto3.resource('dynamodb').Table(conversations_table_name)
conversation_history_bucket = os.environ['CONVERSATION_HISTORY_BUCKET']

apigateway_management_api = boto3.client('apigatewaymanagementapi', 
                                         endpoint_url=f"{WEBSOCKET_API_ENDPOINT.replace('wss', 'https')}/ws")

@tracer.capture_lambda_handler
def lambda_handler(event, context):
    """Lambda Handler Function"""
    try:
        access_token = event.get('access_token', {})
        session_id = event.get('session_id', 'XYZ')
        connection_id = event.get('connection_id', 'ZYX')
        user_id = access_token['payload']['sub']
        message_type = event.get('type', '')
        selected_mode = event.get('selected_mode', {})
        selected_model_category = selected_mode.get('category')
        prompt = event.get('prompt', '')
        model_id = selected_mode.get('modelId','')
        # if prompt length is < 3 then prepend text 'image of '
        if len(prompt) < 3:
            prompt = 'image of ' + prompt
        chat_title = prompt[:16] if len(prompt) > 16 else prompt
        
        style_preset = event.get('stylePreset', 'photographic')
        height_width = event.get('heightWidth', '1024x1024')
        height, width = map(int, height_width.split('x'))
        message_id = event.get('message_id', None)
        message_received_timestamp_utc = event.get('timestamp', datetime.now(timezone.utc).isoformat())
        if message_type == 'clear_conversation':
            # logger.info(f'Action: Clear Conversation {session_id}')
            # Delete the conversation history from DynamoDB
            commons.delete_s3_attachments_for_session(session_id,image_bucket,user_id,'images',s3_client, logger)
            conversations.delete_conversation_history(dynamodb,conversations_table_name,logger,session_id)
            return
        elif message_type == 'load':
            # Load conversation history from DynamoDB
            conversations.load_and_send_conversation_history(session_id, connection_id, user_id, dynamodb,conversations_table_name,s3_client,conversation_history_bucket,logger, commons,apigateway_management_api)
            return
        #if model_id contains titan or nova then
        if 'titan' in model_id or 'nova' in model_id:
            image_base64,success_status,error_message = commons.generate_image_titan_nova(logger,bedrock_runtime,model_id, prompt, width, height,None)
        elif 'stability' in model_id:
            image_base64,success_status,error_message = commons.generate_image_stable_diffusion(logger,bedrock_runtime,model_id, prompt, width, height, style_preset,None,None)
        else:
            raise ValueError(f"Unsupported model: {model_id}")
        
        needs_load_from_s3, chat_title_loaded, original_existing_history = conversations.query_existing_history(dynamodb,conversations_table_name,logger,session_id)
        existing_history = copy.deepcopy(original_existing_history)
        new_conversation = bool(not existing_history or len(existing_history) == 0)
        persisted_chat_title = chat_title_loaded if chat_title_loaded and chat_title_loaded.strip() else chat_title
        
        if not success_status:
            commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                'type': 'message_start',
                'message': {"model": model_id},
                'session_id':session_id,
                'delta': {'text': error_message},
                'message_counter': 0
            })
            commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                    'type': 'message_title',
                    'message_id': message_id,
                    'session_id':session_id,
                    'title': persisted_chat_title
                })
            message_end_timestamp_utc = datetime.now(timezone.utc).isoformat()
            commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                'type': 'message_stop',
                'session_id':session_id,
                'message_counter': 1,
                'new_conversation': True,
                'timestamp': message_end_timestamp_utc,
                'amazon_bedrock_invocation_metrics': {
                    'inputTokenCount': 0,
                    'outputTokenCount': 0
                },
            })
            return {'statusCode': 200, 'body': json.dumps(f"Image Generation failed due to: {error_message}")}
        # Save image to S3 and generate pre-signed URL
        image_url = save_image_to_s3_and_get_url(image_base64,user_id,session_id)
        # logger.info("Image saved to S3 and URL generated")
        commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
            'type': 'image_generated',
            'image_url': image_url,
            'prompt': prompt,
            'modelId': model_id,
            'message_id': message_id,
            'session_id':session_id,
            'timestamp': message_received_timestamp_utc,
        })
        
        
        
        commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
            'type': 'message_title',
            'message_id': message_id,
            'session_id':session_id,
            'title': persisted_chat_title
        })
        # set new string variable message_end_timestand as current UTC timestamp in this format: 9/9/2024, 6:58:45 AM
        commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
            'type': 'message_stop',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'modelId': model_id,
            'new_conversation': new_conversation,
            'session_id':session_id,
            'backend_type': 'image_generated',
            'message_id': message_id,
        })
        store_bedrock_images_response(prompt,image_url, existing_history, message_id, session_id,user_id, model_id,selected_model_category, persisted_chat_title)

        # logger.info("Image URL sent successfully")
        return {'statusCode': 200, 'body': json.dumps('Image generated successfully')}

    except Exception as e:
        logger.exception(e)
        logger.error(f"Error generating image: {str(e)}", exc_info=True)
        commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
            'type': 'error',
            'error': str(e)
        })
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}

def save_image_to_s3_and_get_url(image_base64,user_id,session_id):
    # Decode base64 image
    image_data = base64.b64decode(image_base64)
    # Current DateTime String YYYYMMDDHH24mmss
    current_datetime = datetime.now().strftime("%Y%m%d%H%M%S")
    prefix = rf'{user_id}/{session_id}'
    # Generate a unique filename
    filename = f"images/{prefix}/generated_image_{current_datetime}_{uuid.uuid4()}.png"
    
    # Upload to S3 with expiration metadata
    s3_client.put_object(
        Bucket=image_bucket,
        Key=filename,
        Body=image_data,
        ContentType='image/png',
    )
    
    # Generate CloudFront URL
    cloudfront_url = f"https://{os.environ['CLOUDFRONT_DOMAIN']}/{filename}"
    
    return cloudfront_url

def store_bedrock_images_response(prompt,image_url, existing_history, message_id, session_id,user_id, model_id,selected_model_category, chat_title):
    conversation_history = existing_history + [
        {
            'role': 'user',
            'content': [{'text': prompt}],
            'timestamp': datetime.now(tz=timezone.utc).isoformat(),
            'message_id': message_id
        },
        {
            "role": "assistant",
            "content": image_url,
            'timestamp': datetime.now(tz=timezone.utc).isoformat(),
            "model": model_id,
            "isImage": True,
            "imageAlt": prompt,
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