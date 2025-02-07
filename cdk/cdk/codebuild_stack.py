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
    def __init__(self, scope: Construct, id: str, custom_model_s3_bucket_name: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        deploy_deep_seek = False
        deploy_deep_seek_input = self.node.try_get_context("deployDeepSeek")
        if deploy_deep_seek_input is not None and deploy_deep_seek_input != "":
            if "y" in deploy_deep_seek_input.lower() or "true" in deploy_deep_seek_input.lower():
                deploy_deep_seek = True
                
        if deploy_deep_seek:
            # IAM Role for CodeBuild
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


            # Grant permissions to access the S3 bucket
            s3.Bucket.from_bucket_name(self, "GenAIChatBotCustomModelImportTargetBucket", custom_model_s3_bucket_name).grant_read_write(codebuild_role)
            
            # Define the build spec as a dictionary
            build_spec_dict = {
                "version": "0.2",
                "phases": {
                    "build": {
                        "commands": [
                            # Group commands in a YAML block scalar
                            f"""|
                            # Define variables
                            S3_BUCKET="{custom_model_s3_bucket_name}"
                            S3_KEY="DeepSeek-R1-Distill-Llama-8B"
                            
                            # Check if the folder exists in the S3 bucket
                            if aws s3 ls "s3://$S3_BUCKET/$S3_KEY" > /dev/null 2>&1; then
                            echo "Folder $S3_KEY already exists in bucket $S3_BUCKET. Exiting successfully."
                            aws codebuild stop-build --id $CODEBUILD_BUILD_ID
                            exit 0
                            fi

                            # Proceed with the rest of the commands if the folder does not exist
                            sudo dnf update -y
                            sudo dnf install git-lfs -y
                            git lfs install
                            git clone --filter=blob:none --no-checkout https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Llama-8B
                            cd DeepSeek-R1-Distill-Llama-8B
                            git checkout main
                            git lfs pull
                            cd ..
                            aws s3 sync --exclude '.git*' DeepSeek-R1-Distill-Llama-8B "s3://$S3_BUCKET/$S3_KEY/"
                            """
                        ]
                    }
                }
            }
    
            # Create CodeBuild Project
            codebuild_project = codebuild.Project(
                self, "GenAIChatBotCustomModelImportCodeBuildProject",
                role=codebuild_role,
                build_spec=codebuild.BuildSpec.from_asset("cdk/buildspec.yml"),
                environment=codebuild.BuildEnvironment(
                    build_image=codebuild.LinuxBuildImage.STANDARD_7_0,
                    compute_type=codebuild.ComputeType.LARGE,
                    privileged=True,
                    environment_variables={
                        "S3_BUCKET": codebuild.BuildEnvironmentVariable(value=custom_model_s3_bucket_name)
                    }
                )
            )
            scheduler_group_name = "ChatbotSchedulerOneTimeGroup"
            scheduler_group = scheduler.Group(self, scheduler_group_name,
                group_name=scheduler_group_name,
                removal_policy=RemovalPolicy.DESTROY,
            )
            # one time schedule to execute in 2 minutes
            deep_seek_deploy_schedule = scheduler.Schedule(
                self, "DeepSeekDeploySchedule",
                target=scheduler_targets.CodeBuildStartBuild(
                    codebuild_project,
                    role=codebuild_role,
                    retry_attempts=0,
                ),
                schedule=scheduler.ScheduleExpression.at(
                    (datetime.now(timezone.utc) + timedelta(minutes=2))
                ),
                description="One-time schedule to trigger CodeBuild project immediately",
                enabled=True,
                group=scheduler_group
            )
            codebuild_role.add_to_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "codebuild:StartBuild","codebuild:StopBuild"
                    ],
                    resources=[codebuild_project.project_arn]
                )
            )
