# Iteration Resource Cleanup Script

## Overview

The `cleanup_iteration_resources.sh` script automates the deletion of Azure resources from previous iterations to prevent "already exists" errors during new deployments.

## Location

```
scripts/cleanup_iteration_resources.sh
```

## Purpose

When deploying new iterations, resources from previous iterations can cause conflicts due to:
- Resource groups with the same name already existing
- Soft-deleted Key Vaults blocking new Key Vault creation
- Orphaned storage accounts preventing name reuse
- Individual resources with name conflicts

This script systematically identifies and removes all iteration-specific resources.

## Features

### Cleanup Actions

1. **Resource Group Deletion**
   - Lists all resource groups matching the iteration prefix
   - Deletes resource groups in parallel using `--no-wait`
   - Monitors deletion progress

2. **Key Vault Purging**
   - Identifies soft-deleted Key Vaults (remain for 90 days by default)
   - Purges them permanently to free up names
   - Handles multi-region Key Vaults

3. **Storage Account Cleanup**
   - Finds orphaned storage accounts with iteration prefix
   - Deletes storage accounts that might block name reuse
   - Case-insensitive matching (storage names are lowercase)

4. **Individual Resource Deletion**
   - Fallback mechanism if resource group deletion fails
   - Deletes resources individually within blocked RGs
   - Handles locked or protected resources

### Safety Features

1. **Dry-Run Mode**
   - Preview all deletions without making changes
   - Validate script behavior before actual execution
   - Safe testing in production environments

2. **Confirmation Prompts**
   - Interactive confirmation for each resource type
   - Prevents accidental deletions
   - Can be skipped for CI/CD automation

3. **Comprehensive Logging**
   - Color-coded output (INFO, SUCCESS, WARNING, ERROR)
   - Verbose mode for detailed debugging
   - Progress reporting for long operations

4. **Error Handling**
   - Continues on individual failures
   - Reports failed deletions
   - Provides troubleshooting guidance

## Usage

### Basic Syntax

```bash
./scripts/cleanup_iteration_resources.sh <ITERATION_PREFIX> [OPTIONS]
```

### Common Examples

#### 1. Dry-Run (Recommended First Step)

Preview what would be deleted without making any changes:

```bash
./scripts/cleanup_iteration_resources.sh ITERATION15_ --dry-run
```

**Output:**
```
[INFO] Dry-run mode enabled
[INFO] Using subscription: Pay-As-You-Go
[SUCCESS] Found 3 resource group(s):
  - ITERATION15_network-rg (eastus) - Succeeded
  - ITERATION15_compute-rg (westus2) - Succeeded
  - ITERATION15_monitoring-rg (centralus) - Succeeded
[DRY-RUN] Would delete resource group: ITERATION15_network-rg
[DRY-RUN] Would delete resource group: ITERATION15_compute-rg
[DRY-RUN] Would delete resource group: ITERATION15_monitoring-rg
```

#### 2. Interactive Deletion (With Confirmation)

Delete resources with confirmation prompts:

```bash
./scripts/cleanup_iteration_resources.sh ITERATION15_
```

**Interaction:**
```
[WARNING] About to delete 3 resource group(s) with prefix 'ITERATION15_'
Are you sure? [y/N] y
[SUCCESS] Initiated deletion of: ITERATION15_network-rg (async)
[SUCCESS] Initiated deletion of: ITERATION15_compute-rg (async)
[SUCCESS] Initiated deletion of: ITERATION15_monitoring-rg (async)
```

#### 3. Automated Deletion (CI/CD)

Skip confirmation prompts for automation:

```bash
./scripts/cleanup_iteration_resources.sh ITERATION15_ --skip-confirmation
```

#### 4. Specific Subscription

Target a specific Azure subscription:

```bash
./scripts/cleanup_iteration_resources.sh ITERATION15_ --subscription xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

#### 5. Verbose Logging

Enable detailed logging for debugging:

```bash
./scripts/cleanup_iteration_resources.sh ITERATION15_ --verbose
```

#### 6. Combined Options

Combine multiple options:

```bash
./scripts/cleanup_iteration_resources.sh ITERATION15_ \
  --subscription xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx \
  --skip-confirmation \
  --verbose
```

## Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--dry-run` | Show what would be deleted without making changes | `false` |
| `--skip-confirmation` | Skip confirmation prompts (for automation) | `false` |
| `--subscription <id>` | Use specific Azure subscription | Current subscription |
| `--verbose` | Enable verbose logging | `false` |
| `-h, --help` | Show help message | - |

## Workflow Integration

### Before New Iteration Deployment

1. **Preview Cleanup:**
   ```bash
   ./scripts/cleanup_iteration_resources.sh ITERATION15_ --dry-run
   ```

2. **Execute Cleanup:**
   ```bash
   ./scripts/cleanup_iteration_resources.sh ITERATION15_
   ```

3. **Verify Cleanup:**
   ```bash
   az group list --query "[?starts_with(name, 'ITERATION15_')]"
   ```

