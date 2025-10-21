#!/bin/bash
# Phase 4: Deploy Terraform to Target Tenant
# Deploy generated IaC to DefenderATEVET12

set -e

# Load .env and set target tenant credentials
source /home/azureuser/src/azure-tenant-grapher/.env

# Export TENANT_2 credentials for Terraform
export ARM_TENANT_ID="$AZURE_TENANT_2_ID"
export ARM_SUBSCRIPTION_ID="$AZURE_TENANT_2_SUBSCRIPTION_ID"
export ARM_CLIENT_ID="$AZURE_TENANT_2_CLIENT_ID"
export ARM_CLIENT_SECRET="$AZURE_TENANT_2_CLIENT_SECRET"

echo "=== Phase 4: Deploy Terraform to Target Tenant ==="
echo "Target Tenant: $AZURE_TENANT_2_NAME"
echo "Target Subscription: $ARM_SUBSCRIPTION_ID"
echo ""

cd /home/azureuser/src/azure-tenant-grapher/demos/iteration_autonomous_001/terraform

# Check if Terraform is initialized
if [ ! -d ".terraform" ]; then
    echo "Initializing Terraform..."
    terraform init
fi

echo ""
echo "Running Terraform plan..."
terraform plan -out=tfplan 2>&1 | tee ../logs/terraform_plan.log

echo ""
echo "📋 Terraform plan saved to tfplan"
echo "Review the plan in logs/terraform_plan.log"
echo ""
echo "To apply: cd demos/iteration_autonomous_001/terraform && terraform apply tfplan"
