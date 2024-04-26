# Define colors
$DefaultColor = "`e[0m"
$GreenColor = "`e[0;32m"
$RedColor = "`e[0;31m"

function List-UserPools {
    aws cognito-idp list-user-pools --max-results 60 --query 'UserPools[*].Id' --output text
}

function Get-UserPoolDomain {
    param (
        [Parameter(Mandatory=$true)]
        [string]$UserPoolId
    )

    $domain = (aws cognito-idp describe-user-pool --user-pool-id "$UserPoolId" --query 'UserPool.Domain' --output text)
    if ($null -ne $domain) {
        return $domain
    }
}

# Parse command-line arguments
:argLoop While ($args.Count -gt 0) {
    $arg = $args[0]
    Switch ($arg) {
        "-a" { $appFlag = "--app $($args[1])"; $args = $args.RemoveRange(0, 2) }
        "-c" { $contextFlag = "--context $($args[1])"; $args = $args.RemoveRange(0, 2) }
        "--debug" { $debugFlag = "--debug"; $args = $args.RemoveRange(0, 1) }
        "--profile" { $profileFlag = "--profile $($args[1])"; $args = $args.RemoveRange(0, 2) }
        "-t" { $tagsFlag = "--tags $($args[1])"; $args = $args.RemoveRange(0, 2) }
        "-f" { $forceFlag = "--force"; $args = $args.RemoveRange(0, 1) }
        "-v" { $verboseFlag = "--verbose"; $args = $args.RemoveRange(0, 1) }
        "-r" { $roleArnFlag = "--role-arn $($args[1])"; $args = $args.RemoveRange(0, 2) }
        Default { Write-Host "Unknown argument: $arg"; $args = $args.RemoveRange(0, 1) }
    }
}

# Check if Chocolatey is installed
if (-not (Get-Command "choco" -ErrorAction SilentlyContinue)) {
    Write-Host "$($GreenColor)Installing Chocolatey...$($DefaultColor)"
    try {
        Set-ExecutionPolicy Bypass -Scope Process -Force
        Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
    } catch {
        Write-Host "$($RedColor)Error: Failed to install Chocolatey. Please install it manually and try again.$($DefaultColor)"
        Exit 1
    }
}

# Check if npm is installed
if (-not (Get-Command "npm" -ErrorAction SilentlyContinue)) {
    Write-Host "$($GreenColor)Installing npm...$($DefaultColor)"
    try {
        Invoke-Expression "choco install nodejs --confirm"
    } catch {
        Write-Host "$($RedColor)Error: Failed to install npm. Please install it manually and try again.$($DefaultColor)"
        Exit 1
    }
}

# Check if python3 is installed
if (-not (Get-Command "python3" -ErrorAction SilentlyContinue)) {
    Write-Host "$($GreenColor)Installing python3...$($DefaultColor)"
    try {
        Invoke-Expression "choco install python --confirm"
    } catch {
        Write-Host "$($RedColor)Error: Failed to install python3. Please install it manually and try again.$($DefaultColor)"
        Exit 1
    }
}

# Check if AWS CDK is installed
if (-not (Get-Command "cdk" -ErrorAction SilentlyContinue)) {
    Write-Host "$($GreenColor)Installing AWS CDK...$($DefaultColor)"
    try {
        Invoke-Expression "npm install -g aws-cdk"
    } catch {
        Write-Host "$($RedColor)Error: Failed to install AWS CDK. Please install it manually and try again.$($DefaultColor)"
        Exit 1
    }
}

# Check if jq is installed
if (-not (Get-Command "jq" -ErrorAction SilentlyContinue)) {
    Write-Host "$($GreenColor)Installing jq...$($DefaultColor)"
    try {
        Invoke-Expression "choco install jq --confirm"
    } catch {
        Write-Host "$($RedColor)Error: Failed to install jq. Please install it manually and try again.$($DefaultColor)"
        Exit 1
    }
}

# Check if AWS CLI is installed
if (-not (Get-Command "aws" -ErrorAction SilentlyContinue)) {
    Write-Host "$($GreenColor)Installing AWS CLI...$($DefaultColor)"
    try {
        $msiUrl = "https://awscli.amazonaws.com/AWSCLIV2.msi"
        $msiPath = Join-Path $env:TEMP "AWSCLIV2.msi"
        Invoke-WebRequest -Uri $msiUrl -OutFile $msiPath
        Start-Process -FilePath $msiPath -ArgumentList "/quiet" -Wait
        Remove-Item $msiPath
    } catch {
        Write-Host "$($RedColor)Error: Failed to install AWS CLI. Please install it manually and try again.$($DefaultColor)"
        Exit 1
    }
}

