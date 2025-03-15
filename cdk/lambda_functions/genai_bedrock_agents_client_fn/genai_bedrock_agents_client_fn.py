import json
import boto3
import os
from datetime import datetime, timezone
from aws_lambda_powertools import Logger, Metrics, Tracer
from botocore.config import Config
from chatbot_commons import commons
from conversations import conversations
import copy

dynamodb = boto3.client("dynamodb")
s3_client = boto3.client("s3")
table_name = os.environ.get("DYNAMODB_TABLE")
table = boto3.resource("dynamodb").Table(table_name)
WEBSOCKET_API_ENDPOINT = os.environ["WEBSOCKET_API_ENDPOINT"]
conversation_history_bucket = os.environ["CONVERSATION_HISTORY_BUCKET"]
usage_table_name = os.environ["DYNAMODB_TABLE_USAGE"]
conversations_table_name = os.environ["CONVERSATIONS_DYNAMODB_TABLE"]
conversations_table = boto3.resource("dynamodb").Table(conversations_table_name)

logger = Logger(service="BedrockAgentsClient")
metrics = Metrics()
tracer = Tracer()
ENABLE_CITATIONS = False


# AWS API Gateway Management API client
apigateway_management_api = boto3.client(
    "apigatewaymanagementapi",
    endpoint_url=f"{WEBSOCKET_API_ENDPOINT.replace('wss', 'https')}/ws",
)
config = Config(retries={"total_max_attempts": 10, "mode": "standard"})
bedrock_agent_runtime = boto3.client("bedrock-agent-runtime", config=config)
bedrock_agent_client = boto3.client("bedrock-agent", config=config)


@tracer.capture_lambda_handler
def lambda_handler(event, context):
    """Lambda Hander Function"""
    force_null_kb_session_id = False
    while True:
        try:
            process_websocket_message(event, force_null_kb_session_id)
            return {"statusCode": 200}
        except Exception as e:
            # if str(e) does not contain ThrottlingException, then log exception
            if "ThrottlingException" not in str(e):
                logger.exception(e)
                logger.error("Error 7460: " + str(e))
            else:
                logger.warn("ThrottlingException: " + str(e))

            if "Session with Id" in str(
                e
            ) and "is not valid. Please check and try again" in str(e):
                logger.error("Removing Session ID and trying again")
                force_null_kb_session_id = True
            else:
                connection_id = event.get("connection_id", "ZYX")
                commons.send_websocket_message(
                    logger,
                    apigateway_management_api,
                    connection_id,
                    {"type": "error", "code": "7460", "error": str(e)},
                )
                return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


