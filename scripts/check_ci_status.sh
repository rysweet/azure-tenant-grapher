#!/bin/bash
# This script checks the status of the latest GitHub Actions workflow run for the current branch.
# It automatically determines the latest run ID for the current branch and polls for its status.
# Exits with code 0 if the run is successful, or 1 otherwise.
#
# Improvements:
# - Adds a summary line at the end: "CI STATUS: success" or "CI STATUS: failure"
# - Collapses repeated status lines, showing only the first, last, and a count of repeats
# - Adds comments to clarify logic

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

# Arrays to store status lines for collapsing repeats
declare -a status_lines
last_status=""
last_conclusion=""
repeat_count=0

# Poll the workflow run status until it completes
while true; do
  # Query current status and conclusion
  STATUS=$(gh run view "$RUN_ID" --json status -q ".status")
  CONCLUSION=$(gh run view "$RUN_ID" --json conclusion -q ".conclusion")
  line="Current status: $STATUS, conclusion: $CONCLUSION"

  # Only print the status line if it has changed since the last poll.
  # Collapse repeated status lines, showing only the first, last, and a count of repeats.
  if [[ "$line" == "$last_status" ]]; then
    ((repeat_count++))
  else
    if [[ $repeat_count -gt 0 ]]; then
      echo "(repeated $repeat_count times)"
      repeat_count=0
    fi
    if [[ -n "$last_status" ]]; then
      echo "$last_status"
    fi
    last_status="$line"
    echo "$line"
  fi

  # If completed, print the last status and summary, then exit
  if [[ "$STATUS" == "completed" ]]; then
    if [[ $repeat_count -gt 0 ]]; then
      echo "(repeated $repeat_count times)"
    fi
    echo "$line"
    echo "Final conclusion: $CONCLUSION"
    gh run view "$RUN_ID" --log
    if [[ "$CONCLUSION" == "success" ]]; then
      echo "CI STATUS: success"
      exit 0
    else
      echo "CI STATUS: failure"
      exit 1
    fi
  fi

  # Print a countdown before the next poll, regardless of status change.
  # This helps users see when the next check will occur.
  WAIT_SECONDS=10
  echo -n "Waiting"
  for ((i=WAIT_SECONDS; i>0; i--)); do
    echo -n " ${i}s..."
    sleep 1
  done
  echo ""
done
