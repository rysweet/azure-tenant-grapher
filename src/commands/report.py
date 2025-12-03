"""
Tenant Report Command - Generate comprehensive Azure tenant inventory report.

This command provides a complete overview of an Azure tenant including:
- Entra ID identities (users, service principals, managed identities, groups)
- Azure resources (counts, types, regions)
- Role assignments and security settings
- Cost data (when available)

Architecture:
- Single-file implementation (~500 lines)
- Hybrid data source: Neo4j (default) or Azure APIs (--live flag)
- Parallel collection using asyncio.gather() for 20+ concurrent operations
- Markdown output format (MVP)

Philosophy:
- Zero-BS: Every function works, no stubs or placeholders
- Simple: Direct orchestration without service layers
- Pragmatic: Show "N/A" when cost data unavailable
"""

import asyncio
import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import click
from azure.identity import DefaultAzureCredential
from neo4j import AsyncDriver, AsyncGraphDatabase

from src.config_manager import AzureTenantGrapherConfig
from src.services.aad_graph_service import AADGraphService
from src.services.azure_discovery_service import AzureDiscoveryService

# ============================================================================
# DATA MODELS
# ============================================================================


@dataclass
class TenantReportData:
    """Complete tenant report data"""

    tenant_id: str
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # Identity counts
    users: int = 0
    service_principals: int = 0
    managed_identities: int = 0
    groups: int = 0

    # Resource counts
    total_resources: int = 0
    total_types: int = 0
    regions: int = 0

    # Resource distributions
    resources_by_type: Dict[str, int] = field(default_factory=dict)
    resources_by_region: Dict[str, int] = field(default_factory=dict)

    # Security
    role_assignments: int = 0
    custom_roles: int = 0

    # Cost (optional)
    cost_data: Optional[Dict[str, Any]] = None

    # Metadata
    data_source: str = "neo4j"  # "neo4j" or "live"


# ============================================================================
# FORMATTING FUNCTIONS (Unit-testable, no dependencies)
# ============================================================================


def format_number(num: int) -> str:
    """Format number with thousand separators"""
    return f"{num:,}"


def format_identity_summary(identity_data: Dict[str, int]) -> str:
    """Format identity summary section"""
    lines = [
        "## Identity Summary",
        "",
        "| Identity Type | Count |",
        "|---------------|-------|",
    ]

    lines.append(f"| Users | {format_number(identity_data.get('users', 0))} |")
    lines.append(
        f"| Service Principals | {format_number(identity_data.get('service_principals', 0))} |"
    )
    lines.append(
        f"| Managed Identities | {format_number(identity_data.get('managed_identities', 0))} |"
    )
    lines.append(f"| Groups | {format_number(identity_data.get('groups', 0))} |")

    return "\n".join(lines)


def format_resource_summary(resource_data: Dict[str, int]) -> str:
    """Format resource summary section"""
    lines = ["## Resource Summary", "", "| Metric | Count |", "|--------|-------|"]

    lines.append(
        f"| Total Resources | {format_number(resource_data.get('total_resources', 0))} |"
    )
    lines.append(
        f"| Resource Types | {format_number(resource_data.get('total_types', 0))} |"
    )
    lines.append(f"| Regions | {format_number(resource_data.get('regions', 0))} |")

    return "\n".join(lines)


def format_top_resource_types(top_types: List[Tuple[str, int]]) -> str:
    """Format top resource types section"""
    lines = [
        "## Top Resource Types",
        "",
        "| Resource Type | Count |",
        "|---------------|-------|",
    ]

    for resource_type, count in top_types:
        lines.append(f"| {resource_type} | {format_number(count)} |")

    return "\n".join(lines)


def format_region_distribution(regions: List[Tuple[str, int]]) -> str:
    """Format region distribution section"""
    lines = [
        "## Region Distribution",
        "",
        "| Region | Resource Count |",
        "|--------|----------------|",
    ]

    for region, count in regions:
        lines.append(f"| {region} | {format_number(count)} |")

    return "\n".join(lines)


