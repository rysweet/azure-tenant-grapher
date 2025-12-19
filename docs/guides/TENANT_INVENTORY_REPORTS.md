# Tenant Inventory Reports Guide

Generate comprehensive Azure tenant inventory reports with the `atg report` command. This guide shows you how to create detailed Markdown reports of your Azure environment for documentation, compliance, or security analysis.

## Overview

The `atg report` command generates rich, human-readable Markdown reports containing:

- **Tenant Overview** - High-level statistics and metadata
- **Identity Summary** - Users, service principals, managed identities, and groups
- **Resource Inventory** - All resources organized by type and region
- **Role Assignments** - RBAC permissions and access patterns
- **Cost Data** - Resource costs when available (requires Azure Cost Management API access)

Reports pull data from your Neo4j graph by default (fast, cached) or can query Azure APIs directly with the `--live` flag (slower, always current).

## Quick Start

```bash
# Generate report from Neo4j graph (requires prior scan)
atg report --tenant-id 3cd87a41-1f61-4aef-a212-cefdecd9a2d1

# Generate report with live Azure data (no scan required)
atg report --tenant-id 3cd87a41-1f61-4aef-a212-cefdecd9a2d1 --live

# Save report to specific file
atg report --tenant-id 3cd87a41-1f61-4aef-a212-cefdecd9a2d1 --output ./reports/tenant-inventory.md

# Include cost data (requires Cost Management permissions)
atg report --tenant-id 3cd87a41-1f61-4aef-a212-cefdecd9a2d1 --include-costs
```

## Report Contents

### Tenant Overview Section

```markdown
# Azure Tenant Inventory Report

**Tenant ID:** 3cd87a41-1f61-4aef-a212-cefdecd9a2d1
**Generated:** 2024-12-03 15:30:45 UTC
**Data Source:** Neo4j Graph Database

## Summary Statistics

- **Total Resources:** 2,248
- **Resource Types:** 93
- **Regions:** 16
- **Subscriptions:** 3
- **Resource Groups:** 45
```

### Identity Summary Section

```markdown
## Identity Overview

### Users
- **Total Users:** 214
- **Active Users:** 198
- **Guest Users:** 16

### Service Principals
- **Total Service Principals:** 1,470
- **Application Service Principals:** 1,245
- **Managed Identities:** 113
  - System-Assigned: 67
  - User-Assigned: 46

### Groups
- **Total Groups:** 84
- **Security Groups:** 72
- **Microsoft 365 Groups:** 12
```

### Resource Inventory Section

Resources are organized by type with counts and regional distribution:

```markdown
## Resource Inventory

### Top Resource Types

| Resource Type | Count | Primary Regions |
|--------------|-------|----------------|
| Microsoft.Network/networkInterfaces | 342 | East US (145), West US 2 (103) |
| Microsoft.Compute/disks | 287 | East US (125), West US 2 (89) |
| Microsoft.Storage/storageAccounts | 156 | East US (67), West Europe (45) |
| Microsoft.Compute/virtualMachines | 134 | East US (58), West US 2 (42) |
| Microsoft.Network/virtualNetworks | 89 | East US (34), West US 2 (28) |

### Resources by Region

| Region | Resource Count | Top Types |
|--------|---------------|-----------|
| East US | 678 | VMs (58), NICs (145), Disks (125) |
| West US 2 | 542 | VMs (42), NICs (103), Disks (89) |
| West Europe | 387 | Storage (45), NICs (34), Disks (56) |
```

### Role Assignments Section

```markdown
## Role Assignments

**Total Role Assignments:** 1,042

### Top Roles Assigned

| Role | Assignment Count | Scope Distribution |
|------|-----------------|-------------------|
| Reader | 342 | Subscription (156), Resource Group (186) |
| Contributor | 287 | Subscription (89), Resource Group (198) |
| Owner | 156 | Subscription (45), Resource Group (111) |
| Storage Blob Data Reader | 134 | Resource (134) |

### Top Principals by Assignment Count

| Principal | Type | Assignment Count | Primary Roles |
|-----------|------|-----------------|--------------|
| DevOps Service Principal | Service Principal | 67 | Contributor, Reader |
| Admin Group | Security Group | 54 | Owner, Contributor |
| Monitoring Identity | Managed Identity | 42 | Monitoring Reader |
```

