#!/bin/bash
# Script to generate Terraform IaC from Neo4j graph

set -e

source .env

# Get target subscription ID from TENANT_2
TARGET_SUB_ID="${AZURE_TENANT_2_SUBSCRIPTION_ID:-unknown}"

echo "=========================================="
echo "Terraform IaC Generation"
echo "=========================================="
echo ""
echo "Source: Neo4j graph (populated from TENANT_1 scan)"
echo "Target: TENANT_2 (DefenderATEVET12)"
echo "Target Subscription: $TARGET_SUB_ID"
echo ""

# Create output directory
OUTPUT_DIR="demos/iteration_autonomous_001/terraform_output"
mkdir -p "$OUTPUT_DIR"

echo "Generating Terraform IaC..."
echo ""

# Generate with conflict detection, subnet auto-fix, and validation
uv run atg generate-iac \
  --format terraform \
  --output "$OUTPUT_DIR" \
  --check-conflicts \
  --auto-fix-subnets \
  --skip-name-validation \
  --resource-group-prefix "replicated-" \
  --target-subscription "$TARGET_SUB_ID" 2>&1 | tee demos/iteration_autonomous_001/logs/terraform_generation.log

echo ""
echo "=========================================="
echo "Generation Complete!"
echo "=========================================="
echo ""
echo "Output directory: $OUTPUT_DIR"
echo "Log file: demos/iteration_autonomous_001/logs/terraform_generation.log"
echo ""
echo "Next steps:"
echo "  cd $OUTPUT_DIR"
echo "  terraform init"
echo "  terraform plan"
echo "  terraform apply"

