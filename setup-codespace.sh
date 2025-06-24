#!/bin/bash
#
# setup-codespace.sh
#
# Automates the creation and setup of a GitHub Codespace for this repository.
#
# Features:
# - Creates a new Codespace for the current repo and branch using the GitHub CLI.
# - Waits for the Codespace to finish provisioning.
# - Copies your local .env file into the Codespace workspace.
# - Opens the Codespace in VS Code Insiders (requires code-insiders installed).
# - Runs install/setup instructions inside the Codespace (uv sync, pip install, dotnet restore).
#
# Requirements:
# - gh CLI (https://cli.github.com/) authenticated with "codespace" scope.
# - code-insiders (VS Code Insiders) installed locally.
# - .env file present in the current directory (optional).
#
# Usage:
#   bash setup-codespace.sh
#
# This script is intended to be run from the root of your project directory.
# It streamlines onboarding and ensures your Codespace is ready for development.
#

# Ensure GitHub CLI (gh) is installed
if ! command -v gh &> /dev/null; then
  echo "GitHub CLI (gh) not found. Installing..."
  type -p curl >/dev/null || (sudo apt update && sudo apt install curl -y)
  curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
  sudo chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
  sudo apt update
  sudo apt install gh -y
fi

# Get repo and branch
REPO=$(git config --get remote.origin.url | sed -E 's#.*github.com[:/](.*)\.git#\1#')
BRANCH=$(git rev-parse --abbrev-ref HEAD)

echo "Creating Codespace for $REPO on branch $BRANCH..."

# Create Codespace (no --json for compatibility)
echo "Requesting Codespace creation..."
gh codespace create -R "$REPO" -b "$BRANCH"

# Find the most recently created Codespace for this repo/branch
echo "Locating the new Codespace..."
CODESPACE=""
for i in {1..12}; do
  # Get the most recent codespace for this repo in Available or Provisioning state
  CODESPACE=$(gh codespace list --json name,repository,state,createdAt --limit 10 | \
    jq -r --arg repo "$REPO" --arg branch "$BRANCH" '
      map(select(.repository == $repo and (.state == "Available" or .state == "Provisioning")))
      | sort_by(.createdAt) | reverse | .[0].name // empty
    ')
  if [ -n "$CODESPACE" ]; then
    echo "Found Codespace: $CODESPACE"
    break
  fi
  echo "Waiting for Codespace to appear in list..."
  sleep 5
done

if [ -z "$CODESPACE" ]; then
  echo "Failed to locate the new Codespace."
  exit 1
fi

# Wait for Codespace to be 'Available'
echo "Waiting for Codespace to be provisioned..."
while true; do
  STATE=$(gh codespace list --json name,state | jq -r ".[] | select(.name==\"$CODESPACE\") | .state")
  echo "Current state: $STATE"
  if [ "$STATE" = "Available" ]; then
    break
  fi
  sleep 10
done

# Copy .env into Codespace
if [ -f .env ]; then
  echo "Copying .env into Codespace..."
  gh codespace cp .env remote:. -c "$CODESPACE"
else
  echo "No .env file found in current directory."
fi

# Open Codespace in VS Code Insiders, fallback to VS Code if not available
echo "Opening Codespace in VS Code..."
if command -v code-insiders >/dev/null 2>&1; then
  code-insiders --folder-uri "vscode-remote://codespaces+$CODESPACE" &
elif command -v code >/dev/null 2>&1; then
  code --folder-uri "vscode-remote://codespaces+$CODESPACE" &
else
  echo "Neither code-insiders nor code (VS Code) is installed. Please install one to open the Codespace."
fi

# Run install/setup instructions inside Codespace
echo "Setup complete. Please run any required install/setup commands inside your Codespace terminal after it opens."
