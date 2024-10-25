import json
import random
from datetime import datetime, timezone, timedelta
from botocore.exceptions import ClientError

def send_websocket_message(logger, apigateway_management_api, connection_id, message):
    """
    Send a message to a client through a WebSocket connection.

    This function attempts to send a message to a client connected via WebSocket.
    It first checks if the connection is open before sending the message.

    Args:
        logger (logging.Logger): A logger object for logging messages and errors.
        apigateway_management_api (boto3.client): An initialized Boto3 API Gateway Management API client.
        connection_id (str): The unique identifier for the WebSocket connection.
        message (dict): The message to be sent to the client. This will be JSON-encoded before sending.

    Returns:
        None

    Raises:
        No exceptions are raised directly by this function. All exceptions are caught and logged.

    Notes:
        - If the connection is not in the 'OPEN' state, a warning is logged and the function returns without sending the message.
        - If the connection is closed (GoneException), an info message is logged.
        - For any other exceptions, an error is logged along with the full exception traceback.
        - The message is JSON-encoded and then encoded to bytes before sending.
        - Error code 9012 is used for general error logging. This can be used for error tracking and debugging.

    Example:
        >>> logger = logging.getLogger()
        >>> api_client = boto3.client('apigatewaymanagementapi', endpoint_url='https://example.execute-api.region.amazonaws.com/stage')
        >>> send_websocket_message(logger, api_client, 'abc123', {'type': 'message', 'content': 'Hello, WebSocket!'})
    """
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
        logger.exception(e)
        logger.error(f"Error sending WebSocket message (9012): {str(e)}")
        
def validate_jwt_token(cognito_client, user_cache,allowlist_domain,access_token):
    """
    Validate a JWT token and check if the user's email domain is in the allowlist.

    This function retrieves user attributes from Cognito, checks if the email is verified,
    and validates if the email domain is in the specified allowlist.

    Args:
        cognito_client (boto3.client): An initialized Boto3 Cognito client.
        user_cache (dict): A dictionary to store user attributes, keyed by access token.
        allowlist_domain (str): A comma-separated string of allowed email domains.
        access_token (str): The Cognito access token for the user.

    Returns:
        tuple: A tuple containing three elements:
            - bool: True if the token is valid and the email domain is allowed, False otherwise.
            - str: An error message if validation fails, empty string if successful.
            - None: Always None in the current implementation.

    Note:
        - The function does not explicitly check if the email is verified, although it sets the 'email_verified' variable.
        - If allowlist_domain is empty or None, the function will return True, allowing all domains.
        - The domain check is case-insensitive and uses a substring match, not an exact domain match.
        - Multiple domains in allowlist_domain should be separated by commas.

    Example:
        >>> is_valid, error_message, _ = validate_jwt_token(cognito_client, user_cache, "example.com,test.com", "user_access_token")
        >>> if is_valid:
        ...     print("User validated successfully")
        ... else:
        ...     print(error_message)
    """
    user_attributes = get_user_attributes(cognito_client, user_cache,access_token)
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
    return False, f'You have not been allow-listed for this application. You require a domain containing: {allowlist_domain}'
        

def get_user_attributes(cognito_client, user_cache, access_token):
    """
    Retrieve user attributes from Amazon Cognito or a local cache.

    This function attempts to fetch user attributes from a local cache first.
    If the attributes are not found in the cache, it makes a call to the
    Cognito service to retrieve them, then caches the result for future use.

    Args:
        cognito_client (boto3.client): An initialized Boto3 Cognito client.
        user_cache (dict): A dictionary to store user attributes, keyed by access token.
        access_token (str): The Cognito access token for the user.

    Returns:
        list: A list of dictionaries containing the user's attributes.
              Each dictionary has 'Name' and 'Value' keys.

    Raises:
        botocore.exceptions.ClientError: If there's an error calling the Cognito service.

    Note:
        This function assumes that the cognito_client has the necessary permissions
        to call the 'get_user' API.
    """
    if access_token in user_cache:
        return user_cache[access_token]
    response = cognito_client.get_user(AccessToken=access_token)
    user_attributes = response['UserAttributes']
    user_cache[access_token] = user_attributes
    return user_attributes

    
def keep_latest_versions(models):
    latest_models = {}
    for model in models:
        model_key = (model['providerName'], model['modelName'])
        if model_key not in latest_models or compare_versions(model['modelId'], latest_models[model_key]['modelId']) > 0:
            latest_models[model_key] = model
    return list(latest_models.values())

