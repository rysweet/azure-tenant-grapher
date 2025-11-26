"""Graph visualization command.

This module provides the 'visualize' command for generating
interactive HTML visualizations from Neo4j graph data.

Issue #482: CLI Modularization
"""

import os
import sys
import time
from datetime import datetime
from typing import Optional

import click

from src.commands.base import async_command
from src.config_manager import create_neo4j_config_from_env, setup_logging
from src.graph_visualizer import GraphVisualizer
from src.utils.neo4j_startup import ensure_neo4j_running


@click.command("visualize")
@click.option(
    "--link-hierarchy/--no-link-hierarchy",
    default=False,
    help="Enable Resource->Subscription->Tenant hierarchical edges.",
)
@click.option(
    "--no-container",
    is_flag=True,
    help="Do not auto-start Neo4j container",
)
@click.option(
    "--output",
    type=str,
    default=None,
    help="Custom output path for the visualization",
)
@click.pass_context
@async_command
async def visualize(
    ctx: click.Context,
    link_hierarchy: bool = True,
    no_container: bool = False,
    output: Optional[str] = None,
) -> None:
    """Generate graph visualization from existing Neo4j data (no tenant-id required)."""
    await visualize_command_handler(ctx, link_hierarchy, no_container, output)


async def visualize_command_handler(
    ctx: click.Context,
    link_hierarchy: bool = True,
    no_container: bool = False,
    output: Optional[str] = None,
) -> None:
    """Handle the visualize command logic."""
    ensure_neo4j_running()

    # Determine output path
    effective_output = ""
    if output and output.strip():
        effective_output = output
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        effective_output = os.path.join(
            "outputs", f"azure_graph_visualization_{ts}.html"
        )

    try:
        # Create configuration (Neo4j-only)
        config = create_neo4j_config_from_env()
        config.logging.level = ctx.obj["log_level"]

        # Setup logging
        setup_logging(config.logging)

        # Ensure outputs/ dir exists for default
        os.makedirs("outputs", exist_ok=True)

        # Create visualizer
        visualizer = GraphVisualizer(
            config.neo4j.uri or "", config.neo4j.user, config.neo4j.password
        )

        click.echo("Generating graph visualization...")

        try:
            # Default HTML output under outputs/ if not specified
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            effective_output = os.path.join(
                "outputs", f"azure_graph_visualization_{ts}.html"
            )
            if output and output.strip():
                effective_output = output
            viz_path = visualizer.generate_html_visualization(
                output_path=effective_output, link_to_hierarchy=link_hierarchy
            )
            click.echo(f"Visualization saved to: {viz_path}")
        except Exception as e:
            click.echo(
                f"Failed to connect to Neo4j: {e}\n"
                "Action: Ensure Neo4j is running and accessible at the configured URI.\n"
                "If using Docker, check that the container is started and healthy.\n"
                "You can start the container with 'python scripts/cli.py container' or 'docker-compose up'.",
                err=True,
            )
            if not no_container:
                click.echo("Attempting to start Neo4j container...")
                try:
                    ensure_neo4j_running()
                    click.echo(
                        "Neo4j container started successfully, retrying visualization..."
                    )
                    for _i in range(10):
                        try:
                            viz_path = visualizer.generate_html_visualization(
                                output_path=effective_output,
                                link_to_hierarchy=link_hierarchy,
                            )
                            click.echo(f"Visualization saved to: {viz_path}")
                            break
                        except Exception:
                            time.sleep(3)
                    else:
                        click.echo(
                            "Failed to connect to Neo4j after starting container.\n"
                            "Action: Check Docker logs and ensure the Neo4j container is healthy.",
                            err=True,
                        )
                        sys.exit(1)
                except Exception as e:
                    click.echo(
                        f"Failed to start Neo4j container: {e}\n"
                        "Action: Check Docker is running and you have permission to start containers.",
                        err=True,
                    )
                    sys.exit(1)
            else:
                click.echo(
                    "Neo4j is not running and --no-container was specified.\n"
                    "Action: Start Neo4j manually or remove --no-container to let the CLI manage it.",
                    err=True,
                )
                sys.exit(1)

    except Exception as e:
        click.echo(f"Failed to generate visualization: {e}", err=True)
        sys.exit(1)


# For backward compatibility
visualize_command = visualize

__all__ = ["visualize", "visualize_command", "visualize_command_handler"]
