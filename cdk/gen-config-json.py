#!/usr/bin/env python3

"""
Purpose:
This script generates a config.json file for Amplify client configuration by querying AWS Cognito 
settings using boto3. The generated file will be placed in /cdk/react-chatbot/src.

This script is used by /deploy-web.sh to generate config.json, which it will deploy with the web
app so that the web app can use the Cognito settings for authentication

Authentication Options:

1. Standalone Cognito Setup (Default):
   - The CDK deployment creates a dedicated Cognito User Pool and User Pool Client
   - Ideal for projects requiring independent user management
   - No external identity provider integration required
   - All you have to do is deploy, using the instructions 
     at https://github.com/seandkendall/genai-bedrock-chatbot 

2. Enterprise Identity Provider Integration:
   - Supports integration with existing corporate identity providers
   - Compatible with SAML and OpenID Connect providers
   - Configuration steps:
     a. Configure your identity provider in AWS Cognito console
        (See https://aws.amazon.com/blogs/security/how-to-set-up-amazon-cognito-for-federated-authentication-using-azure-ad/
        for an example of how to configure Azure AD SAML integration)
     c. Run this script to generate updated config.json with the new settings

The config.json file contains the necessary connection properties for your 
application to interact with Cognito, whether using the standalone pool or 
an integrated identity provider.

Prerequisites:
Before running this script, you need valid AWS credentials configured for your target AWS account.

To set up your AWS credentials, you have several options:
1. Configure AWS CLI credentials
2. Use environment variables
3. Use AWS IAM roles

For guidance on AWS credentials setup, you can:
- Consult your AWS administrator
- Work with your AWS Account Team
- Use Amazon Q for developer assistance
- Review the AWS CLI configuration documentation

The script requires proper AWS authentication to execute successfully.

OR you can run this script from cloudshell in your AWS console if you've already cloned the git repo there.
"""


import boto3
import json

# Initialize AWS clients
cognito_client = boto3.client('cognito-idp')

# Specify your User Pool name or partial name (if known)
user_pool_name = "ChatbotUserPool"  # Replace with your user pool name or leave blank to list all
aws_region = "us-west-2"  # Replace with your AWS region

# Function to fetch the User Pool ID
def get_user_pool_id():
    paginator = cognito_client.get_paginator("list_user_pools")
    page_iterator = paginator.paginate(MaxResults=10)

    for page in page_iterator:
        for pool in page.get("UserPools", []):
            if user_pool_name in pool["Name"]:
                return pool["Id"]
    raise Exception(f"User Pool with name '{user_pool_name}' not found.")

# Function to fetch User Pool details

# Function to fetch OAuth details (App Client) for a given User Pool ID
def get_app_client_details(user_pool_id):
    response = cognito_client.list_user_pool_clients(UserPoolId=user_pool_id, MaxResults=10)
    
    if not response["UserPoolClients"]:
        raise Exception(f"No app clients found for User Pool ID: {user_pool_id}")

    # Assume the first app client is the one we care about (customize as needed)
    app_client_id = response["UserPoolClients"][0]["ClientId"]
    
    # Get App Client details
    app_client_details = cognito_client.describe_user_pool_client(
        UserPoolId=user_pool_id, ClientId=app_client_id
    )["UserPoolClient"]

    oauth_settings = app_client_details.get("AllowedOAuthFlowsUserPoolClient", False)

    return app_client_details

def validate_and_get_idp(providers):
    """
    Validates the list of identity providers and returns the first one if there is only one.

    Args:
        providers (list): A list of identity provider names.

    Returns:
        str: The name of the single identity provider if exactly one exists.
        None: If there are zero or more than one identity providers.
    """
    if len(providers) == 1:
        print(f"The only identity provider is: {providers[0]}")
        return providers[0]  # Return the single provider's name
    elif len(providers) == 0:
        print("There is either no identity provider or more than one.")
        return None  # Return None if there are zero or multiple providers
    elif len(providers) == 2:
        # find the provider that is not COGNITO and return that one, print that you are returning that one and also print the whole list of providers
        print(f"There are two identity providers: {providers}")
        for provider in providers:
            if provider != "COGNITO":
                print(f"The identity provider that is not COGNITO is: {provider}, so using that")
                return provider
                # return the provider that is not COGNITO
    else:
        print(f"There are more than two identity providers: {providers}, returning None")
        return None

# Main function to extract details and write to config.json
def main():
    try:
        # Step 1: Get the User Pool ID
        user_pool_id = get_user_pool_id()
        
        print(f"User Pool ID: {user_pool_id}")

        # Step 2: Get User Pool Details
        response = cognito_client.describe_user_pool(UserPoolId=user_pool_id)
        user_pool = response["UserPool"]

        # Extract password policy
        password_policy = user_pool["Policies"]["PasswordPolicy"]

        # Extract MFA configuration
        mfa_configuration = user_pool.get("MfaConfiguration", "NONE")

        # Extract username attributes and standard required attributes
        username_attributes = user_pool.get("UsernameAttributes", [])
        standard_required_attributes = [
            attr["Name"] for attr in user_pool["SchemaAttributes"] if attr.get("Required", False)
        ]

        domain = user_pool["Domain"]

        # Step 3: Get OAuth Details
        app_client_details = get_app_client_details(user_pool_id)

        # Step 4: Combine all details into the desired format
        config_data = {
                "auth": {
                        "user_pool_id": user_pool_id,
                        "user_pool_client_id": app_client_details['ClientId'],
                        "aws_region": aws_region,
                        "mfa_methods": [],  # Customize if needed
                        "standard_required_attributes": standard_required_attributes,
                        "username_attributes": username_attributes,
                        "user_verification_types": ["email"],  # Customize if needed
                        "password_policy": {
                            "min_length": password_policy.get("MinimumLength", 8),
                            "require_lowercase": password_policy.get("RequireLowercase", False),
                            "require_numbers": password_policy.get("RequireNumbers", False),
                            "require_symbols": password_policy.get("RequireSymbols", False),
                            "require_uppercase": password_policy.get("RequireUppercase", False),
                        },
                        "oauth": {
                            "identity_providers": [validate_and_get_idp(app_client_details['SupportedIdentityProviders'])],  # Customize if needed (e.g., from list_identity_providers API)
                            "redirect_sign_in_uri": app_client_details.get("CallbackURLs", []),
                            "redirect_sign_out_uri": app_client_details.get("LogoutURLs", []),
                            "response_type": app_client_details.get("AllowedOAuthFlows", ["code"]),
                            "scopes": app_client_details.get("AllowedOAuthScopes", ["phone", "email", "profile", "openid"]),
                            "domain": f"{domain}.auth.{aws_region}.amazoncognito.com",
                        }
                        },
                        "version": "1.2",
                    }

        # Write details to config.json
        with open("./react-chatbot/src/config.json", "w") as config_file:
            json.dump(config_data, config_file, indent=4)

        print("Configuration details have been written to config.json")

    except Exception as e:
        print(f"An error occurred: {e}")

# Run the script
if __name__ == "__main__":
    main()