# Tenant Reset Guide

Complete guide to using Azure Tenant Grapher's Tenant Reset feature for safe, controlled Azure resource cleanup with automatic ATG Service Principal preservation.

## Overview

The Tenant Reset feature provides safe, automated deletion of Azure resources across four scopes:

- **Tenant**: Delete all resources in all subscriptions
- **Subscription**: Delete all resources in specific subscriptions
- **Resource Group**: Delete specific resource groups
- **Resource**: Delete individual resources

All operations automatically preserve the Azure Tenant Grapher Service Principal to prevent self-destruction.

## Quick Start

```bash
# Reset entire tenant (requires confirmation)
atg reset tenant --tenant-id <tenant-id>

# Reset specific subscription
atg reset subscription --subscription-ids <sub-id>

# Reset resource group
atg reset resource-group --resource-group-names <rg-name> --subscription-id <sub-id>

# Reset single resource
atg reset resource --resource-id "/subscriptions/.../resourceGroups/.../providers/..."
```

## Safety Features

### 1. ATG Service Principal Preservation

The system automatically identifies and preserves the Azure Tenant Grapher Service Principal in all reset operations. This prevents accidental deletion of the identity ATG uses to access Azure.

**What gets preserved:**
- ATG Service Principal object
- All role assignments for ATG SP
- Any Key Vault access policies for ATG SP

**How it works:**
The service uses the current authentication context to identify the ATG Service Principal, then excludes it from all deletion operations.

### 2. Dry-Run Mode

Always test reset operations before executing:

```bash
# Preview tenant reset without deleting anything
atg reset tenant --tenant-id <tenant-id> --dry-run

# Preview subscription reset
atg reset subscription --subscription-ids <sub-id> --dry-run
```

Dry-run output shows:
- Total resources to be deleted
- Resources by type
- Dependency-ordered deletion sequence
- Preserved resources (ATG SP and dependencies)

### 3. Type "DELETE" Confirmation

All destructive operations require typing "DELETE" in uppercase:

```
About to delete 847 resources across 3 subscriptions.
This operation cannot be undone.

Type 'DELETE' to confirm: DELETE
```

This confirmation is skipped in dry-run mode.

### 4. Dependency-Aware Deletion

Resources are deleted in reverse dependency order to avoid conflicts:

1. VMs and compute resources first
2. Network interfaces and related resources
3. Virtual networks and subnets
4. Storage accounts and disks
5. Resource groups last (if empty)

## Command Reference

### Tenant Reset

Delete all resources in all subscriptions:

```bash
atg reset tenant --tenant-id <tenant-id> [OPTIONS]
```

**Options:**
- `--tenant-id TEXT`: Azure tenant ID (required)
- `--dry-run`: Preview without deleting
- `--skip-confirmation`: Skip "DELETE" confirmation (use with caution)
- `--concurrency INTEGER`: Parallel deletion threads (default: 5)
- `--log-level TEXT`: Logging level (default: INFO)

**Example:**

```bash
# Preview tenant reset
atg reset tenant --tenant-id 12345678-1234-1234-1234-123456789abc --dry-run

# Execute tenant reset
atg reset tenant --tenant-id 12345678-1234-1234-1234-123456789abc
Type 'DELETE' to confirm: DELETE

# Tenant reset with increased concurrency
atg reset tenant --tenant-id 12345678-1234-1234-1234-123456789abc --concurrency 10
```

### Subscription Reset

Delete all resources in specific subscriptions:

```bash
atg reset subscription --subscription-ids <sub-id1> [<sub-id2>...] [OPTIONS]
```

**Options:**
- `--subscription-ids TEXT`: One or more subscription IDs (required)
- `--dry-run`: Preview without deleting
- `--skip-confirmation`: Skip "DELETE" confirmation
- `--concurrency INTEGER`: Parallel deletion threads (default: 5)
- `--log-level TEXT`: Logging level (default: INFO)

**Example:**

```bash
# Reset single subscription
atg reset subscription --subscription-ids aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee

# Reset multiple subscriptions
atg reset subscription \
  --subscription-ids \
    aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee \
    ffffffff-gggg-hhhh-iiii-jjjjjjjjjjjj
```

### Resource Group Reset

Delete specific resource groups:

```bash
atg reset resource-group \
  --resource-group-names <rg1> [<rg2>...] \
  --subscription-id <sub-id> \
  [OPTIONS]
```

**Options:**
- `--resource-group-names TEXT`: One or more resource group names (required)
- `--subscription-id TEXT`: Subscription containing the resource groups (required)
- `--dry-run`: Preview without deleting
- `--skip-confirmation`: Skip "DELETE" confirmation
- `--concurrency INTEGER`: Parallel deletion threads (default: 5)
- `--log-level TEXT`: Logging level (default: INFO)

**Example:**

```bash
# Delete single resource group
atg reset resource-group \
  --resource-group-names test-rg \
  --subscription-id aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee

# Delete multiple resource groups
atg reset resource-group \
  --resource-group-names test-rg-1 test-rg-2 dev-rg \
  --subscription-id aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee
```

### Resource Reset

Delete individual resources:

```bash
atg reset resource --resource-id <resource-id> [OPTIONS]
```

**Options:**
- `--resource-id TEXT`: Full Azure resource ID (required)
- `--dry-run`: Preview without deleting
- `--skip-confirmation`: Skip "DELETE" confirmation
- `--log-level TEXT`: Logging level (default: INFO)

