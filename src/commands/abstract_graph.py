"""CLI command for graph abstraction.

Creates smaller, representative subsets of Azure tenant graphs.
"""

import asyncio
import logging
import os
from typing import Any, Dict

import click
from neo4j import GraphDatabase
from rich.console import Console
from rich.table import Table

from src.container_manager import Neo4jContainerManager
from src.services.graph_abstraction_service import GraphAbstractionService

logger = logging.getLogger(__name__)
console = Console()


@click.command("abstract-graph")
@click.option("--tenant-id", required=True, help="Source tenant ID to abstract from")
@click.option(
    "--sample-size",
    type=int,
    required=True,
    help="Target number of nodes in abstraction",
)
@click.option(
    "--seed", type=int, default=None, help="Random seed for reproducible sampling"
)
@click.option(
    "--clear",
    is_flag=True,
    default=False,
    help="Clear existing :SAMPLE_OF relationships first",
)
@click.option(
    "--preserve-security-patterns",
    is_flag=True,
    default=False,
    help="Preserve security-critical patterns (attack paths, privilege escalation)",
)
@click.option(
    "--security-patterns",
    type=str,
    default=None,
    help="Comma-separated pattern names to preserve (default: all HIGH criticality)",
)
def abstract_graph(
    tenant_id: str,
    sample_size: int,
    seed: int | None,
    clear: bool,
    preserve_security_patterns: bool,
    security_patterns: str | None,
) -> None:
    """Create abstracted subset of Azure tenant graph with optional security preservation.

    This command creates a smaller, representative subset of a large Azure
    tenant graph while preserving resource type distribution and (optionally)
    security-critical patterns like attack paths and privilege escalation chains.

    Examples:
        Basic sampling (original behavior):
        atg abstract-graph --tenant-id abc-123 --sample-size 100 --clear

        Security-aware sampling (preserve HIGH criticality patterns):
        atg abstract-graph --tenant-id abc-123 --sample-size 100 --preserve-security-patterns

        Preserve specific patterns:
        atg abstract-graph --tenant-id abc-123 --sample-size 100 \\
            --preserve-security-patterns \\
            --security-patterns "public_to_sensitive,privilege_escalation"

    The command:
    1. Samples nodes using stratified sampling by resource type
    2. (Optional) Augments sample to preserve security patterns
    3. Creates :SAMPLE_OF relationships linking samples to originals
    4. Displays statistics including security coverage metrics

    \b
    Requirements:
    - Source tenant must be already scanned (use 'atg scan' first)
    - Neo4j must be running (started automatically)
    - Minimum 10 resources required in source graph
    """
    try:
        asyncio.run(
            _abstract_graph_async(
                tenant_id,
                sample_size,
                seed,
                clear,
                preserve_security_patterns,
                security_patterns,
            )
        )
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise click.Abort() from e


async def _abstract_graph_async(
    tenant_id: str,
    sample_size: int,
    seed: int | None,
    clear: bool,
    preserve_security_patterns: bool,
    security_patterns: str | None,
) -> None:
    """Async implementation of abstract-graph command."""
    # Ensure Neo4j is running
    container_manager = Neo4jContainerManager()
    await container_manager.ensure_neo4j_running()

    console.print(f"[bold]Creating abstraction for tenant:[/bold] {tenant_id}")
    console.print(f"[bold]Target sample size:[/bold] {sample_size}")

    if preserve_security_patterns:
        console.print(
            "[bold]Security mode:[/bold] [green]ENABLED[/green] "
            "(preserving security-critical patterns)"
        )

    # Get Neo4j configuration from environment
    neo4j_uri = os.environ.get("NEO4J_URI")
    neo4j_password = os.environ.get("NEO4J_PASSWORD")

    if not neo4j_uri or not neo4j_password:
        console.print("[red]Error:[/red] NEO4J_URI and NEO4J_PASSWORD must be set")
        raise click.Abort()

    # Create Neo4j driver
    driver = GraphDatabase.driver(neo4j_uri, auth=("neo4j", neo4j_password))

    try:
        # Parse security patterns if provided
        patterns_list = None
        if security_patterns:
            patterns_list = [p.strip() for p in security_patterns.split(",")]
            console.print(f"[bold]Patterns to preserve:[/bold] {', '.join(patterns_list)}")

        # Create service and perform abstraction
        service = GraphAbstractionService(driver)

        result = await service.abstract_tenant_graph(
            tenant_id=tenant_id,
            sample_size=sample_size,
            seed=seed,
            clear_existing=clear,
            preserve_security_patterns=preserve_security_patterns,
            security_patterns=patterns_list,
        )

        # Display results
        _display_results(result)

    finally:
        if driver:
            driver.close()


