import json
from datetime import datetime, timezone, timedelta
from aws_lambda_powertools import Logger
from chatbot_commons import commons

logger = Logger(service="BedrockConfigLoadUtilities")

# Cache the DynamoDB results for 5 minutes
CACHE_DURATION = 60 * 5  # 5 minutes
ddb_cache = {}
ddb_cache_timestamp = None

def datetime_to_iso(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError("Type not serializable")



def load_knowledge_bases(bedrock_agent_client, table):
    try:
        response = bedrock_agent_client.list_knowledge_bases(maxResults=100)
        kb_summaries = response.get('knowledgeBaseSummaries', [])
        ret = []

        # Convert datetime objects to ISO format strings
        for kb in kb_summaries:
            kb_id = kb['knowledgeBaseId']
            kb['mode_selector'] = kb_id
            kb['mode_selector_name'] = kb_id
            if kb['status'] == 'ACTIVE':
                ddb_config = commons.get_ddb_config(table,ddb_cache,ddb_cache_timestamp,CACHE_DURATION,logger)
                kb['is_active'] = ddb_config.get(kb_id, {}).get('access_granted', True)
                kb['allow_input_image'] = ddb_config.get(kb_id, {}).get('IMAGE', False)
                kb['allow_input_document'] = ddb_config.get(kb_id, {}).get('DOCUMENT', False)
                ret.append(kb)

        return {
            'type': 'load_knowledge_bases',
            'knowledge_bases': ret
        }
    except Exception as e:
        logger.exception(e)
        logger.error(f"Error loading agents: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'type': 'error',
                'message': str(e)
            })
        }

def load_agents(bedrock_agent_client, table):
    try:
        response = bedrock_agent_client.list_agents(maxResults=100)
        agent_summaries = response.get('agentSummaries', [])
        ret = []

        # Convert datetime objects to ISO format strings
        for agent in agent_summaries:
            agent_id = agent['agentId']
            agent_name = agent['agentName']
            agent_alias_response = bedrock_agent_client.list_agent_aliases(
                maxResults=100,
                agentId=agent_id,
            )
            agent_aliases = agent_alias_response['agentAliasSummaries']
            # add agent_id to each item in agent_aliases
            for alias in agent_aliases:
                alias['agentId'] = agent_id
                alias['mode_selector'] = alias['agentAliasId']
                alias['mode_selector_name'] = alias['agentAliasName']
                alias['agent_name'] = agent_name
                ddb_config = commons.get_ddb_config(table,ddb_cache,ddb_cache_timestamp,CACHE_DURATION,logger)
                alias['is_active'] = ddb_config.get(alias['agentAliasId'], {}).get('access_granted', True)
                alias['allow_input_image'] = ddb_config.get(alias['agentAliasId'], {}).get('IMAGE', False)
                alias['allow_input_document'] = ddb_config.get(alias['agentAliasId'], {}).get('DOCUMENT', False)
                if alias['agentAliasName'] != 'AgentTestAlias':
                    ret.append(alias)

        return {
            'type': 'load_agents',
            'agents': ret
        }
    except Exception as e:
        logger.exception(e)
        logger.error(f"Error loading agents: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'type': 'error',
                'message': str(e)
            })
        }

def load_prompt_flows(bedrock_agent_client, table):
    try:
        response = bedrock_agent_client.list_flows(maxResults=100,)
        flow_summaries = response.get('flowSummaries', [])
        ret = []

        # Convert datetime objects to ISO format strings
        for flow in flow_summaries:
            flow_id = flow['id']
            flow_alias_response = bedrock_agent_client.list_flow_aliases(
                maxResults=100,
                flowIdentifier=flow_id,
            )
            flow_aliases = flow_alias_response['flowAliasSummaries']
            for alias in flow_aliases:
                alias['mode_selector'] = alias['arn']
                alias['mode_selector_name'] = alias['name']
                ddb_config = commons.get_ddb_config(table,ddb_cache,ddb_cache_timestamp,CACHE_DURATION,logger)
                alias['is_active'] = ddb_config.get(alias['arn'], {}).get('access_granted', True)
                alias['allow_input_image'] = ddb_config.get(alias['arn'], {}).get('IMAGE', False)
                alias['allow_input_document'] = ddb_config.get(alias['arn'], {}).get('DOCUMENT', False)
                if alias['name'] != 'TSTALIASID':
                    ret.append(alias)

        return {
            'type': 'load_prompt_flows',
            'prompt_flows': ret
        }
    except Exception as e:
        logger.exception(e)
        logger.error(f"Error loading prompt flows: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'type': 'error',
                'message': str(e)
            })
        }

def load_models(bedrock_client, table):
    try:
        response = bedrock_client.list_foundation_models(byInferenceType='ON_DEMAND')
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
            if ('Stability' in model['providerName'] or 'Amazon' in model['providerName']) and 'TEXT' in model['inputModalities'] and 'IMAGE' in model['outputModalities'] and model['modelLifecycle']['status'] == 'ACTIVE'
            
        ]

        # Process to keep only the latest version of each model
        available_text_models = keep_latest_versions(text_models)
        available_image_models = keep_latest_versions(image_models)

        available_text_models_return = []
        available_image_models_return = []
        # Update the models with DynamoDB config
        ddb_config = commons.get_ddb_config(table,ddb_cache,ddb_cache_timestamp,CACHE_DURATION,logger)
        for model in available_text_models:
            if ddb_config.get(model['modelId'], {}).get('access_granted', True):
                model['is_active'] = True
                model['allow_input_image'] = ddb_config.get(model['modelId'], {}).get('IMAGE', False)
                model['allow_input_document'] = ddb_config.get(model['modelId'], {}).get('DOCUMENT', False)
                available_text_models_return.append(model)
                
        for model in available_image_models:
            if ddb_config.get(model['modelId'], {}).get('access_granted', True):
                model['is_active'] = True
                model['allow_input_image'] = ddb_config.get(model['modelId'], {}).get('IMAGE', False)
                model['allow_input_document'] = ddb_config.get(model['modelId'], {}).get('DOCUMENT', False)
                available_image_models_return.append(model)
            
            
        
        # Load the kb_models from the JSON file    
        with open('./bedrock_supported_kb_models.json', 'r') as f:
            kb_models = json.load(f)
        
        return {'type': 'load_models', 'text_models': available_text_models_return, 'image_models': available_image_models_return, 'kb_models': kb_models}
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