# Check if the virtual environment is activated
if ($null -eq $env:VIRTUAL_ENV) {
    # Virtual environment is not activated
    if (Test-Path ".\cdk\.venv") {
        # Virtual environment exists, but not activated
        Write-Host "$($DefaultColor)The virtual environment exists but is not activated."
        Write-Host "$($DefaultColor)To activate the virtual environment, run the following commands:"
        Write-Host ""
        Write-Host "$($GreenColor)cd cdk"
        Write-Host "$($GreenColor). .venv\Scripts\activate.ps1"
        Write-Host "$($GreenColor)cd .."
        Write-Host ""
        Write-Host "$($DefaultColor)Once this is complete, run the deploy command again"
    } else {
        # Virtual environment does not exist
        Write-Host "$($DefaultColor)The virtual environment does not exist."
        Write-Host "$($DefaultColor)To create and activate the virtual environment, run the following commands:"
        Write-Host ""
        Write-Host "$($GreenColor)cd cdk"
        Write-Host "$($GreenColor)python3 -m venv .venv"
        Write-Host "$($GreenColor). .venv\Scripts\activate.ps1"
        Write-Host "$($GreenColor)python3 -m pip install -r requirements.txt"
        Write-Host "$($GreenColor)cd .."
        Write-Host ""
        Write-Host "$($DefaultColor)Once this is complete, run the deploy command again"
    }
    Exit 1
}

# Read cognitoDomain from reference file, if it exists
if (Test-Path "cognitoDomain.ref") {
    $cognitoDomain = Get-Content "cognitoDomain.ref"
} else {
    # List all user pools
    $userPools = List-UserPools

    # Check if any existing user pool has a domain matching the expected format
    foreach ($userPoolId in $userPools) {
        $domain = Get-UserPoolDomain -UserPoolId $userPoolId
        if ($null -ne $domain -and $domain -match "^[a-z]+$") {
            $useExisting = Read-Host "An existing Cognito user pool domain '$domain' was found. Do you want to use it? (y/n)"
            if ($useExisting -match "[yY][eE][sS]|[yY]") {
                $cognitoDomain = $domain
                Set-Content -Path "cognitoDomain.ref" -Value $cognitoDomain
                break
            }
        }
    }
}

# Read cognitoDomain from reference file, if it exists
if (Test-Path "cognitoDomain.ref") {
    $cognitoDomain = Get-Content "cognitoDomain.ref"
} else {
    while ($true) {
        Write-Host "A cognito Domain is needed to create a new userpool. This name must be globally unique, if another user is already using this domain, this script will fail."
        $cognitoDomain = Read-Host "Enter a cognitoDomain (lowercase, no special characters, no numbers, and without the words 'cognito', 'aws', 'amazon')"
        # Validate cognitoDomain format
        if ($cognitoDomain -match "^[a-z]+$" -and $cognitoDomain -notmatch "cognito" -and $cognitoDomain -notmatch "aws" -and $cognitoDomain -notmatch "amazon") {
            Set-Content -Path "cognitoDomain.ref" -Value $cognitoDomain
            break
        } else {
            Write-Host "Error: cognitoDomain must be lowercase, contain no special characters, no numbers, and should not contain the words 'cognito', 'amazon', 'aws'."
        }
    }
}

Invoke-Expression ".\recreate-python-lambda-layer.ps1"

# Change to cdk Directory
Set-Location "cdk"
if (-not (Test-Path ".\static-website-source")) {
    # Create the directory if it doesn't exist
    Write-Host "Creating static-website-source directory..."
    New-Item -ItemType Directory -Path ".\static-website-source"
    New-Item -ItemType File -Path ".\static-website-source\placeholder.txt"
}

# Install Python dependencies
python3 -m pip install -r requirements.txt

# Check if CDK bootstrap has been completed
$bootstrapRefFile = "bootstrap.ref"

if (Test-Path $bootstrapRefFile) {
    Write-Host "Skipping CDK bootstrap process."
} else {
    $runBootstrap = Read-Host "Do you want to run cdk Bootstrap now (if you don't know, assume Yes)? (y/n)"
    if ($runBootstrap -match "[yY][eE][sS]|[yY]") {
        Write-Host "Running CDK bootstrap..."
        cdk bootstrap --require-approval never
        if ($LASTEXITCODE -eq 0) {
            Write-Host "CDK bootstrap completed successfully."
        } else {
            Write-Host "Failed to run CDK bootstrap."
            Exit 1
        }
    } else {
        Write-Host "Skipping CDK bootstrap process."
    }
}
New-Item -ItemType File -Path $bootstrapRefFile -Force

