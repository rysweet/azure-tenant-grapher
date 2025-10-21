#!/bin/bash
# Phase 3: Target tenant baseline scan (FINAL FIX)

set -e
source .env

# Use CORRECT variable names from .env
export AZURE_CLIENT_ID="$AZURE_TENANT_2_CLIENT_ID"
export AZURE_CLIENT_SECRET="$AZURE_TENANT_2_CLIENT_SECRET"
export AZURE_TENANT_ID="$AZURE_TENANT_2_ID"

echo "=========================================="
echo "Phase 3: Target Baseline Scan (FINAL)"
echo "=========================================="
echo ""
echo "Tenant: $AZURE_TENANT_2_NAME"
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
  > demos/iteration_autonomous_001/logs/target_baseline_scan_final.log 2>&1 &

SCAN_PID=$!
echo "✅ Target baseline scan started with PID: $SCAN_PID"
echo "Log: demos/iteration_autonomous_001/logs/target_baseline_scan_final.log"

