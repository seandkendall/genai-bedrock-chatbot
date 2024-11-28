#!/usr/bin/env bash

# Purpose:
# This script provides a streamlined way to deploy updates to the web application
# component of your solution to Amazon S3. It should only be used after you have
# successfully completed at least one full deployment of the entire application stack.
#
# Use Case:
# - When you've made changes only to the web application code
# - When you want to update the frontend without modifying backend resources
# - For rapid iteration on UI changes without redeploying infrastructure
#
# Prerequisites:
# - A complete initial deployment must exist
# - Valid AWS credentials with S3 access
# - The S3 bucket from the initial deployment must still exist
#
# Note: If you need to deploy backend changes or if this is your first deployment,
# use the complete deployment script instead.

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
npm install -g aws-cdk
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


#change to cdk Directory
cd cdk
if [ ! -d "./static-website-source" ]; then
    # Create the directory if it doesn't exist
    echo "Creating static-website-source directory..."
    mkdir ./static-website-source
    touch ./static-website-source/placeholder.txt
fi

# generate outputs.json
./gen-outputs-json.py

# Function to validate the existence and non-emptiness of a variable
validate_variable() {
    local var_name=$1
    local var_value=$2

    if [[ -z "$var_value" || "$var_value" == "null" ]]; then
        echo "Error: Required variable '$var_name' is missing or empty in outputs.json."
        exit 1
    fi
}

# Extract values from outputs.json
websocketapiendpoint=$(jq -r '.ChatbotWebsiteStack.websocketapiendpoint' ./outputs.json)
validate_variable "websocketapiendpoint" "$websocketapiendpoint"

region=$(jq -r '.ChatbotWebsiteStack.region' ./outputs.json)
validate_variable "region" "$region"

s3bucket=$(jq -r '.ChatbotWebsiteStack.s3bucket' ./outputs.json)
validate_variable "s3bucket" "$s3bucket"

userpoolid=$(jq -r '.ChatbotWebsiteStack.userpoolid' ./outputs.json)
validate_variable "userpoolid" "$userpoolid"

userpoolclientid=$(jq -r '.ChatbotWebsiteStack.userpoolclientid' ./outputs.json)
validate_variable "userpoolclientid" "$userpoolclientid"

awschatboturl=$(jq -r '.ChatbotWebsiteStack.AWSChatBotURL' ./outputs.json)
validate_variable "awschatboturl" "$awschatboturl"

# If all variables are valid, proceed with the script
echo "All required variables have been successfully validated."
echo "WebSocket API Endpoint: $websocketapiendpoint"
echo "Region: $region"
echo "S3 Bucket: $s3bucket"
echo "User Pool ID: $userpoolid"
echo "User Pool Client ID: $userpoolclientid"
echo "AWS ChatBot URL: $awschatboturl"
# Generate ./react-chatbot/src/variables.js
mkdir -p ./react-chatbot/src/

variables_file="./react-chatbot/src/variables.js"
new_variables_content=$(cat <<HEREDOC_DELIMITER
const websocketUrl = '$websocketapiendpoint';

export { websocketUrl };
HEREDOC_DELIMITER
)

# generate variables.js
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

# generate config.json
./gen-config-json.py

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
# rm outputs.json
cd ..
echo -e "${GREEN_COLOR}Deployment complete! (Git Version $latest_commit)${DEFAULT_COLOR}"
# tell user to visit the url: awschatboturl
echo -e "${GREEN_COLOR}Visit the chatbot here: ${awschatboturl}${DEFAULT_COLOR}"
