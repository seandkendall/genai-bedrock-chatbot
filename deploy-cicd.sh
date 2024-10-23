#!/bin/bash
export AWS_PAGER=""
# GitHub repository URL
REPO_URL="https://github.com/seandkendall/genai-bedrock-chatbot"

# Project names
CODEBUILD_PROJECT_NAME="genai-bedrock-chatbot-build"

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
    aws codebuild delete-project --name $CODEBUILD_PROJECT_NAME 
    aws iam delete-role-policy --role-name "codebuild-$CODEBUILD_PROJECT_NAME-service-role" --policy-name "codebuild-base-policy"
    aws iam delete-role --role-name "codebuild-$CODEBUILD_PROJECT_NAME-service-role"
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
        echo "Waiting for role creation..."
        aws iam wait role-exists --role-name "$role_name"
        aws iam put-role-policy --role-name "$role_name" --policy-name "$policy_name" --policy-document "$policy_document" 
        echo "Getting policy 1"
        echo "$(aws iam get-role-policy --role-name "$role_name" --policy-name "$policy_name")"
        sleep 1
        echo "Getting policy 2"
        echo "$(aws iam get-role-policy --role-name "$role_name" --policy-name "$policy_name")"
        sleep 1
        echo "Getting policy 3"
        echo "$(aws iam get-role-policy --role-name "$role_name" --policy-name "$policy_name")"
        sleep 1
        echo "Getting policy 4"
        echo "$(aws iam get-role-policy --role-name "$role_name" --policy-name "$policy_name")"
        sleep 1
        echo "Getting policy 5"
        echo "$(aws iam get-role-policy --role-name "$role_name" --policy-name "$policy_name")"
        sleep 1
    fi
    sleep 2
}

# Create or update IAM roles
echo "Creating or updating IAM roles..."

# CodeBuild role
create_or_update_role \
    "codebuild-$CODEBUILD_PROJECT_NAME-service-role" \
    '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"codebuild.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
    "codebuild-base-policy" \
    '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Resource":"*","Action":["ecr:*","ssm:*","apigateway:*","lambda:*","logs:*","s3:*","ec2:*","iam:*","codebuild:*","cloudformation:*","cognito-idp:*","acm:*"]}]}'

# Create CodeBuild project
echo "Creating CodeBuild project..."
source_config="{\"type\": \"GITHUB\", \"location\": \"$REPO_URL\""
if [ -n "$branch_name" ]; then
    source_config="$source_config, \"gitCloneDepth\": 1, \"buildspec\": \"version: 0.2\nphases:\n  install:\n    runtime-versions:\n      python: latest\n      nodejs: latest\n    commands:\n      - python -m pip install --upgrade pip\n      - npm install -g aws-cdk\n      - pip install --upgrade awscli\n  pre_build:\n    commands:\n      - git checkout $branch_name\n      - cd cdk\n      - cdk --version\n      - python3 -m venv .venv\n      - . .venv/bin/activate\n      - pip install --upgrade pip\n      - pip install -r requirements.txt\n  build:\n    commands:\n      - cd ..\n      - chmod +x deploy.sh\n      - ./deploy.sh --headless --allowlist @amazon.com,@amazon.\""
else
    source_config="$source_config, \"buildspec\": \"version: 0.2\nphases:\n  install:\n    runtime-versions:\n      python: latest\n      nodejs: latest\n    commands:\n      - python -m pip install --upgrade pip\n      - npm install -g aws-cdk\n      - pip install --upgrade awscli\n  pre_build:\n    commands:\n      - cd cdk\n      - cdk --version\n      - python3 -m venv .venv\n      - . .venv/bin/activate\n      - pip install --upgrade pip\n      - pip install -r requirements.txt\n  build:\n    commands:\n      - cd ..\n      - chmod +x deploy.sh\n      - ./deploy.sh --headless --allowlist @amazon.com,@amazon.\""
fi
source_config="$source_config}"

aws codebuild create-project --name $CODEBUILD_PROJECT_NAME \
    --source "$source_config" \
    --artifacts "{\"type\": \"NO_ARTIFACTS\"}" \
    --environment "{\"type\": \"LINUX_CONTAINER\", \"image\": \"aws/codebuild/standard:7.0\", \"computeType\": \"BUILD_GENERAL1_SMALL\"}" \
    --service-role "arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/codebuild-$CODEBUILD_PROJECT_NAME-service-role" 

sleep 1
# wait for the project $CODEBUILD_PROJECT_NAME to be created
TIMEOUT=60
INTERVAL=2

start_time=$(date +%s)
end_time=$((start_time + TIMEOUT))
build_success=False 


while [ $(date +%s) -lt $end_time ]; do
    echo "Checking for project '$CODEBUILD_PROJECT_NAME' "
    raw_output=$(aws codebuild list-projects --query "projects[?@=='genai-bedrock-chatbot-build']")
    # if raw_output contains text from: $CODEBUILD_PROJECT_NAME
    if echo "$raw_output" | grep -q "$CODEBUILD_PROJECT_NAME"; then
        echo "Project '$CODEBUILD_PROJECT_NAME' found"
        echo "Deployment resources created successfully."
        break
    sleep $INTERVAL
done

if [ "$build_success" = true ]; then
    # Start the CodeBuild project build
    echo "Starting CodeBuild project build..."
    aws codebuild start-build --project-name $CODEBUILD_PROJECT_NAME
    echo "Build Started..."
fi

