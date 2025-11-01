# Identity Mapping Guide for Cross-Tenant Translation

This guide explains how to create an identity mapping file for cross-tenant Azure deployments. Identity mapping is crucial when your infrastructure references Entra ID (formerly Azure AD) objects like users, groups, or service principals.

## Table of Contents

1. [What is Identity Mapping?](#what-is-identity-mapping)
2. [When Do You Need It?](#when-do-you-need-it)
3. [Identity Mapping File Structure](#identity-mapping-file-structure)
4. [Step-by-Step Guide](#step-by-step-guide)
5. [Examples](#examples)
6. [Troubleshooting](#troubleshooting)

---

## What is Identity Mapping?

Identity mapping is a JSON file that maps Entra ID objects from your **source tenant** to corresponding objects in your **target tenant**. This is necessary because:

- **Object IDs are unique per tenant**: The same user in two different tenants has different Object IDs
- **Cross-tenant references fail**: Azure resources (Key Vaults, Storage Accounts, etc.) reference Entra ID objects by Object ID
- **Manual mapping is required**: There's no automatic way to match identities across tenants

### Example Scenario

You have a Key Vault in **Tenant A** with an access policy granting permissions to:
- User: `alice@tenantA.onmicrosoft.com` (Object ID: `aaaa-1111-bbbb-2222`)

You want to deploy the same Key Vault to **Tenant B**, but grant permissions to:
- User: `alice@tenantB.onmicrosoft.com` (Object ID: `cccc-3333-dddd-4444`)

The identity mapping file tells the translation system to replace `aaaa-1111-bbbb-2222` with `cccc-3333-dddd-4444`.

---

## When Do You Need It?

You need identity mapping when your infrastructure includes:

- **Key Vaults** with access policies referencing users/groups/service principals
- **Storage Accounts** with IAM role assignments
- **Managed Identities** assigned to resources
- **SQL Databases** with Entra ID authentication
- **Cosmos DB** with role-based access control
- **Any resource** with Azure RBAC role assignments

If your infrastructure only includes network resources (VNets, subnets, NSGs) and compute resources without identity references, you may not need identity mapping.

---

## Identity Mapping File Structure

The identity mapping file is a JSON file with the following structure:

```json
{
  "users": {
    "SOURCE_USER_OBJECT_ID": "TARGET_USER_OBJECT_ID",
    "SOURCE_USER_UPN": "TARGET_USER_UPN"
  },
  "groups": {
    "SOURCE_GROUP_OBJECT_ID": "TARGET_GROUP_OBJECT_ID",
    "SOURCE_GROUP_NAME": "TARGET_GROUP_NAME"
  },
  "service_principals": {
    "SOURCE_SP_OBJECT_ID": "TARGET_SP_OBJECT_ID",
    "SOURCE_SP_APP_ID": "TARGET_SP_APP_ID"
  },
  "managed_identities": {
    "SOURCE_MI_OBJECT_ID": "TARGET_MI_OBJECT_ID",
    "SOURCE_MI_RESOURCE_ID": "TARGET_MI_RESOURCE_ID"
  }
}
```

### Mapping Strategies

You can map by:
1. **Object ID** (most reliable): Maps the unique identifier
2. **UPN/Name** (convenient): Maps by user principal name or display name
3. **Resource ID** (for managed identities): Maps the full Azure resource ID

The translator will check all mapping types in order.

---

## Step-by-Step Guide

### Step 1: Identify Source Identities

First, identify which Entra ID objects are referenced in your source tenant resources.

#### Option A: Use Azure Tenant Grapher (Recommended)

```bash
# Scan your source tenant
uv run atg scan --tenant-id SOURCE_TENANT_ID

# Generate a spec to see all referenced identities
uv run atg generate-spec

# The spec file will include identity references in various resources
```

Look for sections like:
- Key Vault access policies
- Role assignments
- Managed identity assignments

#### Option B: Use Azure CLI

```bash
# Set source tenant context
az login --tenant SOURCE_TENANT_ID
az account set --subscription SOURCE_SUBSCRIPTION_ID

# List users referenced in a specific Key Vault
az keyvault show --name YOUR_KEYVAULT_NAME --query "properties.accessPolicies[].objectId" -o tsv

# List all role assignments in a resource group
az role assignment list --resource-group YOUR_RG_NAME --query "[].principalId" -o tsv
```

### Step 2: Get Source Object Details

For each Object ID you found, get the full details:

```bash
# For users
az ad user show --id OBJECT_ID --query "{objectId:id, userPrincipalName:userPrincipalName, displayName:displayName}"

# For groups
az ad group show --group OBJECT_ID --query "{objectId:id, displayName:displayName}"

# For service principals
az ad sp show --id OBJECT_ID --query "{objectId:id, appId:appId, displayName:displayName}"
```

### Step 3: Find Target Identities

Switch to your target tenant and find the corresponding objects:

```bash
# Switch to target tenant
az login --tenant TARGET_TENANT_ID
az account set --subscription TARGET_SUBSCRIPTION_ID

# Find user by UPN
az ad user show --id alice@targetdomain.com --query "{objectId:id, userPrincipalName:userPrincipalName}"

# Find group by name
az ad group list --display-name "Database Admins" --query "[0].{objectId:id, displayName:displayName}"

# Find service principal by display name
az ad sp list --display-name "MyApp" --query "[0].{objectId:id, appId:appId}"
```

### Step 4: Create the Mapping File

Create a file `identity_mapping.json` with your mappings:

```json
{
  "users": {
    "aaaaaaaa-1111-1111-1111-111111111111": "bbbbbbbb-2222-2222-2222-222222222222",
    "alice@sourcetenant.com": "alice@targettenant.com"
  },
  "groups": {
    "cccccccc-3333-3333-3333-333333333333": "dddddddd-4444-4444-4444-444444444444"
  },
  "service_principals": {
    "eeeeeeee-5555-5555-5555-555555555555": "ffffffff-6666-6666-6666-666666666666"
  }
}
```

### Step 5: Validate the Mapping

Use Azure CLI to verify each mapping:

```bash
# Verify source identity exists
az ad user show --id aaaaaaaa-1111-1111-1111-111111111111 --tenant SOURCE_TENANT_ID

# Verify target identity exists
az ad user show --id bbbbbbbb-2222-2222-2222-222222222222 --tenant TARGET_TENANT_ID
```

### Step 6: Test with IaC Generation

Generate IaC using your identity mapping:

```bash
# Note: Identity mapping support is currently built-in to the translation system
# Future versions will support explicit --identity-mapping-file parameter
uv run atg generate-iac \
  --tenant-id SOURCE_TENANT_ID \
  --target-subscription TARGET_SUBSCRIPTION_ID \
  --format terraform
```

---

## Examples

### Example 1: Simple User Mapping

**Scenario**: Key Vault with one user access policy

**Source Tenant**:
```bash
az ad user show --id aaaaaaaa-1111-1111-1111-111111111111
# Output:
# {
#   "id": "aaaaaaaa-1111-1111-1111-111111111111",
#   "userPrincipalName": "alice@contoso.com",
#   "displayName": "Alice Johnson"
# }
```

**Target Tenant**:
```bash
az ad user show --id alice@fabrikam.com
# Output:
# {
#   "id": "bbbbbbbb-2222-2222-2222-222222222222",
#   "userPrincipalName": "alice@fabrikam.com",
#   "displayName": "Alice Johnson"
# }
```

**Mapping File**:
```json
{
  "users": {
    "aaaaaaaa-1111-1111-1111-111111111111": "bbbbbbbb-2222-2222-2222-222222222222"
  }
}
```

### Example 2: Group and Service Principal Mapping

**Scenario**: Storage Account with RBAC role assignments

**Mapping File**:
```json
{
  "groups": {
    "cccccccc-3333-3333-3333-333333333333": "dddddddd-4444-4444-4444-444444444444",
    "Storage Contributors": "Storage Contributors"
  },
  "service_principals": {
    "eeeeeeee-5555-5555-5555-555555555555": "ffffffff-6666-6666-6666-666666666666"
  }
}
```

### Example 3: Managed Identity Mapping

**Scenario**: VM with User-Assigned Managed Identity

```json
{
  "managed_identities": {
    "gggggggg-7777-7777-7777-777777777777": "hhhhhhhh-8888-8888-8888-888888888888",
    "/subscriptions/SOURCE-SUB/resourceGroups/rg1/providers/Microsoft.ManagedIdentity/userAssignedIdentities/myIdentity": "/subscriptions/TARGET-SUB/resourceGroups/rg1/providers/Microsoft.ManagedIdentity/userAssignedIdentities/myIdentity"
  }
}
```

### Example 4: Complete Enterprise Mapping

```json
{
  "users": {
    "aaaaaaaa-1111-1111-1111-111111111111": "bbbbbbbb-2222-2222-2222-222222222222",
    "alice@contoso.com": "alice@fabrikam.com",
    "bob@contoso.com": "bob@fabrikam.com"
  },
  "groups": {
    "cccccccc-3333-3333-3333-333333333333": "dddddddd-4444-4444-4444-444444444444",
    "Database Admins": "Database Admins",
    "App Developers": "App Developers"
  },
  "service_principals": {
    "eeeeeeee-5555-5555-5555-555555555555": "ffffffff-6666-6666-6666-666666666666",
    "MyApp": "MyApp"
  },
  "managed_identities": {
    "gggggggg-7777-7777-7777-777777777777": "hhhhhhhh-8888-8888-8888-888888888888"
  }
}
```

---

## Troubleshooting

### Common Issues

#### Issue 1: "Identity not found in target tenant"

**Problem**: The translator can't find a mapping for a source identity.

**Solution**:
1. Verify the source Object ID is correct
2. Check if you've created the corresponding identity in the target tenant
3. Ensure your mapping file includes all required identities

#### Issue 2: "Permission denied when querying Entra ID"

**Problem**: Azure CLI can't read Entra ID information.

**Solution**:
```bash
# Grant yourself Entra ID read permissions
# Ask your tenant admin to assign you one of these roles:
# - Global Reader
# - Directory Readers
# - User Administrator
```

#### Issue 3: "UPN mapping doesn't work"

**Problem**: You mapped by UPN but the translator still shows warnings.

**Solution**: Add Object ID mapping as well:
```json
{
  "users": {
    "SOURCE_OBJECT_ID": "TARGET_OBJECT_ID",
    "alice@source.com": "alice@target.com"
  }
}
```

Object ID mapping is more reliable than UPN mapping.

#### Issue 4: "Service Principal not found by display name"

**Problem**: Multiple service principals can have the same display name.

**Solution**: Always map by Object ID or App ID for service principals:
```json
{
  "service_principals": {
    "SOURCE_OBJECT_ID": "TARGET_OBJECT_ID"
  }
}
```

### Validation Script

Create a simple validation script to check your mappings:

```bash
#!/bin/bash
# validate_mappings.sh

SOURCE_TENANT="your-source-tenant-id"
TARGET_TENANT="your-target-tenant-id"

# Validate source identities
echo "Validating source identities..."
az login --tenant "$SOURCE_TENANT"
jq -r '.users | keys[]' identity_mapping.json | while read id; do
  az ad user show --id "$id" > /dev/null 2>&1 && echo "✓ $id" || echo "✗ $id"
done

# Validate target identities
echo "Validating target identities..."
az login --tenant "$TARGET_TENANT"
jq -r '.users | values[]' identity_mapping.json | while read id; do
  az ad user show --id "$id" > /dev/null 2>&1 && echo "✓ $id" || echo "✗ $id"
done
```

---

## Best Practices

1. **Use Object IDs**: Always prefer Object ID mapping over UPN/name mapping
2. **Document mappings**: Add comments in a separate `identity_mapping_notes.txt` file
3. **Version control**: Store mapping files in version control (use Azure Key Vault for sensitive IDs)
4. **Automate where possible**: Use scripts to generate mappings for large organizations
5. **Validate before deployment**: Always test with `--dry-run` first
6. **Keep mappings synchronized**: Update the file when identities change in either tenant

---

## Related Resources

- [Azure Tenant Grapher Documentation](../README.md)
- [Cross-Tenant Deployment Example](./cross_tenant_deployment.sh)
- [Translation Testing Script](./test_translation.py)
- [Identity Mapping Example](./identity_mapping_example.json)
- [Azure AD Graph API](https://docs.microsoft.com/graph/api/overview)
- [Azure RBAC Documentation](https://docs.microsoft.com/azure/role-based-access-control/)

---

## Support

If you encounter issues with identity mapping:

1. Check the translation report in `outputs/iac-out-*/translation_report.json`
2. Review logs for translation warnings
3. File an issue on the [Azure Tenant Grapher GitHub repository](https://github.com/yourusername/azure-tenant-grapher/issues)
