# AAD Enrichment User Guide

## What is AAD Enrichment?

AAD (Azure Active Directory / Entra ID) Enrichment automatically discovers and imports ServicePrincipals from Microsoft Graph API during tenant scans. This ensures that identity resources are captured alongside infrastructure resources in the Neo4j graph database.

## How to Enable/Disable

AAD enrichment is **enabled by default** but can be controlled via environment variable:

```bash
# Enable (default)
export ENABLE_AAD_IMPORT=true

# Disable
export ENABLE_AAD_IMPORT=false
```

## Running a Scan with AAD Enrichment

```bash
# Standard scan (AAD enrichment enabled by default)
uv run atg scan --tenant-id <TENANT_ID>

# Explicitly enable
ENABLE_AAD_IMPORT=true uv run atg scan --tenant-id <TENANT_ID>

# Disable AAD enrichment
ENABLE_AAD_IMPORT=false uv run atg scan --tenant-id <TENANT_ID>
```

## What Gets Captured

When AAD enrichment runs, it captures:
- **ServicePrincipals**: All service principals in the tenant
- **Properties**: `displayName`, `appId`, `servicePrincipalType`
- **Resource Format**: Compatible with IaC generation

Example ServicePrincipal in Neo4j:
```cypher
{
  id: "/servicePrincipals/abc-123-xyz",
  name: "My Application",
  displayName: "My Application",
  type: "Microsoft.Graph/servicePrincipals",
  app_id: "app-guid-here",
  service_principal_type: "Application",
  location: "global",
  resource_group: null
}
```

## Verifying It Works

### 1. Check Logs During Scan

Look for these log messages:
```
======================================================================
Enriching with Entra ID (Azure AD) identity data...
======================================================================
Fetching service principals from Microsoft Graph API...
Successfully fetched X service principals from Graph API
Successfully added X service principals to processing queue
Total resources after AAD enrichment: Y (was Z)
```

### 2. Query Neo4j

After the scan completes, verify ServicePrincipals were captured:

```cypher
// Count service principals
MATCH (sp:ServicePrincipal)
RETURN count(sp) as service_principal_count

// List all service principals
MATCH (sp:ServicePrincipal)
RETURN sp.displayName, sp.app_id, sp.id
LIMIT 10

// Find service principals with relationships
MATCH (sp:ServicePrincipal)-[r]->(target)
RETURN sp.displayName, type(r), labels(target)
LIMIT 10
```

### 3. Check Resource Counts

The log will show resource counts before and after enrichment:
```
Total resources after AAD enrichment: 150 (was 142)
```

This means 8 service principals were added.

## Troubleshooting

### ServicePrincipals Not Appearing

**Problem**: No service principals in Neo4j after scan.

**Solutions**:
1. Check if AAD enrichment is enabled:
   ```bash
   echo $ENABLE_AAD_IMPORT  # Should be 'true' or empty (defaults to true)
   ```

2. Check logs for errors:
   ```bash
   uv run atg scan --tenant-id <TENANT_ID> 2>&1 | grep -A 5 "Enriching with Entra ID"
   ```

3. Verify Azure credentials have Graph API permissions:
   - Required permission: `Application.Read.All` or `Directory.Read.All`
   - Check with: `az ad sp show --id $AZURE_CLIENT_ID`

### Graph API Permission Errors

**Problem**: Error message about insufficient permissions.

**Solution**:
Grant your service principal Graph API read permissions:
```bash
# Get your service principal object ID
SP_OBJECT_ID=$(az ad sp show --id $AZURE_CLIENT_ID --query id -o tsv)

# Grant Directory.Read.All permission
az ad app permission add \
  --id $AZURE_CLIENT_ID \
  --api 00000003-0000-0000-c000-000000000000 \
  --api-permissions 7ab1d382-f21e-4acd-a863-ba3e13f7da61=Role

# Grant admin consent
az ad app permission admin-consent --id $AZURE_CLIENT_ID
```

### AAD Enrichment Disabled Message

**Problem**: Log shows "AAD enrichment disabled".

**Causes**:
1. `ENABLE_AAD_IMPORT` is set to `false`
2. AAD Graph Service failed to initialize (check earlier logs)
3. Missing Azure credentials (`AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`)

**Solution**:
```bash
# Verify environment variables
echo $ENABLE_AAD_IMPORT
echo $AZURE_CLIENT_ID
echo $AZURE_TENANT_ID
env | grep AZURE

# Re-enable if needed
export ENABLE_AAD_IMPORT=true
```

## Performance Considerations

### Large Tenants

For tenants with many service principals (>1000):
- AAD enrichment adds ~5-30 seconds to scan time
- Graph API handles pagination automatically
- Rate limiting is handled with exponential backoff

### Resource Limits

If using `--resource-limit` for testing:
```bash
# Limit affects only Azure resources, NOT ServicePrincipals
uv run atg scan --tenant-id <TENANT_ID> --resource-limit 10
```

ServicePrincipals are added AFTER the resource limit is applied, so you'll get:
- Up to 10 Azure resources (from subscription)
- ALL ServicePrincipals from tenant (no limit)

## Integration with IaC Generation

ServicePrincipals captured during AAD enrichment are available for IaC generation:

```bash
# Generate IaC including ServicePrincipals
uv run atg generate-iac --tenant-id <TENANT_ID>
```

ServicePrincipals will be included in:
- **Terraform**: `azuread_service_principal` data sources
- **ARM/Bicep**: Service principal references
- **Cross-tenant**: Translated using identity mappings

## Error Handling

AAD enrichment uses graceful degradation:
- If Graph API call fails, scan continues without ServicePrincipals
- Error is logged with full details
- User is warned but scan completes successfully
- Other resources are not affected

Example error log:
```
Failed to fetch service principals from Graph API: HttpResponseError: Insufficient privileges
Continuing without service principal enrichment
```

## Testing AAD Enrichment

Run the test suite to verify AAD enrichment works:
```bash
uv run pytest tests/test_aad_enrichment_execution.py -v
```

Expected output:
```
test_aad_enrichment_executes PASSED
test_aad_enrichment_handles_errors PASSED
test_aad_enrichment_disabled PASSED
```

## Additional Resources

- Microsoft Graph API: https://docs.microsoft.com/en-us/graph/api/serviceprincipal-list
- Azure AD Permissions: https://docs.microsoft.com/en-us/graph/permissions-reference
- Issue #408: ServicePrincipal enrichment implementation
