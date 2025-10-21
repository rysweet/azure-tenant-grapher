#!/bin/bash
# Phase 4: Generate Terraform IaC from Neo4j graph

set -e

cd /home/azureuser/src/azure-tenant-grapher
source .env

echo "========================================"
echo "Phase 4: Terraform IaC Generation"
echo "========================================"
echo ""
echo "Source: Neo4j graph database"
echo "Resources in graph: 271"
echo "Target subscription: $AZURE_TENANT_2_SUBSCRIPTION_ID"
echo "Output directory: demos/iteration_autonomous_001/terraform_output"
echo ""

# Generate Terraform IaC
uv run atg generate-iac --format terraform --output demos/iteration_autonomous_001/terraform_output --target-subscription "$AZURE_TENANT_2_SUBSCRIPTION_ID" --auto-fix-subnets --skip-name-validation --no-fail-on-conflicts --resource-group-prefix "replicated-"

echo ""
echo "========================================"
echo "Terraform Generation Complete!"
echo "========================================"
