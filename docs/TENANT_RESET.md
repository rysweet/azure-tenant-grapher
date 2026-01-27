# Tenant Reset Feature

## Overview

The Tenant Reset feature allows users to delete Azure resources and Entra ID objects at different scopes (tenant-wide, subscription, resource group, or individual resource) with comprehensive safety mechanisms.

**CRITICAL**: This feature DELETES ACTUAL Azure resources and Entra ID objects. Use with extreme caution.

## Safety Mechanisms

1. **Explicit Confirmation Required**: Users must type "DELETE" exactly (case-sensitive) to proceed
2. **Preview Before Deletion**: Shows counts and warnings before any deletion
3. **ATG Service Principal Preservation**: The ATG service principal used for provisioning is NEVER deleted
4. **Dry-Run Mode**: Test the feature without actual deletion
5. **Comprehensive Audit Logging**: All operations are logged with timestamps and user info
6. **Rate Limiting**: API endpoints are rate-limited to prevent accidental rapid deletions
7. **Authorization**: Only authorized users can perform reset operations

## Reset Scopes

### 1. Tenant-Level Reset

Deletes:
- All Azure resources across all subscriptions
- All Entra ID users
- All Entra ID groups
- All Entra ID service principals (except ATG SP)
- All graph data in Neo4j

Preserves:
- ATG service principal
- ATG configuration and credentials

**CLI Command**:
```bash
atg reset tenant [--dry-run]
```

**API Endpoint**:
```http
GET  /api/v1/reset/tenant/preview      # Preview deletion
POST /api/v1/reset/tenant               # Execute deletion
```

### 2. Subscription-Level Reset

Deletes:
- All Azure resources in the specified subscription
- Graph data for resources in that subscription

Does NOT affect:
- Entra ID objects (subscription scope only affects Azure resources)
- Resources in other subscriptions

**CLI Command**:
```bash
atg reset subscription <subscription-id> [--dry-run]
```

**API Endpoint**:
```http
GET  /api/v1/reset/subscription/{subscription_id}/preview
POST /api/v1/reset/subscription/{subscription_id}
```

### 3. Resource Group Reset

Deletes:
- All Azure resources in the specified resource group
- Graph data for resources in that resource group

**CLI Command**:
```bash
atg reset resource-group <subscription-id> <rg-name> [--dry-run]
```

**API Endpoint**:
```http
GET  /api/v1/reset/resource-group/{subscription_id}/{rg_name}/preview
POST /api/v1/reset/resource-group/{subscription_id}/{rg_name}
```

### 4. Resource-Level Reset

Deletes:
- The specified individual Azure resource
- Graph node for that resource

**CLI Command**:
```bash
atg reset resource <resource-id> [--dry-run]
```

Example resource ID:
```
/subscriptions/12345678-1234-1234-1234-123456789abc/resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/vm1
```

**API Endpoint**:
```http
GET  /api/v1/reset/resource/preview?resource_id=<resource-id>
POST /api/v1/reset/resource?resource_id=<resource-id>
```

## CLI Usage

### Interactive Confirmation Flow

1. **Preview**: Shows deletion counts and warnings
2. **Prominent Warning**: Displays a visual warning box
3. **Confirmation Prompt**: User must type "DELETE" exactly
4. **Execution**: Performs deletion and shows results

### Example Session

```bash
$ atg reset tenant

Loading preview...

Deletion Preview:
------------------------------------------------------------
Scope: tenant

Azure Resources: 47
Entra ID Users: 12
Entra ID Groups: 5
Entra ID Service Principals: 8 (excluding ATG SP)
Graph Nodes: 72

Estimated Duration: 120 seconds

⚠️  This will DELETE ALL Azure resources in the tenant
⚠️  This will DELETE ALL Entra ID users, groups, and service principals (except ATG SP)
⚠️  This action CANNOT be undone
⚠️  Production data will be permanently lost

╔══════════════════════════════════════════════════════════╗
║                                                          ║
║  ⚠️  WARNING: DESTRUCTIVE OPERATION                      ║
║                                                          ║
║  This will DELETE ALL Azure resources and Entra ID objects! ║
║  This action CANNOT be undone!                          ║
║  Production data will be permanently lost!              ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝

Type DELETE to confirm (or anything else to cancel): DELETE

Executing tenant reset...

Reset Operation Result:
------------------------------------------------------------
Status: completed
Success: True

Deleted:
  Azure Resources: 47
  Entra ID Users: 12
  Entra ID Groups: 5
  Entra ID Service Principals: 8
  Graph Nodes: 72
  Graph Relationships: 120

Duration: 125.45 seconds
```

