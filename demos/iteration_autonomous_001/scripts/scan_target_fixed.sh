#!/bin/bash
# Phase 3: Target tenant baseline scan (PROPERLY FIXED)

set -e
source .env

# Set credentials properly
export AZURE_CLIENT_ID="$TENANT_2_AZURE_CLIENT_ID"
export AZURE_CLIENT_SECRET="$TENANT_2_AZURE_CLIENT_SECRET"
export AZURE_TENANT_ID="$TENANT_2_AZURE_TENANT_ID"

echo "=========================================="
echo "Phase 3: Target Baseline Scan"
echo "=========================================="
echo ""
echo "Tenant ID: $AZURE_TENANT_ID"
echo "Client ID: ${AZURE_CLIENT_ID:0:8}..."
echo "Subscription: $AZURE_TENANT_2_SUBSCRIPTION_ID"
echo ""

if [ -z "$AZURE_TENANT_ID" ]; then
    echo "❌ ERROR: AZURE_TENANT_ID is not set!"
    exit 1
fi

# Run scan
nohup uv run atg scan \
  --no-dashboard \
  --no-container \
  > demos/iteration_autonomous_001/logs/target_baseline_scan.log 2>&1 &

SCAN_PID=$!
echo "✅ Scan started with PID: $SCAN_PID"

