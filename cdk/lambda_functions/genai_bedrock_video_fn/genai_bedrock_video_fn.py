import json
import os
import base64
import random
import copy
from datetime import datetime, timezone
import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from botocore.config import Config
from chatbot_commons import commons
from conversations import conversations

logger = Logger(service="BedrockVideo")
metrics = Metrics()
tracer = Tracer()
MAX_IMAGES = 1
config = Config(retries={"total_max_attempts": 20, "mode": "standard"})
bedrock_runtime = boto3.client("bedrock-runtime", config=config)
WEBSOCKET_API_ENDPOINT = os.environ["WEBSOCKET_API_ENDPOINT"]
s3_client = boto3.client("s3")
dynamodb = boto3.client("dynamodb")
video_bucket = os.environ["S3_IMAGE_BUCKET_NAME"]
cloudfront_domain = os.environ["CLOUDFRONT_DOMAIN"]
conversations_table_name = os.environ["CONVERSATIONS_DYNAMODB_TABLE"]
conversations_table = boto3.resource("dynamodb").Table(conversations_table_name)
conversation_history_bucket = os.environ["CONVERSATION_HISTORY_BUCKET"]
attachment_bucket_name = os.environ["ATTACHMENT_BUCKET_NAME"]
aws_account_id = os.environ["AWS_ACCOUNT_ID"]

apigateway_management_api = boto3.client(
    "apigatewaymanagementapi",
    endpoint_url=f"{WEBSOCKET_API_ENDPOINT.replace('wss', 'https')}/ws",
)

SLEEP_TIME = 2