def _display_results(result: Dict[str, Any]) -> None:
    """Display abstraction results with security metrics.

    Args:
        result: Abstraction result dictionary
    """
    console.print("\n[bold green]✓ Abstraction Complete[/bold green]\n")

    # Summary
    console.print("[bold]Summary:[/bold]")
    console.print(f"  Tenant ID: {result['tenant_id']}")
    console.print(f"  Target Size: {result['target_size']}")

    # Show base vs final size if security augmentation was used
    if "base_sample_size" in result and result.get("security_metrics"):
        console.print(f"  Base Sample: {result['base_sample_size']}")
        console.print(f"  Final Size: [bold]{result['actual_size']}[/bold]")
        overhead = result["actual_size"] - result["base_sample_size"]
        overhead_pct = (overhead / result["base_sample_size"] * 100) if result["base_sample_size"] > 0 else 0
        console.print(f"  Security Overhead: [cyan]+{overhead} nodes ({overhead_pct:.1f}%)[/cyan]")
    else:
        console.print(f"  Actual Size: [bold]{result['actual_size']}[/bold]")

    size_delta_pct = (
        abs(result["actual_size"] - result["target_size"]) / result["target_size"]
    )
    if size_delta_pct <= 0.10:
        console.print("  Size Match: [green]✓ Within tolerance (±10%)[/green]")
    else:
        console.print(
            f"  Size Match: [yellow]⚠ Outside tolerance ({size_delta_pct:.1%})[/yellow]"
        )

    # Security metrics (if enabled)
    if result.get("security_metrics"):
        console.print("\n[bold]Security Pattern Preservation:[/bold]")
        security_metrics = result["security_metrics"]

        for pattern_name, count in security_metrics["patterns_preserved"].items():
            coverage = security_metrics["coverage_percentages"][pattern_name]
            color = "green" if coverage >= 90.0 else "yellow" if coverage >= 70.0 else "red"
            console.print(f"  {pattern_name}: {count} instances ([{color}]{coverage:.1f}% coverage[/{color}])")

        added = security_metrics["nodes_added_for_security"]
        console.print(f"\n  [bold]Nodes added for security:[/bold] {added}")

    # Type distribution table
    console.print("\n[bold]Resource Type Distribution:[/bold]")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Resource Type", style="cyan")
    table.add_column("Count", justify="right", style="green")
    table.add_column("Percentage", justify="right")

    total = result["actual_size"]
    type_dist = result["type_distribution"]

    # Sort by count descending
    sorted_types = sorted(type_dist.items(), key=lambda x: x[1], reverse=True)

    for resource_type, count in sorted_types:
        percentage = (count / total * 100) if total > 0 else 0
        table.add_row(resource_type, str(count), f"{percentage:.1f}%")

    console.print(table)

    # Next steps
    console.print("\n[bold]Next Steps:[/bold]")
    console.print("  1. Visualize: [cyan]atg visualize[/cyan]")
    console.print("  2. Query in Neo4j Browser:")
    console.print("     [dim]MATCH (s:Resource)-[:SAMPLE_OF]->(o:Resource)")
    console.print(f"     WHERE o.tenant_id = '{result['tenant_id']}'")
    console.print("     RETURN s, o LIMIT 100[/dim]")
    console.print("  3. Generate IaC from abstraction:")
    console.print(
        f"     [cyan]atg generate-iac --tenant-id {result['tenant_id']}[/cyan]"
    )
