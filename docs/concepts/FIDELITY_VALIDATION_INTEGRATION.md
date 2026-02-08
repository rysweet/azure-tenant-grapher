# Fidelity Validation Integration Guide

Understand how resource-level validation fits into Azure Tenant Grapher workflows and when to use tenant-level versus resource-level validation.

## Validation Hierarchy

Azure Tenant Grapher provides two complementary validation approaches:

### Tenant-Level Validation (Aggregate View)

**Purpose**: High-level overview of replication quality across entire tenant

**Best for**:
- Initial post-deployment assessment
- Executive dashboards and reporting
- Tracking replication trends over time
- Identifying which resource types need attention

**Command**:
```bash
azure-tenant-grapher fidelity
```

**Output**:
```
Tenant Fidelity Report
======================

Resource Type Distribution:
  - Storage Accounts: 45 resources (98% match)
  - Virtual Machines: 32 resources (94% match)
  - Virtual Networks: 12 resources (100% match)

Overall Fidelity: 96%
Total Resources: 234
```

### Resource-Level Validation (Detailed View)

**Purpose**: Property-by-property comparison for individual resources

**Best for**:
- Troubleshooting specific mismatches
- Compliance auditing with detailed evidence
- Debugging replication issues
- Configuration drift detection
- Post-fix validation

**Command**:
```bash
azure-tenant-grapher fidelity --resource-level
```

**Output**:
```
Resource: mystorageaccount
  ✗ sku.name: source='Standard_LRS', target='Premium_LRS'
  ✗ properties.accessTier: source='Hot', target='Cool'
  ✓ location: eastus (match)
```

## When to Use Each Approach

### Start with Tenant-Level

Use tenant-level validation when:

1. **Post-deployment overview**: Just finished replication and want high-level status
2. **Regular monitoring**: Weekly/monthly health checks
3. **Executive reporting**: Presenting metrics to stakeholders
4. **Resource type prioritization**: Identifying which resource types have issues

**Example workflow**:
```bash
# Step 1: Get overview
azure-tenant-grapher fidelity

# Output shows: "Storage Accounts: 85% match"
# Decision: Need to investigate storage accounts
```

### Drill Down with Resource-Level

Use resource-level validation when:

1. **Tenant-level shows issues**: Aggregate metrics reveal problems needing investigation
2. **Specific resource types**: Focus on particular Azure service types
3. **Compliance requirements**: Need detailed evidence for audit trails
4. **Debugging**: Troubleshooting persistent replication failures
5. **Change validation**: Verify specific configuration changes

**Example workflow**:
```bash
# Step 2: Investigate storage accounts identified in tenant-level report
azure-tenant-grapher fidelity --resource-level \
  --resource-type "Microsoft.Storage/storageAccounts" \
  --output storage-deep-dive.json
```

## Complete Validation Workflow

### Phase 1: Initial Assessment (Tenant-Level)

```bash
# 1. Run tenant-level validation after replication
azure-tenant-grapher fidelity --output initial-assessment.json

# 2. Review aggregate metrics
jq '.resource_types[] | select(.match_percentage < 95)' initial-assessment.json
```

**Decision point**: If any resource type shows < 95% match, proceed to Phase 2.

### Phase 2: Resource-Type Investigation (Resource-Level)

```bash
# 3. Deep dive into problem resource types
for resource_type in $(jq -r '.resource_types[] | select(.match_percentage < 95) | .resource_type' initial-assessment.json); do
  echo "Investigating $resource_type"
  azure-tenant-grapher fidelity --resource-level \
    --resource-type "$resource_type" \
    --output "investigation-${resource_type//\//-}.json"
done
```

### Phase 3: Root Cause Analysis (Resource-Level Detail)

```bash
# 4. Extract specific property mismatches
jq '.resources[] | select(.status == "MISMATCH") | {
  resource: .resource_name,
  mismatches: [.property_comparisons[] | select(.match == false) | .property_path]
}' investigation-*.json > root-causes.json
```

### Phase 4: Remediation Tracking

```bash
# 5. After fixes, validate specific resources
azure-tenant-grapher fidelity --resource-level \
  --resource-type "Microsoft.Storage/storageAccounts" \
  --track \
  --output post-remediation.json

# 6. Compare before/after
azure-tenant-grapher report fidelity-diff \
  --baseline investigation-Microsoft.Storage-storageAccounts.json \
  --current post-remediation.json
```

### Phase 5: Final Validation (Tenant-Level)

```bash
# 7. Confirm overall improvement
azure-tenant-grapher fidelity --output final-validation.json

# 8. Compare to initial assessment
azure-tenant-grapher report fidelity-diff \
  --baseline initial-assessment.json \
  --current final-validation.json
```

## Integration with Other ATG Commands

### Post-Scan Validation

