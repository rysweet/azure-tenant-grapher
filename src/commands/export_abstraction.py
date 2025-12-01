"""Export Abstraction command.

Philosophy:
- Single responsibility: CLI interface only (thin wrapper over service)
- Ruthless simplicity: Delegate to GraphExportService
- Zero-BS implementation: Clear error messages, no stubs

Exports graph abstractions to visualization formats:
- GraphML (Gephi, Cytoscape, yEd)
- JSON (D3.js, custom visualization tools)
- DOT (Graphviz rendering)

Usage:
    atg export-abstraction --tenant-id abc-123 --output graph.graphml
    atg export-abstraction --output graph.json --format json
    atg export-abstraction --output graph.dot --format dot --no-relationships

Issue #508: MCP Server and Visualization Export Integration
"""

import sys
from pathlib import Path
from typing import Optional

import click

from src.commands.base import async_command, get_neo4j_config_from_env, get_tenant_id
from src.config_manager import LoggingConfig, Neo4jConfig, setup_logging
from src.services.graph_export_service import GraphExportService
from src.utils.session_manager import Neo4jSessionManager


@click.command("export-abstraction")
@click.option(
    "--tenant-id",
    required=False,
    help="Azure tenant ID (defaults to AZURE_TENANT_ID from .env)",
)
@click.option(
    "--output",
    required=True,
    type=click.Path(),
    help="Output file path (e.g., abstraction.graphml)",
)
@click.option(
    "--format",
    type=click.Choice(["graphml", "json", "dot"], case_sensitive=False),
    default="graphml",
    help="Export format (default: graphml)",
)
@click.option(
    "--no-relationships",
    is_flag=True,
    help="Export nodes only (no edges)",
)
@async_command
async def export_abstraction_command(
    tenant_id: Optional[str],
    output: str,
    format: str,
    no_relationships: bool,
) -> None:
    """Export graph abstraction to visualization format.

    Supported formats:
      - graphml: For Gephi, Cytoscape, yEd
      - json: For D3.js, custom visualization tools
      - dot: For Graphviz rendering

    Example:
        atg export-abstraction --tenant-id abc-123 --output graph.graphml
        atg export-abstraction --output graph.json --format json
        atg export-abstraction --output graph.dot --format dot --no-relationships
    """
    # Setup logging
    logging_config = LoggingConfig(level="INFO")
    setup_logging(logging_config)

    # Get tenant ID
    tenant_id_resolved = get_tenant_id(tenant_id)

    # Get Neo4j connection
    neo4j_uri, neo4j_user, neo4j_password = get_neo4j_config_from_env()

    click.echo(f"Exporting abstraction for tenant: {tenant_id_resolved}")
    click.echo(f"Format: {format}")
    click.echo(f"Output: {output}")

    try:
        # Connect to Neo4j
        neo4j_config = Neo4jConfig(
            uri=neo4j_uri, user=neo4j_user, password=neo4j_password
        )
        session_manager = Neo4jSessionManager(neo4j_config)
        session_manager.connect()

        # Export abstraction
        service = GraphExportService(session_manager)
        result = service.export_abstraction(
            tenant_id=tenant_id_resolved,
            output_path=Path(output),
            format=format,
            include_relationships=not no_relationships,
        )

        # Display results
        if result["success"]:
            click.echo("\nExport complete!")
            click.echo(f"  Nodes: {result['node_count']}")
            click.echo(f"  Edges: {result['edge_count']}")
            click.echo(f"  File: {result['output_path']}")

            # Format-specific usage tips
            if format == "graphml":
                click.echo("\nOpen in Gephi:")
                click.echo(f"  File → Open → {result['output_path']}")
            elif format == "json":
                click.echo("\nUse with D3.js:")
                click.echo(f"  d3.json('{result['output_path']}').then(data => ...)")
            elif format == "dot":
                click.echo("\nRender with Graphviz:")
                click.echo(f"  dot -Tpng {result['output_path']} -o graph.png")
        else:
            click.echo("Export failed", err=True)
            sys.exit(1)

    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


__all__ = ["export_abstraction_command"]
