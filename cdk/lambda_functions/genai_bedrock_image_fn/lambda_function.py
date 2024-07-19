import json
import boto3
import base64
from botocore.exceptions import ClientError
import uuid
import os
import logging
from aws_lambda_powertools import Tracer

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
        connection_id = event['requestContext']['connectionId']
        
        logger.info(f"Prompt: {prompt}")
        logger.info(f"Connection ID: {connection_id}")

        logger.info("Generating image using Titan Image Generator")
        response = bedrock.invoke_model(
            modelId="amazon.titan-image-generator-v1",
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
                    "width": 512,
                    "height": 512,
                    "seed": 0,
                    "cfgScale": 8.0
                }
            })
        )
        logger.info("Image generation completed")

        response_body = json.loads(response['body'].read())
        image_base64 = response_body['images'][0]

        # Save image to S3 and generate pre-signed URL
        image_url = save_image_to_s3_and_get_url(image_base64)
        logger.info("Image saved to S3 and URL generated")

        logger.info("Sending image URL back to the client")
        send_websocket_message(connection_id, {
            'type': 'image_generated',
            'image_url': image_url
        })
        send_websocket_message(connection_id, {
            'type': 'message_stop',
            'backend_type': 'image_generated'
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

def save_image_to_s3_and_get_url(image_base64):
    # Decode base64 image
    image_data = base64.b64decode(image_base64)
    
    # Generate a unique filename
    filename = f"images/generated_image_{uuid.uuid4()}.png"
    
    # Upload to S3
    s3_client.put_object(Bucket=S3_BUCKET_NAME, Key=filename, Body=image_data, ContentType='image/png')
    
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
