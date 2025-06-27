#!/bin/bash
# Usage: ./scripts/check_ci_status.sh <run_id>
# Example: ./scripts/check_ci_status.sh 15932713219

RUN_ID="$1"
if [ -z "$RUN_ID" ]; then
  echo "Usage: $0 <run_id>"
  exit 1
fi

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