@tracer.capture_lambda_handler
def lambda_handler(event, context):
    """Lambda Handler Function"""
    try:
        access_token = event.get("access_token", {})
        session_id = event.get("session_id", "XYZ")
        connection_id = event.get("connection_id", "ZYX")
        user_id = access_token["payload"]["sub"]
        message_type = event.get("type", "")
        selected_mode = event.get("selected_mode", {})
        selected_model_category = selected_mode.get("category")
        prompt = event.get("prompt", "")
        attachments = event.get("attachments", [])
        model_id = selected_mode.get("modelId", "amazon.nova-reel-v1:0")
        image_model_id = selected_mode.get(
            "video_helper_image_model_id", "amazon.nova-canvas-v1:0"
        )
        # if prompt length is < 3 then prepend text 'image of '
        if len(prompt) < 3:
            prompt = "image of " + prompt
        chat_title = prompt[:16] if len(prompt) > 16 else prompt

        message_id = event.get("message_id", None)
        new_message_id = commons.generate_random_string()
        message_received_timestamp_utc = event.get(
            "timestamp", datetime.now(timezone.utc).isoformat()
        )

        if message_type == "clear_conversation":
            commons.delete_s3_attachments_for_session(
                session_id, video_bucket, user_id, "videos", s3_client, logger
            )
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
        # Resolution and aspect_ratio only used for Luma models
        resolution = "720p"
        aspect_ratio = "16:9"
        duration_seconds = 6
        if "luma" in model_id.lower():
            duration_seconds = 9
        seed = random.randint(0, 2147483648)
        image_count = sum(1 for a in attachments if a["type"].startswith("image/"))
        if image_count > MAX_IMAGES:
            commons.send_websocket_message(
                logger,
                apigateway_management_api,
                connection_id,
                {
                    "type": "error",
                    "session_id": session_id,
                    "error": f"Too many images. Maximum allowed is {MAX_IMAGES}.",
                },
            )
            return {"statusCode": 400}
        required_image_width = 1280
        required_image_height = 720
        processed_attachments, error_message = commons.process_attachments(
            attachments,
            user_id,
            session_id,
            attachment_bucket_name,
            logger,
            s3_client,
            [],
            required_image_width,
            required_image_height,
            bedrock_runtime,
            image_model_id,
        )
        if error_message and len(error_message) > 1:
            commons.send_websocket_message(
                logger,
                apigateway_management_api,
                connection_id,
                {"type": "error", "session_id": session_id, "error": error_message},
            )
            return {"statusCode": 400}
        images_array = convert_attachments(processed_attachments)
        video_url, success_status, error_message = commons.generate_video(
            prompt,
            model_id,
            user_id,
            session_id,
            bedrock_runtime,
            s3_client,
            video_bucket,
            SLEEP_TIME,
            logger,
            cloudfront_domain,
            duration_seconds,
            seed,
            False,
            images_array,
            resolution,
            aspect_ratio,
            aws_account_id,
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
        existing_history = copy.deepcopy(original_existing_history)
        new_conversation = bool(not existing_history or len(existing_history) == 0)
        persisted_chat_title = (
            chat_title_loaded
            if chat_title_loaded and chat_title_loaded.strip()
            else chat_title
        )

        if not success_status:
            commons.send_websocket_message(
                logger,
                apigateway_management_api,
                connection_id,
                {
                    "type": "message_start",
                    "message_id": new_message_id,
                    "message": {"model": model_id},
                    "session_id": session_id,
                    "delta": {"text": error_message},
                    "message_counter": 0,
                },
            )
            commons.send_websocket_message(
                logger,
                apigateway_management_api,
                connection_id,
                {
                    "type": "message_title",
                    "message_id": new_message_id,
                    "session_id": session_id,
                    "title": persisted_chat_title,
                },
            )
            message_end_timestamp_utc = datetime.now(timezone.utc).isoformat()
            commons.send_websocket_message(
                logger,
                apigateway_management_api,
                connection_id,
                {
                    "type": "message_stop",
                    "message_id": new_message_id,
                    "session_id": session_id,
                    "message_counter": 1,
                    "new_conversation": new_conversation,
                    "timestamp": message_end_timestamp_utc,
                    "amazon_bedrock_invocation_metrics": {
                        "inputTokenCount": 0,
                        "outputTokenCount": 0,
                    },
                },
            )
            return {
                "statusCode": 200,
                "body": json.dumps(f"Video Generation failed due to: {error_message}"),
            }

        commons.send_websocket_message(
            logger,
            apigateway_management_api,
            connection_id,
            {
                "type": "video_generated",
                "message_id": new_message_id,
                "session_id": session_id,
                "video_url": video_url,
                "prompt": prompt,
                "modelId": model_id,
                "timestamp": message_received_timestamp_utc,
            },
        )

        commons.send_websocket_message(
            logger,
            apigateway_management_api,
            connection_id,
            {
                "type": "message_title",
                "message_id": new_message_id,
                "session_id": session_id,
                "title": persisted_chat_title,
            },
        )

        commons.send_websocket_message(
            logger,
            apigateway_management_api,
            connection_id,
            {
                "type": "message_stop",
                "message_id": new_message_id,
                "session_id": session_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "modelId": model_id,
                "new_conversation": new_conversation,
                "backend_type": "video_generated",
            },
        )

        store_bedrock_videos_response(
            prompt,
            video_url,
            existing_history,
            message_id,
            session_id,
            user_id,
            model_id,
            selected_model_category,
            persisted_chat_title,
            new_message_id,
        )

        return {"statusCode": 200, "body": json.dumps("Video generated successfully")}

    except Exception as e:
        logger.exception(e)
        logger.error(f"Error generating video: {str(e)}", exc_info=True)
        commons.send_websocket_message(
            logger,
            apigateway_management_api,
            connection_id,
            {"type": "error", "session_id": session_id, "error": str(e)},
        )
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


def store_bedrock_videos_response(
    prompt,
    video_url,
    existing_history,
    message_id,
    session_id,
    user_id,
    model_id,
    selected_model_category,
    chat_title,
    new_message_id,
):
    """Stores the bedrock video conversation"""
    conversation_history = existing_history + [
        {
            "role": "user",
            "content": [{"text": prompt}],
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "message_id": message_id,
        },
        {
            "role": "assistant",
            "content": video_url,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "model": model_id,
            "isVideo": True,
            "videoAlt": prompt,
            "prompt": prompt,
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
        "selected_model_id": {"S": model_id},
        "category": {"S": selected_model_category},
        "conversation_history": {"S": conversation_json},
        "conversation_history_in_s3": {"BOOL": False},
    }
    dynamodb.put_item(TableName=conversations_table_name, Item=item_value)


def convert_attachments(attachments):
    """
    Convert a list of attachments from the input format to the desired output format.

    This function takes a list of attachment dictionaries and converts each one
    to a new format suitable for further processing or API calls.

    Args:
    attachments (list): A list of dictionaries, each representing an attachment.
        Each dictionary should have the following keys:
        - 'name': str, the filename of the attachment
        - 'content': bytes, the base64 encoded content of the attachment

    Returns:
    list: A list of dictionaries in the new format. Each dictionary contains:
        - 'format': str, the file extension of the attachment
        - 'source': dict, containing:
            - 'bytes': str, the base64 encoded content as a UTF-8 string

    Example:
    >>> input = [{'name': 'image.png', 'content': b'base64encodedcontent'}]
    >>> convert_attachments(input)
    [{'format': 'png', 'source': {'bytes': 'base64encodedcontent'}}]
    """
    converted_attachments = []

    for attachment in attachments:
        # Extract the file extension from the name
        file_extension = attachment["name"].split(".")[-1].lower()

        # Convert the binary content directly to a string
        base64_content = base64.b64encode(attachment["content"]).decode("utf-8")

        converted_attachment = {
            "format": file_extension,
            "source": {"bytes": base64_content},
        }

        converted_attachments.append(converted_attachment)

    return converted_attachments
