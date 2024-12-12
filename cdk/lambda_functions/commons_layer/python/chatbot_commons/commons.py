import json
import decimal
import time
import random
import string
from datetime import datetime, timezone, timedelta
from botocore.exceptions import ClientError

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

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
            Data=json.dumps(message, cls=DecimalEncoder).encode()
        )
    except apigateway_management_api.exceptions.GoneException:
        logger.info(f"WebSocket connection is closed (connectionId: {connection_id})")
    except Exception as e:
        logger.exception(e)
        logger.error(f"Error sending WebSocket message (9012): {str(e)}")
        
def validate_jwt_token(cognito_client, user_cache, allowlist_domain, access_token):
    """
    Validate a JWT token and check if the user's email domain is in the allowlist.

    Args:
        cognito_client (boto3.client): An initialized Boto3 Cognito client.
        user_cache (dict): A dictionary to store user attributes, keyed by access token.
        allowlist_domain (str): A comma-separated string of allowed email domains.
        access_token (str): The Cognito access token for the user.

    Returns:
        tuple: (is_valid: bool, error_message: str)
    """
    user_attributes = get_user_attributes(cognito_client, user_cache, access_token)
    
    # Extract email using dictionary comprehension
    email = next((attr['Value'] for attr in user_attributes if attr['Name'] == 'email'), None)
    
    # If allowlist_domain is empty or None, allow all domains
    if not allowlist_domain:
        return True, ''

    # Convert email to lowercase once
    email_lower = email.casefold()
    
    # Handle both single and multiple domains
    domains = allowlist_domain.split(',') if ',' in allowlist_domain else [allowlist_domain]
    
    # Check if any domain matches
    if any(email_lower.find(domain.casefold()) != -1 for domain in domains):
        return True, ''

    return False, (f'You have not been allow-listed for this application. '
                  f'You require a domain containing: {allowlist_domain}')


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
        NotAuthorizedException: When the access token is invalid, expired, or revoked.

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
    """
    Keep only the latest version of each model in the list.

    This function processes a list of models, keeping only the latest version of each model.
    If a model has multiple versions, only the one with the highest version number is kept.
    The input models are expected to be in the format of a list of dictionaries, where each
    dictionary represents a model with 'providerName', 'modelName', and 'modelId' keys.

    Args:
        models (list): A list of dictionaries representing models.
                       Each dictionary should have 'providerName', 'modelName', and 'modelId' keys.

    Returns:
        list: A list of dictionaries representing the latest version of each model.
              The returned list will have the same structure as the input list.

    Example:
        >>> input_models = [
        ...     {'providerName': 'Bedrock', 'modelName': 'amazon.ai21.j2-mid-v1', 'modelId': 'XXXXXX'},
        ...     {'providerName': 'Bedrock', 'modelName': 'amazon.ai21.j2-mid-v1', 'modelId': 'XXXXXX'},
        ...     {'providerName': 'Bedrock', 'modelName': 'amazon.ai21.j2-ultra-v1', 'modelId': 'XXXXXX'}
        ... ]
        >>> keep_latest_versions(input_models)
        [{'providerName': 'Bedrock', 'modelName': 'amazon.ai21.j2-ultra-v1', 'modelId': 'XXXXXX'}]
    """
    if not models:
        return []
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
    """
    Retrieves the DynamoDB configuration from the table and caches it.

    This function attempts to fetch the configuration from a local cache first.
    If the cache is not available or has expired, it fetches the configuration from DynamoDB.
    The configuration is then cached for future use.

    Args:
        table (boto3.resource.Table): An initialized DynamoDB table resource.
        ddb_cache (dict): A dictionary to store the configuration, keyed by 'user'.
        ddb_cache_timestamp (datetime): The timestamp when the cache was last updated.
        cache_duration (int): The duration (in seconds) for which the cache is considered valid.
        logger (logging.Logger): A logger object for logging messages and errors.

    Returns:
        dict: The configuration retrieved from DynamoDB or the cache.
              The returned dictionary has 'user' as the key, and the value is the configuration.
    """
    logger.info("Getting DynamoDB config")

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
    
def generate_image_titan_nova(logger,bedrock,model_id, prompt, width, height, seed):
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
        error_message = e.response['Error']['Message']
        if e.response['Error']['Code'] == 'AccessDeniedException':
            logger.warn("No Model Access to: %s",model_id)
        else:
            logger.exception(e)
        return None,False,error_message
    except Exception as e:
        logger.exception(e)
        return None, False, str(e)
    response_body = json.loads(response['body'].read())
    return response_body['images'][0], True, None

