# Automated Service Principal Setup (CLI-Only)

## Overview

This document describes the fully automated, CLI-only approach for creating and configuring service principals for Azure Tenant Grapher cross-tenant operations. **No Azure Portal access required.**

## Problem Statement

Global Admins in Entra ID do not automatically have Azure RBAC permissions (Contributor, Owner, etc.) to perform resource operations. This creates a chicken-and-egg problem:

- **Need**: Service principal with Contributor role for Azure Tenant Grapher
- **Blocker**: Global Admin can't assign roles without elevated RBAC access
- **Solution**: Programmatically elevate access using Azure REST API

## Automated Solution

### Prerequisites

1. Azure CLI installed and authenticated as Global Admin
2. Authenticated to target tenant: `az login --tenant <TENANT_ID>`

### Step 1: Create App Registration and Service Principal

```bash
# Create app registration
APP_JSON=$(az ad app create --display-name "azure-tenant-grapher-<TENANT_NAME>" --output json)
APP_ID=$(echo $APP_JSON | jq -r '.appId')

# Create service principal from app
SP_JSON=$(az ad sp create --id $APP_ID --output json)
SP_OBJECT_ID=$(echo $SP_JSON | jq -r '.id')

# Create client secret (1 year expiration)
CRED_JSON=$(az ad app credential reset --id $APP_ID --years 1 --output json)
CLIENT_SECRET=$(echo $CRED_JSON | jq -r '.password')
TENANT_ID=$(echo $CRED_JSON | jq -r '.tenant')

echo "✅ Service Principal Created"
echo "App ID: $APP_ID"
echo "Object ID: $SP_OBJECT_ID"
echo "Client Secret: $CLIENT_SECRET"
echo "Tenant ID: $TENANT_ID"
```

### Step 2: Elevate Global Admin Access

As a Global Admin in Entra ID, elevate yourself to **User Access Administrator** at the root management group scope:

```bash
# Get management API token
TOKEN=$(az account get-access-token --resource https://management.azure.com --query accessToken -o tsv)

# Elevate access (empty response = success)
curl -X POST \
  "https://management.azure.com/providers/Microsoft.Authorization/elevateAccess?api-version=2016-07-01" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Length: 0"

echo "✅ Access elevated - waiting for propagation..."
sleep 15
```

### Step 3: Assign Contributor Role via REST API

**Important**: Use REST API (not `az role assignment create`) because az CLI caches tokens and won't immediately recognize the elevated permissions.

```bash
# Prepare role assignment data
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
CONTRIBUTOR_ROLE_ID=$(az role definition list --name "Contributor" --query "[0].id" -o tsv)
UUID_CONTRIBUTOR=$(uuidgen)

# Get fresh token
TOKEN=$(az account get-access-token --resource https://management.azure.com --query accessToken -o tsv)

# Assign Contributor role via REST API
curl -X PUT \
  "https://management.azure.com/subscriptions/${SUBSCRIPTION_ID}/providers/Microsoft.Authorization/roleAssignments/${UUID_CONTRIBUTOR}?api-version=2022-04-01" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"properties\": {
      \"roleDefinitionId\": \"${CONTRIBUTOR_ROLE_ID}\",
      \"principalId\": \"${SP_OBJECT_ID}\",
      \"principalType\": \"ServicePrincipal\"
    }
  }"

echo "✅ Contributor role assigned"
```

### Step 4: Assign Security Reader Role (CRITICAL for Role Assignment Scanning)

**NEW**: Role assignment scanning requires Security Reader, User Access Administrator, or Owner role.

```bash
# Get Security Reader role definition
SECURITY_READER_ROLE_ID=$(az role definition list --name "Security Reader" --query "[0].id" -o tsv)
UUID_SECURITY=$(uuidgen)

# Get fresh token
TOKEN=$(az account get-access-token --resource https://management.azure.com --query accessToken -o tsv)

# Assign Security Reader role via REST API
curl -X PUT \
  "https://management.azure.com/subscriptions/${SUBSCRIPTION_ID}/providers/Microsoft.Authorization/roleAssignments/${UUID_SECURITY}?api-version=2022-04-01" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"properties\": {
      \"roleDefinitionId\": \"${SECURITY_READER_ROLE_ID}\",
      \"principalId\": \"${SP_OBJECT_ID}\",
      \"principalType\": \"ServicePrincipal\"
    }
  }"

echo "✅ Security Reader role assigned"
echo "⚠️  CRITICAL: Without Security Reader, role assignments cannot be scanned!"
```

