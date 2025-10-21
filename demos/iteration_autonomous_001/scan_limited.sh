#!/bin/bash
# Limited scan for demo (100 resources)
set -euo pipefail

if [ -f .env ]; then
    export $(grep -v '^#' .env | grep -v '^\s*$' | xargs)
fi

export AZURE_TENANT_ID="$AZURE_TENANT_1_ID"
export AZURE_CLIENT_ID="$AZURE_TENANT_1_CLIENT_ID"
export AZURE_CLIENT_SECRET="$AZURE_TENANT_1_CLIENT_SECRET"

echo "=== Scanning Source Tenant (LIMITED: 100 resources) ==="
echo "Tenant: $AZURE_TENANT_1_NAME ($AZURE_TENANT_ID)"
echo

uv run atg scan --no-dashboard --resource-limit 100 --generate-spec
