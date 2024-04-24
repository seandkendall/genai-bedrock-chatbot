from aws_cdk import (
    aws_cognito as cognito,
    custom_resources as cr,
    aws_iam as iam,
)
from constructs import Construct

class UserPoolUser(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        props: dict,
        **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        user_pool = props["user_pool"]
        username = props["username"]
        password = props["password"]
        attributes = props.get("attributes", [])
        group_name = props.get("group_name")

        # Create the user inside the Cognito user pool using Lambda backed AWS Custom resource
        admin_create_user = cr.AwsCustomResource(
            self,
            "AwsCustomResource-CreateUser",
            on_create={
                "service": "CognitoIdentityServiceProvider",
                "action": "adminCreateUser",
                "parameters": {
                    "UserPoolId": user_pool.user_pool_id,
                    "Username": username,
                    "MessageAction": "SUPPRESS",
                    "TemporaryPassword": password,
                    "UserAttributes": [{"Name": attr["Name"], "Value": attr["Value"]} for attr in attributes],
                },
                "physical_resource_id": cr.PhysicalResourceId.of(f"AwsCustomResource-CreateUser-{username}"),
            },
            on_delete={
                "service": "CognitoIdentityServiceProvider",
                "action": "adminDeleteUser",
                "parameters": {
                    "UserPoolId": user_pool.user_pool_id,
                    "Username": username,
                },
            },
            policy=cr.AwsCustomResourcePolicy.from_sdk_calls(
                resources=[stmt.resources[0] for stmt in [  # Extract ARN strings from PolicyStatement
                    iam.PolicyStatement(
                        actions=["cognito-idp:AdminCreateUser", "cognito-idp:AdminDeleteUser"],
                        resources=["*"],
                    )
                ]]
            ),
        )

        # Force the password for the user, because by default when new users are created
        # they are in FORCE_PASSWORD_CHANGE status. The newly created user has no way to change it though
        admin_set_user_password = cr.AwsCustomResource(
            self,
            "AwsCustomResource-ForcePassword",
            on_create={
                "service": "CognitoIdentityServiceProvider",
                "action": "adminSetUserPassword",
                "parameters": {
                    "UserPoolId": user_pool.user_pool_id,
                    "Username": username,
                    "Password": password,
                    "Permanent": True,
                },
                "physical_resource_id": cr.PhysicalResourceId.of(f"AwsCustomResource-ForcePassword-{username}"),
            },
            policy=cr.AwsCustomResourcePolicy.from_sdk_calls(
                resources=[stmt.resources[0] for stmt in [  # Extract ARN strings from PolicyStatement
                    iam.PolicyStatement(
                        actions=["cognito-idp:AdminSetUserPassword"],
                        resources=["*"],
                    )
                ]]
            ),
        )
        admin_set_user_password.node.add_dependency(admin_create_user)

        # If a Group Name is provided, also add the user to this Cognito UserPool Group
        if group_name:
            user_to_group_attachment = cognito.CfnUserPoolUserToGroupAttachment(
                self,
                "AttachUserToGroup",
                user_pool_id=user_pool.user_pool_id,
                group_name=group_name,
                username=username,
            )
            user_to_group_attachment.node.add_dependency(admin_create_user)
            user_to_group_attachment.node.add_dependency(admin_set_user_password)
