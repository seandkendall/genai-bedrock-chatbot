import json
import re
import os
import commons
from datetime import datetime, timezone
from aws_lambda_powertools import Logger

logger = Logger(service="BedrockAsyncLLMFunctions")
WEBSOCKET_API_ENDPOINT = os.environ["WEBSOCKET_API_ENDPOINT"]


def process_message_history_converse(existing_history):
    """Function to process message history for converse"""
    normalized_history = []
    for message in existing_history:
        role = message.get("role")
        content = [item for item in message.get("content") if "text" in item]
        if role in ["user", "assistant"]:
            normalized_message = {"role": role, "content": content}

            normalized_history.append(normalized_message)

    return normalized_history


def process_bedrock_converse_response(
    apigateway_management_api,
    response,
    selected_model_id,
    connection_id,
    converse_content_with_s3_pointers,
    new_conversation,
    session_id,
    message_id,
):
    """Function to process a bedrock response and send the messages back to the websocket for converse API"""
    result_text = ""
    reasoning_text = ""
    current_input_tokens = 0
    current_output_tokens = 0
    counter = 0
    message_end_timestamp_utc = ""
    message_stop_reason = ""
    stream = response.get("stream")

    if stream:
        buffer = []
        char_count = 0
        is_reasoning = False
        for event in stream:
            if "contentBlockDelta" in event:
                msg_text = ""
                if "reasoningContent" in event["contentBlockDelta"]["delta"]:
                    msg_text = event["contentBlockDelta"]["delta"]["reasoningContent"][
                        "text"
                    ]
                    is_reasoning = True
                else:
                    msg_text = event["contentBlockDelta"]["delta"]["text"]
                    is_reasoning = False

                if counter == 0:
                    # Always send the first message immediately
                    commons.send_websocket_message(
                        logger,
                        apigateway_management_api,
                        connection_id,
                        {
                            "type": "message_start",
                            "message": {"model": selected_model_id},
                            "message_id": message_id,
                            "session_id": session_id,
                            "is_reasoning": is_reasoning,
                            "delta": {"text": msg_text},
                            "message_counter": counter,
                        },
                    )
                elif len(result_text) < 1000:
                    commons.send_websocket_message(
                        logger,
                        apigateway_management_api,
                        connection_id,
                        {
                            "type": "content_block_delta",
                            "message_id": message_id,
                            "session_id": session_id,
                            "is_reasoning": is_reasoning,
                            "delta": {"text": msg_text},
                            "message_counter": counter,
                        },
                    )
                else:
                    # Add the new message text to the buffer
                    buffer.append(msg_text)
                    char_count += len(msg_text)

                    # Check if the accumulated buffer exceeds or equals 300 characters
                    if char_count >= 300:
                        combined_text = "".join(buffer)
                        commons.send_websocket_message(
                            logger,
                            apigateway_management_api,
                            connection_id,
                            {
                                "type": "content_block_delta",
                                "message_id": message_id,
                                "session_id": session_id,
                                "is_reasoning": is_reasoning,
                                "delta": {"text": combined_text},
                                "message_counter": counter,
                            },
                        )
                        # Clear the buffer and reset character count
                        buffer.clear()
                        char_count = 0
                if is_reasoning:
                    reasoning_text += msg_text
                else:
                    result_text += msg_text
                counter += 1

            if "messageStop" in event:
                message_stop = event["messageStop"]
                if "stopReason" in message_stop:
                    message_stop_reason = message_stop["stopReason"]

            if "metadata" in event:
                metadata = event["metadata"]
                if "usage" in metadata:
                    current_input_tokens = metadata["usage"]["inputTokens"]
                    current_output_tokens = metadata["usage"]["outputTokens"]

        # Send any remaining buffered messages
        if buffer:
            combined_text = "".join(buffer)
            commons.send_websocket_message(
                logger,
                apigateway_management_api,
                connection_id,
                {
                    "type": "content_block_delta",
                    "message_id": message_id,
                    "session_id": session_id,
                    "is_reasoning": is_reasoning,
                    "delta": {"text": combined_text},
                    "message_counter": counter,
                },
            )
            buffer.clear()

        logger.info(
            f"TokenCounts (Converse): {str(current_input_tokens)}/{str(current_output_tokens)}"
        )
        # Send the message_stop event to the WebSocket client
        message_end_timestamp_utc = datetime.now(timezone.utc).isoformat()
        needs_code_end = False

        if result_text.count("```") % 2 != 0:
            needs_code_end = True
        commons.send_websocket_message(
            logger,
            apigateway_management_api,
            connection_id,
            {
                "type": "message_stop",
                "message_id": message_id,
                "session_id": session_id,
                "message_counter": counter,
                "message_stop_reason": message_stop_reason,
                "needs_code_end": needs_code_end,
                "new_conversation": new_conversation,
                "timestamp": message_end_timestamp_utc,
                "amazon_bedrock_invocation_metrics": {
                    "inputTokenCount": current_input_tokens,
                    "outputTokenCount": current_output_tokens,
                },
            },
        )

        return (
            result_text,
            reasoning_text,
            current_input_tokens,
            current_output_tokens,
            message_end_timestamp_utc,
            message_stop_reason,
        )


def process_bedrock_converse_response_for_title(response):
    """Function to process a bedrock title response for converse API"""
    result_text = ""
    stream = response.get("stream")
    if stream:
        for event in stream:
            if "contentBlockDelta" in event:
                result_text += event["contentBlockDelta"]["delta"]["text"]

    try:
        # Parse the JSON string into a Python dictionary
        json_result = extract_and_parse_json(result_text)
        return json_result
    except json.JSONDecodeError as e:
        # Handle the case where the string is not valid JSON
        logger.warn(f"Error(0901) parsing JSON: {e}")
        logger.warn(f"Original result_text: {result_text}")
        return None


def extract_and_parse_json(text):
    # Regular expression to find JSON-like structures
    json_pattern = r"\{(?:[^{}]|(?R))*\}"

    try:
        # First, try to parse the entire text as JSON
        return json.loads(text)
    except json.JSONDecodeError:
        # If that fails, try to find JSON within the text
        match = re.search(json_pattern, text)
        if match:
            try:
                # Try to parse the extracted JSON
                return json.loads(match.group())
            except json.JSONDecodeError:
                # If parsing fails, return None or raise an exception
                return None
        else:
            # If no JSON-like structure is found, return None or raise an exception
            return None
