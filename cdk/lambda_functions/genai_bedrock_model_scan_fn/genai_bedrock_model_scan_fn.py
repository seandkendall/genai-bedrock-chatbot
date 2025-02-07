import json
import os
import logging
import concurrent.futures
from datetime import datetime, timezone
from functools import partial
import boto3
from chatbot_commons import commons
from botocore.exceptions import ClientError
from aws_lambda_powertools import Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit

logger = logging.getLogger()
logger.setLevel(logging.INFO)
tracer = Tracer()
metrics = Metrics()
WEBSOCKET_API_ENDPOINT = os.environ['WEBSOCKET_API_ENDPOINT']
cloudfront_domain = os.environ['CLOUDFRONT_DOMAIN']
video_bucket = os.environ['S3_IMAGE_BUCKET_NAME']
model_import_bucket_name = os.environ['S3_CUSTOM_MODEL_IMPORT_BUCKET_NAME']
s3_client = boto3.client('s3')
codebuild_client = boto3.client('codebuild')
allowlist_domain = os.environ['ALLOWLIST_DOMAIN']
user_pool_id = os.environ['USER_POOL_ID']
config_table = boto3.resource('dynamodb').Table(os.environ.get('CONFIG_DYNAMODB_TABLE'))
bedrock = boto3.client('bedrock')
bedrock_runtime = boto3.client('bedrock-runtime')
cognito_client = boto3.client('cognito-idp')
apigateway_management_api = boto3.client('apigatewaymanagementapi', 
                                         endpoint_url=f"{WEBSOCKET_API_ENDPOINT.replace('wss', 'https')}/ws")
user_cache = {}
CACHE_DURATION = 60 * 5  # 5 minutes
ddb_cache = {}
ddb_cache_timestamp = None

@metrics.log_metrics
def lambda_handler(event, context):
    """Lambda Hander Function"""
    is_websocket_event = False
    connection_id = None
    access_token = None

    if 'Records' in event:
        is_websocket_event = True
        record = event['Records'][0]
        request_body = json.loads(record['body'])
        connection_id = request_body.get('connection_id')
        access_token = request_body.get('accessToken')
    elif 'immediate' in event:
        is_websocket_event = False
    else:
        logger.error(f"Unexpected event format: {event}")
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Unexpected event format'})
        }

    if is_websocket_event:
        # Check if the WebSocket connection is open
        try:
            connection = apigateway_management_api.get_connection(ConnectionId=connection_id)
            connection_state = connection.get('ConnectionStatus', 'OPEN')
            if connection_state != 'OPEN':
                logger.info(f"WebSocket connection is not open (state: {connection_state})")
                return
        except apigateway_management_api.exceptions.GoneException:
            logger.warn(f"WebSocket connection is closed (connectionId: {connection_id})")
            return

        try:
            allowed, not_allowed_message = commons.validate_jwt_token(cognito_client, user_cache, allowlist_domain, access_token)
        except ClientError as e:
            allowed, not_allowed_message = (False, "Your Access Token has expired. Please log in again.") if e.response['Error']['Code'] == 'NotAuthorizedException' else (None, None)

        if not allowed:
            return {
                'statusCode': 403,
                'body': json.dumps({'error': not_allowed_message})
            }

    result = start_custom_model_deployment_to_s3()
    if result:
        print("Custom model install Started")
    else:
        print("Custom Model Install: No deployment was needed.")
        
    active_models = scan_for_active_models()
    commons.send_websocket_message(logger, apigateway_management_api, connection_id, {'type':'modelscan','results':active_models,'timestamp': datetime.now(timezone.utc).isoformat(),})

    return {
        'statusCode': 200,
        'body': json.dumps(active_models, indent=2)
    }
    
