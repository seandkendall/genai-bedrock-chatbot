import json, os
import boto3
from datetime import datetime, timezone
from aws_lambda_powertools import Tracer


# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['DYNAMODB_TABLE'])
allowlist_domain = os.environ['ALLOWLIST_DOMAIN']
cognito_client = boto3.client('cognito-idp')
bedrock_client = boto3.client(service_name='bedrock')
region = os.environ['REGION']
user_cache = {}
tracer = Tracer()

@tracer.capture_lambda_handler
def lambda_handler(event, context):
    try:
        # Parse request body
        request_body = json.loads(event.get('body', '{}'))
        id_token = request_body.get('idToken', 'none')
        access_token = request_body.get('accessToken', 'none')
        config_type = request_body.get('config_type')
        action = request_body.get('subaction')
        user = request_body.get('user', 'system')
        config = request_body.get('config')
        
        allowed, not_allowed_message = validate_jwt_token(id_token, access_token)
        if not allowed:
            return {
                'statusCode': 403,
                'body': json.dumps({'error': not_allowed_message})
            }
        if action == 'load_models':
            return load_models()
        elif config_type not in ['system', 'user', 'load_models']:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Invalid config_type. Must be "system" or "user".'})
            }

        if action == 'load':
            return load_config(user, config_type)
        elif action == 'save':
            return save_config(user, config_type, config)
        else:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Invalid action. Must be "load_models", "load" or "save".'})
            }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

@tracer.capture_method
def load_config(user, config_type):
    try:
        response = table.get_item(
            Key={
                'user': user,
                'config_type': config_type
            }
        )

        if 'Item' in response:
            config = response['Item']['config']
            config['config_type'] = config_type
            if 'system' in user:
                config['region'] = region
            return {
                'statusCode': 200,
                'body': json.dumps(config)
            }
        else:
            return {
                'statusCode': 404,
                'body': json.dumps({'message': 'Config not found'})
            }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
@tracer.capture_method
def save_config(user, config_type, config):
    try:
        now = datetime.now(timezone.utc).isoformat()
        existing_config = table.get_item(
            Key={
                'user': user,
                'config_type': config_type
            },
            ProjectionExpression='config'
        )

        if 'Item' in existing_config:
            previous_config = existing_config['Item']['config']
            table.put_item(
                Item={
                    'user': user,
                    'config_type': config_type,
                    'config': config,
                    'previous_config': previous_config,
                    'last_update_timestamp': now
                }
            )
        else:
            table.put_item(
                Item={
                    'user': user,
                    'config_type': config_type,
                    'config': config,
                    'last_update_timestamp': now
                }
            )

        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Config saved successfully'})
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
@tracer.capture_method
def load_models():
    try:
        # Call the Bedrock API to list available foundation models
        response = bedrock_client.list_foundation_models()
        available_models = [
            {
                'providerName': model['providerName'],
                'modelName': model['modelName'],
                'modelId': model['modelId'],
                'modelArn': model['modelArn']
            }
            for model in response['modelSummaries']
            if ('Anthropic' in model['providerName'] or 'Mistral' in model['providerName']) and 'TEXT' in model['inputModalities'] and 'TEXT' in model['outputModalities'] and model['modelLifecycle']['status'] == 'ACTIVE' and 'ON_DEMAND' in model['inferenceTypesSupported']
        ]

        # Send the available models to the frontend
        retObj = {
            'statusCode': 200,
            'body': json.dumps({'type': 'load_models', 'models': available_models})
        }
        return retObj
    except Exception as e:
        print(f"Error loading models: {str(e)}")
        return []

@tracer.capture_method    
def validate_jwt_token(id_token, access_token):
    # return True, ''
    # Check if the access_token is in the cache
    if access_token in user_cache:
        user_attributes = user_cache[access_token]
    else:
        # Call cognito_client.get_user if access_token is not in the cache
        print('calling cognito_client.get_user 1')
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
    # if allowlist_domain contains a comma, then split it into a list and return true of the email ends with any of the domains
    if ',' in allowlist_domain:
        allowlist_domains = allowlist_domain.split(',')
        for domain in allowlist_domains:
            if email.endswith(domain):
                return True, ''
            
    # if allowlist_domain is not empty and not null then
    if allowlist_domain and allowlist_domain != '':
        if email.endswith(allowlist_domain):
            return True, ''
    else:
        return True, ''
    return False, f'You have not been allow-listed for this application. You require a domain ending with: {allowlist_domain}'
        