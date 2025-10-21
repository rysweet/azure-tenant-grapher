#!/bin/bash
# Script to scan TARGET_2 (DefenderATEVET12) - baseline before replication

set -e

source .env

export AZURE_CLIENT_ID="$TENANT_2_AZURE_CLIENT_ID"
export AZURE_CLIENT_SECRET="$TENANT_2_AZURE_CLIENT_SECRET"
export AZURE_TENANT_ID="$TENANT_2_AZURE_TENANT_ID"

echo "Starting TARGET_2 baseline scan (DefenderATEVET12)..."
echo "Tenant ID: $AZURE_TENANT_ID"

# Run scan with dashboard disabled for clean output
uv run atg scan --no-dashboard --label "target-baseline"

echo "Target baseline scan complete!"
