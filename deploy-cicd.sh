#!/bin/bash
export AWS_PAGER=""

# Function to display help information
display_help() {
  echo "Usage: $0 [OPTIONS]"
  echo
  echo "Options:"
  echo "  -h, --help                 Display this help message"
  echo "  -d                         Delete existing resources"
  echo "  -a                         Enable auto-deploy branch detection"
  echo "  --deploy-agents-example    Deploy agents example"
  echo "  --branch BRANCH_NAME       Specify a branch to use"
  echo "  --schedule SCHEDULE        Set the deployment schedule (daily or weekly, default: weekly)"
  echo "  --allowlist PATTERN        Set the allowlist pattern"
  echo
  echo "Example:"
  echo "  $0 -a --schedule daily --allowlist 'mypattern*'"
  exit 0
}

# GitHub repository URL
REPO_URL="https://github.com/seandkendall/genai-bedrock-chatbot"

# Project names
CODEBUILD_PROJECT_NAME="genai-bedrock-chatbot-build"

# Set default schedule to weekly
schedule="weekly"

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
  -h | --help) display_help ;;
  -d)
    delete_flag=true
    shift
    ;;
  -a)
    auto_deploy_branch=true
    shift
    ;;
  --deploy-agents-example)
    deploy_agents_example=true
    shift
    ;;
  --branch)
    branch_name="$2"
    shift 2
    ;;
  --schedule)
    schedule="$2"
    shift 2
    ;;
  --allowlist)
    allowlist_pattern="$2"
    shift 2
    ;;
  *)
    echo "Unknown argument: $1"
    display_help
    ;;
  esac
done

get_aws_region() {
  local region=""

  # Check if AWS_REGION is set
  if [ -n "${AWS_REGION}" ]; then
    region="${AWS_REGION}"
  # Check if AWS_DEFAULT_REGION is set
  elif [ -n "${AWS_DEFAULT_REGION}" ]; then
    region="${AWS_DEFAULT_REGION}"
  # Try to get region from AWS CLI configuration
  else
    local cli_region=$(aws configure get region)
    if [ -n "${cli_region}" ]; then
      region="${cli_region}"
    # Default to us-east-1 if no region is found
    else
      region="us-east-1"
    fi
  fi

  echo "${region}"
}

create_eventbridge_rule() {
  local schedule=$1
  local rule_name="$CODEBUILD_PROJECT_NAME-trigger"
  local region=$(get_aws_region)

  # Debug output
  echo "Using region: $region"
  echo "CodeBuild project name: $CODEBUILD_PROJECT_NAME"

  # Create the EventBridge rule
  aws events put-rule \
    --name "$rule_name" \
    --schedule-expression "$schedule" \
    --state "ENABLED" \
    --region "$region"

  # Create the target for the rule
  aws events put-targets \
    --rule "$rule_name" \
    --region "$region" \
    --targets "[{\"Id\": \"1\", \"Arn\": \"arn:aws:codebuild:$region:$(aws sts get-caller-identity --query Account --output text):project/$CODEBUILD_PROJECT_NAME\", \"RoleArn\": \"arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/service-role/Amazon_EventBridge_Invoke_CodeBuild\"}]"

  # Confirm created resources
  echo "EventBridge rule ARN: $(aws events describe-rule --name "$rule_name" --region "$region" --query 'Arn' --output text)"
  echo "Target ARN: arn:aws:codebuild:$region:$(aws sts get-caller-identity --query Account --output text):project/$CODEBUILD_PROJECT_NAME"
}

# Function to delete existing resources
delete_resources() {
  echo "Deleting existing resources..."
  aws events remove-targets --rule "$CODEBUILD_PROJECT_NAME-trigger" --ids "1" 2>/dev/null || true
  aws events delete-rule --name "$CODEBUILD_PROJECT_NAME-trigger" 2>/dev/null || true
  aws codebuild delete-project --name $CODEBUILD_PROJECT_NAME 2>/dev/null || true
  aws iam delete-role-policy --role-name "codebuild-$CODEBUILD_PROJECT_NAME-service-role" --policy-name "codebuild-base-policy" 2>/dev/null || true
  aws iam delete-role --role-name "codebuild-$CODEBUILD_PROJECT_NAME-service-role" 2>/dev/null || true
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
  fi
  sleep 5
}

# Create or update IAM roles
echo "Creating or updating IAM roles..."

