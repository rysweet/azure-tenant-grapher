#!/usr/bin/env python3
"""
Enhanced CLI wrapper for Azure Tenant Grapher

This script provides an improved command-line interface with better error handling,
configuration validation, and progress tracking.
"""

import asyncio
import functools
import logging
import os
import sys

# Add the parent directory to the path for imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

try:
    import click

    from src.azure_tenant_grapher import AzureTenantGrapher
    from src.config_manager import (
        create_config_from_env,
        create_neo4j_config_from_env,
        setup_logging,
    )
    from src.container_manager import Neo4jContainerManager
    from src.graph_visualizer import GraphVisualizer
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Please ensure all required packages are installed:")
    print("pip install -r requirements.txt")
    sys.exit(1)


from typing import Any, Callable, Coroutine, Optional


def async_command(f: Callable[..., Coroutine[Any, Any, Any]]) -> Callable[..., Any]:
    """Decorator to make Click commands async-compatible."""

    @functools.wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return asyncio.run(f(*args, **kwargs))

    return wrapper


@click.group()
@click.option(
    "--log-level",
    default="INFO",
    help="Logging level (DEBUG, INFO, WARNING, ERROR)",
)
@click.pass_context
def cli(ctx: click.Context, log_level: str) -> None:
    """Azure Tenant Grapher - Enhanced CLI for building Neo4j graphs of Azure resources."""
    ctx.ensure_object(dict)
    ctx.obj["log_level"] = log_level.upper()


@cli.command()
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
    "--generate-spec",
    is_flag=True,
    help="Generate tenant specification after graph building",
)
@click.option(
    "--visualize",
    is_flag=True,
    help="Generate graph visualization after building",
)
@click.pass_context
@async_command
async def build(
    ctx: click.Context,
    tenant_id: str,
    resource_limit: Optional[int],
    batch_size: int,
    no_container: bool,
    generate_spec: bool,
    visualize: bool,
) -> None:
    """Build the complete Azure tenant graph with enhanced processing."""

    try:
        # Create and validate configuration
        config = create_config_from_env(tenant_id, resource_limit)
        config.processing.batch_size = batch_size
        config.processing.auto_start_container = not no_container
        config.logging.level = ctx.obj["log_level"]

        # Setup logging
        setup_logging(config.logging)

        # Validate configuration
        config.validate_all()

        logger = logging.getLogger(__name__)

        # Create and run the grapher
        grapher = AzureTenantGrapher(config)

        logger.info("🚀 Starting Azure Tenant Graph building...")
        # --- ASYNC LLM SUMMARIZATION WITH RICH LIVE PANEL ---
        import time

        from rich.live import Live
        from rich.table import Table

        # Discover resources
        all_resources = []
        subscriptions = await grapher.discover_subscriptions()
        with grapher.driver.session() as session:
            for subscription in subscriptions:
                resources = await grapher.discover_resources_in_subscription(
                    subscription["id"]
                )
                all_resources.extend(resources)

            # Prepare and run async LLM summary pool
            counters, counters_lock = (
                grapher.process_resources_async_llm_with_adaptive_pool(
                    all_resources, session, max_workers=10, min_workers=1
                )
            )

            def make_table():
                table = Table(title="LLM Summarization Progress", expand=True)
                table.add_column("Metric", style="bold cyan")
                table.add_column("Count", style="bold magenta")
                with counters_lock:
                    table.add_row("Total Resources", str(counters.get("total", 0)))
                    table.add_row("Inserted in Graph", str(counters.get("inserted", 0)))
                    table.add_row(
                        "LLM Summaries Generated", str(counters.get("llm_generated", 0))
                    )
                    table.add_row(
                        "Summaries In-Flight", str(counters.get("in_flight", 0))
                    )
                    table.add_row(
                        "Summaries Remaining", str(counters.get("remaining", 0))
                    )
                    table.add_row("Throttled Events", str(counters.get("throttled", 0)))
                return table

            with Live(make_table(), refresh_per_second=1, transient=True) as live:
                while True:
                    live.update(make_table())
                    with counters_lock:
                        if counters["remaining"] <= 0 and counters["in_flight"] == 0:
                            break
                    time.sleep(1)
        # --- END RICH LIVE PANEL ---
        result = await grapher.build_graph()

        if result.get("success", False):
            click.echo("🎉 Graph building completed successfully!")
            click.echo("📊 Summary:")
            click.echo(f"   - Subscriptions: {result.get('subscriptions', 0)}")
            click.echo(f"   - Total Resources: {result.get('total_resources', 0)}")
            click.echo(f"   - Successful: {result.get('successful_resources', 0)}")
            click.echo(f"   - Failed: {result.get('failed_resources', 0)}")

            if "skipped_resources" in result:
                click.echo(f"   - Skipped: {result['skipped_resources']}")
            if "llm_descriptions_generated" in result:
                click.echo(
                    f"   - LLM Descriptions: {result['llm_descriptions_generated']}"
                )

            click.echo(f"   - Success Rate: {result.get('success_rate', 0):.1f}%")

            # Generate visualization if requested
            if visualize:
                try:
                    click.echo("🎨 Generating graph visualization...")
                    visualizer = GraphVisualizer(
                        config.neo4j.uri, config.neo4j.user, config.neo4j.password
                    )
                    viz_path = visualizer.generate_html_visualization()
                    click.echo(f"✅ Visualization saved to: {viz_path}")
                except Exception as e:
                    click.echo(f"❌ Failed to generate visualization: {e}", err=True)

            # Generate tenant specification if requested and LLM is available
            if generate_spec and config.azure_openai.is_configured():
                try:
                    click.echo("📋 Generating tenant specification...")
                    await grapher.generate_tenant_specification()
                    click.echo("✅ Tenant specification generated successfully")
                except Exception as e:
                    click.echo(
                        f"❌ Failed to generate tenant specification: {e}", err=True
                    )
            elif generate_spec:
                click.echo(
                    "⚠️ Tenant specification requires Azure OpenAI configuration",
                    err=True,
                )
        else:
            click.echo(
                f"❌ Graph building failed: {result.get('error', 'Unknown error')}",
                err=True,
            )
            sys.exit(1)

    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--tenant-id", required=True, help="Azure tenant ID")
