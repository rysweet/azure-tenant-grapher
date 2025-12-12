# Command Help Text for `atg report`

This document contains the docstring that appears when users run `atg report --help`.

## Help Text

```
Generate comprehensive Azure tenant inventory report in Markdown format.

This command creates detailed reports of your Azure environment including:
- Tenant overview and summary statistics
- Identity summary (users, service principals, groups)
- Resource inventory by type and region
- Role assignments and RBAC configuration
- Cost data (optional, requires Azure Cost Management API access)

By default, reports are generated from cached Neo4j graph data (fast). Use the
--live flag to query Azure APIs directly for real-time data (slower).

USAGE:
    atg report --tenant-id <TENANT_ID> [OPTIONS]

REQUIRED ARGUMENTS:
    --tenant-id <TENANT_ID>
        Azure tenant ID to generate report for

OPTIONS:
    --output <FILE>, -o <FILE>
        Output file path for the generated report
        Default: ./reports/tenant-inventory-<TENANT_ID>-<TIMESTAMP>.md

    --live
        Query Azure APIs directly instead of using cached Neo4j data
        Slower but guarantees current state. No scan required.
        Default: false (use Neo4j graph)

    --include-costs
        Include cost data from Azure Cost Management API
        Requires Cost Management Reader permissions
        Default: false

    --subscriptions <SUB1,SUB2,...>
        Filter report to specific subscriptions (comma-separated)
        Example: --subscriptions 00000000-0000-0000-0000-000000000001

    --resource-groups <RG1,RG2,...>
        Filter report to specific resource groups (comma-separated)
        Example: --resource-groups prod-rg,dev-rg

    --format <FORMAT>
        Output format (currently only 'markdown' is supported)
        Default: markdown
        Future: json, html, csv

    --verbose, -v
        Enable verbose output showing report generation progress

    --help, -h
        Show this help message

EXAMPLES:
    # Generate report from cached Neo4j data (requires prior scan)
    atg report --tenant-id 3cd87a41-1f61-4aef-a212-cefdecd9a2d1

    # Generate report with live Azure data (no scan required)
    atg report --tenant-id 3cd87a41-1f61-4aef-a212-cefdecd9a2d1 --live

    # Generate report with cost data
    atg report --tenant-id <TENANT_ID> --include-costs --output ./reports/cost-report.md

    # Generate report for specific subscriptions only
    atg report --tenant-id <TENANT_ID> --subscriptions sub1,sub2

    # Generate verbose report with progress information
    atg report --tenant-id <TENANT_ID> --live --verbose

DATA SOURCES:
    Neo4j Graph (default):
        - Fast (seconds)
        - Requires prior 'atg scan' to populate graph
        - Data reflects state at last scan
        - No API rate limits

    Live Azure APIs (--live flag):
        - Slower (minutes for large tenants)
        - Always current (real-time data)
        - No scan required
        - Subject to Azure API rate limits

REPORT CONTENTS:
    1. Tenant Overview
       - Tenant ID, generation timestamp, data source
       - Summary statistics (total resources, types, regions)

    2. Identity Summary
       - Users (total, active, guests)
       - Service principals and managed identities
       - Groups (security groups, M365 groups)

    3. Resource Inventory
       - Top resource types with counts
       - Resources by region
       - Subscription breakdown

    4. Role Assignments
       - Total role assignments
       - Top roles and their distribution
       - Top principals by assignment count

    5. Cost Analysis (if --include-costs specified)
       - Cost by resource type
       - Monthly spending breakdown
       - Average cost per resource

AUTHENTICATION:
    The command uses Azure CLI authentication by default:
        az login --tenant <TENANT_ID>

    For service principal authentication, set environment variables:
        export AZURE_TENANT_ID=<TENANT_ID>
        export AZURE_CLIENT_ID=<CLIENT_ID>
        export AZURE_CLIENT_SECRET=<CLIENT_SECRET>

PERMISSIONS:
    Required Azure RBAC permissions:
        - Reader (for basic resource inventory)
        - Cost Management Reader (for --include-costs)

    Required Microsoft Graph API permissions (for identity data):
        - User.Read.All
        - Group.Read.All

TROUBLESHOOTING:
    "Neo4j database not found"
        Solution: Run 'atg scan --tenant-id <TENANT_ID>' first, or use --live flag

    "Authentication failed"
        Solution: Run 'az login --tenant <TENANT_ID>' to authenticate

    "Cost data unavailable"
        Causes:
            - Missing Cost Management Reader role
            - Cost data not yet processed (24-48 hour delay)
            - --include-costs flag not specified

    "Report generation timeout"
        Solution: For large tenants, use Neo4j data source (default) instead of --live

OUTPUT FORMAT:
    Reports are generated as Markdown (.md) files with:
        - Clean, human-readable formatting
        - Tables for structured data
        - Hierarchical sections
        - Metadata headers

    Markdown reports can be:
        - Viewed in text editors
        - Rendered on GitHub, GitLab, Confluence
        - Converted to HTML/PDF with pandoc
        - Diffed for change detection

PERFORMANCE:
    Neo4j data source:
        - Small tenants (<1,000 resources): ~2-5 seconds
        - Medium tenants (1,000-5,000 resources): ~5-15 seconds
        - Large tenants (>5,000 resources): ~15-30 seconds

    Live Azure API data source (--live):
        - Small tenants: ~30-60 seconds
        - Medium tenants: ~1-3 minutes
        - Large tenants: ~3-10 minutes

RELATED COMMANDS:
    atg scan              Populate Neo4j graph for fast report generation
    atg visualize         Interactive 3D visualization of tenant
    atg agent-mode        Query tenant with natural language
    atg generate-spec     Generate anonymized tenant specification
    atg generate-iac      Generate Infrastructure-as-Code

SEE ALSO:
    Documentation: docs/guides/TENANT_INVENTORY_REPORTS.md
    Neo4j Schema: docs/NEO4J_SCHEMA_REFERENCE.md
    GitHub Issues: https://github.com/<org>/azure-tenant-grapher/issues/569
```