def generate_video(prompt, model_id,user_id,session_id,bedrock_runtime,s3_client,video_bucket,SLEEP_TIME,logger, cloudfront_domain, duration_seconds,seed):
    prefix = rf'{user_id}/{session_id}'
    model_input = {
        "taskType": "TEXT_VIDEO",
        "textToVideoParams": {"text": prompt},
        "videoGenerationConfig": {
            "durationSeconds": duration_seconds,
            "fps": 24,
            "dimension": "1280x720",
            "seed": seed
        }
    }

    try:
        s3uri = f"s3://{video_bucket}/videos/{prefix}/"
        invocation = bedrock_runtime.start_async_invoke(
            modelId=model_id,
            modelInput=model_input,
            outputDataConfig={"s3OutputDataConfig": {"s3Uri": s3uri}}
        )
        invocation_arn = invocation["invocationArn"]
        s3_prefix = invocation_arn.split('/')[-1]
        s3_location_original = f"videos/{prefix}/{s3_prefix}/output.mp4"
        s3_location = f"videos/{prefix}/{s3_prefix}/{s3_prefix}.mp4"

        while True:
            response = bedrock_runtime.get_async_invoke(
                invocationArn=invocation_arn
            )
            status = response["status"]
            if status != "InProgress":
                break
            time.sleep(SLEEP_TIME)
        if status == "Completed":
            s3_client.copy_object(CopySource={'Bucket': video_bucket, 'Key': f"{s3_location_original}"}, Bucket=video_bucket, Key=f"{s3_location}")
            s3_client.delete_object(Bucket=video_bucket, Key=f"{s3_location_original}")
            cloudfront_url = f"https://{cloudfront_domain}/{s3_location}"
            return f"{cloudfront_url}", True, ""
        else:
            return "", False, f"Video generation failed with status: {status}"

    except Exception as e:
        logger.exception(e)
        return "", False, str(e)
    
def generate_random_string(length=8):
    """Function to generate a random String of length 8"""
    characters = string.ascii_lowercase + string.digits
    random_part = ''.join(random.choice(characters) for _ in range(length))
    return f"RES{random_part}"

def generate_image_stable_diffusion(logger,bedrock,model_id, prompt, width, height, style_preset,seed,steps):
    """Generates an image using StableDiffusion"""
    # write log for model_id
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
            error_message = e.response['Error']['Message']
            if e.response['Error']['Code'] == 'AccessDeniedException':
                logger.warn("No Model Access to: %s",model_id)
            else:
                logger.exception(e)
            return None,False,error_message
        except Exception as e:
            logger.exception(e)
            return None, False, str(e)
        model_response = json.loads(response["body"].read())
        base64_image_data = model_response["images"][0]
        return base64_image_data,True,None
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
            error_message = e.response['Error']['Message']
            if e.response['Error']['Code'] == 'AccessDeniedException':
                logger.warn("No Model Access to: %s",model_id)
            else:
                logger.exception(e)
            return None,False,error_message
        except Exception as e:
            logger.exception(e)
            return None, False, str(e)
        
        response_body = json.loads(response['body'].read())
        return response_body['artifacts'][0]['base64'],True,None

def delete_s3_attachments_for_session(session_id: str,bucket: str,user_id:str,additional_prefix:str, s3_client, logger):
    """Function to delete conversation attachments from s3"""
    logger.info(f"Deleting conversation attachments for session: {session_id} bucket: {bucket} user_id: {user_id}")
    deleted_objects = []
    errors = []
    # if additional_prefix is not null
    if additional_prefix:
        prefix = rf'{additional_prefix}/{user_id}/{session_id}'
    else:
        prefix = rf'{user_id}/{session_id}'
    
    try:
        # List objects with the specified prefix
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket, Prefix=prefix)
        
        for page in pages:
            if 'Contents' in page:
                for obj in page['Contents']:
                    key = obj['Key']
                    try:
                        s3_client.delete_object(Bucket=bucket, Key=key)
                        logger.info(f"Deleted s3://{bucket}/{key}")
                        deleted_objects.append(f"s3://{bucket}/{key}")
                    except Exception as e:
                        logger.exception(e)
                        errors.append(f"Error deleting s3://{bucket}/{key}: {str(e)}")
    
    except Exception as e:
        logger.exception(e)
        errors.append(f"Error listing objects in s3://{bucket}/{prefix}: {str(e)}")
    
    if errors:
        logger.error(f"Encountered {len(errors)} errors:")
        for error in errors:
            logger.error(f"- {error}")