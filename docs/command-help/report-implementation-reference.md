# Report Command Implementation Reference

Quick reference for developers implementing the `atg report` command based on design decisions from Issue #569.

## Command Signature

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
    """Generate comprehensive Azure tenant inventory report in Markdown format."""
```

## Implementation Architecture

### Single-File Implementation

**Location:** `src/commands/report.py`

**Design Decision:** Single file with clear section organization, not a full orchestrator pattern.

**File Structure:**
```python
# src/commands/report.py

# 1. Imports
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path
import asyncio

# 2. Data Source Orchestration
class ReportDataSource:
    """Orchestrates data retrieval from Neo4j or Azure APIs"""

    def __init__(self, tenant_id: str, use_live: bool = False):
        self.tenant_id = tenant_id
        self.use_live = use_live

    async def get_tenant_summary(self) -> Dict[str, Any]:
        """Get tenant overview statistics"""

    async def get_identity_data(self) -> Dict[str, Any]:
        """Get users, service principals, managed identities, groups"""

    async def get_resource_inventory(self) -> Dict[str, Any]:
        """Get resources by type, region, subscription"""

    async def get_role_assignments(self) -> Dict[str, Any]:
        """Get RBAC role assignments and distributions"""

    async def get_cost_data(self) -> Optional[Dict[str, Any]]:
        """Get cost data from Azure Cost Management API"""

# 3. Report Generation
class ReportGenerator:
    """Generates Markdown report from data"""

    def __init__(self, data: Dict[str, Any]):
        self.data = data

    def generate_markdown(self) -> str:
        """Generate complete Markdown report"""
        sections = [
            self._generate_header(),
            self._generate_summary(),
            self._generate_identity_section(),
            self._generate_resource_inventory(),
            self._generate_role_assignments(),
            self._generate_cost_section(),
            self._generate_footer(),
        ]
        return "\n\n---\n\n".join(sections)

    def _generate_header(self) -> str:
        """Generate report header with metadata"""

    def _generate_summary(self) -> str:
        """Generate summary statistics table"""

    # ... more section generators

# 4. Main Command Function
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
    """Main command entry point"""

    # 1. Validate inputs
    if format != "markdown":
        raise ValueError(f"Only 'markdown' format supported (got: {format})")

    # 2. Create data source
    data_source = ReportDataSource(tenant_id=tenant_id, use_live=live)

    # 3. Gather data
    if verbose:
        print("Gathering tenant data...")

    data = asyncio.run(data_source.gather_all_data(
        include_costs=include_costs,
        subscriptions=subscriptions,
        resource_groups=resource_groups,
    ))

    # 4. Generate report
    if verbose:
        print("Generating report...")

    generator = ReportGenerator(data)
    report_content = generator.generate_markdown()

    # 5. Save report
    output_path = output or _default_output_path(tenant_id)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(report_content)

    if verbose:
        print(f"Report saved to: {output_path}")

    return output_path
```

## Data Retrieval Strategy

### Neo4j Queries (Default)

```python
# Get resource count by type
RESOURCE_COUNT_QUERY = """
MATCH (r:Resource)
RETURN r.resource_type AS type, COUNT(r) AS count
ORDER BY count DESC
"""

# Get identity summary
IDENTITY_SUMMARY_QUERY = """
MATCH (u:User)
RETURN
    COUNT(u) AS total_users,
    SUM(CASE WHEN u.is_guest THEN 1 ELSE 0 END) AS guest_users
"""

# Get role assignments
ROLE_ASSIGNMENTS_QUERY = """
MATCH (principal)-[r:HAS_ROLE]->(scope)
RETURN
    principal.displayName AS principal_name,
    type(principal) AS principal_type,
    r.role_name AS role,
    labels(scope)[0] AS scope_type,
    COUNT(*) AS assignment_count
ORDER BY assignment_count DESC
"""
```

### Live Azure API Queries

```python
from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from msgraph.core import GraphClient

