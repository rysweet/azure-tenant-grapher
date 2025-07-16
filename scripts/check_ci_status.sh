#!/bin/bash
# This script checks the status of the latest GitHub Actions workflow run for the current branch.
# It automatically determines the latest run ID for the current branch and polls for its status.
# Exits with code 0 if the run is successful, or 1 otherwise.

set -e

# Get the current branch name
BRANCH_NAME=$(git rev-parse --abbrev-ref HEAD)
if [ -z "$BRANCH_NAME" ]; then
  echo "Error: Could not determine current branch."
  exit 1
fi

# Find the latest workflow run for the current branch using GitHub CLI
# We use --limit 10 for efficiency, but this can be increased if needed
RUN_ID=$(gh run list --limit 10 --json databaseId,headBranch,createdAt \
  | jq -r --arg branch "$BRANCH_NAME" '
      map(select(.headBranch == $branch)) 
      | sort_by(.createdAt) 
      | reverse 
      | .[0].databaseId // empty
    ')

if [ -z "$RUN_ID" ]; then
  echo "No workflow runs found for branch: $BRANCH_NAME"
  exit 1
fi

echo "Checking status for latest workflow run ID: $RUN_ID on branch: $BRANCH_NAME"

# Poll the workflow run status until it completes
while true; do
  STATUS=$(gh run view "$RUN_ID" --json status -q ".status")
  CONCLUSION=$(gh run view "$RUN_ID" --json conclusion -q ".conclusion")
  echo "Current status: $STATUS, conclusion: $CONCLUSION"
  if [[ "$STATUS" == "completed" ]]; then
    echo "Final conclusion: $CONCLUSION"
    gh run view "$RUN_ID" --log
    if [[ "$CONCLUSION" == "success" ]]; then
      exit 0
    else
      exit 1
    fi
  fi
  sleep 10
done
