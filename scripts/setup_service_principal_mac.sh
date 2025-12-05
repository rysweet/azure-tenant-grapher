#!/bin/bash
set -euo pipefail

# setup_service_principal_mac.sh
# Automated service principal creation with CORRECT permissions for Azure Tenant Grapher
# macOS-compatible version (uses 'sed' instead of 'head -n -1')
#
# Creates SP with:
# - Contributor (for resource management)
# - Security Reader (for role assignment scanning)
# - Owner (for deploying resources with role assignments)
#
# Usage:
#   ./scripts/setup_service_principal.sh <TENANT_NAME> <TENANT_ID> [SUBSCRIPTION_ID]
#
# Prerequisites:
# - Azure CLI installed
# - Logged in as Global Admin: az login --tenant <TENANT_ID>
# - jq installed

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $*"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# Validate arguments
if [ $# -lt 2 ]; then
    echo "Usage: $0 <TENANT_NAME> <TENANT_ID> [SUBSCRIPTION_ID]"
    echo ""
    echo "Example:"
    echo "  $0 DefenderATEVET17 3cd87a41-1f61-4aef-a212-cefdecd9a2d1"
    echo ""
    echo "Prerequisites:"
    echo "  - Logged in as Global Admin: az login --tenant <TENANT_ID>"
    echo "  - jq installed: apt-get install jq"
    exit 1
fi

TENANT_NAME="$1"
TENANT_ID="$2"
SUBSCRIPTION_ID="${3:-$(az account show --query id -o tsv)}"

log_info "Setting up Service Principal for Azure Tenant Grapher"
log_info "Tenant: $TENANT_NAME ($TENANT_ID)"
log_info "Subscription: $SUBSCRIPTION_ID"
echo ""

# Step 1: Create app registration and service principal
log_info "Step 1: Creating app registration and service principal..."
APP_JSON=$(az ad app create --display-name "azure-tenant-grapher-${TENANT_NAME}" --output json)
APP_ID=$(echo "$APP_JSON" | jq -r '.appId')

SP_JSON=$(az ad sp create --id "$APP_ID" --output json)
SP_OBJECT_ID=$(echo "$SP_JSON" | jq -r '.id')

CRED_JSON=$(az ad app credential reset --id "$APP_ID" --years 1 --output json)
CLIENT_SECRET=$(echo "$CRED_JSON" | jq -r '.password')

log_success "Service principal created"
log_info "   App ID: $APP_ID"
log_info "   Object ID: $SP_OBJECT_ID"
echo ""

# Step 2: Elevate Global Admin access
log_info "Step 2: Elevating Global Admin access to User Access Administrator..."
TOKEN=$(az account get-access-token --resource https://management.azure.com --query accessToken -o tsv)

ELEVATE_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
  "https://management.azure.com/providers/Microsoft.Authorization/elevateAccess?api-version=2016-07-01" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Length: 0")

HTTP_CODE=$(echo "$ELEVATE_RESPONSE" | tail -n 1)
if [ "$HTTP_CODE" = "200" ]; then
    log_success "Access elevated successfully"
else
    log_warning "Elevation returned HTTP $HTTP_CODE (may already be elevated)"
fi

log_info "Waiting 20 seconds for permission propagation..."
sleep 20
log_success "Permission propagation complete"
echo ""

# Step 3: Assign Contributor role
log_info "Step 3: Assigning Contributor role (for resource management)..."
ROLE_DEF_ID=$(az role definition list --name "Contributor" --query "[0].id" -o tsv)
UUID_CONTRIBUTOR=$(uuidgen)
TOKEN=$(az account get-access-token --resource https://management.azure.com --query accessToken -o tsv)

CONTRIBUTOR_RESPONSE=$(curl -s -w "\n%{http_code}" -X PUT \
  "https://management.azure.com/subscriptions/${SUBSCRIPTION_ID}/providers/Microsoft.Authorization/roleAssignments/${UUID_CONTRIBUTOR}?api-version=2022-04-01" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"properties\":{\"roleDefinitionId\":\"${ROLE_DEF_ID}\",\"principalId\":\"${SP_OBJECT_ID}\",\"principalType\":\"ServicePrincipal\"}}")

HTTP_CODE=$(echo "$CONTRIBUTOR_RESPONSE" | tail -n 1)
if [ "$HTTP_CODE" = "201" ] || [ "$HTTP_CODE" = "200" ]; then
    log_success "Contributor role assigned"
else
    log_error "Failed to assign Contributor role (HTTP $HTTP_CODE)"
    echo "$CONTRIBUTOR_RESPONSE" | sed '$d'
    exit 1
fi
echo ""

# Step 4: Assign Security Reader role (CRITICAL for role assignment scanning)
log_info "Step 4: Assigning Security Reader role (for role assignment scanning)..."
SECURITY_READER_DEF_ID=$(az role definition list --name "Security Reader" --query "[0].id" -o tsv)
UUID_SECURITY=$(uuidgen)
TOKEN=$(az account get-access-token --resource https://management.azure.com --query accessToken -o tsv)

SECURITY_RESPONSE=$(curl -s -w "\n%{http_code}" -X PUT \
  "https://management.azure.com/subscriptions/${SUBSCRIPTION_ID}/providers/Microsoft.Authorization/roleAssignments/${UUID_SECURITY}?api-version=2022-04-01" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"properties\":{\"roleDefinitionId\":\"${SECURITY_READER_DEF_ID}\",\"principalId\":\"${SP_OBJECT_ID}\",\"principalType\":\"ServicePrincipal\"}}")

HTTP_CODE=$(echo "$SECURITY_RESPONSE" | tail -n 1)
if [ "$HTTP_CODE" = "201" ] || [ "$HTTP_CODE" = "200" ]; then
    log_success "Security Reader role assigned"
else
    log_error "Failed to assign Security Reader role (HTTP $HTTP_CODE)"
    echo "$SECURITY_RESPONSE" | sed '$d'
    exit 1
fi
echo ""

# Step 5: Assign Owner role (CRITICAL for IaC deployment with role assignments)
log_info "Step 5: Assigning Owner role (for deploying resources with role assignments)..."
OWNER_DEF_ID=$(az role definition list --name "Owner" --query "[0].id" -o tsv)
UUID_OWNER=$(uuidgen)
TOKEN=$(az account get-access-token --resource https://management.azure.com --query accessToken -o tsv)

OWNER_RESPONSE=$(curl -s -w "\n%{http_code}" -X PUT \
  "https://management.azure.com/subscriptions/${SUBSCRIPTION_ID}/providers/Microsoft.Authorization/roleAssignments/${UUID_OWNER}?api-version=2022-04-01" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"properties\":{\"roleDefinitionId\":\"${OWNER_DEF_ID}\",\"principalId\":\"${SP_OBJECT_ID}\",\"principalType\":\"ServicePrincipal\"}}")

HTTP_CODE=$(echo "$OWNER_RESPONSE" | tail -n 1)
if [ "$HTTP_CODE" = "201" ] || [ "$HTTP_CODE" = "200" ]; then
    log_success "Owner role assigned"
else
    log_error "Failed to assign Owner role (HTTP $HTTP_CODE)"
    echo "$OWNER_RESPONSE" | sed '$d'
    log_warning "Deployment may fail when creating role assignments without Owner role"
fi
echo ""

# Step 6: Verify role assignments
log_info "Step 5: Verifying role assignments..."
sleep 10  # Allow Azure to propagate assignments

log_info "Role assignments for service principal:"
az role assignment list --assignee "$APP_ID" --output table

ROLE_COUNT=$(az role assignment list --assignee "$APP_ID" --query "length(@)" -o tsv)
if [ "$ROLE_COUNT" -ge 3 ]; then
    log_success "✅ Service principal has $ROLE_COUNT role(s) assigned (Contributor, Security Reader, Owner)"
else
    log_warning "⚠️  Expected 3 roles (Contributor, Security Reader, Owner), found $ROLE_COUNT"
    log_warning "⚠️  Deployment of role assignments may fail without Owner role"
fi
echo ""

# Step 7: Output credentials
log_success "=========================================="
log_success "SERVICE PRINCIPAL SETUP COMPLETE"
log_success "=========================================="
echo ""
echo "Add these to your .env file:"
echo ""
echo "AZURE_TENANT_ID=$TENANT_ID"
echo "AZURE_CLIENT_ID=$APP_ID"
echo "AZURE_CLIENT_SECRET=$CLIENT_SECRET"
echo "AZURE_SUBSCRIPTION_ID=$SUBSCRIPTION_ID"
echo ""
echo "Or for secondary tenant:"
echo ""
echo "AZURE_TENANT_2_ID=$TENANT_ID"
echo "AZURE_TENANT_2_CLIENT_ID=$APP_ID"
echo "AZURE_TENANT_2_CLIENT_SECRET=$CLIENT_SECRET"
echo "AZURE_TENANT_2_NAME=$TENANT_NAME"
echo ""
log_info "Test scan: uv run atg scan --tenant-id $TENANT_ID --no-dashboard --resource-limit 5"
log_info "Test deployment: uv run atg generate-iac --tenant-id $TENANT_ID --output /tmp/test-iac"
echo ""
log_success "🎉 Service principal ready with FULL permissions!"
log_success "   ✅ Contributor - Resource management"
log_success "   ✅ Security Reader - Role assignment scanning"
log_success "   ✅ Owner - Deploy resources with role assignments"
