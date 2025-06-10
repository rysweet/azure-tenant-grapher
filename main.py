#!/usr/bin/env python3
"""
Azure Tenant Grapher CLI

Command-line interface for the Azure Tenant Grapher tool.
"""

import asyncio
import os
import sys

import click

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from src.azure_tenant_grapher import AzureTenantGrapher
from src.config_manager import create_config_from_env, setup_logging
from src.container_manager import Neo4jContainerManager
from src.graph_visualizer import GraphVisualizer


@click.command()
@click.option("--tenant-id", required=True, help="Azure tenant ID")
@click.option(
    "--resource-limit",
    type=int,
    help="Maximum number of resources to process (for testing)",
)
@click.option(
    "--batch-size",
    type=int,
    default=5,
    help="Number of resources to process in parallel (default: 5)",
)
@click.option("--no-container", is_flag=True, help="Do not auto-start Neo4j container")
@click.option(
    "--container-only", is_flag=True, help="Only start Neo4j container and exit"
)
@click.option(
    "--visualize", is_flag=True, help="Generate graph visualization after building"
)
@click.option(
    "--generate-spec", is_flag=True, help="Generate tenant specification after building"
)
@click.option(
    "--log-level", default="INFO", help="Logging level (DEBUG, INFO, WARNING, ERROR)"
)
async def main(
    tenant_id: str,
    resource_limit: int,
    batch_size: int,
    no_container: bool,
    container_only: bool,
    visualize: bool,
    generate_spec: bool,
    log_level: str,
) -> None:
    """Azure Tenant Grapher - Build a Neo4j graph of Azure tenant resources."""

    # Create configuration
    try:
        config = create_config_from_env(tenant_id, resource_limit)

        # Override configuration with CLI arguments
        if no_container:
            config.processing.auto_start_container = False
        config.processing.batch_size = batch_size
        config.logging.level = log_level.upper()

        # Setup logging
        setup_logging(config.logging)

        # Validate configuration
        config.validate_all()

        import logging

        logger = logging.getLogger(__name__)

    except Exception as e:
        click.echo(f"❌ Configuration error: {e}", err=True)
        return

    # Handle container-only mode
    if container_only:
        container_manager = Neo4jContainerManager()
        if container_manager.setup_neo4j():
            click.echo("✅ Neo4j container started successfully")
        else:
            click.echo("❌ Failed to start Neo4j container", err=True)
        return

    # Create and run the grapher
    try:
        grapher = AzureTenantGrapher(config)

        logger.info("🏁 Starting Azure Tenant Graph building...")
        result = await grapher.build_graph()

        if result.get("success", False):
            logger.info("🎉 Graph building completed successfully!")
            logger.info("📊 Final Summary:")
            logger.info(f"   - Subscriptions: {result.get('subscriptions', 0)}")
            logger.info(f"   - Total Resources: {result.get('total_resources', 0)}")
            logger.info(f"   - Successful: {result.get('successful_resources', 0)}")
            logger.info(f"   - Failed: {result.get('failed_resources', 0)}")
            if "skipped_resources" in result:
                logger.info(f"   - Skipped: {result['skipped_resources']}")
            if "llm_descriptions_generated" in result:
                logger.info(
                    f"   - LLM Descriptions: {result['llm_descriptions_generated']}"
                )
            logger.info(f"   - Success Rate: {result.get('success_rate', 0):.1f}%")

            # Generate visualization if requested
            if visualize:
                try:
                    logger.info("🎨 Generating graph visualization...")
                    visualizer = GraphVisualizer(
                        config.neo4j.uri, config.neo4j.user, config.neo4j.password
                    )
                    viz_path = visualizer.generate_html_visualization()
                    logger.info(f"✅ Visualization saved to: {viz_path}")
                except Exception as e:
                    logger.error(f"❌ Failed to generate visualization: {e}")

            # Generate tenant specification if requested and LLM is available
            if generate_spec and config.azure_openai.is_configured():
                try:
                    logger.info("📋 Generating tenant specification...")
                    await grapher.generate_tenant_specification()
                except Exception as e:
                    logger.error(f"❌ Failed to generate tenant specification: {e}")
            elif generate_spec:
                logger.warning(
                    "⚠️ Tenant specification requires Azure OpenAI configuration"
                )
        else:
            logger.error(
                f"❌ Graph building failed: {result.get('error', 'Unknown error')}"
            )

    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
