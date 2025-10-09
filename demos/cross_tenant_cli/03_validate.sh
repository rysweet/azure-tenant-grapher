#!/bin/bash
# Demo script for validating deployment between source and target tenants
# This script demonstrates the validate-deployment command

set -e

echo "=========================================="
echo "Cross-Tenant Deployment Validation Demo"
echo "=========================================="
echo ""

# Example tenant IDs - replace with your actual tenant IDs
SOURCE_TENANT_ID="${SOURCE_TENANT_ID:-3cd87a41-1f61-4aef-a212-cefdecd9a2d1}"
TARGET_TENANT_ID="${TARGET_TENANT_ID:-506f82b2-e2e7-40a2-b0be-ea6f8cb908f8}"

echo "Source Tenant: $SOURCE_TENANT_ID"
echo "Target Tenant: $TARGET_TENANT_ID"
echo ""

# Check if Neo4j is running
echo "Checking Neo4j connection..."
if ! docker ps | grep -q neo4j; then
    echo "Warning: Neo4j container not running. Starting it..."
    docker start azure-tenant-grapher-neo4j || echo "Could not start Neo4j. Please start it manually."
fi
echo ""

# Basic validation
echo "=== Basic Validation ==="
echo "Comparing graphs between source and target tenants..."
echo ""

uv run atg validate-deployment \
  --source-tenant-id "$SOURCE_TENANT_ID" \
  --target-tenant-id "$TARGET_TENANT_ID" \
  --output validation-report.md

echo ""
echo "=== Validation Report Preview ==="
head -n 30 validation-report.md
echo ""
echo "... (see validation-report.md for full report)"
echo ""

# Validation with filters
echo "=== Validation with Filters ==="
echo "Comparing specific resource groups..."
echo ""

uv run atg validate-deployment \
  --source-tenant-id "$SOURCE_TENANT_ID" \
  --target-tenant-id "$TARGET_TENANT_ID" \
  --source-filter "resourceGroup=Production" \
  --target-filter "resourceGroup=Staging" \
  --output filtered-validation-report.md

echo ""
echo "Filtered validation complete!"
echo ""

# JSON output
echo "=== JSON Output Format ==="
echo "Generating validation report in JSON format..."
echo ""

uv run atg validate-deployment \
  --source-tenant-id "$SOURCE_TENANT_ID" \
  --target-tenant-id "$TARGET_TENANT_ID" \
  --format json \
  --output validation.json

echo ""
echo "JSON report generated: validation.json"
cat validation.json | python -m json.tool | head -n 20
echo ""

echo "=========================================="
echo "Demo Complete!"
echo "=========================================="
echo ""
echo "Generated files:"
echo "  - validation-report.md (full validation report)"
echo "  - filtered-validation-report.md (filtered comparison)"
echo "  - validation.json (JSON format)"
echo ""
echo "Next steps:"
echo "  1. Review validation reports to identify discrepancies"
echo "  2. Use filters to compare specific resource groups or scopes"
echo "  3. Integrate validation into CI/CD pipelines"
echo ""
