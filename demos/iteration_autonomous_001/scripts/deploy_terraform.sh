#!/bin/bash
# Script to deploy Terraform IaC to target tenant

set -e

source .env

# Set Azure credentials for TENANT_2
export ARM_CLIENT_ID="$TENANT_2_AZURE_CLIENT_ID"
export ARM_CLIENT_SECRET="$TENANT_2_AZURE_CLIENT_SECRET"
export ARM_TENANT_ID="$TENANT_2_AZURE_TENANT_ID"
export ARM_SUBSCRIPTION_ID="${AZURE_TENANT_2_SUBSCRIPTION_ID:-unknown}"

TERRAFORM_DIR="demos/iteration_autonomous_001/terraform_output"

echo "=========================================="
echo "Terraform Deployment"
echo "=========================================="
echo ""
echo "Target: TENANT_2 (DefenderATEVET12)"
echo "Subscription: $ARM_SUBSCRIPTION_ID"
echo "Terraform directory: $TERRAFORM_DIR"
echo ""

if [ ! -d "$TERRAFORM_DIR" ]; then
    echo "❌ ERROR: Terraform directory not found!"
    echo "Please run generate_terraform.sh first."
    exit 1
fi

cd "$TERRAFORM_DIR"

echo "Step 1: Terraform Init"
echo "----------------------"
terraform init 2>&1 | tee ../logs/terraform_init.log
echo ""

echo "Step 2: Terraform Plan"
echo "----------------------"
terraform plan -out=tfplan 2>&1 | tee ../logs/terraform_plan.log
echo ""

echo "Step 3: Terraform Apply"
echo "-----------------------"
echo "⚠️  This will deploy resources to Azure!"
read -p "Continue with deployment? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Deployment cancelled."
    exit 0
fi

terraform apply tfplan 2>&1 | tee ../logs/terraform_apply.log

echo ""
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="

