# Validate-Deployment Command Documentation

## Overview

The `atg validate-deployment` command compares Neo4j graphs from source and target tenants to validate deployment fidelity. It generates detailed reports showing resource counts, missing/extra resources, and overall similarity scores.

## Command Syntax

```bash
atg validate-deployment [OPTIONS]
```

## Required Options

- `--source-tenant-id TEXT`: Source tenant ID to compare from
- `--target-tenant-id TEXT`: Target tenant ID to compare to

## Optional Options

- `--source-filter TEXT`: Filter for source resources (e.g., `resourceGroup=RG1`)
- `--target-filter TEXT`: Filter for target resources (e.g., `resourceGroup=RG2`)
- `--output PATH`: Output file path for the validation report (default: stdout)
- `--format [markdown|json]`: Report output format (default: `markdown`)
- `--verbose`: Enable verbose logging

## Features

### Graph Comparison

Compares two Neo4j graphs and calculates:
- Total resource counts
- Resource counts by type
- Missing resources (in source but not target)
- Extra resources (in target but not source)
- Similarity score (percentage match)

### Similarity Scoring

The similarity score is calculated as:

```
similarity = (min(source_count, target_count) / max(source_count, target_count)) * 100
```

- **100%**: Perfect match
- **95-99%**: Mostly complete
- **80-94%**: Incomplete
- **<80%**: Failed

### Report Formats

#### Markdown Report

Human-readable format with tables and recommendations:

```markdown
# Deployment Validation Report

## Summary
- **Source Tenant**: 3cd87a41-1f61-4aef-a212-cefdecd9a2d1
- **Target Tenant**: 506f82b2-e2e7-40a2-b0be-ea6f8cb908f8
- **Similarity Score**: 98.5%
- **Status**: ✅ Mostly Complete

## Resource Comparison
| Resource Type | Source | Target | Match |
|---------------|--------|--------|-------|
| Microsoft.Compute/virtualMachines | 10 | 10 | ✅ |
| Microsoft.Network/virtualNetworks | 5 | 4 | ⚠️ |
...
```

#### JSON Report

Machine-readable format for automation:

```json
{
  "summary": {
    "source_tenant_id": "...",
    "target_tenant_id": "...",
    "source_resource_count": 90,
    "target_resource_count": 89,
    "similarity_score": 98.5,
    "status": "mostly_complete"
  },
  "resource_type_counts": {
    "Microsoft.Compute/virtualMachines": {
      "source": 10,
      "target": 10
    }
  },
  "missing_resources": [...],
  "extra_resources": [...]
}
```

### Filtering

Apply filters to compare specific subsets of resources:

```bash
# Compare specific resource groups
atg validate-deployment \
  --source-tenant-id <SOURCE> \
  --target-tenant-id <TARGET> \
  --source-filter "resourceGroup=SimuLand" \
  --target-filter "resourceGroup=SimuLand-Replica"
```

Filter syntax supports multiple predicates (see SubsetFilter documentation).

## Examples

### Basic Validation

```bash
atg validate-deployment \
  --source-tenant-id 3cd87a41-1f61-4aef-a212-cefdecd9a2d1 \
  --target-tenant-id 506f82b2-e2e7-40a2-b0be-ea6f8cb908f8
```

### Validation with Filtering

```bash
atg validate-deployment \
  --source-tenant-id <SOURCE> \
  --target-tenant-id <TARGET> \
  --source-filter "resourceGroup=SimuLand" \
  --target-filter "resourceGroup=SimuLand-Replica"
```

### Save Report to File

```bash
atg validate-deployment \
  --source-tenant-id <SOURCE> \
  --target-tenant-id <TARGET> \
  --output validation-report.md
```

### JSON Output for Automation

```bash
atg validate-deployment \
  --source-tenant-id <SOURCE> \
  --target-tenant-id <TARGET> \
  --format json \
  --output validation.json
```

### Verbose Logging

```bash
atg validate-deployment \
  --source-tenant-id <SOURCE> \
  --target-tenant-id <TARGET> \
  --verbose
```

