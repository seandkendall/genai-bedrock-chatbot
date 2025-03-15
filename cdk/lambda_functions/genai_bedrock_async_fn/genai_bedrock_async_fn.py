import json
import os
import copy
import re
import time
from datetime import datetime, timezone
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config
import commons
import conversations

# use AWS powertools for logging
from aws_lambda_powertools import Logger, Metrics, Tracer
from llm_conversion_functions import (
    process_message_history_converse,
    process_bedrock_converse_response,
    process_bedrock_converse_response_for_title,
)
from transformers import AutoTokenizer


logger = Logger(service="BedrockAsync")
metrics = Metrics()
tracer = Tracer()

# Initialize DynamoDB client
dynamodb = boto3.client("dynamodb")
config_table_name = os.environ.get("DYNAMODB_TABLE_CONFIG")
config_table = boto3.resource("dynamodb").Table(config_table_name)
s3_client = boto3.client("s3")
conversation_history_bucket = os.environ["CONVERSATION_HISTORY_BUCKET"]
attachment_bucket_name = os.environ["ATTACHMENT_BUCKET_NAME"]
image_bucket_name = os.environ["S3_IMAGE_BUCKET_NAME"]
WEBSOCKET_API_ENDPOINT = os.environ["WEBSOCKET_API_ENDPOINT"]
conversations_table_name = os.environ["CONVERSATIONS_DYNAMODB_TABLE"]
conversations_table = boto3.resource("dynamodb").Table(conversations_table_name)
s3_custom_model_import_bucket_name = os.environ["S3_CUSTOM_MODEL_IMPORT_BUCKET_NAME"]
usage_table_name = os.environ["DYNAMODB_TABLE_USAGE"]
region = os.environ["REGION"]
# models that do not support a system prompt (also includes all amazon models)
SYSTEM_PROMPT_EXCLUDED_MODELS = (
    "cohere.command-text-v14",
    "cohere.command-light-text-v14",
    "mistral.mistral-7b-instruct-v0:2",
    "mistral.mixtral-8x7b-instruct-v0:1",
)
tokenizer_cache = {}
# Constants
MAX_DDB_SIZE = 400 * 1024  # 400KB
DDB_SIZE_THRESHOLD = 0.8
S3_KEY_FORMAT = "{prefix}/{session_id}.json"

MAX_CONTENT_ITEMS = 20
MAX_IMAGES = 20
MAX_DOCUMENTS = 5
ALLOWED_DOCUMENT_TYPES = [
    "plain",
    "pdf",
    "csv",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "html",
    "txt",
    "md",
    "png",
    "jpeg",
    "gif",
    "webp",
]

# Initialize bedrock_runtime client
config = Config(retries={"total_max_attempts": 5, "mode": "standard"})
bedrock_runtime = boto3.client("bedrock-runtime", config=config)
bedrock_client = boto3.client("bedrock", config=config)


# AWS API Gateway Management API client
apigateway_management_api = boto3.client(
    "apigatewaymanagementapi",
    endpoint_url=f"{WEBSOCKET_API_ENDPOINT.replace('wss', 'https')}/ws",
)

system_prompt = ""


@tracer.capture_lambda_handler
def lambda_handler(event, context):
    """Lambda Hander Function"""
    try:
        process_websocket_message(event)
        return {"statusCode": 200}

    except Exception as e:
        logger.exception(e)
        logger.error("Error (766)")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


