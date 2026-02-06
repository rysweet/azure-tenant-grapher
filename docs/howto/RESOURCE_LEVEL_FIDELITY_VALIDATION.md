# Resource-Level Fidelity Validation

Validate individual resource properties between source and replicated Azure environments to ensure accurate tenant replication.

## Quick Start

Validate all resources in current layer:

```bash
azure-tenant-grapher fidelity --resource-level
```

Compare specific resource type with JSON export:

```bash
azure-tenant-grapher fidelity --resource-level \
  --resource-type "Microsoft.Storage/storageAccounts" \
  --output fidelity-report.json
```

## Contents

- [What Is Resource-Level Validation?](#what-is-resource-level-validation)
- [When to Use It](#when-to-use-it)
- [Command Syntax](#command-syntax)
- [Understanding Output](#understanding-output)
- [Filtering Resources](#filtering-resources)
- [Historical Tracking](#historical-tracking)
- [Security Considerations](#security-considerations)
- [Troubleshooting](#troubleshooting)

## What Is Resource-Level Validation?

Resource-level fidelity validation compares **individual resource properties** between your source Azure subscription and the replicated target subscription. Unlike tenant-level validation (which provides aggregate metrics), resource-level validation shows exactly which properties differ for each resource.

**What it validates:**

- Resource configuration properties (SKU, location, settings)
- Resource tags and metadata
- Dependent resource relationships
- Security configurations (within redaction rules)

**What it redacts (for security):**

- Passwords and connection strings
- API keys and secrets
- Certificate private keys
- Storage account keys
- Any property containing "password", "key", "secret", "token"

## When to Use It

Use resource-level validation when:

- **Post-deployment verification**: Confirm replicated resources match source configurations
- **Troubleshooting mismatches**: Investigate specific property discrepancies identified in tenant-level reports
- **Compliance auditing**: Validate resource configurations meet requirements
- **Drift detection**: Compare current state against baseline after changes
- **Debugging replication issues**: Identify which resource types have persistent configuration problems

**Don't use it when:**

- You need high-level aggregate metrics (use tenant-level validation instead)
- You're validating large environments (1000+ resources) without filtering
- You need real-time monitoring (resource-level is point-in-time snapshot)

## Command Syntax

```bash
azure-tenant-grapher fidelity --resource-level [OPTIONS]
```

### Options

| Option | Description | Example |
|--------|-------------|---------|
| `--resource-level` | Enable resource-level validation (required) | `--resource-level` |
| `--resource-type TEXT` | Filter by Azure resource type | `--resource-type "Microsoft.Compute/virtualMachines"` |
| `--output FILE` | Export to JSON file | `--output validation-report.json` |
| `--track` | Save metrics to historical database | `--track` |
| `--redaction-level LEVEL` | Set redaction level (FULL/MINIMAL/NONE) | `--redaction-level MINIMAL` |
| `--source-subscription ID` | Override source subscription | `--source-subscription abc123...` |
| `--target-subscription ID` | Override target subscription | `--target-subscription def456...` |

### Common Usage Patterns

**Basic validation (console output):**
```bash
azure-tenant-grapher fidelity --resource-level
```

**Validate specific resource type:**
```bash
azure-tenant-grapher fidelity --resource-level \
  --resource-type "Microsoft.Network/virtualNetworks"
```

**Export to file with tracking:**
```bash
azure-tenant-grapher fidelity --resource-level \
  --output reports/$(date +%Y%m%d)-fidelity.json \
  --track
```

**Minimal redaction for internal review:**
```bash
azure-tenant-grapher fidelity --resource-level \
  --redaction-level MINIMAL \
  --output internal-review.json
```

## Understanding Output

### Console Output Format

```
Resource-Level Fidelity Validation Report
=========================================

Layer: production-replication
Source Subscription: abc123-def456-... (Source Tenant)
Target Subscription: ghi789-jkl012-... (Target Tenant)

Resource Type: Microsoft.Storage/storageAccounts
-------------------------------------------------
Resource: mystorageaccount123
  Status: MISMATCH
  Discrepancies:
    ✗ sku.name: source='Standard_LRS', target='Premium_LRS'
    ✗ properties.accessTier: source='Hot', target='Cool'
    ✓ location: East US (match)
    ✓ tags.environment: production (match)

Resource: backupstorage456
  Status: MATCH
  All properties validated successfully.

Resource Type: Microsoft.Compute/virtualMachines
-------------------------------------------------
Resource: webapp-vm-01
  Status: MISSING_TARGET
  Error: Resource exists in source but not found in target subscription

Summary
-------
Total Resources Validated: 47
  - Exact Match: 38 (81%)
  - Mismatches: 7 (15%)
  - Missing in Target: 2 (4%)
  - Missing in Source: 0 (0%)

Top Mismatched Properties:
  1. sku.name: 4 resources
  2. properties.accessTier: 3 resources
  3. tags.costCenter: 2 resources

Validation completed in 12.3 seconds.
```

### JSON Output Format

```json
{
  "metadata": {
    "validation_timestamp": "2026-02-05T14:32:18Z",
    "layer_id": "production-replication",
    "source_subscription": "abc123-def456-...",
    "target_subscription": "ghi789-jkl012-...",
    "redaction_level": "FULL",
    "resource_type_filter": null
  },
  "resources": [
    {
      "resource_id": "/subscriptions/.../storageAccounts/mystorageaccount123",
      "resource_name": "mystorageaccount123",
      "resource_type": "Microsoft.Storage/storageAccounts",
      "status": "MISMATCH",
      "source_exists": true,
      "target_exists": true,
      "property_comparisons": [
        {
          "property_path": "sku.name",
          "source_value": "Standard_LRS",
          "target_value": "Premium_LRS",
          "match": false
        },
        {
          "property_path": "properties.accessTier",
          "source_value": "Hot",
          "target_value": "Cool",
          "match": false
        },
        {
          "property_path": "location",
          "source_value": "eastus",
          "target_value": "eastus",
          "match": true
        }
      ],
      "mismatch_count": 2,
      "match_count": 18
    }
  ],
  "summary": {
    "total_resources": 47,
    "exact_match": 38,
    "mismatches": 7,
    "missing_target": 2,
    "missing_source": 0,
    "match_percentage": 81,
    "top_mismatched_properties": [
      {"property": "sku.name", "count": 4},
      {"property": "properties.accessTier", "count": 3}
    ]
  },
  "security_warnings": [
    "This report contains redacted sensitive properties. Redaction level: FULL",
    "Do not share this report outside authorized personnel without security review."
  ]
}
```

## Filtering Resources

### By Resource Type

Validate specific Azure resource types:

```bash
# Virtual Machines only
azure-tenant-grapher fidelity --resource-level \
  --resource-type "Microsoft.Compute/virtualMachines"

# Storage Accounts only
azure-tenant-grapher fidelity --resource-level \
  --resource-type "Microsoft.Storage/storageAccounts"

# All Network resources
azure-tenant-grapher fidelity --resource-level \
  --resource-type "Microsoft.Network/*"
```

### By Subscription

Override default subscription detection:

```bash
azure-tenant-grapher fidelity --resource-level \
  --source-subscription <source-sub-id> \
  --target-subscription <target-sub-id>
```

### Combining Filters

```bash
# Validate VMs in specific subscriptions with tracking
azure-tenant-grapher fidelity --resource-level \
  --resource-type "Microsoft.Compute/virtualMachines" \
  --source-subscription abc123... \
  --target-subscription def456... \
  --track \
  --output vm-validation.json
```

## Historical Tracking

Track validation metrics over time to detect drift and monitor replication quality:

```bash
# Enable tracking during validation
azure-tenant-grapher fidelity --resource-level --track
```

**What gets tracked:**

- Validation timestamp
- Match/mismatch counts per resource type
- Specific property discrepancies
- Drift from previous validations

**Query historical data:**

> **Note**: Advanced reporting commands (`fidelity-history`, `fidelity-diff`) are planned for a future release. The `--track` flag saves metrics to the database, but advanced report generation is not yet implemented.

**Current workaround - Manual comparison using `jq`:**

```bash
# Compare two JSON reports manually
# 1. Save baseline validation
azure-tenant-grapher fidelity --resource-level --track \
  --output baseline-2026-01-15.json

# 2. Save current validation
azure-tenant-grapher fidelity --resource-level --track \
  --output current-2026-02-05.json

# 3. Compare match percentages
echo "Baseline match rate:"
jq '.summary.match_percentage' baseline-2026-01-15.json

echo "Current match rate:"
jq '.summary.match_percentage' current-2026-02-05.json

# 4. Compare specific resource mismatches
jq '.resources[] | select(.status=="MISMATCH") | .resource_name' \
  baseline-2026-01-15.json > baseline-mismatches.txt

jq '.resources[] | select(.status=="MISMATCH") | .resource_name' \
  current-2026-02-05.json > current-mismatches.txt

diff baseline-mismatches.txt current-mismatches.txt
```

**Planned for future release:**

```bash
# View validation history (COMING SOON)
azure-tenant-grapher report fidelity-history --days 30

# Compare two validations (COMING SOON)
azure-tenant-grapher report fidelity-diff \
  --baseline 2026-01-15 \
  --current 2026-02-05
```

## Security Considerations

### Redaction Levels

**FULL** (default) - Maximum security:
- Redacts all sensitive properties (passwords, keys, secrets, tokens)
- Redacts connection strings and certificates
- Safe for external sharing (with approval)

**MINIMAL** - Internal use only:
- Redacts only critical secrets (passwords, private keys)
- Includes connection strings and non-sensitive keys
- For internal security team review only

**NONE** - Development/testing only:
- No redaction applied
- **WARNING**: Never use in production or with real credentials

### Safe Sharing Practices

1. **Always use FULL redaction** for reports leaving your security team
2. **Verify redaction** before sharing reports externally
3. **Store reports securely** (encrypted storage, access controls)
4. **Rotate credentials** if unredacted reports are exposed
5. **Audit access** to validation reports and outputs

See [Security Guide](../reference/RESOURCE_LEVEL_VALIDATION_SECURITY.md) for complete security practices.

## Troubleshooting

### No Resources Found

**Problem**: Validation returns empty results or "No resources found"

**Solutions**:
- Verify source and target subscriptions contain resources
- Check `--resource-type` filter isn't too restrictive
- Ensure Azure authentication is active (`az account show`)
- Confirm layer contains scanned resources

### Performance Issues

**Problem**: Validation takes too long (>5 minutes) or times out

**Solutions**:
- Use `--resource-type` filter to reduce scope
- Validate specific resource types in separate runs
- Consider using Remote Mode for large tenants (1000+ resources)
- Check network connectivity to Azure APIs

### Property Mismatches Not Expected

**Problem**: Resources show mismatches but configurations look identical

**Possible causes**:
- **Case sensitivity**: Azure property names are case-sensitive
- **Default values**: Source has explicit value, target using Azure default
- **Timing**: Target resource not fully provisioned yet (retry after 5 minutes)
- **Hidden properties**: Read-only properties generated by Azure (ignore these)

**Resolution**:
```bash
# Export detailed comparison
azure-tenant-grapher fidelity --resource-level \
  --resource-type "Microsoft.Storage/storageAccounts" \
  --output detailed-comparison.json

# Review JSON for exact property paths and values
jq '.resources[] | select(.status=="MISMATCH")' detailed-comparison.json
```

### Authentication Errors

**Problem**: "Authentication failed" or "Unauthorized" errors

**Solutions**:
```bash
# Re-authenticate with Azure
az login --tenant <tenant-id>

# Verify correct subscription is active
az account show

# Check required permissions
az role assignment list --assignee $(az account show --query user.name -o tsv)
```

## Next Steps

- See [Examples](../examples/RESOURCE_LEVEL_VALIDATION_EXAMPLES.md) for real-world scenarios
- Read [Integration Guide](../concepts/FIDELITY_VALIDATION_INTEGRATION.md) for workflow integration
- Review [Security Guide](../reference/RESOURCE_LEVEL_VALIDATION_SECURITY.md) for security best practices
- Check [Fidelity Command Reference](../reference/FIDELITY_COMMAND_REFERENCE.md) for complete API details

---

**Last Updated**: 2026-02-05
**Status**: current
**Category**: howto
