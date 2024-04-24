#!/bin/bash
# Define colors
DEFAULT_COLOR="\033[0m"
GREEN_COLOR="\033[0;32m"
RED_COLOR="\033[0;31m"

# Parse command-line arguments
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
        *) echo "Unknown argument: $1"; shift;;
    esac
done

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

# Check if it's a new day and update pip and aws-cdk if needed
# last_update_file="last_update.txt"
# current_date=$(date +%Y%m%d)

# if [ -f "$last_update_file" ]; then
#     last_update=$(cat "$last_update_file")
# else
#     last_update=0
# fi

# if [ "$current_date" != "$last_update" ]; then
#     echo "Updating pip and aws-cdk..."
#     python3 -m pip install --upgrade pip
#     npm install -g aws-cdk
#     echo "$current_date" > "$last_update_file"
# fi

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

# Read cognitoDomain from reference file, if it exists
if [ -f cognitoDomain.ref ]; then
  cognitoDomain=$(cat cognitoDomain.ref)
else
  read -p "Enter a cognitoDomain (lowercase, no special characters): " cognitoDomain
  # Validate cognitoDomain format
  if ! [[ "$cognitoDomain" =~ ^[a-z]+$ ]]; then
    echo "Error: cognitoDomain must be lowercase and contain no special characters."
    exit 1
  fi
  echo "$cognitoDomain" > cognitoDomain.ref
fi

# Check if allowlistDomain exists, else prompt user
allowListDomain=""
if [ -f allowlistdomain.ref ]; then
  allowListDomain=$(cat allowlistdomain.ref)
else
  read -p "Would you like to add an email domain allowlist for user registration? (y/n) " add_allowlist
  case "$add_allowlist" in
    [yY][eE][sS]|[yY])
      while true; do
        read -p "Enter the allowlist domain (Example: @amazon.com): " allowListDomain
        if [[ "$allowListDomain" =~ ^@[a-zA-Z0-9.-]+\.[a-zA-Z]+$ ]]; then
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
    read -p "Do you want to run cdk Bootstrap now (if you don't know, assume Yes)? (y/n) " run_bootstrap
    case "$run_bootstrap" in
        [yY][eE][sS]|[yY])
            echo "Running CDK bootstrap..."
            cdk bootstrap --require-approval never
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
touch "$bootstrap_ref_file"

# Deploy the CDK app
cdk deploy --outputs-file outputs.json --parameters cognitoDomain="$cognitoDomain" --parameters allowlistDomain="$allowListDomain" --require-approval never $app_flag $context_flag $debug_flag $profile_flag $tags_flag $force_flag $verbose_flag $role_arn_flag
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

# Go back to the parent directory
cd ..

cdk deploy --outputs-file outputs.json --parameters cognitoDomain="$cognitoDomain" --parameters allowlistDomain="$allowListDomain" --require-approval never $app_flag $context_flag $debug_flag $profile_flag $tags_flag $force_flag $verbose_flag $role_arn_flag
if [ $? -ne 0 ]; then
    echo -e "${RED_COLOR}Error: CDK deployment failed. Exiting script.${DEFAULT_COLOR}"
    exit 1
fi
rm outputs.json

cd ..
echo -e "${GREEN_COLOR}Deployment complete!${DEFAULT_COLOR}"
# tell user to visit the url: awschatboturl
echo -e "${GREEN_COLOR}Visit the chatbot here: ${awschatboturl}${DEFAULT_COLOR}"