After scanning source and target tenants:

```bash
# 1. Scan source subscription
azure-tenant-grapher scan --tenant-id <source-tenant> \
  --subscription <source-sub>

# 2. Scan target subscription
azure-tenant-grapher scan --tenant-id <target-tenant> \
  --subscription <target-sub>

# 3. Run validation
azure-tenant-grapher fidelity --resource-level
```

### Post-Deployment Validation

After deploying IaC generated by ATG:

```bash
# 1. Generate IaC from source
azure-tenant-grapher generate-iac --format terraform \
  --output-dir ./iac-output

# 2. Deploy to target (external to ATG)
cd iac-output && terraform apply

# 3. Validate deployment
azure-tenant-grapher fidelity --resource-level \
  --track \
  --output deployment-validation.json
```

### Autonomous Deployment Integration

> **Note**: Autonomous deployment with integrated validation (`agent deploy --validate`) requires ATG v2.0+ or a separate feature branch. Check your version before using these commands.

When using ATG's autonomous deployment (v2.0+):

```bash
# Deployment automatically runs validation
azure-tenant-grapher agent deploy \
  --source-subscription <source-sub> \
  --target-subscription <target-sub> \
  --validate

# Validation results included in deployment report
```

**Current workaround (pre-v2.0) - Manual validation after deployment:**

```bash
# 1. Deploy using standard workflow
azure-tenant-grapher generate-iac --format terraform \
  --output-dir ./iac-output

cd iac-output && terraform apply

# 2. Manually run validation after deployment
cd .. && azure-tenant-grapher fidelity --resource-level \
  --track \
  --output deployment-validation.json
```

## Workflow Patterns

### Pattern 1: Continuous Validation

For environments with frequent changes:

```bash
# Nightly validation script
#!/bin/bash
DATE=$(date +%Y%m%d)

# Tenant-level overview
azure-tenant-grapher fidelity \
  --track \
  --output "daily-validation-${DATE}.json"

# Check if action needed (< 95% match)
MATCH_PCT=$(jq '.summary.match_percentage' "daily-validation-${DATE}.json")

if (( $(echo "$MATCH_PCT < 95" | bc -l) )); then
  echo "WARNING: Match percentage below threshold: ${MATCH_PCT}%"

  # Run detailed validation
  azure-tenant-grapher fidelity --resource-level \
    --output "detailed-validation-${DATE}.json"

  # Send alert
  ./send-alert.sh "Fidelity validation failed" "detailed-validation-${DATE}.json"
fi
```

### Pattern 2: Pre-Production Validation

Before promoting replicated environment to production:

```bash
# Comprehensive validation checklist
#!/bin/bash

echo "Running pre-production validation..."

# 1. Tenant-level validation
azure-tenant-grapher fidelity --output preprod-tenant-level.json
TENANT_MATCH=$(jq '.summary.match_percentage' preprod-tenant-level.json)

# 2. Critical resource types
for type in "Microsoft.Compute/virtualMachines" \
            "Microsoft.Network/virtualNetworks" \
            "Microsoft.Storage/storageAccounts" \
            "Microsoft.Sql/servers"; do

  azure-tenant-grapher fidelity --resource-level \
    --resource-type "$type" \
    --output "preprod-${type//\//-}.json"
done

# 3. Generate approval report
jq -s '{
  tenant_match_percentage: .[0].summary.match_percentage,
  critical_resources: [.[1:] | .[] | {
    resource_type: .metadata.resource_type_filter,
    match_count: .summary.exact_match,
    mismatch_count: .summary.mismatches
  }],
  approval_status: (if .[0].summary.match_percentage >= 98 then "APPROVED" else "REVIEW_REQUIRED" end)
}' preprod-*.json > preprod-approval-report.json

echo "Validation complete. Review preprod-approval-report.json"
```

### Pattern 3: Compliance Audit Trail

Monthly compliance validation with detailed evidence:

```bash
# Monthly compliance audit
#!/bin/bash

AUDIT_DATE=$(date +%Y-%m)
AUDIT_DIR="compliance-audits/${AUDIT_DATE}"

mkdir -p "$AUDIT_DIR"

# 1. Full tenant-level baseline
azure-tenant-grapher fidelity \
  --track \
  --output "${AUDIT_DIR}/tenant-baseline.json"

# 2. Detailed resource-level for audit evidence
azure-tenant-grapher fidelity --resource-level \
  --track \
  --output "${AUDIT_DIR}/resource-level-evidence.json"

# 3. Historical comparison (month-over-month)
LAST_MONTH=$(date -d "1 month ago" +%Y-%m)
if [ -f "compliance-audits/${LAST_MONTH}/tenant-baseline.json" ]; then
  azure-tenant-grapher report fidelity-diff \
    --baseline "compliance-audits/${LAST_MONTH}/tenant-baseline.json" \
    --current "${AUDIT_DIR}/tenant-baseline.json" \
    --output "${AUDIT_DIR}/drift-report.json"
fi

# 4. Package for compliance team
tar czf "${AUDIT_DIR}.tar.gz" "$AUDIT_DIR"
echo "Compliance audit package: ${AUDIT_DIR}.tar.gz"
```