### Dry-Run Mode

Test the feature without actual deletion:

```bash
atg reset tenant --dry-run
atg reset subscription <sub-id> --dry-run
atg reset resource-group <sub-id> <rg-name> --dry-run
atg reset resource <resource-id> --dry-run
```

Dry-run mode:
- Shows the same preview
- Requires confirmation
- Does NOT delete anything
- Returns zero counts in the result

## API Usage

### Preview Endpoint

**Request**:
```http
GET /api/v1/reset/tenant/preview
Authorization: Bearer <api-key>
```

**Response**:
```json
{
  "scope": {
    "scope_type": "tenant",
    "subscription_id": null,
    "resource_group_name": null,
    "resource_id": null
  },
  "azure_resources_count": 47,
  "entra_users_count": 12,
  "entra_groups_count": 5,
  "entra_service_principals_count": 8,
  "graph_nodes_count": 72,
  "estimated_duration_seconds": 120,
  "warnings": [
    "⚠️  This will DELETE ALL Azure resources in the tenant",
    "⚠️  This will DELETE ALL Entra ID users, groups, and service principals (except ATG SP)",
    "⚠️  This action CANNOT be undone",
    "⚠️  Production data will be permanently lost"
  ]
}
```

### Execution Endpoint

**Request**:
```http
POST /api/v1/reset/tenant
Authorization: Bearer <api-key>
Content-Type: application/json

{
  "confirmation_token": "DELETE",
  "dry_run": false
}
```

**Response**:
```json
{
  "scope": {
    "scope_type": "tenant",
    "subscription_id": null,
    "resource_group_name": null,
    "resource_id": null
  },
  "status": "completed",
  "success": true,
  "deleted_azure_resources": 47,
  "deleted_entra_users": 12,
  "deleted_entra_groups": 5,
  "deleted_entra_service_principals": 8,
  "deleted_graph_nodes": 72,
  "deleted_graph_relationships": 120,
  "errors": [],
  "duration_seconds": 125.45,
  "started_at": "2026-01-27T12:00:00",
  "completed_at": "2026-01-27T12:02:05"
}
```

### Error Responses

#### Invalid Confirmation Token

**Status**: `400 Bad Request`

```json
{
  "detail": "Confirmation token must be exactly 'DELETE' (case-sensitive). Provided: 'delete'"
}
```

#### Rate Limit Exceeded

**Status**: `429 Too Many Requests`

```json
{
  "detail": "Rate limit exceeded. Try again in 5 minutes."
}
```

#### Unauthorized

**Status**: `401 Unauthorized`

```json
{
  "detail": "Invalid API key"
}
```

## Configuration

### Environment Variables

```bash
# REQUIRED: ATG service principal ID to preserve
export ATG_SERVICE_PRINCIPAL_ID=<sp-id>

# OPTIONAL: Rate limiting configuration
export ATG_RESET_RATE_LIMIT_PREVIEW=10    # requests per minute
export ATG_RESET_RATE_LIMIT_EXECUTE=1     # requests per 5 minutes

# OPTIONAL: Authorization configuration
export ATG_RESET_REQUIRE_ADMIN=true       # require admin role
```

### Configuration File

Create `config/reset.yaml`:

```yaml
reset:
  atg_sp_id: ${ATG_SERVICE_PRINCIPAL_ID}
  rate_limits:
    preview: 10  # per minute
    execute: 1   # per 5 minutes
  authorization:
    require_admin: true
    allowed_roles:
      - admin
      - reset_operator
  audit:
    enabled: true
    retention_days: 90
```