@click.option(
    "--limit",
    type=int,
    default=50,
    help="Maximum number of resources to process (default: 50)",
)
@click.pass_context
@async_command
async def test(ctx: click.Context, tenant_id: str, limit: int) -> None:
    """Run a test with limited resources to validate setup."""

    click.echo(f"🧪 Running test mode with up to {limit} resources...")

    ctx.invoke(
        build,
        tenant_id=tenant_id,
        resource_limit=limit,
        batch_size=3,
        no_container=False,
        generate_spec=False,
        visualize=False,
    )


@cli.command()
def container() -> None:
    """Manage Neo4j container."""

    @click.group()
    def container_group() -> None:
        pass

    @container_group.command()
    def start() -> None:
        """Start Neo4j container."""
        container_manager = Neo4jContainerManager()
        if container_manager.setup_neo4j():
            click.echo("✅ Neo4j container started successfully")
        else:
            click.echo("❌ Failed to start Neo4j container", err=True)
            sys.exit(1)

    @container_group.command()
    def stop() -> None:
        """Stop Neo4j container."""
        container_manager = Neo4jContainerManager()
        if container_manager.stop_neo4j_container():
            click.echo("✅ Neo4j container stopped successfully")
        else:
            click.echo("❌ Failed to stop Neo4j container", err=True)
            sys.exit(1)

    @container_group.command()
    def status() -> None:
        """Check Neo4j container status."""
        container_manager = Neo4jContainerManager()
        if container_manager.is_neo4j_container_running():
            click.echo("✅ Neo4j container is running")
        else:
            click.echo("⏹️ Neo4j container is not running")

    pass


