import json
        
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
    return False, f'You have not been allow-listed for this application. You require a domain containing: {allowlist_domain}', None
        

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

def load_models(logger,bedrock_client, table):
    try:
        response = bedrock_client.list_foundation_models()
        # Filter and process text models
        text_models = [
            {
                'providerName': model['providerName'],
                'modelName': model['modelName'],
                'modelId': model['modelId'],
                'modelArn': model['modelArn'],
                'mode_selector': model['modelArn'],
                'mode_selector_name': model['modelName'],
            }
            for model in response['modelSummaries']
            if 'TEXT' in model['inputModalities'] and 'TEXT' in model['outputModalities'] and model['modelLifecycle']['status'] == 'ACTIVE' and 'ON_DEMAND' in model['inferenceTypesSupported']
        ]

        # Filter and process image models
        image_models = [
            {
                'providerName': model['providerName'],
                'modelName': model['modelName'],
                'modelId': model['modelId'],
                'modelArn': model['modelArn'],
                'mode_selector': model['modelArn'],
                'mode_selector_name': model['modelName'],
            }
            for model in response['modelSummaries']
            if ('Stability' in model['providerName'] or 'Amazon' in model['providerName']) and 'TEXT' in model['inputModalities'] and 'IMAGE' in model['outputModalities'] and model['modelLifecycle']['status'] == 'ACTIVE' and 'ON_DEMAND' in model['inferenceTypesSupported']
            
        ]

        # Process to keep only the latest version of each model
        available_text_models = keep_latest_versions(text_models)
        available_image_models = keep_latest_versions(image_models)

        # Update the models with DynamoDB config
        ddb_config = get_ddb_config(table)
        for model in available_text_models + available_image_models:
            model['is_active'] = ddb_config.get(model['modelId'], {}).get('access_granted', True)
            model['allow_input_image'] = ddb_config.get(model['modelId'], {}).get('IMAGE', False)
            model['allow_input_document'] = ddb_config.get(model['modelId'], {}).get('DOCUMENT', False)
        # Load the kb_models from the JSON file    
        with open('./bedrock_supported_kb_models.json', 'r') as f:
            kb_models = json.load(f)
        
        retObj = {'type': 'load_models', 'text_models': available_text_models, 'image_models': available_image_models, 'kb_models': kb_models}
        return retObj
    except Exception as e:
        logger.exception(e)
        logger.error(f"Error loading models: {str(e)}")
        return []
    
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