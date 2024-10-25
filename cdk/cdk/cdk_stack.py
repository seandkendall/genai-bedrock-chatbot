from aws_cdk import ( # type: ignore
    Stack, Duration, CfnOutput,
    aws_s3 as s3,
    aws_lambda as _lambda,
    aws_lambda_python_alpha as lambda_python,
    aws_s3_deployment as s3deploy,
    aws_cloudfront as cloudfront,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    aws_logs as logs,
    aws_apigatewayv2 as apigwv2,
    aws_apigateway as apigw,
    aws_apigatewayv2_integrations as apigwv2_integrations,
    aws_cognito as cognito,
    aws_cloudfront_origins as origins,
    RemovalPolicy,
    aws_certificatemanager as acm,
    aws_events as events,
    aws_scheduler_alpha as scheduler,
    aws_scheduler_targets_alpha as scheduler_targets,
)
from constructs import Construct
from datetime import datetime, timezone
from aws_solutions_constructs.aws_cloudfront_s3 import CloudFrontToS3 # type: ignore
from .constructs.user_pool_user import UserPoolUser
import json
import os
from aws_cdk.aws_route53 import PublicHostedZone
from .cdk_constants import lambda_insights_layers






class ChatbotWebsiteStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)    
        region = os.environ.get('CDK_DEFAULT_REGION')
        scheduler_group_name = "ChatbotSchedulerGroup"
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
        boto3_layer = lambda_python.PythonLayerVersion(
            self, "Boto3Layer",
            entry="lambda_functions/python_layer2",
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_12],
            compatible_architectures=[_lambda.Architecture.ARM_64],
            description="Boto3 library with  PyJWT django pytz requests used for arm64/3.12"
        )
        commons_layer = _lambda.LayerVersion(
            self, "KendallChatCommons",
            code=_lambda.Code.from_asset("lambda_functions/commons_layer"),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_12],
            compatible_architectures=[_lambda.Architecture.ARM_64],
            description="KendallChat Commons: Making all the code more simple and reusable"
        )
        
        # ARN Lookup: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Lambda-Insights-extension-versionsARM.html
        lambda_insights_layer = _lambda.LayerVersion.from_layer_version_arn(
            self,
            "LambdaInsightsLayer",
            lambda_insights_layers[region]
        )



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
        
        attachment_bucket = s3.Bucket(self, "AttachmentBucket",
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
            ])
        

        # Deploy agent schemas to the S3 bucket
        s3deploy.BucketDeployment(self, "s3FilesDeploymentSchema",
                            sources=[s3deploy.Source.asset("./bedrock_agent_schemas")],
                            destination_bucket=schemabucket,
                            prune=True)

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
        cloudfront_distribution_domain_name = cloudfront_distribution.domain_name
        
        # add cors to attachment_bucket
        attachment_bucket.add_cors_rule(
            allowed_methods=[s3.HttpMethods.GET, s3.HttpMethods.POST, s3.HttpMethods.PUT],
            allowed_origins=["*"],
            allowed_headers=["*"],
            exposed_headers=['ETag'],
            max_age=3600
        )

        # Add the image bucket as a new origin
        image_origin = origins.S3BucketOrigin.with_origin_access_control(image_bucket)

        # Add a new behavior for the /images/* path
        cloudfront_distribution.add_behavior(
            path_pattern="/images/*",
            origin=image_origin,
            viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
            origin_request_policy=cloudfront.OriginRequestPolicy.CORS_S3_ORIGIN,
        )
        
        # Create DynamoDB table for bedrock_usage with a user_id (partition key string), input_tokens (number) and output_tokens(number)
        dynamodb_bedrock_usage_table = dynamodb.Table(self, "bedrock_usage_table",
                                                      partition_key=dynamodb.Attribute(name="user_id", 
                                                                                       type=dynamodb.AttributeType.STRING),
                                                                                       billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
                                                                                       removal_policy=RemovalPolicy.DESTROY, )
        
        dynamodb_conversations_table = dynamodb.Table(self, "conversations_table", 
                                                      partition_key=dynamodb.Attribute(name="session_id", type=dynamodb.AttributeType.STRING),
                                                      billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
                                                      removal_policy=RemovalPolicy.DESTROY,)
        
        dynamodb_incidents_table = dynamodb.Table(self, "incidents_table", 
                                                  partition_key=dynamodb.Attribute(name="incident_id", type=dynamodb.AttributeType.STRING),
                                                  billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
                                                  removal_policy=RemovalPolicy.DESTROY,)

        dynamodb_configurations_table = dynamodb.Table(
            self, "configurations_table",
            partition_key=dynamodb.Attribute(name="user", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="config_type", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY
        )


        # Create a WebSocket API
        websocket_api = apigwv2.WebSocketApi(
            self, "ChatbotWebSocketApi",
            description="WebSocket API for KendallChatbot",
        )
        websocket_api.removal_policy = RemovalPolicy.DESTROY
        websocket_api_endpoint = websocket_api.api_endpoint
        apigwv2.WebSocketStage(self, "mystage",
            web_socket_api=websocket_api,
            stage_name="ws",
            auto_deploy=True
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
            layers=[boto3_layer, commons_layer, lambda_insights_layer],
            log_retention=logs.RetentionDays.FIVE_DAYS,
            environment={
                "WEBSOCKET_API_ENDPOINT": websocket_api_endpoint,
                "S3_IMAGE_BUCKET_NAME": image_bucket.bucket_name,
                "CLOUDFRONT_DOMAIN": cloudfront_distribution.distribution_domain_name,
            },
        )
        image_generation_function.apply_removal_policy(RemovalPolicy.DESTROY)
        websocket_api.grant_manage_connections(image_generation_function)
        image_bucket.grant_read_write(image_generation_function)
        image_generation_function.role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonBedrockFullAccess"))
        image_generation_function.role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonAPIGatewayInvokeFullAccess"))

        config_function = _lambda.Function(
            self, "GenAIBedrockConfigFunction",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="genai_bedrock_config_fn.lambda_handler",
            code=_lambda.Code.from_asset("./lambda_functions/genai_bedrock_config_fn/"),
            timeout=Duration.seconds(30),
            architecture=_lambda.Architecture.ARM_64,
            tracing=_lambda.Tracing.ACTIVE,
            memory_size=1024,
            layers=[boto3_layer, commons_layer, lambda_insights_layer],
            log_retention=logs.RetentionDays.FIVE_DAYS,
            environment={
                "DYNAMODB_CONFIG_TABLE": dynamodb_configurations_table.table_name,
                "ALLOWLIST_DOMAIN": allowlist_domain_string,
                "REGION": region,
                "POWERTOOLS_SERVICE_NAME":"CONFIG_SERVICE",
            }
        )
        config_function.apply_removal_policy(RemovalPolicy.DESTROY)
        config_function_role = config_function.role
        config_function_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AmazonBedrockReadOnly")
        )
        # Add permissions to the Lambda function's role
        config_function.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["bedrock:ListFlows", "bedrock:ListFlowAliases", "bedrock:ListAgents","bedrock:ListAgentAliases", "bedrock:ListKnowledgeBases"],
            resources=["*"]
        ))

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
                                     layers=[boto3_layer, commons_layer, lambda_insights_layer],
                                     log_retention=logs.RetentionDays.FIVE_DAYS,
                                     environment={
                                          "DYNAMODB_TABLE": dynamodb_configurations_table.table_name,
                                          "WEBSOCKET_API_ENDPOINT": websocket_api_endpoint,
                                          "POWERTOOLS_SERVICE_NAME":"AGENTS_CLIENT_SERVICE",
                                     }
                                     )
        agents_client_function.apply_removal_policy(RemovalPolicy.DESTROY)
        websocket_api.grant_manage_connections(agents_client_function)
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
                                     layers=[boto3_layer, commons_layer, lambda_insights_layer],
                                     log_retention=logs.RetentionDays.FIVE_DAYS,
                                     environment={
                                          "DYNAMODB_TABLE": dynamodb_incidents_table.table_name,
                                          "POWERTOOLS_SERVICE_NAME":"AGENTS_SERVICE",
                                     }
                                     )
        agents_function.apply_removal_policy(RemovalPolicy.DESTROY)
        dynamodb_incidents_table.grant_full_access(agents_function)
        agents_function.add_permission(
            "AllowBedrock",
            principal=iam.ServicePrincipal("bedrock.amazonaws.com"),
            source_arn=f"arn:aws:bedrock:{region}:{self.account}:agent/*"
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
                                     layers=[boto3_layer, commons_layer, lambda_insights_layer],
                                     log_retention=logs.RetentionDays.FIVE_DAYS,
                                     environment={
                                          "DYNAMODB_TABLE": dynamodb_conversations_table.table_name,
                                          "CONVERSATION_HISTORY_BUCKET": conversation_history_bucket.bucket_name,
                                          "WEBSOCKET_API_ENDPOINT": websocket_api_endpoint,
                                          "DYNAMODB_TABLE_CONFIG": dynamodb_configurations_table.table_name,
                                          "DYNAMODB_TABLE_USAGE": dynamodb_bedrock_usage_table.table_name,
                                          "REGION": region,
                                          "POWERTOOLS_SERVICE_NAME":"BEDROCK_ASYNC_SERVICE",
                                          "ATTACHMENT_BUCKET": attachment_bucket.bucket_name,
                                          "S3_IMAGE_BUCKET_NAME": image_bucket.bucket_name,
                                     }
                                     )
        lambda_fn_async.apply_removal_policy(RemovalPolicy.DESTROY)
        websocket_api.grant_manage_connections(lambda_fn_async)
        lambda_fn_async.role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonBedrockFullAccess"))
        lambda_fn_async.role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonAPIGatewayInvokeFullAccess"))
        lambda_fn_async.role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSQSFullAccess"))
        dynamodb_conversations_table.grant_full_access(lambda_fn_async)
        dynamodb_configurations_table.grant_full_access(lambda_fn_async)
        conversation_history_bucket.grant_read_write(lambda_fn_async)
        dynamodb_bedrock_usage_table.grant_full_access(lambda_fn_async)
        attachment_bucket.grant_read_write(lambda_fn_async)

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
        # Create the Lambda function for Scanning through LLM Models
        model_scan_function = _lambda.Function(self, "ModelScanFunction",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="genai_bedrock_model_scan_fn.lambda_handler",
            code=_lambda.Code.from_asset("lambda_functions/genai_bedrock_model_scan_fn/"),
            timeout=Duration.seconds(300),
            architecture=_lambda.Architecture.ARM_64 ,
            tracing=_lambda.Tracing.ACTIVE,
            memory_size=1024,
            layers=[boto3_layer, commons_layer, lambda_insights_layer],
            log_retention=logs.RetentionDays.FIVE_DAYS,
            environment={
                "CONFIG_DYNAMODB_TABLE": dynamodb_configurations_table.table_name,
                "USER_POOL_ID": user_pool.user_pool_id,
                "REGION": region,
                "ALLOWLIST_DOMAIN": allowlist_domain_string,
                "WEBSOCKET_API_ENDPOINT": websocket_api_endpoint,
                "POWERTOOLS_SERVICE_NAME":"MODEL_SCAN_SERVICE",
                "POWERTOOLS_METRICS_NAMESPACE": "BedrockChatbotModelScan"
            },
        )
        model_scan_function.apply_removal_policy(RemovalPolicy.DESTROY)
        websocket_api.grant_manage_connections(model_scan_function)
        dynamodb_configurations_table.grant_read_write_data(model_scan_function)
        model_scan_function.role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonBedrockFullAccess"))
        model_scan_function.role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonAPIGatewayInvokeFullAccess"))
        # Add permissions to the Lambda function's role
        model_scan_function.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["bedrock:*"],
            resources=["*"]
        ))
        # Create the "genai_bedrock_fn" Lambda function
        lambda_router_fn = _lambda.Function(self, "GenAIBedrockRouterFunction",
                                     runtime=_lambda.Runtime.PYTHON_3_12,
                                     handler="genai_bedrock_router_fn.lambda_handler",
                                     code=_lambda.Code.from_asset("./lambda_functions/genai_bedrock_router_fn/"),
                                     timeout=Duration.seconds(20),
                                     architecture=_lambda.Architecture.ARM_64,
                                     tracing=_lambda.Tracing.ACTIVE,
                                     memory_size=1024,
                                     layers=[boto3_layer, commons_layer, lambda_insights_layer],
                                     log_retention=logs.RetentionDays.FIVE_DAYS,
                                     environment={
                                          "USER_POOL_ID": user_pool.user_pool_id,
                                          "REGION": region,
                                          "AGENTS_FUNCTION_NAME": agents_client_function.function_name,
                                          "BEDROCK_FUNCTION_NAME": lambda_fn_async.function_name,
                                          "ALLOWLIST_DOMAIN": allowlist_domain_string,
                                          "IMAGE_GENERATION_FUNCTION_NAME": image_generation_function.function_name,
                                          "POWERTOOLS_SERVICE_NAME":"BEDROCK_ROUTER",
                                        }
                                     )
        lambda_router_fn.apply_removal_policy(RemovalPolicy.DESTROY)
        dynamodb_conversations_table.grant_full_access(lambda_router_fn)
        lambda_fn_async.grant_invoke(lambda_router_fn)
        agents_client_function.grant_invoke(lambda_router_fn)
        image_generation_function.grant_invoke(lambda_router_fn)
        dynamodb_incidents_table.grant_full_access(agents_client_function)
        
        presigned_url_function = _lambda.Function(self, "PreSignedUrlFunction",
                                    runtime=_lambda.Runtime.PYTHON_3_12,
                                    handler="genai_bedrock_presigned_fn.lambda_handler",
                                    code=_lambda.Code.from_asset("./lambda_functions/genai_bedrock_presigned_fn"),
                                    timeout=Duration.seconds(20),
                                    architecture=_lambda.Architecture.ARM_64,
                                    tracing=_lambda.Tracing.ACTIVE,
                                    memory_size=1024,
                                    layers=[boto3_layer, commons_layer, lambda_insights_layer],
                                    log_retention=logs.RetentionDays.FIVE_DAYS,
                                    environment={
                                        "ATTACHMENT_BUCKET": attachment_bucket.bucket_name,
                                    },
        )
        presigned_url_function.apply_removal_policy(RemovalPolicy.DESTROY)
        attachment_bucket.grant_read_write(presigned_url_function)
        presigned_url_function.add_to_role_policy(iam.PolicyStatement(
            actions=["s3:PutObject"],
            resources=[attachment_bucket.arn_for_objects("*")],
        ))

        rest_api = apigw.RestApi(self, "ChatbotRestApi",
            description="RESTAPI for KendallChatbot",
            deploy_options=apigw.StageOptions(stage_name="rest"),
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS
            )
        )
        # Add a resource and method for the pre-signed URL endpoint
        presigned_url_resource = rest_api.root.add_resource("get-presigned-url")
        presigned_url_integration = apigw.LambdaIntegration(presigned_url_function)
        # Create a Cognito authorizer
        cognito_authorizer = apigw.CognitoUserPoolsAuthorizer(
            self, "CognitoAuthorizer",
            cognito_user_pools=[user_pool],
            identity_source="method.request.header.Authorization"
        )
        presigned_url_resource.add_method("POST", presigned_url_integration,
                                          authorization_type=apigw.AuthorizationType.COGNITO,
                                          authorizer=cognito_authorizer)
        
        # Add the REST API as an origin to the CloudFront distribution
        rest_api_origin = origins.RestApiOrigin(rest_api, origin_path='/')
        cloudfront_distribution.add_behavior("/rest/*", rest_api_origin,
            allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
            viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.HTTPS_ONLY
        )
        
        # Create a Lambda integrations
        bedrock_fn_integration = apigwv2_integrations.WebSocketLambdaIntegration(
            "BedrockFnIntegration", lambda_router_fn
        )
        config_fn_integration = apigwv2_integrations.WebSocketLambdaIntegration(
            "ConfigFnIntegration", config_function
        )
        model_scan_fn_integration = apigwv2_integrations.WebSocketLambdaIntegration(
            "ModelScanFnIntegration", model_scan_function
        )


        # Add routes and integrations to the WebSocket API
        websocket_api.add_route(
            "config",
            integration=config_fn_integration,
            return_response=True
        )
        websocket_api.add_route(
            "modelscan",
            integration=model_scan_fn_integration,
            return_response=False
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
                callback_urls=[f'https://{cloudfront_distribution_domain_name}'],
                logout_urls=[f'https://{cloudfront_distribution_domain_name}'],
            ),
            user_pool_client_name="ChatbotUserPoolClient",
        )
        user_pool_client.apply_removal_policy(RemovalPolicy.DESTROY)

        # Create a Cognito User Pool Domain
        user_pool_domain = cognito.UserPoolDomain(
            self, "ChatbotUserPoolDomain",
            user_pool=user_pool,
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=cognito_domain_string
            )
        )
        # TODO Customize Cognito Hosted Login
        # cfn_user_pool_uICustomization_attachment = cognito.CfnUserPoolUICustomizationAttachment(self, "CfnUserPoolUICustomizationAttachment",
        #     client_id="ALL",
        #     user_pool_id=user_pool.user_pool_id,
        #     # the properties below are optional
        #     css="css"
        # )

        # Create the EventBridge Scheduler schedule
        scheduler_group = scheduler.Group(self, "ChatbotSchedulerGroup",
            group_name=scheduler_group_name,
            removal_policy=RemovalPolicy.DESTROY,
        )
        module_scan_schedule = scheduler.Schedule(
            self, "ModelScanSchedule",
            schedule=scheduler.ScheduleExpression.rate(Duration.hours(24)),
            target=scheduler_targets.LambdaInvoke(
                model_scan_function,
                retry_attempts=0,
                input=scheduler.ScheduleTargetInput.from_object({"immediate": True})
            ),
            description="Schedule to run the model_scan_function Lambda function",
            enabled=True,
            group=scheduler_group
        )
        # add env variable to lambda function model_scan_function
        config_function.add_environment("SCHEDULE_NAME", module_scan_schedule.schedule_name)
        config_function.add_environment("SCHEDULE_GROUP_NAME", scheduler_group_name)
        # add scheduler:GetSchedule to config_function role to module_scan_schedule custom policy
        #TODO: module_scan_schedule.schedule_arn fails because the construct is in alpha, fix this once its out of alpha 
        config_function_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["scheduler:GetSchedule","scheduler:UpdateSchedule","iam:PassRole"],
            resources=["*"],
        ))
        

        # Export CloudFormation outputs
        CfnOutput(self, "AWSChatBotURL", value=f"https://{cloudfront_distribution_domain_name}")
        CfnOutput(self, "s3bucket", value=website_content_bucket.bucket_name)
        CfnOutput(self, "region", value=region)
        CfnOutput(self, "user_pool_id", value=user_pool.user_pool_id)
        CfnOutput(self, "user_pool_client_id", value=user_pool_client.user_pool_client_id)
        CfnOutput(self, "websocket_api_endpoint", value=websocket_api_endpoint+'/ws')
        CfnOutput(self, "RestApiUrl", value=rest_api.url)