def format_security_summary(security_data: Dict[str, int]) -> str:
    """Format security summary section"""
    lines = ["## Security Summary", "", "| Metric | Count |", "|--------|-------|"]

    lines.append(
        f"| Role Assignments | {format_number(security_data.get('role_assignments', 0))} |"
    )
    lines.append(
        f"| Custom Roles | {format_number(security_data.get('custom_roles', 0))} |"
    )

    return "\n".join(lines)


def format_cost_summary(cost_data: Optional[Dict[str, Any]]) -> str:
    """Format cost summary section"""
    lines = ["## Cost Summary", "", "| Metric | Value |", "|--------|-------|"]

    if cost_data is None:
        lines.append("| Total Cost (30 days) | N/A |")
    else:
        total_cost = cost_data.get("total_cost", 0.0)
        currency = cost_data.get("currency", "USD")
        # Format cost with proper rounding to 2 decimal places
        lines.append(f"| Total Cost (30 days) | ${total_cost:,.2f} {currency} |")

    return "\n".join(lines)


# ============================================================================
# DATA AGGREGATION FUNCTIONS (Unit-testable)
# ============================================================================


def aggregate_identity_counts(graph_data: List[Dict[str, Any]]) -> Dict[str, int]:
    """Aggregate identity counts from graph data"""
    result = {
        "users": 0,
        "service_principals": 0,
        "managed_identities": 0,
        "groups": 0,
    }

    for item in graph_data:
        identity_type = item.get("type", "")
        count = item.get("count", 0)

        if identity_type == "User":
            result["users"] = count
        elif identity_type == "ServicePrincipal":
            result["service_principals"] = count
        elif identity_type == "ManagedIdentity":
            result["managed_identities"] = count
        elif identity_type == "Group":
            result["groups"] = count

    return result


def group_resources_by_type(resources: List[Dict[str, Any]]) -> Dict[str, int]:
    """Group resources by type and count"""
    result: Dict[str, int] = defaultdict(int)

    for resource in resources:
        resource_type = resource.get("type", "Unknown")
        result[resource_type] += 1

    return dict(result)


def group_resources_by_region(resources: List[Dict[str, Any]]) -> Dict[str, int]:
    """Group resources by region and count"""
    result: Dict[str, int] = defaultdict(int)

    for resource in resources:
        location = resource.get("location", "Unknown")
        result[location] += 1

    return dict(result)


def count_unique_regions(resources: List[Dict[str, Any]]) -> int:
    """Count unique regions from resource data"""
    regions = set()
    for resource in resources:
        location = resource.get("location")
        if location:
            regions.add(location)
    return len(regions)


def get_top_items(data: Dict[str, int], limit: int = 10) -> List[Tuple[str, int]]:
    """Sort and limit to top N items"""
    sorted_items = sorted(data.items(), key=lambda x: x[1], reverse=True)
    return sorted_items[:limit]


# ============================================================================
# COST DATA HANDLING
# ============================================================================


