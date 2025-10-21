#!/bin/bash

# Load .env file
source .env

# Set environment for TENANT_2 (DefenderATEVET12 - Target)
export AZURE_TENANT_ID="$AZURE_TENANT_2_ID"
export AZURE_CLIENT_ID="$AZURE_TENANT_2_CLIENT_ID"
export AZURE_CLIENT_SECRET="$AZURE_TENANT_2_CLIENT_SECRET"

# Run the target baseline scan
uv run atg scan --no-container --no-dashboard --generate-spec
