#!/usr/bin/env bash
# Define colors
has_colors() {
    local has_colors=false
    if [ -t 1 ]; then
        if command -v tput >/dev/null 2>&1; then
            if [ "$TERM" != linux ]; then
                has_colors=true
            fi
        fi
    fi
    echo $has_colors
}

if $(has_colors); then
    # Use color codes
    DEFAULT_COLOR="\033[0m"
    GREEN_COLOR="\033[0;32m"
    RED_COLOR="\033[0;31m"
else
    # Don't use color codes
    DEFAULT_COLOR=""
    GREEN_COLOR=""
    RED_COLOR=""
fi


# Parse command-line arguments
POSITIONAL_ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        -a|--app) app_flag="--app $2"; shift 2;;
        -c|--context) context_flag="--context $2"; shift 2;;
        --debug) debug_flag="--debug"; shift;;
        --profile) profile_flag="--profile $2"; shift 2;;
        -t|--tags) tags_flag="--tags $2"; shift 2;;
        -f|--force) force_flag="--force"; shift;;
        -v|--verbose) verbose_flag="--verbose"; shift;;
        -r|--role-arn) role_arn_flag="--role-arn $2"; shift 2;;
        --allowlist)
            allowListDomain="$2"
            shift 2
            ;;
        --headless)
            run_bootstrap=true
            shift
            ;;
        *)
            POSITIONAL_ARGS+=("$1")
            shift
            ;;
    esac
done

# Restore the positional arguments
set -- "${POSITIONAL_ARGS[@]}"

# Check if AWS CDK is installed
if ! command -v cdk &> /dev/null
then
    echo -e "${RED_COLOR}Error: AWS CDK is not installed. Please install the AWS CDK or run the setup script.${DEFAULT_COLOR}"
    echo -e "${GREEN_COLOR}To install the AWS CDK manually, follow the instructions at: https://docs.aws.amazon.com/cdk/latest/guide/getting_started.html${DEFAULT_COLOR}"
    echo -e "${GREEN_COLOR}Alternatively, you can run the setup script by executing: ./setup.sh${DEFAULT_COLOR}"
    exit 1
fi

# Check if jq is installed
if ! command -v jq &> /dev/null
then
    echo -e "${RED_COLOR}Error: jq is not installed. Please install jq and try again.${DEFAULT_COLOR}"
    case "$(uname -s)" in
        Linux*) echo -e "${GREEN_COLOR}On Linux, you can install jq with: sudo apt-get install jq${DEFAULT_COLOR}" ;;
        Darwin*) echo -e "${GREEN_COLOR}On macOS, you can install jq with: brew install jq${DEFAULT_COLOR}" ;; 
        CYGWIN*|MINGW*|MSYS*) echo -e "${GREEN_COLOR}On Windows with PowerShell, you can install jq with: choco install jq${DEFAULT_COLOR}" ;;
        *) echo -e "${RED_COLOR}Unsupported operating system. Please install jq manually.${DEFAULT_COLOR}" ;;
    esac
    exit 1
fi

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null
then
    echo -e "${RED_COLOR}Error: AWS CLI is not installed. Please install the AWS CLI and configure your AWS credentials before running this script.${DEFAULT_COLOR}"
    case "$(uname -s)" in
        Linux*) echo -e "${GREEN_COLOR}On Linux, you can install the AWS CLI with: sudo apt-get install awscli${DEFAULT_COLOR}" ;;
        Darwin*) echo -e "${GREEN_COLOR}On macOS, you can install the AWS CLI with: brew install awscli${DEFAULT_COLOR}" ;;
        CYGWIN*|MINGW*|MSYS*) echo -e "${GREEN_COLOR}On Windows, you can download and install the AWS CLI from: https://aws.amazon.com/cli/${DEFAULT_COLOR}" ;;
        *) echo -e "${RED_COLOR}Unsupported operating system. Please visit https://aws.amazon.com/cli/ for installation instructions.${DEFAULT_COLOR}" ;;
    esac
    echo -e "${GREEN_COLOR}After installing the AWS CLI, run 'aws configure' to set up your AWS credentials.${DEFAULT_COLOR}"
    echo -e "${GREEN_COLOR}Visit https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-configure.html for more information.${DEFAULT_COLOR}"
    exit 1
fi

