# Tenant Reset Quick Reference

Quick command reference for Azure Tenant Grapher's Tenant Reset feature.

## Commands

### Tenant Reset

Delete all resources in all subscriptions:

```bash
# Preview (dry-run)
atg reset tenant --tenant-id <tenant-id> --dry-run

# Execute
atg reset tenant --tenant-id <tenant-id>
```

### Subscription Reset

Delete all resources in specific subscriptions:

```bash
# Single subscription
atg reset subscription --subscription-ids <sub-id> --dry-run
atg reset subscription --subscription-ids <sub-id>

# Multiple subscriptions
atg reset subscription --subscription-ids <sub-id-1> <sub-id-2> --dry-run
atg reset subscription --subscription-ids <sub-id-1> <sub-id-2>
```

### Resource Group Reset

Delete specific resource groups:

```bash
# Single resource group
atg reset resource-group --resource-group-names <rg-name> --subscription-id <sub-id> --dry-run
atg reset resource-group --resource-group-names <rg-name> --subscription-id <sub-id>

# Multiple resource groups
atg reset resource-group --resource-group-names <rg-1> <rg-2> --subscription-id <sub-id>
```

### Resource Reset

Delete individual resource:

```bash
# Preview
atg reset resource --resource-id "/subscriptions/.../providers/..." --dry-run

# Execute
atg reset resource --resource-id "/subscriptions/.../providers/..."
```

## Common Options

| Option | Description | Default |
|--------|-------------|---------|
| `--dry-run` | Preview without deleting | False |
| `--skip-confirmation` | Skip "DELETE" confirmation | False |
| `--concurrency INTEGER` | Parallel deletion threads | 5 |
| `--log-level TEXT` | Logging level | INFO |

## Safety Features

| Feature | Purpose |
|---------|---------|
| **ATG SP Preservation** | Automatically protects ATG Service Principal |
| **Dry-Run Mode** | Preview all operations before execution |
| **Type "DELETE" Confirmation** | Explicit user acknowledgment required |
| **Dependency-Aware Deletion** | Correct ordering prevents orphaned resources |
| **Audit Logging** | Complete record in `~/.atg/logs/tenant-reset/` |

## Quick Examples

### Test Environment Cleanup

```bash
# Preview cleanup
atg reset subscription --subscription-ids <dev-sub-id> --dry-run

# Clean up after confirmation
atg reset subscription --subscription-ids <dev-sub-id>
```

### Remove Specific Resource Group

```bash
# Single command cleanup
atg reset resource-group --resource-group-names old-project-rg --subscription-id <sub-id>
```

### Automated Testing Cleanup

```bash
# Skip confirmation for CI/CD pipelines
atg reset tenant --tenant-id <test-tenant-id> --skip-confirmation
```

### High-Speed Cleanup

```bash
# Increase concurrency for large tenants
atg reset tenant --tenant-id <tenant-id> --concurrency 10
```

## Confirmation Flow

```
About to delete 845 resources across 3 subscriptions.
This operation cannot be undone.

Type 'DELETE' to confirm: DELETE
```

Type exactly `DELETE` in uppercase to proceed. Any other input cancels the operation.

## Log Location

All reset operations log to:

```
~/.atg/logs/tenant-reset/
├── reset-tenant-2026-01-27-143022.log
├── reset-subscription-2026-01-27-143145.log
└── reset-resource-group-2026-01-27-143302.log
```

## Common Errors

| Error | Solution |
|-------|----------|
| ATG SP Not Found | `az login --service-principal ...` |
| Permission Denied | `az role assignment create --role Owner` |
| Resource Has Lock | `az lock delete --name <lock-name>` |
| Dependency Exists | Re-run reset (recalculates dependencies) |
| Concurrent Operation | Wait 2 minutes and retry |

## Next Steps

- [Tenant Reset Guide](../guides/TENANT_RESET_GUIDE.md) - Complete user guide
- [Tenant Reset Safety Guide](../guides/TENANT_RESET_SAFETY.md) - Detailed safety mechanisms
- [Tenant Reset Troubleshooting](../reference/TENANT_RESET_TROUBLESHOOTING.md) - Error resolution

## Metadata

---
last_updated: 2026-01-27
status: current
category: howto
related_commands: reset
---
