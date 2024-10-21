import json, os, boto3
from datetime import datetime, timezone
from chatbot_commons import commons
from aws_lambda_powertools import Logger, Metrics, Tracer
from load_utilities import (
    load_knowledge_bases,
    load_agents,
    load_models,
    load_prompt_flows,
    datetime_to_iso
)

logger = Logger(service="BedrockConfig")
metrics = Metrics()
tracer = Tracer()



# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['DYNAMODB_TABLE'])
allowlist_domain = os.environ['ALLOWLIST_DOMAIN']
schedule_name = os.environ['SCHEDULE_NAME']
schedule_group_name = os.environ['SCHEDULE_GROUP_NAME']

cognito_client = boto3.client('cognito-idp')
bedrock_client = boto3.client(service_name='bedrock')
bedrock_agent_client = boto3.client(service_name='bedrock-agent')
s3_client = boto3.client('s3')
events_client = boto3.client('scheduler')

region = os.environ['REGION']
user_cache = {}


load_models_response = None
load_agents_response = None
load_prompt_flow_response = None
load_knowledgebase_response = None
load_agents_response = None

@tracer.capture_lambda_handler
def lambda_handler(event, context):
    # logger.info("Executing Bedrock Config Function")
    try:
        # Parse request body
        request_body = json.loads(event.get('body', '{}'))
        access_token = request_body.get('accessToken', 'none')
        config_type = request_body.get('config_type','system')
        action = request_body.get('subaction')
        user = request_body.get('user', 'system')
        config = request_body.get('config')
        
        allowed, not_allowed_message = commons.validate_jwt_token(cognito_client, user_cache,allowlist_domain,access_token)
        if not allowed:
            return {
                'statusCode': 403,
                'body': json.dumps({'error': not_allowed_message})
            }
        if action == 'enable_schedule':
            return enable_disable_eventbridge_schedule(True)
        elif action == 'disable_schedule':
            return enable_disable_eventbridge_schedule(False)
        elif action == 'load':
            return load_config(user, config_type)
        elif action == 'save':
            return save_config(user, config_type, config)
        elif action.startswith('load_'):
            # Use a dictionary to map actions to functions
            action_map = {
                'load_prompt_flows': lambda: load_prompt_flows(bedrock_agent_client,table),
                'load_knowledge_bases': lambda: load_knowledge_bases(bedrock_agent_client,table),
                'load_agents': lambda: load_agents(bedrock_agent_client,table),
                'load_models': lambda: load_models(bedrock_client,table)
            }
            # if actions contains ,modelscan then set modelscan = true, then remove ',modelscan' from action
            modelscan = False
            if ',modelscan' in action:
                modelscan = True
                action = action.replace(',modelscan', '')
            # split action by ,
            actions = action.split(',')
            return_obj = {}
            for action in actions:
                if action in action_map:
                    global load_prompt_flow_response, load_knowledgebase_response, load_agents_response, load_models_response
                    response_var = f"load_{action.split('_', 1)[1]}_response"
                    if response_var in globals() and globals()[response_var] is not None:
                        return_obj[action] = globals()[response_var]
                    else:
                        # Call the mapped function and store the response in the corresponding global variable
                        response = action_map[action]()
                        globals()[response_var] = response
                        return_obj[action] = response

            if return_obj:
                return_obj['type'] = 'load_response'
                return_obj['modelscan'] = modelscan
                return {
                    'statusCode': 200,
                    'body': json.dumps(return_obj, default=datetime_to_iso)
                }
        else:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Invalid action. Must be "load_prompt_flows", "load_knowledge_bases", "load_agents", "load_models", "load", "save".'})
            }

    except Exception as e:
        logger.exception(e)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


@tracer.capture_method
def load_config(user, config_type):
    """
    Load configuration for a specific user and config type from DynamoDB.

    This function attempts to retrieve a configuration from a DynamoDB table
    based on the provided user and config type. If found, it returns the
    configuration with additional metadata. For system users, it also includes
    region information and EventBridge scheduler status.

    Parameters:
    user (str): The identifier for the user.
    config_type (str): The type of configuration to load.

    Returns:
    dict: A dictionary containing the HTTP status code and a JSON-formatted body.
          On success, returns a 200 status code with the configuration data.
          On failure, returns a 500 status code with an error message.

    The returned configuration includes:
    - All key-value pairs from the stored configuration
    - 'config_type': The type of configuration (always included)
    - For system users:
        - 'region': The AWS region
        - 'eventbridge_scheduler_enabled': Boolean indicating if EventBridge 
          scheduler is enabled

    Raises:
    Exception: Any exception that occurs during the execution is caught and logged.

    Note:
    - The function uses a global 'table' object, which should be a boto3 DynamoDB Table resource.
    - The function uses a global 'logger' object for logging exceptions.
    - The function relies on a global 'region' variable for system users.
    - The function calls 'is_eventbridge_schedule_enabled()' for system users, 
      which should be defined elsewhere in the code.
    """
    config = {}
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
            config['eventbridge_scheduler_enabled'] = is_eventbridge_schedule_enabled()
        return {
            'statusCode': 200,
            'body': json.dumps(config)
        }

    except Exception as e:
        logger.exception(e)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

