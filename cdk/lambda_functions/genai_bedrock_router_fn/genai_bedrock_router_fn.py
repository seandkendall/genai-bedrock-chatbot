import json
import boto3
import os
from chatbot_commons import commons
from aws_lambda_powertools import Logger, Metrics, Tracer

logger = Logger(service="BedrockRouter")
metrics = Metrics()
tracer = Tracer()

lambda_client = boto3.client('lambda')
cognito_client = boto3.client('cognito-idp')
agents_function_name = os.environ['AGENTS_FUNCTION_NAME']
bedrock_function_name = os.environ['BEDROCK_FUNCTION_NAME']
user_pool_id = os.environ['USER_POOL_ID']
region = os.environ['REGION']
allowlist_domain = os.environ['ALLOWLIST_DOMAIN']
image_generation_function_name = os.environ['IMAGE_GENERATION_FUNCTION_NAME']
user_cache = {}


@tracer.capture_lambda_handler
def lambda_handler(event, context):
    try:
        request_body = json.loads(event['body'])
    except (ValueError, KeyError):
        # Handle the case where the request body is not valid JSON or does not contain the 'body' key
        request_body = {}
    selected_mode = request_body.get('selectedMode', 'none')
    response_message = 'Message Received'
    message_type = request_body.get('type', '')
    access_token = request_body.get('accessToken', 'none')
    allowed, not_allowed_message = commons.validate_jwt_token(cognito_client, user_cache,allowlist_domain,access_token)
    if allowed:
        if selected_mode.get('category') == 'Bedrock Agents' or selected_mode.get('category') == 'Bedrock KnowledgeBases':
            # Invoke genai_bedrock_agents_client_fn
            if message_type == 'load':
                response_message = 'no_conversation_to_load'
            if message_type != 'load' and message_type != 'clear_conversation':
                lambda_client.invoke(FunctionName=agents_function_name, InvocationType='Event', Payload=json.dumps(event))
            # Process the response from agents_client_function
        elif selected_mode.get('category') == 'Bedrock Models':
            # Invoke genai_bedrock_async_fn
            lambda_client.invoke(FunctionName=bedrock_function_name, InvocationType='Event', Payload=json.dumps(event))
            # Process the response from lambda_fn_async
        elif selected_mode.get('category') == 'Bedrock Image Models':
            # Invoke image generation function
            if message_type == 'load':
                response_message = 'no_conversation_to_load'
            if message_type != 'load':
                lambda_client.invoke(FunctionName=image_generation_function_name, InvocationType='Event', Payload=json.dumps(event))
        elif selected_mode.get('category') == 'Bedrock Prompt Flows':
            if message_type == 'load':
                response_message = 'no_conversation_to_load'
        else:
            return {
                'statusCode': 404,
                'body': json.dumps('Endpoint Not Found')
            }
        return {
            'statusCode': 200,
            'body': json.dumps(response_message)
        }
    else:
        return {
            'statusCode': 403,
            'body': json.dumps(not_allowed_message)
        }