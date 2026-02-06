# Resource-Level Validation Examples

Real-world scenarios and workflows for validating replicated Azure resources.

## Example 1: Post-Deployment Validation

**Scenario**: You've just replicated a production environment to a disaster recovery region. Verify all resources match expected configurations.

### Step 1: Run Complete Validation

```bash
# Validate all resources with tracking
azure-tenant-grapher fidelity --resource-level \
  --track \
  --output dr-validation-$(date +%Y%m%d).json
```

### Expected Output

```
Resource-Level Fidelity Validation Report
=========================================

Layer: production-dr-replication
Source Subscription: prod-eastus (Production)
Target Subscription: prod-westus (DR Region)

Total Resources Validated: 234
  - Exact Match: 228 (97%)
  - Mismatches: 4 (2%)
  - Missing in Target: 2 (1%)

Top Mismatched Properties:
  1. location: 4 resources (expected - different region)
  2. tags.environment: 2 resources

⚠️  WARNING: 2 resources missing in target subscription
```

### Step 2: Investigate Mismatches

```bash
# Filter to mismatched resources only
jq '.resources[] | select(.status == "MISMATCH" or .status == "MISSING_TARGET")' \
  dr-validation-20260205.json
```

### Result Analysis

**Finding**: 4 location mismatches are expected (DR in different region)
**Action**: None required - this is correct replication behavior

**Finding**: 2 resources missing in target
**Action**: Investigate why VMs didn't replicate:

```bash
# Check specific resource type
azure-tenant-grapher fidelity --resource-level \
  --resource-type "Microsoft.Compute/virtualMachines" \
  --output vm-deep-dive.json
```

## Example 2: Storage Account Configuration Audit

**Scenario**: Audit all Storage Account configurations match security baseline after replication.

### Command

```bash
azure-tenant-grapher fidelity --resource-level \
  --resource-type "Microsoft.Storage/storageAccounts" \
  --output storage-audit.json \
  --track
```

### Output

```
Resource Type: Microsoft.Storage/storageAccounts
-------------------------------------------------

Resource: proddata001
  Status: MISMATCH
  Discrepancies:
    ✗ sku.name: source='Standard_GRS', target='Standard_LRS'
    ✗ properties.supportsHttpsTrafficOnly: source=true, target=false
    ✓ properties.encryption.services.blob.enabled: true (match)

Resource: backupstorage002
  Status: MATCH
  All properties validated successfully.

Resource: logstorage003
  Status: MISMATCH
  Discrepancies:
    ✗ properties.minimumTlsVersion: source='TLS1_2', target='TLS1_0'

Summary
-------
Total Resources: 12
  - Exact Match: 9 (75%)
  - Mismatches: 3 (25%)

Critical Issues Found:
  - 1 storage account allows HTTP traffic (security risk)
  - 1 storage account using outdated TLS version
  - 1 storage account using lower redundancy than source
```

### Remediation Actions

**Issue 1: HTTP traffic allowed on `proddata001`**

```bash
# Fix manually via Azure CLI
az storage account update \
  --name proddata001 \
  --resource-group production-rg \
  --https-only true
```

**Issue 2: Outdated TLS version on `logstorage003`**

```bash
az storage account update \
  --name logstorage003 \
  --resource-group production-rg \
  --min-tls-version TLS1_2
```

**Issue 3: Replication redundancy mismatch**

Recreate storage account with correct SKU (requires data migration).

## Example 3: Virtual Network Validation

**Scenario**: Verify virtual networks and subnets replicated correctly with proper address spaces.

### Command

```bash
azure-tenant-grapher fidelity --resource-level \
  --resource-type "Microsoft.Network/virtualNetworks" \
  --output vnet-validation.json
```

### Output

```
Resource Type: Microsoft.Network/virtualNetworks
-------------------------------------------------

Resource: production-vnet
  Status: MATCH
  All properties validated successfully.
  - Address Space: 10.0.0.0/16
  - Subnets: 5 (all match)
  - DNS Servers: Custom (match)

Resource: app-tier-vnet
  Status: MISMATCH
  Discrepancies:
    ✗ properties.addressSpace.addressPrefixes[0]:
       source='10.1.0.0/16', target='10.2.0.0/16'
    ✗ properties.subnets[2].properties.addressPrefix:
       source='10.1.2.0/24', target='10.2.2.0/24'

Resource: dmz-vnet
  Status: MISSING_TARGET
  Error: Resource exists in source but not found in target
```

### Analysis

**`production-vnet`**: Perfect replication - no action needed

