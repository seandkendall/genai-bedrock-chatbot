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
from datetime import datetime, timezone
from botocore.exceptions import ClientError
#use AWS powertools for logging
from aws_lambda_powertools import Logger, Metrics, Tracer
logger = Logger(service="BedrockAsync")
metrics = Metrics()
tracer = Tracer()


# Initialize DynamoDB client
dynamodb = boto3.client('dynamodb')
config_table_name = os.environ.get('DYNAMODB_TABLE_CONFIG')
config_table = boto3.resource('dynamodb').Table(config_table_name)
s3_client = boto3.client('s3')
conversation_history_bucket = os.environ['CONVERSATION_HISTORY_BUCKET']
conversations_table_name = os.environ['CONVERSATIONS_DYNAMODB_TABLE']
conversations_table = boto3.resource('dynamodb').Table(conversations_table_name)
attachment_bucket = os.environ['ATTACHMENT_BUCKET']
image_bucket = os.environ['S3_IMAGE_BUCKET_NAME']
WEBSOCKET_API_ENDPOINT = os.environ['WEBSOCKET_API_ENDPOINT']
usage_table_name = os.environ['DYNAMODB_TABLE_USAGE']
region = os.environ['REGION']

# AWS API Gateway Management API client
apigateway_management_api = boto3.client('apigatewaymanagementapi', endpoint_url=f"{WEBSOCKET_API_ENDPOINT.replace('wss', 'https')}/ws")


@tracer.capture_lambda_handler
def lambda_handler(event, context): 
    """Lambda Hander Function"""
    request_body = json.loads(event['body'])
    id_token = request_body.get('idToken', 'none')
    decoded_token = jwt.decode(id_token, algorithms=["RS256"], options={"verify_signature": False})
    user_id = decoded_token['cognito:username']
    connection_id = event['requestContext']['connectionId']
    get_conversation_list_from_dynamodb_conversation_history_bucket(user_id)

    return {'statusCode': 200}

@tracer.capture_method
def get_conversation_list_from_dynamodb_conversation_history_bucket(user_id):
    """Function to get conversation list from DynamoDB, sorted by last_modified_date desc."""
    try:
        response = conversations_table.query(
            IndexName='user_id-index',
            KeyConditionExpression=Key('user_id').eq(user_id),
            ProjectionExpression="#session_id, #selected_model_id, #last_modified_date, #title",
            ExpressionAttributeNames={
                "#session_id": "session_id",
                "#title":"title",
                "#selected_model_id": "selected_model_id",
                "#last_modified_date": "last_modified_date",
            },
            ScanIndexForward=False
        )
        # Return an empty list if no items are found
        return response.get('Items', [])
    except Exception as e:
        logger.exception(e)
        logger.error("Error querying DynamoDB (7266)")
        return []

@tracer.capture_method
def process_websocket_message(event):
    """Function to process a websocket message"""
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