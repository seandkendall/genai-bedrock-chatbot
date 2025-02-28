#!/usr/bin/env python3
import os

import aws_cdk as cdk
# import cdk_nag
from aws_cdk import (aws_servicecatalogappregistry_alpha as appreg)
from cdk.cdk_stack import ChatbotWebsiteStack
 
DEPLOY_SERVICE_CATALOG_APPLICATION = True
app = cdk.App()
region = os.environ.get('CDK_DEFAULT_REGION')
# uncomment the following line to turn on AWS CDK NAG
# cdk.Aspects.of(app).add(cdk_nag.AwsSolutionsChecks(verbose=True))
chatbot_stack = ChatbotWebsiteStack(app, "ChatbotWebsiteStack")
if DEPLOY_SERVICE_CATALOG_APPLICATION:
    application = appreg.Application(chatbot_stack,
                    "GenAIBedrockChatbot",
                    application_name=f"GenAIBedrockChatbot-{region}",
                    description=f"GenAI Bedrock Chatbot deployed in the {region} Region")
    application.associate_application_with_stack(chatbot_stack)

cdk.Tags.of(chatbot_stack).add("auto-delete", "false")
cdk.Tags.of(chatbot_stack).add("auto-stop", "false")
cdk.Tags.of(chatbot_stack).add("project", f"genai-bedrock-chatbot-{region}")


if DEPLOY_SERVICE_CATALOG_APPLICATION and chatbot_stack.aws_application is not None and len(chatbot_stack.aws_application) > 1:
    cdk.Tags.of(chatbot_stack).add("awsApplication", chatbot_stack.aws_application)
    
app.synth()
