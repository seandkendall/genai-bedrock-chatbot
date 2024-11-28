#!/usr/bin/env python3
"""
CloudFormation Stack Output Generator

This script extracts outputs from a specified AWS CloudFormation stack and writes
them to a JSON file in a CDK-compatible format. It's particularly useful for
capturing and persisting stack outputs for use in other applications or processes.

This script is used by /deploy-web.sh to generate outputs.json, which it will refer
to for creation of config.json and variables.js

Usage:
    Simply run the script with appropriate AWS credentials configured.
    The script will generate an outputs.json file in the current directory.

Requirements:
    - boto3
    - Valid AWS credentials with CloudFormation read permissions
    - Existing CloudFormation stack
"""

import boto3
import json

# Initialize the CloudFormation client
cloudformation_client = boto3.client('cloudformation')

# Specify the stack name (update this as needed)
stack_name = "ChatbotWebsiteStack"  # Replace with your stack name

try:
    # Call describe_stacks to get stack details
    response = cloudformation_client.describe_stacks(StackName=stack_name)
    
    # Extract outputs from the stack
    stacks = response.get('Stacks', [])
    if not stacks:
        raise Exception(f"No stack found with name {stack_name}")
    
    # Get the outputs from the stack
    stack_outputs = stacks[0].get('Outputs', [])
    
    # Convert outputs into a nested dictionary format for CDK-style outputs.json
    outputs_dict = {
        stack_name: {
            output["OutputKey"]: output["OutputValue"] for output in stack_outputs
        }
    }
    
    # Write the outputs to outputs.json
    with open("outputs.json", "w") as file:
        json.dump(outputs_dict, file, indent=4)
    
    print("CloudFormation outputs have been written to outputs.json")

except Exception as e:
    print(f"An error occurred: {e}")