### Cost Data Section

When `--include-costs` is specified and Cost Management API access is available:

```markdown
## Cost Analysis

**Note:** Cost data represents the last 30 days of Azure spending.

### Cost by Resource Type

| Resource Type | Monthly Cost (USD) | Resource Count | Avg Cost per Resource |
|--------------|-------------------|----------------|---------------------|
| Microsoft.Compute/virtualMachines | $12,456.78 | 134 | $92.96 |
| Microsoft.Storage/storageAccounts | $3,234.56 | 156 | $20.73 |
| Microsoft.Network/applicationGateways | $2,890.12 | 12 | $240.84 |

**Total Monthly Cost:** $24,567.89
```

If cost data is unavailable, the section shows:

```markdown
## Cost Analysis

**Cost data unavailable.** This may be because:
- Cost Management API permissions are not configured
- Cost data has not yet been processed by Azure (can take 24-48 hours)
- The `--include-costs` flag was not specified

To enable cost reporting, ensure your service principal has `Cost Management Reader` role.
```

## Common Scenarios

### Scenario 1: Quick Documentation Report

Generate a snapshot of your tenant for documentation purposes:

```bash
# Use cached Neo4j data (fast, requires prior scan)
atg report --tenant-id <TENANT_ID> --output ./docs/azure-inventory.md
```

**When to use:** Documenting your current Azure environment, creating architecture documentation, or sharing tenant structure with team members.

### Scenario 2: Compliance Audit Report

Generate a live report with current Azure state for compliance audits:

```bash
# Use live Azure data (slower, always current)
atg report --tenant-id <TENANT_ID> --live --output ./audit/compliance-report.md
```

**When to use:** Compliance audits, security reviews, or when you need to guarantee the report reflects real-time Azure state.

### Scenario 3: Cost Analysis Report

Generate a report with cost breakdowns for financial analysis:

```bash
# Include cost data from Azure Cost Management API
atg report --tenant-id <TENANT_ID> --include-costs --output ./finance/cost-report.md
```

**When to use:** Budget planning, cost optimization analysis, or financial reporting.

### Scenario 4: Change Detection

Compare reports over time to identify changes:

```bash
# Generate baseline report
atg report --tenant-id <TENANT_ID> --output ./reports/baseline-2024-12-01.md

# Generate current report
atg report --tenant-id <TENANT_ID> --output ./reports/current-2024-12-03.md

# Diff the reports
diff ./reports/baseline-2024-12-01.md ./reports/current-2024-12-03.md
```

**When to use:** Tracking resource changes over time, identifying unauthorized modifications, or monitoring tenant growth.

### Scenario 5: Multi-Tenant Comparison

Generate reports for multiple tenants and compare:

```bash
# Generate reports for each tenant
atg report --tenant-id <TENANT_A_ID> --output ./reports/tenant-a.md
atg report --tenant-id <TENANT_B_ID> --output ./reports/tenant-b.md
atg report --tenant-id <TENANT_C_ID> --output ./reports/tenant-c.md
```

**When to use:** Managing multiple Azure tenants, standardizing configurations across tenants, or comparing dev/staging/prod environments.

## Data Sources: Neo4j vs Live Azure

The `atg report` command supports two data sources:

### Neo4j Graph (Default)

```bash
atg report --tenant-id <TENANT_ID>
```

**Advantages:**
- Fast report generation (seconds)
- No Azure API rate limits
- Works offline (cached data)
- Consistent performance regardless of tenant size

**Disadvantages:**
- Requires prior `atg scan` to populate graph
- Data may be stale (reflects last scan)
- Graph must be running

