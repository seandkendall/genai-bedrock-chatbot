#!/bin/bash

# Define default values
REPO_URL="https://github.com/seandkendall/genai-bedrock-chatbot.git"
BRANCH="main"
AWS_PROFILE="default"
PROJECT_NAME="genai-bedrock-chatbot"

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -b|--branch)
            BRANCH="$2"
            shift 2
            ;;
        --profile)
            AWS_PROFILE="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1"
            shift
            ;;
    esac
done

# Set AWS credentials and region
export AWS_PROFILE="$AWS_PROFILE"
AWS_REGION=$(aws configure get region)

# Check if the projects already exist
CODEBUILD_PROJECT=$(aws codebuild list-projects --query 'projects[?contains(name, `'$PROJECT_NAME'-build`)]' --output text --region "$AWS_REGION")
CODEDEPLOY_PROJECT=$(aws deploy list-deployments --compute-platform ECS --query 'deployments[?contains(deploymentName, `'$PROJECT_NAME'-deploy`)]' --output text --region "$AWS_REGION")

# Create or update the CodeBuild project
if [ -z "$CODEBUILD_PROJECT" ]; then
    echo "Creating CodeBuild project..."
    aws codebuild create-project --name "$PROJECT_NAME-build" --source '{"type":"GITHUB","location":"'$REPO_URL'","gitCloneDepth":1,"buildspec":"buildspec.yml","auth":{"type":"OAUTH"}}' --artifacts '{"type":"NO_ARTIFACTS"}' --environment '{"type":"LINUX_CONTAINER","image":"aws/codebuild/amazonlinux2-x86_64-standard:3.0","computeType":"BUILD_GENERAL1_SMALL"}' --service-role "arn:aws:iam::${AWS_ACCOUNT_ID}:role/service-role/codebuild-${PROJECT_NAME}-service-role" --region "$AWS_REGION"
else
    echo "Updating CodeBuild project..."
    aws codebuild update-project --name "$PROJECT_NAME-build" --source '{"type":"GITHUB","location":"'$REPO_URL'","gitCloneDepth":1,"buildspec":"buildspec.yml","auth":{"type":"OAUTH"}}' --region "$AWS_REGION"
fi

# Create or update the CodeDeploy project
if [ -z "$CODEDEPLOY_PROJECT" ]; then
    echo "Creating CodeDeploy project..."
    aws deploy create-deployment --application-name "$PROJECT_NAME-app" --deployment-config-name CodeDeployDefault.ECSAllAtOnce --deployment-group-name "$PROJECT_NAME-deployment-group" --description "Deploy application revision" --ecs-services "arn:aws:ecs:$AWS_REGION:$AWS_ACCOUNT_ID:service/$PROJECT_NAME-service" --ignore-application-stop-failures --region "$AWS_REGION"
else
    echo "Updating CodeDeploy project..."
    aws deploy update-deployment-group --application-name "$PROJECT_NAME-app" --current-deployment-group-name "$PROJECT_NAME-deployment-group" --deployment-config-name CodeDeployDefault.ECSAllAtOnce --ecs-services "arn:aws:ecs:$AWS_REGION:$AWS_ACCOUNT_ID:service/$PROJECT_NAME-service" --region "$AWS_REGION"
fi

# Create or update the CodePipeline
echo "Creating or updating CodePipeline..."
aws codepipeline create-pipeline --pipeline '{"name":"'$PROJECT_NAME'-pipeline","roleArn":"arn:aws:iam::${AWS_ACCOUNT_ID}:role/AWS-CodePipeline-Service","stages":[{"name":"Source","actions":[{"name":"Source","actionTypeId":{"category":"Source","owner":"AWS","version":"1","provider":"CodeCommit"},"outputArtifacts":[{"name":"SourceArtifact"}],"configuration":{"BranchName":"'$BRANCH'","PollForSourceChanges":"false","RepositoryName":"'$REPO_URL'"},"runOrder":1}]},{"name":"Build","actions":[{"name":"Build","actionTypeId":{"category":"Build","owner":"AWS","version":"1","provider":"CodeBuild"},"inputArtifacts":[{"name":"SourceArtifact"}],"outputArtifacts":[{"name":"BuildArtifact"}],"configuration":{"ProjectName":"'$PROJECT_NAME'-build"},"runOrder":1}]},{"name":"Deploy","actions":[{"name":"Deploy","actionTypeId":{"category":"Deploy","owner":"AWS","version":"1","provider":"ECS"},"inputArtifacts":[{"name":"BuildArtifact"}],"configuration":{"ApplicationName":"'$PROJECT_NAME'-app","DeploymentGroupName":"'$PROJECT_NAME'-deployment-group","TaskDefinitionTemplateUri":"","AppSpecTemplateUri":""},"runOrder":1}]}],"artifactStore":{"type":"S3","location":"codepipeline-${AWS_REGION}-${AWS_ACCOUNT_ID}","encryptionKey":{"type":"KMS","id":"arn:aws:kms:${AWS_REGION}:${AWS_ACCOUNT_ID}:alias/aws/s3"}},"webhookAuthenticationType":"GITHUB_HMAC","webhookAuthenticationConfiguration":{"SecretToken":"not_set"}}' --region "$AWS_REGION"

echo "CodePipeline created or updated successfully!"