@tracer.capture_method
def process_websocket_message(request_body):
    """Function to process a websocket message"""
    # amazonq-ignore-next-line
    global system_prompt
    access_token = request_body.get("access_token", {})
    session_id = request_body.get("session_id", "XYZ")
    connection_id = request_body.get("connection_id", "ZYX")
    user_id = access_token["payload"]["sub"]
    message_type = request_body.get("type", "")
    if session_id:
        tracer.put_annotation(key="SessionID", value=session_id)
    if user_id:
        tracer.put_annotation(key="UserID", value=user_id)
    if message_type:
        tracer.put_annotation(key="MessageType", value=message_type)
    if connection_id:
        tracer.put_annotation(key="ConnectionID", value=connection_id)
    # Check if the WebSocket connection is open
    try:
        connection = apigateway_management_api.get_connection(
            ConnectionId=connection_id
        )
        connection_state = connection.get("ConnectionStatus", "OPEN")
        if connection_state != "OPEN":
            logger.info(f"WebSocket connection is not open (state: {connection_state})")
            return
    except apigateway_management_api.exceptions.GoneException:
        logger.warn(f"WebSocket connection is closed (connectionId: {connection_id})")
        return

    if message_type == "clear_conversation":
        # logger.info(f'Action: Clear Conversation {session_id}')
        # Delete the conversation history from DynamoDB
        commons.delete_s3_attachments_for_session(
            session_id, attachment_bucket_name, user_id, None, s3_client, logger
        )
        commons.delete_s3_attachments_for_session(
            session_id, image_bucket_name, user_id, None, s3_client, logger
        )
        commons.delete_s3_attachments_for_session(
            session_id, conversation_history_bucket, user_id, None, s3_client, logger
        )
        conversations.delete_conversation_history(
            dynamodb, conversations_table_name, logger, session_id
        )
        return
    elif message_type == "load":
        conversation_history_in_s3 = (
            request_body.get("conversation_history_in_s3", {}).get("BOOL", False)
            if isinstance(request_body.get("conversation_history_in_s3"), dict)
            else request_body.get("conversation_history_in_s3", False)
        )
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
            conversation_history_in_s3,
            False,
        )
        return
    else:
        # Handle other message types (e.g., prompt)
        prompt = request_body.get("prompt", "")
        conversation_history_in_s3 = (
            request_body.get("conversation_history_in_s3", {}).get("BOOL", False)
            if isinstance(request_body.get("conversation_history_in_s3"), dict)
            else request_body.get("conversation_history_in_s3", False)
        )
        attachments = request_body.get("attachments", [])
        selected_mode = request_body.get("selected_mode", {})
        selected_model_id = selected_mode.get("modelId", "")
        selected_model_name = selected_mode.get("modelName", "")
        selected_model_category = selected_mode.get("category", "")
        if "." in selected_model_id:
            model_provider = selected_model_id.split(".")[0]
        else:
            model_provider = selected_mode.get("providerName", "")
        # Validate attachments
        if len(attachments) > MAX_CONTENT_ITEMS:
            commons.send_websocket_message(
                logger,
                apigateway_management_api,
                connection_id,
                {
                    "type": "error",
                    "error": f"Too many attachments. Maximum allowed is {MAX_CONTENT_ITEMS}.",
                },
            )
            return {"statusCode": 400}

        image_count = sum(1 for a in attachments if a["type"].startswith("image/"))
        document_count = len(attachments) - image_count
        if image_count > MAX_IMAGES:
            commons.send_websocket_message(
                logger,
                apigateway_management_api,
                connection_id,
                {
                    "type": "error",
                    "error": f"Too many images. Maximum allowed is {MAX_IMAGES}.",
                },
            )
            return {"statusCode": 400}

        if document_count > MAX_DOCUMENTS:
            commons.send_websocket_message(
                logger,
                apigateway_management_api,
                connection_id,
                {
                    "type": "error",
                    "error": f"Too many documents. Maximum allowed is {MAX_DOCUMENTS}.",
                },
            )
            return {"statusCode": 400}
        processed_attachments, error_message = commons.process_attachments(
            attachments,
            user_id,
            session_id,
            attachment_bucket_name,
            logger,
            s3_client,
            ALLOWED_DOCUMENT_TYPES,
            0,
            0,
            bedrock_runtime,
            selected_model_id,
        )
        if error_message and len(error_message) > 1:
            commons.send_websocket_message(
                logger,
                apigateway_management_api,
                connection_id,
                {"type": "error", "error": error_message},
            )
            return {"statusCode": 400}

        # Query existing history for the session from DynamoDB
        needs_load_from_s3, chat_title, original_existing_history = (
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
                conversation_history_in_s3,
                True,
            )
        )
        if needs_load_from_s3:
            existing_history = load_documents_from_existing_history(
                original_existing_history
            )
        else:
            existing_history = copy.deepcopy(original_existing_history)
        reload_prompt_config = bool(request_body.get("reloadPromptConfig", "False"))
        system_prompt_user_or_system = request_body.get(
            "systemPromptUserOrSystem", "system"
        )
        if system_prompt_user_or_system:
            tracer.put_annotation(
                key="PromptUserOrSystem", value=system_prompt_user_or_system
            )
        if not system_prompt or reload_prompt_config:
            system_prompt = load_system_prompt_config(
                system_prompt_user_or_system, user_id
            )

        title_theme = request_body.get("titleGenTheme", "")
        title_gen_model = request_body.get("titleGenModel", "")
        if title_gen_model == "DEFAULT" or not title_gen_model:
            title_gen_model = ""
        if "/" in title_gen_model:
            title_gen_model = title_gen_model.split("/")[1]

        message_id = request_body.get("message_id", None)
        new_message_id = commons.generate_random_string()
        message_received_timestamp_utc = request_body.get(
            "timestamp", datetime.now(tz=timezone.utc).isoformat()
        )
        timestamp_local_timezone = request_body.get("timestamp_local_timezone")
        bedrock_request = None
        converse_content_array = []
        converse_content_with_s3_pointers = []
        if prompt:
            converse_content_array.append({"text": prompt})
            converse_content_with_s3_pointers.append({"text": prompt})
        for attachment in processed_attachments:
            if attachment["type"].startswith("image/"):
                converse_content_array.append(
                    {
                        "image": {
                            "format": attachment["type"].split("/")[1],
                            "source": {"bytes": attachment["content"]},
                        }
                    }
                )
                converse_content_with_s3_pointers.append(
                    {
                        "image": {
                            "format": attachment["type"].split("/")[1],
                            "s3source": {
                                "s3bucket": attachment["s3bucket"],
                                "s3key": attachment["s3key"],
                            },
                        }
                    }
                )
            elif attachment["type"].startswith("video/"):
                video_format = attachment["type"].split("/")[1]
                if video_format == "3pg":
                    video_format = "three_gp"

                converse_content_array.append(
                    {
                        "video": {
                            "format": video_format,
                            "source": {
                                "s3Location": {
                                    "uri": f"s3://{attachment['s3bucket']}/{attachment['s3key']}"
                                }
                            },
                        }
                    }
                )
                converse_content_with_s3_pointers.append(
                    {
                        "video": {
                            "format": video_format,
                            "s3source": {
                                "s3bucket": attachment["s3bucket"],
                                "s3key": attachment["s3key"],
                            },
                        }
                    }
                )
            else:
                file_type = attachment["type"].split("/")[-1]
                if file_type == "plain":
                    file_type = "txt"
                converse_content_array.append(
                    {
                        "document": {
                            "format": file_type,
                            "name": sanitize_filename(attachment["name"]),
                            "source": {"bytes": attachment["content"]},
                        }
                    }
                )
                converse_content_with_s3_pointers.append(
                    {
                        "document": {
                            "format": file_type,
                            "name": sanitize_filename(attachment["name"]),
                            "s3source": {
                                "s3bucket": attachment["s3bucket"],
                                "s3key": attachment["s3key"],
                            },
                        }
                    }
                )
        message_content = process_message_history_converse(existing_history) + [
            {
                "role": "user",
                "content": converse_content_array,
            }
        ]
        bedrock_request = {"messages": message_content}
        if model_provider == "meta":
            bedrock_request["additionalModelRequestFields"] = {"max_gen_len": 2048}
        try:
            if selected_model_id:
                tracer.put_annotation(key="Model", value=selected_model_id)
            system_prompt_array = []
            if (not chat_title and len(bedrock_request.get("messages")) == 1) or (
                chat_title.startswith("New Conversation:")
            ):
                title_prompt_string = (
                    f"Generate a Title in under 16 characters, "
                    f'for a Chatbot conversation Header where the initial user prompt is: "{prompt}". '
                )
                if len(title_theme) > 0:
                    title_prompt_string = (
                        title_prompt_string
                        + f' Be creative using the following theme: "{title_theme}" '
                    )
                title_prompt_string = (
                    title_prompt_string
                    + 'You MUST answer in RAW JSON format only matching this well defined json format: {"title":"title_value"}'
                )

                title_prompt_request = [
                    {"role": "user", "content": [{"text": title_prompt_string}]}
                ]
                try:
                    chat_title = get_title_from_message(
                        title_prompt_request,
                        title_gen_model if title_gen_model else selected_model_id,
                        connection_id,
                        new_message_id,
                        session_id,
                    )
                except Exception:
                    chat_title = f"New Conversation: {hash(prompt) % 1000000:06x}"
            new_conversation = bool(
                not original_existing_history or len(original_existing_history) == 0
            )
            timezone_prompt = (
                f"The Current Time in UTC is: {message_received_timestamp_utc}. "
                f"Use the timezone of {timestamp_local_timezone} when making a reference to time. "
                "ALWAYS use the date format of: Month DD, YYYY HH24:mm:ss. "
                "ONLY include the time if needed. "
                "NEVER reference this date randomly. "
                "Use it to support high quality answers when the current date is NEEDED."
            )

            if system_prompt:
                system_prompt = system_prompt + " " + timezone_prompt
            else:
                system_prompt = timezone_prompt
            response = None
            if (
                system_prompt
                and selected_model_id not in SYSTEM_PROMPT_EXCLUDED_MODELS
                and model_provider != "amazon"
                and "imported-model" not in selected_model_id
            ):
                system_prompt_array.append({"text": system_prompt})
                response = bedrock_runtime.converse_stream(
                    messages=bedrock_request.get("messages"),
                    modelId=selected_model_id,
                    system=system_prompt_array,
                    additionalModelRequestFields=bedrock_request.get(
                        "additionalModelRequestFields", {}
                    ),
                )
                # uncomment for prompt debugging
                # commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                #     'type': 'system_prompt_used',
                #     'system_prompt': system_prompt,
                #     'session_id':session_id,
                # });
            elif "imported-model" in selected_model_id:
                if not os.path.exists(f"/tmp/{selected_model_name.replace('/', '-')}"):
                    os.makedirs(f"/tmp/{selected_model_name.replace('/', '-')}")
                tags_response = bedrock_client.list_tags_for_resource(
                    resourceARN=selected_model_id
                )
                model_identifier = [
                    tag["value"]
                    for tag in tags_response["tags"]
                    if tag["key"] == "modelIdentifier"
                ][0]
                tokenizer = get_tokenizer(model_identifier)
                messages = convert_message_format(message_content)
                (
                    assistant_response,
                    input_tokens,
                    output_tokens,
                    message_end_timestamp_utc,
                    message_stop_reason,
                ) = auto_generate(
                    connection_id,
                    session_id,
                    new_message_id,
                    tokenizer,
                    selected_model_id,
                    selected_model_name,
                    messages,
                    temperature=0.7,
                    max_tokens=4096,
                    top_p=0.9,
                )
                store_conversation_history_converse(
                    session_id,
                    selected_model_id,
                    original_existing_history,
                    converse_content_with_s3_pointers,
                    prompt,
                    assistant_response,
                    None,  # reasoning_text if exists
                    user_id,
                    input_tokens,
                    output_tokens,
                    message_end_timestamp_utc,
                    message_received_timestamp_utc,
                    message_id,
                    chat_title,
                    new_conversation,
                    selected_model_category,
                    message_stop_reason,
                    new_message_id,
                )
            else:
                response = bedrock_runtime.converse_stream(
                    messages=bedrock_request.get("messages"),
                    modelId=selected_model_id,
                    additionalModelRequestFields=bedrock_request.get(
                        "additionalModelRequestFields", {}
                    ),
                )
            if "imported-model" not in selected_model_id:
                (
                    assistant_response,
                    reasoning_text,
                    input_tokens,
                    output_tokens,
                    message_end_timestamp_utc,
                    message_stop_reason,
                ) = process_bedrock_converse_response(
                    apigateway_management_api,
                    response,
                    selected_model_id,
                    connection_id,
                    converse_content_with_s3_pointers,
                    new_conversation,
                    session_id,
                    new_message_id,
                )
                store_conversation_history_converse(
                    session_id,
                    selected_model_id,
                    original_existing_history,
                    converse_content_with_s3_pointers,
                    prompt,
                    assistant_response,
                    reasoning_text,
                    user_id,
                    input_tokens,
                    output_tokens,
                    message_end_timestamp_utc,
                    message_received_timestamp_utc,
                    message_id,
                    chat_title,
                    new_conversation,
                    selected_model_category,
                    message_stop_reason,
                    new_message_id,
                )
        except Exception as e:
            if "ResourceNotFoundException" in str(e):
                logger.error(
                    f"Imported Model not found: {selected_model_name} - {selected_model_id}"
                )
                commons.send_websocket_message(
                    logger,
                    apigateway_management_api,
                    connection_id,
                    {
                        "type": "error",
                        "error": f"Imported Model: {selected_model_name} Not Found. Please re-scan models.",
                    },
                )
                return {"statusCode": 400}
            if "ThrottlingException" not in str(e):
                logger.exception(e)
            logger.warn(f"Error calling bedrock model (912): {str(e)}")
            if "have access to the model with the specified model ID." in str(e):
                model_access_url = f"https://{region}.console.aws.amazon.com/bedrock/home?region={region}#/modelaccess"
                commons.send_websocket_message(
                    logger,
                    apigateway_management_api,
                    connection_id,
                    {
                        "type": "error",
                        "error": f"You have not enabled the selected model. Please visit the following link to request model access: [{model_access_url}]({model_access_url})",
                    },
                )
            else:
                commons.send_websocket_message(
                    logger,
                    apigateway_management_api,
                    connection_id,
                    {
                        "type": "error",
                        "error": f"An Error has occurred, please try again: {str(e)}",
                    },
                )