@tracer.capture_method
def process_websocket_message(request_body, force_null_kb_session_id):
    access_token = request_body.get("access_token", {})
    session_id = request_body.get("session_id", "XYZ")
    connection_id = request_body.get("connection_id", "ZYX")
    user_id = access_token["payload"]["sub"]
    message_type = request_body.get("type", "")
    selected_mode = request_body.get("selected_mode", {})
    selected_model_category = selected_mode.get("category")
    if force_null_kb_session_id:
        kb_session_id = "null"
    else:
        kb_session_id = request_body.get("kb_session_id", "")
    if kb_session_id == "undefined":
        kb_session_id = ""

    if session_id:
        tracer.put_annotation(key="SessionID", value=session_id)
    if user_id:
        tracer.put_annotation(key="UserID", value=user_id)
    if message_type:
        tracer.put_annotation(key="MessageType", value=message_type)
    if connection_id:
        tracer.put_annotation(key="ConnectionID", value=connection_id)
    if kb_session_id:
        tracer.put_annotation(key="KBSessionID", value=kb_session_id)

    # Check if the WebSocket connection is open
    try:
        connection = apigateway_management_api.get_connection(
            ConnectionId=connection_id
        )
        connection_state = connection.get("ConnectionStatus", "OPEN")
        if connection_state != "OPEN":
            logger.warn(f"WebSocket connection is not open (state: {connection_state})")
            return
    except apigateway_management_api.exceptions.GoneException:
        logger.warn(f"WebSocket connection is closed (connectionId: {connection_id})")
        return

    prompt = request_body.get("prompt", "")
    chat_title = prompt[:16] if len(prompt) > 16 else prompt
    message_id = request_body.get("message_id", "")
    new_message_id = commons.generate_random_string()
    if message_type == "clear_conversation":
        conversations.delete_conversation_history(
            dynamodb, conversations_table_name, logger, session_id
        )
        return
    elif message_type == "load":
        # Load conversation history from DynamoDB
        conversations.load_and_send_conversation_history(
            session_id,
            connection_id,
            user_id,
            dynamodb,
            conversations_table_name,
            s3_client,
            conversation_history_bucket,
            logger,
            commons,
            apigateway_management_api,
            False,
            False,
        )
        return
    else:
        if selected_model_category == "Bedrock KnowledgeBases":
            selected_knowledgebase_id = selected_mode.get("knowledgeBaseId")
            selected_kb_mode = request_body.get("selectedKbMode", "none")
            selected_model_id = selected_kb_mode.get("modelArn")
            selected_model_name = selected_model_id

            retrieveAndGenerateConfigurationData = {
                "knowledgeBaseConfiguration": {
                    "knowledgeBaseId": selected_knowledgebase_id,
                    "modelArn": selected_model_id,
                    "retrievalConfiguration": {
                        "vectorSearchConfiguration": {
                            "numberOfResults": 20,
                            "overrideSearchType": "HYBRID",
                        }
                    },
                },
                "type": "KNOWLEDGE_BASE",
            }

            response = None
            loop_counter = 0
            while not response and loop_counter < 3:
                loop_counter += 1
                try:
                    if not kb_session_id or kb_session_id == "null":
                        response = bedrock_agent_runtime.retrieve_and_generate_stream(
                            input={"text": prompt},
                            retrieveAndGenerateConfiguration=retrieveAndGenerateConfigurationData,
                        )
                    else:
                        response = bedrock_agent_runtime.retrieve_and_generate_stream(
                            input={"text": prompt},
                            retrieveAndGenerateConfiguration=retrieveAndGenerateConfigurationData,
                            sessionId=kb_session_id,
                        )
                except Exception as e:
                    if (
                        "Knowledge base configurations cannot be modified for an ongoing session"
                        in str(e)
                        or "is not valid. Please check and try again" in str(e)
                    ):
                        # reset kb_session_id and loop
                        kb_session_id = None
                    else:
                        logger.exception(e)
                        logger.error("Error 187464: " + str(e))

            needs_load_from_s3, chat_title_loaded, original_existing_history = (
                conversations.load_and_send_conversation_history(
                    session_id,
                    connection_id,
                    user_id,
                    dynamodb,
                    conversations_table_name,
                    s3_client,
                    conversation_history_bucket,
                    logger,
                    commons,
                    apigateway_management_api,
                    False,
                    True,
                )
            )
            existing_history = copy.deepcopy(original_existing_history)
            new_conversation = bool(not existing_history or len(existing_history) == 0)
            persisted_chat_title = (
                chat_title_loaded
                if chat_title_loaded and chat_title_loaded.strip()
                else chat_title
            )
            response_text, kb_session_id = (
                process_bedrock_knowledgebase_response_stream(
                    response,
                    new_message_id,
                    connection_id,
                    session_id,
                    selected_model_category,
                    persisted_chat_title,
                    new_conversation,
                    kb_session_id,
                )
            )
            store_bedrock_knowledgebase_response(
                prompt,
                response_text,
                existing_history,
                message_id,
                session_id,
                kb_session_id,
                user_id,
                selected_knowledgebase_id,
                selected_model_id,
                selected_model_name,
                selected_model_category,
                persisted_chat_title,
                new_message_id,
            )

        elif selected_model_category == "Bedrock Agents":
            response_stream_key = "completion"
            selected_agent_id = selected_mode.get("agentId")
            selected_agent_alias_id = selected_mode.get("agentAliasId")
            response = bedrock_agent_runtime.invoke_agent(
                agentAliasId=selected_agent_alias_id,
                agentId=selected_agent_id,
                enableTrace=True,
                endSession=False,
                inputText=prompt,
                sessionId=session_id,
            )
            (
                needs_load_fneeds_load_from_s3,
                chat_title_loaded,
                original_existing_history,
            ) = conversations.load_and_send_conversation_history(
                session_id,
                connection_id,
                user_id,
                dynamodb,
                conversations_table_name,
                s3_client,
                conversation_history_bucket,
                logger,
                commons,
                apigateway_management_api,
                False,
                True,
            )
            persisted_chat_title = (
                chat_title_loaded
                if chat_title_loaded and chat_title_loaded.strip()
                else chat_title
            )
            existing_history = copy.deepcopy(original_existing_history)
            new_conversation = bool(not existing_history or len(existing_history) == 0)
            response_text, contains_errors = process_bedrock_agents_response(
                iter(response[response_stream_key]),
                new_message_id,
                connection_id,
                selected_model_category,
                "Agent-" + selected_mode.get("agentAliasId"),
                session_id,
                persisted_chat_title,
                new_conversation,
            )
            if not contains_errors:
                store_bedrock_agents_response(
                    prompt,
                    response_text,
                    existing_history,
                    message_id,
                    session_id,
                    user_id,
                    selected_agent_id,
                    selected_agent_alias_id,
                    None,
                    None,
                    selected_model_category,
                    persisted_chat_title,
                    new_message_id,
                )
        elif selected_model_category == "Bedrock Prompt Flows":
            response_stream_key = "responseStream"
            flow_alias_id = selected_mode.get("id")
            flow_id = selected_mode.get("flowId")
            response = bedrock_agent_runtime.invoke_flow(
                flowAliasIdentifier=flow_alias_id,
                flowIdentifier=flow_id,
                inputs=[
                    {
                        "nodeName": "FlowInputNode",
                        "nodeOutputName": "document",
                        "content": {"document": prompt},
                    }
                ],
            )
            needs_load_from_s3, chat_title_loaded, original_existing_history = (
                conversations.load_and_send_conversation_history(
                    session_id,
                    connection_id,
                    user_id,
                    dynamodb,
                    conversations_table_name,
                    s3_client,
                    conversation_history_bucket,
                    logger,
                    commons,
                    apigateway_management_api,
                    False,
                    True,
                )
            )
            persisted_chat_title = (
                chat_title_loaded
                if chat_title_loaded and chat_title_loaded.strip()
                else chat_title
            )
            existing_history = copy.deepcopy(original_existing_history)
            new_conversation = bool(not existing_history or len(existing_history) == 0)
            response_text, contains_errors = process_bedrock_agents_response(
                iter(response[response_stream_key]),
                new_message_id,
                connection_id,
                selected_model_category,
                "PromptFlow-" + selected_mode.get("id"),
                session_id,
                persisted_chat_title,
                new_conversation,
            )
            if not contains_errors:
                store_bedrock_agents_response(
                    prompt,
                    response_text,
                    existing_history,
                    message_id,
                    session_id,
                    user_id,
                    None,
                    None,
                    flow_id,
                    flow_alias_id,
                    selected_model_category,
                    persisted_chat_title,
                    new_message_id,
                )


