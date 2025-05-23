import json
from datetime import datetime
from aws_lambda_powertools import Logger
from chatbot_commons import commons

logger = Logger(service="BedrockConfigLoadUtilities")

# Cache the DynamoDB results for 5 minutes
CACHE_DURATION = 60 * 5  # 5 minutes
ddb_cache = {}
ddb_cache_timestamp = None


def datetime_to_iso(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError("Type not serializable")


def load_knowledge_bases(bedrock_agent_client, table):
    try:
        response = bedrock_agent_client.list_knowledge_bases(maxResults=100)
        kb_summaries = response.get("knowledgeBaseSummaries", [])
        ret = []

        # Convert datetime objects to ISO format strings
        for kb in kb_summaries:
            kb_id = kb["knowledgeBaseId"]
            kb["mode_selector"] = kb_id
            kb["mode_selector_name"] = kb_id
            if kb["status"] == "ACTIVE":
                ddb_config = commons.get_ddb_config(
                    table, ddb_cache, ddb_cache_timestamp, CACHE_DURATION, logger
                )
                kb["is_active"] = ddb_config.get(kb_id, {}).get("access_granted", True)
                kb["allow_input_image"] = ddb_config.get(kb_id, {}).get("IMAGE", False)
                kb["allow_input_video"] = ddb_config.get(kb_id, {}).get("VIDEO", False)
                kb["allow_input_document"] = ddb_config.get(kb_id, {}).get(
                    "DOCUMENT", False
                )
                kb["allow_input_speech"] = ddb_config.get(kb_id, {}).get(
                    "SPEECH", False
                )
                kb["output_type"] = "TEXT"
                kb["category"] = "Bedrock KnowledgeBases"
                ret.append(kb)
        return {"type": "load_knowledge_bases", "knowledge_bases": ret}
    except Exception as e:
        logger.exception(e)
        logger.error(f"Error loading agents: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"type": "error", "message": str(e)}),
        }


def load_agents(bedrock_agent_client, table):
    try:
        response = bedrock_agent_client.list_agents(maxResults=100)
        agent_summaries = response.get("agentSummaries", [])
        ret = []

        # Convert datetime objects to ISO format strings
        for agent in agent_summaries:
            agent_id = agent["agentId"]
            agent_name = agent["agentName"]
            agent_alias_response = bedrock_agent_client.list_agent_aliases(
                maxResults=100,
                agentId=agent_id,
            )
            agent_aliases = agent_alias_response["agentAliasSummaries"]
            # add agent_id to each item in agent_aliases
            for alias in agent_aliases:
                alias["agentId"] = agent_id
                alias["mode_selector"] = alias["agentAliasId"]
                alias["mode_selector_name"] = alias["agentAliasName"]
                alias["agent_name"] = agent_name
                ddb_config = commons.get_ddb_config(
                    table, ddb_cache, ddb_cache_timestamp, CACHE_DURATION, logger
                )
                alias["is_active"] = ddb_config.get(alias["agentAliasId"], {}).get(
                    "access_granted", True
                )
                alias["allow_input_image"] = ddb_config.get(
                    alias["agentAliasId"], {}
                ).get("IMAGE", False)
                alias["allow_input_video"] = ddb_config.get(
                    alias["agentAliasId"], {}
                ).get("VIDEO", False)
                alias["allow_input_document"] = ddb_config.get(
                    alias["agentAliasId"], {}
                ).get("DOCUMENT", False)
                alias["allow_input_speech"] = ddb_config.get(
                    alias["agentAliasId"], {}
                ).get("SPEECH", False)
                alias["output_type"] = "TEXT"
                alias["category"] = "Bedrock Agents"
                if alias["agentAliasName"] != "AgentTestAlias":
                    ret.append(alias)

        return {"type": "load_agents", "agents": ret}
    except Exception as e:
        logger.exception(e)
        logger.error(f"Error loading agents: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"type": "error", "message": str(e)}),
        }


def load_prompt_flows(bedrock_agent_client, table):
    try:
        response = bedrock_agent_client.list_flows(
            maxResults=100,
        )
        flow_summaries = response.get("flowSummaries", [])
        ret = []

        # Convert datetime objects to ISO format strings
        for flow in flow_summaries:
            flow_id = flow["id"]
            flow_alias_response = bedrock_agent_client.list_flow_aliases(
                maxResults=100,
                flowIdentifier=flow_id,
            )
            flow_aliases = flow_alias_response["flowAliasSummaries"]
            for alias in flow_aliases:
                alias["mode_selector"] = alias["arn"]
                alias["mode_selector_name"] = alias["name"]
                ddb_config = commons.get_ddb_config(
                    table, ddb_cache, ddb_cache_timestamp, CACHE_DURATION, logger
                )
                alias["is_active"] = ddb_config.get(alias["arn"], {}).get(
                    "access_granted", True
                )
                alias["allow_input_image"] = ddb_config.get(alias["arn"], {}).get(
                    "IMAGE", False
                )
                alias["allow_input_video"] = ddb_config.get(alias["arn"], {}).get(
                    "VIDEO", False
                )
                alias["allow_input_document"] = ddb_config.get(alias["arn"], {}).get(
                    "DOCUMENT", False
                )
                alias["allow_input_speech"] = ddb_config.get(alias["arn"], {}).get(
                    "SPEECH", False
                )
                alias["output_type"] = "TEXT"
                alias["category"] = "Bedrock Prompt Flows"
                if alias["name"] != "TSTALIASID":
                    ret.append(alias)

        return {"type": "load_prompt_flows", "prompt_flows": ret}
    except Exception as e:
        logger.exception(e)
        logger.error(f"Error loading prompt flows: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"type": "error", "message": str(e)}),
        }


def load_models(bedrock_client, table):
    try:
        # Remove unwanted models from foundation models
        foundation_model_response = (
            bedrock_client.list_foundation_models()
        )  # removed byInferenceType='ON_DEMAND'
        foundation_model_response["modelSummaries"] = [
            model
            for model in foundation_model_response["modelSummaries"]
            if "ON_DEMAND" in model["inferenceTypesSupported"]
            or "INFERENCE_PROFILE" in model["inferenceTypesSupported"]
        ]

        # query imported and inference profile models
        # list_imported_models_response = bedrock_client.list_imported_models()
        inference_profile_response = bedrock_client.list_inference_profiles()

        # Create a mapping of model ARNs to inference profile information
        # this is a list of model ARN's each pointing to an inference profile ARN and inference profile name
        inference_profile_map = {}
        for inference_profile in inference_profile_response[
            "inferenceProfileSummaries"
        ]:
            for model in inference_profile["models"]:
                inference_profile_map[model["modelArn"]] = {
                    "inferenceProfileArn": inference_profile["inferenceProfileArn"],
                    "inferenceProfileName": inference_profile["inferenceProfileName"],
                }

        bedrock_text_models = []
        # construct bedrock_text_models array:  add foundation models that dont map to an inference profile
        for model in foundation_model_response["modelSummaries"]:
            if model["modelArn"] not in inference_profile_map:
                bedrock_text_models.append(model)
        # construct bedrock_text_models array: add imported models
        # for model in list_imported_models_response["modelSummaries"]:
        #     original_model_arn = model["modelArn"]
        #     if original_model_arn in inference_profile_map:
        #         model["originalModelArn"] = original_model_arn
        #         model["originalModelName"] = model["modelName"]
        #         model["modelArn"] = inference_profile_map[original_model_arn][
        #             "inferenceProfileArn"
        #         ]
        #         model["modelName"] = inference_profile_map[original_model_arn][
        #             "inferenceProfileName"
        #         ]
        #         list_imported_models_response["modelSummaries"].append(model)
        # add inference profiles models to bedrock_text_models array
        for model in inference_profile_response["inferenceProfileSummaries"]:
            model["modelArn"] = model["inferenceProfileArn"]
            model["modelName"] = model["inferenceProfileName"]
            model["modelId"] = model["inferenceProfileId"]
            # for each model in models, find record in foundation_model_response['modelSummaries'] by modelArn
            for model_arn in model["models"]:
                for foundation_model in foundation_model_response["modelSummaries"]:
                    if foundation_model["modelArn"] == model_arn["modelArn"]:
                        model["providerName"] = foundation_model["providerName"]
                        model["inputModalities"] = foundation_model["inputModalities"]
                        model["outputModalities"] = foundation_model["outputModalities"]
                        model["modelLifecycle"] = {"status": "ACTIVE"}
                        model["inferenceTypesSupported"] = foundation_model[
                            "inferenceTypesSupported"
                        ]
                        model["responseStreamingSupported"] = foundation_model[
                            "responseStreamingSupported"
                        ]
                        break
            bedrock_text_models.append(model)

        text_models = [
            {
                "providerName": model["providerName"],
                "modelName": model["modelName"],
                "modelId": model["modelId"],
                "modelArn": model["modelArn"],
                "mode_selector": model["modelArn"],
                "mode_selector_name": model["modelName"],
            }
            for model in bedrock_text_models
            if "TEXT" in model["inputModalities"]
            and "TEXT" in model["outputModalities"]
            and model["modelLifecycle"]["status"] == "ACTIVE"
            and (
                "ON_DEMAND" in model["inferenceTypesSupported"]
                or "INFERENCE_PROFILE" in model["inferenceTypesSupported"]
            )
        ]
        # Filter and process text models
        # imported_models = [
        #     {
        #         "providerName": model["modelArchitecture"],
        #         "modelName": model["modelName"],
        #         "modelId": model["modelArn"],
        #         "modelArn": model["modelArn"],
        #         "mode_selector": model["modelArn"],
        #         "mode_selector_name": model["modelName"],
        #     }
        #     for model in list_imported_models_response["modelSummaries"]
        # ]

        # Filter and process image models
        image_models = [
            {
                "providerName": model["providerName"],
                "modelName": model["modelName"],
                "modelId": model["modelId"],
                "modelArn": model["modelArn"],
                "mode_selector": model["modelArn"],
                "mode_selector_name": model["modelName"],
            }
            for model in foundation_model_response["modelSummaries"]
            if (
                "Stability" in model["providerName"]
                or "Amazon" in model["providerName"]
            )
            and "TEXT" in model["inputModalities"]
            and "IMAGE" in model["outputModalities"]
            and model["modelLifecycle"]["status"] == "ACTIVE"
        ]

        # Filter and process speech models
        speech_models = [
            {
                "providerName": model["providerName"],
                "modelName": model["modelName"],
                "modelId": model["modelId"],
                "modelArn": model["modelArn"],
                "mode_selector": model["modelArn"],
                "mode_selector_name": model["modelName"],
            }
            for model in foundation_model_response["modelSummaries"]
            if (
                "SPEECH" in model["inputModalities"]
                and model["modelLifecycle"]["status"] == "ACTIVE"
            )
        ]

        video_models = [
            {
                "providerName": model["providerName"],
                "modelName": model["modelName"],
                "modelId": model["modelId"],
                "modelArn": model["modelArn"],
                "mode_selector": model["modelArn"],
                "mode_selector_name": model["modelName"],
            }
            for model in foundation_model_response["modelSummaries"]
            if "VIDEO" in model["outputModalities"]
            and model["modelLifecycle"]["status"] == "ACTIVE"
        ]

        # Process to keep only the latest version of each model
        available_text_models = keep_latest_versions(text_models)
        available_image_models = keep_latest_versions(image_models)
        available_speech_models = keep_latest_versions(speech_models)
        available_video_models = keep_latest_versions(video_models)

        available_text_models_return = []
        # available_imported_models_return = []
        available_image_models_return = []
        available_speech_models_return = []
        available_video_models_return = []
        # Update the models with DynamoDB config
        ddb_config = commons.get_ddb_config(
            table, ddb_cache, ddb_cache_timestamp, CACHE_DURATION, logger
        )
        for model in available_text_models:
            model_identifier = model.get("originalModelArn", model["modelId"])
            if ddb_config.get(model_identifier, {}).get("access_granted", False):
                model["is_active"] = True
                model["is_kb_model"] = ddb_config.get(model["modelId"], {}).get(
                    "is_kb_model", False
                )
                model["allow_input_image"] = ddb_config.get(model["modelId"], {}).get(
                    "IMAGE", False
                )
                model["allow_input_video"] = ddb_config.get(model["modelId"], {}).get(
                    "VIDEO", False
                )
                model["allow_input_document"] = ddb_config.get(
                    model["modelId"], {}
                ).get("DOCUMENT", False)
                model["allow_input_speech"] = ddb_config.get(model["modelId"], {}).get(
                    "SPEECH", False
                )
                model["output_type"] = "TEXT"
                model["category"] = "Bedrock Models"
                available_text_models_return.append(model)

        for model in available_image_models:
            model_identifier = model.get("originalModelArn", model["modelId"])
            if ddb_config.get(model_identifier, {}).get("access_granted", False):
                model["is_active"] = True
                model["allow_input_image"] = ddb_config.get(model["modelId"], {}).get(
                    "IMAGE", False
                )
                model["allow_input_video"] = ddb_config.get(model["modelId"], {}).get(
                    "VIDEO", False
                )
                model["allow_input_document"] = ddb_config.get(
                    model["modelId"], {}
                ).get("DOCUMENT", False)
                model["allow_input_speech"] = ddb_config.get(model["modelId"], {}).get(
                    "SPEECH", False
                )
                model["output_type"] = "IMAGE"
                model["category"] = "Bedrock Image Models"
                available_image_models_return.append(model)

        for model in available_speech_models:
            model_identifier = model.get("originalModelArn", model["modelId"])
            if ddb_config.get(model_identifier, {}).get("access_granted", False):
                model["is_active"] = True
                model["allow_input_image"] = ddb_config.get(model["modelId"], {}).get(
                    "IMAGE", False
                )
                model["allow_input_video"] = ddb_config.get(model["modelId"], {}).get(
                    "VIDEO", False
                )
                model["allow_input_document"] = ddb_config.get(
                    model["modelId"], {}
                ).get("DOCUMENT", False)
                model["allow_input_speech"] = ddb_config.get(model["modelId"], {}).get(
                    "SPEECH", False
                )
                model["output_type"] = "SPEECH"
                model["category"] = "Bedrock Speech Models"
                available_speech_models_return.append(model)

        for model in available_video_models:
            model_identifier = model.get("originalModelArn", model["modelId"])
            if ddb_config.get(model_identifier, {}).get("access_granted", False):
                model["is_active"] = True
                model["allow_input_image"] = ddb_config.get(model["modelId"], {}).get(
                    "IMAGE", False
                )
                model["allow_input_video"] = ddb_config.get(model["modelId"], {}).get(
                    "VIDEO", False
                )
                model["allow_input_document"] = ddb_config.get(
                    model["modelId"], {}
                ).get("DOCUMENT", False)
                model["allow_input_speech"] = ddb_config.get(model["modelId"], {}).get(
                    "SPEECH", False
                )
                model["output_type"] = "VIDEO"
                model["video_helper_image_model_id"] = ddb_config.get(
                    model["modelId"], {}
                ).get("video_helper_image_model_id", None)
                model["category"] = "Bedrock Video Models"
                available_video_models_return.append(model)
        # for model in imported_models:
        #     model_identifier = model.get("originalModelArn", model["modelId"])
        #     if ddb_config.get(model_identifier, {}).get("access_granted", False):
        #         model["is_active"] = True
        #         model["allow_input_image"] = ddb_config.get(model["modelId"], {}).get(
        #             "IMAGE", False
        #         )
        #         model["allow_input_video"] = ddb_config.get(model["modelId"], {}).get(
        #             "VIDEO", False
        #         )
        #         model["allow_input_document"] = ddb_config.get(
        #             model["modelId"], {}
        #         ).get("DOCUMENT", False)
        #         model["allow_input_speech"] = ddb_config.get(model["modelId"], {}).get(
        #             "SPEECH", False
        #         )
        #         model["output_type"] = "TEXT"
        #         model["category"] = "Imported Models"
        #         available_imported_models_return.append(model)

        return {
            "type": "load_models",
            # "imported_models": available_imported_models_return,
            "text_models": available_text_models_return,
            "video_models": available_video_models_return,
            "image_models": available_image_models_return,
            "speech_models": available_speech_models_return,
        }
    except Exception as e:
        logger.exception(e)
        logger.error(f"Error loading models: {str(e)}")
        return []


def keep_latest_versions(models):
    latest_models = {}
    for model in models:
        model_key = (model["providerName"], model["modelName"])
        if (
            model_key not in latest_models
            or compare_versions(model["modelId"], latest_models[model_key]["modelId"])
            > 0
        ):
            latest_models[model_key] = model
    return list(latest_models.values())


def compare_versions(version1, version2):
    """
    Compare two version strings.
    Returns: 1 if version1 is newer, -1 if version2 is newer, 0 if equal
    """
    v1_parts = version1.split(":")
    v2_parts = version2.split(":")

    # Compare the base part (before the colon)
    if v1_parts[0] != v2_parts[0]:
        return 1 if v1_parts[0] > v2_parts[0] else -1

    # If base parts are equal, compare the version numbers after the colon
    if len(v1_parts) > 1 and len(v2_parts) > 1:
        v1_num = int(v1_parts[1]) if v1_parts[1].isdigit() else 0
        v2_num = int(v2_parts[1]) if v2_parts[1].isdigit() else 0
        return 1 if v1_num > v2_num else (-1 if v1_num < v2_num else 0)

    # If one has a version number and the other doesn't, the one with a version number is newer
    return (
        1
        if len(v1_parts) > len(v2_parts)
        else (-1 if len(v2_parts) > len(v1_parts) else 0)
    )