## Validation Workflow

1. **Query Source Graph**: Retrieves all resources from source tenant
2. **Query Target Graph**: Retrieves all resources from target tenant
3. **Apply Filters**: Applies source and target filters (if specified)
4. **Compare Resources**: Matches resources by ID and type
5. **Calculate Metrics**: Computes counts, similarity score, and status
6. **Generate Report**: Creates markdown or JSON report

## Validation Status

The validation status is determined by the similarity score:

| Status | Similarity Score | Description |
|--------|-----------------|-------------|
| ✅ **Complete** | 100% | All source resources exist in target |
| ✅ **Mostly Complete** | 95-99% | Minor discrepancies, mostly successful |
| ⚠️ **Incomplete** | 80-94% | Significant resources missing |
| ❌ **Failed** | <80% | Deployment likely failed or incomplete |

## Recommendations

The report includes actionable recommendations based on the validation status:

### Complete (100%)
- Deployment successfully replicated all resources
- No action required

### Mostly Complete (95-99%)
- Review missing resources for intentional exclusions
- Consider redeploying if critical resources are missing
- Check if extra resources are expected (e.g., auto-created dependencies)

### Incomplete (80-94%)
- Investigate missing resources
- Check deployment logs for errors
- Verify source and target filters are correct
- Consider redeploying

### Failed (<80%)
- Review deployment logs for critical errors
- Verify Azure permissions in target tenant
- Check quotas and limits in target subscription
- Consider manual remediation

## Prerequisites

### Neo4j Database

Both tenants must be scanned and stored in Neo4j:

```bash
# Scan source tenant
atg scan --tenant-id <SOURCE_TENANT_ID>

# Scan target tenant (after deployment)
atg scan --tenant-id <TARGET_TENANT_ID>
```

### Neo4j Connection

Ensure Neo4j is running and accessible:

```bash
atg doctor
```

## Return Value

The command returns a comparison result object:

```python
ComparisonResult(
    source_resource_count=90,
    target_resource_count=89,
    resource_type_counts={...},
    missing_resources=[...],
    extra_resources=[...],
    similarity_score=98.5
)
```

## Error Handling

Common errors and solutions:

### "Neo4j connection failed"

Ensure Neo4j is running:

```bash
atg doctor
docker ps | grep neo4j
```

### "No resources found for tenant"

Scan the tenant first:

```bash
atg scan --tenant-id <TENANT_ID>
```

### "Invalid filter format"

Check filter syntax (see SubsetFilter documentation):

```bash
# Correct
--source-filter "resourceGroup=RG1"

# Incorrect
--source-filter "resourceGroup:RG1"
```

## Related Commands

- `atg deploy`: Deploy IaC to target tenant
- `atg generate-iac`: Generate IaC from graph data
- `atg scan`: Scan tenant into Neo4j graph

## Demo Script

See `demos/cross_tenant_cli/03_validate.sh` for a complete example demonstrating validation after deployment.

## Testing

The validation command has comprehensive test coverage (100% on new code):

```bash
uv run pytest tests/validation/ -v
```

## Use Cases

### Disaster Recovery Validation

Verify backup tenant matches production:

```bash
atg validate-deployment \
  --source-tenant-id <PROD_TENANT> \
  --target-tenant-id <DR_TENANT>
```

### Environment Cloning Verification

Ensure staging matches production:

```bash
atg validate-deployment \
  --source-tenant-id <PROD_TENANT> \
  --target-tenant-id <STAGING_TENANT> \
  --source-filter "resourceGroup=Production" \
  --target-filter "resourceGroup=Staging"
```

### Compliance Auditing

Generate compliance reports showing configuration drift:

```bash
atg validate-deployment \
  --source-tenant-id <BASELINE_TENANT> \
  --target-tenant-id <AUDIT_TENANT> \
  --format json \
  --output compliance-report.json
```

## Issue Reference

Implemented in Issue #279: Add Validation Command
PR: #283
