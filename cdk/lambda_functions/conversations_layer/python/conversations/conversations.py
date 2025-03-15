from typing import List, Dict
import json
from datetime import datetime, timezone
from aws_lambda_powertools import Logger


def delete_conversation_history(dynamodb, conversations_table_name, logger, session_id):
    """Function to delete conversation history from DDB"""
    try:
        dynamodb.delete_item(
            TableName=conversations_table_name, Key={"session_id": {"S": session_id}}
        )
        logger.info(f"Conversation history deleted for session ID: {session_id}")
    except Exception as e:
        logger.exception(e)
        logger.error(f"Error deleting conversation history (9781): {str(e)}")


def load_and_send_conversation_history(
    session_id: str,
    connection_id: str,
    user_id: str,
    dynamodb,
    conversations_table_name,
    s3_client,
    conversation_history_bucket,
    logger,
    commons,
    apigateway_management_api,
    conversation_history_in_s3,
    return_conversation_without_sending,
):
    """Function to load and send conversation history"""
    try:
        projection_expression = "session_id,category,conversation_history,conversation_history_in_s3,last_message_id,last_modified_date,selected_model_id,title,user_id"
        if conversation_history_in_s3:
            projection_expression = "session_id,category,conversation_history_in_s3,last_message_id,last_modified_date,selected_model_id,title,user_id"

        response = dynamodb.get_item(
            TableName=conversations_table_name,
            Key={"session_id": {"S": session_id}},
            ProjectionExpression=projection_expression,
        )

        if "Item" in response:
            item = response["Item"]

            conversation_history_in_s3 = (
                item.get("conversation_history_in_s3", {}).get("BOOL", False)
                if isinstance(item.get("conversation_history_in_s3"), dict)
                else item.get("conversation_history_in_s3", False)
            )

            if conversation_history_in_s3:
                prefix = rf"{user_id}/{session_id}"
                # Load conversation history from S3
                response = s3_client.get_object(
                    Bucket=conversation_history_bucket,
                    Key=f"{prefix}/{session_id}.json",
                )
                conversation_history = json.loads(
                    response["Body"].read().decode("utf-8")
                )
            else:
                # Load conversation history from DynamoDB
                conversation_history_str = item["conversation_history"]["S"]
                conversation_history = json.loads(conversation_history_str)

            if return_conversation_without_sending:
                title_string = item["title"]["S"]
                needs_load_from_s3 = "s3source" in json.dumps(conversation_history)
                return (
                    needs_load_from_s3,
                    title_string,
                    conversation_history,
                )

            # Split the conversation history into chunks
            conversation_history_chunks = split_message(conversation_history, logger)
            # Send the conversation history chunks to the WebSocket client
            total_chunks = len(conversation_history_chunks)
            for index, chunk in enumerate(conversation_history_chunks, start=1):
                commons.send_websocket_message(
                    logger,
                    apigateway_management_api,
                    connection_id,
                    {
                        "type": "conversation_history",
                        "session_id": session_id,
                        "last_message": index == total_chunks,
                        "loaded_from_s3": conversation_history_in_s3,
                        "chunk": chunk.decode("utf-8"),
                        "current_chunk": index,
                        "total_chunks": total_chunks,
                    },
                )
        else:
            if return_conversation_without_sending:
                return (False, "", [])
            commons.send_websocket_message(
                logger,
                apigateway_management_api,
                connection_id,
                {"type": "no_conversation_to_load", "last_message": True,"session_id": session_id,},
            )
            return []

    except Exception as e:
        logger.error("Error loading conversation history")
        logger.exception(e)
        return []


def create_base_message(msg: Dict, is_partial: bool = False) -> Dict:
    """Creates a base message structure for chunking"""
    msg["msg_partial"] = is_partial
    msg["msg_partial_last_chunk"] = False
    return msg


def split_message(
    conversation_history: List[Dict], logger: Logger, max_chunk_size: int = 31744
) -> List[bytes]:
    """
    Split conversation messages into chunks within specified size limit, optimizing for minimum chunks.

    Args:
        conversation_history (List[Dict]): Array of conversation message objects
        logger (Logger): AWS Lambda Powertools Logger instance
        max_chunk_size (int): Maximum size in bytes per chunk. Defaults to 31744.

    Returns:
        List[bytes]: Array of UTF-8 encoded JSON strings
    """
    chunks = []
    SAFETY_BUFFER = 1000

    try:
        for msg_index, msg in enumerate(conversation_history, 1):
            base_msg = create_base_message(msg)
            msg_json = json.dumps(base_msg)
            msg_size = len(msg_json.encode("utf-8"))
            if msg_size <= max_chunk_size:
                chunks.append(msg_json.encode("utf-8"))
                continue

            base_template = create_base_message(msg, is_partial=True)
            content_limit = max_chunk_size - SAFETY_BUFFER
            content = str(msg["content"])
            chunk_count = 0

            while content:
                chunk_count += 1
                chunk = base_template.copy()
                current_slice = content[:content_limit]

                # If we can't slice anymore, use all remaining content as the final chunk
                if not current_slice:
                    chunk["content"] = content
                    chunk["msg_partial_last_chunk"] = True
                    chunk_json = json.dumps(chunk)
                    chunks.append(chunk_json.encode("utf-8"))
                    break

                chunk["content"] = current_slice
                content = content[content_limit:]

                if not content:
                    chunk["msg_partial_last_chunk"] = True

                chunk_json = json.dumps(chunk)
                chunks.append(chunk_json.encode("utf-8"))
        return chunks

    except Exception as e:
        logger.exception(f"Error processing messages: {str(e)}")
        raise


def save_token_usage(user_id, input_tokens, output_tokens, dynamodb, usage_table_name):
    """Function to save token usage in DDB"""
    current_date_ymd = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    current_date_ym = datetime.now(tz=timezone.utc).strftime("%Y-%m")

    dynamodb.update_item(
        TableName=usage_table_name,
        Key={"user_id": {"S": user_id}},
        UpdateExpression="ADD input_tokens :input_tokens, output_tokens :output_tokens, message_count :message_count",
        ExpressionAttributeValues={
            ":input_tokens": {"N": str(input_tokens)},
            ":output_tokens": {"N": str(output_tokens)},
            ":message_count": {"N": str(1)},
        },
    )
    dynamodb.update_item(
        TableName=usage_table_name,
        Key={"user_id": {"S": user_id + "-" + current_date_ym}},
        UpdateExpression="ADD input_tokens :input_tokens, output_tokens :output_tokens, message_count :message_count",
        ExpressionAttributeValues={
            ":input_tokens": {"N": str(input_tokens)},
            ":output_tokens": {"N": str(output_tokens)},
            ":message_count": {"N": str(1)},
        },
    )
    dynamodb.update_item(
        TableName=usage_table_name,
        Key={"user_id": {"S": user_id + "-" + current_date_ymd}},
        UpdateExpression="ADD input_tokens :input_tokens, output_tokens :output_tokens, message_count :message_count",
        ExpressionAttributeValues={
            ":input_tokens": {"N": str(input_tokens)},
            ":output_tokens": {"N": str(output_tokens)},
            ":message_count": {"N": str(1)},
        },
    )
