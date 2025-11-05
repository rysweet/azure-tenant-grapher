# Resource Coverage Analysis Script

This script analyzes the gap between scanned Azure resources and generated Terraform resources to help identify missing coverage and prioritize emitter implementations.

## Purpose

Investigates **Gap #1: Missing 380 Resources (Issue #414)** by:

1. Querying all resource types from Neo4j
2. Comparing against Terraform emitter mappings
3. Categorizing resources into:
   - **Supported**: Have Terraform emitters
   - **Non-Deployable**: Graph API objects (users, groups, service principals)
   - **Unsupported**: No Terraform provider support
   - **Missing Emitters**: Could be added but haven't yet

## Usage

### Basic Usage

```bash
# Run with default settings (markdown output to outputs/)
uv run python scripts/analyze_resource_coverage.py

# Or with activated venv
source .venv/bin/activate
python scripts/analyze_resource_coverage.py
```

### Advanced Options

```bash
# Generate both markdown and JSON reports
python scripts/analyze_resource_coverage.py --format both

# Change output directory
python scripts/analyze_resource_coverage.py --output-dir /path/to/output

# Enable debug logging
python scripts/analyze_resource_coverage.py --debug

# Full example with all options
python scripts/analyze_resource_coverage.py \
  --output-dir ./reports \
  --format both \
  --debug
```

## Output

The script generates comprehensive reports:

### Markdown Report (`resource_coverage_analysis.md`)

- Executive summary with key statistics
- Detailed breakdown by category:
  - Supported resources (with Terraform type mapping)
  - Non-deployable resources (Graph API objects)
  - Unsupported resources (no Terraform provider)
  - Missing emitters (prioritized by count)
- Recommendations for next steps

### JSON Report (`resource_coverage_analysis.json`)

- Machine-readable format with all data
- Resource counts by type
- Statistics and percentages
- Full categorization lists
- Top missing emitters

## Key Findings

From the analysis of the current tenant:

- **Total Resources Scanned**: 2,157
- **Expected in Terraform**: 1,783 (82.7%)
- **Actual Gap**: 374 resources (17.3%)

### Gap Breakdown

| Category | Count | Percentage | Description |
|----------|-------|------------|-------------|
| Supported | 1,783 | 82.7% | Resources with emitters |
| Non-Deployable | 0 | 0.0% | Graph API objects |
| Unsupported | 7 | 0.3% | No Terraform provider |
| Missing Emitters | 367 | 17.0% | Could add but haven't |

### The 380 Resource Mystery Solved

The reported gap of 380 resources (2,157 scanned → 1,777 in Terraform) breaks down as:

1. **374 resources** have no emitters:
   - 367 missing emitter implementations (could be added)
   - 7 unsupported by Terraform provider

2. **6 resources** (~1,783 expected - 1,777 actual) are likely:
   - Filtered during emission (e.g., NICs without IP configs)
   - Failed validation checks
   - Excluded due to dependency issues

### High-Priority Missing Emitters

These resource types have the most instances and should be prioritized:

| Resource Type | Count | Priority |
|---------------|-------|----------|
| Microsoft.App/containerApps | 35 | HIGH |
| Microsoft.Compute/virtualMachineScaleSets | 33 | HIGH |
| Microsoft.Network/loadBalancers | 31 | HIGH |
| Microsoft.ContainerService/managedClusters | 29 | HIGH |
| Microsoft.ContainerRegistry/registries | 26 | HIGH |
| Microsoft.Compute/virtualMachines/runCommands | 22 | HIGH |
| Microsoft.Compute/snapshots | 17 | HIGH |
| Microsoft.Insights/metricalerts | 14 | HIGH |
| Microsoft.Cache/Redis | 14 | HIGH |
| Microsoft.Network/applicationGateways | 14 | HIGH |

## Requirements

- Neo4j database must be running
- Environment variables configured:
  - `NEO4J_URI` or `NEO4J_PORT`
  - `NEO4J_USER` (default: neo4j)
  - `NEO4J_PASSWORD`

## Implementation Details

### Data Sources

1. **Neo4j Query**:
   ```cypher
   MATCH (r:Resource)
   RETURN r.type as resource_type, count(*) as count
   ORDER BY count DESC
   ```

2. **Terraform Mapping**: `AZURE_TO_TERRAFORM_MAPPING` from `src/iac/emitters/terraform_emitter.py`

### Categorization Logic

- **Supported**: Type exists in Terraform mapping dictionary
- **Non-Deployable**: Graph API objects (User, Group, ServicePrincipal, etc.)
- **Unsupported**: Known types without Terraform provider support
- **Missing Emitters**: Everything else (potential additions)

### Special Cases

- **Microsoft.Web/sites**: Dynamically mapped based on app type
- **Case-insensitive matching**: Handles lowercase variants (e.g., `microsoft.insights` vs `Microsoft.Insights`)
- **Neo4j label types**: Maps simple labels like "User" to full types

## Next Steps

1. **Investigate the 6-resource discrepancy**:
   - Review terraform_emitter.py filtering logic
   - Check logs for skipped resources
   - Validate resource dependencies

2. **Add high-priority emitters**:
   - Start with types that have >10 instances
   - Focus on networking and compute resources
   - Consider business value and deployment frequency

3. **Continuous monitoring**:
   - Run after each scan to track coverage
   - Update as new emitters are added
   - Monitor for new Azure resource types

## Troubleshooting

### Neo4j Connection Errors

```bash
# Check if Neo4j is running
docker ps | grep neo4j

# Verify environment variables
echo $NEO4J_PORT
echo $NEO4J_PASSWORD

# Start Neo4j if needed
uv run atg doctor
```

### No Resources Found

Ensure you've run a scan first:

```bash
uv run atg scan --tenant-id <TENANT_ID>
```

### Output Directory Errors

The script creates the output directory if it doesn't exist. If you get permission errors:

```bash
# Create directory manually
mkdir -p outputs

# Or use a different directory
python scripts/analyze_resource_coverage.py --output-dir ~/reports
```

## Related Files

- `/src/iac/emitters/terraform_emitter.py` - Terraform emitter with AZURE_TO_TERRAFORM_MAPPING
- `/src/utils/session_manager.py` - Neo4j session management
- `/src/config_manager.py` - Configuration and environment variables

## See Also

- Issue #414: Resource Coverage Investigation
- Issue #333: Subnet Validation
- Issue #406: Cross-Tenant Translation