@tracer.capture_method
def save_config(user, config_type, config):
    """
    Save or update a configuration for a specific user and config type in DynamoDB.

    This function is decorated with @tracer.capture_method for tracing purposes.
    It attempts to save a new configuration or update an existing one in a DynamoDB table.
    If a configuration already exists for the given user and config type, it stores
    the current configuration as the previous configuration before updating with the new one.

    Parameters:
    user (str): The identifier for the user.
    config_type (str): The type of configuration being saved.
    config (dict): The configuration data to be saved.

    Returns:
    dict: A dictionary containing the HTTP status code and a JSON-formatted body.
          On success, returns a 200 status code with a success message.
          On failure, returns a 500 status code with an error message.

    Raises:
    Exception: Any exception that occurs during the execution is caught, logged,
               and returned as part of the response.

    Behavior:
    1. Generates a UTC timestamp for the update.
    2. Checks if a configuration already exists for the user and config type.
    3. If exists, saves the current config as 'previous_config' and updates with the new config.
    4. If not exists, creates a new item with the provided config.
    5. In both cases, includes a 'last_update_timestamp' with the current UTC time.

    Note:
    - The function uses a global 'table' object, which should be a boto3 DynamoDB Table resource.
    - The function uses a global 'logger' object for logging exceptions.
    - The timestamp is stored in ISO format using UTC timezone.
    - The @tracer.capture_method decorator suggests this function is part of a larger
      tracing or monitoring system.
    """
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
        logger.exception(e)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def is_eventbridge_schedule_enabled():
    """
    Check if the EventBridge schedule is enabled.

    This function queries the EventBridge service to get the state of a specific schedule.

    Returns:
        bool: True if the schedule is enabled, False otherwise.

    Raises:
        ClientError: If there's an error when calling the EventBridge API.

    Note:
        This function assumes that 'events_client', 'schedule_group_name', and 'schedule_name'
        are defined and accessible in the current scope.
    """
    schedule_response = events_client.get_schedule(GroupName=schedule_group_name ,Name=schedule_name)
    return schedule_response['State'] == 'ENABLED'

def enable_disable_eventbridge_schedule(enable):
    """
    Enable or disable an EventBridge schedule.

    This function updates the state of an existing EventBridge schedule to either
    enabled or disabled based on the input parameter. It retrieves the current
    schedule configuration, updates the state, and applies the changes.

    Args:
        enable (bool): True to enable the schedule, False to disable it.

    Returns:
        dict: A dictionary containing the status code and the new enabled state.
            {
                'statusCode': 200,
                'body': {'enabled': bool}
            }

    Raises:
        ClientError: If there's an error interacting with the EventBridge API.
    """
    try:
        schedule_response = events_client.get_schedule(
            GroupName=schedule_group_name,
            Name=schedule_name
        )

        # Prepare update parameters
        update_params = {
            'GroupName': schedule_group_name,
            'Name': schedule_name,
            'State': 'ENABLED' if enable else 'DISABLED',
            'Description': schedule_response.get('Description', ''),
            'ScheduleExpression': schedule_response['ScheduleExpression'],
            'ScheduleExpressionTimezone': schedule_response.get('ScheduleExpressionTimezone', 'Etc/UTC'),
            'FlexibleTimeWindow': schedule_response['FlexibleTimeWindow'],
            'Target': schedule_response['Target']
        }

        # Add optional parameters if they exist
        for param in ['StartDate', 'EndDate', 'KmsKeyArn']:
            if param in schedule_response:
                update_params[param] = schedule_response[param]

        events_client.update_schedule(**update_params)

        logger.info(f"Schedule '{schedule_name}' {'enabled' if enable else 'disabled'} successfully.")

        return {
            'statusCode': 200,
            'body': json.dumps({'schedule_name': schedule_name})
        }

    except events_client.exceptions.ClientError as e:
        logger.error(f"Error updating schedule: {e}")
        return {
            'statusCode': 500,
            'body': {'error': str(e)}
        }
