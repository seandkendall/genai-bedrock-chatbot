import json, boto3, os
from aws_lambda_powertools import Tracer



lambda_client = boto3.client('lambda')
cognito_client = boto3.client('cognito-idp')
agents_function_name = os.environ['AGENTS_FUNCTION_NAME']
bedrock_function_name = os.environ['BEDROCK_FUNCTION_NAME']
user_pool_id = os.environ['USER_POOL_ID']
region = os.environ['REGION']
allowlist_domain = os.environ['ALLOWLIST_DOMAIN']
image_generation_function_name = os.environ['IMAGE_GENERATION_FUNCTION_NAME']
user_cache = {}
tracer = Tracer()

@tracer.capture_lambda_handler
def lambda_handler(event, context):
    try:
        request_body = json.loads(event['body'])
    except (ValueError, KeyError):
        # Handle the case where the request body is not valid JSON or does not contain the 'body' key
        request_body = {}
    selected_mode = request_body.get('selectedMode', 'none')
    print('selected_mode:'+selected_mode)
    id_token = request_body.get('idToken', 'none')
    access_token = request_body.get('accessToken', 'none')
    tracer.put_annotation(key="SelectedMode", value=selected_mode)
    
    allowed, not_allowed_message = validate_jwt_token(id_token, access_token)
    if allowed:
        if selected_mode == 'agents':
            # Invoke genai_bedrock_agents_client_fn
            lambda_client.invoke(FunctionName=agents_function_name, InvocationType='Event', Payload=json.dumps(event))
            # Process the response from agents_client_function
        elif selected_mode == 'bedrock':
            # Invoke genai_bedrock_async_fn
            lambda_client.invoke(FunctionName=bedrock_function_name, InvocationType='Event', Payload=json.dumps(event))
            # Process the response from lambda_fn_async
        elif selected_mode == 'image':
            # Invoke image generation function
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
    # return True, ''
    # Check if the access_token is in the cache
    if access_token in user_cache:
        user_attributes = user_cache[access_token]
        print('using user cache')
    else:
        # Call cognito_client.get_user if access_token is not in the cache
        response = cognito_client.get_user(AccessToken=access_token)
        user_attributes = response['UserAttributes']
        
        # Store the user attributes in the cache
        user_cache[access_token] = user_attributes

    email_verified = False
    email = None
    for attribute in user_attributes:
        if attribute['Name'] == 'email_verified':
            email_verified = attribute['Value'] == 'true'
        elif attribute['Name'] == 'email':
            email = attribute['Value']
            tracer.put_annotation(key="Email", value=email)
    # if allowlist_domain contains a comma, then split it into a list and return true of the email contains any of the domains
    if ',' in allowlist_domain:
        allowlist_domains = allowlist_domain.split(',')
        for domain in allowlist_domains:
            if domain.casefold() in email.casefold():
                return True, ''

                        
    # if allowlist_domain is not empty and not null then
    if allowlist_domain and allowlist_domain != '':
        tracer.put_annotation(key="AllowListDomain", value=allowlist_domain)
        if email.endswith(allowlist_domain):
            return True, ''
    else:
        return True, ''
    return False, f'You have not been allow-listed for this application. You require a domain ending with: {allowlist_domain}'
        