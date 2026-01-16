#!/bin/bash
# Deploy Azure Lighthouse Delegation to Customer Tenant
# This script must be run by a user with Owner or User Access Administrator role in the customer tenant

set -e

# Configuration
MANAGING_TENANT_ID="your-managing-tenant-id"
CUSTOMER_TENANT_ID="customer-tenant-id"
SUBSCRIPTION_ID="customer-subscription-id"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Azure Lighthouse Delegation Deployment ===${NC}"
echo ""

# Check if logged in
echo "Checking Azure CLI authentication..."
az account show > /dev/null 2>&1 || {
    echo -e "${RED}Error: Not logged in to Azure CLI${NC}"
    echo "Please run: az login --tenant $CUSTOMER_TENANT_ID"
    exit 1
}

# Verify correct tenant
CURRENT_TENANT=$(az account show --query tenantId -o tsv)
if [ "$CURRENT_TENANT" != "$CUSTOMER_TENANT_ID" ]; then
    echo -e "${YELLOW}Warning: Logged in to wrong tenant${NC}"
    echo "Current tenant: $CURRENT_TENANT"
    echo "Expected tenant: $CUSTOMER_TENANT_ID"
    echo ""
    echo "Switching tenant..."
    az login --tenant $CUSTOMER_TENANT_ID
fi

# Set subscription context
echo "Setting subscription context..."
az account set --subscription $SUBSCRIPTION_ID

# Validate Bicep template
echo "Validating Bicep template..."
az bicep build --file lighthouse-delegation.bicep

# Deploy at subscription level
echo ""
echo -e "${GREEN}Deploying Lighthouse delegation...${NC}"
echo "Managing Tenant ID: $MANAGING_TENANT_ID"
echo "Customer Tenant ID: $CUSTOMER_TENANT_ID"
echo "Subscription ID: $SUBSCRIPTION_ID"
echo ""

az deployment sub create \
    --location eastus \
    --template-file lighthouse-delegation.bicep \
    --parameters lighthouse-parameters.json \
    --parameters managingTenantId=$MANAGING_TENANT_ID \
    --name "sentinel-lighthouse-$(date +%Y%m%d-%H%M%S)" \
    --verbose

echo ""
echo -e "${GREEN}✓ Deployment complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Verify delegation in Azure portal (Service Providers blade)"
echo "2. Login to managing tenant to test access"
echo "3. Run cross-tenant query to verify permissions"
echo ""