# CodeBuild role
create_or_update_role \
  "codebuild-$CODEBUILD_PROJECT_NAME-service-role" \
  '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"codebuild.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
  "codebuild-base-policy" \
  '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Resource":"*","Action":["ecr:GetAuthorizationToken","ecr:BatchCheckLayerAvailability","ecr:GetDownloadUrlForLayer","ecr:BatchGetImage","ecr:PutImage","ecr:InitiateLayerUpload","ecr:UploadLayerPart","ecr:CompleteLayerUpload","ecr:DescribeRepositories","ecr:CreateRepository","ecr:SetRepositoryPolicy","ecr:GetRepositoryPolicy","ecr:ListImages","ecr:DeleteRepository","ecr:TagResource","dynamodb:CreateTable","dynamodb:DeleteTable","dynamodb:DescribeTable","dynamodb:UpdateTable","dynamodb:PutItem","dynamodb:GetItem","dynamodb:ListTables","dynamodb:TagResource","dynamodb:UntagResource","dynamodb:DescribeContinuousBackups","dynamodb:UpdateContinuousBackups","dynamodb:ListTagsOfResource","ssm:GetParameter","ssm:PutParameter","ssm:DeleteParameter","ssm:GetParameters","ssm:DescribeParameters","ssm:AddTagsToResource","ssm:RemoveTagsFromResource","ssm:ListTagsForResource","apigateway:GET","apigateway:POST","apigateway:PUT","apigateway:DELETE","apigateway:PATCH","apigateway:TagResource","apigateway:UntagResource","lambda:CreateFunction","lambda:DeleteFunction","lambda:GetFunction","lambda:GetFunctionConfiguration","lambda:UpdateFunctionCode","lambda:UpdateFunctionConfiguration","lambda:AddPermission","lambda:RemovePermission","lambda:InvokeFunction","lambda:PublishLayerVersion","lambda:DeleteLayerVersion","lambda:GetLayerVersion","lambda:ListLayerVersions","lambda:CreateEventSourceMapping","lambda:DeleteEventSourceMapping","lambda:GetEventSourceMapping","lambda:ListEventSourceMappings","lambda:UpdateEventSourceMapping","lambda:TagResource","lambda:UntagResource","lambda:ListTags","lambda:GetPolicy","lambda:PutFunctionEventInvokeConfig","logs:CreateLogGroup","logs:DeleteLogGroup","logs:DescribeLogGroups","logs:PutRetentionPolicy","logs:DeleteRetentionPolicy","logs:TagResource","logs:UntagResource","logs:ListTagsForResource","logs:TagLogGroup","logs:UntagLogGroup","s3:CreateBucket","s3:DeleteBucket","s3:PutObject","s3:GetObject","s3:DeleteObject","s3:ListBucket","s3:GetBucketLocation","s3:PutBucketPolicy","s3:GetBucketPolicy","s3:DeleteBucketPolicy","s3:PutBucketPublicAccessBlock","s3:GetBucketPublicAccessBlock","s3:PutEncryptionConfiguration","s3:GetEncryptionConfiguration","s3:PutLifecycleConfiguration","s3:GetLifecycleConfiguration","s3:PutBucketCors","s3:GetBucketCors","s3:PutBucketVersioning","s3:GetBucketVersioning","s3:PutBucketNotification","s3:GetBucketNotification","s3:PutBucketTagging","s3:GetBucketTagging","s3:ListAllMyBuckets","ec2:DescribeVpcs","ec2:DescribeSubnets","ec2:DescribeSecurityGroups","ec2:DescribeAvailabilityZones","ec2:DescribeAccountAttributes","iam:CreateRole","iam:DeleteRole","iam:GetRole","iam:PassRole","iam:AttachRolePolicy","iam:DetachRolePolicy","iam:PutRolePolicy","iam:DeleteRolePolicy","iam:GetRolePolicy","iam:TagRole","iam:UntagRole","iam:CreatePolicy","iam:DeletePolicy","iam:GetPolicy","iam:ListRolePolicies","iam:ListAttachedRolePolicies","iam:CreateServiceLinkedRole","iam:ListPolicyVersions","iam:CreatePolicyVersion","iam:DeletePolicyVersion","iam:ListRoles","codebuild:CreateProject","codebuild:DeleteProject","codebuild:UpdateProject","codebuild:StartBuild","codebuild:BatchGetProjects","codebuild:ListProjects","cloudformation:CreateStack","cloudformation:UpdateStack","cloudformation:DeleteStack","cloudformation:DescribeStacks","cloudformation:DescribeStackEvents","cloudformation:GetTemplate","cloudformation:ListStacks","cloudformation:CreateChangeSet","cloudformation:DeleteChangeSet","cloudformation:DescribeChangeSet","cloudformation:ExecuteChangeSet","cloudformation:ListChangeSets","cloudformation:GetTemplateSummary","cloudformation:ValidateTemplate","cloudformation:ListStackResources","cloudformation:DescribeStackResource","cloudformation:TagResource","cognito-idp:CreateUserPool","cognito-idp:DeleteUserPool","cognito-idp:DescribeUserPool","cognito-idp:UpdateUserPool","cognito-idp:CreateUserPoolClient","cognito-idp:DeleteUserPoolClient","cognito-idp:DescribeUserPoolClient","cognito-idp:UpdateUserPoolClient","cognito-idp:CreateUserPoolDomain","cognito-idp:DeleteUserPoolDomain","cognito-idp:DescribeUserPoolDomain","cognito-idp:ListUserPools","cognito-idp:SetUserPoolMfaConfig","cognito-idp:AdminCreateUser","cognito-idp:AdminDeleteUser","acm:ListCertificates","acm:DescribeCertificate","acm:RequestCertificate","sts:AssumeRole","sts:GetCallerIdentity","cloudfront:CreateDistribution","cloudfront:UpdateDistribution","cloudfront:DeleteDistribution","cloudfront:GetDistribution","cloudfront:TagResource","cloudfront:ListDistributions","cloudfront:CreateOriginAccessControl","cloudfront:DeleteOriginAccessControl","cloudfront:GetOriginAccessControl","cloudfront:ListOriginAccessControls","sqs:CreateQueue","sqs:DeleteQueue","sqs:GetQueueAttributes","sqs:SetQueueAttributes","sqs:TagQueue","sqs:UntagQueue","sqs:GetQueueUrl","sqs:ListQueues","scheduler:CreateSchedule","scheduler:DeleteSchedule","scheduler:GetSchedule","scheduler:UpdateSchedule","scheduler:CreateScheduleGroup","scheduler:DeleteScheduleGroup","scheduler:GetScheduleGroup","scheduler:TagResource","events:PutRule","events:DeleteRule","events:DescribeRule","events:PutTargets","events:RemoveTargets","events:ListRules","cognito-identity:CreateIdentityPool","cognito-identity:DeleteIdentityPool","cognito-identity:DescribeIdentityPool","cognito-identity:UpdateIdentityPool","cognito-identity:SetIdentityPoolRoles","cognito-identity:GetIdentityPoolRoles","cognito-identity:TagResource","rum:CreateAppMonitor","rum:DeleteAppMonitor","rum:GetAppMonitor","rum:UpdateAppMonitor","rum:TagResource","rum:ListAppMonitors","bedrock:ListFoundationModels","bedrock:GetFoundationModel","bedrock:ListInferenceProfiles","bedrock:ListAgents","bedrock:CreateAgent","bedrock:DeleteAgent","bedrock:GetAgent","route53:GetHostedZone","route53:ListHostedZones","route53:ChangeResourceRecordSets","servicecatalog-appregistry:GetApplication","servicecatalog-appregistry:CreateApplication","servicecatalog-appregistry:TagResource"]}]}'