@tracer.capture_method
def process_bedrock_knowledgebase_response_stream(
    response,
    message_id,
    connection_id,
    session_id,
    backend_type,
    chat_title,
    new_conversation,
    kb_session_id,
):
    """
    Process a streaming response from Amazon Bedrock Knowledge Base and send updates via WebSocket.

    Args:
        response (dict): The streaming response from Bedrock Knowledge Base containing EventStream
        message_id (str): Unique identifier for the message being processed
        connection_id (str): WebSocket connection identifier for the client
        session_id (str): Session identifier for the current chat session
        backend_type (str): The type of backend model being used
        chat_title (str): Title of the chat conversation
        new_conversation (bool): Flag indicating if this is a new conversation
        kb_session_id (str): Existing kb_session_id

    Returns:
        tuple: A tuple containing:
            - str: The complete response content (concatenated from stream)
            - str: The Knowledge Base session ID

    Structure:
        1. Sends initial message_start notification
        2. Iterates through the stream:
           - Processes and sends content chunks as they arrive
           - Collects citations for later processing
        3. Sends chat title
        4. Processes and sends collected citations
        5. Sends message_stop notification

    WebSocket Message Types:
        - message_start: Indicates the start of the response
        - content_block_delta: Contains chunks of the response content
        - citation_data: Contains citation information
        - message_title: Contains the chat title
        - message_stop: Indicates the end of the response

    Stream Event Types:
        - output: Contains text chunks of the response
        - citation: Contains citation information
        - guardrail: Contains moderation information
        - Various exception events for error handling
    """
    counter = 0
    content = ""

    # if kb_session_id is null or empty
    if not kb_session_id or kb_session_id == "null":
        kb_session_id = response.get("sessionId")
    citations_list = []

    # Send initial message start
    commons.send_websocket_message(
        logger,
        apigateway_management_api,
        connection_id,
        {
            "type": "message_start",
            "message_id": message_id,
            "session_id": session_id,
            "message": "Agent response started",
        },
    )
    counter += 1

    # Process the stream
    for event in response["stream"]:
        if "output" in event:
            # Handle text output
            text_chunk = event["output"].get("text", "")
            if text_chunk:
                content += text_chunk
                commons.send_websocket_message(
                    logger,
                    apigateway_management_api,
                    connection_id,
                    {
                        "type": "content_block_delta",
                        "message_id": message_id,
                        "delta": {"text": text_chunk},
                        "message_counter": counter,
                        "kb_session_id": kb_session_id,
                        "session_id": session_id,
                        "backend_type": backend_type,
                    },
                )
                counter += 1

        elif "citation" in event:
            # Collect citations to send later
            if ENABLE_CITATIONS:
                citation_data = event["citation"]
                if citation_data:
                    citations_list.append(citation_data)

    # Send chat title
    commons.send_websocket_message(
        logger,
        apigateway_management_api,
        connection_id,
        {
            "type": "message_title",
            "message_id": message_id,
            "session_id": session_id,
            "title": chat_title,
        },
    )

    # Send collected citations
    if citations_list:
        for citation in citations_list:
            if len(str(citation)) > 10000:
                citation_parts = split_string_into_chunks(str(citation))
                for citation_part in citation_parts:
                    try:
                        commons.send_websocket_message(
                            logger,
                            apigateway_management_api,
                            connection_id,
                            {
                                "type": "citation_data_part",
                                "message_id": message_id,
                                "delta": citation_part,
                                "last_part": citation_part == citation_parts[-1],
                                "kb_session_id": kb_session_id,
                                "session_id": session_id,
                                "backend_type": backend_type,
                            },
                        )
                    except Exception as e:
                        logger.error(
                            "Error sending citation (part) data (not passing error to client)"
                        )
                        logger.exception(e)
            else:
                try:
                    commons.send_websocket_message(
                        logger,
                        apigateway_management_api,
                        connection_id,
                        {
                            "type": "citation_data",
                            "message_id": message_id,
                            "delta": citation,
                            "kb_session_id": kb_session_id,
                            "session_id": session_id,
                            "backend_type": backend_type,
                        },
                    )
                except Exception as e:
                    logger.error(
                        "Error sending citation data (not passing error to client)"
                    )
                    logger.exception(e)

    # Send message stop
    commons.send_websocket_message(
        logger,
        apigateway_management_api,
        connection_id,
        {
            "type": "message_stop",
            "message_id": message_id,
            "new_conversation": new_conversation,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "kb_session_id": kb_session_id,
            "session_id": session_id,
            "backend_type": backend_type,
        },
    )

    return content, kb_session_id


