#!/usr/bin/env python3
import os

import aws_cdk as cdk
import cdk_nag
from aws_cdk import (aws_servicecatalogappregistry_alpha as appreg)
from cdk.cdk_stack import ChatbotWebsiteStack
from cdk.codebuild_stack import CodeBuildStack
 

app = cdk.App()
# uncomment the following line to turn on AWS CDK NAG
# cdk.Aspects.of(app).add(cdk_nag.AwsSolutionsChecks(verbose=True))
region = os.environ.get('CDK_DEFAULT_REGION')
chatbot_stack = ChatbotWebsiteStack(app, "ChatbotWebsiteStack")
custom_model_s3_bucket_name = chatbot_stack.custom_model_import_bucket.bucket_name
codebuild_stack = CodeBuildStack(app, "ChatbotWebsiteStack-CodeBuildStack", custom_model_s3_bucket_name=custom_model_s3_bucket_name)
application = appreg.Application(chatbot_stack,
                   "GenAIBedrockChatbot",
                   application_name="GenAIBedrockChatbot",
                   description="GenAI Bedrock Chatbot")
application.associate_application_with_stack(chatbot_stack)
application.associate_application_with_stack(codebuild_stack)
cdk.Tags.of(chatbot_stack).add("auto-delete", "false")
cdk.Tags.of(chatbot_stack).add("auto-stop", "false")
cdk.Tags.of(chatbot_stack).add("project", f"genai-bedrock-chatbot-{region}")

cdk.Tags.of(codebuild_stack).add("auto-delete", "false")
cdk.Tags.of(codebuild_stack).add("auto-stop", "false")
cdk.Tags.of(codebuild_stack).add("project", f"genai-bedrock-chatbot-{region}")
app.synth()