## Implementation Note

This help text should be implemented as the docstring in `src/commands/report.py`:

```python
def report_command(
    tenant_id: str,
    output: Optional[str] = None,
    live: bool = False,
    include_costs: bool = False,
    subscriptions: Optional[List[str]] = None,
    resource_groups: Optional[List[str]] = None,
    format: str = "markdown",
    verbose: bool = False,
) -> None:
    """Generate comprehensive Azure tenant inventory report in Markdown format.

    This command creates detailed reports of your Azure environment including:
    - Tenant overview and summary statistics
    - Identity summary (users, service principals, groups)
    - Resource inventory by type and region
    - Role assignments and RBAC configuration
    - Cost data (optional, requires Azure Cost Management API access)

    By default, reports are generated from cached Neo4j graph data (fast). Use the
    --live flag to query Azure APIs directly for real-time data (slower).

    Args:
        tenant_id: Azure tenant ID to generate report for
        output: Output file path (default: ./reports/tenant-inventory-<TENANT_ID>-<TIMESTAMP>.md)
        live: Query Azure APIs directly instead of Neo4j (default: False)
        include_costs: Include cost data from Azure Cost Management API (default: False)
        subscriptions: Filter to specific subscriptions (comma-separated)
        resource_groups: Filter to specific resource groups (comma-separated)
        format: Output format - currently only 'markdown' supported (default: markdown)
        verbose: Enable verbose output (default: False)

    Examples:
        >>> # Generate report from Neo4j (fast)
        >>> atg report --tenant-id 3cd87a41-1f61-4aef-a212-cefdecd9a2d1

        >>> # Generate report with live Azure data
        >>> atg report --tenant-id <TENANT_ID> --live

        >>> # Generate report with costs
        >>> atg report --tenant-id <TENANT_ID> --include-costs

    See docs/guides/TENANT_INVENTORY_REPORTS.md for detailed usage guide.
    """
    pass  # Implementation here
```