# Check if the virtual environment is activated
if [ -z "${VIRTUAL_ENV}" ]; then
    # Virtual environment is not activated
    if [ -d "./cdk/.venv" ]; then
        # Virtual environment exists, but not activated
        echo -e "${DEFAULT_COLOR}The virtual environment exists but is not activated."
        echo -e "${DEFAULT_COLOR}To activate the virtual environment, run the following commands:"
        echo -e ""
        echo -e "${GREEN_COLOR}cd cdk"
        echo -e "${GREEN_COLOR}source .venv/bin/activate"
        echo -e "${GREEN_COLOR}cd .."
        echo -e ""
        echo -e "${DEFAULT_COLOR}Once this is complete, run the deploy command again"
    else
        # Virtual environment does not exist
        echo -e "${DEFAULT_COLOR}The virtual environment does not exist."
        echo -e "${DEFAULT_COLOR}To create and activate the virtual environment, run the following commands:"
        echo -e ""
        echo -e "${GREEN_COLOR}cd cdk"
        echo -e "${GREEN_COLOR}python3 -m venv .venv"
        echo -e "${GREEN_COLOR}source .venv/bin/activate"
        echo -e "${GREEN_COLOR}python3 -m pip install -r requirements.txt"
        echo -e "${GREEN_COLOR}cd .."
        echo -e ""
        echo -e "${DEFAULT_COLOR}Once this is complete, run the deploy command again"
    fi
    exit 1
fi

user_pool_id=$(aws cognito-idp list-user-pools --max-results 60 --query 'UserPools[?contains(Name, `ChatbotUserPool`)].Id' --output text)
if [ -n "$user_pool_id" ] && [ "$user_pool_id" != "None" ]; then
    cognitoDomain=$(aws cognito-idp describe-user-pool --user-pool-id "$user_pool_id" --query 'UserPool.Domain' --output text)
    if [ -n "$cognitoDomain" ] && [ "$cognitoDomain" != "None" ]; then
        echo -e "${DEFAULT_COLOR}User pool found with ID $user_pool_id and domain $cognitoDomain"
    else
        echo -e "${DEFAULT_COLOR}User pool found with ID $user_pool_id, but no Domain"
        cognitoDomain="genchatbot-$(LC_ALL=C tr -dc 'a-z0-9' < /dev/urandom | head -c 8)-$(date +%y%m%d%H%M)"
        echo -e "${DEFAULT_COLOR}New Domain Set: $cognitoDomain"
    fi
else
    cognitoDomain="genchatbot-$(LC_ALL=C tr -dc 'a-z0-9' < /dev/urandom | head -c 8)-$(date +%y%m%d%H%M)"
    echo -e "${DEFAULT_COLOR}No User Pool or Domain Found, Creating New Domain: $cognitoDomain"
fi

get_certificate_arn() {
    local cname="$1"
    local wildcard_cname="*.$cname"

    # Check for a direct match first
    certificate_arn=$(aws acm list-certificates --query "CertificateSummaryList[?DomainName=='$cname'].CertificateArn|[0]" --output text)

    # If no direct match, check for a wildcard certificate
    if [ -z "$certificate_arn" ]; then
        certificate_arn=$(aws acm list-certificates --query "CertificateSummaryList[?DomainName=='$wildcard_cname'].CertificateArn|[0]" --output text)
    fi

    echo "$certificate_arn"
}


# Check if allowlistDomain exists, else prompt user
if [ -z "$allowListDomain" ]; then
    if [ -n "$run_bootstrap" ]; then
        # If --headless flag is used, assume add_allowlist is false
        allowListDomain=""
    else
        read -p "Would you like to add one or more email domains to an allowlist for user registration? (y/n) " add_allowlist
        case "$add_allowlist" in
            [yY][eE][sS]|[yY])
                while true; do
                    read -p "Enter the allowlist domains separated by commas (Example: @amazon.com,@example.ca): " allowListDomain
                    valid=true
                    IFS=',' read -ra domains <<< "$allowListDomain"
                    for domain in "${domains[@]}"; do
                        if ! [[ "$domain" =~ ^@?[a-zA-Z0-9.-]+$ ]]; then
                            valid=false
                            break
                        fi
                    done
                    if $valid; then
                        echo "$allowListDomain" > allowlistdomain.ref
                        break
                    else
                        echo "Error: Invalid domain format. Please try again."
                    fi
                done
                ;;
            *)
                echo "" > allowlistdomain.ref
                ;;
        esac
    fi
fi

./recreate-python-lambda-layer.sh
#change to cdk Directory
cd cdk
if [ ! -d "./static-website-source" ]; then
    # Create the directory if it doesn't exist
    echo "Creating static-website-source directory..."
    mkdir ./static-website-source
    touch ./static-website-source/placeholder.txt
fi

# Install Python dependencies
python3 -m pip install -r requirements.txt

# Check if CDK bootstrap has been completed
bootstrap_ref_file="bootstrap.ref"

if [ -f "$bootstrap_ref_file" ]; then
    echo "Skipping CDK bootstrap process."
