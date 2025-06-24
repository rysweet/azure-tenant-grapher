#!/usr/bin/env bash
set -e

# Create and activate Python venv
python3.13 -m venv .venv
source .venv/bin/activate

# Upgrade pip and install core tools
pip install --upgrade pip
pip install uv pre-commit python-dotenv pytest

# Sync dependencies (fallback to pip if uv fails)
uv sync || pip install -r requirements.txt -r requirements-dev.txt || true

# Install pre-commit hooks
pre-commit install

# Restore .NET dependencies (if dotnet folder exists)
if [ -d "dotnet" ]; then
  cd dotnet && dotnet restore || true
  cd ..
fi

# Upgrade Bicep CLI via Azure CLI
az bicep upgrade

# Install GitHub CLI (gh) if not present
if ! command -v gh &> /dev/null; then
  echo "Installing GitHub CLI (gh)..."
  type -p curl >/dev/null || sudo apt-get update && sudo apt-get install -y curl
  curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
  sudo chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
  sudo apt-get update
  sudo apt-get install -y gh
else
  echo "GitHub CLI (gh) already installed."
fi

# Authenticate GitHub CLI if not already authenticated
if ! gh auth status &> /dev/null; then
  echo "GitHub CLI is not authenticated. Please run 'gh auth login' to authenticate."
else
  echo "GitHub CLI is already authenticated."
fi

# Install common CLI tools for dev convenience
sudo apt-get update
sudo apt-get install -y jq tree unzip less

# Check for required environment variables (example: AZURE_TENANT_ID)
if [ -z "$AZURE_TENANT_ID" ]; then
  echo "Warning: AZURE_TENANT_ID environment variable is not set. Some Azure operations may fail."
fi

# Check for .env file and remind user if missing
if [ ! -f .env ]; then
  echo "Warning: .env file not found in the project root. Please create and configure your .env file for local development."
fi

# Print useful environment info
python --version
if command -v dotnet &> /dev/null; then dotnet --version; else echo "dotnet not installed"; fi
if command -v node &> /dev/null; then node --version; else echo "node not installed"; fi
if command -v az &> /dev/null; then az version | jq -r .azure-cli; else echo "Azure CLI not installed"; fi
if command -v gh &> /dev/null; then gh --version | head -n1; else echo "GitHub CLI not installed"; fi
