from aws_cdk import ( # type: ignore
    Stack, Duration, CfnOutput,
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
    aws_cloudfront_origins as origins,
    RemovalPolicy,
    aws_certificatemanager as acm
)
from constructs import Construct
from aws_solutions_constructs.aws_cloudfront_s3 import CloudFrontToS3 # type: ignore
from .constructs.user_pool_user import UserPoolUser
import json
from aws_cdk.aws_route53 import PublicHostedZone


class ChatbotWebsiteStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        cognito_domain_string = self.node.try_get_context("cognitoDomain")
        if cognito_domain_string is None:
            cognito_domain_string = ""
        allowlist_domain_string = self.node.try_get_context("allowlistDomain")
        # if allowlist_domain_string is null then set as empty string
        if allowlist_domain_string is None:
            allowlist_domain_string = ""
        cname_string = self.node.try_get_context("cname")
        certificate_arn_string = self.node.try_get_context("certificate_arn")

        #set boolean has_cname_condition for if cname_string is not null and not empty
        has_cname_condition = False
        if cname_string is not None and cname_string != "":
            has_cname_condition = True
        has_certificate_arn_condition = False
        if certificate_arn_string is not None and certificate_arn_string != "":
            has_certificate_arn_condition = True
        
        

        # Create a Lambda layer for the Boto3 library
        boto3_layer = _lambda.LayerVersion(
            self, "Boto3Layer",
            code=_lambda.Code.from_asset("lambda_functions/python_layer"),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_12],
            compatible_architectures=[_lambda.Architecture.ARM_64],
            description="Boto3 library layer"
        )
        # Add powertools layer
        powertools_layer = _lambda.LayerVersion.from_layer_version_arn(self, "PowertoolsLayer",f"arn:aws:lambda:{self.region}:017000801446:layer:AWSLambdaPowertoolsPythonV2-Arm64:69")
        lambda_insights_layer = _lambda.LayerVersion.from_layer_version_arn(self, "LambdaInsightsLayer",f"arn:aws:lambda:{self.region}:580247275435:layer:LambdaInsightsExtension-Arm64:20") 

        # Create the S3 bucket for website content
        website_content_bucket = s3.Bucket(self, "GenAiChatbotS3BucketContent",
                           removal_policy=RemovalPolicy.DESTROY,
                           auto_delete_objects=True,
                           enforce_ssl=True)

        # Create the S3 bucket for conversation history
        conversation_history_bucket = s3.Bucket(self, "ConversationHistoryBucket",
                           removal_policy=RemovalPolicy.DESTROY,
                           auto_delete_objects=True,
                           enforce_ssl=True)

        # Create the S3 bucket for agent schemas
        schemabucket = s3.Bucket(self, "GenAiChatbotS3BucketAgentSchemas",
                           removal_policy=RemovalPolicy.DESTROY,
                           auto_delete_objects=True,
                           enforce_ssl=True)
        # Add this after the existing S3 bucket definitions
        image_bucket = s3.Bucket(self, "GeneratedImagesBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            enforce_ssl=True,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="TransitionAndDelete",
                    enabled=True,
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=Duration.days(30)
                        )
                    ],
                    expiration=Duration.days(60)
                )
            ]
        )

        # Deploy agent schemas to the S3 bucket
        s3deploy.BucketDeployment(self, "s3FilesDeploymentSchema",
                            sources=[s3deploy.Source.asset("./bedrock_agent_schemas")],
                            destination_bucket=schemabucket,
                            prune=True)

        #ORIGINAL  cloud_front_distribution_props={
        #                    'comment': 'GenAiChatbot Website',
        #                    'defaultBehavior': {
        #                        'cachePolicy': cloudfront.CachePolicy.CACHING_DISABLED
        #                    },
        #                }
        cloud_front_distribution_props = {
            'comment': 'GenAiChatbot Website',
            'defaultBehavior': {
                'viewerProtocolPolicy': cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                'cachePolicy': cloudfront.CachePolicy.CACHING_DISABLED,
                'originRequestPolicy': cloudfront.OriginRequestPolicy.CORS_S3_ORIGIN,
            },
        }
        if has_cname_condition:
            #get hosted zone
            hosted_zone = PublicHostedZone.from_lookup(self, "HostedZone", domain_name=cname_string)
            #if hosted zone was found:
            if hosted_zone is not None:
                #continue
                print('TODO: continue')
            else:
                print('TODO: error')
                #error
                
            cloud_front_distribution_props['domainNames'] = [cname_string]
            if has_certificate_arn_condition:
                print("has_certificate_arn_condition: "+certificate_arn_string)
                # cloud_front_distribution_props['certificate'] = acm.Certificate.from_certificate_arn(self, "Certificate", certificate_arn_string)
            else:
                print("Not has_certificate_arn_condition!")
                # cloud_front_distribution_props['certificate'] = acm.Certificate(self, "Certificate", domain_name=cname_string)
        
        

        # Create a CloudFront distribution for the website content S3 bucket
        cloudfront_to_s3 = CloudFrontToS3(self, 'CloudfrontDist',
                       existing_bucket_obj=website_content_bucket,
                       insert_http_security_headers=False,
                       cloud_front_distribution_props=cloud_front_distribution_props
                       )
        cloudfront_distribution = cloudfront_to_s3.cloud_front_web_distribution

        oai = cloudfront.OriginAccessIdentity(self, "ImageBucketOAI")

        # Add the image bucket as a new origin
        image_origin = origins.S3Origin(
            bucket=image_bucket,
            origin_access_identity=oai
        )

        # Add a new behavior for the /images/* path
        cloudfront_distribution.add_behavior(
            path_pattern="/images/*",
            origin=image_origin,
            viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
            origin_request_policy=cloudfront.OriginRequestPolicy.CORS_S3_ORIGIN,
        )
        image_bucket.grant_read(oai)    
        
        

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
        
        # Create the Lambda function for image generation
        image_generation_function = _lambda.Function(self, "ImageGenerationFunction",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="genai_bedrock_image_fn.lambda_handler",
            code=_lambda.Code.from_asset("lambda_functions/genai_bedrock_image_fn/"),
            timeout=Duration.seconds(300),
            architecture=_lambda.Architecture.ARM_64,
            tracing=_lambda.Tracing.ACTIVE,
            memory_size=1024,
            layers=[boto3_layer, powertools_layer, lambda_insights_layer],
            log_retention=logs.RetentionDays.FIVE_DAYS,
            environment={
                "WEBSOCKET_API_ENDPOINT": websocket_api.api_endpoint,
                "S3_IMAGE_BUCKET_NAME": image_bucket.bucket_name,
                "CLOUDFRONT_DOMAIN": cloudfront_distribution.distribution_domain_name,
            },
        )
        image_generation_function.removal_policy = RemovalPolicy.DESTROY
        image_bucket.grant_read_write(image_generation_function)
        image_generation_function.role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonBedrockFullAccess"))
        image_generation_function.role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonAPIGatewayInvokeFullAccess"))

        config_function = _lambda.Function(
            self, "genai_bedrock_config_fn",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="genai_bedrock_config_fn.lambda_handler",
            code=_lambda.Code.from_asset("./lambda_functions/genai_bedrock_config_fn/"),
            timeout=Duration.seconds(30),
            architecture=_lambda.Architecture.ARM_64,
            tracing=_lambda.Tracing.ACTIVE,
            memory_size=1024,
            layers=[boto3_layer, powertools_layer,lambda_insights_layer],
            log_retention=logs.RetentionDays.FIVE_DAYS,
            environment={
                "DYNAMODB_TABLE": dynamodb_configurations_table.table_name,
                "ALLOWLIST_DOMAIN": allowlist_domain_string,
                "REGION": self.region,
                "POWERTOOLS_SERVICE_NAME":"CONFIG_SERVICE",
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
                                     handler="genai_bedrock_agents_client_fn.lambda_handler",
                                     code=_lambda.Code.from_asset("./lambda_functions/genai_bedrock_agents_client_fn/"),
                                     timeout=Duration.seconds(900),
                                     architecture=_lambda.Architecture.ARM_64,
                                     tracing=_lambda.Tracing.ACTIVE,
                                     memory_size=1024,
                                     layers=[boto3_layer, powertools_layer,lambda_insights_layer],
                                     log_retention=logs.RetentionDays.FIVE_DAYS,
                                     environment={
                                          "DYNAMODB_TABLE": dynamodb_configurations_table.table_name,
                                          "WEBSOCKET_API_ENDPOINT": websocket_api_endpoint,
                                          "POWERTOOLS_SERVICE_NAME":"AGENTS_CLIENT_SERVICE",
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
                                     handler="genai_bedrock_agents_fn.lambda_handler",
                                     code=_lambda.Code.from_asset("./lambda_functions/genai_bedrock_agents_fn/"),
                                     timeout=Duration.seconds(120),
                                     architecture=_lambda.Architecture.ARM_64,
                                     tracing=_lambda.Tracing.ACTIVE,
                                     memory_size=1024,
                                     layers=[boto3_layer, powertools_layer,lambda_insights_layer],
                                     log_retention=logs.RetentionDays.FIVE_DAYS,
                                     environment={
                                          "DYNAMODB_TABLE": dynamodb_incidents_table.table_name,
                                          "POWERTOOLS_SERVICE_NAME":"AGENTS_SERVICE",
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
                                     handler="genai_bedrock_async_fn.lambda_handler",
                                     code=_lambda.Code.from_asset("./lambda_functions/genai_bedrock_async_fn/"),
                                     timeout=Duration.seconds(900),
                                     architecture=_lambda.Architecture.ARM_64,
                                     tracing=_lambda.Tracing.ACTIVE,
                                     memory_size=1024,
                                     layers=[boto3_layer, powertools_layer,lambda_insights_layer],
                                     log_retention=logs.RetentionDays.FIVE_DAYS,                                     
                                     environment={
                                          "DYNAMODB_TABLE": dynamodb_conversations_table.table_name,
                                          "CONVERSATION_HISTORY_BUCKET": conversation_history_bucket.bucket_name,
                                          "WEBSOCKET_API_ENDPOINT": websocket_api_endpoint,
                                          "DYNAMODB_TABLE_CONFIG": dynamodb_configurations_table.table_name,
                                          "DYNAMODB_TABLE_USAGE": dynamodb_bedrock_usage_table.table_name,
                                          "REGION": self.region,
                                          "POWERTOOLS_SERVICE_NAME":"BEDROCK_ASYNC_SERVICE",
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
        lambda_router_fn = _lambda.Function(self, "genai_bedrock_router_fn",
                                     runtime=_lambda.Runtime.PYTHON_3_12,
                                     handler="genai_bedrock_fn.lambda_handler",
                                     code=_lambda.Code.from_asset("./lambda_functions/genai_bedrock_fn/"),
                                     timeout=Duration.seconds(20),
                                     architecture=_lambda.Architecture.ARM_64,
                                     tracing=_lambda.Tracing.ACTIVE,
                                     memory_size=1024,
                                     layers=[boto3_layer, powertools_layer,lambda_insights_layer],
                                     log_retention=logs.RetentionDays.FIVE_DAYS,
                                     environment={
                                          "USER_POOL_ID": user_pool.user_pool_id,
                                          "REGION": self.region,
                                          "AGENTS_FUNCTION_NAME": agents_client_function.function_name,
                                          "BEDROCK_FUNCTION_NAME": lambda_fn_async.function_name,
                                          "ALLOWLIST_DOMAIN": allowlist_domain_string,
                                          "IMAGE_GENERATION_FUNCTION_NAME": image_generation_function.function_name,
                                          "POWERTOOLS_SERVICE_NAME":"BEDROCK_ROUTER",
                                        }
                                     )
        lambda_router_fn.removal_policy = RemovalPolicy.DESTROY
        
        dynamodb_conversations_table.grant_full_access(lambda_router_fn)
        lambda_fn_async.grant_invoke(lambda_router_fn)
        agents_client_function.grant_invoke(lambda_router_fn)
        image_generation_function.grant_invoke(lambda_router_fn)
        dynamodb_incidents_table.grant_full_access(agents_client_function)

        # Create a Lambda integration for the "genai_bedrock_fn" Lambda
        bedrock_fn_integration = apigwv2_integrations.WebSocketLambdaIntegration(
            "BedrockFnIntegration", lambda_router_fn
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
                            destination_bucket=website_content_bucket,
                            prune=True)


        # Export CloudFormation outputs
        CfnOutput(self, "AWSChatBotURL", value='https://'+cloudfront_to_s3.cloud_front_web_distribution.domain_name) 
        CfnOutput(self, "region", value=self.region) 
        CfnOutput(self, "user_pool_id", value=user_pool.user_pool_id) 
        CfnOutput(self, "user_pool_client_id", value=user_pool_client.user_pool_client_id) 
        CfnOutput(self, "websocket_api_endpoint", value=websocket_api_endpoint+'/ws') 