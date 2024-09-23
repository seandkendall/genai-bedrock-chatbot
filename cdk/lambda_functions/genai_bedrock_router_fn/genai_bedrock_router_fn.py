import json, boto3, os
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
    message_type = request_body.get('type', '')
    id_token = request_body.get('idToken', 'none')
    access_token = request_body.get('accessToken', 'none')
    allowed, not_allowed_message = validate_jwt_token(id_token, access_token)
    if allowed:
        if selected_mode.get('category') == 'Bedrock Agents' or selected_mode.get('category') == 'Bedrock KnowledgeBases':
            # Invoke genai_bedrock_agents_client_fn
            if message_type != 'load' and message_type != 'clear_conversation':
                lambda_client.invoke(FunctionName=agents_function_name, InvocationType='Event', Payload=json.dumps(event))
            # Process the response from agents_client_function
        elif selected_mode.get('category') == 'Bedrock Models':
            # Invoke genai_bedrock_async_fn
            lambda_client.invoke(FunctionName=bedrock_function_name, InvocationType='Event', Payload=json.dumps(event))
            # Process the response from lambda_fn_async
        elif selected_mode.get('category') == 'Bedrock Image Models':
            # Invoke image generation function
            if message_type != 'load':
                lambda_client.invoke(FunctionName=image_generation_function_name, InvocationType='Event', Payload=json.dumps(event))
        else:
            return {
                'statusCode': 404,
                'body': json.dumps('Endpoint Not Found')
            }
        return {
            'statusCode': 200,
            'body': json.dumps('Message Received')
        }
    else:
        return {
            'statusCode': 403,
            'body': json.dumps(not_allowed_message)
        }
@tracer.capture_method
def validate_jwt_token(id_token, access_token):
    user_attributes = get_user_attributes(access_token)
    email_verified = False
    email = None
    for attribute in user_attributes:
        if attribute['Name'] == 'email_verified':
            email_verified = attribute['Value'] == 'true'
        elif attribute['Name'] == 'email':
            email = attribute['Value']
    # if allowlist_domain contains a comma, then split it into a list and return true of the email ends with any of the domains
    if ',' in allowlist_domain:
        allowlist_domains = allowlist_domain.split(',')
        for domain in allowlist_domains:
            if email.casefold().find(domain.casefold()) != -1:
                return True, ''
            
    # if allowlist_domain is not empty and not null then
    if allowlist_domain and allowlist_domain != '':
        if email.casefold().find(allowlist_domain.casefold()) != -1:
            return True, ''
    else:
        return True, ''
    return False, f'You have not been allow-listed for this application. You require a domain containing: {allowlist_domain}', None
        
@tracer.capture_method
def get_user_attributes(access_token):
    if access_token in user_cache:
        return user_cache[access_token]
    else:
        response = cognito_client.get_user(AccessToken=access_token)
        user_attributes = response['UserAttributes']
        user_cache[access_token] = user_attributes
        return user_attributes       