**`app-tier-vnet`**: Address space intentionally different in target region (anti-overlap design)
- **Action**: Verify this is intentional design, update documentation

**`dmz-vnet`**: Missing entirely from target
- **Action**: Investigate deployment failure, check logs

```bash
# Check deployment history
azure-tenant-grapher report deployment-history --resource-type "Microsoft.Network/virtualNetworks"
```

## Example 4: Compliance Audit with Historical Tracking

**Scenario**: Monthly compliance audit comparing resource configurations against approved baseline.

### Week 1: Establish Baseline

```bash
# Create baseline validation
azure-tenant-grapher fidelity --resource-level \
  --track \
  --output compliance-baseline-2026-02-01.json

# Results: 100% match (245 resources)
```

### Week 4: Detect Drift

```bash
# Run validation again
azure-tenant-grapher fidelity --resource-level \
  --track \
  --output compliance-check-2026-02-28.json

# Results: 96% match (8 resources drifted)
```

### Compare Baseline to Current

```bash
# Generate drift report
azure-tenant-grapher report fidelity-diff \
  --baseline compliance-baseline-2026-02-01.json \
  --current compliance-check-2026-02-28.json \
  --output drift-report.json
```

### Drift Report Output

```json
{
  "drift_summary": {
    "baseline_date": "2026-02-01",
    "current_date": "2026-02-28",
    "total_resources": 245,
    "drifted_resources": 8,
    "drift_percentage": 3.3
  },
  "drifted_resources": [
    {
      "resource_name": "webapp-vm-03",
      "resource_type": "Microsoft.Compute/virtualMachines",
      "changes": [
        {
          "property": "properties.hardwareProfile.vmSize",
          "baseline_value": "Standard_D2s_v3",
          "current_value": "Standard_D4s_v3",
          "change_type": "value_changed"
        }
      ]
    },
    {
      "resource_name": "sql-db-prod",
      "resource_type": "Microsoft.Sql/servers/databases",
      "changes": [
        {
          "property": "sku.tier",
          "baseline_value": "Standard",
          "current_value": "Premium",
          "change_type": "value_changed"
        }
      ]
    }
  ]
}
```

### Compliance Actions

1. **Review drift report with compliance team**
2. **Approve or reject changes** based on change management policy
3. **Update baseline** if changes are approved
4. **Remediate unauthorized changes** if rejected

## Example 5: Debugging Replication Failures

**Scenario**: Some resources consistently fail to replicate correctly. Use resource-level validation to identify patterns.

### Step 1: Identify Problem Resource Types

```bash
# Run full validation
azure-tenant-grapher fidelity --resource-level \
  --track \
  --output replication-debug.json

# Extract mismatch statistics
jq '.summary.top_mismatched_properties' replication-debug.json
```

### Output

```json
{
  "top_mismatched_properties": [
    {"property": "sku.name", "count": 12},
    {"property": "properties.sslEnforcement", "count": 8},
    {"property": "tags.costCenter", "count": 6}
  ]
}
```

### Step 2: Deep Dive on SKU Mismatches

```bash
# Find all resources with SKU mismatches
jq '.resources[] | select(.property_comparisons[] | select(.property_path == "sku.name" and .match == false))' \
  replication-debug.json > sku-mismatches.json
```

### Analysis

**Finding**: 12 resources have incorrect SKUs in target subscription

**Pattern**: All are database resources (MySQL, PostgreSQL, SQL)

**Root Cause**: IaC template uses different SKU naming convention in target region

### Step 3: Validate Fix

```bash
# After updating IaC template and redeploying
azure-tenant-grapher fidelity --resource-level \
  --resource-type "Microsoft.DBforMySQL/servers" \
  --output mysql-validation-post-fix.json
```

### Result

```
Resource Type: Microsoft.DBforMySQL/servers
-------------------------------------------------

✓ All 8 MySQL resources now match source configuration
✓ SKU mismatches resolved

Summary
-------
Total Resources: 8
  - Exact Match: 8 (100%)
  - Mismatches: 0 (0%)
```

## Example 6: Targeted Resource Type Validation

**Scenario**: Quick validation of specific high-value resources after maintenance window.

### Validate Critical VMs

```bash
azure-tenant-grapher fidelity --resource-level \
  --resource-type "Microsoft.Compute/virtualMachines" \
  --output critical-vms-check.json
```

### Validate Load Balancers

```bash
azure-tenant-grapher fidelity --resource-level \
  --resource-type "Microsoft.Network/loadBalancers" \
  --output lb-check.json
```