## ATG Service Principal Preservation

### How It Works

The ATG service principal is the identity used to provision and manage the ATG infrastructure. Deleting it would break ATG's ability to operate.

**Protection Mechanisms**:

1. **Configuration**: ATG SP ID is configured via `ATG_SERVICE_PRINCIPAL_ID` environment variable
2. **Filtering**: Before deletion, the service filters out the ATG SP from the deletion list
3. **Double-Check**: Even if filtering fails, there's a safety check that prevents ATG SP deletion
4. **Logging**: When ATG SP is detected in scope, a CRITICAL log message is generated

### Configuring ATG SP ID

**Method 1: Environment Variable**
```bash
export ATG_SERVICE_PRINCIPAL_ID=<your-sp-id>
```

**Method 2: Configuration File**
```yaml
reset:
  atg_sp_id: <your-sp-id>
```

**Finding Your ATG SP ID**:
```bash
# If you created the SP with name "atg-sp"
az ad sp list --display-name "atg-sp" --query "[0].id" -o tsv
```

**WARNING**: If `ATG_SERVICE_PRINCIPAL_ID` is not configured, the reset operation will proceed but with a warning that ATG SP preservation cannot be guaranteed.

## Security Considerations

### Authorization

- API endpoints require authentication via API key
- Additional authorization checks verify user has permission to delete resources
- Azure RBAC permissions are checked for the scope being deleted

### Rate Limiting

**Preview Endpoints**:
- Limit: 10 requests per minute per user
- Purpose: Prevent resource exhaustion

**Execution Endpoints**:
- Limit: 1 request per 5 minutes per user
- Purpose: Prevent accidental rapid-fire deletions

### Audit Logging

All reset operations are logged with:
- Timestamp
- User identity
- Operation type (preview/execute)
- Scope (tenant/subscription/resource group/resource)
- Result (success/failure/partial)
- Deleted resource counts
- Errors (if any)

**Audit Log Retention**: Minimum 90 days (configurable)

**Audit Log Location**: Existing ATG audit log system

## Error Handling

### Common Errors

| Error | Description | Resolution |
|-------|-------------|------------|
| `InvalidConfirmationToken` | User didn't type "DELETE" exactly | Type "DELETE" (case-sensitive) |
| `RateLimitExceeded` | Too many reset requests | Wait for rate limit to reset |
| `Unauthorized` | User lacks permissions | Verify API key and user permissions |
| `ATGServicePrincipalInScope` | ATG SP would be deleted | Check `ATG_SERVICE_PRINCIPAL_ID` configuration |
| `AzureResourceDeletionFailed` | Azure resource deletion failed | Check Azure permissions and resource locks |
| `EntraObjectDeletionFailed` | Entra ID object deletion failed | Check Entra ID permissions |
| `GraphCleanupFailed` | Neo4j cleanup failed | Check Neo4j connection and credentials |

### Partial Completion

If some deletions succeed and others fail, the result status will be `partial`.

**Example**:
```json
{
  "status": "partial",
  "success": false,
  "deleted_azure_resources": 45,  // 45 out of 47 succeeded
  "errors": [
    "Failed to delete resource: /subscriptions/.../vm1 - resource locked",
    "Failed to delete resource: /subscriptions/.../vm2 - resource locked"
  ]
}
```

**Rollback**: Azure resource deletion is irreversible. There is NO automatic rollback.

**Recommendation**: If partial completion occurs:
1. Review the errors in the result
2. Fix the issues (e.g., remove resource locks)
3. Run the reset operation again (idempotent - safe to re-run)

## Testing

### Unit Tests

```bash
pytest tests/services/test_tenant_reset_models.py -v
pytest tests/services/test_tenant_reset_service.py -v
```

**Coverage**: 44 tests covering:
- Confirmation token validation (4 tests)
- ATG SP preservation (3 tests)
- Dry-run mode (1 test)
- Preview operations (4 tests)
- Scope validation (4 tests)
- Result serialization (3 tests)
- Error handling (2 tests)
- Model validation (24 tests)

