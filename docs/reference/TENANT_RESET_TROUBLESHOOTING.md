# Tenant Reset Troubleshooting

Common errors, solutions, and recovery procedures for Azure Tenant Grapher's Tenant Reset feature.

## Common Errors

### 1. ATG Service Principal Not Found

**Error Message:**

```
ERROR: Unable to identify ATG Service Principal.
Cannot proceed with reset operation - risk of self-destruction.
```

**Cause:**

ATG cannot determine which Service Principal it's using for authentication, preventing it from preserving itself during reset.

**Solutions:**

**Option 1: Authenticate with Azure CLI**

```bash
# Authenticate with the service principal
az login --service-principal \
  --username <app-id> \
  --password <secret> \
  --tenant <tenant-id>

# Verify authentication
az account show

# Retry reset operation
atg reset tenant --tenant-id <tenant-id> --dry-run
```

**Option 2: Check Environment Variables**

```bash
# Ensure service principal credentials are set
echo $AZURE_CLIENT_ID
echo $AZURE_TENANT_ID
echo $AZURE_CLIENT_SECRET  # Should not display actual secret

# Set if missing
export AZURE_CLIENT_ID="<app-id>"
export AZURE_TENANT_ID="<tenant-id>"
export AZURE_CLIENT_SECRET="<secret>"
```

**Option 3: Verify Service Principal Exists**

```bash
# Check if service principal exists in Azure AD
az ad sp list --display-name "azure-tenant-grapher"

# If missing, recreate
az ad sp create-for-rbac \
  --name azure-tenant-grapher \
  --role Reader \
  --scopes /subscriptions/<sub-id>
```

### 2. Permission Denied Errors

**Error Message:**

```
ERROR: Insufficient permissions to delete resources.
AuthorizationFailed: The client '<client-id>' with object id '<object-id>'
does not have authorization to perform action 'Microsoft.Compute/virtualMachines/delete'.
```

**Cause:**

ATG Service Principal lacks the necessary role assignments to delete resources.

**Solutions:**

**Option 1: Grant Owner Role (Recommended for Reset Operations)**

```bash
# Grant Owner role at subscription level
az role assignment create \
  --assignee <atg-sp-object-id> \
  --role Owner \
  --scope /subscriptions/<subscription-id>

# Verify role assignment
az role assignment list --assignee <atg-sp-object-id>
```

**Option 2: Grant Contributor Role (Alternative)**

```bash
# Grant Contributor role (can delete resources but not manage access)
az role assignment create \
  --assignee <atg-sp-object-id> \
  --role Contributor \
  --scope /subscriptions/<subscription-id>
```

**Option 3: Grant Resource-Specific Roles**

```bash
# For resource group scope, grant role at RG level
az role assignment create \
  --assignee <atg-sp-object-id> \
  --role Contributor \
  --scope /subscriptions/<sub-id>/resourceGroups/<rg-name>
```

### 3. Resource Has Delete Lock

**Error Message:**

```
ERROR: Failed to delete resource.
ScopeLocked: The scope '/subscriptions/.../resourceGroups/test-rg/providers/Microsoft.Network/networkSecurityGroups/nsg-locked'
cannot perform delete operation because following scope(s) are locked:
'/subscriptions/.../resourceGroups/test-rg/providers/Microsoft.Network/networkSecurityGroups/nsg-locked'.
```

**Cause:**

Resource or resource group has an Azure delete lock preventing deletion.

**Solutions:**

**Option 1: Remove Lock via Azure CLI**

```bash
# List locks on resource
az lock list --resource-group <rg-name> --resource-name <resource-name> --resource-type <resource-type>

# Delete specific lock
az lock delete \
  --name <lock-name> \
  --resource-group <rg-name> \
  --resource-name <resource-name> \
  --resource-type <resource-type>

# Retry deletion
atg reset resource --resource-id <resource-id>
```

**Option 2: Remove Lock via Azure Portal**

1. Navigate to resource in Azure Portal
2. Go to "Locks" section
3. Delete the lock
4. Retry reset operation

**Option 3: Remove All Locks in Scope**

```bash
# Remove all locks in resource group
for lock in $(az lock list --resource-group <rg-name> --query "[].name" -o tsv); do
  az lock delete --name "$lock" --resource-group <rg-name>
done

# Retry reset operation
atg reset resource-group --resource-group-names <rg-name> --subscription-id <sub-id>
```

### 4. Resource Deletion Failed - Dependency Exists

**Error Message:**

```
ERROR: Failed to delete Virtual Network.
InUseSubnetCannotBeDeleted: Subnet vnet-1/subnet-1 is in use by
/subscriptions/.../networkInterfaces/nic-1 and cannot be deleted.
```

**Cause:**

ATG's dependency ordering failed to correctly identify a dependency, or a resource was created after scope calculation.

**Solutions:**

**Option 1: Manual Deletion of Dependencies**

```bash
# Identify dependent resources
az network nic show --ids <nic-id> --query "ipConfigurations[].subnet.id"

# Delete dependent resources first
atg reset resource --resource-id <nic-id>

# Retry deletion of original resource
atg reset resource --resource-id <vnet-id>
```

