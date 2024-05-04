import json
import boto3
import os
from aws_lambda_powertools import Tracer


# Initialize Bedrock client
bedrock = boto3.client(service_name="bedrock-agent-runtime")
dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('DYNAMODB_TABLE')
table = dynamodb.Table(table_name)
WEBSOCKET_API_ENDPOINT = os.environ['WEBSOCKET_API_ENDPOINT']
tracer = Tracer()

# AWS API Gateway Management API client
apigateway_management_api = boto3.client('apigatewaymanagementapi', endpoint_url=f"{WEBSOCKET_API_ENDPOINT.replace('wss', 'https')}/ws")

bedrock_agents_id = ''
bedrock_agents_alias_id = ''
bedrock_knowledgebase_id = ''

@tracer.capture_lambda_handler
def lambda_handler(event, context):
    global bedrock_agents_id, bedrock_agents_alias_id, bedrock_knowledgebase_id 

    try:
        if not bedrock_agents_id or not bedrock_agents_alias_id or not bedrock_knowledgebase_id:
            bedrock_agents_id, bedrock_agents_alias_id, bedrock_knowledgebase_id = load_config()
            print(f"Bedrock agents id: {bedrock_agents_id}")
            tracer.put_annotation(key="BedrockAgentsId", value=bedrock_agents_id)
            print(f"Bedrock agents alias id: {bedrock_agents_alias_id}")
            tracer.put_annotation(key="BedrockAgentsAliasId", value=bedrock_agents_alias_id)
            print(f"Loaded Bedrock Knowledgebase id: {bedrock_knowledgebase_id}")
            tracer.put_annotation(key="BedrockKnowledgeBaseId", value=bedrock_knowledgebase_id)
            
        # Check if the event is a WebSocket event
        if event['requestContext']['eventType'] == 'MESSAGE':
            # Handle WebSocket message
            process_websocket_message(event, bedrock_agents_id, bedrock_agents_alias_id, bedrock_knowledgebase_id)

        return {'statusCode': 200}

    except Exception as e:
        print("Error 7460: " + str(e))
        bedrock_agents_id = ''
        bedrock_agents_alias_id = ''
        bedrock_knowledgebase_id = ''
        send_websocket_message(event['requestContext']['connectionId'], {
            'type': 'error',
            'code':'7460',
            'error': str(e)
        })
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}

@tracer.capture_method
def process_websocket_message(event,bedrock_agents_id,bedrock_agents_alias_id,bedrock_knowledgebase_id):
    # Extract the request body and session ID from the WebSocket event
    request_body = json.loads(event['body'])
    message_type = request_body.get('type', '')
    tracer.put_annotation(key="MessageType", value=message_type)
    session_id = request_body.get('session_id', 'XYZ')
    tracer.put_annotation(key="SessionID", value=session_id)
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
            print(f"WebSocket connection is not open (state: {connection_state})")
            return
    except apigateway_management_api.exceptions.GoneException:
        print(f"WebSocket connection is closed (connectionId: {connection_id})")
        return

    if message_type == 'clear_conversation':
        return
    elif message_type == 'load':
        return
    else:
        # Handle other message types (e.g., prompt)
        prompt = request_body.get('prompt', '')
        
        if request_body.get('knowledgebasesOrAgents', '') == 'knowledgeBases':
            if not bedrock_knowledgebase_id:
                send_websocket_message(connection_id, {
                    'type': 'error',
                    'code':'6450',
                    'error': 'No KnowledgeBaseID configured. please enter one on the settings screen'
                })
            else:
                selected_model = request_body.get('model')
                if isinstance(selected_model,str):
                    selected_model_id = selected_model
                else:
                    selected_model_id = selected_model.get('modelId').replace(' ','')
                print(f"Selected For Agents Client Model: {selected_model_id}")
                tracer.put_annotation(key="Model", value=selected_model_id)
                retrieveAndGenerateConfigurationData={
                        'knowledgeBaseConfiguration': {
                            'knowledgeBaseId': bedrock_knowledgebase_id,
                            'modelArn': selected_model_id,
                            'retrievalConfiguration': {
                                'vectorSearchConfiguration': {
                                    'numberOfResults': 20,
                                    'overrideSearchType': 'HYBRID'
                                }
                            }
                        },
                        'type': 'KNOWLEDGE_BASE'
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
                        sessionId=kb_session_id
                    )
                    
                process_bedrock_knowledgebase_response(response, connection_id, 'Knowledgebase')
        else:
            if not bedrock_agents_alias_id or not bedrock_agents_id:
                send_websocket_message(connection_id, {
                    'type': 'error',
                    'code':'8860',
                    'error': 'No Bedrock Agents alias ID or bedrock Agents ID configured. please enter these on the settings screen'
                })
            else:
                response = bedrock.invoke_agent(
                    agentAliasId=bedrock_agents_alias_id,
                    agentId=bedrock_agents_id,
                    enableTrace=False,
                    endSession=False,
                    inputText=prompt,
                    sessionId=session_id
                )
                process_bedrock_agents_response(iter(response['completion']), connection_id, 'Agent')
            
