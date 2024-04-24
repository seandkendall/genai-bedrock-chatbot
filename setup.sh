#!/bin/bash

# Check the operating system
if [[ "$(uname)" == "Darwin" ]]; then
  OS="macOS"
elif [[ "$(uname)" == "Linux" ]]; then
  OS="AWS CloudShell"
else
  OS="Other"
fi

# Function to check if a command is installed
command_exists() {
  command -v "$1" >/dev/null 2>&1
}

if [[ "$OS" == "macOS" ]]; then
  # macOS-specific installation steps

  # Check if Python is installed
  if ! command_exists python3; then
    read -p "Python is not installed. Do you want to install it? (y/n): " install_python
    case "$install_python" in
      y|Y)
        # Install Python (using Homebrew on macOS)
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        brew install python3
        ;;
      *)
        echo "Python is required. Please install Python and try again."
        exit 1
        ;;
    esac
  fi

  # Check if pip is installed
  if ! command_exists pip3; then
    read -p "pip is not installed. Do you want to install it? (y/n): " install_pip
    case "$install_pip" in
      y|Y)
        # Install pip (using Python's get-pip.py script)
        python3 -m ensurepip
        ;;
      *)
        echo "pip is required. Please install pip and try again."
        exit 1
        ;;
    esac
  fi

  # Check if Git is installed
  if ! command_exists git; then
    read -p "Git is not installed. Do you want to install it? (y/n): " install_git
    case "$install_git" in
      y|Y)
        # Install Git (using Homebrew on macOS)
        brew install git
        ;;
      *)
        echo "Git is required. Please install Git and try again."
        exit 1
        ;;
    esac
  fi

  # Check if Node.js is installed
  if ! command_exists node; then
    read -p "Node.js is not installed. Do you want to install it? (y/n): " install_node
    case "$install_node" in
      y|Y)
        # Install Node.js (using Homebrew on macOS)
        brew install node
        ;;
      *)
        echo "Node.js is required. Please install Node.js and try again."
        exit 1
        ;;
    esac
  fi

  # Check if AWS CLI is installed
  if ! command_exists aws; then
    read -p "AWS CLI is not installed. Do you want to install it? (y/n): " install_awscli
    case "$install_awscli" in
      y|Y)
        # Install AWS CLI (using the bundled installer on macOS)
        curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "AWSCLIV2.pkg"
        sudo installer -pkg AWSCLIV2.pkg -target /
        rm AWSCLIV2.pkg
        ;;
      *)
        echo "AWS CLI is required. Please install AWS CLI and try again."
        exit 1
        ;;
    esac
  fi
  
  # Check if jq is installed
  if ! command_exists jq; then
    read -p "jq is not installed. Do you want to install it? (y/n): " install_jq
    case "$install_jq" in
      y|Y)
        # Install jq (using Homebrew on macOS)
        brew install jq
        ;;
      *)
        echo "jq is required. Please install jq and try again."
        exit 1
        ;;
    esac
  fi

elif [[ "$OS" == "AWS CloudShell" ]]; then
  # AWS CloudShell-specific installation steps

  # Check if Python is installed
  if ! command_exists python3; then
    echo "Python is not installed. Please install Python and try again."
    exit 1
  fi

  # Check if pip is installed
  if ! command_exists pip3; then
    echo "pip is not installed. Please install pip and try again."
    exit 1
  fi

  # Check if Git is installed
  if ! command_exists git; then
    echo "Git is not installed. Please install Git and try again."
    exit 1
  fi

  # Check if Node.js is installed
  if ! command_exists node; then
    echo "Node.js is not installed. Please install Node.js and try again."
    exit 1
  fi

  # Check if AWS CLI is installed
  if ! command_exists aws; then
    echo "AWS CLI is not installed. Please install AWS CLI and try again."
    exit 1
  fi

  # Check if jq is installed
  if ! command_exists jq; then
    echo "jq is not installed. Please install jq and try again."
    exit 1
  fi

else
  echo "This script is currently designed to run on macOS and AWS CloudShell systems."
  echo "Please ensure you have the following tools installed manually on your system:"
  echo "- Python 3"
  echo "- pip"
  echo "- Git"
  echo "- Node.js"
  echo "- jq"
  echo "- AWS CLI (configured with your AWS credentials)"
  exit 0
fi

# Check if AWS CLI is configured
if ! aws configure list >/dev/null 2>&1; then
  echo "AWS CLI is not configured. Please configure AWS CLI using the following guide:"
  echo "https://docs.aws.amazon.com/cli/latest/userguide/getting-started-quickstart.html"
  exit 1
fi