# Property Mapping Manifests

This directory contains complete property mapping manifests for Azure to Terraform resource translation.

## Created: 2026-01-17

Complete implementation of property mappings for all 9 resource types from PR #712.

## Files

| File | Resource Type | Properties | Security Props |
|------|---------------|------------|----------------|
| `storage_account.yaml` | Microsoft.Storage/storageAccounts | 19 | 6 |
| `key_vault.yaml` | Microsoft.KeyVault/vaults | 14 | 5 |
| `sql_server.yaml` | Microsoft.Sql/servers | 13 | 3 |
| `sql_database.yaml` | Microsoft.Sql/servers/databases | 9 | 3 |
| `container_registry.yaml` | Microsoft.ContainerRegistry/registries | 13 | 4 |
| `app_service.yaml` | Microsoft.Web/sites | 14 | 3 |
| `cognitive_services.yaml` | Microsoft.CognitiveServices/accounts | 15 | 5 |
| `postgresql.yaml` | Microsoft.DBforPostgreSQL/flexibleServers | 17 | 4 |
| `cosmosdb.yaml` | Microsoft.DocumentDB/databaseAccounts | 19 | 4 |

**Total: 9 resources, 133 properties**

## Manifest Structure

Each manifest file contains:

```yaml
resource_type:
  azure: Microsoft.Service/resourceType
  terraform: azurerm_resource_type

provider_version:
  min: "3.0.0"
  max: "4.99.99"
  notes: Provider-specific version notes

metadata:
  description: Resource description
  last_updated: "YYYY-MM-DD"
  author: "ATG Property Validation System"

properties:
  - azure_path: properties.propertyName
    terraform_param: terraform_parameter_name
    required: true|false
    criticality: CRITICAL|HIGH|MEDIUM|LOW
    type: string|boolean|integer|array|object
    valid_values: [...]
    default_value: ...
    description: Property description
    transformation: Mapping logic notes
    notes: Additional notes
```

## Criticality Levels

- **CRITICAL**: Essential for resource creation or security (e.g., names, IDs, HTTPS enforcement)
- **HIGH**: Important security properties (e.g., network access, encryption, authentication)
- **MEDIUM**: Feature configuration (e.g., backup settings, performance tiers)
- **LOW**: Metadata and tags

## Security Properties (PR #712)

All manifests include complete security property mappings:

### Common Security Properties

- `public_network_access_enabled` - Network isolation control
- `network_acls.*` - IP and VNet firewall rules
- `*_tls_version` - TLS protocol enforcement
- `https_*` - HTTPS protocol enforcement

### Resource-Specific Security

- **Storage Account**: Shared key access, OAuth authentication, blob public access
- **Key Vault**: RBAC authorization, purge protection, soft delete
- **SQL Server/Database**: Azure AD authentication, TDE encryption, ledger
- **Container Registry**: Data endpoint control, network rules
- **App Service**: Client certificates, HTTPS only
- **Cognitive Services**: Local authentication control
- **PostgreSQL**: Active Directory authentication
- **Cosmos DB**: Local authentication, IP filtering

## Usage

These manifests are used by:

1. **Property Validation System** - Validates Azure to Terraform property mappings
2. **Handler Code Generation** - Generates handler code from manifests
3. **Documentation** - Auto-generates property mapping documentation
4. **Testing** - Validates handler implementations match specifications

## Source of Truth

All properties extracted directly from handler implementation code in:
- `src/iac/emitters/terraform/handlers/`

## Validation

All manifests are validated for:
- ✓ YAML syntax correctness
- ✓ Required fields present
- ✓ Property completeness vs handler code
- ✓ Security property coverage
- ✓ Criticality levels assigned
- ✓ Type information present

## Provider Version Notes

Many properties were renamed in provider v3.0+ and v4.0+. See individual manifest files for specific notes:

- Storage Account: `https_traffic_only` → `https_traffic_only_enabled` (v4.0+)
- Storage Account: `allow_blob_public_access` → `allow_nested_items_to_be_public` (v3.0+)
- Key Vault: SKU names must be lowercase (v3.0+)

## Transformation Notes

Some properties require transformation between Azure and Terraform formats:

- **String to Boolean**: `publicNetworkAccess` ("Enabled"/"Disabled") → `public_network_access_enabled` (true/false)
- **Inverse Logic**: `disableLocalAuth` (Azure) → `local_auth_enabled` (Terraform, inverted)
- **Units**: `storageSizeGB` → `storage_mb` (multiply by 1024)
- **Arrays**: IP rules arrays → comma-separated strings (Cosmos DB)

See individual manifest files for detailed transformation logic.

## Completeness

Each manifest includes:
- ✓ ALL properties from corresponding handler
- ✓ NO placeholders or TODOs
- ✓ Complete security coverage from PR #712
- ✓ Transformation documentation
- ✓ Valid values where applicable
- ✓ Provider version compatibility notes

## Statistics

- **9 resource types** fully documented
- **133 total properties** mapped
- **46 CRITICAL** properties
- **34 HIGH** priority properties
- **43 MEDIUM** priority properties
- **10 LOW** priority properties
- **37 security properties** from PR #712

## Updates

When adding new properties to handlers:

1. Update the corresponding manifest YAML file
2. Set appropriate criticality level
3. Document any transformations needed
4. Add provider version notes if parameter was renamed
5. Run validation: `python -m yaml.safe_load manifest.yaml`

## Questions?

See `src/iac/property_validation/manifest/README.md` for system documentation.