@tracer.capture_method        
def process_bedrock_knowledgebase_response(response, connection_id, backend_type):
    counter = 0
    send_websocket_message(connection_id, {
                        'type': 'message_start',
                        'message': 'Agent response started'
                    })
    counter += 1

    content = response['output']['text']
    citations = response['citations']
    kb_session_id = response['sessionId']
    
    send_websocket_message(connection_id, {
                    'type': 'content_block_delta',
                    'delta': {'text': content},
                    'message_id': counter,
                    'kb_session_id':kb_session_id,
                    'backend_type': backend_type
                })
    #if citations is not None, then for each citations send to websocket
    if citations is not None:
        for citation in citations:
            send_websocket_message(connection_id, {
                    'type': 'citation_data',
                    'delta': citation,
                    'kb_session_id':kb_session_id,
                    'backend_type': backend_type
                })
    
    send_websocket_message(connection_id, {
                'type': 'message_stop',
                'kb_session_id':kb_session_id,
                'backend_type': backend_type
            })
    
@tracer.capture_method
def process_bedrock_agents_response(response_stream, connection_id, backend_type):
    result_text = ""
    # new counter starting at 0
    counter = 0
    try:
        for event in response_stream:
            chunk = event.get('chunk', {})
            if chunk:
                try:
                    content_chunk = chunk['bytes'].decode('utf-8')
                except (UnicodeDecodeError, AttributeError):
                    # Skip this event if the bytes value is not a valid UTF-8 string
                    continue

                if counter == 0:
                    # Send the message_start event to the WebSocket client
                    send_websocket_message(connection_id, {
                        'type': 'message_start',
                        'message': 'Agent response started'
                    })

                # Increment counter by 1
                counter += 1

                # Send the content_block_delta event to the WebSocket client
                send_websocket_message(connection_id, {
                    'type': 'content_block_delta',
                    'delta': {'text': content_chunk},
                    'message_id': counter,
                    'backend_type': backend_type
                })

                result_text += content_chunk

        if counter > 0:
            # Send the message_stop event to the WebSocket client
            send_websocket_message(connection_id, {
                'type': 'message_stop',
                'backend_type': backend_type
            })

    except Exception as e:
        print(f"Error processing Bedrock response: {str(e)}")
        # Send an error message to the WebSocket client
        send_websocket_message(connection_id, {
            'type': 'error',
            'code':'9200',
            'error': str(e)
        })
        bedrock_agents_id = ''
        bedrock_agents_alias_id = ''
        bedrock_knowledgebase_id = ''
        if counter > 0:
            print('Sending message stop now...(error)')
            send_websocket_message(connection_id, {'type': 'message_stop'})

    return result_text

@tracer.capture_method
def send_websocket_message(connection_id, message):
    try:
        # Check if the WebSocket connection is open
        connection = apigateway_management_api.get_connection(ConnectionId=connection_id)
        connection_state = connection.get('ConnectionStatus', 'OPEN')
        if connection_state != 'OPEN':
            print(f"WebSocket connection is not open (state: {connection_state})")
            return

        apigateway_management_api.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(message).encode()
        )
    except apigateway_management_api.exceptions.GoneException:
        print(f"WebSocket connection is closed (connectionId: {connection_id})")
    except Exception as e:
        print(f"Error sending WebSocket message (672): {str(e)}")

@tracer.capture_method
def load_config():
    try:
        # Get the configuration from DynamoDB
        response = table.get_item(
            Key={
                'user': 'system',
                'config_type': 'system'
            }
        )

        config = response.get('Item', {}).get('config', {})
        bedrock_knowledgebase_id = config.get('bedrockKnowledgeBaseID')
        bedrock_agents_id = config.get('bedrockAgentsID')
        bedrock_agents_alias_id = config.get('bedrockAgentsAliasID')
        return bedrock_agents_id, bedrock_agents_alias_id, bedrock_knowledgebase_id

    except Exception as e:
        raise e