### Integration Tests

```bash
pytest tests/integration/test_tenant_reset_integration.py -v
```

**Note**: Integration tests use mocked Azure SDK and Graph API clients.

### Safety Tests

```bash
pytest tests/safety/test_tenant_reset_safety.py -v
```

Critical safety tests verify:
- ATG SP is NEVER deleted
- Confirmation token must be exact match
- Dry-run mode doesn't delete anything
- Rate limiting works correctly

### Manual Testing

**Before Production Use**:

1. **Test in Dev Environment**:
   ```bash
   # Use dry-run mode first
   atg reset tenant --dry-run
   
   # Then test on a non-production tenant
   atg reset subscription <dev-subscription-id>
   ```

2. **Verify ATG SP Preservation**:
   ```bash
   # Check ATG SP is configured
   echo $ATG_SERVICE_PRINCIPAL_ID
   
   # Run preview and verify SP count is correct
   atg reset tenant --dry-run
   ```

3. **Test Confirmation Flow**:
   - Verify typing "delete" (lowercase) is rejected
   - Verify typing "CONFIRM" is rejected
   - Verify typing "DELETE" (exact) is accepted

## Troubleshooting

### ATG SP Not Preserved

**Symptom**: Warning "ATG service principal ID not configured"

**Solution**:
```bash
# Find your ATG SP ID
az ad sp list --display-name "atg-sp" --query "[0].id" -o tsv

# Set environment variable
export ATG_SERVICE_PRINCIPAL_ID=<sp-id>

# Or add to configuration file
echo "reset:" >> config/reset.yaml
echo "  atg_sp_id: <sp-id>" >> config/reset.yaml
```

### Rate Limit Exceeded

**Symptom**: 429 Too Many Requests

**Solution**: Wait 5 minutes between execution requests

**Alternative**: Adjust rate limits in configuration (not recommended for production)

### Permission Denied

**Symptom**: 403 Forbidden or Azure permission errors

**Solution**:
- Verify user has Azure Owner or Contributor role
- Verify API key has admin permissions
- Check Azure RBAC assignments for the scope being deleted

### Partial Deletion

**Symptom**: Some resources deleted, others failed

**Common Causes**:
- Resource locks
- Dependencies between resources
- Azure API throttling
- Network issues

**Solution**:
1. Review error messages in result
2. Remove resource locks: `az resource lock delete --name <lock-name> --resource-group <rg>`
3. Re-run reset operation (idempotent)

## Best Practices

1. **Always Use Dry-Run First**: Test with `--dry-run` before actual deletion
2. **Start Small**: Test on individual resources or resource groups before tenant-level
3. **Verify ATG SP Configuration**: Ensure `ATG_SERVICE_PRINCIPAL_ID` is set correctly
4. **Review Preview**: Carefully review counts and warnings before confirming
5. **Use in Dev First**: Test thoroughly in development environments
6. **Monitor Audit Logs**: Review audit logs after operations
7. **Backup Critical Data**: Ensure backups exist before using (deletion is irreversible)

## Architecture

### Components

- **Models**: `src/services/tenant_reset_models.py` - Type-safe data structures
- **Service**: `src/services/tenant_reset_service.py` - Core deletion logic
- **API Router**: `src/remote/server/routers/reset.py` - FastAPI endpoints
- **CLI Commands**: `src/commands/reset.py` - Click command group
- **Tests**: `tests/services/test_tenant_reset_*.py` - Comprehensive test suite

### Design Principles

1. **Safety-First**: Multiple confirmation layers prevent accidental deletion
2. **Ruthless Simplicity**: Clear separation of preview vs execution
3. **Zero-BS Implementation**: ATG SP preservation is hardcoded safety check
4. **Comprehensive Logging**: All operations audited with structured logging
5. **Type Safety**: Dataclasses and enums ensure type-safe operations
6. **Error Recovery**: Graceful handling of partial failures

## License

This feature is part of Azure Tenant Grapher, subject to the project's license.

## Issue Reference

- GitHub Issue: #627 - Tenant Reset Feature with Granular Scopes
