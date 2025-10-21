#!/bin/bash
# Phase 4: Generate Terraform IaC
# Generate Terraform from source tenant graph (in Neo4j)

set -e

# Load .env and set source tenant credentials (to read from Neo4j)
source .env

export AZURE_TENANT_ID="$AZURE_TENANT_1_ID"
export AZURE_CLIENT_ID="$AZURE_TENANT_1_CLIENT_ID"
export AZURE_CLIENT_SECRET="$AZURE_TENANT_1_CLIENT_SECRET"
export AZURE_SUBSCRIPTION_ID="$AZURE_TENANT_1_SUBSCRIPTION_ID"

echo "=== Phase 4: Generate Terraform IaC ==="
echo "Reading from: Neo4j graph (source tenant: $AZURE_TENANT_1_NAME)"
echo "Target subscription: $AZURE_TENANT_2_SUBSCRIPTION_ID"
echo "Output: demos/iteration_autonomous_001/terraform/"
echo ""

# Generate Terraform - skip subnet validation due to empty VNet address spaces in source data
# This is a known gap: VNet address spaces not captured during scan
uv run atg generate-iac \
  --format terraform \
  --target-subscription "$AZURE_TENANT_2_SUBSCRIPTION_ID" \
  --output demos/iteration_autonomous_001/terraform \
  --skip-subnet-validation \
  --location eastus \
  2>&1 | tee demos/iteration_autonomous_001/logs/generate_iac.log

echo ""
echo "✅ Terraform generation complete!"