def process_prompt(model_id, prompt_type, prompt_text, model_name):
    try:
        if 'imported-model' in model_id and prompt_type == 'TEXT':
            response = bedrock_runtime.invoke_model(
                modelId=model_id,
                body=json.dumps({'prompt':prompt_text, 'max_gen_len':100})
            )
            # if response contains ResponseMetadata and HTTPHeaders and x-amzn-bedrock-input-token-count
            if 'ResponseMetadata' in response and 'HTTPHeaders' in response['ResponseMetadata'] and 'x-amzn-bedrock-input-token-count' in response['ResponseMetadata']['HTTPHeaders']:
                input_token_count = int(response['ResponseMetadata']['HTTPHeaders']['x-amzn-bedrock-input-token-count'])                
                output_token_count = int(response['ResponseMetadata']['HTTPHeaders']['x-amzn-bedrock-output-token-count'])
            else:
                input_token_count = 0
                output_token_count = 0
            return model_id, prompt_type, True, input_token_count, output_token_count
        else:
            content = [{"text": prompt_text}]
            if prompt_type == 'IMAGE':
                image_bytes = load_1px_image()
                content.append({
                    "image": {
                        "format": "png",
                        "source": {
                            "bytes": image_bytes
                        }
                    }
                })
            elif prompt_type == 'DOCUMENT':
                doc_bytes = load_pdf()
                content.append({
                    "document": {
                        "format": "pdf",
                        "name": "samplepdf",
                        "source": {
                            "bytes": doc_bytes
                        }
                    }
                })
            elif prompt_type == 'VIDEO':
                doc_bytes = load_mp4()
                content.append({
                    "video": {
                        "format": "mp4",
                        "source": {
                            "bytes": doc_bytes
                        }
                    }
                })
            response = bedrock_runtime.converse(
                modelId=model_id,
                messages=[
                    {
                        "role": "user",
                        "content": content
                    }
                ]
            )
            
        return model_id, prompt_type, True, response['usage']['inputTokens'], response['usage']['outputTokens']
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'ThrottlingException':
            logger.warning(f"Throttling for model {model_id}, prompt type {prompt_type}, model name: {model_name}")
            return model_id, prompt_type, True, 0, 0
        elif error_code == 'ValidationException':
            print(e)
            logger.warning(f"Validation issues (not supported) for model {model_id}, prompt type {prompt_type}, model name: {model_name}")
        elif error_code == 'AccessDeniedException':
            logger.warning(f"AccessDenied for model {model_id}, prompt type {prompt_type}, model name: {model_name}")
        else:
            print(e)
            logger.warning(f"Client issue for model {model_id}, prompt type {prompt_type}, model name: {model_name}")
        return model_id, prompt_type, False, 0, 0
    except Exception as e:
        logger.exception(e)
        logger.error(f"Unexpected error for model {model_id}, prompt type {prompt_type}, model name: {model_name}: {str(e)}")
        return model_id, prompt_type, False, 0, 0