@tracer.capture_method
def get_title_from_message(
    messages: list,
    selected_model_id: str,
    connection_id: str,
    message_id: str,
    session_id: str,
) -> str:
    response = bedrock_runtime.converse_stream(
        messages=messages, modelId=selected_model_id, additionalModelRequestFields={}
    )
    # chat_title is a json object
    chat_title = process_bedrock_converse_response_for_title(response)
    commons.send_websocket_message(
        logger,
        apigateway_management_api,
        connection_id,
        {
            "type": "message_title",
            "message_id": message_id,
            "session_id": session_id,
            "title": chat_title["title"],
        },
    )
    return chat_title["title"]


@tracer.capture_method
def download_s3_content(item, content_type):
    """
    Download content from S3 and update the item with the downloaded content.

    Args:
        item (dict): The item containing the content to be downloaded.
        content_type (str): The type of content, either 'document' or 'image'.

    Returns:
        None
    """
    content = item[content_type]
    status = False
    if "s3source" in content:
        s3_bucket = content["s3source"]["s3bucket"]
        s3_key = content["s3source"]["s3key"]
        try:
            response = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
            if response is not None and response["Body"] is not None:
                file_content = response["Body"].read()
                content["source"] = {"bytes": file_content}
                status = True
        except ClientError as e:
            logger.error(f"Error downloading content from S3: {e}")
            if e.response["Error"]["Code"] == "NoSuchKey":
                logger.error(f"Key {s3_key} not found in bucket {s3_bucket}")
            logger.exception(e)
        del content["s3source"]
        return status


