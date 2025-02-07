import json
import boto3
import os
from chatbot_commons import commons
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger, Metrics, Tracer

logger = Logger(service="BedrockRouter")
metrics = Metrics()
tracer = Tracer()

lambda_client = boto3.client('lambda')
cognito_client = boto3.client('cognito-idp')
agents_function_name = os.environ['AGENTS_FUNCTION_NAME']
conversations_list_function_name = os.environ['CONVERSATIONS_LIST_FUNCTION_NAME']
bedrock_function_name = os.environ['BEDROCK_FUNCTION_NAME']
user_pool_id = os.environ['USER_POOL_ID']
region = os.environ['REGION']
allowlist_domain = os.environ['ALLOWLIST_DOMAIN']
image_generation_function_name = os.environ['IMAGE_GENERATION_FUNCTION_NAME']
video_generation_function_name = os.environ['VIDEO_GENERATION_FUNCTION_NAME']
WEBSOCKET_API_ENDPOINT = os.environ['WEBSOCKET_API_ENDPOINT']

"""
Bedrock Router Function

This is the first function to be called via websocket.  It will parse the message and determine
which lambda function to call next, based on the selectedMode.category field in the input json

You can see an example of the input json at /sample-json/1-message-from-browser.json

"""

@tracer.capture_lambda_handler
def lambda_handler(event, context):
    """Lambda Hander Function"""
    if 'body' in event:
        event_body = json.loads(event['body'])
        if event_body['type'] == 'ping':
            return {'statusCode': 200, 'body': json.dumps({'type':'pong','connection_id': event['requestContext']['connectionId']})}

    # for each record
    for record in event['Records']:
        request_body = json.loads(record['body'])
        message_type = request_body.get('type', '')
        connection_id = request_body.get('connection_id', '')
        session_id = request_body.get('session_id', '')
        selected_mode = request_body.get('selected_mode', {})
        route_request(request_body,message_type,selected_mode)
        # log all attribute/variable values
        # print(f"message_type: {message_type} connection_id: {connection_id} session_id: {session_id} selected_mode: {selected_mode}")
        
def route_request(request_body,message_type,selected_mode):    
    if message_type == 'load_conversation_list':
        lambda_client.invoke(FunctionName=conversations_list_function_name, InvocationType='Event', Payload=json.dumps(request_body))
    elif selected_mode.get('category') == 'Bedrock Agents' or selected_mode.get('category') == 'Bedrock KnowledgeBases' or selected_mode.get('category') == 'Bedrock Prompt Flows':
        lambda_client.invoke(FunctionName=agents_function_name, InvocationType='Event', Payload=json.dumps(request_body))
        # Process the response from agents_client_function
    elif selected_mode.get('category') == 'Bedrock Models':
        # Invoke genai_bedrock_async_fn
        lambda_client.invoke(FunctionName=bedrock_function_name, InvocationType='Event', Payload=json.dumps(request_body))
    elif selected_mode.get('category') == 'Imported Models':
        # Invoke genai_bedrock_async_fn
        lambda_client.invoke(FunctionName=bedrock_function_name, InvocationType='Event', Payload=json.dumps(request_body))
    elif selected_mode.get('category') == 'Bedrock Image Models':
        lambda_client.invoke(FunctionName=image_generation_function_name, InvocationType='Event', Payload=json.dumps(request_body))
    elif selected_mode.get('category') == 'Bedrock Video Models':
        lambda_client.invoke(FunctionName=video_generation_function_name, InvocationType='Event', Payload=json.dumps(request_body))