### Validate SQL Databases

```bash
azure-tenant-grapher fidelity --resource-level \
  --resource-type "Microsoft.Sql/servers/databases" \
  --output sql-check.json
```

### Combined Report

```bash
# Merge validation results
jq -s '{
  validation_timestamp: now | todate,
  resource_types_validated: [
    "Microsoft.Compute/virtualMachines",
    "Microsoft.Network/loadBalancers",
    "Microsoft.Sql/servers/databases"
  ],
  combined_summary: {
    total_resources: (.[].summary.total_resources | add),
    exact_match: (.[].summary.exact_match | add),
    mismatches: (.[].summary.mismatches | add)
  }
}' critical-vms-check.json lb-check.json sql-check.json > combined-validation.json
```

## Example 7: Minimal Redaction for Security Review

**Scenario**: Security team needs to review resource configurations including connection strings (but not passwords).

### Command

```bash
azure-tenant-grapher fidelity --resource-level \
  --redaction-level MINIMAL \
  --output security-review-minimal-redaction.json
```

### Output Difference

**FULL redaction** (default):
```json
{
  "property_path": "properties.connectionStrings[0].connectionString",
  "source_value": "[REDACTED]",
  "target_value": "[REDACTED]",
  "match": true
}
```

**MINIMAL redaction**:
```json
{
  "property_path": "properties.connectionStrings[0].connectionString",
  "source_value": "Server=tcp:myserver.database.windows.net,1433;Initial Catalog=mydb;",
  "target_value": "Server=tcp:myserver-dr.database.windows.net,1433;Initial Catalog=mydb;",
  "match": false
}
```

### Security Warning

All reports include security warnings:

```json
{
  "security_warnings": [
    "This report contains redacted sensitive properties. Redaction level: MINIMAL",
    "Do not share this report outside security team without additional review.",
    "Connection strings visible but passwords redacted."
  ]
}
```

## Example 8: Automation Integration

**Scenario**: Integrate validation into CI/CD pipeline for infrastructure deployments.

### Pipeline Script

```bash
#!/bin/bash
# validate-deployment.sh

set -e

# Run resource-level validation
echo "Running post-deployment validation..."
azure-tenant-grapher fidelity --resource-level \
  --track \
  --output "validation-$(date +%Y%m%d-%H%M%S).json"

# Check for critical mismatches
MISMATCH_COUNT=$(jq '.summary.mismatches' "validation-$(date +%Y%m%d-%H%M%S).json")
MISSING_COUNT=$(jq '.summary.missing_target' "validation-$(date +%Y%m%d-%H%M%S).json")

if [ "$MISMATCH_COUNT" -gt 5 ]; then
  echo "ERROR: Too many mismatches ($MISMATCH_COUNT). Deployment validation failed."
  exit 1
fi

if [ "$MISSING_COUNT" -gt 0 ]; then
  echo "ERROR: Resources missing in target ($MISSING_COUNT). Deployment incomplete."
  exit 1
fi

echo "✓ Validation passed: $MISMATCH_COUNT mismatches, $MISSING_COUNT missing resources"
exit 0
```

### Azure DevOps Pipeline Integration

```yaml
# azure-pipelines.yml

stages:
  - stage: Deploy
    jobs:
      - job: DeployInfrastructure
        steps:
          - task: AzureCLI@2
            displayName: 'Deploy Resources'
            inputs:
              azureSubscription: '$(AzureSubscription)'
              scriptType: 'bash'
              scriptLocation: 'inlineScript'
              inlineScript: |
                terraform apply -auto-approve

  - stage: Validate
    dependsOn: Deploy
    jobs:
      - job: ValidateDeployment
        steps:
          - task: Bash@3
            displayName: 'Resource-Level Validation'
            inputs:
              targetType: 'filePath'
              filePath: './scripts/validate-deployment.sh'

          - task: PublishBuildArtifacts@1
            displayName: 'Publish Validation Report'
            inputs:
              pathToPublish: 'validation-*.json'
              artifactName: 'fidelity-reports'
```

## Next Steps

- Review [User Guide](../howto/RESOURCE_LEVEL_FIDELITY_VALIDATION.md) for command syntax
- Read [Integration Guide](../concepts/FIDELITY_VALIDATION_INTEGRATION.md) for workflow patterns
- Check [Security Guide](../reference/RESOURCE_LEVEL_VALIDATION_SECURITY.md) for handling sensitive data

---

**Last Updated**: 2026-02-05
**Status**: current
**Category**: examples
