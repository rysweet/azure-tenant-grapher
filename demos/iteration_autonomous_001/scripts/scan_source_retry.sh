#!/bin/bash
# Retry Source Tenant Scan (DefenderATEVET17) - Phase 2 Retry
# Created: 2025-10-20 (Autonomous Demo - Retry after stall)
# Reason: First scan stalled at 21% (348/1632 resources)

set -euo pipefail

source .env

echo "=== Phase 2 RETRY: Source Tenant Discovery ==="
echo "Tenant: TENANT_1 (DefenderATEVET17 - Primary)"
echo "Expected: 1,632 resources"
echo "Previous attempt: Stalled at 348 resources (21%)"
echo "Timestamp: $(date -Iseconds)"
echo ""

# Set environment for TENANT_1
export AZURE_TENANT_ID="${AZURE_TENANT_ID_TENANT_1}"
export AZURE_CLIENT_ID="${AZURE_CLIENT_ID_TENANT_1}"
export AZURE_CLIENT_SECRET="${AZURE_CLIENT_SECRET_TENANT_1}"

echo "Tenant ID: ${AZURE_TENANT_ID:0:8}..."
echo "Client ID: ${AZURE_CLIENT_ID:0:8}..."
echo "Neo4j: Port 7688, database cleared"
echo ""

# Create retry log directory
mkdir -p demos/iteration_autonomous_001/logs

echo "Starting source tenant scan (RETRY)..."
echo "Log: demos/iteration_autonomous_001/logs/source_scan_retry.log"
echo ""

# Run scan with:
# - no-dashboard for line-by-line output
# - generate-spec to auto-create tenant spec
# - explicit credentials
# - verbose logging
# - output to dedicated retry log
uv run atg scan \
    --tenant-id "$AZURE_TENANT_ID" \
    --client-id "$AZURE_CLIENT_ID" \
    --client-secret "$AZURE_CLIENT_SECRET" \
    --no-dashboard \
    --generate-spec \
    2>&1 | tee demos/iteration_autonomous_001/logs/source_scan_retry.log

EXIT_CODE=${PIPESTATUS[0]}

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Source tenant scan completed successfully!"
    echo ""
    echo "Next steps:"
    echo "1. Verify Neo4j: docker exec azure-tenant-grapher-neo4j cypher-shell -u neo4j -p \$NEO4J_PASSWORD 'MATCH (n) RETURN count(n);'"
    echo "2. Check spec: ls -lh specs/*.yaml"
    echo "3. Proceed to Phase 3: Target tenant baseline scan"
else
    echo "❌ Scan failed with exit code: $EXIT_CODE"
    echo "Check log: demos/iteration_autonomous_001/logs/source_scan_retry.log"
    exit $EXIT_CODE
fi
