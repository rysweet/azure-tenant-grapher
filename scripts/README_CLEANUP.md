# Iteration Resource Cleanup

## Quick Start

### 1. Preview What Will Be Deleted (Dry-Run)

```bash
./scripts/cleanup_iteration_resources.sh ITERATION15_ --dry-run
```

### 2. Execute Cleanup

```bash
./scripts/cleanup_iteration_resources.sh ITERATION15_
```

### 3. Verify Cleanup

```bash
az group list --query "[?starts_with(name, 'ITERATION15_')]"
```

## Files

| File | Purpose |
|------|---------|
| `cleanup_iteration_resources.sh` | Main cleanup script |
| `cleanup_examples.sh` | Quick reference and examples |
| `../tests/test_cleanup_script.sh` | Test suite for validation |
| `../docs/cleanup_iteration_resources.md` | Comprehensive documentation |

## Features

### What It Cleans Up

1. **Resource Groups** - All resource groups matching the iteration prefix
2. **Key Vaults** - Soft-deleted Key Vaults (purge to free names)
3. **Storage Accounts** - Orphaned storage accounts with matching prefix
4. **Individual Resources** - Fallback if resource group deletion fails

### Safety Features

- **Dry-run mode** - Preview without making changes
- **Confirmation prompts** - Interactive approval before deletion
- **Comprehensive logging** - Detailed progress and error reporting
- **Parallel deletion** - Fast cleanup using async operations
- **Error handling** - Continue on failures, report issues

## Common Use Cases

### Before New Iteration Deployment

```bash
# Step 1: Preview
./scripts/cleanup_iteration_resources.sh ITERATION15_ --dry-run

# Step 2: Clean
./scripts/cleanup_iteration_resources.sh ITERATION15_

# Step 3: Verify
az group list --query "[?starts_with(name, 'ITERATION15_')]"

# Step 4: Deploy
uv run atg create-tenant --spec demos/simuland_iteration2/iteration15/iteration15_spec.md
```

### CI/CD Pipeline

```bash
# Non-interactive cleanup for automation
./scripts/cleanup_iteration_resources.sh ITERATION15_ --skip-confirmation --verbose || true

# Then deploy
uv run atg create-tenant --spec spec.md
```

### Cleanup Multiple Iterations

```bash
# Clean iterations 10-15
for i in {10..15}; do
  ./scripts/cleanup_iteration_resources.sh ITERATION${i}_ --skip-confirmation
done
```

### Specific Subscription

```bash
# Target specific Azure subscription
./scripts/cleanup_iteration_resources.sh ITERATION15_ \
  --subscription xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

## Command-Line Options

```
Usage: cleanup_iteration_resources.sh <ITERATION_PREFIX> [OPTIONS]

Options:
  --dry-run              Show what would be deleted (no changes)
  --skip-confirmation    Skip interactive prompts (automation)
  --subscription <id>    Use specific Azure subscription
  --verbose              Enable detailed logging
  -h, --help            Show help message
```

## Example Output

### Dry-Run Mode

```
========================================
[INFO] Azure Iteration Resource Cleanup
========================================

[INFO] Dry-run mode enabled
[INFO] Using subscription: Pay-As-You-Go

[INFO] Step 1: Processing resource groups...
[SUCCESS] Found 3 resource group(s):
  - ITERATION15_network-rg (eastus) - Succeeded
  - ITERATION15_compute-rg (westus2) - Succeeded
  - ITERATION15_monitoring-rg (centralus) - Succeeded

[DRY-RUN] Would delete resource group: ITERATION15_network-rg
[DRY-RUN] Would delete resource group: ITERATION15_compute-rg
[DRY-RUN] Would delete resource group: ITERATION15_monitoring-rg

========================================
[INFO] Cleanup Summary
========================================
Prefix:              ITERATION15_
Dry-run mode:        true
Resource Groups:     3
Key Vaults:          1
Storage Accounts:    1
========================================

[WARNING] This was a DRY-RUN. No resources were actually deleted.
[INFO] Run without --dry-run to perform actual deletion.
```

### Actual Deletion

```
[WARNING] About to delete 3 resource group(s) with prefix 'ITERATION15_'
Are you sure? [y/N] y

[INFO] Deleting 3 resource group(s)...
[SUCCESS] Initiated deletion of: ITERATION15_network-rg (async)
[SUCCESS] Initiated deletion of: ITERATION15_compute-rg (async)
[SUCCESS] Initiated deletion of: ITERATION15_monitoring-rg (async)

[INFO] Waiting for resource group deletions to complete...
[INFO] Still waiting for 2 resource group(s) to be deleted... (10s elapsed)
[SUCCESS] All resource groups have been deleted

[SUCCESS] Cleanup initiated successfully!
```

## Troubleshooting

### Resource Group Won't Delete

**Problem:** Resource group deletion fails

**Solutions:**
```bash
# Check for locks
az lock list --resource-group ITERATION15_network-rg

# Remove locks
az lock delete --name <lock-name> --resource-group ITERATION15_network-rg

# Delete individual resources first
az resource list --resource-group ITERATION15_network-rg -o table
az resource delete --ids <resource-id>
```

### Key Vault Purge Fails

**Problem:** Soft-deleted Key Vault can't be purged

**Solutions:**
```bash
# Wait for deletion to complete
az keyvault list-deleted --query "[?name=='iteration15keyvault']"

# Manual purge
az keyvault purge --name iteration15keyvault --location eastus
```

### Permission Denied

**Problem:** Not logged in or insufficient permissions

**Solutions:**
```bash
# Login
az login

# Set subscription
az account set --subscription <subscription-id>

# Verify permissions
az role assignment list --assignee $(az account show --query user.name -o tsv)
```

### Storage Account Name Conflict

**Problem:** Storage account already exists

**Solutions:**
```bash
# Check if exists
az storage account show --name iteration15storage