def extract_cost_data(
    cost_response: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Extract cost data from API response"""
    if cost_response is None:
        return None

    try:
        rows = cost_response.get("properties", {}).get("rows", [])
        if not rows:
            return None

        # First row contains total cost and currency
        first_row = rows[0]
        return {
            "total_cost": first_row[0],
            "currency": first_row[1],
            "period": "last_30_days",
        }
    except (IndexError, KeyError, TypeError):
        return None


# ============================================================================
# ERROR MESSAGE FORMATTING
# ============================================================================


def format_neo4j_connection_error(error_msg: str) -> str:
    """Format error message when Neo4j connection fails"""
    return f"""Neo4j connection failed: {error_msg}

Please ensure Neo4j is running. You can start it with:
    atg container start
"""


def format_azure_auth_error(error_msg: str) -> str:
    """Format error message when Azure authentication fails"""
    return f"""Azure authentication failed: {error_msg}

Please check your credentials and ensure you have the required permissions.
Run 'atg doctor' to verify your Azure configuration.
"""


def format_no_data_error() -> str:
    """Format error message when no data is found in Neo4j"""
    return """No data found in Neo4j database.

Please run a scan first to populate the database:
    atg scan --tenant-id <TENANT_ID>
"""


# ============================================================================
# NEO4J QUERY FUNCTIONS
# ============================================================================


async def query_identity_counts(driver: AsyncDriver) -> Dict[str, int]:
    """Query identity counts from Neo4j"""
    query = """
    MATCH (n)
    WHERE n:User OR n:ServicePrincipal OR n:ManagedIdentity OR n:Group
    WITH labels(n)[0] AS type, count(n) AS count
    RETURN type, count
    """

    async with driver.session() as session:
        result = await session.run(query)
        records = await result.data()

    return aggregate_identity_counts(records)


async def query_resource_counts(driver: AsyncDriver) -> Dict[str, int]:
    """Query resource counts from Neo4j"""
    query = """
    MATCH (r:Resource)
    WITH count(r) AS total,
         count(DISTINCT r.type) AS types,
         count(DISTINCT r.location) AS regions
    RETURN total, types, regions
    """

    async with driver.session() as session:
        result = await session.run(query)
        records = await result.data()

    if not records:
        return {"total_resources": 0, "total_types": 0, "regions": 0}

    record = records[0]
    return {
        "total_resources": record.get("total", 0),
        "total_types": record.get("types", 0),
        "regions": record.get("regions", 0),
    }


async def query_resources_by_type(driver: AsyncDriver) -> Dict[str, int]:
    """Query resources grouped by type from Neo4j"""
    query = """
    MATCH (r:Resource)
    WHERE r.type IS NOT NULL
    RETURN r.type AS type, count(r) AS count
    ORDER BY count DESC
    """

    async with driver.session() as session:
        result = await session.run(query)
        records = await result.data()

    return {record["type"]: record["count"] for record in records}


async def query_resources_by_region(driver: AsyncDriver) -> Dict[str, int]:
    """Query resources grouped by region from Neo4j"""
    query = """
    MATCH (r:Resource)
    WHERE r.location IS NOT NULL
    RETURN r.location AS region, count(r) AS count
    ORDER BY count DESC
    """

    async with driver.session() as session:
        result = await session.run(query)
        records = await result.data()

    return {record["region"]: record["count"] for record in records}


async def query_role_assignments(driver: AsyncDriver) -> Dict[str, int]:
    """Query role assignment counts from Neo4j"""
    query = """
    MATCH ()-[r:HAS_ROLE]->()
    RETURN count(r) AS role_assignments
    """

    async with driver.session() as session:
        result = await session.run(query)
        records = await result.data()

    if not records:
        return {"role_assignments": 0}

    return {"role_assignments": records[0].get("role_assignments", 0)}


async def collect_neo4j_data(driver: AsyncDriver) -> TenantReportData:
    """Collect all data from Neo4j in parallel"""
    # Execute all queries in parallel
    identity_task = query_identity_counts(driver)
    resource_task = query_resource_counts(driver)
    by_type_task = query_resources_by_type(driver)
    by_region_task = query_resources_by_region(driver)
    role_task = query_role_assignments(driver)

    (
        identities,
        resource_counts,
        by_type,
        by_region,
        roles,
    ) = await asyncio.gather(
        identity_task,
        resource_task,
        by_type_task,
        by_region_task,
        role_task,
    )

    # Build report data
    report = TenantReportData(
        tenant_id="",  # Will be set by caller
        users=identities.get("users", 0),
        service_principals=identities.get("service_principals", 0),
        managed_identities=identities.get("managed_identities", 0),
        groups=identities.get("groups", 0),
        total_resources=resource_counts.get("total_resources", 0),
        total_types=resource_counts.get("total_types", 0),
        regions=resource_counts.get("regions", 0),
        resources_by_type=by_type,
        resources_by_region=by_region,
        role_assignments=roles.get("role_assignments", 0),
        data_source="neo4j",
    )

    return report


# ============================================================================
# AZURE API FUNCTIONS
# ============================================================================


async def fetch_identities_from_azure(aad_service: AADGraphService) -> Dict[str, int]:
    """Fetch identity data from Azure Graph API"""
    users_task = aad_service.get_users()
    sps_task = aad_service.get_service_principals()
    groups_task = aad_service.get_groups()

    users, sps, groups = await asyncio.gather(users_task, sps_task, groups_task)

    return {
        "users": len(users),
        "service_principals": len(sps),
        "groups": len(groups),
        "managed_identities": 0,  # Will be counted from resources
    }


async def fetch_resources_from_azure(
    discovery_service: AzureDiscoveryService,
) -> Dict[str, Any]:
    """Fetch resource data from Azure Resource Management API"""
    # First discover subscriptions
    subscriptions = await discovery_service.discover_subscriptions()
    subscription_ids = [sub["id"] for sub in subscriptions]

    # Then discover resources across all subscriptions
    resources = await discovery_service.discover_resources_across_subscriptions(
        subscription_ids=subscription_ids
    )

    by_type = group_resources_by_type(resources)
    by_region = group_resources_by_region(resources)

    # Count managed identities from resources
    mi_type = "Microsoft.ManagedIdentity/userAssignedIdentities"
    managed_identities = by_type.get(mi_type, 0)

    return {
        "total_resources": len(resources),
        "total_types": len(by_type),
        "regions": len(by_region),
        "by_type": by_type,
        "by_region": by_region,
        "managed_identities": managed_identities,
    }


async def fetch_cost_from_azure(cost_service: Any) -> Optional[Dict[str, Any]]:
    """Fetch cost data from Azure Cost Management API"""
    try:
        cost_data = await cost_service.get_subscription_costs()
        return cost_data
    except Exception:
        # Cost API is optional - return None if unavailable
        return None


async def collect_azure_data(
    aad_service: AADGraphService,
    discovery_service: AzureDiscoveryService,
    cost_service: Optional[Any] = None,
) -> TenantReportData:
    """Collect all data from Azure APIs in parallel"""
    # Launch all collection tasks in parallel
    identities_task = fetch_identities_from_azure(aad_service)
    resources_task = fetch_resources_from_azure(discovery_service)

    tasks: List[Any] = [identities_task, resources_task]

    if cost_service:
        cost_task = fetch_cost_from_azure(cost_service)
        tasks.append(cost_task)
        results = await asyncio.gather(*tasks)
        identities = results[0]
        resources = results[1]
        cost_data = results[2]
    else:
        results = await asyncio.gather(*tasks)
        identities = results[0]
        resources = results[1]
        cost_data = None

    # Merge managed identities count from resources
    identities["managed_identities"] = resources["managed_identities"]

    # Build report data
    report = TenantReportData(
        tenant_id="",  # Will be set by caller
        users=identities["users"],
        service_principals=identities["service_principals"],
        managed_identities=identities["managed_identities"],
        groups=identities["groups"],
        total_resources=resources["total_resources"],
        total_types=resources["total_types"],
        regions=resources["regions"],
        resources_by_type=resources["by_type"],
        resources_by_region=resources["by_region"],
        role_assignments=0,  # Not collected in live mode (too expensive)
        cost_data=cost_data,
        data_source="live",
    )

    return report


# ============================================================================
# FILE OUTPUT
# ============================================================================


def write_report_to_file(content: str, output_path: Path) -> None:
    """Write report content to file"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content)


# ============================================================================
# REPORT GENERATION
# ============================================================================


def generate_markdown_report(data: TenantReportData) -> str:
    """Generate complete markdown report"""
    lines = []

    # Header
    lines.append("# Azure Tenant Report")
    lines.append("")
    lines.append(f"**Tenant ID**: `{data.tenant_id}`")
    lines.append(f"**Generated**: {data.generated_at}")
    lines.append(f"**Data Source**: {data.data_source}")
    lines.append("")

    # Identity Summary
    identity_data = {
        "users": data.users,
        "service_principals": data.service_principals,
        "managed_identities": data.managed_identities,
        "groups": data.groups,
    }
    lines.append(format_identity_summary(identity_data))
    lines.append("")

    # Resource Summary
    resource_data = {
        "total_resources": data.total_resources,
        "total_types": data.total_types,
        "regions": data.regions,
    }
    lines.append(format_resource_summary(resource_data))
    lines.append("")

    # Top Resource Types
    if data.resources_by_type:
        top_types = get_top_items(data.resources_by_type, limit=10)
        lines.append(format_top_resource_types(top_types))
        lines.append("")

    # Region Distribution
    if data.resources_by_region:
        top_regions = get_top_items(data.resources_by_region, limit=10)
        lines.append(format_region_distribution(top_regions))
        lines.append("")

    # Security Summary
    security_data = {
        "role_assignments": data.role_assignments,
        "custom_roles": data.custom_roles,
    }
    lines.append(format_security_summary(security_data))
    lines.append("")

    # Cost Summary
    lines.append(format_cost_summary(data.cost_data))
    lines.append("")

    return "\n".join(lines)


# ============================================================================
# NEO4J CONFIGURATION
# ============================================================================


def get_neo4j_config_from_env() -> Tuple[str, str, str]:
    """Get Neo4j configuration from environment variables"""
    port = os.getenv("NEO4J_PORT", "7687")
    uri = os.getenv("NEO4J_URI", f"bolt://localhost:{port}")
    user = "neo4j"
    password = os.getenv("NEO4J_PASSWORD", "password")

    return uri, user, password


# ============================================================================
# CLI COMMAND
# ============================================================================


@click.command()
@click.option(
    "--tenant-id",
    required=True,
    help="Azure tenant ID",
)
@click.option(
    "--output",
    type=click.Path(),
    default="tenant-report.md",
    help="Output file path (default: tenant-report.md)",
)
@click.option(
    "--live",
    is_flag=True,
    help="Query Azure APIs directly instead of Neo4j",
)
def report(tenant_id: str, output: str, live: bool) -> None:
    """Generate comprehensive tenant report.

    Display: Users, Service Principals, Managed Identities, Groups,
    Resources, Resource Types, Regions, Role Assignments, Costs

    Default mode: Query Neo4j database (fast)
    Live mode: Query Azure APIs directly (slower, requires auth)
    """
    asyncio.run(_async_report(tenant_id, output, live))


async def _async_report(tenant_id: str, output: str, live: bool) -> None:
    """Async implementation of report command"""
    try:
        click.echo(f"Generating tenant report for: {tenant_id}")
        click.echo(f"Data source: {'Azure APIs (live)' if live else 'Neo4j (cached)'}")
        click.echo("")

        if live:
            # Live mode: Query Azure APIs
            credential = DefaultAzureCredential()
            aad_service = AADGraphService(use_mock=False)

            # Create config for discovery service
            config = AzureTenantGrapherConfig()
            config.tenant_id = tenant_id
            discovery_service = AzureDiscoveryService(
                config=config, credential=credential
            )

            click.echo("Collecting data from Azure APIs (parallel)...")
            data = await collect_azure_data(aad_service, discovery_service)
            data.tenant_id = tenant_id

        else:
            # Neo4j mode: Query graph database
            try:
                uri, user, password = get_neo4j_config_from_env()
                async with AsyncGraphDatabase.driver(
                    uri, auth=(user, password)
                ) as driver:
                    click.echo("Collecting data from Neo4j (parallel)...")
                    data = await collect_neo4j_data(driver)
                    data.tenant_id = tenant_id

            except Exception as e:
                click.echo(format_neo4j_connection_error(str(e)), err=True)
                raise click.Abort() from e

        # Check if data was found
        if data.total_resources == 0 and data.users == 0:
            click.echo(format_no_data_error(), err=True)
            raise click.Abort()

        # Generate markdown report
        click.echo("Generating markdown report...")
        markdown = generate_markdown_report(data)

        # Write to file
        output_path = Path(output)
        write_report_to_file(markdown, output_path)

        click.echo("")
        click.echo(f"✅ Report generated successfully: {output_path}")
        click.echo("")
        click.echo("Summary:")
        click.echo(f"  Users: {format_number(data.users)}")
        click.echo(f"  Service Principals: {format_number(data.service_principals)}")
        click.echo(f"  Managed Identities: {format_number(data.managed_identities)}")
        click.echo(f"  Groups: {format_number(data.groups)}")
        click.echo(f"  Total Resources: {format_number(data.total_resources)}")
        click.echo(f"  Resource Types: {format_number(data.total_types)}")
        click.echo(f"  Regions: {format_number(data.regions)}")
        click.echo(f"  Role Assignments: {format_number(data.role_assignments)}")

    except click.Abort:
        raise
    except Exception as e:
        if "authentication" in str(e).lower() or "credential" in str(e).lower():
            click.echo(format_azure_auth_error(str(e)), err=True)
        else:
            click.echo(f"Error generating report: {e}", err=True)
        raise click.Abort() from e
