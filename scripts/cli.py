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
from rich.logging import RichHandler
from rich.style import Style

from src.rich_dashboard import RichDashboard


class GreenInfoRichHandler(RichHandler):
    def get_level_style(self, level_name: str) -> Style:
        """Override log level colors for better readability."""
        if level_name == "INFO":
            return Style(color="blue", bold=True)
        if level_name == "DEBUG":
            return Style(color="white", dim=True)
        if level_name == "WARNING":
            return Style(color="yellow", bold=True)
        if level_name == "ERROR":
            return Style(color="red", bold=True)
        if level_name == "CRITICAL":
            return Style(color="red", bold=True, reverse=True)
        # Fallback for other levels
        return Style(color="cyan")


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
        # Always show all logs, color by level
        if record.levelno >= logging.ERROR:
            self.dashboard.add_error(msg)
        elif record.levelno >= logging.WARNING:
            with self.dashboard.lock:
                self.dashboard.log_widget.add_line(msg, "red", "warning")
                self.dashboard.layout["logs"].update(self.dashboard._render_log_panel())
        elif record.levelno >= logging.INFO:
            self.dashboard.log_info(msg)
        else:
            with self.dashboard.lock:
                self.dashboard.log_widget.add_line(msg, "white", "debug")
                self.dashboard.layout["logs"].update(self.dashboard._render_log_panel())


def async_command(f: Callable[..., Coroutine[Any, Any, Any]]) -> Callable[..., Any]:
    """Decorator to make Click commands async-compatible."""

    @functools.wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return asyncio.run(f(*args, **kwargs))

    return wrapper


def show_comprehensive_help(ctx: click.Context) -> None:
    """Show comprehensive help for all commands."""
    click.echo("🚀 Azure Tenant Grapher - Enhanced CLI")
    click.echo("=" * 60)
    click.echo()

    # Show main help
    click.echo(ctx.get_help())
    click.echo()

    # Show command descriptions
    commands_info = {
        "build": "🏗️  Build Azure tenant graph with optional dashboard interface",
        "test": "🧪 Run quick test with limited resources to validate setup",
        "visualize": "🎨 Generate interactive HTML visualization from existing graph",
        "spec": "📋 Generate tenant specification document from existing graph",
        "generate-spec": "📄 Generate anonymized tenant specification (standalone)",
        "config": "⚙️  Show current configuration template",
        "progress": "📊 Check processing progress in the database",
        "container": "🐳 Manage Neo4j Docker container",
    }

    click.echo("📚 COMMAND DESCRIPTIONS:")
    click.echo("=" * 60)

    for cmd_name, description in commands_info.items():
        click.echo(f"\n{description}")
        click.echo(f"Usage: {ctx.info_name} {cmd_name} [OPTIONS]")
        click.echo(f"Help:  {ctx.info_name} {cmd_name} --help")

    click.echo()
    click.echo("💡 QUICK START EXAMPLES:")
    click.echo("=" * 60)
    click.echo("  # Build graph with dashboard (default)")
    click.echo("  python scripts/cli.py build")
    click.echo()
    click.echo("  # Build graph without dashboard (line-by-line logs)")
    click.echo("  python scripts/cli.py build --no-dashboard --log-level DEBUG")
    click.echo()
    click.echo("  # Test with limited resources")
    click.echo("  python scripts/cli.py test --limit 20")
    click.echo()
    click.echo("  # Generate visualization from existing data")
    click.echo("  python scripts/cli.py visualize")
    click.echo()
    click.echo("  # Check processing progress")
    click.echo("  python scripts/cli.py progress")
    click.echo()
    click.echo("📖 For detailed help on any command, use: {command} --help")
    click.echo("🌐 Documentation: https://github.com/your-repo/azure-tenant-grapher")