@tracer.capture_method
def load_documents_from_existing_history(existing_history):
    """
    Load documents and images from the existing history, where the content is stored in S3.

    Args:
        existing_history (list): A list of dictionaries representing the existing history.

    Returns:
        list: The modified history with the downloaded content.
    """
    modified_history = []
    existing_history = copy.deepcopy(existing_history)
    for item in existing_history:
        modified_item = {}
        modified_item["role"] = item["role"]
        modified_item["timestamp"] = item["timestamp"]
        modified_item["message_id"] = item["message_id"]
        modified_item["content"] = []
        for content_item in item["content"]:
            modified_content_item = {}
            add_item = True
            for key, value in content_item.items():
                if key in ["video"]:
                    modified_content_item[key] = (
                        convert_video_s3_source_to_bedrock_format(value)
                    )
                elif key in ["text"]:
                    modified_content_item[key] = value
                elif key in ["document", "image"]:
                    modified_content_item[key] = value
                    download_s3_content_worked = download_s3_content(
                        modified_content_item, key
                    )
                    if not download_s3_content_worked:
                        add_item = False
            if add_item:
                modified_item["content"].append(modified_content_item)
        modified_history.append(modified_item)
    return modified_history


@tracer.capture_method
def store_conversation_history_converse(
    session_id,
    selected_model_id,
    existing_history,
    converse_content_array,
    user_message,
    assistant_message,
    reasoning_text,
    user_id,
    input_tokens,
    output_tokens,
    message_end_timestamp_utc,
    message_received_timestamp_utc,
    message_id,
    title,
    new_conversation,
    selected_model_category,
    message_stop_reason,
    new_message_id,
):
    """Function to store conversation history in DDB or S3 in the converse format"""
    # logger.info(f"Storing conversation for session ID: {session_id}")

    if not (user_message.strip() and assistant_message.strip()):
        if not user_message.strip():
            logger.info(
                f"User message is empty, skipping storage for session ID: {session_id}"
            )
        if not assistant_message.strip():
            logger.info(
                f"Assistant response is empty, skipping storage for session ID: {session_id}"
            )
        return

    prefix = rf"{user_id}/{session_id}"
    # Prepare the updated conversation history once
    assistant_content_array = [{"text": assistant_message}]
    if reasoning_text and len(reasoning_text) > 1:
        assistant_content_array.append({"reasoning": reasoning_text})
    conversation_history = existing_history + [
        {
            "role": "user",
            "content": converse_content_array,
            "timestamp": message_received_timestamp_utc,
            "message_id": message_id,
        },
        {
            "role": "assistant",
            "content": assistant_content_array,
            "message_stop_reason": message_stop_reason,
            "timestamp": message_end_timestamp_utc,
            "message_id": new_message_id,
        },
    ]

    # Convert to JSON string once
    conversation_json = json.dumps(conversation_history)
    conversation_history_size = len(conversation_json.encode("utf-8"))
    current_timestamp = str(datetime.now(tz=timezone.utc).timestamp())

    try:
        if conversation_history_size > (MAX_DDB_SIZE * DDB_SIZE_THRESHOLD):
            logger.warn(
                f"Warning: Session ID {session_id} has reached 80% of the DynamoDB limit. Storing conversation history in S3."
            )

            # Store in S3
            s3_client.put_object(
                Bucket=conversation_history_bucket,
                Key=S3_KEY_FORMAT.format(prefix=prefix, session_id=session_id),
                Body=conversation_json.encode("utf-8"),
            )

            # Update DynamoDB to indicate S3 storage
            dynamodb.update_item(
                TableName=conversations_table_name,
                Key={"session_id": {"S": session_id}},
                UpdateExpression="SET conversation_history_in_s3=:true, last_modified_date = :current_time, last_message_id=:last_message_id",
                ExpressionAttributeValues={
                    ":true": {"BOOL": True},
                    ":current_time": {"N": current_timestamp},
                    ":last_message_id": {"S": new_message_id},
                },
            )

        else:
            # Store in DynamoDB
            logger.info(f"Storing TITLE for conversation history in DynamoDB: {title}")
            if new_conversation:
                dynamodb.put_item(
                    TableName=conversations_table_name,
                    Item={
                        "session_id": {"S": session_id},
                        "user_id": {"S": user_id},
                        "title": {"S": title},
                        "last_modified_date": {"N": current_timestamp},
                        "selected_model_id": {"S": selected_model_id},
                        "category": {"S": selected_model_category},
                        "last_message_id": {"S": new_message_id},
                        "conversation_history": {"S": conversation_json},
                        "conversation_history_in_s3": {"BOOL": False},
                    },
                )
            else:
                dynamodb.update_item(
                    TableName=conversations_table_name,
                    Key={"session_id": {"S": session_id}},
                    UpdateExpression="SET last_modified_date = :current_time, title = :title, selected_model_id = :selected_model_id, conversation_history = :conversation_history, category = :category, last_message_id=:last_message_id",
                    ExpressionAttributeValues={
                        ":current_time": {"N": current_timestamp},
                        ":title": {"S": title},
                        ":selected_model_id": {"S": selected_model_id},
                        ":conversation_history": {"S": conversation_json},
                        ":category": {"S": selected_model_category},
                        ":last_message_id": {"S": new_message_id},
                    },
                )

        # Batch token usage update
        conversations.save_token_usage(
            user_id, input_tokens, output_tokens, dynamodb, usage_table_name
        )

    except (ClientError, Exception) as e:
        logger.error(f"Error storing conversation history: {e}")
        raise