4. **Deploy New Iteration:**
   ```bash
   uv run atg create-tenant --spec demos/simuland_iteration2/iteration15/iteration15_spec.md
   ```

### In CI/CD Pipeline

```yaml
- name: Cleanup Previous Iteration
  run: |
    ./scripts/cleanup_iteration_resources.sh ITERATION${{ matrix.iteration }}_ \
      --skip-confirmation \
      --subscription ${{ secrets.AZURE_SUBSCRIPTION_ID }}
  continue-on-error: true

- name: Deploy New Iteration
  run: |
    uv run atg create-tenant --spec demos/simuland_iteration2/iteration${{ matrix.iteration }}/spec.md
```

### In Makefile

```makefile
.PHONY: clean-iteration
clean-iteration:
	@echo "Cleaning iteration resources: $(ITERATION_PREFIX)"
	./scripts/cleanup_iteration_resources.sh $(ITERATION_PREFIX) --skip-confirmation

.PHONY: deploy-iteration
deploy-iteration: clean-iteration
	@echo "Deploying iteration: $(ITERATION_PREFIX)"
	uv run atg create-tenant --spec $(SPEC_FILE)
```

## Monitoring Deletion Progress

### Check Remaining Resource Groups

```bash
az group list --query "[?starts_with(name, 'ITERATION15_')]" -o table
```

### Check Soft-Deleted Key Vaults

```bash
az keyvault list-deleted --query "[?starts_with(name, 'iteration15')]" -o table
```

### Monitor Activity Log

```bash
az monitor activity-log list \
  --max-events 50 \
  --query "[?contains(resourceGroupName, 'ITERATION15_')]" \
  -o table
```

## Troubleshooting

### Issue: Resource Group Won't Delete

**Symptom:**
```
[ERROR] Failed to delete resource group: ITERATION15_network-rg
```

**Cause:** Resource group may contain locked resources or have dependencies.

**Solution:**
1. Check for resource locks:
   ```bash
   az lock list --resource-group ITERATION15_network-rg
   ```

2. Remove locks:
   ```bash
   az lock delete --name <lock-name> --resource-group ITERATION15_network-rg
   ```

3. Delete individual resources first:
   ```bash
   az resource list --resource-group ITERATION15_network-rg -o table
   az resource delete --ids <resource-id>
   ```

### Issue: Key Vault Purge Fails

**Symptom:**
```
[ERROR] Failed to purge Key Vault: iteration15keyvault
```

**Cause:** Key Vault may still be in deletion state or requires special permissions.

**Solution:**
1. Wait for deletion to complete (can take several minutes):
   ```bash
   az keyvault list-deleted --query "[?name=='iteration15keyvault']"
   ```

2. Ensure you have `purge` permission:
   ```bash
   az keyvault purge --name iteration15keyvault --location eastus
   ```

### Issue: Storage Account Name Conflict

**Symptom:**
```
Storage account 'iteration15storage' already exists
```

**Cause:** Storage account names are globally unique and case-insensitive.

**Solution:**
1. Check if storage account still exists:
   ```bash
   az storage account show --name iteration15storage
   ```

2. Delete manually if needed:
   ```bash
   az storage account delete --name iteration15storage --yes
   ```

### Issue: Permission Denied

**Symptom:**
```
[ERROR] Not logged in to Azure. Please run 'az login' first.
```

**Solution:**
1. Login to Azure:
   ```bash
   az login
   ```

2. Set correct subscription:
   ```bash
   az account set --subscription <subscription-id>
   ```

3. Verify permissions:
   ```bash
   az account show
   az role assignment list --assignee $(az account show --query user.name -o tsv)
   ```

## Best Practices

### 1. Always Dry-Run First

Never skip the dry-run step in production:
```bash
./scripts/cleanup_iteration_resources.sh ITERATION15_ --dry-run
```

### 2. Use Consistent Prefixes

Maintain consistent naming conventions:
- `ITERATION15_` (uppercase, trailing underscore)
- `iteration15-` (lowercase, trailing dash)
- Choose one pattern and stick to it

### 3. Document Iterations

Keep a log of cleaned iterations:
```bash
echo "$(date): Cleaned ITERATION15_" >> cleanup_log.txt
./scripts/cleanup_iteration_resources.sh ITERATION15_
```

### 4. Verify Before Deploy

Always verify cleanup completed:
```bash
# Should return empty
az group list --query "[?starts_with(name, 'ITERATION15_')]"
```

### 5. Handle Errors Gracefully

In automation, continue on cleanup errors:
```bash
./scripts/cleanup_iteration_resources.sh ITERATION15_ --skip-confirmation || true
# Proceed with deployment even if cleanup had issues
```

## Performance Considerations

### Parallel Deletion

The script uses `--no-wait` for parallel deletion:
- Multiple resource groups delete simultaneously
- Significantly faster than sequential deletion
- Monitor with `az group list` to check progress

### Timing Expectations