@click.group(invoke_without_command=True)
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

    # If no command is provided, show comprehensive help
    if ctx.invoked_subcommand is None:
        show_comprehensive_help(ctx)


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
@click.option(
    "--no-dashboard",
    is_flag=True,
    help="Disable the Rich dashboard and emit logs line by line",
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
    no_dashboard: bool,
) -> None:
    """
    Build the complete Azure tenant graph with enhanced processing.

    By default, shows a live Rich dashboard with progress, logs, and interactive controls:
      - Press 'x' to exit the dashboard at any time.
      - Press 'i', 'd', or 'w' to set log level to INFO, DEBUG, or WARNING.

    Use --no-dashboard to disable the dashboard and emit logs line by line to the terminal.
    """

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

        if no_dashboard:
            # Standard logging, no dashboard
            root_logger = logging.getLogger()
            # Set log level from CLI or default to INFO
            cli_log_level = ctx.obj.get("log_level", "INFO").upper()
            level_map = {
                "DEBUG": logging.DEBUG,
                "INFO": logging.INFO,
                "WARNING": logging.WARNING,
                "ERROR": logging.ERROR,
            }
            root_logger.setLevel(level_map.get(cli_log_level, logging.INFO))
            root_logger.handlers.clear()
            handler = GreenInfoRichHandler(
                rich_tracebacks=True, show_time=True, show_level=True, show_path=False
            )
            handler.setLevel(level_map.get(cli_log_level, logging.INFO))
            root_logger.addHandler(handler)
            for name in logging.root.manager.loggerDict:
                logging.getLogger(name).setLevel(
                    level_map.get(cli_log_level, logging.INFO)
                )
            logging.info(
                f"Running in no-dashboard mode: logs will be emitted line by line. Log level: {cli_log_level}"
            )
            try:
                grapher.connect_to_neo4j()
            except Exception as e:
                click.echo(f"❌ Failed to connect to Neo4j: {e}", err=True)
                sys.exit(1)
            logger.info("🚀 Starting Azure Tenant Graph building...")
            result = await grapher.build_graph()
            click.echo("🎉 Graph building completed.")
            click.echo(f"Result: {result}")
            return
        else:
            # Setup RichDashboard
            dashboard = RichDashboard(
                config=config.to_dict(),
                batch_size=max_llm_threads,
                total_threads=max_llm_threads,
            )

            # Setup file logging to the dashboard's log file
            # Create file handler for logging to dashboard's timestamped file
            file_handler = logging.FileHandler(dashboard.log_file_path)
            file_handler.setFormatter(
                logging.Formatter("%(asctime)s - %(levelname)s:%(name)s:%(message)s")
            )
            file_handler.setLevel(logging.DEBUG)

            # Ensure Neo4j connection is established before using grapher.driver
            try:
                grapher.connect_to_neo4j()
            except Exception as e:
                dashboard.add_error(f"❌ Failed to connect to Neo4j: {e}")
                click.echo(f"❌ Failed to connect to Neo4j: {e}", err=True)
                sys.exit(1)

            logger.info("🚀 Starting Azure Tenant Graph building...")

            # Define a progress callback for the dashboard
            def progress_callback(**kwargs):
                dashboard.update_progress(**kwargs)

            # Patch logging to send INFO/ERROR to both dashboard and file
            dashboard_handler = DashboardLogHandler(dashboard)
            dashboard_handler.setFormatter(
                logging.Formatter("%(levelname)s:%(name)s:%(message)s")
            )

            root_logger = logging.getLogger()
            root_logger.setLevel(logging.DEBUG)
            root_logger.handlers.clear()

            # Add both dashboard and file handlers
            root_logger.addHandler(dashboard_handler)
            root_logger.addHandler(file_handler)

            # Set all known loggers to DEBUG
            for name in logging.root.manager.loggerDict:
                logging.getLogger(name).setLevel(logging.DEBUG)

            # Emit test log messages to verify handlers
            logging.debug("Test DEBUG log: dashboard and file handlers are active.")
            logging.info("Test INFO log: dashboard and file handlers are active.")
            logging.warning("Test WARNING log: dashboard and file handlers are active.")
            logging.error("Test ERROR log: dashboard and file handlers are active.")

            dashboard.log_info(
                f"📄 Logs are being written to: {dashboard.log_file_path}"
            )

            # Start the graph build concurrently before entering dashboard.live()
            build_task = asyncio.create_task(
                grapher.build_graph(progress_callback=progress_callback)
            )
            dashboard.set_processing(True)
            dashboard.log_info("Starting build...")  # Ensure user sees activity

            # Enter the dashboard live context so UI is immediately responsive
            try:
                async with dashboard.live():
                    dashboard.log_info("Press 'x' to exit the dashboard")
                    # Poll for build completion or user exit
                    while not build_task.done() and not dashboard.should_exit:
                        await asyncio.sleep(0.1)
                    if dashboard.should_exit and not build_task.done():
                        dashboard.add_error(
                            "Dashboard exited before build completed. Cancelling build..."
                        )
                        build_task.cancel()
                        try:
                            await build_task
                        except Exception:
                            pass
            except Exception as e:
                # If the dashboard was exited by user, suppress context manager errors
                if (
                    "'NoneType' object does not support the context manager protocol"
                    in str(e)
                ):
                    return
                raise

            # After dashboard context exits, await the build if still running
            if not build_task.done():
                try:
                    result = await build_task
                except Exception as build_e:
                    dashboard.set_processing(False)
                    dashboard.add_error(f"❌ Graph building failed: {build_e}")
                    # dashboard.layout.refresh()  # Not needed; Live auto-refreshes
                    raise
            else:
                result = build_task.result()

            dashboard.set_processing(False)
            dashboard.log_info("🎉 Graph building completed successfully!")
            dashboard.log_info(f"Result: {result}")
            # dashboard.layout.refresh()  # Not needed; Live auto-refreshes

            # Handle post-processing options (generate_spec, visualize) after build
            if generate_spec:
                dashboard.log_info("📋 Generating tenant specification...")
                try:
                    await grapher.generate_tenant_specification()
                    dashboard.log_info("✅ Tenant specification generated")
                    # dashboard.layout.refresh()  # Not needed; Live auto-refreshes
                except Exception as spec_e:
                    dashboard.add_error(
                        f"❌ Tenant specification generation failed: {spec_e}"
                    )
                    # dashboard.layout.refresh()  # Not needed; Live auto-refreshes

            if visualize:
                dashboard.log_info("🎨 Generating visualization...")
                try:
                    from src.graph_visualizer import GraphVisualizer

                    visualizer = GraphVisualizer(
                        config.neo4j.uri,
                        config.neo4j.user,
                        config.neo4j.password,
                    )
                    viz_path = visualizer.generate_html_visualization()
                    dashboard.log_info(f"✅ Visualization saved to: {viz_path}")
                    # dashboard.layout.refresh()  # Not needed; Live auto-refreshes
                except Exception as viz_e:
                    dashboard.add_error(f"⚠️ Visualization failed: {viz_e}")
                    # dashboard.layout.refresh()  # Not needed; Live auto-refreshes

            return  # Prevent further code from referencing result outside the dashboard

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
