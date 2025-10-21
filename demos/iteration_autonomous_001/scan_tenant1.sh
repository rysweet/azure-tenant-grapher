#!/bin/bash
# Scan source tenant (Tenant 1 - Primary / DefenderATEVET17)

set -euo pipefail

# Load .env file safely
if [ -f .env ]; then
    export $(grep -v '^#' .env | grep -v '^\s*$' | xargs)
fi

# Set tenant 1 as active
export AZURE_TENANT_ID="$AZURE_TENANT_1_ID"
export AZURE_CLIENT_ID="$AZURE_TENANT_1_CLIENT_ID"
export AZURE_CLIENT_SECRET="$AZURE_TENANT_1_CLIENT_SECRET"

echo "=== Scanning Source Tenant ==="
echo "Tenant ID: $AZURE_TENANT_ID"
echo "Tenant Name: $AZURE_TENANT_1_NAME"
echo

# Run the scan
uv run atg scan --no-dashboard --generate-spec
