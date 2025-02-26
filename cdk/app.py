#!/usr/bin/env python3
import os

import aws_cdk as cdk
import cdk_nag
from cdk.cdk_stack import ChatbotWebsiteStack
from cdk.codebuild_stack import CodeBuildStack
from aws_cdk import (aws_servicecatalogappregistry_alpha as appreg)
 
# create variable for deploy_service_catalog_application as True
deploy_service_catalog_application = True
app = cdk.App()
region = os.environ.get('CDK_DEFAULT_REGION')
# uncomment the following line to turn on AWS CDK NAG
# cdk.Aspects.of(app).add(cdk_nag.AwsSolutionsChecks(verbose=True))
chatbot_stack = ChatbotWebsiteStack(app, "ChatbotWebsiteStack")

aws_application = 'NoApplicationCreatedyet'
if chatbot_stack.aws_application is not None and len(chatbot_stack.aws_application) > 1:
    aws_application = chatbot_stack.aws_application
imported_models = ""
if chatbot_stack.imported_models is not None and len(chatbot_stack.imported_models) > 1:
    imported_models = chatbot_stack.imported_models    

custom_model_s3_bucket_name = chatbot_stack.custom_model_import_bucket.bucket_name
codebuild_stack = CodeBuildStack(app, "ChatbotWebsiteStack-CodeBuildStack",
                                 custom_model_s3_bucket_name=custom_model_s3_bucket_name,
                                 imported_models=imported_models,
                                 project=f"genai-bedrock-chatbot-{region}",
                                 aws_application=aws_application)
if deploy_service_catalog_application:
    application = appreg.Application(chatbot_stack,
                    "GenAIBedrockChatbot",
                    application_name=f"GenAIBedrockChatbot-{region}",
                    description=f"GenAI Bedrock Chatbot deployed in the {region} Region")
    application.associate_application_with_stack(chatbot_stack)
    application.associate_application_with_stack(codebuild_stack)

cdk.Tags.of(chatbot_stack).add("auto-delete", "false")
cdk.Tags.of(chatbot_stack).add("auto-stop", "false")
cdk.Tags.of(chatbot_stack).add("project", f"genai-bedrock-chatbot-{region}")

cdk.Tags.of(codebuild_stack).add("auto-delete", "false")
cdk.Tags.of(codebuild_stack).add("auto-stop", "false")
cdk.Tags.of(codebuild_stack).add("project", f"genai-bedrock-chatbot-{region}")

if deploy_service_catalog_application and chatbot_stack.aws_application is not None and len(chatbot_stack.aws_application) > 1:
    cdk.Tags.of(chatbot_stack).add("awsApplication", chatbot_stack.aws_application)
    cdk.Tags.of(codebuild_stack).add("awsApplication", chatbot_stack.aws_application)
    
app.synth()
