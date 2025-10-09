"""Validate deployment command for comparing source and target graphs.

This module provides the CLI command for validating deployments by comparing
Neo4j graphs between source and target tenants.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import click
from neo4j import GraphDatabase
from rich.console import Console

from ..config_manager import create_neo4j_config_from_env
from ..validation import (
    compare_filtered_graphs,
    compare_graphs,
    generate_json_report,
    generate_markdown_report,
)

logger = logging.getLogger(__name__)
console = Console()


def query_resources(
    driver: Any, tenant_id: str, filter_query: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Query resources from Neo4j for a given tenant.

    Args:
        driver: Neo4j driver instance
        tenant_id: Tenant ID to query
        filter_query: Optional Cypher filter clause

    Returns:
        List of resource dictionaries
    """
    with driver.session() as session:
        # Build Cypher query
        query = "MATCH (r:Resource) WHERE r.tenant_id = $tid"
        if filter_query:
            query += f" AND {filter_query}"
        query += " RETURN r"

        result = session.run(query, tid=tenant_id)
        resources = [dict(record["r"]) for record in result]
        logger.info(f"Retrieved {len(resources)} resources for tenant {tenant_id}")
        return resources


@click.command(name="validate-deployment")
@click.option("--source-tenant-id", required=True, help="Source tenant ID to compare from")
@click.option("--target-tenant-id", required=True, help="Target tenant ID to compare to")
@click.option(
    "--source-filter",
    help="Filter for source resources (e.g., resourceGroup=RG1)",
)
@click.option(
    "--target-filter",
    help="Filter for target resources (e.g., resourceGroup=RG2)",
)
@click.option(
    "--output",
    type=click.Path(),
    help="Output file path for the validation report (default: stdout)",
)
@click.option(
    "--format",
    type=click.Choice(["markdown", "json"], case_sensitive=False),
    default="markdown",
    help="Report output format",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Enable verbose logging",
)
def validate_deployment_command(
    source_tenant_id: str,
    target_tenant_id: str,
    source_filter: Optional[str],
    target_filter: Optional[str],
    output: Optional[str],
    format: str,
    verbose: bool,
) -> None:
    """Validate deployment by comparing source and target graphs.

    This command compares the Neo4j graphs for two tenants (source and target)
    and generates a detailed validation report showing:

    - Resource count comparison
    - Missing and extra resources
    - Overall similarity score
    - Validation status and recommendations

    The comparison helps verify that a deployment successfully replicated
    the source configuration to the target environment.

    Examples:

        # Basic validation
        atg validate-deployment \\
            --source-tenant-id 3cd87a41-1f61-4aef-a212-cefdecd9a2d1 \\
            --target-tenant-id 506f82b2-e2e7-40a2-b0be-ea6f8cb908f8

        # With filtering
        atg validate-deployment \\
            --source-tenant-id 3cd87a41-1f61-4aef-a212-cefdecd9a2d1 \\
            --target-tenant-id 506f82b2-e2e7-40a2-b0be-ea6f8cb908f8 \\
            --source-filter resourceGroup=RG1 \\
            --target-filter resourceGroup=RG2

        # Save to file
        atg validate-deployment \\
            --source-tenant-id 3cd87a41-1f61-4aef-a212-cefdecd9a2d1 \\
            --target-tenant-id 506f82b2-e2e7-40a2-b0be-ea6f8cb908f8 \\
            --output validation-report.md

        # JSON output
        atg validate-deployment \\
            --source-tenant-id 3cd87a41-1f61-4aef-a212-cefdecd9a2d1 \\
            --target-tenant-id 506f82b2-e2e7-40a2-b0be-ea6f8cb908f8 \\
            --format json \\
            --output validation.json
    """
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    try:
        console.print("[cyan]Connecting to Neo4j...[/cyan]")

        # Connect to Neo4j
        config = create_neo4j_config_from_env()
        if not config.neo4j.uri:
            raise RuntimeError("Neo4j URI is not configured")
        driver = GraphDatabase.driver(
            config.neo4j.uri, auth=(config.neo4j.user, config.neo4j.password)
        )

        console.print(f"[cyan]Querying source resources (tenant: {source_tenant_id})...[/cyan]")

        # Query source resources
        source_resources = query_resources(driver, source_tenant_id)

        if not source_resources:
            console.print(
                f"[yellow]⚠ Warning: No resources found for source tenant {source_tenant_id}[/yellow]"
            )

        console.print(f"[cyan]Querying target resources (tenant: {target_tenant_id})...[/cyan]")

        # Query target resources
        target_resources = query_resources(driver, target_tenant_id)

        if not target_resources:
            console.print(
                f"[yellow]⚠ Warning: No resources found for target tenant {target_tenant_id}[/yellow]"
            )

        driver.close()

        console.print("[cyan]Comparing graphs...[/cyan]")

        # Perform comparison
        if source_filter or target_filter:
            result = compare_filtered_graphs(
                source_resources, target_resources, source_filter, target_filter
            )
        else:
            result = compare_graphs(source_resources, target_resources)

        # Generate report based on format
        if format == "json":
            report_data = generate_json_report(result)
            report_text = json.dumps(report_data, indent=2)
        else:
            report_text = generate_markdown_report(
                result, source_tenant_id, target_tenant_id
            )

        # Output report
        if output:
            output_path = Path(output)
            output_path.write_text(report_text)
            console.print(f"[green]✅ Report saved to {output}[/green]")

            # Show summary in console
            console.print("\n[bold]Validation Summary[/bold]")
            console.print(f"Similarity Score: {result.similarity_score:.1f}%")
            console.print(f"Source Resources: {result.source_resource_count}")
            console.print(f"Target Resources: {result.target_resource_count}")

            if result.similarity_score >= 95:
                console.print("[green]Status: COMPLETE ✅[/green]")
            elif result.similarity_score >= 80:
                console.print("[yellow]Status: MOSTLY COMPLETE ⚠️[/yellow]")
            else:
                console.print("[red]Status: INCOMPLETE ❌[/red]")
        else:
            # Print full report to stdout
            click.echo(report_text)

    except Exception as e:
        console.print(f"[red]❌ Validation failed: {e}[/red]")
        if verbose:
            logger.exception("Validation error details:")
        raise SystemExit(1) from e