# Delete manually
az storage account delete --name iteration15storage --yes
```

## Performance

| Resource Type | Typical Time |
|---------------|--------------|
| Empty Resource Group | 1-2 minutes |
| Resource Group with VNets | 5-10 minutes |
| Resource Group with VMs | 10-20 minutes |
| Key Vault Purge | 2-5 minutes |
| Storage Account | 1-3 minutes |

**Note:** Script uses parallel deletion (`--no-wait`) for faster cleanup.

## Best Practices

### 1. Always Dry-Run First

```bash
./scripts/cleanup_iteration_resources.sh ITERATION15_ --dry-run
```

### 2. Use Consistent Naming

Choose one prefix pattern and stick to it:
- `ITERATION15_` (uppercase with underscore)
- `iteration15-` (lowercase with dash)

### 3. Verify Before Deploy

```bash
# Should return empty
az group list --query "[?starts_with(name, 'ITERATION15_')]"
```

### 4. Log Cleanups

```bash
echo "$(date): Cleaned ITERATION15_" >> cleanup_log.txt
./scripts/cleanup_iteration_resources.sh ITERATION15_
```

### 5. Handle Errors in Automation

```bash
# Continue even if cleanup fails
./scripts/cleanup_iteration_resources.sh ITERATION15_ --skip-confirmation || true
```

## Security Considerations

### Audit Trail

All deletions are logged in Azure Activity Log:

```bash
az monitor activity-log list \
  --start-time "2025-10-14T00:00:00Z" \
  --query "[?contains(operationName.value, 'Delete')]"
```

### Required Permissions

- `Contributor` on subscription or resource groups
- `Key Vault Contributor` for purging Key Vaults
- `Storage Account Contributor` for storage deletion

### Production Safety

```bash
# Add subscription check
CURRENT_SUB=$(az account show --query name -o tsv)
if [[ "$CURRENT_SUB" != *"Dev"* ]]; then
  echo "Error: Not in dev subscription"
  exit 1
fi

./scripts/cleanup_iteration_resources.sh ITERATION15_
```

## Integration Examples

### Makefile

```makefile
.PHONY: clean-iteration
clean-iteration:
	./scripts/cleanup_iteration_resources.sh $(PREFIX) --skip-confirmation

.PHONY: deploy-iteration
deploy-iteration: clean-iteration
	uv run atg create-tenant --spec $(SPEC_FILE)
```

### GitHub Actions

```yaml
- name: Cleanup Previous Iteration
  run: |
    ./scripts/cleanup_iteration_resources.sh ITERATION${{ matrix.iteration }}_ \
      --skip-confirmation \
      --subscription ${{ secrets.AZURE_SUBSCRIPTION_ID }}
  continue-on-error: true

- name: Deploy New Iteration
  run: |
    uv run atg create-tenant --spec iteration${{ matrix.iteration }}/spec.md
```

### Bash Script

```bash
#!/bin/bash
set -euo pipefail

ITERATION="ITERATION15_"
SPEC_FILE="demos/simuland_iteration2/iteration15/iteration15_spec.md"

# Cleanup
echo "Cleaning up resources from previous iteration..."
./scripts/cleanup_iteration_resources.sh "$ITERATION" --skip-confirmation

# Verify cleanup
echo "Verifying cleanup..."
REMAINING=$(az group list --query "[?starts_with(name, '$ITERATION')] | length(@)")
if [ "$REMAINING" -ne 0 ]; then
  echo "Warning: $REMAINING resource groups still exist"
fi

# Deploy
echo "Deploying new iteration..."
uv run atg create-tenant --spec "$SPEC_FILE"
```

## Monitoring

### Check Cleanup Progress

```bash
# Resource groups
az group list --query "[?starts_with(name, 'ITERATION15_')]" -o table

# Soft-deleted Key Vaults
az keyvault list-deleted --query "[?starts_with(name, 'iteration15')]" -o table

# Activity log
az monitor activity-log list \
  --max-events 50 \
  --query "[?contains(resourceGroupName, 'ITERATION15_')]" \
  -o table
```

### Wait for Completion

```bash
# Poll until all resource groups are deleted
while true; do
  count=$(az group list --query "[?starts_with(name, 'ITERATION15_')] | length(@)")
  if [ "$count" -eq 0 ]; then
    echo "All resource groups deleted!"
    break
  fi
  echo "Waiting for $count resource groups to be deleted..."
  sleep 10
done
```

## Testing

Run the test suite to verify script functionality:

```bash
./tests/test_cleanup_script.sh
```

Expected output:
```
╔══════════════════════════════════════════════════════════════════════╗
║          Cleanup Script Test Suite                                  ║
╚══════════════════════════════════════════════════════════════════════╝

[PASS] Script file exists
[PASS] Script is executable
[PASS] Help message displays correctly
[PASS] All required functions present
...

Tests Passed: 15
Tests Failed: 0

All tests passed!
```

## Related Documentation

- **Comprehensive Guide**: `../docs/cleanup_iteration_resources.md`
- **Quick Examples**: `cleanup_examples.sh`
- **Test Suite**: `../tests/test_cleanup_script.sh`
- **Main CLI Docs**: `../CLAUDE.md`

## Support

For issues or questions:

1. Run with `--verbose` flag for detailed output
2. Check Azure Activity Log for deletion errors
3. Review comprehensive docs at `docs/cleanup_iteration_resources.md`
4. Open GitHub issue with full output

## Version History

- **v1.0.0** (2025-10-14)
  - Initial release
  - Resource group deletion
  - Key Vault purging
  - Storage account cleanup
  - Dry-run mode
  - Confirmation prompts
  - Parallel deletion
  - Comprehensive logging
