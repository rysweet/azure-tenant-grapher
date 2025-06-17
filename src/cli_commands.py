"""
CLI Command Handlers

Contains the implementation of various CLI commands to keep the main CLI file focused.
"""

import asyncio
import logging
import os
import sys
from typing import TYPE_CHECKING, Optional

import click

from src.azure_tenant_grapher import AzureTenantGrapher
from src.cli_dashboard_manager import CLIDashboardManager
from src.config_manager import (
    create_config_from_env,
    create_neo4j_config_from_env,
    setup_logging,
)
from src.container_manager import Neo4jContainerManager
from src.graph_visualizer import GraphVisualizer
from src.rich_dashboard import RichDashboard

if TYPE_CHECKING:
    from src.config_manager import AzureTenantGrapherConfig


class DashboardLogHandler(logging.Handler):
    """Custom log handler that sends logs to the dashboard."""

    def __init__(self, dashboard: "RichDashboard") -> None:
        super().__init__()
        self.dashboard = dashboard

    def emit(self, record: logging.LogRecord) -> None:
        # Only emit logs that meet the handler's level threshold
        if record.levelno < self.level:
            return

        msg = self.format(record)
        # Color by level
        if record.levelno >= logging.ERROR:
            self.dashboard.add_error(msg)
        elif record.levelno >= logging.WARNING:
            self.dashboard.add_error(msg)
        elif record.levelno >= logging.INFO:
            self.dashboard.log_info(msg)
        else:
            self.dashboard.log_info(msg)


async def build_command_handler(
    ctx: click.Context,
    tenant_id: str,
    resource_limit: Optional[int],
    max_llm_threads: int,
    no_container: bool,
    generate_spec: bool,
    visualize: bool,
    no_dashboard: bool,
    test_keypress_queue: bool,
    test_keypress_file: str,
) -> None:
    """Handle the build command logic."""

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
            await _run_no_dashboard_mode(ctx, grapher, logger)
            return
        else:
            await _run_dashboard_mode(
                ctx,
                grapher,
                config,
                max_llm_threads,
                test_keypress_file,
                test_keypress_queue,
                generate_spec,
                visualize,
                logger,
            )

    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}", err=True)
        logging.error(f"CLI exiting with code 1 after dashboard: {e}")
        sys.exit(1)


async def _run_no_dashboard_mode(
    ctx: click.Context, grapher: "AzureTenantGrapher", logger: logging.Logger
) -> None:
    """Run build in no-dashboard mode with line-by-line logging."""

    from rich.logging import RichHandler
    from rich.style import Style

    class GreenInfoRichHandler(RichHandler):  # type: ignore[misc]
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
        # Preserve specific logger configurations
        if name in ["httpx", "azure", "openai"]:
            continue
        logging.getLogger(name).setLevel(level_map.get(cli_log_level, logging.INFO))
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


