import boto3
import json
import os
import logging
from chatbot_commons import commons
from botocore.exceptions import ClientError
from datetime import datetime, timezone
from aws_lambda_powertools import Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit


logger = logging.getLogger()
logger.setLevel(logging.INFO)
tracer = Tracer()
metrics = Metrics()
WEBSOCKET_API_ENDPOINT = os.environ['WEBSOCKET_API_ENDPOINT']
allowlist_domain = os.environ['ALLOWLIST_DOMAIN']
user_pool_id = os.environ['USER_POOL_ID']
config_table_name = os.environ.get('CONFIG_DYNAMODB_TABLE')
bedrock = boto3.client('bedrock')
bedrock_runtime = boto3.client('bedrock-runtime')
cognito_client = boto3.client('cognito-idp')
apigateway_management_api = boto3.client('apigatewaymanagementapi', 
                                         endpoint_url=f"{WEBSOCKET_API_ENDPOINT.replace('wss', 'https')}/ws")
config_table = boto3.resource('dynamodb').Table(config_table_name)
user_cache = {}

@metrics.log_metrics
def lambda_handler(event, context):
    is_websocket_event = False
    
    if 'requestContext' in event:
        is_websocket_event = True
        request_context = event['requestContext']
        if 'connectionId' in request_context:
            connection_id = event['requestContext']['connectionId']
            # Check if the WebSocket connection is open
            try:
                connection = apigateway_management_api.get_connection(ConnectionId=connection_id)
                connection_state = connection.get('ConnectionStatus', 'OPEN')
                if connection_state != 'OPEN':
                    logger.info(f"WebSocket connection is not open (state: {connection_state})")
                    return
            except apigateway_management_api.exceptions.GoneException:
                logger.error(f"WebSocket connection is closed (connectionId: {connection_id})")
                return

        try:
            request_body = json.loads(event.get('body', '{}'))
        except json.JSONDecodeError:
            request_body = {}
        access_token = request_body.get('accessToken', 'none')
        try:
            allowed, not_allowed_message = commons.validate_jwt_token(cognito_client, user_cache,allowlist_domain,access_token)
        except ClientError as e:
            allowed, not_allowed_message = (False, "Your Access Token has expired. Please log in again.") if e.response['Error']['Code'] == 'NotAuthorizedException' else (None, None)
            
        if not allowed:
            return {
                'statusCode': 403,
                'body': json.dumps({'error': not_allowed_message})
            }
    
    active_models = scan_for_active_models()
    commons.send_websocket_message(logger, apigateway_management_api, connection_id, {'type':'modelscan','results':active_models,'timestamp': datetime.now(timezone.utc).isoformat(),})
    return {
        'statusCode': 200,
        'body': json.dumps(active_models, indent=2)
    }
def scan_for_active_models():
    """ Scans for active models in Bedrock """
    try:
        
        list_foundation_models_response = bedrock.list_foundation_models(byInferenceType='ON_DEMAND')
        all_models = list_foundation_models_response.get('modelSummaries', [])
    except ClientError as e:
        logger.exception(e)
        logger.error("Error listing foundation models: %s",str(e))
        return {
            'statusCode': 500,
            'body': json.dumps(f"Error listing foundation models: {str(e)}")
        }
    
    active_models = [model for model in all_models if model['modelLifecycle']['status'] == 'ACTIVE']
    
    results = {}
    
    total_input_tokens = 0
    total_output_tokens = 0
    for model in active_models:
        model_id = model['modelId']
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
                'IMAGE': False,
                'DOCUMENT': False,
                'access_granted': False,
                'mode_selector': model['modelArn'],
                'mode_selector_name': model['modelName']
            }
        if 'TEXT' in output_modalities:
            prompts = []
            prompts.append(('TEXT', "reply with '1'"))
            prompts.append(('IMAGE', "what color is this?"))
            prompts.append(('DOCUMENT', "what number is in the document?"))
            
            for prompt_type, prompt_text in prompts:
                try:
                    content = [{"text": prompt_text}]
                    if prompt_type == 'IMAGE':
                        image_bytes  = load_1px_image()
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
                    
                    response = bedrock_runtime.converse(
                        modelId=model_id,
                        messages=[
                            {
                                "role": "user",
                                "content": content
                            }
                        ]
                    )
                    
                    total_input_tokens += response['usage']['inputTokens']
                    total_output_tokens += response['usage']['outputTokens']
                    
                    results[model_id][prompt_type] = True
                except ClientError as e:
                    error_code = e.response['Error']['Code']
                    if error_code == 'ThrottlingException':
                        results[model_id][prompt_type] = True
                        logger.warning(f"ThrottlingException for model {model_id}, prompt type {prompt_type}: {str(e)}")
                    elif error_code == 'ValidationException':
                        # log warning
                        logger.warning(f"ValidationException for model {model_id}, prompt type {prompt_type}: {str(e)}")
                    elif error_code == 'AccessDeniedException':
                        logger.warning(f"AccessDeniedException for model {model_id}, prompt type {prompt_type}: {str(e)}")
                    else:
                        logger.warning(f"ClientError for model {model_id}, prompt type {prompt_type}: {str(e)}")
                except Exception as e:
                    logger.exception(e)
                    logger.error(f"Unexpected error for model {model_id}, prompt type {prompt_type}: {str(e)}")
        if 'IMAGE' in output_modalities:
            results[model_id]['TEXT'] = test_image_model(model_id)
            
            
    for model_id, model_info in results.items():
        # if TEXT = True or DOCUMENT = True or IMAGE = true then access_granted = True
        if model_info['TEXT'] or model_info['DOCUMENT'] or model_info['IMAGE']:
            model_info['access_granted'] = True
            
        
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
def test_image_model(model_id):
    """ tests image model for access"""
    if 'titan' in model_id:
        image_base64 = commons.generate_image_titan(logger,bedrock_runtime,model_id, 'dog', None, None,5)
        if image_base64 is None:
            return False
        return True
    elif 'stability' in model_id:
        image_base64 = commons.generate_image_stable_diffusion(logger,bedrock_runtime,model_id, 'dog', None, None,None,5,10)
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
        