**Example:**

```bash
# Delete specific VM
atg reset resource \
  --resource-id "/subscriptions/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm"

# Dry-run for single resource
atg reset resource \
  --resource-id "/subscriptions/.../providers/Microsoft.Storage/storageAccounts/mystorageaccount" \
  --dry-run
```

## Audit Logging

All reset operations are logged to `~/.atg/logs/tenant-reset/` with:

- Timestamp and operation scope
- Resources deleted (count and types)
- Resources preserved (ATG SP and dependencies)
- Errors and warnings
- Execution time and performance metrics

**Log location:**

```
~/.atg/logs/tenant-reset/
├── reset-tenant-2026-01-27-143022.log
├── reset-subscription-2026-01-27-143145.log
└── reset-resource-group-2026-01-27-143302.log
```

**Log format:**

```
2026-01-27 14:30:22 [INFO] Starting tenant reset: tenant_id=12345678-1234-1234-1234-123456789abc
2026-01-27 14:30:23 [INFO] Discovered 847 resources across 3 subscriptions
2026-01-27 14:30:23 [INFO] Preserving ATG Service Principal: sp_object_id=87654321-4321-4321-4321-210987654321
2026-01-27 14:30:24 [INFO] User confirmed deletion by typing 'DELETE'
2026-01-27 14:30:24 [INFO] Deleting resources in dependency order (5 concurrent threads)
2026-01-27 14:30:45 [INFO] Deleted 150/847 resources (17.7%)
2026-01-27 14:31:30 [INFO] Deleted 500/847 resources (59.0%)
2026-01-27 14:32:15 [INFO] Deleted 847/847 resources (100.0%)
2026-01-27 14:32:15 [INFO] Tenant reset completed successfully in 113.2 seconds
```

## Use Cases

### 1. Development Environment Cleanup

Reset test subscriptions after development cycles:

```bash
# Clean up dev subscription
atg reset subscription --subscription-ids <dev-sub-id>
```

### 2. Disaster Recovery Testing

Test disaster recovery procedures by resetting and recreating environments:

```bash
# Step 1: Reset tenant
atg reset tenant --tenant-id <tenant-id>

# Step 2: Recreate from IaC
cd iac-output
terraform apply
```

### 3. Cost Optimization

Remove unused resource groups to reduce costs:

```bash
# Identify unused resource groups
atg query "MATCH (rg:ResourceGroup) WHERE NOT (rg)<-[:IN_RESOURCE_GROUP]-() RETURN rg.name"

# Delete empty/unused resource groups
atg reset resource-group --resource-group-names old-project-rg --subscription-id <sub-id>
```

### 4. Compliance Cleanup

Remove resources that violate compliance policies:

```bash
# Find non-compliant resources via ATG graph query
atg query "MATCH (r:Resource) WHERE r.location = 'westus' RETURN r.id"

# Delete non-compliant resources individually
atg reset resource --resource-id <resource-id>
```

### 5. Test Tenant Cleanup

Clean up automated test tenants after testing:

```bash
# Reset test tenant (with automation-friendly skip confirmation)
atg reset tenant --tenant-id <test-tenant-id> --skip-confirmation
```

## Best Practices

### 1. Always Dry-Run First

Never execute a reset operation without first running with `--dry-run`:

```bash
# Preview operation
atg reset tenant --tenant-id <tenant-id> --dry-run

# Review output carefully

# Execute if satisfied
atg reset tenant --tenant-id <tenant-id>
```

### 2. Use Resource-Specific Resets When Possible

Prefer narrower scopes to reduce blast radius:

```bash
# Better: Delete specific resource group
atg reset resource-group --resource-group-names test-rg --subscription-id <sub-id>

# Worse: Delete entire subscription if only one RG needs cleanup
atg reset subscription --subscription-ids <sub-id>
```

### 3. Monitor Logs During Execution

Tail logs in real-time to monitor progress:

```bash
# Terminal 1: Execute reset
atg reset subscription --subscription-ids <sub-id>

# Terminal 2: Monitor logs
tail -f ~/.atg/logs/tenant-reset/reset-subscription-*.log
```

### 4. Verify ATG SP Preservation

After reset, verify ATG Service Principal still exists:

```bash
# Check ATG SP exists
az ad sp show --id <atg-sp-object-id>

# Verify ATG can still authenticate
az login --service-principal --username <app-id> --password <secret> --tenant <tenant-id>
```

### 5. Keep Logs for Audit Trail

Preserve reset logs for compliance and troubleshooting:

```bash
# Archive logs periodically
tar -czf tenant-reset-logs-2026-01.tar.gz ~/.atg/logs/tenant-reset/

# Upload to blob storage for long-term retention
az storage blob upload --account-name logs --container-name atg-audit --file tenant-reset-logs-2026-01.tar.gz
```

## Troubleshooting

See [Tenant Reset Troubleshooting](../reference/TENANT_RESET_TROUBLESHOOTING.md) for common errors and solutions.

## Related Documentation

- [Tenant Reset Safety Guide](./TENANT_RESET_SAFETY.md) - Detailed safety mechanisms
- [Tenant Reset API Reference](../reference/TENANT_RESET_API.md) - Service architecture and APIs
- [Tenant Reset Troubleshooting](../reference/TENANT_RESET_TROUBLESHOOTING.md) - Error resolution

## Metadata

---
last_updated: 2026-01-27
status: current
category: guides
related_commands: reset
---
