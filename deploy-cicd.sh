#!/bin/bash

# GitHub repository URL
REPO_URL="https://github.com/seandkendall/genai-bedrock-chatbot"

# Project names
CODEBUILD_PROJECT_NAME="genai-bedrock-chatbot-build"
CODEDEPLOY_APP_NAME="genai-bedrock-chatbot-app"
CODEDEPLOY_DEPLOYMENT_GROUP_NAME="genai-bedrock-chatbot-deployment-group"

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -d) delete_flag=true; shift;;
        --branch) branch_name="$2"; shift 2;;
        --allowlist) allowlist_pattern="$2"; shift 2;;
        *) echo "Unknown argument: $1"; shift;;
    esac
done

# Function to delete existing resources
delete_resources() {
    echo "Deleting existing resources..."

    # Delete CodeBuild project
    echo "Deleting CodeBuild Project CodeBuild..."
    aws codebuild delete-project --name $CODEBUILD_PROJECT_NAME

    # Delete CodeDeploy application and deployment group
    echo "Deleting Deployment Group CodeDeploy..."
    aws deploy delete-deployment-group --application-name $CODEDEPLOY_APP_NAME --deployment-group-name $CODEDEPLOY_DEPLOYMENT_GROUP_NAME
    echo "Deleting Application CodeDeploy..."
    aws deploy delete-application --application-name $CODEDEPLOY_APP_NAME

    # Delete associated IAM roles
    echo "Deleting Role Policy CodeBuild..."
    aws iam delete-role-policy --role-name codebuild-$CODEBUILD_PROJECT_NAME-service-role --policy-name codebuild-base-policy
    echo "Deleting Role CodeBuild..."
    aws iam delete-role --role-name codebuild-$CODEBUILD_PROJECT_NAME-service-role
    
    echo "Detaching Role Policy CodeDeploy..."
    aws iam detach-role-policy --role-name codedeploy-$CODEDEPLOY_APP_NAME-service-role --policy-arn arn:aws:iam::aws:policy/service-role/AWSCodeDeployRole
    echo "Deleting Role CodeDeploy..."
    aws iam delete-role --role-name codedeploy-$CODEDEPLOY_APP_NAME-service-role

    echo "Existing resources deleted."
}

# Check for delete flag
if [ "$delete_flag" = true ]; then
    delete_resources
fi

# Function to create or update IAM role
create_or_update_role() {
    local role_name=$1
    local assume_role_policy=$2
    local policy_name=$3
    local policy_document=$4

    # Check if the role exists
    if aws iam get-role --role-name "$role_name" 2>/dev/null; then
        echo "Updating existing role: $role_name"
        aws iam update-assume-role-policy --role-name "$role_name" --policy-document "$assume_role_policy"
        aws iam put-role-policy --role-name "$role_name" --policy-name "$policy_name" --policy-document "$policy_document"
    else
        echo "Creating new role: $role_name"
        aws iam create-role --role-name "$role_name" --assume-role-policy-document "$assume_role_policy"
        aws iam put-role-policy --role-name "$role_name" --policy-name "$policy_name" --policy-document "$policy_document"
    fi
}

# Create or update IAM roles
echo "Creating or updating IAM roles..."

# CodeBuild role
create_or_update_role \
    "codebuild-$CODEBUILD_PROJECT_NAME-service-role" \
    '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"codebuild.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
    "codebuild-base-policy" \
    '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Resource":"*","Action":["apigateway:*","lambda:*","logs:*","s3:*","ec2:*","iam:*","codebuild:*","cloudformation:*","cognito-idp:*","acm:*"]}]}'

# CodeDeploy role
create_or_update_role \
    "codedeploy-$CODEDEPLOY_APP_NAME-service-role" \
    '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"codedeploy.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
    "codedeploy-base-policy" \
    '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Resource":"*","Action":["s3:*","ec2:*","iam:*","cloudformation:*"]}]}'

# Create CodeBuild project
echo "Creating CodeBuild project..."
source_config="{\"type\": \"GITHUB\", \"location\": \"$REPO_URL\""
if [ -n "$branch_name" ]; then
    source_config="$source_config, \"gitCloneDepth\": 1, \"buildspec\": \"version: 0.2\nphases:\n  install:\n    runtime-versions:\n      python: 3.8\n      nodejs: 12\n    commands:\n      - python -m pip install --upgrade pip\n      - npm install -g aws-cdk\n      - yum update -y\n      - yum install -y jq\n      - pip install --upgrade awscli\n  pre_build:\n    commands:\n      - git checkout $branch_name\n      - cd cdk\n      - python3 -m venv .venv\n      - source .venv/bin/activate\n      - pip install --upgrade pip\n      - pip install -r requirements.txt\n  build:\n    commands:\n      - cd ..\n      - chmod +x deploy.sh\n      - ./deploy.sh --headless --allowlist @amazon.com,@amazon.\""
else
    source_config="$source_config, \"buildspec\": \"version: 0.2\nphases:\n  install:\n    runtime-versions:\n      python: 3.8\n      nodejs: 12\n    commands:\n      - python -m pip install --upgrade pip\n      - npm install -g aws-cdk\n      - yum update -y\n      - yum install -y jq\n      - pip install --upgrade awscli\n  pre_build:\n    commands:\n      - cd cdk\n      - python3 -m venv .venv\n      - source .venv/bin/activate\n      - pip install --upgrade pip\n      - pip install -r requirements.txt\n  build:\n    commands:\n      - cd ..\n      - chmod +x deploy.sh\n      - ./deploy.sh --headless --allowlist @amazon.com,@amazon.\""
fi
source_config="$source_config}"

aws codebuild create-project --name $CODEBUILD_PROJECT_NAME \
    --source "$source_config" \
    --artifacts "{\"type\": \"NO_ARTIFACTS\"}" \
    --environment "{\"type\": \"LINUX_CONTAINER\", \"image\": \"aws/codebuild/amazonlinux2-x86_64-standard:3.0\", \"computeType\": \"BUILD_GENERAL1_SMALL\"}" \
    --service-role "arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/codebuild-$CODEBUILD_PROJECT_NAME-service-role"

# Create CodeDeploy application
echo "Creating CodeDeploy application..."
aws deploy create-application --application-name $CODEDEPLOY_APP_NAME

# Create CodeDeploy deployment group
echo "Creating CodeDeploy deployment group..."
aws deploy create-deployment-group \
    --application-name $CODEDEPLOY_APP_NAME \
    --deployment-group-name $CODEDEPLOY_DEPLOYMENT_GROUP_NAME \
    --service-role-arn "arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/codedeploy-$CODEDEPLOY_APP_NAME-service-role"

echo "Deployment resources created successfully."