**When to use:** Regular reporting, documentation, or when speed matters more than real-time accuracy.

### Live Azure APIs

```bash
atg report --tenant-id <TENANT_ID> --live
```

**Advantages:**
- Always current (real-time data)
- No scan required
- Guaranteed accurate

**Disadvantages:**
- Slower (minutes for large tenants)
- Subject to Azure API rate limits
- Requires Azure authentication
- Performance varies with tenant size

**When to use:** Compliance audits, security reviews, or when you need guaranteed current state.

## Output Format

Reports are generated as Markdown (`.md`) files with:

- **Clean formatting** - Easy to read in text editors or rendered on GitHub/Confluence
- **Tables** - Structured data for resource counts, costs, and statistics
- **Hierarchical sections** - Logical organization with collapsible sections
- **Metadata** - Generation timestamp, data source, and tenant information

### Default Output Location

If `--output` is not specified, reports are saved to:

```
./reports/tenant-inventory-<TENANT_ID>-<TIMESTAMP>.md
```

Example: `./reports/tenant-inventory-3cd87a41-1f61-4aef-a212-cefdecd9a2d1-20241203-153045.md`

## Troubleshooting

### Issue: "Neo4j database not found"

**Error:**
```
Error: Neo4j database is not running or no graph exists for tenant <TENANT_ID>
```

**Solution:**
```bash
# Run a scan first to populate the graph
atg scan --tenant-id <TENANT_ID>

# Then generate the report
atg report --tenant-id <TENANT_ID>
```

Or use `--live` to bypass Neo4j:
```bash
atg report --tenant-id <TENANT_ID> --live
```

### Issue: "Authentication failed"

**Error:**
```
Error: Azure authentication failed. Please run 'az login'
```

**Solution:**
```bash
# Authenticate with Azure CLI
az login --tenant <TENANT_ID>

# Verify authentication
az account show

# Generate report
atg report --tenant-id <TENANT_ID>
```

### Issue: "Cost data unavailable"

**Error:**
```
Warning: Cost data could not be retrieved
```

**Causes and Solutions:**

1. **Missing permissions** - Ensure service principal has `Cost Management Reader` role:
   ```bash
   az role assignment create \
     --assignee <SERVICE_PRINCIPAL_ID> \
     --role "Cost Management Reader" \
     --scope /subscriptions/<SUBSCRIPTION_ID>
   ```

2. **Cost data not yet processed** - Azure Cost Management data has 24-48 hour delay. Wait and retry:
   ```bash
   # Check again tomorrow
   atg report --tenant-id <TENANT_ID> --include-costs
   ```

3. **Cost flag not specified** - Cost data is opt-in:
   ```bash
   # Explicitly request cost data
   atg report --tenant-id <TENANT_ID> --include-costs
   ```

### Issue: "Report generation timeout"

**Error:**
```
Error: Report generation timed out after 300 seconds
```

**Solution:**

For very large tenants (>10,000 resources), use Neo4j data source instead of live:

```bash
# Scan first (can take time but runs once)
atg scan --tenant-id <TENANT_ID>

# Generate report from graph (fast)
atg report --tenant-id <TENANT_ID>
```

If using `--live` is required, increase timeout:
```bash
export ATG_REPORT_TIMEOUT=600  # 10 minutes
atg report --tenant-id <TENANT_ID> --live
```

## Advanced Usage

### Custom Report Sections

Use environment variables to customize report sections:

```bash
# Include detailed RBAC breakdown
export ATG_REPORT_DETAILED_RBAC=true

# Include resource tags summary
export ATG_REPORT_INCLUDE_TAGS=true

# Include network topology
export ATG_REPORT_INCLUDE_NETWORK=true

atg report --tenant-id <TENANT_ID>
```

### Filtering Reports

Generate reports for specific subscriptions or resource groups:

