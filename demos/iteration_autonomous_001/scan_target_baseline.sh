#!/bin/bash
# Phase 3: Target Tenant Baseline Scan
# Scan DefenderATEVET12 to establish baseline before deployment

set -e

# Load .env and export target tenant as main credentials
source .env

# Export TENANT_2 credentials as the main AZURE_* variables
export AZURE_TENANT_ID="$AZURE_TENANT_2_ID"
export AZURE_CLIENT_ID="$AZURE_TENANT_2_CLIENT_ID"
export AZURE_CLIENT_SECRET="$AZURE_TENANT_2_CLIENT_SECRET"
export AZURE_SUBSCRIPTION_ID="$AZURE_TENANT_2_SUBSCRIPTION_ID"

echo "=== Phase 3: Target Tenant Baseline Scan ==="
echo "Tenant: $AZURE_TENANT_2_NAME"
echo "Tenant ID: $AZURE_TENANT_ID"
echo "Subscription: $AZURE_SUBSCRIPTION_ID"
echo ""

# Run scan with target tenant credentials (uses env vars)
uv run atg scan \
  --no-dashboard \
  --generate-spec \
  2>&1 | tee demos/iteration_autonomous_001/logs/target_baseline_scan.log

echo ""
echo "✅ Target baseline scan complete!"