@tracer.capture_method
def process_bedrock_agents_response(
    response_stream,
    message_id,
    connection_id,
    backend_type,
    selected_model_id,
    session_id,
    chat_title,
    new_conversation,
):
    """
    Process a streaming response from Amazon Bedrock Agents and send updates via WebSocket.

    Args:
        response_stream (generator): The streaming response from Bedrock Agent containing chunks and flow events
        message_id (str): Unique identifier for the message being processed
        connection_id (str): WebSocket connection identifier for the client
        backend_type (str): The type of backend model being used
        selected_model_id (str): Identifier of the selected Bedrock model
        session_id (str): Session identifier for the current chat session
        chat_title (str): Title of the chat conversation
        new_conversation (bool): Flag indicating if this is a new conversation

    Returns:
        tuple: A tuple containing:
            - str: The complete response content (concatenated from stream)
            - bool: Flag indicating if any errors occurred during processing

    Stream Event Types:
        - chunk: Contains raw bytes of response content
        - flowOutputEvent: Contains structured output from the agent
        - flowCompletionEvent: Indicates completion status of the agent flow

    WebSocket Message Types:
        - message_start: First message sent for new content
        - content_block_delta: Subsequent content chunks
        - message_title: Contains the chat title
        - message_stop: Indicates end of response
        - error: Contains error information if processing fails

    Error Handling:
        - Handles UnicodeDecodeError for invalid UTF-8 content
        - Handles non-successful flow completion events
        - Handles general exceptions during processing
        - Ensures message_stop is sent even after errors
        - Uses error code '9200' for all error messages

    Notes:
        - The function is decorated with @tracer.capture_method for monitoring
        - Content is processed and sent in chunks for real-time updates
        - Maintains message ordering with counter
        - Ensures proper cleanup with message_stop in all scenarios
        - Logs errors for debugging purposes
    """
    result_text = ""
    counter = 0
    message_stop_sent = False
    contains_errors = False
    message_type = "content_block_delta"
    try:
        for event in response_stream:
            if "chunk" in event:
                chunk = event["chunk"]
                try:
                    content_chunk = chunk["bytes"].decode("utf-8")
                except (UnicodeDecodeError, AttributeError):
                    # Skip this event if the bytes value is not a valid UTF-8 string
                    continue

                if counter == 0:
                    message_type = "message_start"

                # Send the content_block_delta event to the WebSocket client
                commons.send_websocket_message(
                    logger,
                    apigateway_management_api,
                    connection_id,
                    {
                        "type": message_type,
                        "message_id": message_id,
                        "session_id": session_id,
                        "message": {"model": selected_model_id},
                        "delta": {"text": content_chunk},
                        "message_counter": counter,
                        "backend_type": backend_type,
                    },
                )
                message_type = "content_block_delta"
                counter += 1

                result_text += content_chunk
            elif "flowOutputEvent" in event:
                flow_output_event = event["flowOutputEvent"]
                content = flow_output_event["content"]["document"]

                if counter == 0:
                    message_type = "message_start"

                commons.send_websocket_message(
                    logger,
                    apigateway_management_api,
                    connection_id,
                    {
                        "type": message_type,
                        "message_id": message_id,
                        "session_id": session_id,
                        "message": {"model": selected_model_id},
                        "delta": {"text": content},
                        "message_counter": counter,
                        "backend_type": backend_type,
                    },
                )
                message_type = "content_block_delta"
                counter += 1
                result_text += content
            elif "flowCompletionEvent" in event:
                flow_completion_event = event["flowCompletionEvent"]
                if flow_completion_event["completionReason"] == "SUCCESS":
                    if counter > 0:
                        # Send the message_stop event to the WebSocket client
                        commons.send_websocket_message(
                            logger,
                            apigateway_management_api,
                            connection_id,
                            {
                                "type": "message_stop",
                                "message_id": message_id,
                                "session_id": session_id,
                                "new_conversation": new_conversation,
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "backend_type": backend_type,
                            },
                        )
                        message_stop_sent = True
                else:
                    # Send an error message to the WebSocket client
                    commons.send_websocket_message(
                        logger,
                        apigateway_management_api,
                        connection_id,
                        {
                            "type": "error",
                            "message_id": message_id,
                            "session_id": session_id,
                            "code": "9200",
                            "error": "Flow completion event with non-success reason",
                        },
                    )
                    contains_errors = True

        commons.send_websocket_message(
            logger,
            apigateway_management_api,
            connection_id,
            {
                "type": "message_title",
                "message_id": message_id,
                "session_id": session_id,
                "title": chat_title,
            },
        )
        if counter > 0 and not message_stop_sent:
            # Send the message_stop event to the WebSocket client
            commons.send_websocket_message(
                logger,
                apigateway_management_api,
                connection_id,
                {
                    "type": "message_stop",
                    "message_id": message_id,
                    "session_id": session_id,
                    "new_conversation": new_conversation,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "backend_type": backend_type,
                },
            )
        message_stop_sent = True

    except Exception as e:
        logger.exception(e)
        logger.error(f"Error processing Bedrock response: {str(e)}")
        # Send an error message to the WebSocket client
        commons.send_websocket_message(
            logger,
            apigateway_management_api,
            connection_id,
            {
                "type": "error",
                "message_id": message_id,
                "session_id": session_id,
                "code": "9200",
                "error": str(e),
            },
        )
        contains_errors = True
        if counter > 0:
            logger.error("Sending message stop now...(error)")
            commons.send_websocket_message(
                logger,
                apigateway_management_api,
                connection_id,
                {
                    "type": "message_stop",
                    "message_id": message_id,
                    "session_id": session_id,
                    "new_conversation": new_conversation,
                },
            )

    return result_text, contains_errors


