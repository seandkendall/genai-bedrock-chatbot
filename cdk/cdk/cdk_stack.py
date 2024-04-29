from aws_cdk import (
    Stack, Duration, CfnOutput,CfnParameter,
    aws_s3 as s3,
    aws_lambda as _lambda,
    aws_s3_deployment as s3deploy,
    aws_cloudfront as cloudfront,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    aws_logs as logs,
    aws_apigatewayv2 as apigwv2,
    aws_apigatewayv2_integrations as apigwv2_integrations,
    aws_cognito as cognito,
    RemovalPolicy,
)
from constructs import Construct
from aws_solutions_constructs.aws_cloudfront_s3 import CloudFrontToS3
from .constructs.user_pool_user import UserPoolUser
import json

class ChatbotWebsiteStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        cognito_domain_param = CfnParameter(self, "cognitoDomain", type="String",
            description="Specify your unique cognito domain")
        cognito_domain_string = cognito_domain_param.value_as_string
        
        allowlist_domain_param = CfnParameter(self, "allowlistDomain", type="String",
            description="Specify your domain allowlist")
        allowlist_domain_string = allowlist_domain_param.value_as_string

        # Create a Lambda layer for the Boto3 library
        boto3_layer = _lambda.LayerVersion(
            self, "Boto3Layer",
            code=_lambda.Code.from_asset("lambda_functions/python_layer"),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_12],
            description="Boto3 library layer"
        )

        # Create the S3 bucket for website content
        bucket = s3.Bucket(self, "GenAiChatbotS3BucketContent",
                           removal_policy=RemovalPolicy.DESTROY,
                           auto_delete_objects=True )

        # Create the S3 bucket for conversation history
        conversation_history_bucket = s3.Bucket(self, "ConversationHistoryBucket",
                           removal_policy=RemovalPolicy.DESTROY,
                           auto_delete_objects=True )

        # Create the S3 bucket for agent schemas
        schemabucket = s3.Bucket(self, "GenAiChatbotS3BucketAgentSchemas",
                           removal_policy=RemovalPolicy.DESTROY,
                           auto_delete_objects=True )

        # Deploy agent schemas to the S3 bucket
        s3deploy.BucketDeployment(self, "s3FilesDeploymentSchema",
                            sources=[s3deploy.Source.asset("./bedrock_agent_schemas")],
                            destination_bucket=schemabucket,
                            prune=True)
        
        
        # Create a CloudFront distribution for the website content S3 bucket
        cloudfront_to_s3 = CloudFrontToS3(self, 'CloudfrontDist',
                       existing_bucket_obj=bucket,
                       insert_http_security_headers=False,
                       cloud_front_distribution_props={
                           'comment': 'GenAiChatbot Website',
                           'defaultBehavior': {
                               'cachePolicy': cloudfront.CachePolicy.CACHING_DISABLED
                           }
                       }
                       )
        cloudfront_distribution = cloudfront_to_s3.cloud_front_web_distribution
        

        # Create DynamoDB table for bedrock_usage with a user_id (partition key string), input_tokens (number) and output_tokens(number)
        dynamodb_bedrock_usage_table = dynamodb.Table(self, "dynamodb_bedrock_usage_table",
                                                      partition_key=dynamodb.Attribute(name="user_id", type=dynamodb.AttributeType.STRING))
        dynamodb_bedrock_usage_table.removal_policy = RemovalPolicy.DESTROY
        
        dynamodb_conversations_table = dynamodb.Table(self, "dynamodb_conversations_table", 
                                                      partition_key=dynamodb.Attribute(name="session_id", type=dynamodb.AttributeType.STRING))
        dynamodb_conversations_table.removal_policy = RemovalPolicy.DESTROY
        dynamodb_incidents_table = dynamodb.Table(self, "dynamodb_incidents_table", 
                                                  partition_key=dynamodb.Attribute(name="incident_id", type=dynamodb.AttributeType.STRING))
        dynamodb_incidents_table.removal_policy = RemovalPolicy.DESTROY

        dynamodb_configurations_table = dynamodb.Table(
            self, "dynamodb_configurations_table",
            partition_key=dynamodb.Attribute(name="user", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="config_type", type=dynamodb.AttributeType.STRING),
            removal_policy=RemovalPolicy.DESTROY
        )
        dynamodb_configurations_table.removal_policy = RemovalPolicy.DESTROY


        # Create a WebSocket API
        websocket_api = apigwv2.WebSocketApi(
            self, "ChatbotWebSocketApi",
        )
        websocket_api.removal_policy = RemovalPolicy.DESTROY
        websocket_api_endpoint = websocket_api.api_endpoint
        apigwv2.WebSocketStage(self, "mystage",
            web_socket_api=websocket_api,
            stage_name="ws",
            auto_deploy=True,
        )

        config_function = _lambda.Function(
            self, "genai_bedrock_config_fn",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="lambda_function.lambda_handler",
            code=_lambda.Code.from_asset("./lambda_functions/genai_bedrock_config_fn/"),
            timeout=Duration.seconds(30),
            tracing=_lambda.Tracing.ACTIVE,
            memory_size=1024,
            layers=[boto3_layer],
            log_retention=logs.RetentionDays.FIVE_DAYS,
            environment={
                "DYNAMODB_TABLE": dynamodb_configurations_table.table_name,
                "ALLOWLIST_DOMAIN": allowlist_domain_string,
                "REGION": self.region,
            }
        )
        config_function.removal_policy = RemovalPolicy.DESTROY
        config_function_role = config_function.role
        config_function_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AmazonBedrockReadOnly")
        )

        dynamodb_configurations_table.grant_full_access(config_function)

        # Create the "genai_bedrock_agents_client_fn" Lambda function
        agents_client_function = _lambda.Function(self, "genai_bedrock_agents_client_fn",
                                     runtime=_lambda.Runtime.PYTHON_3_12,
                                     handler="lambda_function.lambda_handler",
                                     code=_lambda.Code.from_asset("./lambda_functions/genai_bedrock_agents_client_fn/"),
                                     timeout=Duration.seconds(900),
                                     tracing=_lambda.Tracing.ACTIVE,
                                     memory_size=1024,
                                     layers=[boto3_layer],
                                     log_retention=logs.RetentionDays.FIVE_DAYS,
                                     environment={
                                          "DYNAMODB_TABLE": dynamodb_configurations_table.table_name,
                                          "WEBSOCKET_API_ENDPOINT": websocket_api_endpoint
                                     }
                                     )
        agents_client_function.removal_policy = RemovalPolicy.DESTROY
        agents_client_function.role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonBedrockFullAccess"))
        agents_client_function.role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonAPIGatewayInvokeFullAccess"))
        agents_client_function.role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSQSFullAccess"))
        dynamodb_conversations_table.grant_full_access(agents_client_function)
        conversation_history_bucket.grant_read_write(agents_client_function)
        dynamodb_configurations_table.grant_read_data(agents_client_function)
        

        # Create the "genai_bedrock_agents_fn" Lambda function
        agents_function = _lambda.Function(self, "genai_bedrock_agents_fn",
                                     runtime=_lambda.Runtime.PYTHON_3_12,
                                     handler="lambda_function.lambda_handler",
                                     code=_lambda.Code.from_asset("./lambda_functions/genai_bedrock_agents_fn/"),
                                     timeout=Duration.seconds(120),
                                     tracing=_lambda.Tracing.ACTIVE,
                                     memory_size=1024,
                                     layers=[boto3_layer],
                                     log_retention=logs.RetentionDays.FIVE_DAYS,
                                     environment={
                                          "DYNAMODB_TABLE": dynamodb_incidents_table.table_name,
                                     }
                                     )
        agents_function.removal_policy = RemovalPolicy.DESTROY
        dynamodb_incidents_table.grant_full_access(agents_function)
        agents_function.add_permission(
            "AllowBedrock",
            principal=iam.ServicePrincipal("bedrock.amazonaws.com"),
            source_arn=f"arn:aws:bedrock:{self.region}:{self.account}:agent/*"
        )

        # Create the "genai_bedrock_fn_async" Lambda function
        lambda_fn_async = _lambda.Function(self, "genai_bedrock_fn_async",
                                     runtime=_lambda.Runtime.PYTHON_3_12,
                                     handler="lambda_function.lambda_handler",
                                     code=_lambda.Code.from_asset("./lambda_functions/genai_bedrock_async_fn/"),
                                     timeout=Duration.seconds(900),
                                     tracing=_lambda.Tracing.ACTIVE,
                                     memory_size=1024,
                                     layers=[boto3_layer],
                                     log_retention=logs.RetentionDays.FIVE_DAYS,                                     
                                     environment={
                                          "DYNAMODB_TABLE": dynamodb_conversations_table.table_name,
                                          "CONVERSATION_HISTORY_BUCKET": conversation_history_bucket.bucket_name,
                                          "WEBSOCKET_API_ENDPOINT": websocket_api_endpoint,
                                          "DYNAMODB_TABLE_CONFIG": dynamodb_configurations_table.table_name,
                                          "DYNAMODB_TABLE_USAGE": dynamodb_bedrock_usage_table.table_name,
                                          "REGION": self.region
                                     }
                                     )
        lambda_fn_async.removal_policy = RemovalPolicy.DESTROY
        lambda_fn_async.role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonBedrockFullAccess"))
        lambda_fn_async.role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonAPIGatewayInvokeFullAccess"))
        lambda_fn_async.role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSQSFullAccess"))
        dynamodb_conversations_table.grant_full_access(lambda_fn_async)
        dynamodb_configurations_table.grant_full_access(lambda_fn_async)
        conversation_history_bucket.grant_read_write(lambda_fn_async)
        dynamodb_bedrock_usage_table.grant_full_access(lambda_fn_async)

        # Create a Cognito User Pool
        user_pool = cognito.UserPool(
            self, "ChatbotUserPool",
            user_pool_name="ChatbotUserPool",
            self_sign_up_enabled=True,
            sign_in_aliases={"email": True},  # Enable sign-in with email
            auto_verify={"email": True},  # Auto-verify email addresses
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            removal_policy=RemovalPolicy.DESTROY,
            password_policy=cognito.PasswordPolicy(  # Configure password policy
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True,
            ),
        )
        # Create the "genai_bedrock_fn" Lambda function
        lambda_fn = _lambda.Function(self, "genai_bedrock_fn",
                                     runtime=_lambda.Runtime.PYTHON_3_12,
                                     handler="lambda_function.lambda_handler",
                                     code=_lambda.Code.from_asset("./lambda_functions/genai_bedrock_fn/"),
                                     timeout=Duration.seconds(20),
                                     tracing=_lambda.Tracing.ACTIVE,
                                     memory_size=1024,
                                     layers=[boto3_layer],
                                     log_retention=logs.RetentionDays.FIVE_DAYS,
                                     environment={
                                          "USER_POOL_ID": user_pool.user_pool_id,
                                          "REGION": self.region,
                                          "AGENTS_FUNCTION_NAME": agents_client_function.function_name,
                                          "BEDROCK_FUNCTION_NAME": lambda_fn_async.function_name,
                                          "ALLOWLIST_DOMAIN": allowlist_domain_string
                                        }
                                     )
        lambda_fn.removal_policy = RemovalPolicy.DESTROY
        
        dynamodb_conversations_table.grant_full_access(lambda_fn)
        lambda_fn_async.grant_invoke(lambda_fn)
        agents_client_function.grant_invoke(lambda_fn)
        dynamodb_incidents_table.grant_full_access(agents_client_function)

        # Create a Lambda integration for the "genai_bedrock_fn" Lambda
        bedrock_fn_integration = apigwv2_integrations.WebSocketLambdaIntegration(
            "BedrockFnIntegration", lambda_fn
        )
        config_fn_integration = apigwv2_integrations.WebSocketLambdaIntegration(
            "ConfigFnIntegration", config_function
        )

        # Add routes and integrations to the WebSocket API
        websocket_api.add_route(
            "config",
            integration=config_fn_integration,
            return_response=True
        )
        websocket_api.add_route(
            "$default",
            integration=bedrock_fn_integration,
            return_response=True
        )

        # Create a Cognito User Pool Client
        user_pool_client = cognito.UserPoolClient(
            self, "ChatbotUserPoolClient",
            user_pool=user_pool,
            auth_flows=cognito.AuthFlow(
                user_srp=True,
                user_password=True,
            ),
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(
                    authorization_code_grant=False,
                    implicit_code_grant=True,
                ),
                scopes=[cognito.OAuthScope.EMAIL],
                callback_urls=[f'https://{cloudfront_to_s3.cloud_front_web_distribution.domain_name}'],
                logout_urls=[f'https://{cloudfront_to_s3.cloud_front_web_distribution.domain_name}'],
            ),
            user_pool_client_name="ChatbotUserPoolClient",
        )

        user_pool_client.removal_policy = RemovalPolicy.DESTROY

        # Create a Cognito User Pool Domain
        user_pool_domain = cognito.UserPoolDomain(
            self, "ChatbotUserPoolDomain",
            user_pool=user_pool,
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=cognito_domain_string
            )
        )

        
        # Deploy the website files and variables.js to the S3 bucket
        s3deploy.BucketDeployment(self, "s3FilesDeployment",
                            sources=[s3deploy.Source.asset("./static-website-source")],
                            destination_bucket=bucket,
                            prune=True)


        # Export CloudFormation outputs
        CfnOutput(self, "AWSChatBotURL", value='https://'+cloudfront_to_s3.cloud_front_web_distribution.domain_name) 
        CfnOutput(self, "region", value=self.region) 
        CfnOutput(self, "user_pool_id", value=user_pool.user_pool_id) 
        CfnOutput(self, "user_pool_client_id", value=user_pool_client.user_pool_client_id) 
        CfnOutput(self, "websocket_api_endpoint", value=websocket_api_endpoint+'/ws') 