def compare_versions(version1, version2):
    """
    Compare two version strings.
    Returns: 1 if version1 is newer, -1 if version2 is newer, 0 if equal
    """
    v1_parts = version1.split(':')
    v2_parts = version2.split(':')

    # Compare the base part (before the colon)
    if v1_parts[0] != v2_parts[0]:
        return 1 if v1_parts[0] > v2_parts[0] else -1

    # If base parts are equal, compare the version numbers after the colon
    if len(v1_parts) > 1 and len(v2_parts) > 1:
        v1_num = int(v1_parts[1]) if v1_parts[1].isdigit() else 0
        v2_num = int(v2_parts[1]) if v2_parts[1].isdigit() else 0
        return 1 if v1_num > v2_num else (-1 if v1_num < v2_num else 0)

    # If one has a version number and the other doesn't, the one with a version number is newer
    return 1 if len(v1_parts) > len(v2_parts) else (-1 if len(v2_parts) > len(v1_parts) else 0)    

def get_ddb_config(table,ddb_cache,ddb_cache_timestamp,cache_duration,logger):

    # Check if the cache is valid
    if ddb_cache and ddb_cache_timestamp and (datetime.now(timezone.utc) - ddb_cache_timestamp) < timedelta(seconds=cache_duration):
        return ddb_cache

    # If the cache is not valid, fetch the data from DynamoDB
    try:
        response = table.get_item(
            Key={
                'user': 'models',
                'config_type': 'models'
            }
        )

        if 'Item' in response:
            ddb_cache = response['Item']['config']
            ddb_cache_timestamp = datetime.now(timezone.utc)
            return ddb_cache
        else:
            return {}
    except Exception as e:
        logger.exception(e)
        logger.error(f"Error getting DynamoDB config: {str(e)}")
        return {}
    
def generate_image_titan(logger,bedrock,model_id, prompt, width, height, seed):
    """ Generates an image using titan """
    logger.info("Generating image using Titan Image Generator")
    # if not seed then set seed random
    if not seed:
        seed = random.randint(0, 2147483646)
    image_gen_config = {
                "numberOfImages": 1,
                "seed": seed,
                "cfgScale": 8.0
            }
    if width:
        image_gen_config['width'] = width
    if height:
        image_gen_config['height'] = height
    try:
        response = bedrock.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "taskType": "TEXT_IMAGE",
                "textToImageParams": {
                    "text": prompt,
                    "negativeText": "low quality, blurry",
                },
                "imageGenerationConfig": image_gen_config
            })
        )
    except ClientError as e:
        if e.response['Error']['Code'] == 'AccessDeniedException':
            logger.warn("No Model Access to: %s",model_id)
        else:
            logger.exception(e)
        return None
    except Exception as e:
        logger.exception(e)
        return None
    response_body = json.loads(response['body'].read())
    return response_body['images'][0]

def generate_image_stable_diffusion(logger,bedrock,model_id, prompt, width, height, style_preset,seed,steps):
    """Generates an image using StableDiffusion"""
    # write log printing model_id
    logger.info(f"Generating image using Model ID: {model_id}")
    if not seed:
        seed = random.randint(0, 2147483646)
    if not steps:
        steps = 30
    # if model_id contains sd3-large
    if 'stable-diffusion-xl-v1' not in model_id:
        try:
            response = bedrock.invoke_model(
                modelId=model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({
                    "prompt": prompt,
                    "mode": "text-to-image",
                    "seed": seed,
                })
            )
        except ClientError as e:
            if e.response['Error']['Code'] == 'AccessDeniedException':
                logger.warn("No Model Access to: %s",model_id)
            else:
                logger.exception(e)
            return None
        except Exception as e:
            logger.exception(e)
            return None
        model_response = json.loads(response["body"].read())
        base64_image_data = model_response["images"][0]
        return base64_image_data
    else:
        body_attributes = {
                "text_prompts": [{"text": prompt}],
                "cfg_scale": 7,
                "seed": seed,
                "steps": steps
            }
        if width:
            body_attributes['width'] = width
        if height:
            body_attributes['height'] = height
        if style_preset:
            body_attributes['style_preset'] = style_preset
        try:
            response = bedrock.invoke_model(
                modelId=model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(body_attributes)
            )
        except ClientError as e:
            if e.response['Error']['Code'] == 'AccessDeniedException':
                logger.warn("No Model Access to: %s",model_id)
            else:
                logger.exception(e)
            return None
        except Exception as e:
            logger.exception(e)
            return None
        
        response_body = json.loads(response['body'].read())
        return response_body['artifacts'][0]['base64']