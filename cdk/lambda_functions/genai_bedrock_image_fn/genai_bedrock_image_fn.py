import json,boto3,base64,uuid,os
from datetime import datetime, timezone
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger, Metrics, Tracer
from chatbot_commons import commons
from conversations import conversations
import random
import copy
import jwt

logger = Logger(service="BedrockImage")
metrics = Metrics()
tracer = Tracer()


bedrock_runtime = boto3.client(service_name="bedrock-runtime")
WEBSOCKET_API_ENDPOINT = os.environ['WEBSOCKET_API_ENDPOINT']
s3_client = boto3.client('s3')
dynamodb = boto3.client('dynamodb')
S3_BUCKET_NAME = os.environ['S3_IMAGE_BUCKET_NAME']
conversations_table_name = os.environ['CONVERSATIONS_DYNAMODB_TABLE']
conversations_table = boto3.resource('dynamodb').Table(conversations_table_name)

apigateway_management_api = boto3.client('apigatewaymanagementapi', 
                                         endpoint_url=f"{WEBSOCKET_API_ENDPOINT.replace('wss', 'https')}/ws")

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
        session_id = request_body.get('session_id', 'XYZ')
        model_id = selected_mode.get('modelId','')
        # if prompt length is < 3 then prepend text 'image of '
        if len(prompt) < 3:
            prompt = 'image of ' + prompt
        chat_title = prompt[:16] if len(prompt) > 16 else prompt
        connection_id = event['requestContext']['connectionId']
        style_preset = request_body.get('stylePreset', 'photographic')
        height_width = request_body.get('heightWidth', '1024x1024')
        height, width = map(int, height_width.split('x'))
        message_id = request_body.get('message_id', None)
        message_received_timestamp_utc = request_body.get('timestamp', datetime.now(timezone.utc).isoformat())
        #if model_id contains titan then
        if 'titan' in model_id:
            image_base64 = commons.generate_image_titan(logger,bedrock_runtime,model_id, prompt, width, height,None)
        elif 'stability' in model_id:
            image_base64 = commons.generate_image_stable_diffusion(logger,bedrock_runtime,model_id, prompt, width, height, style_preset,None,None)
        else:
            raise ValueError(f"Unsupported model: {model_id}")

        # Save image to S3 and generate pre-signed URL
        image_url = save_image_to_s3_and_get_url(image_base64)
        # logger.info("Image saved to S3 and URL generated")
        commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
            'type': 'image_generated',
            'image_url': image_url,
            'prompt': prompt,
            'modelId': model_id,
            'message_id': message_id,
            'timestamp': message_received_timestamp_utc,
        })
        needs_load_from_s3, chat_title_loaded, original_existing_history = conversations.query_existing_history(dynamodb,conversations_table_name,logger,session_id)
        existing_history = copy.deepcopy(original_existing_history)
        new_conversation = bool(not existing_history or len(existing_history) == 0)
        persisted_chat_title = chat_title_loaded if chat_title_loaded and chat_title_loaded.strip() else chat_title
        
        
        commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
            'type': 'message_title',
            'message_id': message_id,
            'title': persisted_chat_title
        })
        # set new string variable message_end_timestand as current UTC timestamp in this format: 9/9/2024, 6:58:45 AM
        commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
            'type': 'message_stop',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'modelId': model_id,
            'new_conversation': new_conversation,
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

def save_image_to_s3_and_get_url(image_base64):
    # Decode base64 image
    image_data = base64.b64decode(image_base64)
    
    # Generate a unique filename
    filename = f"images/generated_image_{uuid.uuid4()}.png"
    
    # Upload to S3 with expiration metadata
    s3_client.put_object(
        Bucket=S3_BUCKET_NAME,
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