#!/usr/bin/env bash
set -euxo pipefail

echo "========== [post-create.sh] START: $(date) =========="

trap 'echo "ERROR: post-create.sh failed at line $LINENO. Exiting."; exit 1' ERR

echo "[INFO] Creating and activating Python venv..."
python3.13 -m venv .venv
source .venv/bin/activate

echo "[INFO] Upgrading pip and installing core Python tools..."
pip install --upgrade pip
pip install uv pre-commit python-dotenv pytest

echo "[INFO] Syncing Python dependencies (using uv, fallback to pip)..."
if ! uv sync; then
  echo "[WARN] uv sync failed, falling back to pip install requirements.txt and requirements-dev.txt"
  pip install -r requirements.txt -r requirements-dev.txt || true
fi

echo "[INFO] Installing pre-commit hooks..."
pre-commit install || echo "[WARN] pre-commit install failed, continuing..."

echo "[INFO] Upgrading Bicep CLI via Azure CLI..."
az bicep upgrade || echo "[WARN] az bicep upgrade failed, continuing..."

# Install GitHub CLI (gh) if not present
if ! command -v gh &> /dev/null; then
  echo "[INFO] Installing GitHub CLI (gh)..."
  if ! type -p curl >/dev/null; then
    sudo apt-get update
    sudo apt-get install -y curl
  fi
  curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
  sudo chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
  sudo apt-get update
  sudo apt-get install -y gh
  echo "[INFO] GitHub CLI (gh) installed."
else
  echo "[INFO] GitHub CLI (gh) already installed."
fi

# Authenticate GitHub CLI if not already authenticated
if ! gh auth status &> /dev/null; then
  echo "[WARN] GitHub CLI is not authenticated. Please run 'gh auth login' to authenticate."
else
  echo "[INFO] GitHub CLI is already authenticated."
fi

echo "[INFO] Installing common CLI tools (jq, tree, unzip, less)..."
sudo apt-get update
sudo apt-get install -y jq tree unzip less

# Check for required environment variables (example: AZURE_TENANT_ID)
if [ -z "${AZURE_TENANT_ID:-}" ]; then
  echo "[WARN] AZURE_TENANT_ID environment variable is not set. Some Azure operations may fail."
fi

# Check for .env file and remind user if missing
if [ ! -f .env ]; then
  echo "[WARN] .env file not found in the project root. Please create and configure your .env file for local development."
fi

echo "[INFO] Printing useful environment info..."
python --version || echo "[WARN] python not found"
if command -v az &> /dev/null; then az version | jq -r .azure-cli; else echo "[WARN] Azure CLI not installed"; fi
if command -v gh &> /dev/null; then gh --version | head -n1; else echo "[WARN] GitHub CLI not installed"; fi
if command -v terraform &> /dev/null; then terraform --version | head -n1; else echo "[WARN] Terraform not installed"; fi
if command -v pwsh &> /dev/null; then pwsh --version; else echo "[WARN] PowerShell not installed"; fi
if command -v uv &> /dev/null; then uv --version; else echo "[WARN] uv not installed"; fi

echo "[INFO] Symlinking Azure CLI-managed Bicep binary to /usr/local/bin/bicep (if needed)..."
BICEP_PATH="$(az bicep version --query path -o tsv 2>/dev/null || true)"
if [ -n "$BICEP_PATH" ] && [ ! -f /usr/local/bin/bicep ]; then
  sudo ln -s "$BICEP_PATH" /usr/local/bin/bicep
  echo "[INFO] Symlinked $BICEP_PATH to /usr/local/bin/bicep"
fi

echo "[INFO] Ensuring user is in the docker group..."
if ! groups | grep -q docker; then
  sudo usermod -aG docker $USER
  echo "[INFO] Added $USER to docker group. You may need to restart the container or shell for this to take effect."
fi

echo "[INFO] Verifying Docker-in-Docker availability..."
if ! docker info >/dev/null 2>&1; then
  echo "[ERROR] Docker is not running or not available in the container."
  exit 1
else
  echo "[INFO] Docker-in-Docker is available."
fi

echo "[INFO] Verifying Bicep CLI installation..."
if ! az bicep version >/dev/null 2>&1; then
  echo "[ERROR] Bicep CLI is not installed or not available via Azure CLI."
  exit 1
else
  echo "[INFO] Bicep CLI is ready."
  az bicep version
fi

echo "========== [post-create.sh] END: $(date) =========="
