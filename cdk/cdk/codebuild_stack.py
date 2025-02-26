from aws_cdk import (
    Stack,
    aws_codebuild as codebuild,
    aws_iam as iam,
    aws_s3 as s3,
    aws_scheduler_alpha as scheduler,
    aws_scheduler_targets_alpha as scheduler_targets,
    CfnOutput,Duration,RemovalPolicy
)
from constructs import Construct
from datetime import datetime, timedelta, timezone


class CodeBuildStack(Stack):
    def __init__(self, scope: Construct, id: str, custom_model_s3_bucket_name: str,imported_models: str, project: str,aws_application: str,**kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        deploy_deep_seek = False
        deploy_deep_seek_input = self.node.try_get_context("deployDeepSeek")
        if deploy_deep_seek_input is not None and deploy_deep_seek_input != "":
            if "y" in deploy_deep_seek_input.lower() or "true" in deploy_deep_seek_input.lower():
                deploy_deep_seek = True
                
        if deploy_deep_seek:
            # Create the trust policy statement
            bedrock_import_model_role_trust_policy_statement = iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["sts:AssumeRole"],
                principals=[iam.ServicePrincipal("bedrock.amazonaws.com")],
                conditions={
                    "StringEquals": {"aws:SourceAccount": self.account},
                    "ArnEquals": {
                        "aws:SourceArn": f"arn:aws:bedrock:{self.region}:{self.account}:model-import-job/*"
                    },
                },
            )

            # Create the inline policy
            bedrock_import_model_role_inline_policy = iam.PolicyDocument()
            bedrock_import_model_role_inline_policy.add_statements(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["s3:*"],
                    resources=[
                        f"arn:aws:s3:::{custom_model_s3_bucket_name}",
                        f"arn:aws:s3:::{custom_model_s3_bucket_name}/*",
                    ],
                    conditions={
                        "StringEquals": {"aws:ResourceAccount": self.account}
                    },
                )
            )

            # Create the IAM Role
            bedrock_import_model_role = iam.Role(
                self,
                "BedrockImportModelRole",
                assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
                inline_policies={"InlinePolicy": bedrock_import_model_role_inline_policy},
                max_session_duration=Duration.hours(3),
            )

            # Attach the trust policy statement to the assume role policy
            if bedrock_import_model_role.assume_role_policy:
                bedrock_import_model_role.assume_role_policy.add_statements(bedrock_import_model_role_trust_policy_statement)

            codebuild_role = iam.Role(
                self, "GenAIChatBotCustomModelImportCodeBuildRole",
                assumed_by=iam.ServicePrincipal("codebuild.amazonaws.com")
            )
            codebuild_role.assume_role_policy.add_statements(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    principals=[iam.ServicePrincipal("scheduler.amazonaws.com")],
                    actions=["sts:AssumeRole"]
                )
            )


            # Grant codebuild_role permissions to access the S3 bucket with bucketname {custom_model_s3_bucket_name}
            codebuild_role.add_to_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["s3:*"],
                    resources=[
                        f"arn:aws:s3:::{custom_model_s3_bucket_name}",
                        f"arn:aws:s3:::{custom_model_s3_bucket_name}/*",
                    ],
                )
            )
            

            # Create CodeBuild Project
            codebuild_project_arns = []
            scheduler_group_name = f"ChatbotSchedulerOneTimeGroup"
            scheduler_group = scheduler.Group(self, scheduler_group_name,
                    group_name=scheduler_group_name,
                    removal_policy=RemovalPolicy.DESTROY,
                )
            # Compute type lookup: https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_codebuild/ComputeType.html
            deepseek_model_8b = {'model_url': "https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Llama-8B", 'compute_type': codebuild.ComputeType.LARGE}
            deepseek_model_70b = {'model_url': "https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Llama-70B", 'compute_type': codebuild.ComputeType.X2_LARGE}
            deepseek_model_r1 = {'model_url': "https://huggingface.co/deepseek-ai/DeepSeek-R1", 'compute_type': codebuild.ComputeType.X2_LARGE}
            code_llama_instruct_hf_model_7b = {'model_url': "https://huggingface.co/codellama/CodeLlama-7b-Instruct-hf", 'compute_type': codebuild.ComputeType.LARGE}
            models = [deepseek_model_8b, deepseek_model_70b]
            for current_model in models:
                model_name = current_model['model_url'].split("/")[-1]
                codebuild_project = codebuild.Project(
                    self, f"GenAIChatBotCMICodeBuildProject-{model_name}",
                    role=codebuild_role,
                    timeout=Duration.hours(3),
                    description=f"GenAI Chatbot CodeBuild Project for {model_name}",
                    build_spec=codebuild.BuildSpec.from_asset("cdk/buildspec.yml"),
                    environment=codebuild.BuildEnvironment(
                        build_image=codebuild.LinuxBuildImage.from_code_build_image_id('aws/codebuild/amazonlinux-x86_64-standard:5.0'),
                        compute_type=current_model['compute_type'],
                        privileged=True,
                        environment_variables={
                            "S3_BUCKET": codebuild.BuildEnvironmentVariable(value=custom_model_s3_bucket_name),
                            "MODEL_URL": codebuild.BuildEnvironmentVariable(value=current_model['model_url']),
                            "MODEL_IDENTIFIER": codebuild.BuildEnvironmentVariable(value=('/'.join(current_model['model_url'].split('/')[3:]))),
                            "ROLE_ARN": codebuild.BuildEnvironmentVariable(value=codebuild_role.role_arn),
                            "MODEL_IMPORT_ROLE_ARN": codebuild.BuildEnvironmentVariable(value=bedrock_import_model_role.role_arn),
                            "PROJECT": codebuild.BuildEnvironmentVariable(value=project),
                            "AWSAPPLICATION": codebuild.BuildEnvironmentVariable(value=aws_application)
                        }
                    )
                )
                codebuild_project_arns.append(codebuild_project.project_arn)
                # one time schedule to execute in 2 minutes
                deep_seek_deploy_schedule = scheduler.Schedule(
                    self, f"CustomModelImportDeploySchedule-{model_name}",
                    target=scheduler_targets.CodeBuildStartBuild(
                        codebuild_project,
                        role=codebuild_role,
                        retry_attempts=0,
                    ),
                    schedule=scheduler.ScheduleExpression.at(
                        (datetime.now(timezone.utc) + timedelta(minutes=1))
                    ),
                    description="One-time schedule to trigger CodeBuild project",
                    enabled=model_name not in imported_models,
                    group=scheduler_group
                )
            codebuild_role.add_to_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "codebuild:StartBuild","codebuild:StopBuild"
                    ],
                    resources=codebuild_project_arns
                )
            )
            codebuild_role.add_to_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "bedrock:CreateModelImportJob","iam:PassRole","bedrock:TagResource"
                    ],
                    resources=["*"]
                )
            )