def scan_for_active_models():
    """ Scans for active models in Bedrock """
    try:
        
        list_foundation_models_response = bedrock.list_foundation_models(byInferenceType='ON_DEMAND')
        all_models = list_foundation_models_response.get('modelSummaries', [])
        list_imported_models_list = bedrock.list_imported_models().get('modelSummaries', [])
        for item in list_imported_models_list:
            item['modelLifecycle'] = {}
            item['modelLifecycle']['status'] = 'ACTIVE'
            item['inputModalities'] = ['TEXT']
            item['outputModalities'] = ['TEXT']
            item['modelId'] = item['modelArn']
            item['providerName'] = item['modelArchitecture']
            all_models.append(item)
    except ClientError as e:
        logger.exception(e)
        logger.error("Error listing foundation models: %s",str(e))
        return {
            'statusCode': 500,
            'body': json.dumps(f"Error listing foundation models: {str(e)}")
        }
    # if modelLifecycle status == ACTIVE or modelLifecycle doesnt exist
    active_models = [
        model for model in all_models
        if model.get('modelLifecycle', {}).get('status') == 'ACTIVE'
    ]

    results = {}
    total_input_tokens = 0
    total_output_tokens = 0
    video_helper_image_model_id = ''
    # Load config from DDB Table so we dont check models that are already set as True for different Capabilities
    ddb_config = commons.get_ddb_config(config_table,ddb_cache,ddb_cache_timestamp,CACHE_DURATION,logger)
    print('SDK printing ddb_config')
    print(ddb_config)
    print('SDK printing ddb_config DONE')
    # ddb_config.get('modelID', {}).get('IMAGE', False)
    # ddb_config.get('modelID', {}).get('access_granted', False)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for model in active_models:
            model_id = model['modelId']
            model_name = model['modelName']
            input_modalities = model['inputModalities']
            output_modalities = model['outputModalities']
            if model_id not in results:
                results[model_id] = {
                    'modelArn': model['modelArn'],
                    'modelName': model['modelName'],
                    'providerName': model['providerName'],
                    'inputModalities': input_modalities,
                    'outputModalities': output_modalities,
                    'responseStreamingSupported': model.get('responseStreamingSupported', False),
                    'TEXT': False,
                    'VIDEO': False,
                    'IMAGE': False,
                    'DOCUMENT': False,
                    'access_granted': False,
                    'mode_selector': model['modelArn'],
                    'mode_selector_name': model['modelName']
                }
            if 'TEXT' in output_modalities:
                prompts = [
                    ('TEXT', "1+1"),
                    ('IMAGE', "what color is this?"),
                    ('VIDEO', "explain this video"),
                    ('DOCUMENT', "what number is in the document?")
                ]
                for prompt_type, prompt_text in prompts:
                    futures.append(executor.submit(
                        process_prompt, model_id, prompt_type, prompt_text, model_name
                    ))

        for future in concurrent.futures.as_completed(futures):
            model_id, prompt_type, success, input_tokens, output_tokens = future.result()
            results[model_id][prompt_type] = success
            total_input_tokens += input_tokens
            total_output_tokens += output_tokens

    # Process IMAGE and VIDEO modalities
    for model in active_models:
        model_id = model['modelId']
        output_modalities = model['outputModalities']
        if 'IMAGE' in output_modalities:
            results[model_id]['TEXT'] = test_image_model(model_id)
            if 'nova' in model_id.lower() and results[model_id]['TEXT'] is True:
                video_helper_image_model_id = model_id
        if 'VIDEO' in output_modalities:
            video_success_status = test_video_model(model_id)
            results[model_id]['TEXT'] = video_success_status
            if 'nova' in model_id.lower():
                results[model_id]['IMAGE'] = video_success_status
            
    for model_id, model_info in results.items():
        if model_info['TEXT'] or model_info['DOCUMENT'] or model_info['IMAGE'] or model_info['VIDEO']:
            model_info['access_granted'] = True
            if 'nova' in model_id.lower() and video_helper_image_model_id:
                model_info['video_helper_image_model_id'] = video_helper_image_model_id
            
        
    # Update DynamoDB with the results
    update_dynamodb(results)
    
    # Submit metrics to CloudWatch using Embedded Metric Format
    metrics.add_metric(name="TotalInputTokens", unit=MetricUnit.Count, value=total_input_tokens)
    metrics.add_metric(name="TotalOutputTokens", unit=MetricUnit.Count, value=total_output_tokens)
    
def load_1px_image():
    """Loads red_pixel.png image"""
    with open('./red_pixel.png', 'rb') as f:
        return f.read()

def load_pdf():
    """Loads a PDF with the number 25"""
    with open('./25.pdf', 'rb') as f:
        return f.read()
 
def load_mp4():
    """Loads a MP4 from ./AWS-SMALL.mp4 with an aws cloud rotating for 1 second"""
    with open('./AWS-SMALL.mp4', 'rb') as f:
        return f.read()
    