# Create CodeBuild project
echo "Creating CodeBuild project..."
source_config="{\"type\": \"GITHUB\", \"location\": \"$REPO_URL\""
deploy_agents_example_option=$([ "$deploy_agents_example" = true ] && echo " --deploy-agents-example " || echo "")

allowlist_option=$([ -n "$allowlist_pattern" ] && echo "--allowlist $allowlist_pattern" || echo "")

if [ -n "$branch_name" ]; then
  # Use the specified branch
  read -r -d '' buildspec <<EOF
version: 0.2

phases:
  install:
    runtime-versions:
      python: latest
      nodejs: latest
    commands:
      - python -m pip install --upgrade pip
      - npm install -g aws-cdk
      - pip install --upgrade awscli
  pre_build:
    commands:
      - docker run --privileged --rm public.ecr.aws/eks-distro-build-tooling/binfmt-misc:qemu-v7.0.0 --install all
      - docker buildx inspect --bootstrap
      - docker buildx create --use --platform=linux/amd64
      - git checkout $branch_name
      - cd cdk
      - cdk --version
      - python3 -m venv .env
      - . .env/bin/activate
      - pip install --upgrade pip
      - pip install -r requirements.txt
  build:
    commands:
      - cd ..
      - chmod +x deploy.sh
      - ./deploy.sh $deploy_agents_example_option --headless $allowlist_option
EOF
elif [ "$auto_deploy_branch" = true ]; then
  # Use auto-deploy branch detection
  read -r -d '' buildspec <<EOF
version: 0.2