**Option 2: Re-run Reset Operation**

```bash
# ATG will recalculate scope and try again
atg reset resource-group --resource-group-names <rg-name> --subscription-id <sub-id>
```

**Option 3: Increase Retry Delays**

```bash
# Wait for Azure to catch up with deletions
sleep 60

# Retry reset operation
atg reset tenant --tenant-id <tenant-id>
```

### 5. Concurrent Operation in Progress

**Error Message:**

```
ERROR: Failed to delete resource.
ConflictError: Another operation on this resource is in progress.
```

**Cause:**

Azure is still processing a previous operation on the resource.

**Solutions:**

**Option 1: Wait and Retry**

```bash
# Wait for Azure operation to complete
sleep 120

# Retry reset operation
atg reset subscription --subscription-ids <sub-id>
```

**Option 2: Reduce Concurrency**

```bash
# Lower concurrency to reduce conflicts
atg reset tenant --tenant-id <tenant-id> --concurrency 2
```

**Option 3: Check Azure Portal for Operation Status**

1. Navigate to resource in Azure Portal
2. Check "Activity Log" for ongoing operations
3. Wait for operation to complete
4. Retry reset

### 6. Subscription Not Found

**Error Message:**

```
ERROR: Subscription 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee' not found.
```

**Cause:**

ATG Service Principal does not have access to the subscription, or subscription ID is incorrect.

**Solutions:**

**Option 1: Verify Subscription ID**

```bash
# List accessible subscriptions
az account list --query "[].{Name:name, SubscriptionId:id}" -o table

# Compare with subscription ID in error
```

**Option 2: Grant Access to Subscription**

```bash
# Grant ATG SP access to subscription
az role assignment create \
  --assignee <atg-sp-object-id> \
  --role Reader \
  --scope /subscriptions/<subscription-id>

# Retry reset operation
atg reset subscription --subscription-ids <subscription-id>
```

**Option 3: Switch Active Subscription**

```bash
# Set active subscription
az account set --subscription <subscription-id>

# Verify
az account show

# Retry reset operation
atg reset subscription --subscription-ids <subscription-id>
```

### 7. Dry-Run Output Shows Zero Resources

**Symptoms:**

```bash
$ atg reset tenant --tenant-id <tenant-id> --dry-run

=== TENANT RESET DRY-RUN ===
Resources discovered: 0
Resources to delete: 0
Resources to preserve: 1
```

**Cause:**

ATG Service Principal lacks Reader role to discover resources.

**Solutions:**

**Option 1: Grant Reader Role**

```bash
# Grant Reader role at tenant level
az role assignment create \
  --assignee <atg-sp-object-id> \
  --role Reader \
  --scope /subscriptions/<subscription-id>

# Retry dry-run
atg reset tenant --tenant-id <tenant-id> --dry-run
```

**Option 2: Verify Authentication**

```bash
# Check current authentication context
az account show

# Ensure correct tenant
az login --tenant <tenant-id>

# Retry dry-run
atg reset tenant --tenant-id <tenant-id> --dry-run
```

### 8. Deletion Hangs on Specific Resource Type

**Symptoms:**

Reset operation hangs during deletion wave without progress for 10+ minutes.

**Cause:**

Azure API is slow or unresponsive for specific resource type, or resource is stuck in provisioning state.

**Solutions:**

**Option 1: Cancel and Exclude Problematic Resources**

```bash
# Press Ctrl+C to cancel operation

# Review logs to identify hanging resource type
cat ~/.atg/logs/tenant-reset/reset-*.log | grep "Deleting" | tail -n 20

# Delete problematic resources manually
az resource delete --ids <resource-id>

# Retry reset operation
atg reset tenant --tenant-id <tenant-id>
```

**Option 2: Increase Timeout**

```bash
# Set longer timeout for Azure operations
export AZURE_OPERATION_TIMEOUT=600  # 10 minutes

# Retry reset operation
atg reset tenant --tenant-id <tenant-id>
```

**Option 3: Check Resource State in Portal**

1. Navigate to hanging resource in Azure Portal
2. Check provisioning state
3. If stuck in "Deleting" or "Failed", manually delete
4. Retry reset operation

## Recovery Procedures

### Full Reset Recovery

If a reset operation fails partway through, follow these steps:

**Step 1: Review Logs**

```bash
# Find latest reset log
ls -lt ~/.atg/logs/tenant-reset/

# Review log for errors
cat ~/.atg/logs/tenant-reset/reset-tenant-2026-01-27-*.log | grep ERROR
```

**Step 2: Identify Failed Resources**

```bash
# Extract failed resource IDs from log
grep "Failed to delete" ~/.atg/logs/tenant-reset/reset-tenant-*.log | \
  sed 's/.*resource: //' > failed-resources.txt

# Count failed resources
wc -l failed-resources.txt
```

**Step 3: Categorize Failures**

