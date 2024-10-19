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
        config_type = request_body.get('config_type')
        action = request_body.get('subaction')
        user = request_body.get('user', 'system')
        config = request_body.get('config')
        
        allowed, not_allowed_message = commons.validate_jwt_token(cognito_client, user_cache,allowlist_domain,access_token)
        if not allowed:
            return {
                'statusCode': 403,
                'body': json.dumps({'error': not_allowed_message})
            }

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
        if config_type not in ['system', 'user']:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Invalid config_type. Must be "system" or "user".'})
            }

        if action == 'load':
            return load_config(user, config_type)
        elif action == 'save':
            return save_config(user, config_type, config)
        elif action == 'get-presigned-url':
            return get_presigned_url(event)
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
        logger.exception(e)
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
        logger.exception(e)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
        
def enable_eventbridge_schedule(schedule_name):
    logger.info('TODO: not yet implemented')