| Resource Type | Typical Deletion Time |
|---------------|----------------------|
| Empty Resource Group | 1-2 minutes |
| Resource Group with VNets | 5-10 minutes |
| Resource Group with VMs | 10-20 minutes |
| Key Vault Purge | 2-5 minutes |
| Storage Account | 1-3 minutes |

### Wait Strategy

The script waits up to 30 minutes for deletions:
```bash
# Wait for completion
./scripts/cleanup_iteration_resources.sh ITERATION15_

# Or skip waiting and check later
./scripts/cleanup_iteration_resources.sh ITERATION15_ &
```

## Security Considerations

### 1. Audit Trail

All deletions are logged in Azure Activity Log:
```bash
az monitor activity-log list \
  --start-time "2025-10-14T00:00:00Z" \
  --query "[?contains(operationName.value, 'Delete')]"
```

### 2. Role Requirements

Required Azure RBAC roles:
- `Contributor` on subscription or resource groups
- `Key Vault Contributor` for purging Key Vaults
- `Storage Account Contributor` for storage deletion

### 3. Prevent Accidental Production Deletion

Use subscription filters:
```bash
# Only allow in dev subscription
CURRENT_SUB=$(az account show --query name -o tsv)
if [[ "$CURRENT_SUB" != *"Dev"* ]]; then
  echo "Error: Not in dev subscription"
  exit 1
fi
```

## Example Output

### Successful Cleanup

```
========================================
[INFO] Azure Iteration Resource Cleanup
========================================

[INFO] Checking prerequisites...
[SUCCESS] Using subscription: Pay-As-You-Go

[INFO] Step 1: Processing resource groups...
[INFO] Searching for resource groups with prefix: ITERATION15_
[SUCCESS] Found 3 resource group(s):
  - ITERATION15_network-rg (eastus) - Succeeded
  - ITERATION15_compute-rg (westus2) - Succeeded
  - ITERATION15_monitoring-rg (centralus) - Succeeded

[WARNING] About to delete 3 resource group(s) with prefix 'ITERATION15_'
Are you sure? [y/N] y

[INFO] Deleting 3 resource group(s)...
[INFO] Deleting resource group: ITERATION15_network-rg
[SUCCESS] Initiated deletion of: ITERATION15_network-rg (async)
[INFO] Deleting resource group: ITERATION15_compute-rg
[SUCCESS] Initiated deletion of: ITERATION15_compute-rg (async)
[INFO] Deleting resource group: ITERATION15_monitoring-rg
[SUCCESS] Initiated deletion of: ITERATION15_monitoring-rg (async)
[SUCCESS] Initiated deletion of 3 resource group(s)

[INFO] Step 2: Processing soft-deleted Key Vaults...
[INFO] Searching for soft-deleted Key Vaults with prefix: ITERATION15_
[SUCCESS] Found 1 soft-deleted Key Vault(s):
  - iteration15-keyvault (eastus) - Deleted: 2025-10-14T10:30:00Z

[WARNING] About to delete 1 soft-deleted Key Vault(s) with prefix 'ITERATION15_'
Are you sure? [y/N] y

[INFO] Purging 1 soft-deleted Key Vault(s)...
[INFO] Purging Key Vault: iteration15-keyvault (location: eastus)
[SUCCESS] Initiated purge of: iteration15-keyvault (async)

[INFO] Step 3: Processing storage accounts...
[INFO] Searching for storage accounts with prefix: iteration15_
[SUCCESS] Found 1 storage account(s):
  - iteration15storage (RG: ITERATION15_network-rg, Location: eastus)

[WARNING] About to delete 1 storage account(s) with prefix 'ITERATION15_'
Are you sure? [y/N] y

[INFO] Deleting 1 storage account(s)...
[INFO] Deleting storage account: iteration15storage (RG: ITERATION15_network-rg)
[SUCCESS] Deleted storage account: iteration15storage

[INFO] Step 4: Monitoring deletion progress...
[INFO] Still waiting for 3 resource group(s) to be deleted... (10s elapsed)
[INFO] Still waiting for 2 resource group(s) to be deleted... (20s elapsed)
[INFO] Still waiting for 1 resource group(s) to be deleted... (30s elapsed)
[SUCCESS] All resource groups have been deleted

========================================
[INFO] Cleanup Summary
========================================
Prefix:              ITERATION15_
Dry-run mode:        false
Resource Groups:     3
Key Vaults:          1
Storage Accounts:    1
========================================

[SUCCESS] Cleanup initiated successfully!
```

## Related Scripts

- `scripts/deploy_iteration.sh` - Deploy new iteration after cleanup
- `scripts/verify_iteration.sh` - Verify iteration deployment
- `scripts/rollback_iteration.sh` - Rollback failed iteration

## Contributing

When modifying this script:
1. Test with `--dry-run` first
2. Add new cleanup actions to main() function
3. Update help message and documentation
4. Add error handling for new resource types
5. Test in multiple Azure subscriptions

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review Azure Activity Log for deletion errors
3. Open GitHub issue with full output
4. Include `--verbose` output for debugging
