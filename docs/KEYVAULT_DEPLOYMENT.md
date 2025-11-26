# KeyVault Manual Deployment Guide

## Overview

Azure Key Vaults require manual deployment when using Azure Tenant Grapher (ATG) for cross-tenant replication. This document explains the technical rationale and provides a manual deployment workflow.

## Why KeyVaults Are Excluded from IaC Generation

### Root Cause Analysis

The `KeyVaultHandler` class (`src/iac/keyvault_handler.py`) is currently a **stub implementation** with no conflict detection or resolution logic:

```python
def handle_vault_conflicts(self, vault_names, subscription_id, location=None, auto_purge=False):
    logger.warning(
        f"KeyVaultHandler.handle_vault_conflicts() is a stub. "
        f"Checked {len(vault_names)} vault names but no conflict detection implemented yet."
    )
    return {}  # No conflicts detected (stub)
```

### Technical Challenges

1. **Global Naming Uniqueness**: Key Vault names must be globally unique across all Azure tenants. Source tenant vault names may conflict with existing target tenant vaults.

2. **Soft-Delete Recovery Period**: Deleted Key Vaults remain recoverable for 90 days by default. If a vault with the same name was previously deleted in the target subscription, creation will fail.

3. **Access Policy Complexity**: Key Vault access policies reference:
   - User Principal IDs (tenant-specific)
   - Service Principal IDs (tenant-specific)
   - Group IDs (tenant-specific)

   These IDs require Entra ID identity mapping which is not fully implemented.

4. **Permission Requirements**: The deployment service principal needs:
   - `Microsoft.KeyVault/vaults/*` permissions
   - `Microsoft.KeyVault/deletedVaults/read` (to check soft-deleted vaults)
   - `Microsoft.KeyVault/deletedVaults/purge/action` (to purge soft-deleted vaults)

## Recommended Workaround

### Step 1: Export KeyVault Configuration

Query the Neo4j graph to extract KeyVault details:

```cypher
MATCH (kv:Resource)
WHERE kv.type =~ '(?i)Microsoft.KeyVault/vaults'
RETURN kv.name, kv.location, kv.properties
```

### Step 2: Check for Name Conflicts

For each KeyVault, verify the name is available in the target subscription:

```bash
# Check if vault name is available
az keyvault list --query "[?name=='<vault-name>']" --subscription <target-subscription>

# Check for soft-deleted vaults with same name
az keyvault list-deleted --query "[?name=='<vault-name>']" --subscription <target-subscription>
```

### Step 3: Manual Creation Options

#### Option A: Create with New Name (Recommended)

```bash
az keyvault create \
  --name "<new-unique-name>" \
  --resource-group "<target-rg>" \
  --location "<location>" \
  --sku standard \
  --subscription "<target-subscription>"
```

#### Option B: Purge and Recreate (If Name Required)

```bash
# Purge the soft-deleted vault (IRREVERSIBLE)
az keyvault purge --name "<vault-name>" --subscription "<target-subscription>"

# Wait for purge to complete (may take several minutes)
sleep 120

# Create the vault
az keyvault create \
  --name "<vault-name>" \
  --resource-group "<target-rg>" \
  --location "<location>" \
  --subscription "<target-subscription>"
```

### Step 4: Configure Access Policies

Map source tenant identities to target tenant identities, then apply access policies:

```bash
# Example: Grant a user access
az keyvault set-policy \
  --name "<vault-name>" \
  --upn "<target-user-email>" \
  --secret-permissions get list set delete \
  --key-permissions get list create delete \
  --subscription "<target-subscription>"
```

### Step 5: Migrate Secrets (If Applicable)

**WARNING**: This requires appropriate authorization and should only be done for secrets you own.

```bash
# Export secret from source vault (requires access)
az keyvault secret show --vault-name "<source-vault>" --name "<secret-name>" --query value -o tsv

# Import to target vault
az keyvault secret set --vault-name "<target-vault>" --name "<secret-name>" --value "<value>"
```

## Future Improvements

The following features are planned for KeyVaultHandler:

1. **Conflict Detection**: Query target subscription for existing/soft-deleted vaults
2. **Name Suggestion**: Propose alternative names when conflicts detected
3. **Identity Mapping Integration**: Translate access policy principals using Entra ID mapping file
4. **Access Policy Templates**: Generate access policy configurations from source vault

## Related Resources

- [Azure Key Vault Soft-Delete Documentation](https://docs.microsoft.com/azure/key-vault/general/soft-delete-overview)
- [Cross-Tenant Identity Mapping](../docs/cross-tenant/FEATURES.md)
- [Terraform AzureRM Key Vault](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/key_vault)

## Version History

| Date | Version | Changes |
|------|---------|---------|
| 2025-11-26 | 1.0 | Initial documentation |
