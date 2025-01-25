#!/usr/bin/env python3
import os

import aws_cdk as cdk
from cdk.cdk_stack import ChatbotWebsiteStack

app = cdk.App()
chatbot_stack = ChatbotWebsiteStack(app, "ChatbotWebsiteStack")
cdk.Tags.of(chatbot_stack).add("auto-delete", "false")
cdk.Tags.of(chatbot_stack).add("auto-stop", "false")
cdk.Tags.of(chatbot_stack).add("project", "genai-bedrock-chatbot")
 
app.synth()
