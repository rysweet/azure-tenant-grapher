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

# Get repo and branch
REPO=$(git config --get remote.origin.url | sed -E 's#.*github.com[:/](.*)\.git#\1#')
BRANCH=$(git rev-parse --abbrev-ref HEAD)

echo "Creating Codespace for $REPO on branch $BRANCH..."

# Create Codespace and capture name
CODESPACE=$(gh codespace create -R "$REPO" -b "$BRANCH" --json name -q .name)
if [ -z "$CODESPACE" ]; then
  echo "Failed to create Codespace."
  exit 1
fi
echo "Created Codespace: $CODESPACE"

# Wait for Codespace to be 'Available'
echo "Waiting for Codespace to be provisioned..."
while true; do
  STATE=$(gh codespace list --json name,state -q ".[] | select(.name==\"$CODESPACE\") | .state")
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
echo "Running setup instructions in Codespace..."
gh codespace ssh -c "$CODESPACE" -- 'uv sync || pip install -r requirements.txt || true && cd dotnet && dotnet restore || true'

echo "Setup complete."
