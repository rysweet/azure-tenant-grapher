"""CLI handler for Infrastructure-as-Code generation commands.

This module provides the command handler for IaC generation functionality
in the Azure Tenant Grapher CLI.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from neo4j import Driver  # type: ignore

from ..config_manager import create_neo4j_config_from_env
from ..utils.session_manager import create_session_manager
from .emitters import get_emitter
from .engine import TransformationEngine
from .traverser import GraphTraverser

logger = logging.getLogger(__name__)


def get_neo4j_driver_from_config() -> Driver:
    """Get Neo4j driver from configuration."""
    config = create_neo4j_config_from_env()
    manager = create_session_manager(config.neo4j)
    manager.connect()
    # pyright: ignore[reportPrivateUsage]
    if manager._driver is None:  # pyright: ignore[reportPrivateUsage]
        raise RuntimeError("Neo4j driver is not initialized")
    return manager._driver  # pyright: ignore[reportPrivateUsage]  # Driver object (protected access intentional)


def default_timestamped_dir() -> Path:
    """Create default timestamped output directory."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(f"./iac-out-{timestamp}")


async def generate_iac_command_handler(
    tenant_id: Optional[str] = None,
    format_type: str = "terraform",
    output_path: Optional[str] = None,
    rules_file: Optional[str] = None,
    dry_run: bool = False,
    resource_filters: Optional[str] = None,
) -> int:
    """Handle the generate-iac CLI command.

    Args:
        tenant_id: Azure tenant ID to process
        format_type: Target IaC format (terraform, arm, bicep)
        output_path: Output directory for generated templates
        rules_file: Path to transformation rules configuration file
        dry_run: If True, only validate inputs without generating templates
        resource_filters: Optional resource type filters

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        logger.info("🏗️ Starting IaC generation")
        logger.info(f"Format: {format_type}")

        # Get Neo4j driver
        driver = get_neo4j_driver_from_config()

        # Create GraphTraverser
        traverser = GraphTraverser(driver, [])

        # Build filter if provided
        filter_cypher = None
        if resource_filters:
            # Convert comma-separated filters to Cypher WHERE clause
            filters = [f.strip() for f in resource_filters.split(",")]
            filter_conditions = [f"r.type = '{f}'" for f in filters]
            filter_cypher = f"""
            MATCH (r:Resource)
            WHERE {' OR '.join(filter_conditions)}
            OPTIONAL MATCH (r)-[rel]->(t:Resource)
            RETURN r, collect({{type:type(rel), target:t.id}}) AS rels
            """

        # Traverse graph
        graph = await traverser.traverse(filter_cypher)
        logger.info(f"Extracted {len(graph.resources)} resources")

        # Apply transformations
        engine = TransformationEngine(rules_file)
        graph.resources = [engine.apply(r) for r in graph.resources]

        # Handle dry run
        if dry_run:
            sample_resources = graph.resources[:5]  # Show first 5 resources
            output_data = {
                "resources": sample_resources,
                "total_count": len(graph.resources),
                "format": format_type,
            }
            click.echo(json.dumps(output_data, indent=2, default=str))
            return 0

        # Get emitter
        emitter_cls = get_emitter(format_type)
        emitter = emitter_cls()

        # Determine output directory
        if output_path:
            out_dir = Path(output_path)
        else:
            out_dir = default_timestamped_dir()

        # Generate templates
        paths = emitter.emit(graph, out_dir)

        click.echo(f"✅ Wrote {len(paths)} files to {paths[0].parent}")
        for path in paths:
            click.echo(f"  📄 {path}")

        return 0

    except Exception as e:
        logger.error(f"❌ IaC generation failed: {e}")
        click.echo(f"❌ Error: {e}", err=True)
        return 1
