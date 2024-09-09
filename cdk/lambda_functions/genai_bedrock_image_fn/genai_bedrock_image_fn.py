import json
import boto3
import base64
import uuid
import os
import logging
from datetime import datetime
from aws_lambda_powertools import Tracer
from django.utils import timezone

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

bedrock = boto3.client(service_name="bedrock-runtime")
WEBSOCKET_API_ENDPOINT = os.environ['WEBSOCKET_API_ENDPOINT']
s3_client = boto3.client('s3')
S3_BUCKET_NAME = os.environ['S3_IMAGE_BUCKET_NAME']
tracer = Tracer()

apigateway_management_api = boto3.client('apigatewaymanagementapi', endpoint_url=f"{WEBSOCKET_API_ENDPOINT.replace('wss', 'https')}/ws")

@tracer.capture_lambda_handler
def lambda_handler(event, context):
    logger.info(f"Received event: {json.dumps(event)}")
    try:
        request_body = json.loads(event['body'])
        prompt = request_body.get('prompt', '')
        # if prompt length is < 3 then prepend text 'image of '
        if len(prompt) < 3:
            prompt = 'image of ' + prompt
        connection_id = event['requestContext']['connectionId']
        modelId = request_body.get('imageModel', 'amazon.titan-image-generator-v2:0')
        stylePreset = request_body.get('stylePreset', 'photographic')
        heightWidth = request_body.get('heightWidth', '1024x1024')
        height, width = map(int, heightWidth.split('x'))
        message_id = request_body.get('message_id', None)
        message_received_timestamp_utc = request_body.get('timestamp', datetime.now(timezone.utc).isoformat())
        #if modelId contains titan then 
        if 'titan' in modelId:
            image_base64 = generate_image_titan(modelId, prompt, width, height)
        elif 'stable' in modelId:
            image_base64 = generate_image_stable_diffusion(modelId, prompt, width, height, stylePreset)
        else:
            raise ValueError(f"Unsupported model: {modelId}")

        # Save image to S3 and generate pre-signed URL
        image_url = save_image_to_s3_and_get_url(image_base64)
        logger.info("Image saved to S3 and URL generated")
        send_websocket_message(connection_id, {
            'type': 'image_generated',
            'image_url': image_url,
            'prompt': prompt,
            'modelId': modelId,
            'message_id': message_id,
            'timestamp': message_received_timestamp_utc,
        })
        # set new string variable message_end_timestand as current UTC timestamp in this format: 9/9/2024, 6:58:45 AM
        send_websocket_message(connection_id, {
            'type': 'message_stop',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'modelId': modelId,
            'backend_type': 'image_generated',
            'message_id': message_id,
        })

        logger.info("Image URL sent successfully")
        return {'statusCode': 200, 'body': json.dumps('Image generated successfully')}

    except Exception as e:
        logger.error(f"Error generating image: {str(e)}", exc_info=True)
        send_websocket_message(connection_id, {
            'type': 'error',
            'error': str(e)
        })
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}

def generate_image_titan(modelId, prompt, width, height):
    logger.info("Generating image using Titan Image Generator")
    response = bedrock.invoke_model(
        modelId=modelId,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "taskType": "TEXT_IMAGE",
            "textToImageParams": {
                "text": prompt,
                "negativeText": "low quality, blurry",
            },
            "imageGenerationConfig": {
                "numberOfImages": 1,
                "width": width,
                "height": height,
                "seed": 0,
                "cfgScale": 8.0
            }
        })
    )
    response_body = json.loads(response['body'].read())
    return response_body['images'][0]

def generate_image_stable_diffusion(modelId, prompt, width, height, style_preset):
    # write log printing modelId
    logger.info(f"Generating image using Model ID: {modelId}")
    # if modelId contains sd3-large
    if 'stable-diffusion-xl-v1' not in modelId:
            response = bedrock.invoke_model(
            modelId=modelId,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "prompt": prompt,
                "seed": 0,
            })
        )
    else:
        response = bedrock.invoke_model(
            modelId=modelId,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "text_prompts": [{"text": prompt}],
                "cfg_scale": 10,
                "seed": 0,
                "steps": 30,
                "width": width,
                "height": height,
                "style_preset": style_preset
            })
        )
    response_body = json.loads(response['body'].read())
    return response_body['artifacts'][0]['base64']

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

@tracer.capture_method
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
        logger.error(f"Error sending WebSocket message (92012): {str(e)}")