## Best Practices

### 1. Always Start Broad, Then Narrow

```bash
# Good: Start with overview
azure-tenant-grapher fidelity
# Then drill down to specific issues
azure-tenant-grapher fidelity --resource-level --resource-type "..."

# Bad: Immediately jumping to resource-level without context
azure-tenant-grapher fidelity --resource-level  # Too much data, no context
```

### 2. Use Tracking for Trend Analysis

```bash
# Always enable tracking for important validations
azure-tenant-grapher fidelity --resource-level \
  --track  # ← Enables historical comparison
  --output validation.json
```

### 3. Filter Strategically

```bash
# Good: Targeted filtering based on investigation
azure-tenant-grapher fidelity --resource-level \
  --resource-type "Microsoft.Storage/storageAccounts"  # Specific issue

# Bad: No filtering on large environments
azure-tenant-grapher fidelity --resource-level  # May timeout or take too long
```

### 4. Combine with Visualization

```bash
# After validation, visualize problem areas
azure-tenant-grapher visualize \
  --filter-resource-types "Microsoft.Storage/storageAccounts"
```

> **Note**: Automatic mismatch highlighting in the visualizer (`--highlight-mismatches`) is planned for a future release. Currently, use filtering to focus on specific resource types that showed mismatches in validation reports.

**Current workaround - Filter by resource type:**

```bash
# 1. Identify problem resource types from validation report
jq '.summary.top_mismatched_properties[] | .property' validation.json

# 2. Visualize those specific resource types
azure-tenant-grapher visualize \
  --filter-resource-types "Microsoft.Storage/storageAccounts"

# 3. Manually inspect resources in visualization
```

**Planned for future release:**

```bash
# Automatic mismatch highlighting (COMING SOON)
azure-tenant-grapher visualize \
  --highlight-mismatches \
  --filter-resource-types "Microsoft.Storage/storageAccounts"
```

### 5. Automate Remediation Tracking

```bash
# Before fix
azure-tenant-grapher fidelity --resource-level \
  --resource-type "Microsoft.Storage/storageAccounts" \
  --output before-fix.json

# Apply fixes
./apply-storage-fixes.sh

# After fix
azure-tenant-grapher fidelity --resource-level \
  --resource-type "Microsoft.Storage/storageAccounts" \
  --output after-fix.json

# Compare
azure-tenant-grapher report fidelity-diff \
  --baseline before-fix.json \
  --current after-fix.json
```

## Common Anti-Patterns

### Anti-Pattern 1: Running Resource-Level on Everything

**Problem**: Resource-level validation on 1000+ resources without filtering takes too long and produces overwhelming output.

**Solution**: Use tenant-level first, then filter resource-level to problem areas:

```bash
# Bad
azure-tenant-grapher fidelity --resource-level  # 1000+ resources, 30+ minutes

# Good
azure-tenant-grapher fidelity  # 30 seconds
# Then target specific resource types identified
azure-tenant-grapher fidelity --resource-level \
  --resource-type "Microsoft.Storage/storageAccounts"  # 2 minutes
```

### Anti-Pattern 2: Ignoring Security Redaction

**Problem**: Using `--redaction-level NONE` in production exports sensitive credentials.

**Solution**: Always use appropriate redaction:

```bash
# Bad
azure-tenant-grapher fidelity --resource-level \
  --redaction-level NONE \
  --output production-validation.json  # Exposes secrets!

# Good
azure-tenant-grapher fidelity --resource-level \
  --redaction-level FULL \  # Default, safe for sharing
  --output production-validation.json
```

### Anti-Pattern 3: Not Tracking Validations

**Problem**: Running one-off validations without tracking prevents historical analysis.

**Solution**: Always use `--track` for important validations:

```bash
# Bad
azure-tenant-grapher fidelity --resource-level  # No history

# Good
azure-tenant-grapher fidelity --resource-level \
  --track  # Enables historical comparison and drift detection
```

## Next Steps

- Review [User Guide](../howto/RESOURCE_LEVEL_FIDELITY_VALIDATION.md) for command details
- See [Examples](../examples/RESOURCE_LEVEL_VALIDATION_EXAMPLES.md) for real-world scenarios
- Read [Security Guide](../reference/RESOURCE_LEVEL_VALIDATION_SECURITY.md) for handling sensitive data

---

**Last Updated**: 2026-02-05
**Status**: current
**Category**: concepts