def store_bedrock_knowledgebase_response(
    prompt,
    response_text,
    existing_history,
    message_id,
    session_id,
    kb_session_id,
    user_id,
    selected_knowledgebase_id,
    selected_model_id,
    selected_model_name,
    selected_model_category,
    chat_title,
    new_message_id,
):
    """Stores the KB response in DynamoDB"""
    conversation_history = existing_history + [
        {
            "role": "user",
            "content": [{"text": prompt}],
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "message_id": message_id,
        },
        {
            "role": "assistant",
            "content": [{"text": response_text}],
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "message_id": new_message_id,
        },
    ]
    conversation_json = json.dumps(conversation_history)
    current_timestamp = str(datetime.now(tz=timezone.utc).timestamp())
    dynamodb.put_item(
        TableName=conversations_table_name,
        Item={
            "session_id": {"S": session_id},
            "user_id": {"S": user_id},
            "title": {"S": chat_title},
            "last_modified_date": {"N": current_timestamp},
            "selected_knowledgebase_id": {"S": selected_knowledgebase_id},
            "selected_model_id": {"S": selected_model_id},
            "selected_model_name": {"S": selected_model_name},
            "kb_session_id": {"S": kb_session_id},
            "category": {"S": selected_model_category},
            "conversation_history": {"S": conversation_json},
            "conversation_history_in_s3": {"BOOL": False},
        },
    )