async def _run_dashboard_mode(
    ctx: click.Context,
    grapher: "AzureTenantGrapher",
    config: "AzureTenantGrapherConfig",
    max_llm_threads: int,
    test_keypress_file: str,
    test_keypress_queue: bool,
    generate_spec: bool,
    visualize: bool,
    logger: logging.Logger,
) -> None:
    """Run build in dashboard mode with Rich UI."""

    # Setup RichDashboard
    dashboard = RichDashboard(
        config=config.to_dict(),
        batch_size=max_llm_threads,
        total_threads=max_llm_threads,
    )

    # Setup file logging to the dashboard's log file
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
    def progress_callback(**kwargs: int) -> None:
        dashboard.update_progress(**kwargs)

    # Patch logging to send INFO/ERROR to both dashboard and file
    dashboard_handler = DashboardLogHandler(dashboard)
    dashboard_handler.setFormatter(
        logging.Formatter("%(levelname)s:%(name)s:%(message)s")
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(
        logging.INFO
    )  # Set to INFO by default, dashboard will manage level changes
    root_logger.handlers.clear()

    # Set dashboard handler to only show INFO and above by default
    dashboard_handler.setLevel(logging.INFO)

    # Add both dashboard and file handlers
    root_logger.addHandler(dashboard_handler)
    root_logger.addHandler(file_handler)

    # Set all known loggers to INFO (not DEBUG) by default
    for name in logging.root.manager.loggerDict:
        # Preserve specific logger configurations (httpx, azure, openai should stay at WARNING)
        if name in ["httpx", "azure", "openai"]:
            continue
        logging.getLogger(name).setLevel(logging.INFO)

    dashboard.log_info(f"📄 Logs are being written to: {dashboard.log_file_path}")

    # Create dashboard manager first
    dashboard_manager = CLIDashboardManager(dashboard)

    # Start the exit file checker immediately if using file-based testing
    exit_checker_task = None
    if test_keypress_file:

        async def check_exit_file():
            """Exit checker that looks for 'x' in the file."""
            while True:
                try:
                    if os.path.exists(test_keypress_file):
                        with open(test_keypress_file) as f:
                            content = f.read()
                            if "x" in content.lower():
                                with dashboard.lock:
                                    dashboard._should_exit = True  # type: ignore[attr-defined]
                                return
                    await asyncio.sleep(0.1)
                except Exception as e:
                    logging.debug(f"Error checking exit file: {e}")
                    await asyncio.sleep(0.1)

        exit_checker_task = asyncio.create_task(check_exit_file())

    # Start the graph build concurrently after starting exit checker
    # Use a mock build task for testing to avoid Azure API calls
    if test_keypress_file:

        async def mock_build_task():
            # Simulate a long-running build that can be cancelled
            try:
                await asyncio.sleep(300)  # 5 minutes - should be cancelled before this
                return "mock build completed"
            except asyncio.CancelledError:
                raise

        build_task = asyncio.create_task(mock_build_task())
    else:
        build_task = asyncio.create_task(
            grapher.build_graph(progress_callback=progress_callback)
        )
    dashboard.set_processing(True)
    dashboard.log_info("Starting build...")

    try:
        if test_keypress_file:
            # For file-based testing, use simplified dashboard runner that doesn't duplicate the exit checker
            with dashboard.live():
                dashboard.log_info("Press 'x' to exit the dashboard")
                await dashboard_manager.poll_build_task(build_task)
        elif test_keypress_queue:
            await dashboard_manager.run_with_queue_keypress(build_task)
        else:
            await dashboard_manager.run_normal(build_task)
    except Exception as e:
        # Check if this is our custom dashboard exit exception or Rich dashboard exit
        from src.cli_dashboard_manager import DashboardExitException
        from src.rich_dashboard import DashboardExit

        if isinstance(
            e, (DashboardExitException, DashboardExit)
        ) or "User pressed 'x' to exit" in str(e):
            # Cancel the build task and exit immediately
            logger.info("User requested exit via 'x' keypress. Exiting...")
            if not build_task.done():
                build_task.cancel()
                try:
                    await build_task
                except asyncio.CancelledError:
                    pass
            sys.exit(0)
        # If the dashboard was exited by user, suppress context manager errors
        if "'NoneType' object does not support the context manager protocol" in str(e):
            return
        raise
    finally:
        # Clean up exit checker if it was created
        if test_keypress_file and exit_checker_task and not exit_checker_task.done():
            exit_checker_task.cancel()

    # Check if user requested exit
    if dashboard_manager.check_exit_condition():
        sys.exit(0)

    # Handle build completion and post-processing
    await dashboard_manager.handle_build_completion(
        build_task, grapher, config, generate_spec, visualize
    )


@click.command("visualize")
@click.option(
    "--link-hierarchy/--no-link-hierarchy",
    default=True,
    help="Include Subscription and Tenant hierarchy links in the visualization (default: enabled)."
)
@click.option(
    "--no-container",
    is_flag=True,
    default=False,
    help="Do not attempt to start a Neo4j container if connection fails."
)
async def visualize_command_handler(
    ctx: click.Context, link_hierarchy: bool, no_container: bool
) -> None:
    """Handle the visualize command logic."""

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


async def spec_command_handler(ctx: click.Context, tenant_id: str) -> None:
    """Handle the spec command logic."""

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


def generate_spec_command_handler(
    ctx: click.Context, limit: Optional[int], output: Optional[str]
) -> None:
    """Handle the generate-spec command logic."""

    try:
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


async def progress_command_handler(ctx: click.Context) -> None:
    """Handle the progress command logic."""

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
