#!/bin/bash
source .env
timeout 300 uv run atg scan \
  --tenant-id "$TENANT_1_TENANT_ID" \
  --resource-limit 100 \
  --no-container \
  --no-dashboard \
  --generate-spec
