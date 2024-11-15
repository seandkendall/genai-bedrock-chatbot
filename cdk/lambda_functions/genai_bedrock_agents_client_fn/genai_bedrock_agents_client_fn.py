import json, boto3, os
from datetime import datetime, timezone
from aws_lambda_powertools import Logger, Metrics, Tracer
from chatbot_commons import commons


# Initialize Bedrock client
bedrock = boto3.client(service_name="bedrock-agent-runtime")
dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('DYNAMODB_TABLE')
table = dynamodb.Table(table_name)
WEBSOCKET_API_ENDPOINT = os.environ['WEBSOCKET_API_ENDPOINT']

logger = Logger(service="BedrockAgentsClient")
metrics = Metrics()
tracer = Tracer()


# AWS API Gateway Management API client
apigateway_management_api = boto3.client('apigatewaymanagementapi', endpoint_url=f"{WEBSOCKET_API_ENDPOINT.replace('wss', 'https')}/ws")
bedrock_agent_client = boto3.client(service_name='bedrock-agent')

@tracer.capture_lambda_handler
def lambda_handler(event, context):
    # logger.info("Executing Bedrock Agents Client Function")
    force_null_kb_session_id = False
    while True:
        try:    
            # Check if the event is a WebSocket event
            if event['requestContext']['eventType'] == 'MESSAGE':
                # Handle WebSocket message
                process_websocket_message(event, force_null_kb_session_id)

            return {'statusCode': 200}

        except Exception as e:
            logger.exception(e)
            logger.error("Error 7460: " + str(e))
            if 'Session with Id' in str(e) and 'is not valid. Please check and try again' in str(e):
                logger.error("Removing Session ID and trying again")
                force_null_kb_session_id = True
            else:
                connection_id = event['requestContext']['connectionId']
                commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                    'type': 'error',
                    'code':'7460',
                    'error': str(e)
                })
                return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}

@tracer.capture_method
def process_websocket_message(event, force_null_kb_session_id):
    request_body = json.loads(event['body'])
    selected_mode = request_body.get('selectedMode', 'none')
    session_id = request_body.get('session_id', 'XYZ')
    tracer.put_annotation(key="SessionID", value=session_id)
    if force_null_kb_session_id:
        kb_session_id = 'null'
    else:
        kb_session_id =  request_body.get('kb_session_id', '')
    tracer.put_annotation(key="KBSessionID", value=kb_session_id)
    if(kb_session_id == 'undefined'):
        kb_session_id = ''
    connection_id = event['requestContext']['connectionId']

    # Check if the WebSocket connection is open
    try:
        connection = apigateway_management_api.get_connection(ConnectionId=connection_id)
        connection_state = connection.get('ConnectionStatus', 'OPEN')
        if connection_state != 'OPEN':
            logger.warn(f"WebSocket connection is not open (state: {connection_state})")
            return
    except apigateway_management_api.exceptions.GoneException:
        logger.warn(f"WebSocket connection is closed (connectionId: {connection_id})")
        return
    
    prompt = request_body.get('prompt', '')
    message_id = request_body.get('message_id', '')
    if selected_mode.get('category') == 'Bedrock KnowledgeBases':
        selected_kb_mode = request_body.get('selectedKbMode', 'none')
        retrieveAndGenerateConfigurationData={
            'knowledgeBaseConfiguration': {
                'knowledgeBaseId': selected_mode.get('knowledgeBaseId'), 
                'modelArn':selected_kb_mode.get('modelArn'),
                'retrievalConfiguration': {
                    'vectorSearchConfiguration': {
                        'numberOfResults': 20,
                        'overrideSearchType': 'HYBRID',
                    }
                }
            },
            'type': 'KNOWLEDGE_BASE',
        }

        if not kb_session_id or kb_session_id == 'null':
            response = bedrock.retrieve_and_generate(
                input={'text': prompt},
                retrieveAndGenerateConfiguration=retrieveAndGenerateConfigurationData,
            )
        else:
            response = bedrock.retrieve_and_generate(
                input={'text': prompt},
                retrieveAndGenerateConfiguration=retrieveAndGenerateConfigurationData,
                sessionId=kb_session_id,
            )
            
        process_bedrock_knowledgebase_response(response, message_id, connection_id, 'Knowledgebase')
    elif selected_mode.get('category') == 'Bedrock Agents':
        response_stream_key = 'completion'
        response = bedrock.invoke_agent(
                agentAliasId=selected_mode.get('agentAliasId'),
                agentId=selected_mode.get('agentId'),
                enableTrace=False,
                endSession=False,
                inputText=prompt,
                sessionId=session_id,
            )
        process_bedrock_agents_response(iter(response[response_stream_key]), message_id, connection_id, "Agent","Agent-"+selected_mode.get('agentAliasId'))
    elif selected_mode.get('category') == 'Bedrock Prompt Flows':
        response_stream_key = 'responseStream'
        response = bedrock.invoke_flow(
                flowAliasIdentifier=selected_mode.get('id'),
                flowIdentifier=selected_mode.get('flowId'),
                inputs=[
                    {   'nodeName': 'FlowInputNode',
                        'nodeOutputName': 'document',
                        'content': {
                            'document': prompt
                        },
                    }
                ],
            )
        process_bedrock_agents_response(iter(response[response_stream_key]), message_id, connection_id, "AgentPromptFlow","PromptFlow-"+selected_mode.get('id'))
            
