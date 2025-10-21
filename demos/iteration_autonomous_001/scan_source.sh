#!/bin/bash

# Load .env file
source .env

# Set environment for TENANT_1 (DefenderATEVET17 - Source)
export AZURE_TENANT_ID="$AZURE_TENANT_1_ID"
export AZURE_CLIENT_ID="$AZURE_TENANT_1_CLIENT_ID"
export AZURE_CLIENT_SECRET="$AZURE_TENANT_1_CLIENT_SECRET"

# Run the scan
uv run atg scan --no-container --no-dashboard --generate-spec
