import json, boto3, os
from datetime import datetime, timezone
from aws_lambda_powertools import Logger, Metrics, Tracer
from chatbot_commons import commons
from conversations import conversations
import random
import string
import jwt


# Initialize Bedrock client
bedrock = boto3.client(service_name="bedrock-agent-runtime")
dynamodb = boto3.client('dynamodb')
table_name = os.environ.get('DYNAMODB_TABLE')
table = boto3.resource('dynamodb').Table(table_name)
WEBSOCKET_API_ENDPOINT = os.environ['WEBSOCKET_API_ENDPOINT']
conversations_table_name = os.environ['CONVERSATIONS_DYNAMODB_TABLE']
conversations_table = boto3.resource('dynamodb').Table(conversations_table_name)

logger = Logger(service="BedrockAgentsClient")
metrics = Metrics()
tracer = Tracer()


# AWS API Gateway Management API client
apigateway_management_api = boto3.client('apigatewaymanagementapi', endpoint_url=f"{WEBSOCKET_API_ENDPOINT.replace('wss', 'https')}/ws")
bedrock_agent_client = boto3.client(service_name='bedrock-agent')

@tracer.capture_lambda_handler
def lambda_handler(event, context):
    # logger.info("Executing Bedrock Agents Client Function")
    # print event
    print('SDK EVENT AGENTS')
    print(event)
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
    id_token = request_body.get('idToken', 'none')
    decoded_token = jwt.decode(id_token, algorithms=["RS256"], options={"verify_signature": False})
    user_id = decoded_token['cognito:username']
    selected_mode = request_body.get('selectedMode', 'none')
    category = selected_mode.get('category','')
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
    chat_title = prompt[:16] if len(prompt) > 16 else prompt    
    message_id = request_body.get('message_id', '')
    if selected_mode.get('category') == 'Bedrock KnowledgeBases':
        selected_knowledgebase_id = selected_mode.get('knowledgeBaseId')
        selected_kb_mode = request_body.get('selectedKbMode', 'none')
        selected_model_id = selected_kb_mode.get('modelArn')
        retrieveAndGenerateConfigurationData={
            'knowledgeBaseConfiguration': {
                'knowledgeBaseId': selected_knowledgebase_id, 
                'modelArn':selected_model_id,
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
            
        # SDK TODO get existing history
        existing_history = []
        new_conversation = bool(not existing_history or len(existing_history) == 0)    
        response_text, kb_session_id = process_bedrock_knowledgebase_response(response, message_id, connection_id, session_id,selected_mode.get('category'),chat_title,new_conversation)
        store_bedrock_knowledgebase_response(prompt,response_text, existing_history, message_id, session_id,kb_session_id,user_id,selected_knowledgebase_id, selected_model_id,selected_mode.get('category'), chat_title)
        
    elif selected_mode.get('category') == 'Bedrock Agents':
        response_stream_key = 'completion'
        selected_agent_id = selected_mode.get('agentId'),
        selected_agent_alias_id = selected_mode.get('agentAliasId')
        response = bedrock.invoke_agent(
                agentAliasId=selected_agent_alias_id,
                agentId=selected_agent_id,
                enableTrace=False,
                endSession=False,
                inputText=prompt,
                sessionId=session_id,
            )
        # SDK TODO get existing history
        existing_history = []
        new_conversation = bool(not existing_history or len(existing_history) == 0)
        content = process_bedrock_agents_response(iter(response[response_stream_key]), message_id, connection_id, selected_mode.get('category'),"Agent-"+selected_mode.get('agentAliasId'),session_id,chat_title,new_conversation)
        store_bedrock_agents_response(prompt,response_text, existing_history, message_id, session_id,user_id,selected_agent_id, selected_agent_alias_id, category, chat_title)
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
        # SDK TODO get existing history
        existing_history = []
        new_conversation = bool(not existing_history or len(existing_history) == 0)
        response_text = process_bedrock_agents_response(iter(response[response_stream_key]), message_id, connection_id, selected_mode.get('category'),"PromptFlow-"+selected_mode.get('id'),session_id,chat_title, new_conversation)
        store_bedrock_agents_response(prompt,response_text, existing_history, message_id, session_id,user_id,selected_agent_id, selected_agent_alias_id, category,chat_title)
            
@tracer.capture_method        
def process_bedrock_knowledgebase_response(response, message_id, connection_id, session_id,backend_type,chat_title,new_conversation):
    counter = 0
    commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                        'type': 'message_start',
                        'message_id': message_id,
                        'session_id':session_id,
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
                    'session_id':session_id,
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
                    'session_id':session_id,
                    'backend_type': backend_type
                })
    
    commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
            'type': 'message_title',
            'message_id': message_id,
            'title': chat_title
        })
    commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                'type': 'message_stop',
                'message_id': message_id,
                'new_conversation': new_conversation,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'kb_session_id':kb_session_id,
                'session_id':session_id,
                'backend_type': backend_type
            })
    return content,kb_session_id
    
