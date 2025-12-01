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
    "--method",
    type=click.Choice(["stratified", "embedding"], case_sensitive=False),
    default="stratified",
    help="Sampling method: stratified (uniform) or embedding (importance-weighted)",
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
def abstract_graph(
    tenant_id: str, sample_size: int, method: str, seed: int | None, clear: bool
) -> None:
    """Create abstracted subset of Azure tenant graph.

    This command creates a smaller, representative subset of a large Azure
    tenant graph while preserving resource type distribution. The abstracted
    graph can be used for training simulations, testing, and demonstrations.

    Example:
        atg abstract-graph --tenant-id abc-123 --sample-size 100 --clear
        atg abstract-graph --tenant-id abc-123 --sample-size 100 --method embedding

    The command:
    1. Samples nodes using stratified or embedding-based sampling
    2. Preserves resource type distribution (±15%)
    3. Creates :SAMPLE_OF relationships linking samples to originals
    4. Displays statistics about the abstraction

    Sampling Methods:
    - stratified: Uniform sampling within each resource type (fast, 70%+ hub preservation)
    - embedding: Importance-weighted sampling using node2vec (slower, 70%+ hub preservation, better bridge preservation)

    \b
    Requirements:
    - Source tenant must be already scanned (use 'atg scan' first)
    - Neo4j must be running (started automatically)
    - Minimum 10 resources required in source graph
    """
    try:
        asyncio.run(_abstract_graph_async(tenant_id, sample_size, method, seed, clear))
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise click.Abort() from e


async def _abstract_graph_async(
    tenant_id: str, sample_size: int, method: str, seed: int | None, clear: bool
) -> None:
    """Async implementation of abstract-graph command."""
    # Ensure Neo4j is running
    container_manager = Neo4jContainerManager()
    await container_manager.ensure_neo4j_running()

    console.print(f"[bold]Creating abstraction for tenant:[/bold] {tenant_id}")
    console.print(f"[bold]Target sample size:[/bold] {sample_size}")
    console.print(f"[bold]Sampling method:[/bold] {method}")

    # Get Neo4j configuration from environment
    neo4j_uri = os.environ.get("NEO4J_URI")
    neo4j_password = os.environ.get("NEO4J_PASSWORD")

    if not neo4j_uri or not neo4j_password:
        console.print("[red]Error:[/red] NEO4J_URI and NEO4J_PASSWORD must be set")
        raise click.Abort()

    # Create Neo4j driver
    driver = GraphDatabase.driver(neo4j_uri, auth=("neo4j", neo4j_password))

    try:
        # Create service and perform abstraction
        service = GraphAbstractionService(driver, method=method)

        result = await service.abstract_tenant_graph(
            tenant_id=tenant_id,
            sample_size=sample_size,
            seed=seed,
            clear_existing=clear,
        )

        # Display results
        _display_results(result)

    finally:
        if driver:
            driver.close()


def _display_results(result: Dict[str, Any]) -> None:
    """Display abstraction results in a rich table.

    Args:
        result: Abstraction result dictionary
    """
    console.print("\n[bold green]✓ Abstraction Complete[/bold green]\n")

    # Summary
    console.print("[bold]Summary:[/bold]")
    console.print(f"  Tenant ID: {result['tenant_id']}")
    console.print(f"  Target Size: {result['target_size']}")
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