phases:
  install:
    runtime-versions:
      python: latest
      nodejs: latest
    commands:
      - python -m pip install --upgrade pip
      - npm install -g aws-cdk
      - pip install --upgrade awscli
  pre_build:
    commands:
      - docker run --privileged --rm public.ecr.aws/eks-distro-build-tooling/binfmt-misc:qemu-v7.0.0 --install all
      - docker buildx inspect --bootstrap
      - docker buildx create --use --platform=linux/amd64
      - auto_deploy_branch=\$(git branch -r | grep -m1 'origin/feature_.*_autodeploy' | sed 's/.*origin\\///' || echo '')
      - |
        if [ -n "\$auto_deploy_branch" ]; then 
          echo "Found auto-deploy branch: \$auto_deploy_branch" && git checkout \$auto_deploy_branch
        else 
          echo "No auto-deploy branch found. Checking out default branch." && git checkout main
        fi
      - cd cdk
      - cdk --version
      - python3 -m venv .env
      - . .env/bin/activate
      - pip install --upgrade pip
      - pip install -r requirements.txt
  build:
    commands:
      - cd ..
      - chmod +x deploy.sh
      - ./deploy.sh $deploy_agents_example_option --headless $allowlist_option
EOF
else
  # Use auto-deploy branch detection
  read -r -d '' buildspec <<EOF
version: 0.2

phases:
  install:
    runtime-versions:
      python: latest
      nodejs: latest
    commands:
      - python -m pip install --upgrade pip
      - npm install -g aws-cdk
      - pip install --upgrade awscli
  pre_build:
    commands:
      - docker run --privileged --rm public.ecr.aws/eks-distro-build-tooling/binfmt-misc:qemu-v7.0.0 --install all
      - docker buildx inspect --bootstrap
      - docker buildx create --use --platform=linux/amd64
      - cd cdk
      - cdk --version
      - python3 -m venv .env
      - . .env/bin/activate
      - pip install --upgrade pip
      - pip install -r requirements.txt
  build:
    commands:
      - cd ..
      - chmod +x deploy.sh
      - ./deploy.sh $deploy_agents_example_option --headless $allowlist_option
EOF
fi

# Escape the buildspec for JSON
buildspec_escaped=$(echo "$buildspec" | jq -Rs .)

# Add the buildspec to the source_config
source_config="$source_config, \"buildspec\": $buildspec_escaped}"

# Create the CodeBuild project
aws codebuild create-project --name $CODEBUILD_PROJECT_NAME \
  --source "$source_config" \
  --description "Build and deploy genai-bedrock-chatbot" \
  --artifacts "{\"type\": \"NO_ARTIFACTS\"}" \
  --environment '{
    "type": "LINUX_CONTAINER", 
    "image": "aws/codebuild/amazonlinux2-x86_64-standard:5.0", 
    "computeType": "BUILD_GENERAL1_SMALL",
    "privilegedMode": true
  }' \
  --service-role "arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/codebuild-$CODEBUILD_PROJECT_NAME-service-role" \
  --build-batch-config '{"serviceRole": "codebuild-'$CODEBUILD_PROJECT_NAME'-service-role"}' \
  --logs-config '{"cloudWatchLogs": {"status": "ENABLED"}}'


sleep 1
# wait for the project $CODEBUILD_PROJECT_NAME to be created
TIMEOUT=60
INTERVAL=2

start_time=$(date +%s)
end_time=$((start_time + TIMEOUT))
build_success=false

while [ $(date +%s) -lt $end_time ]; do
  echo "Checking for project '$CODEBUILD_PROJECT_NAME' "
  raw_output=$(aws codebuild list-projects --query "projects[?@=='genai-bedrock-chatbot-build']")
  # if raw_output contains text from: $CODEBUILD_PROJECT_NAME
  if echo "$raw_output" | grep -q "$CODEBUILD_PROJECT_NAME"; then
    echo "Project '$CODEBUILD_PROJECT_NAME' found"
    echo "Deployment resources created successfully."
    build_success=true
    break
  fi
  sleep $INTERVAL
done

# Create EventBridge rule for scheduled trigger
echo "Creating EventBridge rule for scheduled trigger..."
if [ "$schedule" = "daily" ]; then
  create_eventbridge_rule "cron(0 0 * * ? *)"
else
  create_eventbridge_rule "cron(0 0 ? * SUN *)"
fi

if [ "$build_success" = true ]; then
  # Start the CodeBuild project build
  echo "Starting CodeBuild project build..."
  aws codebuild start-build --project-name $CODEBUILD_PROJECT_NAME
  echo "Build Started..."
  echo "View Build status here: https://console.aws.amazon.com/codesuite/codebuild/projects/genai-bedrock-chatbot-build/history"
fi