@tracer.capture_method        
def process_bedrock_knowledgebase_response(response, message_id, connection_id, backend_type):
    counter = 0
    commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                        'type': 'message_start',
                        'message_id': message_id,
                        'message': 'Agent response started'
                    })
    counter += 1

    content = response['output']['text']
    citations = response['citations']
    kb_session_id = response['sessionId']
    
    commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                    'type': 'content_block_delta',
                    'message_id': message_id,
                    'delta': {'text': content},
                    'message_counter': counter,
                    'kb_session_id':kb_session_id,
                    'backend_type': backend_type
                })
    #if citations is not None, then for each citations send to websocket
    if citations is not None:
        for citation in citations:
            commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                    'type': 'citation_data',
                    'message_id': message_id,
                    'delta': citation,
                    'kb_session_id':kb_session_id,
                    'backend_type': backend_type
                })
    
    commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                'type': 'message_stop',
                'message_id': message_id,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'kb_session_id':kb_session_id,
                'backend_type': backend_type
            })
    
@tracer.capture_method
def process_bedrock_agents_response(response_stream, message_id, connection_id, backend_type,selected_model_id):
    result_text = ""
    counter = 0
    message_stop_sent = False
    message_type = 'content_block_delta'
    try:
        for event in response_stream:
            if 'chunk' in event:
                chunk = event['chunk']
                try:
                    content_chunk = chunk['bytes'].decode('utf-8')
                except (UnicodeDecodeError, AttributeError):
                    # Skip this event if the bytes value is not a valid UTF-8 string
                    continue

                if counter == 0:
                    message_type = 'message_start';

                # Send the content_block_delta event to the WebSocket client
                commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                    'type': message_type,
                    'message_id': message_id,
                    'message': {"model": selected_model_id},
                    'delta': {'text': content_chunk},
                    'message_counter': counter,
                    'backend_type': backend_type
                })
                message_type = 'content_block_delta'
                counter += 1

                result_text += content_chunk
            elif 'flowOutputEvent' in event:
                flow_output_event = event['flowOutputEvent']
                content = flow_output_event['content']['document']
                
                if counter == 0:
                    message_type = 'message_start';
                    
                commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                    'type': message_type,
                    'message_id': message_id,
                    'message': {"model": selected_model_id},
                    'delta': {'text': content},
                    'message_counter': counter,
                    'backend_type': backend_type
                })
                message_type = 'content_block_delta'
                counter += 1
                result_text += content
            elif 'flowCompletionEvent' in event:
                flow_completion_event = event['flowCompletionEvent']
                if flow_completion_event['completionReason'] == 'SUCCESS':
                    if counter > 0:
                        # Send the message_stop event to the WebSocket client
                        commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                            'type': 'message_stop',
                            'message_id': message_id,
                            'timestamp': datetime.now(timezone.utc).isoformat(),
                            'backend_type': backend_type
                        })
                        message_stop_sent = True
                else:
                    # Send an error message to the WebSocket client
                    commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                        'type': 'error',
                        'message_id': message_id,
                        'code': '9200',
                        'error': 'Flow completion event with non-success reason'
                    })

        if counter > 0 and not message_stop_sent:
            # Send the message_stop event to the WebSocket client
            commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                'type': 'message_stop',
                'message_id': message_id,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'backend_type': backend_type
            })
        message_stop_sent = True

    except Exception as e:
        logger.exception(e)
        logger.error(f"Error processing Bedrock response: {str(e)}")
        # Send an error message to the WebSocket client
        commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
            'type': 'error',
            'message_id': message_id,
            'code': '9200',
            'error': str(e)
        })
        if counter > 0:
            logger.error('Sending message stop now...(error)')
            commons.send_websocket_message(logger, apigateway_management_api, connection_id, {'type': 'message_stop','message_id': message_id,})

    return result_text