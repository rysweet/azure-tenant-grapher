# Deployment Validation Module

This module provides functionality to validate deployments by comparing Neo4j graphs between source and target tenants.

## Overview

The validation module enables users to:

- Compare resource counts between source and target deployments
- Identify missing and extra resources
- Calculate overall deployment similarity scores
- Generate detailed validation reports in markdown or JSON format

## Components

### Core Modules

1. **comparator.py** - Graph comparison engine
   - `compare_graphs()` - Compare two resource lists
   - `compare_filtered_graphs()` - Compare with optional filtering
   - `ComparisonResult` - Dataclass for comparison results

2. **report.py** - Report generation
   - `generate_markdown_report()` - Create markdown validation reports
   - `generate_json_report()` - Create JSON validation reports

### CLI Command

The `validate-deployment` command provides a user-friendly interface:

```bash
# Basic validation
atg validate-deployment \
  --source-tenant-id <SOURCE_ID> \
  --target-tenant-id <TARGET_ID>

# With filtering
atg validate-deployment \
  --source-tenant-id <SOURCE_ID> \
  --target-tenant-id <TARGET_ID> \
  --source-filter resourceGroup=Production \
  --target-filter resourceGroup=Staging

# Save to file
atg validate-deployment \
  --source-tenant-id <SOURCE_ID> \
  --target-tenant-id <TARGET_ID> \
  --output validation-report.md

# JSON output
atg validate-deployment \
  --source-tenant-id <SOURCE_ID> \
  --target-tenant-id <TARGET_ID> \
  --format json \
  --output validation.json
```

## Comparison Algorithm

The comparison engine uses a count-based similarity algorithm:

1. **Resource Type Aggregation**: Groups resources by type
2. **Count Comparison**: Compares counts for each resource type
3. **Similarity Score**: Calculates overall similarity percentage
4. **Gap Analysis**: Identifies missing and extra resources

### Similarity Score Calculation

```
similarity = (min(source_count, target_count) / max(source_count, target_count)) * 100
```

### Validation Status Levels

- **COMPLETE** (95-100%): Deployment matches source
- **MOSTLY COMPLETE** (80-95%): Minor discrepancies
- **INCOMPLETE** (50-80%): Significant differences
- **FAILED** (<50%): Major differences

## Report Format

### Markdown Report

The markdown report includes:

- Executive summary with similarity score
- Resource count comparison table
- Missing resources list
- Extra resources list
- Validation status assessment
- Actionable recommendations

Example output:

```markdown
# Deployment Validation Report

## Summary

- **Overall Similarity**: 90.0%
- **Source Resources**: 100
- **Target Resources**: 90
- **Missing Resources**: 10
- **Extra Resources**: 0

## Resource Count Comparison

| Resource Type | Source | Target | Match |
|---------------|--------|--------|-------|
| Microsoft.Compute/virtualMachines | 50 | 45 | DIFF |
| Microsoft.Network/virtualNetworks | 50 | 45 | DIFF |

## Missing Resources

- Microsoft.Compute/virtualMachines (5 missing)
- Microsoft.Network/virtualNetworks (5 missing)

## Validation Status

**MOSTLY COMPLETE**: Deployment is mostly complete with minor discrepancies.

## Recommendations

1. **Investigate Missing Resources**: Review the missing resources list
2. **Re-run Deployment**: Consider re-running if discrepancies are unintentional
```

### JSON Report

The JSON report provides machine-readable output:

```json
{
  "timestamp": "2025-10-09T13:15:55.123456",
  "summary": {
    "similarity_score": 90.0,
    "source_resource_count": 100,
    "target_resource_count": 90,
    "missing_count": 10,
    "extra_count": 0
  },
  "resource_type_counts": {
    "Microsoft.Compute/virtualMachines": {"source": 50, "target": 45}
  },
  "missing_resources": ["Microsoft.Compute/virtualMachines (5 missing)"],
  "extra_resources": [],
  "validation_status": "mostly_complete"
}
```

## Usage Examples

### Python API

```python
from src.validation import compare_graphs, generate_markdown_report

# Compare resources
source_resources = [...]  # From Neo4j query
target_resources = [...]  # From Neo4j query

result = compare_graphs(source_resources, target_resources)

# Generate report
report = generate_markdown_report(result, "source-tenant", "target-tenant")
print(report)
```

### With Filtering

```python
from src.validation import compare_filtered_graphs

result = compare_filtered_graphs(
    source_resources,
    target_resources,
    source_filter="resourceGroup=Production",
    target_filter="resourceGroup=Staging"
)
```

## Testing

Comprehensive test suite included:

```bash
# Run validation tests
uv run pytest tests/validation/ -v

# Run with coverage
uv run pytest tests/validation/ --cov=src/validation --cov-report=term-missing
```

Test coverage:
- **test_comparator.py**: Graph comparison logic
- **test_report.py**: Report generation

## Demo Script

A complete demo script is available:

```bash
./demos/cross_tenant_cli/03_validate.sh
```

## Integration

### CI/CD Pipeline

```yaml
# Example GitHub Actions workflow
- name: Validate Deployment
  run: |
    uv run atg validate-deployment \
      --source-tenant-id ${{ secrets.SOURCE_TENANT }} \
      --target-tenant-id ${{ secrets.TARGET_TENANT }} \
      --format json \
      --output validation.json

    # Parse similarity score
    SCORE=$(jq '.summary.similarity_score' validation.json)
    if (( $(echo "$SCORE < 95" | bc -l) )); then
      echo "Deployment validation failed: $SCORE%"
      exit 1
    fi
```

## Future Enhancements

Potential improvements for future versions:

1. **Topology Comparison**: Deep comparison of resource relationships
2. **Configuration Drift**: Detect changes in resource properties
3. **Historical Tracking**: Track validation results over time
4. **Custom Rules**: User-defined validation criteria
5. **Notification Integration**: Slack/Teams/Email alerts
6. **Diff Visualization**: Interactive visual comparison

## Related Commands

- `atg scan` - Discover and graph Azure resources
- `atg generate-iac` - Generate IaC from graph
- `atg create-tenant` - Deploy resources to target tenant
- `atg list-deployments` - List tracked deployments
- `atg undeploy` - Remove deployed resources

## Support

For issues or questions:
- Review tests: `tests/validation/`
- Check examples: `demos/cross_tenant_cli/`
- File issue: GitHub Issues