### Step 5: Assign Owner Role (CRITICAL for IaC Deployment with Role Assignments)

**IMPORTANT**: Deploying IaC templates that include `azurerm_role_assignment` resources requires Owner role (or User Access Administrator).

```bash
# Get Owner role definition
OWNER_ROLE_ID=$(az role definition list --name "Owner" --query "[0].id" -o tsv)
UUID_OWNER=$(uuidgen)

# Get fresh token
TOKEN=$(az account get-access-token --resource https://management.azure.com --query accessToken -o tsv)

# Assign Owner role via REST API
curl -X PUT \
  "https://management.azure.com/subscriptions/${SUBSCRIPTION_ID}/providers/Microsoft.Authorization/roleAssignments/${UUID_OWNER}?api-version=2022-04-01" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"properties\": {
      \"roleDefinitionId\": \"${OWNER_ROLE_ID}\",
      \"principalId\": \"${SP_OBJECT_ID}\",
      \"principalType\": \"ServicePrincipal\"
    }
  }"

echo "✅ Owner role assigned"
echo "⚠️  CRITICAL: Without Owner, terraform apply will fail on role assignment resources!"
```

### Step 6: Verify Role Assignments

```bash
az role assignment list --assignee $APP_ID --output table
```

Expected output:
```
Principal               Role            Scope
----------------------  --------------  ---------------------------------------------
<APP_ID>                Contributor     /subscriptions/<SUBSCRIPTION_ID>
<APP_ID>                Security Reader /subscriptions/<SUBSCRIPTION_ID>
<APP_ID>                Owner           /subscriptions/<SUBSCRIPTION_ID>
```

**Note**: All three roles are required:
- **Contributor**: Manage Azure resources (VMs, networks, storage, etc.)
- **Security Reader**: Scan role assignments during tenant discovery
- **Owner**: Deploy resources with role assignments via Terraform

## Integration with Azure Tenant Grapher

### Update .env File

```bash
# Add or update service principal credentials
cat >> .env <<EOF
AZURE_TENANT_2_ID=${TENANT_ID}
AZURE_TENANT_2_CLIENT_ID=${APP_ID}
AZURE_TENANT_2_CLIENT_SECRET=${CLIENT_SECRET}
AZURE_TENANT_2_NAME=<TENANT_NAME>
EOF
```

### Test Authentication

```bash
# Test with minimal scan
uv run atg scan --tenant-id $TENANT_ID --no-dashboard --resource-limit 5
```

If successful, you'll see:
```
✅ Connected to Neo4j at bolt://localhost:7688
🚀 Starting Azure Tenant Graph building...
🔍 Discovering subscriptions in tenant <TENANT_ID>
```

## Complete Automation Script