```bash
# Group by error type
grep "Failed to delete" ~/.atg/logs/tenant-reset/reset-tenant-*.log | \
  grep -oP 'Error: \K[^:]+' | sort | uniq -c
```

**Step 4: Address Each Failure Category**

```bash
# For delete locks:
az lock list --query "[?name=='<lock-name>']" | jq -r '.[].id' | \
  xargs -I {} az lock delete --ids {}

# For permission errors:
az role assignment create --assignee <atg-sp-object-id> --role Contributor --scope <scope>

# For dependency errors:
# Re-run reset (will recalculate dependencies)
atg reset tenant --tenant-id <tenant-id>
```

**Step 5: Retry Reset Operation**

```bash
# Retry with increased concurrency and logging
atg reset tenant --tenant-id <tenant-id> --concurrency 10 --log-level DEBUG
```

### Partial Deletion Verification

After a failed reset, verify what was actually deleted:

```bash
# Count remaining resources in scope
az resource list --subscription <sub-id> --query "length(@)"

# Compare with dry-run output before reset
atg reset subscription --subscription-ids <sub-id> --dry-run
```

## Diagnostic Commands

### Check ATG Service Principal Status

```bash
# Verify ATG SP exists
az ad sp show --id <atg-sp-object-id>

# Check role assignments
az role assignment list --assignee <atg-sp-object-id> --all

# Test authentication
az login --service-principal \
  --username <app-id> \
  --password <secret> \
  --tenant <tenant-id>
```

### Check Resource Locks

```bash
# List all locks in subscription
az lock list --subscription <sub-id> -o table

# List locks for specific resource
az lock list --resource-group <rg-name> --resource-name <resource-name> --resource-type <resource-type>

# Count total locks
az lock list --subscription <sub-id> --query "length(@)"
```

### Check Resource Dependencies

```bash
# List resources with dependencies (Azure Resource Graph)
az graph query -q "Resources | where type =~ 'Microsoft.Network/virtualNetworks' | project name, id, properties.subnets"

# Check specific resource dependencies
az resource show --ids <resource-id> --query "properties.dependencies"
```

### Monitor Deletion Progress

```bash
# Watch resource count in real-time
watch -n 10 "az resource list --subscription <sub-id> --query 'length(@)'"

# Tail reset operation logs
tail -f ~/.atg/logs/tenant-reset/reset-tenant-*.log
```

## Best Practices for Troubleshooting

### 1. Always Check Dry-Run First

```bash
# Dry-run reveals most permission and lock issues
atg reset tenant --tenant-id <tenant-id> --dry-run 2>&1 | tee dry-run-output.txt

# Review for warnings or errors
grep -i "error\|warning\|failed" dry-run-output.txt
```

### 2. Enable Debug Logging

```bash
# Run with debug logging for detailed error information
atg reset tenant --tenant-id <tenant-id> --log-level DEBUG
```

### 3. Test with Small Scope First

```bash
# Test with single resource group before full tenant reset
atg reset resource-group --resource-group-names test-rg --subscription-id <sub-id>

# If successful, proceed to larger scopes
atg reset subscription --subscription-ids <sub-id>
```

### 4. Use Idempotent Operations

```bash
# Reset operations are idempotent - safe to retry
atg reset tenant --tenant-id <tenant-id>

# If fails, retry without data loss risk
atg reset tenant --tenant-id <tenant-id>
```

### 5. Monitor Azure Service Health

Check Azure Service Health before large reset operations:

```bash
# Check service health via CLI
az rest --method get --url "https://management.azure.com/subscriptions/<sub-id>/providers/Microsoft.ResourceHealth/availabilityStatuses?api-version=2020-05-01"

# Or visit Azure Portal > Service Health
```

## Getting Help

### Log Collection for Support

If issues persist, collect diagnostic information:

```bash
# Create support bundle
mkdir atg-reset-support-$(date +%Y%m%d)
cd atg-reset-support-$(date +%Y%m%d)

# Copy logs
cp ~/.atg/logs/tenant-reset/* ./

# Capture environment
az account show > azure-context.json
az role assignment list --assignee <atg-sp-object-id> > role-assignments.json
az lock list --subscription <sub-id> > locks.json

# Capture dry-run output
atg reset tenant --tenant-id <tenant-id> --dry-run > dry-run-output.txt 2>&1

# Create tarball
cd ..
tar -czf atg-reset-support-$(date +%Y%m%d).tar.gz atg-reset-support-$(date +%Y%m%d)/
```

### GitHub Issues

Report issues at: https://github.com/rysweet/azure-tenant-grapher/issues

Include:
- Error message and full log output
- Dry-run output
- Azure environment details (subscription count, resource count)
- ATG version: `atg --version`

## Related Documentation

- [Tenant Reset Guide](../guides/TENANT_RESET_GUIDE.md) - User guide and command reference
- [Tenant Reset Safety Guide](../guides/TENANT_RESET_SAFETY.md) - Safety mechanisms
- [Tenant Reset API Reference](./TENANT_RESET_API.md) - Service architecture

## Metadata

---
last_updated: 2026-01-27
status: current
category: reference
troubleshooting: true
---