```bash
# Report for specific subscriptions only
atg report --tenant-id <TENANT_ID> --subscriptions sub1,sub2

# Report for specific resource groups only
atg report --tenant-id <TENANT_ID> --resource-groups rg1,rg2
```

### Programmatic Access

Use report data programmatically:

```python
from azure_tenant_grapher import ReportGenerator

# Generate report
generator = ReportGenerator(tenant_id="<TENANT_ID>")
report_data = generator.generate(output_format="dict")

# Access structured data
print(f"Total resources: {report_data['summary']['total_resources']}")
print(f"Resource types: {report_data['summary']['resource_types']}")

# Save to custom format
import json
with open("report.json", "w") as f:
    json.dump(report_data, f, indent=2)
```

## Integration with Other Commands

### Report After Scan

Generate reports automatically after scanning:

```bash
# Scan and immediately generate report
atg scan --tenant-id <TENANT_ID> && \
  atg report --tenant-id <TENANT_ID> --output ./reports/post-scan-report.md
```

### Report Before IaC Generation

Use reports to understand your environment before generating IaC:

```bash
# 1. Generate report to understand current state
atg report --tenant-id <TENANT_ID> --output ./planning/current-state.md

# 2. Review report and identify resources to replicate

# 3. Generate IaC for specific resource types
atg generate-iac --format terraform --subset-filter "types=Microsoft.Storage/*"
```

### Report in CI/CD Pipelines

Integrate reports into automated workflows:

```yaml
# .github/workflows/azure-inventory.yml
name: Azure Inventory Report

on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly on Sunday

jobs:
  generate-report:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install ATG
        run: |
          pip install uv
          uv pip install azure-tenant-grapher

      - name: Azure Login
        run: |
          az login --service-principal \
            --username ${{ secrets.AZURE_CLIENT_ID }} \
            --password ${{ secrets.AZURE_CLIENT_SECRET }} \
            --tenant ${{ secrets.AZURE_TENANT_ID }}

      - name: Generate Report
        run: |
          atg report \
            --tenant-id ${{ secrets.AZURE_TENANT_ID }} \
            --live \
            --include-costs \
            --output ./reports/weekly-inventory.md

      - name: Commit Report
        run: |
          git config user.name "GitHub Actions"
          git config user.email "actions@github.com"
          git add reports/
          git commit -m "Weekly Azure inventory report"
          git push
```

## Best Practices

### Report Frequency

- **Documentation reports:** Monthly or when major changes occur
- **Compliance reports:** Quarterly or as required by auditors
- **Cost reports:** Weekly or monthly for budget tracking
- **Change detection:** Daily or after deployment events

### Report Storage

- Store reports in version control (Git) to track changes over time
- Use descriptive filenames with timestamps
- Keep historical reports for at least 12 months
- Consider archiving old reports to separate storage

### Report Accuracy

- Use `--live` flag for compliance and security audits
- Use Neo4j (default) for regular documentation
- Scan regularly (daily/weekly) if using Neo4j for reports
- Validate cost data has processed (wait 24-48 hours after resource changes)

### Performance Optimization

- For large tenants (>5,000 resources), use Neo4j data source
- Generate filtered reports (`--subscriptions`, `--resource-groups`) for faster results
- Run reports during off-peak hours if using `--live`
- Cache reports and refresh periodically rather than generating on-demand

## Related Commands

- **`atg scan`** - Populate Neo4j graph for fast report generation
- **`atg visualize`** - Interactive 3D visualization of tenant resources
- **`atg agent-mode`** - Query tenant data with natural language
- **`atg generate-spec`** - Generate anonymized tenant specifications
- **`atg generate-iac`** - Generate Infrastructure-as-Code from tenant data

## See Also

- [Neo4j Graph Schema Reference](../NEO4J_SCHEMA_REFERENCE.md) - Understanding the underlying data model
- [Agent Mode Guide](../command-help/report-help-text.md) - Natural language queries
- [IaC Generation Guide](../quickstart/quick-start.md) - Infrastructure as Code workflows
