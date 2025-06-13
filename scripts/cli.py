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
from typing import Any, Callable, Coroutine, Optional

from dotenv import load_dotenv

from src.rich_dashboard import RichDashboard

# Add the parent directory to the path for imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# Always load .env if present
load_dotenv()

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


class DashboardLogHandler(logging.Handler):
    def __init__(self, dashboard):
        super().__init__()
        self.dashboard = dashboard

    def emit(self, record):
        msg = self.format(record)
        if record.levelno >= logging.ERROR:
            self.dashboard.add_error(msg)
        elif record.levelno >= logging.INFO:
            self.dashboard.log_info(msg)


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
@click.option(
    "--tenant-id",
    required=False,
    help="Azure tenant ID (defaults to AZURE_TENANT_ID from .env)",
)
@click.option(
    "--resource-limit",
    type=int,
    help="Maximum number of resources to process (for testing)",
)
@click.option(
    "--max-llm-threads",
    type=int,
    default=5,
    help="Maximum number of parallel LLM threads (default: 5)",
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
    max_llm_threads: int,
    no_container: bool,
    generate_spec: bool,
    visualize: bool,
) -> None:
    """Build the complete Azure tenant graph with enhanced processing."""

    try:
        # Use tenant_id from CLI or .env
        effective_tenant_id = tenant_id or os.environ.get("AZURE_TENANT_ID")
        if not effective_tenant_id:
            click.echo(
                "❌ No tenant ID provided and AZURE_TENANT_ID not set in environment.",
                err=True,
            )
            sys.exit(1)
        # Create and validate configuration
        config = create_config_from_env(effective_tenant_id, resource_limit)
        config.processing.batch_size = max_llm_threads  # For backward compatibility
        config.processing.auto_start_container = not no_container
        config.logging.level = ctx.obj["log_level"]

        # Setup logging
        setup_logging(config.logging)

        # Validate configuration
        config.validate_all()

        logger = logging.getLogger(__name__)

        # Create and run the grapher
        grapher = AzureTenantGrapher(config)

        # Setup RichDashboard
        dashboard = RichDashboard(
            config=config.to_dict(),
            batch_size=max_llm_threads,
            total_threads=max_llm_threads,
        )

        # Ensure Neo4j connection is established before using grapher.driver
        try:
            grapher.connect_to_neo4j()
        except Exception as e:
            dashboard.add_error(f"❌ Failed to connect to Neo4j: {e}")
            click.echo(f"❌ Failed to connect to Neo4j: {e}", err=True)
            sys.exit(1)

        logger.info("🚀 Starting Azure Tenant Graph building...")

        # Run the dashboard live while building the graph
        # Run the graph build and update the dashboard synchronously
        # Define a progress callback for the dashboard
        def progress_callback(**kwargs):
            dashboard.update_progress(**kwargs)

        # Patch logging to send INFO/ERROR to dashboard
        log_handler = DashboardLogHandler(dashboard)
        log_handler.setFormatter(
            logging.Formatter("%(levelname)s:%(name)s:%(message)s")
        )
        logging.getLogger().addHandler(log_handler)

        # Run the graph build and update the dashboard live
        with dashboard.live():
            result = await grapher.build_graph(progress_callback=progress_callback)
            # Final summary after build completes
            dashboard.update_progress(
                batch=1,
                total_batches=1,
                processed=result.get("total_resources", 0),
                total=result.get("total_resources", 0),
                successful=result.get("successful_resources", 0),
                failed=result.get("failed_resources", 0),
                skipped=result.get("skipped_resources", 0),
                llm_generated=result.get("llm_descriptions_generated", 0),
                llm_skipped=0,
            )
            if not result.get("success", True):
                dashboard.add_error(result.get("error", "Unknown error"))
            else:
                dashboard.add_error("🎉 Graph building completed successfully!")
                dashboard.add_error(
                    f"📊 Subscriptions: {result.get('subscriptions', 0)}"
                )
                dashboard.add_error(
                    f"📊 Total Resources: {result.get('total_resources', 0)}"
                )
                dashboard.add_error(
                    f"✅ Successful: {result.get('successful_resources', 0)}"
                )
                dashboard.add_error(f"❌ Failed: {result.get('failed_resources', 0)}")
                if "skipped_resources" in result:
                    dashboard.add_error(f"⏭️ Skipped: {result['skipped_resources']}")
                if "llm_descriptions_generated" in result:
                    dashboard.add_error(
                        f"🤖 LLM Descriptions: {result['llm_descriptions_generated']}"
                    )
                dashboard.add_error(
                    f"   - Success Rate: {result.get('success_rate', 0):.1f}%"
                )
        return  # Prevent further code from referencing result outside the dashboard

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
@click.option(
    "--tenant-id",
    required=False,
    help="Azure tenant ID (defaults to AZURE_TENANT_ID from .env)",
)
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

    effective_tenant_id = tenant_id or os.environ.get("AZURE_TENANT_ID")
    if not effective_tenant_id:
        click.echo(
            "❌ No tenant ID provided and AZURE_TENANT_ID not set in environment.",
            err=True,
        )
        sys.exit(1)

    click.echo(f"🧪 Running test mode with up to {limit} resources...")

    ctx.invoke(
        build,
        tenant_id=effective_tenant_id,
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
@click.option(
    "--tenant-id",
    required=False,
    help="Azure tenant ID (defaults to AZURE_TENANT_ID from .env)",
)
@click.pass_context
@async_command
async def spec(ctx: click.Context, tenant_id: str) -> None:
    """Generate only the tenant specification (requires existing graph)."""

    effective_tenant_id = tenant_id or os.environ.get("AZURE_TENANT_ID")
    if not effective_tenant_id:
        click.echo(
            "❌ No tenant ID provided and AZURE_TENANT_ID not set in environment.",
            err=True,
        )
        sys.exit(1)

    try:
        # Create configuration
        config = create_config_from_env(effective_tenant_id)
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
@click.option(
    "--link-hierarchy/--no-link-hierarchy",
    default=False,
    help="Enable Resource→Subscription→Tenant hierarchical edges.",
)
@click.option(
    "--no-container",
    is_flag=True,
    help="Do not auto-start Neo4j container",
)
@click.pass_context
@async_command
async def visualize(
    ctx: click.Context, link_hierarchy: bool, no_container: bool
) -> None:
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

        try:
            viz_path = visualizer.generate_html_visualization(
                link_to_hierarchy=link_hierarchy
            )
            click.echo(f"✅ Visualization saved to: {viz_path}")
        except Exception as e:
            click.echo(f"⚠️  Failed to connect to Neo4j: {e}", err=True)
            if not no_container:
                click.echo("🔄 Attempting to start Neo4j container...")
                container_manager = Neo4jContainerManager()
                if container_manager.setup_neo4j():
                    click.echo(
                        "✅ Neo4j container started successfully, retrying visualization..."
                    )
                    import time

                    for _i in range(10):
                        try:
                            viz_path = visualizer.generate_html_visualization(
                                link_to_hierarchy=link_hierarchy
                            )
                            click.echo(f"✅ Visualization saved to: {viz_path}")
                            break
                        except Exception:
                            time.sleep(3)
                    else:
                        click.echo(
                            "❌ Failed to connect to Neo4j after starting container.",
                            err=True,
                        )
                        sys.exit(1)
                else:
                    click.echo("❌ Failed to start Neo4j container", err=True)
                    sys.exit(1)
            else:
                click.echo(
                    "❌ Neo4j is not running and --no-container was specified.",
                    err=True,
                )
                sys.exit(1)

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
    cli()  # type: ignore[reportCallIssue]


if __name__ == "__main__":
    main()
