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
    conversation_items = get_conversation_list_from_dynamodb_conversation_history_table(user_id)
    commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                    'type': 'load_conversation_list',
                    'conversation_list': conversation_items,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                })
    return {'statusCode': 200}

@tracer.capture_method
def get_conversation_list_from_dynamodb_conversation_history_table(user_id):
    """Function to get conversation list from DynamoDB, sorted by last_modified_date desc."""
    try:
        response = conversations_table.query(
            IndexName='user_id-index',
            KeyConditionExpression=Key('user_id').eq(user_id),
            ProjectionExpression="#session_id, #selected_model_id, #last_modified_date, #title, #category,#kb_session_id,#selected_knowledgebase_id,#flow_id,#flow_alias_id,#selected_agent_id,#selected_agent_alias_id",
            ExpressionAttributeNames={
                "#session_id": "session_id",
                "#title":"title",
                "#selected_model_id": "selected_model_id",
                "#last_modified_date": "last_modified_date",
                "#category": "category",
                "#kb_session_id":"kb_session_id",
                "#selected_knowledgebase_id":"selected_knowledgebase_id",
                "#flow_id": "flow_id",
                "#flow_alias_id": "flow_alias_id",
                "#selected_agent_id": "selected_agent_id",
                "#selected_agent_alias_id": "selected_agent_alias_id"
            },
            ScanIndexForward=False
        )
        # Return an empty list if no items are found
        return response.get('Items', [])
    except Exception as e:
        logger.exception(e)
        logger.error("Error querying DynamoDB (7266)")
        return []