# Resource inventory via Azure SDK
credential = DefaultAzureCredential()
resource_client = ResourceManagementClient(credential, subscription_id)

resources = []
for resource in resource_client.resources.list():
    resources.append({
        'type': resource.type,
        'location': resource.location,
        'resource_group': resource.id.split('/')[4],
    })

# Identity data via Microsoft Graph
graph_client = GraphClient(credential=credential)
users = graph_client.get('/users').json()['value']
service_principals = graph_client.get('/servicePrincipals').json()['value']
```

## Report Sections

### 1. Header Section

```markdown
# Azure Tenant Inventory Report

**Tenant ID:** {tenant_id}
**Generated:** {timestamp} UTC
**Data Source:** {Neo4j Graph Database | Live Azure APIs}
**Report Version:** 1.0
```

### 2. Summary Statistics Section

```markdown
## Summary Statistics

| Metric | Value |
|--------|-------|
| **Total Resources** | {resource_count} |
| **Resource Types** | {type_count} |
| **Regions** | {region_count} |
| **Subscriptions** | {subscription_count} |
| **Resource Groups** | {rg_count} |
| **Total Role Assignments** | {role_assignment_count} |
```

### 3. Identity Overview Section

```markdown
## Identity Overview

### Users
- **Total Users:** {total_users}
- **Active Users:** {active_users}
- **Guest Users:** {guest_users}

### Service Principals
- **Total Service Principals:** {total_sps}
- **Application Service Principals:** {app_sps}
- **Enterprise Applications:** {enterprise_sps}

### Managed Identities
- **Total Managed Identities:** {total_mis}
  - **System-Assigned:** {system_assigned}
  - **User-Assigned:** {user_assigned}

### Groups
- **Total Groups:** {total_groups}
- **Security Groups:** {security_groups}
- **Microsoft 365 Groups:** {m365_groups}
```

### 4. Resource Inventory Section

```markdown
## Resource Inventory

### Top Resource Types

| Resource Type | Count | Primary Regions |
|--------------|-------|----------------|
| {type} | {count} | {regions} |
...

### Resources by Region

| Region | Resource Count | Percentage | Top Resource Types |
|--------|---------------|-----------|-------------------|
| {region} | {count} | {pct}% | {types} |
...
```

### 5. Role Assignments Section

```markdown
## Role Assignments

**Total Role Assignments:** {total_assignments}

### Top Roles Assigned

| Role | Assignment Count | Scope Distribution |
|------|-----------------|-------------------|
| {role} | {count} | {scopes} |
...

### Top Principals by Assignment Count

| Principal | Type | Assignment Count | Primary Roles |
|-----------|------|-----------------|--------------|
| {principal} | {type} | {count} | {roles} |
...
```

### 6. Cost Analysis Section

```markdown
## Cost Analysis

**Note:** Cost data represents the last 30 days of Azure spending.

### Cost by Resource Type

| Resource Type | Monthly Cost (USD) | Resource Count | Avg Cost per Resource |
|--------------|-------------------|----------------|---------------------|
| {type} | ${cost} | {count} | ${avg} |
...

**Total Monthly Cost:** ${total}
```

**If cost data unavailable:**
```markdown
## Cost Analysis

**Cost data unavailable.** This may be because:
- Cost Management API permissions are not configured
- Cost data has not yet been processed by Azure (can take 24-48 hours)
- The `--include-costs` flag was not specified

To enable cost reporting, ensure your service principal has `Cost Management Reader` role.
```

## Error Handling

```python
class ReportError(Exception):
    """Base exception for report command errors"""
    pass

class DataSourceError(ReportError):
    """Error retrieving data from Neo4j or Azure APIs"""
    pass

class ReportGenerationError(ReportError):
    """Error generating report content"""
    pass

# Usage
try:
    data = await data_source.get_tenant_summary()