@tracer.capture_method
def process_bedrock_agents_response(response_stream, message_id, connection_id, backend_type,selected_model_id,session_id,chat_title,new_conversation):
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
                    'session_id':session_id,
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
                    'session_id':session_id,
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
                            'session_id':session_id,
                            'new_conversation': new_conversation,
                            'timestamp': datetime.now(timezone.utc).isoformat(),
                            'backend_type': backend_type
                        })
                        message_stop_sent = True
                else:
                    # Send an error message to the WebSocket client
                    commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                        'type': 'error',
                        'message_id': message_id,
                        'session_id':session_id,
                        'code': '9200',
                        'error': 'Flow completion event with non-success reason'
                    })

        commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
            'type': 'message_title',
            'message_id': message_id,
            'title': chat_title
        })
        if counter > 0 and not message_stop_sent:
            # Send the message_stop event to the WebSocket client
            commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                'type': 'message_stop',
                'message_id': message_id,
                'session_id':session_id,
                'new_conversation': new_conversation,
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
            'session_id':session_id,
            'code': '9200',
            'error': str(e)
        })
        if counter > 0:
            logger.error('Sending message stop now...(error)')
            commons.send_websocket_message(logger, apigateway_management_api, connection_id, {'type': 'message_stop','message_id': message_id,'session_id':session_id,'new_conversation': new_conversation,})

    return result_text

@tracer.capture_method    
def store_conversation_history_converse(session_id, selected_model_id, existing_history,
    converse_content_array, user_message, assistant_message, user_id,
    input_tokens, output_tokens, message_end_timestamp_utc,
    message_received_timestamp_utc, message_id, title,new_conversation,selected_model_category):
    """Function to store conversation history in DDB"""
    
    if not (user_message.strip() and assistant_message.strip()):
        if not user_message.strip():
            logger.info(f"User message is empty, skipping storage for session ID: {session_id}")
        if not assistant_message.strip():
            logger.info(f"Assistant response is empty, skipping storage for session ID: {session_id}")
        return

    prefix = rf'{user_id}/{session_id}'
    
    # Prepare the updated conversation history once
    conversation_history = existing_history + [
        {
            'role': 'user',
            'content': converse_content_array,
            'timestamp': message_received_timestamp_utc,
            'message_id': message_id
        },
        {
            'role': 'assistant',
            'content': [{'text': assistant_message}],
            'timestamp': message_end_timestamp_utc,
            'message_id': generate_random_string()
        }
    ]
    
    # Convert to JSON string once
    conversation_json = json.dumps(conversation_history)
    conversation_history_size = len(conversation_json.encode('utf-8'))
    current_timestamp = str(datetime.now(tz=timezone.utc).timestamp())
    
    try:
        # Store in DynamoDB
        logger.info(f"Storing TITLE for conversation history in DynamoDB: {title}")
        if new_conversation:
            print('SDK: 55455: Storing a new conversation')
            dynamodb.put_item(
                TableName=conversations_table_name,
                Item={
                    'session_id': {'S': session_id},
                    'user_id': {'S': user_id},
                    'title': {'S': title},
                    'last_modified_date': {'N': current_timestamp},
                    'selected_model_id': {'S': selected_model_id},
                    'category': {'S': selected_model_category},
                    'conversation_history': {'S': conversation_json},
                    'conversation_history_in_s3': {'BOOL': False}
                }
            )
        else:
            print('SDK: 55455: UPDATING an existing conversation')
            dynamodb.update_item(
                TableName=conversations_table_name,
                Key={'session_id': {'S': session_id}},
                UpdateExpression="SET last_modified_date = :current_time, title = :title, selected_model_id = :selected_model_id, conversation_history = :conversation_history, category = :category",
                ExpressionAttributeValues={
                    ':current_time': {'N': current_timestamp},
                    ':title': {'S': title},
                    ':selected_model_id': {'S': selected_model_id},
                    ':conversation_history': {'S': conversation_json},
                    ':category': {'S': selected_model_category},
                }
            )
        
        # Batch token usage update
        save_token_usage(user_id, input_tokens, output_tokens)
        
    except (ClientError, Exception) as e:
        logger.error(f"Error storing conversation history: {e}")
        raise
    