@tracer.capture_method
def load_system_prompt_config(system_prompt_user_or_system, user_id):
    """Function to load system prompt from DDB config"""
    user_key = "system"
    if system_prompt_user_or_system == "user":
        user_key = user_id if user_id else "system"
    if system_prompt_user_or_system == "global":
        system_prompt_user_or_system = "system"
    # Get the configuration from DynamoDB
    response = config_table.get_item(
        Key={"user": user_key, "config_type": system_prompt_user_or_system}
    )
    config = response.get("Item", {})
    config_item = config.get("config", {})
    return config_item.get("systemPrompt", "")


def sanitize_filename(filename: str) -> str:
    """
    Sanitizes a filename to only contain alphanumeric characters, whitespace characters, hyphens, parentheses, and square brackets.
    Removes consecutive whitespace characters.
    """
    # Replace non-alphanumeric characters, non-whitespace, non-hyphens, non-parentheses, and non-square brackets with an underscore
    sanitized_filename = re.sub(r"[^a-zA-Z0-9\s\-()\[\]]", "_", filename)

    # Replace consecutive whitespace characters with a single space
    sanitized_filename = re.sub(r"\s+", " ", sanitized_filename)

    # Remove leading and trailing whitespace characters
    sanitized_filename = sanitized_filename.strip()

    return sanitized_filename