except Neo4jConnectionError:
    raise DataSourceError(
        "Neo4j database not found. Run 'atg scan --tenant-id <TENANT_ID>' first, "
        "or use the --live flag to query Azure APIs directly."
    )
except AzureAuthenticationError:
    raise DataSourceError(
        "Azure authentication failed. Please run 'az login --tenant <TENANT_ID>'"
    )
```

## Default Output Path

```python
def _default_output_path(tenant_id: str) -> str:
    """Generate default output path with timestamp"""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"tenant-inventory-{tenant_id}-{timestamp}.md"
    return f"./reports/{filename}"
```

## Filtering Implementation

```python
class ReportDataSource:
    async def get_resource_inventory(
        self,
        subscriptions: Optional[List[str]] = None,
        resource_groups: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Get filtered resource inventory"""

        # Build filter clause
        filters = []
        if subscriptions:
            sub_filter = "r.subscription_id IN $subscriptions"
            filters.append(sub_filter)
        if resource_groups:
            rg_filter = "r.resource_group IN $resource_groups"
            filters.append(rg_filter)

        where_clause = " AND ".join(filters) if filters else "1=1"

        query = f"""
        MATCH (r:Resource)
        WHERE {where_clause}
        RETURN r.resource_type AS type, COUNT(r) AS count
        ORDER BY count DESC
        """

        # Execute with parameters
        result = await neo4j_client.run(
            query,
            subscriptions=subscriptions,
            resource_groups=resource_groups,
        )

        return result
```

## Cost Data Integration

```python
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.costmanagement.models import (
    QueryDefinition,
    TimeframeType,
    QueryDataset,
)

async def get_cost_data(self) -> Optional[Dict[str, Any]]:
    """Get cost data from Azure Cost Management API"""

    try:
        cost_client = CostManagementClient(
            credential=self.credential,
            subscription_id=self.subscription_id,
        )

        # Query last 30 days of costs grouped by resource type
        query = QueryDefinition(
            type="Usage",
            timeframe=TimeframeType.MONTH_TO_DATE,
            dataset=QueryDataset(
                granularity="Monthly",
                aggregation={
                    "totalCost": {
                        "name": "PreTaxCost",
                        "function": "Sum"
                    }
                },
                grouping=[
                    {"type": "Dimension", "name": "ResourceType"}
                ]
            )
        )

        result = cost_client.query.usage(
            scope=f"/subscriptions/{self.subscription_id}",
            parameters=query
        )

        # Parse results into dictionary
        costs = {}
        for row in result.rows:
            resource_type = row[1]  # ResourceType dimension
            cost = row[0]  # PreTaxCost value
            costs[resource_type] = cost

        return costs

    except Exception as e:
        # Cost data is optional - log but don't fail
        if self.verbose:
            print(f"Warning: Could not retrieve cost data: {e}")
        return None
```

## Performance Considerations

### Neo4j Query Optimization

```python
# BAD - Multiple separate queries
users = neo4j.run("MATCH (u:User) RETURN COUNT(u)")
sps = neo4j.run("MATCH (sp:ServicePrincipal) RETURN COUNT(sp)")
groups = neo4j.run("MATCH (g:Group) RETURN COUNT(g)")

# GOOD - Single combined query
identity_summary = neo4j.run("""
    MATCH (u:User)
    OPTIONAL MATCH (sp:ServicePrincipal)
    OPTIONAL MATCH (g:Group)
    RETURN
        COUNT(DISTINCT u) AS user_count,
        COUNT(DISTINCT sp) AS sp_count,
        COUNT(DISTINCT g) AS group_count
""")
```

### Async Gathering

```python
async def gather_all_data(
    self,
    include_costs: bool = False,
    subscriptions: Optional[List[str]] = None,
    resource_groups: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Gather all report data concurrently"""

    # Gather data in parallel for speed
    tasks = [
        self.get_tenant_summary(),
        self.get_identity_data(),
        self.get_resource_inventory(subscriptions, resource_groups),
        self.get_role_assignments(),
    ]

    if include_costs:
        tasks.append(self.get_cost_data())

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Handle any errors
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            task_name = ["summary", "identity", "resources", "roles", "costs"][i]
            print(f"Warning: Failed to retrieve {task_name} data: {result}")
            results[i] = None  # Use None for failed data

    return {
        "summary": results[0],
        "identity": results[1],
        "resources": results[2],
        "roles": results[3],
        "costs": results[4] if include_costs else None,
    }
```

## Testing Strategy

### Unit Tests

```python
# Test report generation
def test_report_generator_creates_valid_markdown():
    data = {
        "summary": {"total_resources": 100, "resource_types": 10},
        "identity": {"users": 50, "service_principals": 200},
        # ...
    }

    generator = ReportGenerator(data)
    report = generator.generate_markdown()

    assert "# Azure Tenant Inventory Report" in report
    assert "100" in report  # total_resources
    assert "| Metric | Value |" in report  # table format

# Test filtering
def test_report_filters_by_subscription():
    data_source = ReportDataSource(tenant_id="test", use_live=False)
    result = asyncio.run(
        data_source.get_resource_inventory(subscriptions=["sub1"])
    )

    # Verify only sub1 resources returned
    assert all(r["subscription_id"] == "sub1" for r in result["resources"])
```

### Integration Tests

```python
# Test end-to-end with Neo4j testcontainers
@pytest.mark.integration
def test_report_command_with_neo4j(neo4j_container):
    # Populate test data
    neo4j_client = neo4j_container.get_client()
    neo4j_client.run("CREATE (r:Resource {resource_type: 'Microsoft.Compute/VMs'})")

    # Run report command
    output = report_command(
        tenant_id="test-tenant",
        output="./test-report.md",
        live=False,
    )

    # Verify report generated
    assert Path(output).exists()
    content = Path(output).read_text()
    assert "Microsoft.Compute/VMs" in content
```

## CLI Integration

```python
# scripts/cli.py

@cli.command("report")
@click.option("--tenant-id", required=True, help="Azure tenant ID")
@click.option("--output", "-o", help="Output file path")
@click.option("--live", is_flag=True, help="Use live Azure data")
@click.option("--include-costs", is_flag=True, help="Include cost data")
@click.option("--subscriptions", help="Filter by subscriptions (comma-separated)")
@click.option("--resource-groups", help="Filter by resource groups (comma-separated)")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def report_cli(tenant_id, output, live, include_costs, subscriptions, resource_groups, verbose):
    """Generate comprehensive Azure tenant inventory report."""

    # Parse filters
    sub_list = subscriptions.split(",") if subscriptions else None
    rg_list = resource_groups.split(",") if resource_groups else None

    # Run command
    try:
        output_path = report_command(
            tenant_id=tenant_id,
            output=output,
            live=live,
            include_costs=include_costs,
            subscriptions=sub_list,
            resource_groups=rg_list,
            verbose=verbose,
        )

        click.echo(f"Report generated: {output_path}")

    except ReportError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
```

## Related Design Decisions

- **Single-file implementation**: Simpler than orchestrator pattern for MVP
- **Markdown only**: Other formats (JSON, HTML) can be added later
- **Hybrid data source**: Neo4j default (fast), `--live` for real-time
- **Cost data optional**: Requires permissions, shows "N/A" if unavailable
- **Direct service calls**: Uses existing services, no new abstractions

## Next Steps After Implementation

1. **Test with real tenants** - Validate report accuracy
2. **Add JSON output** - `--format json` for programmatic use
3. **Add report diff** - Compare reports over time
4. **Add filtering** - More granular resource selection
5. **Add HTML export** - `--format html` with charts

## See Also

- Issue #569: Original feature request
- `docs/guides/TENANT_INVENTORY_REPORTS.md`: User guide
- `docs/examples/example-tenant-report.md`: Example output
- `src/services/`: Existing services to reuse