else
    if [ -n "$run_bootstrap" ]; then
        # If --headless flag is used, run cdk bootstrap
        echo "Running CDK bootstrap..."
        cdk bootstrap --require-approval never --context cognitoDomain="$cognitoDomain" --context allowlistDomain="$allowListDomain"
        if [ $? -eq 0 ]; then
            echo "CDK bootstrap completed successfully."
        else
            echo "Failed to run CDK bootstrap."
            exit 1
        fi
    else
        read -p "Do you want to run cdk Bootstrap now (if you don't know, assume Yes)? (y/n) " run_bootstrap
        case "$run_bootstrap" in
            [yY][eE][sS]|[yY])
                echo "Running CDK bootstrap..."
                cdk bootstrap --require-approval never --context cognitoDomain="$cognitoDomain" --context allowlistDomain="$allowListDomain"
                if [ $? -eq 0 ]; then
                    echo "CDK bootstrap completed successfully."
                else
                    echo "Failed to run CDK bootstrap."
                    exit 1
                fi
                ;;
            *)
                echo "Skipping CDK bootstrap process."
                ;;
        esac
    fi
fi
touch "$bootstrap_ref_file"

# Deploy the CDK app
cdk deploy --outputs-file outputs.json --context cognitoDomain="$cognitoDomain" --context allowlistDomain="$allowListDomain" --require-approval never $app_flag $context_flag $debug_flag $profile_flag $tags_flag $force_flag $verbose_flag $role_arn_flag
if [ $? -ne 0 ]; then
    echo "Error: CDK deployment failed. Exiting script."
    exit 1
fi

#### START BUILDING REACT APP ####
# Check if outputs.json exists
if [ ! -f "./outputs.json" ]; then
    echo "Error: outputs.json file not found in the current directory."
    exit 1
fi

# Extract values from outputs.json
websocketapiendpoint=$(jq -r '.ChatbotWebsiteStack.websocketapiendpoint' ./outputs.json)
region=$(jq -r '.ChatbotWebsiteStack.region' ./outputs.json)
s3bucket=$(jq -r '.ChatbotWebsiteStack.s3bucket' ./outputs.json)
userpoolid=$(jq -r '.ChatbotWebsiteStack.userpoolid' ./outputs.json)
userpoolclientid=$(jq -r '.ChatbotWebsiteStack.userpoolclientid' ./outputs.json)
awschatboturl=$(jq -r '.ChatbotWebsiteStack.AWSChatBotURL' ./outputs.json)

# Generate ./react-chatbot/src/variables.js
mkdir -p ./react-chatbot/src/

variables_file="./react-chatbot/src/variables.js"
new_variables_content=$(cat <<HEREDOC_DELIMITER
const websocketUrl = '$websocketapiendpoint';

export { websocketUrl };
HEREDOC_DELIMITER
)


if [ -f "$variables_file" ]; then
    # File exists, compare contents
    existing_variables_content=$(cat "$variables_file")
    if [ "$existing_variables_content" != "$new_variables_content" ]; then
        # Contents are different, update the file
        printf "%s" "$new_variables_content" > "$variables_file"
        echo "variables.js file updated."
    else
        echo "variables.js file is up-to-date."
    fi
else
    # File doesn't exist, create it
    printf "%s" "$new_variables_content" > "$variables_file"
    echo "variables.js file created."
fi

# Generate ./react-chatbot/src/config.json
config_file="./react-chatbot/src/config.json"
new_config_content=$(cat <<HEREDOC_DELIMITER
{
  "aws_project_region": "${region}",
  "aws_cognito_region": "${region}",
  "aws_user_pools_id": "${userpoolid}",
  "aws_user_pools_web_client_id": "${userpoolclientid}"
}
HEREDOC_DELIMITER
)

if [ -f "$config_file" ]; then
    # File exists, compare contents
    existing_config_content=$(cat "$config_file")
    if [ "$existing_config_content" != "$new_config_content" ]; then
        # Contents are different, update the file
        printf "%s" "$new_config_content" > "$config_file"
        echo "config.json file updated."
    else
        echo "config.json file is up-to-date."
    fi
else
    # File doesn't exist, create it
    printf "%s" "$new_config_content" > "$config_file"
    echo "config.json file created."
fi

echo "Config files processed successfully!"

# Change to the cdk/react-chatbot directory
cd ./react-chatbot

# Install dependencies and build the React application
npm install
if [ $? -ne 0 ]; then
    echo -e "${RED_COLOR}Error: npm install failed. Exiting script.${DEFAULT_COLOR}"
    exit 1
fi
npm run build
if [ $? -ne 0 ]; then
    echo -e "${RED_COLOR}Error: npm run build failed. Exiting script.${DEFAULT_COLOR}"
    exit 1
fi

cd ../static-website-source
aws s3 sync . s3://$s3bucket/ --delete

# Go back to the parent directory
cd ..
rm outputs.json
cd ..
echo -e "${GREEN_COLOR}Deployment complete!${DEFAULT_COLOR}"
# tell user to visit the url: awschatboturl
echo -e "${GREEN_COLOR}Visit the chatbot here: ${awschatboturl}${DEFAULT_COLOR}"