@tracer.capture_method(capture_response=False)
def convert_video_s3_source_to_bedrock_format(input_json):
    # Extract the necessary information from the input dictionary
    videoformat = input_json["format"]
    s3bucket = input_json["s3source"]["s3bucket"]
    s3key = input_json["s3source"]["s3key"]

    # Construct the S3 URI
    s3_uri = f"s3://{s3bucket}/{s3key}"

    # Create the new dictionary structure
    output_dict = {"format": videoformat, "source": {"s3Location": {"uri": s3_uri}}}

    return output_dict


def generate(
    connection_id,
    result_length,
    buffer,
    char_count,
    session_id,
    message_id,
    tokenizer,
    selected_model_id,
    selected_model_name,
    messages,
    temperature=0.3,
    max_tokens=4096,
    top_p=0.9,
    continuation=False,
    max_retries=10,
):
    """
    Generate response using the model with proper tokenization and retry mechanism
    """
    prompt = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=not continuation
    )
    result = ""
    message_stop_reason = ""
    current_input_tokens = 0
    current_output_tokens = 0
    message_end_timestamp_utc = None

    attempt = 0
    while attempt < max_retries:
        try:
            response = bedrock_runtime.invoke_model_with_response_stream(
                modelId=selected_model_id,
                body=json.dumps(
                    {
                        "prompt": prompt,
                        "temperature": temperature,
                        "max_gen_len": max_tokens,
                        "top_p": top_p,
                    }
                ),
                accept="application/json",
                contentType="application/json",
            )
            event_stream = response["body"]
            counter = 0
            for event in event_stream:
                if "chunk" in event:
                    data = event["chunk"]["bytes"]
                    event_json = json.loads(data.decode("utf8"))
                    message_stop_reason = event_json["stop_reason"]
                    if event_json["prompt_token_count"] is not None:
                        current_input_tokens += event_json["prompt_token_count"]
                    if event_json["generation_token_count"] is not None:
                        current_output_tokens += event_json["generation_token_count"]
                    if message_stop_reason is not None and len(message_stop_reason) > 2:
                        result += event_json["generation"]
                        message_end_timestamp_utc = datetime.now(
                            timezone.utc
                        ).isoformat()
                        needs_code_end = False
                        if result.count("```") % 2 != 0:
                            needs_code_end = True
                        # Send any remaining buffered messages
                        if buffer:
                            combined_text = "".join(buffer)
                            commons.send_websocket_message(
                                logger,
                                apigateway_management_api,
                                connection_id,
                                {
                                    "type": "content_block_delta",
                                    "message": {"model": selected_model_name},
                                    "delta": {"text": combined_text},
                                    "message_id": message_id,
                                    "session_id": session_id,
                                },
                            )
                            buffer.clear()
                            char_count = 0
                        commons.send_websocket_message(
                            logger,
                            apigateway_management_api,
                            connection_id,
                            {
                                "type": "message_stop",
                                "session_id": session_id,
                                "message_id": message_id,
                                "message_counter": counter,
                                "message_stop_reason": message_stop_reason,
                                "needs_code_end": needs_code_end,
                                "new_conversation": True,
                                "timestamp": message_end_timestamp_utc,
                                "amazon_bedrock_invocation_metrics": {
                                    "inputTokenCount": current_input_tokens,
                                    "outputTokenCount": current_output_tokens,
                                },
                            },
                        )
                    else:
                        if result_length + len(result) <= 1000:
                            commons.send_websocket_message(
                                logger,
                                apigateway_management_api,
                                connection_id,
                                {
                                    "type": "message_start"
                                    if (result_length + len(result) == 0)
                                    else "content_block_delta",
                                    "message": {"model": selected_model_name},
                                    "delta": {"text": event_json["generation"]},
                                    "message_id": message_id,
                                    "session_id": session_id,
                                },
                            )
                        else:
                            buffer.append(event_json["generation"])
                            char_count += len(event_json["generation"])
                            # Check if the accumulated buffer exceeds or equals 300 characters
                            if char_count >= 300:
                                combined_text = "".join(buffer)
                                commons.send_websocket_message(
                                    logger,
                                    apigateway_management_api,
                                    connection_id,
                                    {
                                        "type": "content_block_delta",
                                        "message": {"model": selected_model_name},
                                        "delta": {"text": combined_text},
                                        "message_id": message_id,
                                        "session_id": session_id,
                                    },
                                )
                                # Clear the buffer and reset character count
                                buffer.clear()
                                char_count = 0

                    counter += 1
                    result += event_json["generation"]
            json_result = {"generation": result, "stop_reason": message_stop_reason}
            return (
                json_result,
                current_input_tokens,
                current_output_tokens,
                message_end_timestamp_utc,
                message_stop_reason,
                len(result),
            )

        except bedrock_runtime.exceptions.ModelNotReadyException as e:
            logger.warning(f'Model "{selected_model_id}" not ready, retrying: {e}')
            commons.send_websocket_message(
                logger,
                apigateway_management_api,
                connection_id,
                {
                    "type": "model_not_ready",
                    "session_id": session_id,
                    "message": f'Custom Model "{selected_model_name}" is starting. Attempt {attempt + 1}...',
                },
            )
            attempt += 1
            if attempt < max_retries:
                time.sleep(30)
        except Exception as e:
            logger.exception(e)
            logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
            attempt += 1
            if attempt < max_retries:
                time.sleep(30)
    commons.send_websocket_message(
        logger,
        apigateway_management_api,
        connection_id,
        {
            "type": "error",
            "error": f'Failed to get response after maximum retries. \n\nCustom Model "{selected_model_name}"',
        },
    )
    # amazonq-ignore-next-line
    raise Exception("Failed to get response after maximum retries")