def test_video_model(model_id):
    """ tests video model for access"""
    duration_seconds=6
    resolution='540p'
    aspect_ratio='16:9'
    if 'luma' in model_id.lower():
        duration_seconds = 5
    video_url, success_status, error_message = commons.generate_video('dog', model_id,'modelscan','ms',bedrock_runtime,s3_client,video_bucket,2,logger, cloudfront_domain,duration_seconds,0,True,[],resolution, aspect_ratio)
    return success_status
    
def test_image_model(model_id) -> bool:
    """ tests image model for access"""
    if 'titan' in model_id or 'nova' in model_id:
        image_base64,success_status,error_message = commons.generate_image_titan_nova(logger,bedrock_runtime,model_id, 'dog', None, None,5)
        if image_base64 is None:
            return False
        return True
    elif 'stability' in model_id:
        image_base64,success_status,error_message = commons.generate_image_stable_diffusion(logger,bedrock_runtime,model_id, 'dog', None, None,None,5,10)
        if image_base64 is None:
            return False
        return True
    else:
        raise ValueError(f"Unsupported model: {model_id}")
    return False
def update_dynamodb(results):
    """ updates config in dynamodb """
    try:
        # Get the current item if it exists
        response = config_table.get_item(
            Key={
                'user': 'models',
                'config_type': 'models'
            }
        )
        
        current_timestamp = datetime.now(timezone.utc).isoformat()
        
        if 'Item' in response:
            # If the item exists, move the current config to previous_config
            update_expression = "SET config = :new_config, previous_config = config, last_update_timestamp = :timestamp"
            expression_attribute_values = {
                ':new_config': results,
                ':timestamp': current_timestamp
            }
        else:
            # If the item doesn't exist, create a new one without previous_config
            update_expression = "SET config = :new_config, last_update_timestamp = :timestamp"
            expression_attribute_values = {
                ':new_config': results,
                ':timestamp': current_timestamp
            }
        
        # Update the item in DynamoDB
        config_table.update_item(
            Key={
                'user': 'models',
                'config_type': 'models'
            },
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values
        )
        
        logger.info("Successfully updated DynamoDB")
    except Exception as e:
        logger.exception(e)
        logger.error(f"Error updating DynamoDB: {str(e)}")
        
def start_custom_model_deployment_to_s3():
    """
    Queries CodeBuild projects and S3 bucket to determine if deployment is needed.
    If deployment is needed, starts the CodeBuild project.
    
    Returns:
        bool: False if no deployment is needed, True if deployment was started.
    """

    try:
        response = codebuild_client.list_projects()
        project_names = response.get('projects', [])
        
        target_projects = [name for name in project_names if name.startswith('GenAIChatBotCustomModel')]
        
        if not target_projects:
            print("No CodeBuild projects found with the prefix 'GenAIChatBotCustomModel'.")
            return False 
        
        codebuild_project_name = target_projects[0]
        print(f"Found CodeBuild project: {codebuild_project_name}")
    
    except ClientError as e:
        print(f"Error querying CodeBuild projects: {e}")
        return False

    try:
        # check to see if codebuild project is already running
        response = codebuild_client.list_builds_for_project(projectName=codebuild_project_name, sortOrder='DESCENDING')
        batch_response = codebuild_client.batch_get_builds(ids=response['ids'][:10])
        # if any builds are running, return False
        for build in batch_response['builds']:
            if build['buildStatus'] == 'IN_PROGRESS':
                print(f"CodeBuild project '{codebuild_project_name}' is already running.")
                return False
        build_response = codebuild_client.start_build(projectName=codebuild_project_name)
        print(f"Started CodeBuild project '{codebuild_project_name}'. Build ID: {build_response['build']['id']}")
        return True
    
    except ClientError as e:
        print(f"Error starting CodeBuild project '{codebuild_project_name}': {e}")
        return False