def store_bedrock_knowledgebase_response(prompt,response_text, existing_history, message_id, session_id,kb_session_id,user_id,selected_knowledgebase_id, selected_model_id,selected_model_category, chat_title):
    conversation_history = existing_history + [
        {
            'role': 'user',
            'content': [{'text': prompt}],
            'timestamp': datetime.now(tz=timezone.utc).isoformat(),
            'message_id': message_id
        },
        {
            'role': 'assistant',
            'content': [{'text': response_text}],
            'timestamp': datetime.now(tz=timezone.utc).isoformat(),
            'message_id': generate_random_string()
        }
    ]
    conversation_json = json.dumps(conversation_history)
    current_timestamp = str(datetime.now(tz=timezone.utc).timestamp())
    dynamodb.put_item(
        TableName=conversations_table_name,
        Item={
            'session_id': {'S': session_id},
            'user_id': {'S': user_id},
            'title': {'S': chat_title},
            'last_modified_date': {'N': current_timestamp},
            'selected_knowledgebase_id': {'S': selected_knowledgebase_id},
            'selected_model_id': {'S': selected_model_id},
            'kb_session_id': {'S': kb_session_id},
            'category': {'S': selected_model_category},
            'conversation_history': {'S': conversation_json},
            'conversation_history_in_s3': {'BOOL': False}
        }
    )

def store_bedrock_agents_response(prompt,response_text, existing_history, message_id, session_id,user_id,selected_agent_id, selected_agent_alias_id, category, chat_title):
    conversation_history = existing_history + [
        {
            'role': 'user',
            'content': [{'text': prompt}],
            'timestamp': datetime.now(tz=timezone.utc).isoformat(),
            'message_id': message_id
        },
        {
            'role': 'assistant',
            'content': [{'text': response_text}],
            'timestamp': datetime.now(tz=timezone.utc).isoformat(),
            'message_id': generate_random_string()
        }
    ]
    conversation_json = json.dumps(conversation_history)
    current_timestamp = str(datetime.now(tz=timezone.utc).timestamp())
    dynamodb.put_item(
        TableName=conversations_table_name,
        Item={
            'session_id': {'S': session_id},
            'user_id': {'S': user_id},
            'title': {'S': chat_title},
            'last_modified_date': {'N': current_timestamp},
            'selected_agent_id': {'S': selected_agent_id},
            'selected_agent_alias_id': {'S': selected_agent_alias_id},
            'category': {'S': category},
            'conversation_history': {'S': conversation_json},
            'conversation_history_in_s3': {'BOOL': False}
        }
    )
    
def generate_random_string(length=8):
    """Function to generate a random String of length 8"""
    characters = string.ascii_lowercase + string.digits
    random_part = ''.join(random.choice(characters) for _ in range(length))
    return f"RES{random_part}"
    
    
    