def auto_generate(
    connection_id,
    session_id,
    message_id,
    tokenizer,
    selected_model_id,
    selected_model_name,
    messages,
    **kwargs,
):
    """
    Handle longer responses that exceed token limit
    """
    assistant_response = ""
    buffer = []
    char_count = 0
    result_length = 0
    iterations = 0
    (
        json_result,
        input_tokens,
        output_tokens,
        message_end_timestamp_utc,
        message_stop_reason,
        result_length,
    ) = generate(
        connection_id,
        result_length,
        buffer,
        char_count,
        session_id,
        message_id,
        tokenizer,
        selected_model_id,
        selected_model_name,
        messages,
        **kwargs,
    )
    while json_result["stop_reason"] == "length":
        iterations += 1
        logger.info(f"Response was truncated. Iteration: {iterations}...")
        assistant_response += json_result["generation"]
        updated_messages_array = messages + [
            {"role": "assistant", "content": assistant_response},
            {
                "role": "user",
                "content": "Previous response was truncated. Continue from where you left off.",
            },
        ]
        (
            json_result,
            temp_input_tokens,
            temp_output_tokens,
            message_end_timestamp_utc,
            message_stop_reason,
            temp_result_length,
        ) = generate(
            connection_id,
            result_length,
            buffer,
            char_count,
            session_id,
            message_id,
            tokenizer,
            selected_model_id,
            selected_model_name,
            updated_messages_array,
            **kwargs,
            continuation=False,
        )
        result_length += temp_result_length
        input_tokens += temp_input_tokens
        output_tokens += temp_output_tokens

    assistant_response += json_result["generation"]
    answer = assistant_response.split("</think>")[-1]
    think = assistant_response.split("</think>")[0].split("<think>")[-1]
    json_result = {
        **json_result,
        "generation": assistant_response,
        "answer": answer,
        "think": think,
    }
    return (
        assistant_response,
        input_tokens,
        output_tokens,
        message_end_timestamp_utc,
        message_stop_reason,
    )


def convert_message_format(message_input):
    # Initialize an empty list to store the converted messages
    converted_messages = []

    # Iterate through each item in the input list
    for item in message_input:
        # Check if 'content' key exists and is a list
        if "content" in item and isinstance(item["content"], list):
            # Iterate through each content item
            for content_item in item["content"]:
                # Check if 'text' key exists
                if "text" in content_item:
                    # Append the text content to the converted messages
                    converted_messages.append(
                        {"role": item["role"], "content": content_item["text"]}
                    )

    return converted_messages


def get_tokenizer(selected_model_name):
    if selected_model_name in tokenizer_cache:
        return tokenizer_cache[selected_model_name]
    else:
        new_tokenizer = AutoTokenizer.from_pretrained(
            selected_model_name,
            cache_dir=f"/tmp/{selected_model_name.replace('/', '-')}",
        )
        tokenizer_cache[selected_model_name] = new_tokenizer
        return new_tokenizer