def store_bedrock_agents_response(
    prompt,
    response_text,
    existing_history,
    message_id,
    session_id,
    user_id,
    selected_agent_id,
    selected_agent_alias_id,
    flow_id,
    flow_alias_id,
    category,
    chat_title,
    new_message_id,
):
    """Stores the Agent response in DynamoDB"""
    conversation_history = existing_history + [
        {
            "role": "user",
            "content": [{"text": prompt}],
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "message_id": message_id,
        },
        {
            "role": "assistant",
            "content": [{"text": response_text}],
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "message_id": new_message_id,
        },
    ]
    conversation_json = json.dumps(conversation_history)
    current_timestamp = str(datetime.now(tz=timezone.utc).timestamp())
    item_value = {
        "session_id": {"S": session_id},
        "user_id": {"S": user_id},
        "title": {"S": chat_title},
        "last_modified_date": {"N": current_timestamp},
        "category": {"S": category},
        "conversation_history": {"S": conversation_json},
        "conversation_history_in_s3": {"BOOL": False},
    }
    if flow_id:
        item_value["flow_id"] = {"S": flow_id}
    if flow_alias_id:
        item_value["flow_alias_id"] = {"S": flow_alias_id}
    if selected_agent_id:
        item_value["selected_agent_id"] = {"S": selected_agent_id}
    if selected_agent_alias_id:
        item_value["selected_agent_alias_id"] = {"S": selected_agent_alias_id}
    dynamodb.put_item(TableName=conversations_table_name, Item=item_value)


def split_string_into_chunks(input_string, max_chars: int = 10000):
    if not input_string:
        return []
    if max_chars <= 0:
        raise ValueError("max_chars must be greater than 0")

    return [
        input_string[i : i + max_chars] for i in range(0, len(input_string), max_chars)
    ]