```bash
#!/bin/bash
set -e

# Configuration
TENANT_NAME="DefenderATEVET12"
TENANT_ID="c7674d41-af6c-46f5-89a5-d41495d2151e"

echo "Creating service principal for $TENANT_NAME..."

# Step 1: Create app and service principal
APP_JSON=$(az ad app create --display-name "azure-tenant-grapher-${TENANT_NAME}" --output json)
APP_ID=$(echo $APP_JSON | jq -r '.appId')

SP_JSON=$(az ad sp create --id $APP_ID --output json)
SP_OBJECT_ID=$(echo $SP_JSON | jq -r '.id')

CRED_JSON=$(az ad app credential reset --id $APP_ID --years 1 --output json)
CLIENT_SECRET=$(echo $CRED_JSON | jq -r '.password')

echo "✅ Service principal created"
echo "   App ID: $APP_ID"
echo "   Object ID: $SP_OBJECT_ID"

# Step 2: Elevate access
echo "Elevating Global Admin access..."
TOKEN=$(az account get-access-token --resource https://management.azure.com --query accessToken -o tsv)
curl -s -X POST \
  "https://management.azure.com/providers/Microsoft.Authorization/elevateAccess?api-version=2016-07-01" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Length: 0"
sleep 15
echo "✅ Access elevated"

# Step 3: Assign role via REST API
echo "Assigning Contributor role..."
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
ROLE_DEF_ID=$(az role definition list --name "Contributor" --query "[0].id" -o tsv)
UUID=$(uuidgen)
TOKEN=$(az account get-access-token --resource https://management.azure.com --query accessToken -o tsv)

curl -s -X PUT \
  "https://management.azure.com/subscriptions/${SUBSCRIPTION_ID}/providers/Microsoft.Authorization/roleAssignments/${UUID}?api-version=2022-04-01" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"properties\":{\"roleDefinitionId\":\"${ROLE_DEF_ID}\",\"principalId\":\"${SP_OBJECT_ID}\",\"principalType\":\"ServicePrincipal\"}}" \
  > /dev/null

echo "✅ Contributor role assigned"

# Step 4: Update .env
echo "Updating .env file..."
cat >> .env <<EOF
AZURE_TENANT_2_ID=${TENANT_ID}
AZURE_TENANT_2_CLIENT_ID=${APP_ID}
AZURE_TENANT_2_CLIENT_SECRET=${CLIENT_SECRET}
AZURE_TENANT_2_NAME=${TENANT_NAME}
EOF

echo "✅ Setup complete!"
echo ""
echo "Service Principal Details:"
echo "  App ID: $APP_ID"
echo "  Client Secret: $CLIENT_SECRET"
echo "  Tenant ID: $TENANT_ID"
echo ""
echo "Test with: uv run atg scan --tenant-id $TENANT_ID --no-dashboard --resource-limit 5"
```

## Key Design Decisions

### Why REST API Instead of az CLI?

**Problem**: `az role assignment create` fails even after elevation because az CLI caches access tokens that don't include the new elevated permissions.

**Solution**: Use Azure REST API directly with a freshly obtained token that includes the elevated User Access Administrator role.

### Why Elevate Access?

**Context**: Global Admin is an Entra ID (formerly Azure AD) role that grants full admin rights over identity and access management. However, it does NOT grant Azure RBAC permissions for resource management.

**Solution**: The `elevateAccess` API endpoint grants Global Admins the **User Access Administrator** role at the root management group scope, which allows them to assign roles at any scope (including subscriptions).

### Security Considerations

1. **Elevation is temporary**: Elevated access automatically expires and is session-specific
2. **Owner role implications**: Service principal has Owner role to deploy role assignments. This is necessary for complete IaC deployments but should be:
   - Limited to specific subscriptions (not root management group)
   - Monitored via Azure Activity Log
   - Rotated when no longer needed for deployments
3. **Secret management**: Client secrets should be rotated annually and stored securely
4. **Audit trail**: All operations are logged in Azure Activity Log
5. **Least privilege alternatives**: If your IaC doesn't include role assignments, you can use Contributor + Security Reader without Owner

## Troubleshooting

### "AuthorizationFailed" after elevation

**Cause**: Permissions haven't propagated yet

**Solution**: Increase sleep duration after elevation (try 30-60 seconds)

### "Invalid client secret" when testing

**Cause**: Service principal needs time to propagate

**Solution**: Wait 1-2 minutes after creation, then retry

### REST API returns 401 Unauthorized

**Cause**: Token expired or doesn't have elevated permissions

**Solution**: Re-run elevation and obtain fresh token

## References

- [Elevate access for Global Admin](https://learn.microsoft.com/en-us/azure/role-based-access-control/elevate-access-global-admin)
- [Azure REST API - Role Assignments](https://learn.microsoft.com/en-us/rest/api/authorization/role-assignments/create)
- [Service Principal Authentication](https://learn.microsoft.com/en-us/azure/active-directory/develop/howto-create-service-principal-portal)

## Demo Scenario

This automated approach was used in the cross-tenant demo:

**Scenario**: Replicate SimuLand resource group from DefenderATEVET17 → DefenderATEVET12

**Challenge**: Target tenant (DefenderATEVET12) needed a service principal with permissions, but manual Portal setup was not acceptable for user experience.

**Solution**: Fully automated CLI workflow that:
1. Creates service principal in <30 seconds
2. Elevates Global Admin access programmatically
3. Assigns Contributor role via REST API
4. Updates .env configuration
5. Tests authentication with atg scan

**Result**: Zero manual steps, completely reproducible, ready for production use.