@cli.command()
@click.option("--tenant-id", required=True, help="Azure tenant ID")
@click.pass_context
@async_command
async def spec(ctx: click.Context, tenant_id: str) -> None:
    """Generate only the tenant specification (requires existing graph)."""

    try:
        # Create configuration
        config = create_config_from_env(tenant_id)
        config.logging.level = ctx.obj["log_level"]

        # Setup logging
        setup_logging(config.logging)

        # Validate Azure OpenAI configuration
        if not config.azure_openai.is_configured():
            click.echo(
                "❌ Azure OpenAI not configured. Tenant specification requires LLM capabilities.",
                err=True,
            )
            sys.exit(1)

        # Create grapher and generate specification
        grapher = AzureTenantGrapher(config)

        click.echo("📋 Generating tenant specification from existing graph...")
        await grapher.generate_tenant_specification()
        click.echo("✅ Tenant specification generated successfully")

    except Exception as e:
        click.echo(f"❌ Failed to generate specification: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
@async_command
async def visualize(ctx: click.Context) -> None:
    """Generate graph visualization from existing Neo4j data (no tenant-id required)."""

    try:
        # Create configuration (Neo4j-only)
        config = create_neo4j_config_from_env()
        config.logging.level = ctx.obj["log_level"]

        # Setup logging
        setup_logging(config.logging)

        # Create visualizer
        visualizer = GraphVisualizer(
            config.neo4j.uri, config.neo4j.user, config.neo4j.password
        )

        click.echo("🎨 Generating graph visualization...")
        viz_path = visualizer.generate_html_visualization()
        click.echo(f"✅ Visualization saved to: {viz_path}")

    except Exception as e:
        click.echo(f"❌ Failed to generate visualization: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--limit", type=int, default=None, help="Resource limit (overrides config)"
)
@click.option("--output", type=str, default=None, help="Custom output path")
@click.pass_context
def generate_spec(
    ctx: click.Context, limit: Optional[int], output: Optional[str]
) -> None:
    """Generate anonymized tenant Markdown specification (no tenant-id required)."""
    try:
        from src.config_manager import create_neo4j_config_from_env, setup_logging
        from src.tenant_spec_generator import (
            ResourceAnonymizer,
            TenantSpecificationGenerator,
        )

        # Load config (Neo4j-only)
        config = create_neo4j_config_from_env()
        config.logging.level = ctx.obj["log_level"]
        setup_logging(config.logging)

        # Neo4j connection info
        neo4j_uri = config.neo4j.uri
        neo4j_user = config.neo4j.user
        neo4j_password = config.neo4j.password

        # Spec config
        spec_config = config.specification
        if limit is not None:
            spec_config.resource_limit = limit

        # Anonymizer
        anonymizer = ResourceAnonymizer(seed=spec_config.anonymization_seed)

        # Generator
        generator = TenantSpecificationGenerator(
            neo4j_uri, neo4j_user, neo4j_password, anonymizer, spec_config
        )

        # Generate spec
        output_path = generator.generate_specification(output_path=output)
        click.echo(f"✅ Tenant Markdown specification generated: {output_path}")

    except Exception as e:
        import traceback

        click.echo(f"❌ Failed to generate tenant specification: {e}", err=True)
        traceback.print_exc()
        sys.exit(1)


@cli.command()
def config() -> None:
    """Show current configuration (without sensitive data)."""

    try:
        # Create dummy configuration to show structure
        config = create_config_from_env("example-tenant-id")

        click.echo("🔧 Current Configuration Template:")
        click.echo("=" * 60)

        config_dict = config.to_dict()

        def print_dict(d: Any, indent: int = 0) -> None:
            for key, value in d.items():
                if isinstance(value, dict):
                    click.echo("  " * indent + f"{key}:")
                    print_dict(value, indent + 1)
                else:
                    click.echo("  " * indent + f"{key}: {value}")

        print_dict(config_dict)
        click.echo("=" * 60)
        click.echo("💡 Set environment variables to customize configuration")

    except Exception as e:
        click.echo(f"❌ Failed to display configuration: {e}", err=True)


@cli.command()
@click.pass_context
@async_command
async def progress(ctx: click.Context) -> None:
    """Check processing progress in the database (no tenant-id required)."""

    try:
        # Import and run the progress checker
        from scripts.check_progress import main as check_progress_main

        config = create_neo4j_config_from_env()
        config.logging.level = ctx.obj["log_level"]
        setup_logging(config.logging)

        click.echo("📊 Checking processing progress...")
        check_progress_main()

    except ImportError:
        click.echo("❌ Progress checker not available", err=True)
    except Exception as e:
        click.echo(f"❌ Failed to check progress: {e}", err=True)


def main() -> None:
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