# Deploy the CDK app
cdk deploy --outputs-file outputs.json --parameters cognitoDomain="$cognitoDomain" --parameters allowlistDomain="$allowListDomain" --require-approval never $appFlag $contextFlag $debugFlag $profileFlag $tagsFlag $forceFlag $verboseFlag $roleArnFlag
if ($LASTEXITCODE -ne 0) {
    Write-Host "$($RedColor)Error: CDK deployment failed. Exiting script.$($DefaultColor)"
    Exit 1
}

#### START BUILDING REACT APP ####
# Check if outputs.json exists
if (-not (Test-Path ".\outputs.json")) {
    Write-Host "$($RedColor)Error: outputs.json file not found in the current directory.$($DefaultColor)"
    Exit 1
}

# Extract values from outputs.json
$websocketapiendpoint = (jq -r '.ChatbotWebsiteStack.websocketapiendpoint' ".\outputs.json")
$region = (jq -r '.ChatbotWebsiteStack.region' ".\outputs.json")
$userpoolid = (jq -r '.ChatbotWebsiteStack.userpoolid' ".\outputs.json")
$userpoolclientid = (jq -r '.ChatbotWebsiteStack.userpoolclientid' ".\outputs.json")
$awschatboturl = (jq -r '.ChatbotWebsiteStack.AWSChatBotURL' ".\outputs.json")

# Generate .\react-chatbot\src\variables.js
New-Item -ItemType Directory -Path ".\react-chatbot\src\" -Force

$variablesFile = ".\react-chatbot\src\variables.js"
$newVariablesContent = @"
const variables = {
  wsApiEndpoint: "$websocketapiendpoint",
  region: "$region",
  userPoolId: "$userpoolid",
  userPoolClientId: "$userpoolclientid",
  awsChatbotUrl: "$awschatboturl"
};

export default variables;
"@

if (Test-Path $variablesFile) {
    $existingContent = Get-Content $variablesFile -Raw
    if ($existingContent -ne $newVariablesContent) {
        Set-Content -Path $variablesFile -Value $newVariablesContent
        Write-Host "variables.js file updated."
    } else {
        Write-Host "variables.js file is up-to-date."
    }
} else {
    # File doesn't exist, create it
    Set-Content -Path $variablesFile -Value $newVariablesContent
    Write-Host "variables.js file created."
}

# Generate .\react-chatbot\src\config.json
$configFile = ".\react-chatbot\src\config.json"
$newConfigContent = @"
{
  "aws_project_region": "$region",
  "aws_cognito_region": "$region",
  "aws_user_pools_id": "$userpoolid",
  "aws_user_pools_web_client_id": "$userpoolclientid",
  "oauth": {},
  "aws_appsync_graphqlEndpoint": "https://$websocketapiendpoint/$region",
  "aws_appsync_apiKey": ""
}
"@

if (Test-Path $configFile) {
    $existingContent = Get-Content $configFile -Raw
    if ($existingContent -ne $newConfigContent) {
        Set-Content -Path $configFile -Value $newConfigContent
        Write-Host "config.json file updated."
    } else {
        Write-Host "config.json file is up-to-date."
    }
} else {
    # File doesn't exist, create it
    Set-Content -Path $configFile -Value $newConfigContent
    Write-Host "config.json file created."
}

Write-Host "Config files processed successfully!"

# Change to the cdk/react-chatbot directory
Set-Location ".\react-chatbot"

# Install dependencies and build the React application
npm install
if ($LASTEXITCODE -ne 0) {
    Write-Host "$($RedColor)Error: npm install failed. Exiting script.$($DefaultColor)"
    Exit 1
}
npm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "$($RedColor)Error: npm run build failed. Exiting script.$($DefaultColor)"
    Exit 1
}

# Go back to the parent directory
Set-Location ".."

cdk deploy --outputs-file outputs.json --parameters cognitoDomain="$cognitoDomain" --parameters allowlistDomain="$allowListDomain" --require-approval never $appFlag $contextFlag $debugFlag $profileFlag $tagsFlag $forceFlag $verboseFlag $roleArnFlag
if ($LASTEXITCODE -ne 0) {
    Write-Host "$($RedColor)Error: CDK deployment failed. Exiting script.$($DefaultColor)"
    Exit 1
}
Remove-Item "outputs.json"

Set-Location ".."
Write-Host "$($GreenColor)Deployment complete!$($DefaultColor)"
# tell user to visit the url: awschatboturl
Write-Host "$($GreenColor)Visit the chatbot here: ${awschatboturl}$($DefaultColor)"