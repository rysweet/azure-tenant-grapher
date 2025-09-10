"""
CLI Command Handlers

Contains the implementation of various CLI commands to keep the main CLI file focused.
"""

import asyncio
import json
import logging
import os
import shutil
import signal
import subprocess
import sys
from typing import TYPE_CHECKING, Optional

import click
import structlog

from src.azure_tenant_grapher import AzureTenantGrapher
from src.cli_dashboard_manager import CLIDashboardManager, DashboardExitException
from src.config_manager import (
    create_config_from_env,
    create_neo4j_config_from_env,
    setup_logging,
)
from src.graph_visualizer import GraphVisualizer
from src.logging_config import configure_logging
from src.rich_dashboard import RichDashboard
from src.utils.neo4j_startup import ensure_neo4j_running

configure_logging()

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
    max_build_threads: int,
    max_retries: int,
    no_container: bool,
    generate_spec: bool,
    visualize: bool,
    no_dashboard: bool,
    test_keypress_queue: bool,
    test_keypress_file: str,
    rebuild_edges: bool = False,
    no_aad_import: bool = False,
    debug: bool = False,
) -> str | None:
    """Handle the build command logic."""
    if debug:
        print("[DEBUG][CLI] Entered build_command_handler", flush=True)
    ensure_neo4j_running(debug)
    if debug:
        print("[DEBUG][CLI] ensure_neo4j_running() complete", flush=True)

    try:
        if debug:
            print("[DEBUG][CLI] Preparing config", flush=True)
        effective_tenant_id = tenant_id or os.environ.get("AZURE_TENANT_ID")
        if not effective_tenant_id:
            click.echo(
                "❌ No tenant ID provided and AZURE_TENANT_ID not set in environment.",
                err=True,
            )
            sys.exit(1)

        config = create_config_from_env(
            effective_tenant_id, resource_limit, max_retries, max_build_threads, debug
        )
        config.processing.max_concurrency = max_llm_threads
        config.processing.auto_start_container = not no_container
        config.processing.enable_aad_import = not no_aad_import
        config.logging.level = ctx.obj["log_level"]

        setup_logging(config.logging)
        print("[DEBUG][CLI] Logging configured", flush=True)

        config.validate_all()
        print("[DEBUG][CLI] Config validated", flush=True)

        logger = structlog.get_logger(__name__)

        grapher = AzureTenantGrapher(config)
        print("[DEBUG][CLI] AzureTenantGrapher instantiated", flush=True)

        if no_dashboard:
            print("[DEBUG][CLI] Entering _run_no_dashboard_mode", flush=True)
            await _run_no_dashboard_mode(ctx, grapher, logger, rebuild_edges)
            print("[DEBUG][CLI] Returned from _run_no_dashboard_mode", flush=True)
            import asyncio
            import threading

            print(
                "[DEBUG] Active threads at build_command_handler return:",
                threading.enumerate(),
                flush=True,
            )
            try:
                loop = asyncio.get_running_loop()
                print(
                    "[DEBUG] asyncio loop at build_command_handler return:",
                    loop,
                    flush=True,
                )
                print(
                    "[DEBUG] asyncio tasks at build_command_handler return:",
                    asyncio.all_tasks(loop),
                    flush=True,
                )
            except Exception as e:
                print(
                    "[DEBUG] Could not get asyncio loop or tasks at build_command_handler return:",
                    e,
                    flush=True,
                )
            print("[DEBUG][CLI] Returning __NO_DASHBOARD_BUILD_COMPLETE__", flush=True)
            structlog.get_logger(__name__).info(
                "[DEBUG][CLI] build_command_handler returning __NO_DASHBOARD_BUILD_COMPLETE__"
            )
            return "__NO_DASHBOARD_BUILD_COMPLETE__"
        else:
            print("[DEBUG][CLI] Entering _run_dashboard_mode", flush=True)
            result = await _run_dashboard_mode(
                ctx,
                grapher,
                config,
                max_llm_threads,
                test_keypress_file,
                test_keypress_queue,
                generate_spec,
                visualize,
                logger,
                rebuild_edges,
            )
            print("[DEBUG][CLI] Returned from _run_dashboard_mode", flush=True)
            structlog.get_logger(__name__).info(
                "[DEBUG][CLI] build_command_handler returning from dashboard mode",
                result=result,
            )
            return result

    except Exception as e:
        print(f"[DEBUG][CLI] Exception in build_command_handler: {e}", flush=True)
        click.echo(
            f"❌ Unexpected error: {e}\n"
            "If this is a Neo4j error, ensure Neo4j is running and credentials are correct.\n"
            "If this is an LLM error, check your Azure OpenAI environment variables and network connectivity.\n"
            "For troubleshooting, run with --log-level DEBUG and see the log file for details.",
            err=True,
        )
        structlog.get_logger(__name__).error(
            "CLI exiting with code 1 after dashboard", error=str(e), exc_info=True
        )
        sys.exit(1)


async def _run_no_dashboard_mode(
    ctx: click.Context,
    grapher: "AzureTenantGrapher",
    logger: logging.Logger,
    rebuild_edges: bool = False,
) -> None:
    """Run build in no-dashboard mode with line-by-line logging."""
    print("[DEBUG][CLI] Entered _run_no_dashboard_mode", flush=True)
    import tempfile
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file_path = f"{tempfile.gettempdir()}/azure_tenant_grapher_{timestamp}.log"
    structlog.get_logger(__name__).info(
        event="Log file path for no-dashboard mode", log_file_path=log_file_path
    )

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

    root_logger = logging.getLogger()
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
        if name in ["httpx", "azure", "openai"]:
            continue
        logging.getLogger(name).setLevel(level_map.get(cli_log_level, logging.INFO))
    structlog.get_logger(__name__).info(
        event="Running in no-dashboard mode: logs will be emitted line by line.",
        log_level=cli_log_level,
    )
    try:
        print("[DEBUG][CLI] Connecting to Neo4j...", flush=True)
        grapher.connect_to_neo4j()
        logger.info("🚀 Starting Azure Tenant Graph building...")
        print("[DEBUG][CLI] About to await grapher.build_graph()", flush=True)
        if hasattr(grapher, "build_graph"):
            if rebuild_edges:
                click.echo(
                    "🔄 Forcing re-evaluation of all relationships/edges for all resources."
                )
                result = await grapher.build_graph(force_rebuild_edges=True)
                print(
                    "[DEBUG][CLI] Awaited grapher.build_graph(force_rebuild_edges=True)",
                    flush=True,
                )
            else:
                result = await grapher.build_graph()
                print("[DEBUG][CLI] Awaited grapher.build_graph()", flush=True)
        else:
            result = None
        click.echo("🎉 Graph building completed.")
        click.echo(f"Result: {result}")
        print("[DEBUG][CLI] Exiting try block in _run_no_dashboard_mode", flush=True)
    except Exception as e:
        print(f"[DEBUG][CLI] Exception in _run_no_dashboard_mode: {e}", flush=True)
        click.echo(
            f"❌ Failed to connect to Neo4j: {e}\n"
            "Action: Ensure Neo4j is running and accessible at the configured URI.\n"
            "If using Docker, check that the container is started and healthy.\n"
            "You can start the container with 'python scripts/cli.py container' or 'docker-compose up'.",
            err=True,
        )
        sys.exit(1)
    finally:
        print(
            "[DEBUG] Reached end of _run_no_dashboard_mode, about to call sys.exit(0)",
            flush=True,
        )
        import asyncio
        import threading

        print(
            "[DEBUG] Active threads at end of _run_no_dashboard_mode:",
            threading.enumerate(),
            flush=True,
        )
        try:
            loop = asyncio.get_running_loop()
            print(
                "[DEBUG] asyncio loop at end of _run_no_dashboard_mode:",
                loop,
                flush=True,
            )
            print(
                "[DEBUG] asyncio tasks at end of _run_no_dashboard_mode:",
                asyncio.all_tasks(loop),
                flush=True,
            )
        except Exception as e:
            print("[DEBUG] Could not get asyncio loop or tasks:", e, flush=True)

        print("[DEBUG] Actually calling sys.exit(0) now", flush=True)
        sys.exit(0)


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
    rebuild_edges: bool = False,
) -> str | None:
    """Run build in dashboard mode with Rich UI."""
    print("[DEBUG][CLI] Entered _run_dashboard_mode", flush=True)

    logger.info("[DEBUG] Entered _run_dashboard_mode")
    # Setup RichDashboard with both thread parameters
    dashboard = RichDashboard(
        config=config.to_dict(),
        max_llm_threads=max_llm_threads,
        max_build_threads=getattr(config.processing, "max_build_threads", 20),
    )
    # Print log file path for test discoverability
    structlog.get_logger(__name__).info(
        event="Log file path for dashboard mode", log_file_path=dashboard.log_file_path
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
        dashboard.add_error(
            f"❌ Failed to connect to Neo4j: {e}\n"
            "Action: Ensure Neo4j is running and accessible at the configured URI.\n"
            "If using Docker, check that the container is started and healthy.\n"
            "You can start the container with 'python scripts/cli.py container' or 'docker-compose up'."
        )
        click.echo(
            f"❌ Failed to connect to Neo4j: {e}\n"
            "Action: Ensure Neo4j is running and accessible at the configured URI.\n"
            "If using Docker, check that the container is started and healthy.\n"
            "You can start the container with 'python scripts/cli.py container' or 'docker-compose up'.",
            err=True,
        )
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
        if rebuild_edges:
            build_task = asyncio.create_task(
                grapher.build_graph(
                    progress_callback=progress_callback, force_rebuild_edges=True
                )
            )
        else:
            build_task = asyncio.create_task(
                grapher.build_graph(progress_callback=progress_callback)
            )
    dashboard.set_processing(True)
    dashboard.log_info("Starting build...")

    # Removed debug print
    try:
        print("[DEBUG][CLI] Entering dashboard build task execution", flush=True)
        if test_keypress_file:
            with dashboard.live():
                dashboard.log_info("Press 'x' to exit the dashboard")
                logger.info("[DEBUG] Entering poll_build_task (file keypress)")
                try:
                    print(
                        "[DEBUG][CLI] Awaiting dashboard_manager.poll_build_task",
                        flush=True,
                    )
                    await dashboard_manager.poll_build_task(build_task)
                    print(
                        "[DEBUG][CLI] Returned from dashboard_manager.poll_build_task",
                        flush=True,
                    )
                except DashboardExitException:
                    print(
                        "[DEBUG][CLI] DashboardExitException in poll_build_task",
                        flush=True,
                    )
                    return "__DASHBOARD_EXIT__"
        elif test_keypress_queue:
            print(
                "[DEBUG][CLI] Awaiting dashboard_manager.run_with_queue_keypress",
                flush=True,
            )
            result = await dashboard_manager.run_with_queue_keypress(build_task)
            print(
                "[DEBUG][CLI] Returned from dashboard_manager.run_with_queue_keypress",
                flush=True,
            )
            if result == "__DASHBOARD_EXIT__":
                print(
                    "[DEBUG][CLI] DashboardExitException in run_with_queue_keypress",
                    flush=True,
                )
                return "__DASHBOARD_EXIT__"
        else:
            print("[DEBUG][CLI] Awaiting dashboard_manager.run_normal", flush=True)
            result = await dashboard_manager.run_normal(build_task)
            print("[DEBUG][CLI] Returned from dashboard_manager.run_normal", flush=True)
            if result == "__DASHBOARD_EXIT__":
                print("[DEBUG][CLI] DashboardExitException in run_normal", flush=True)
                return "__DASHBOARD_EXIT__"
    except DashboardExitException:
        print(
            "[DEBUG][CLI] DashboardExitException caught in _run_dashboard_mode",
            flush=True,
        )
        return "__DASHBOARD_EXIT__"
    finally:
        if test_keypress_file and exit_checker_task and not exit_checker_task.done():
            exit_checker_task.cancel()

    # Removed debug print

    # Minimal, direct exit logic: after dashboard context, check exit flag and exit if needed
    if dashboard_manager.check_exit_condition() or dashboard.should_exit:
        logger.info("[DEBUG] Dashboard manager exit condition triggered (post-context)")
        try:
            logger.info("[DEBUG] Closing Neo4j connection before exit")
            # Just skip the cleanup for now to avoid attribute errors
            pass
        except Exception as e:
            logger.error(f"[DEBUG] Error during cleanup: {e}")
        # Removed debug print
        return "__DASHBOARD_EXIT__"

    # Handle build completion and post-processing
    print("[DEBUG][CLI] Awaiting dashboard_manager.handle_build_completion", flush=True)
    await dashboard_manager.handle_build_completion(
        build_task, grapher, config, generate_spec, visualize
    )
    print(
        "[DEBUG][CLI] Returned from dashboard_manager.handle_build_completion",
        flush=True,
    )
    return None


async def visualize_command_handler(
    ctx: click.Context,
    link_hierarchy: bool = True,
    no_container: bool = False,
    output: Optional[str] = None,
) -> None:
    """Handle the visualize command logic."""
    import os
    from datetime import datetime

    ensure_neo4j_running()
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

        click.echo("🎨 Generating graph visualization...")

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
            click.echo(f"✅ Visualization saved to: {viz_path}")
        except Exception as e:
            click.echo(
                f"⚠️  Failed to connect to Neo4j: {e}\n"
                "Action: Ensure Neo4j is running and accessible at the configured URI.\n"
                "If using Docker, check that the container is started and healthy.\n"
                "You can start the container with 'python scripts/cli.py container' or 'docker-compose up'.",
                err=True,
            )
            if not no_container:
                click.echo("🔄 Attempting to start Neo4j container...")
                try:
                    ensure_neo4j_running()
                    click.echo(
                        "✅ Neo4j container started successfully, retrying visualization..."
                    )
                    import time

                    for _i in range(10):
                        try:
                            viz_path = visualizer.generate_html_visualization(
                                output_path=effective_output,
                                link_to_hierarchy=link_hierarchy,
                            )
                            click.echo(f"✅ Visualization saved to: {viz_path}")
                            break
                        except Exception:
                            time.sleep(3)
                    else:
                        click.echo(
                            "❌ Failed to connect to Neo4j after starting container.\n"
                            "Action: Check Docker logs and ensure the Neo4j container is healthy.",
                            err=True,
                        )
                        sys.exit(1)
                except Exception as e:
                    click.echo(
                        f"❌ Failed to start Neo4j container: {e}\n"
                        "Action: Check Docker is running and you have permission to start containers.",
                        err=True,
                    )
                    sys.exit(1)
            else:
                click.echo(
                    "❌ Neo4j is not running and --no-container was specified.\n"
                    "Action: Start Neo4j manually or remove --no-container to let the CLI manage it.",
                    err=True,
                )
                sys.exit(1)

    except Exception as e:
        click.echo(f"❌ Failed to generate visualization: {e}", err=True)
        sys.exit(1)


async def spec_command_handler(
    ctx: click.Context, tenant_id: str, domain_name: Optional[str] = None
) -> None:
    """Handle the spec command logic."""
    ensure_neo4j_running()
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
                "❌ Azure OpenAI not configured. Tenant specification requires LLM capabilities.\n"
                "Action: Set the required Azure OpenAI environment variables (AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY, AZURE_OPENAI_API_VERSION) and try again.",
                err=True,
            )
            sys.exit(1)

        # Create grapher and generate specification
        grapher = AzureTenantGrapher(config)

        click.echo("📋 Generating tenant specification from existing graph...")
        # Pass domain_name to the grapher if/when supported
        await grapher.generate_tenant_specification(domain_name=domain_name)
        click.echo("✅ Tenant specification generated successfully")

    except Exception as e:
        click.echo(
            f"❌ Failed to generate specification: {e}\n"
            "Action: Check that Neo4j and Azure OpenAI are configured correctly. Run with --log-level DEBUG for more details.",
            err=True,
        )
        sys.exit(1)


def generate_spec_command_handler(
    ctx: click.Context, limit: Optional[int], output: Optional[str]
) -> None:
    """Handle the generate-spec command logic."""
    ensure_neo4j_running()
    import os

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
        neo4j_uri = config.neo4j.uri or ""
        neo4j_user = config.neo4j.user
        neo4j_password = config.neo4j.password

        # Spec config
        spec_config = config.specification
        if limit is not None:
            spec_config.resource_limit = limit

        # Ensure outputs/ dir exists for defaulting
        os.makedirs("outputs", exist_ok=True)

        # Anonymizer
        anonymizer = ResourceAnonymizer(seed=spec_config.anonymization_seed)

        # Generator
        generator = TenantSpecificationGenerator(
            neo4j_uri, neo4j_user, neo4j_password, anonymizer, spec_config
        )

        # Default output to outputs/ if not specified
        effective_output = output
        if not effective_output:
            from datetime import datetime, timezone

            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            effective_output = os.path.join("outputs", f"{ts}_tenant_spec.md")

        output_path = generator.generate_specification(output_path=effective_output)
        click.echo(f"✅ Tenant Markdown specification generated: {output_path}")

    except Exception as e:
        import traceback

        click.echo(f"❌ Failed to generate tenant specification: {e}", err=True)
        traceback.print_exc()
        sys.exit(1)


# === MCP Server Command Handler ===


async def mcp_server_command_handler(ctx: click.Context):
    """
    Ensure Neo4j is running, then launch MCP server (uvx mcp-neo4j-cypher).
    """
    import logging

    from src.mcp_server import run_mcp_server_foreground

    try:
        logging.basicConfig(level=ctx.obj.get("log_level", "INFO"))
        exit_code = await run_mcp_server_foreground()
        if exit_code == 0:
            click.echo("✅ MCP server exited cleanly.")
        else:
            click.echo(f"❌ MCP server exited with code {exit_code}", err=True)
    except Exception as e:
        click.echo(f"❌ Failed to start MCP server: {e}", err=True)
        import traceback

        traceback.print_exc()
        sys.exit(1)


# === Agent Mode Command Handler ===


async def agent_mode_command_handler(
    ctx: click.Context, question: Optional[str] = None
):
    """
    Start Neo4j, MCP server, and launch AutoGen MCP agent chat loop.
    """
    import logging

    from src.agent_mode import run_agent_mode

    try:
        logging.basicConfig(level=ctx.obj.get("log_level", "INFO"))
        await run_agent_mode(question=question)
    except Exception as e:
        import click

        click.echo(f"❌ Failed to start agent mode: {e}", err=True)
        import traceback

        traceback.print_exc()


# === Threat Modeling Agent Command Handler ===


async def generate_sim_doc_command_handler(
    ctx: click.Context,
    size: Optional[int] = None,
    seed_path: Optional[str] = None,
    out_path: Optional[str] = None,
) -> None:
    """
    Handle the generate-sim-doc CLI command.
    """
    import os

    from rich.console import Console

    from src.llm_descriptions import create_llm_generator

    console = Console()
    # Read seed file if provided
    seed_text = None
    if seed_path:
        try:
            with open(seed_path, encoding="utf-8") as f:
                seed_text = f.read()
        except Exception as e:
            click.echo(f"❌ Failed to read seed file: {e}", err=True)
            sys.exit(1)

    # Create LLM generator
    llm = create_llm_generator()
    if not llm:
        click.echo(
            "❌ LLM configuration is invalid or missing. Check your environment.\n"
            "Action: Set the required Azure OpenAI environment variables (AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY, AZURE_OPENAI_API_VERSION) and ensure network connectivity.",
            err=True,
        )
        sys.exit(1)

    # Determine identity count ranges based on company size
    if size:
        if size < 100:
            # Small company
            user_range = "5-15"
            group_range = "2-5"
            sp_range = "2-3"
            mi_range = "1-2"
            ca_range = "1-2"
        elif size < 1000:
            # Medium company (default)
            user_range = "15-50"
            group_range = "5-10"
            sp_range = "5-10"
            mi_range = "3-5"
            ca_range = "3-5"
        elif size < 10000:
            # Large company
            user_range = "50-200"
            group_range = "10-30"
            sp_range = "10-20"
            mi_range = "5-10"
            ca_range = "5-10"
        else:
            # Enterprise
            user_range = "200-500"
            group_range = "30-50"
            sp_range = "20-50"
            mi_range = "10-20"
            ca_range = "10-15"
    else:
        # Default to medium company ranges
        user_range = "15-50"
        group_range = "5-10"
        sp_range = "5-10"
        mi_range = "3-5"
        ca_range = "3-5"

    # Build the prompt as in generate_sim_customer_profile
    prompt = (
        "I'm a research scientist planning on building accurate simulations of Microsoft Azure customer environments so that security professionals can run realistic security scenarios in those environments. "
        "We want the environments to be as close to real customer environments of large customers as possible, but we cannot copy real customer data or real customer names/identities etc. "
        "We care more about simulating customer complexity and configuration than we do about scale. "
        "We have a large trove of customer stories here: https://www.microsoft.com/en-us/customers/search?filters=product%3Aazure which you can browse and search to find relevant customer profiles. "
        "We also have a collection of Azure reference architectures here: https://learn.microsoft.com/en-us/azure/architecture/browse/. "
        "You can use both of these resources to research typical customers and the architectures they deploy on Azure.\n\n"
        "Please use that background information and produce for me a distinct fake customer profile that describes the customer company, its goals, its personnel, and the solutions that they are leveraging on Azure, "
        "with enough detail that we could begin to go model that customer environment. The fake profiles must be somewhat realistic in terms of storytelling, application, and personnel, but MAY NOT use any of the content from the Customer Stories site verbatim and MAY NOT use the names of real companies or customers.\n\n"
        "IMPORTANT: Generate comprehensive identity and access management details including:\n\n"
        f"1. USERS ({user_range} total):\n"
        "   - Full realistic names, job titles, and departments\n"
        "   - Manager relationships forming an organizational hierarchy\n"
        "   - Mix of authentication methods (password, password+MFA, passwordless, FIDO2, Windows Hello)\n"
        "   - MFA status variations (enabled/disabled/enforced)\n"
        "   - Risk profiles (low/medium/high) based on privileges and behavior\n"
        "   - Last sign-in patterns (recent, stale, never)\n"
        "   - Include various user types: regular employees, executives, IT admins, contractors, external guests, service accounts\n"
        "   - Account statuses (active, disabled, locked)\n"
        "   - License assignments (E3, E5, F1, etc.)\n\n"
        f"2. GROUPS ({group_range} total):\n"
        "   - Different types: Security groups, Microsoft 365 groups, Distribution lists, Mail-enabled security groups\n"
        "   - Some with dynamic membership rules (e.g., department eq 'Sales', jobTitle contains 'Manager')\n"
        "   - Nested group structures showing inheritance\n"
        "   - Clear owners and members for each group\n"
        "   - Groups for different purposes: department teams, project groups, role-based access groups\n\n"
        f"3. SERVICE PRINCIPALS ({sp_range} total):\n"
        "   - Mix of first-party Microsoft apps and third-party integrations\n"
        "   - Various API permissions (Microsoft Graph, Azure AD Graph, SharePoint, etc.)\n"
        "   - Different authentication methods (certificates, client secrets, managed identities)\n"
        "   - Mix of application permissions and delegated permissions\n"
        "   - Include common scenarios: backup solutions, monitoring tools, CI/CD pipelines, SaaS integrations\n\n"
        f"4. MANAGED IDENTITIES ({mi_range} total):\n"
        "   - Both system-assigned and user-assigned identities\n"
        "   - Associated with specific Azure resources (VMs, App Services, Functions, AKS)\n"
        "   - Clear resource associations and permission scopes\n\n"
        "5. RBAC WITH PRIVILEGED IDENTITY MANAGEMENT (PIM):\n"
        "   - Mix of permanent and eligible role assignments\n"
        "   - Just-in-time (JIT) access patterns with activation requirements\n"
        "   - Approval workflows for privileged roles\n"
        "   - Time-bound assignments with start/end dates\n"
        "   - Various Azure RBAC roles (Owner, Contributor, Reader, custom roles)\n"
        "   - Azure AD roles (Global Admin, User Admin, Application Admin, etc.)\n"
        "   - Include role assignment conditions and justifications\n\n"
        f"6. CONDITIONAL ACCESS POLICIES ({ca_range} total):\n"
        "   - MFA requirements for specific apps or user groups\n"
        "   - Device compliance requirements (Intune enrolled, compliant, hybrid joined)\n"
        "   - Location-based access controls (trusted locations, country restrictions)\n"
        "   - Risk-based policies (sign-in risk, user risk)\n"
        "   - Session controls (app-enforced restrictions, limited access)\n"
        "   - Different policy states (enabled, disabled, report-only)\n\n"
        "7. ADDITIONAL IDENTITY SCENARIOS:\n"
        "   - B2B guest users from partner organizations\n"
        "   - Temporary contractor accounts with expiration dates\n"
        "   - Privileged access workstations (PAW) users\n"
        "   - Emergency break-glass accounts\n"
        "   - Synchronized on-premises accounts (hybrid identity)\n"
        "   - Application-specific service accounts\n\n"
        "For each identity-related entity, provide rich details that would exist in a real enterprise environment. "
        "Include realistic relationships between entities (e.g., users in groups, groups assigned to roles, service principals with specific permissions). "
        "Structure the output with clear sections and subsections, using a format that can be parsed to extract the identity and access management configuration. "
        "Include specific Azure AD object IDs (GUIDs) for all entities to enable relationship mapping."
    )
    if size:
        prompt += f"\n\nTarget company size: {size} employees (approximate)."
    if seed_text:
        prompt += f"\n\nSeed/suggestions for the profile:\n{seed_text}"

    # Generate the profile with streaming and progress indicator
    markdown = ""
    try:
        with console.status(
            "[bold green]Generating documentation...", spinner="dots"
        ) as status:
            first_token = True
            tokens = []
            try:
                async for token in llm.generate_description_streaming(prompt):
                    if first_token:
                        status.stop()
                        first_token = False
                    tokens.append(token)
                    console.print(token, end="", soft_wrap=True, highlight=False)
                markdown = "".join(tokens)
            except Exception as stream_exc:
                if first_token:
                    status.stop()
                console.print(
                    f"\n[red]⚠️ Streaming failed, falling back to non-streaming mode: {stream_exc}[/red]"
                )
                try:
                    markdown = await llm.generate_sim_customer_profile(
                        size=size, seed=seed_text
                    )
                    console.print(markdown)
                except Exception as e:
                    click.echo(
                        f"❌ LLM generation failed: {e}\n"
                        "Action: Check your Azure OpenAI configuration and network connectivity. Run with --log-level DEBUG for more details.",
                        err=True,
                    )
                    sys.exit(1)
    except Exception as e:
        click.echo(
            f"❌ LLM generation failed: {e}\n"
            "Action: Check your Azure OpenAI configuration and network connectivity. Run with --log-level DEBUG for more details.",
            err=True,
        )
        sys.exit(1)

    # Determine output path (migrate simdocs/ to outputs/)
    effective_out_path = out_path
    if effective_out_path:
        output_path = effective_out_path
    else:
        os.makedirs("outputs", exist_ok=True)
        import datetime

        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        output_path = os.path.join("outputs", f"simdoc-{timestamp}.md")

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown)
        console.print(
            f"\n[bold green]✅ Simulated customer profile written to: {output_path}[/bold green]"
        )
    except Exception as e:
        click.echo(
            f"❌ Failed to write output file: {e}\n"
            "Action: Check that the output path is writable and you have sufficient disk space.",
            err=True,
        )
        sys.exit(1)


async def generate_threat_model_command_handler(
    ctx: Optional["click.Context"] = None,
):
    """
    Handler for the threat-model CLI command.
    Runs the ThreatModelAgent workflow and prints/logs each stage.
    """
    import click

    from src.threat_modeling_agent.agent import ThreatModelAgent

    click.echo("🚀 Starting Threat Modeling Agent workflow...")
    agent = ThreatModelAgent()
    report_path = await agent.run()
    click.echo("✅ Threat Modeling Agent workflow complete.")
    if report_path:
        click.echo(f"📄 Threat modeling report saved to: {report_path}")


# === Create Tenant Command Handler ===


def create_tenant_from_markdown(text: str):
    """Create a tenant from markdown using TenantCreator."""
    import asyncio

    from src.llm_descriptions import create_llm_generator
    from src.tenant_creator import TenantCreator

    llm_generator = create_llm_generator()
    creator = TenantCreator(llm_generator=llm_generator)
    
    # Store stats for return
    creation_stats = None

    async def _run():
        from src.exceptions import LLMGenerationError
        nonlocal creation_stats

        try:
            spec = await creator.create_from_markdown(text)
            # Check if spec was generated by LLM for permissive validation
            is_llm_generated = getattr(spec, "_is_llm_generated", False)
            creation_stats = await creator.ingest_to_graph(spec, is_llm_generated=is_llm_generated)
        except LLMGenerationError as e:
            import click

            click.echo("❌ LLM output parsing failed during tenant creation.", err=True)
            click.echo(f"Error: {e}", err=True)
            click.echo(
                "Action: The LLM response could not be parsed. Check your Azure OpenAI configuration and try again.\n"
                "If the error persists, run with --log-level DEBUG and review the prompt and raw LLM response below.",
                err=True,
            )
            if hasattr(e, "context") and e.context:
                prompt = e.context.get("prompt")
                raw_response = e.context.get("raw_response")
                if prompt:
                    click.echo("Prompt used for LLM:", err=True)
                    click.echo(prompt, err=True)
                if raw_response:
                    click.echo("Raw LLM response:", err=True)
                    click.echo(raw_response, err=True)
            import sys

            sys.exit(1)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # If we're already in an event loop, schedule the task and wait for it
        task = loop.create_task(_run())
        # For CLI, block until done
        import nest_asyncio

        nest_asyncio.apply()
        result = loop.run_until_complete(task)
    else:
        asyncio.run(_run())
    
    return creation_stats


@click.command("create-tenant")
@click.argument("markdown_file", type=click.Path(exists=True))
def create_tenant_command(markdown_file: str):
    """Create a tenant graph from a tenant spec."""
    try:
        ensure_neo4j_running()
        with open(markdown_file, encoding="utf-8") as f:
            text = f.read()
        print("DEBUG: Raw markdown file contents:\n", text)
        
        # Get creation statistics
        stats = create_tenant_from_markdown(text)
        
        # Display success with detailed feedback
        click.echo("")
        click.echo("✅ Tenant successfully created in Neo4j!")
        click.echo("")
        
        # Display resource counts
        if stats:
            click.echo("📊 Resources created:")
            click.echo("-" * 40)
            
            # Display non-zero counts in a logical order
            display_order = [
                ("tenant", "Tenant"),
                ("subscriptions", "Subscriptions"),
                ("resource_groups", "Resource Groups"),
                ("resources", "Resources"),
                ("users", "Users"),
                ("groups", "Groups"),
                ("service_principals", "Service Principals"),
                ("managed_identities", "Managed Identities"),
                ("admin_units", "Admin Units"),
                ("rbac_assignments", "RBAC Assignments"),
                ("relationships", "Relationships")
            ]
            
            for key, label in display_order:
                if key in stats and stats[key] > 0:
                    click.echo(f"  • {label}: {stats[key]}")
            
            click.echo("-" * 40)
            click.echo(f"  Total entities: {stats.get('total', 0)}")
            click.echo("")
            click.echo("💡 Next steps:")
            click.echo("  • Run 'atg visualize' to see the graph")
            click.echo("  • Run 'atg build' to enrich with more data")
        else:
            click.echo("⚠️  No statistics available")
            
    except Exception as e:
        click.echo(
            f"❌ Failed to create tenant: {e}\n"
            "Action: Check that the markdown file is valid and that Neo4j and Azure OpenAI are configured correctly. Run with --log-level DEBUG for more details.",
            err=True,
        )
        exit(1)


SPA_PIDFILE = os.path.join("outputs", "spa_server.pid")
MCP_PIDFILE = os.path.join("outputs", "mcp_server.pid")


@click.command("start")
def spa_start():
    """Start the local SPA/Electron dashboard and MCP server."""
    # Check for stale PID file
    if os.path.exists(SPA_PIDFILE):
        try:
            with open(SPA_PIDFILE) as f:
                pid = int(f.read().strip())
            # Check if process is actually running
            try:
                os.kill(pid, 0)  # Signal 0 checks if process exists
                click.echo(
                    f"⚠️  SPA already running (PID: {pid}). Use 'atg stop' first.",
                    err=True,
                )
                return
            except ProcessLookupError:
                # Process not running, clean up stale PID file
                click.echo(f"ℹ️  Cleaning up stale PID file (process {pid} not found)")
                os.remove(SPA_PIDFILE)
        except (ValueError, IOError) as e:
            # Invalid PID file, remove it
            click.echo(f"ℹ️  Removing invalid PID file: {e}")
            os.remove(SPA_PIDFILE)

    # Check if npm is available
    if not shutil.which("npm"):
        click.echo(
            "❌ npm is not installed. Please install Node.js and npm first.", err=True
        )
        return

    try:
        # Change to the spa directory
        spa_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "spa")

        # Check if package.json exists
        if not os.path.exists(os.path.join(spa_dir, "package.json")):
            click.echo(
                "❌ SPA not found. Please ensure the spa directory exists with package.json",
                err=True,
            )
            return

        # Check if node_modules exists, if not, install dependencies
        if not os.path.exists(os.path.join(spa_dir, "node_modules")):
            click.echo("📦 Installing SPA dependencies...")
            install_proc = subprocess.run(
                ["npm", "install"], cwd=spa_dir, capture_output=True, text=True
            )
            if install_proc.returncode != 0:
                click.echo(
                    f"❌ Failed to install dependencies: {install_proc.stderr}",
                    err=True,
                )
                return
            click.echo("✅ Dependencies installed successfully")

        # Always build the app to ensure latest code is used
        click.echo("🔨 Building Electron app with latest code...")
        build_proc = subprocess.run(
            ["npm", "run", "build"], cwd=spa_dir, capture_output=True, text=True
        )
        if build_proc.returncode != 0:
            click.echo(
                f"❌ Failed to build app: {build_proc.stderr}",
                err=True,
            )
            return

        # Verify the build created the main entry point
        main_entry = os.path.join(spa_dir, "dist", "main", "index.js")
        if not os.path.exists(main_entry):
            click.echo(
                "❌ Build completed but main entry point not found. Check build configuration.",
                err=True,
            )
            return
        click.echo("✅ Electron app built successfully")

        # Start the MCP server
        click.echo("🤖 Starting MCP server...")
        try:
            # Check if MCP server is already running
            mcp_needs_start = True
            if os.path.exists(MCP_PIDFILE):
                # Check if it's a stale PID file
                try:
                    with open(MCP_PIDFILE) as f:
                        mcp_pid = int(f.read().strip())
                    try:
                        os.kill(mcp_pid, 0)  # Check if process exists
                        click.echo(f"⚠️  MCP server already running (PID: {mcp_pid}), skipping...")
                        mcp_needs_start = False
                    except ProcessLookupError:
                        # Process not running, clean up stale PID file
                        click.echo(f"ℹ️  Cleaning up stale MCP PID file (process {mcp_pid} not found)")
                        os.remove(MCP_PIDFILE)
                except (ValueError, IOError) as e:
                    # Invalid PID file, remove it
                    click.echo(f"ℹ️  Removing invalid MCP PID file: {e}")
                    os.remove(MCP_PIDFILE)
            
            if mcp_needs_start:
                # Start MCP server in the background
                mcp_proc = subprocess.Popen(
                    [sys.executable, "-m", "src.mcp_server"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env={
                        **os.environ,
                        "PYTHONPATH": os.path.dirname(os.path.dirname(__file__)),
                    },
                )

                # Save MCP PID
                with open(MCP_PIDFILE, "w") as f:
                    f.write(str(mcp_proc.pid))

                click.echo(f"✅ MCP server started (PID: {mcp_proc.pid})")
        except Exception as e:
            click.echo(f"⚠️  Failed to start MCP server: {e}")
            # Continue even if MCP fails to start

        # Start the Electron app
        spa_proc = subprocess.Popen(
            ["npm", "run", "start"],
            cwd=spa_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Save the PID
        os.makedirs("outputs", exist_ok=True)
        with open(SPA_PIDFILE, "w") as f:
            f.write(str(spa_proc.pid))

        click.echo("🚀 SPA started. The Electron app should open shortly.")
        click.echo(f"(PID: {spa_proc.pid} | pidfile: {SPA_PIDFILE})")
        click.echo("Use 'atg stop' to shut down the SPA and MCP server when done.")
    except Exception as e:
        click.echo(f"❌ Failed to start SPA: {e}", err=True)


@click.command("stop")
def spa_stop():
    """Stop the local SPA/Electron dashboard and MCP server."""
    spa_stopped = False
    mcp_stopped = False

    # Stop SPA
    if os.path.exists(SPA_PIDFILE):
        try:
            with open(SPA_PIDFILE) as f:
                pid = int(f.read().strip())
            try:
                os.kill(pid, signal.SIGTERM)
                click.echo("🛑 Sent SIGTERM to SPA process.")
                spa_stopped = True
            except Exception as e:
                click.echo(f"⚠️  Could not terminate SPA process: {e}", err=True)
            os.remove(SPA_PIDFILE)
        except Exception as e:
            click.echo(f"❌ Failed to stop SPA: {e}", err=True)
    else:
        click.echo("ℹ️  No SPA process running.")

    # Stop MCP server
    if os.path.exists(MCP_PIDFILE):
        try:
            with open(MCP_PIDFILE) as f:
                pid = int(f.read().strip())
            try:
                os.kill(pid, signal.SIGTERM)
                click.echo("🛑 Sent SIGTERM to MCP server.")
                mcp_stopped = True
            except Exception as e:
                click.echo(f"⚠️  Could not terminate MCP server: {e}", err=True)
            os.remove(MCP_PIDFILE)
        except Exception as e:
            click.echo(f"❌ Failed to stop MCP server: {e}", err=True)
    else:
        click.echo("ℹ️  No MCP server running.")

    if spa_stopped or mcp_stopped:
        click.echo("✅ Services stopped successfully.")
    else:
        click.echo("ℹ️  No services were running.")


@click.command("app-registration")
@click.option(
    "--tenant-id",
    help="Azure tenant ID for the app registration",
    required=False,
)
@click.option(
    "--name",
    default="Azure Tenant Grapher",
    help="Display name for the app registration",
)
@click.option(
    "--redirect-uri",
    default="http://localhost:3000",
    help="Redirect URI for the app registration",
)
@click.option(
    "--create-secret",
    is_flag=True,
    default=True,
    help="Create a client secret for the app registration",
)
@click.option(
    "--save-to-env",
    is_flag=True,
    default=False,
    help="Automatically save configuration to .env file",
)
def app_registration_command(
    tenant_id: Optional[str],
    name: str,
    redirect_uri: str,
    create_secret: bool,
    save_to_env: bool,
):
    """Create an Azure AD app registration for Azure Tenant Grapher.

    This command guides you through creating an Azure AD application registration
    with the necessary permissions for Azure Tenant Grapher to function properly.

    The app registration will be configured with:
    - Microsoft Graph API permissions (User.Read, Directory.Read.All)
    - Azure Management API permissions (user_impersonation)
    - Optional client secret for authentication

    You can either:
    1. Run this command with Azure CLI installed to automatically create the registration
    2. Follow the manual instructions provided to create it through the Azure Portal
    """
    import subprocess

    click.echo("🔐 Azure AD App Registration Setup")
    click.echo("=" * 50)

    # Check if Azure CLI is installed
    try:
        result = subprocess.run(
            ["az", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        has_azure_cli = result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        has_azure_cli = False

    if not has_azure_cli:
        click.echo("⚠️  Azure CLI not detected. Showing manual instructions...")
        click.echo("\n📋 Manual App Registration Steps:")
        click.echo("\n1. Navigate to Azure Portal (https://portal.azure.com)")
        click.echo(
            "2. Go to Azure Active Directory → App registrations → New registration"
        )
        click.echo(f"3. Name: {name}")
        click.echo("4. Supported account types: Single tenant")
        click.echo(f"5. Redirect URI: Web - {redirect_uri}")
        click.echo("\n6. After creation, go to API permissions and add:")
        click.echo("   - Microsoft Graph:")
        click.echo("     • User.Read (Delegated)")
        click.echo("     • Directory.Read.All (Application)")
        click.echo("   - Azure Service Management:")
        click.echo("     • user_impersonation (Delegated)")
        click.echo("\n7. Grant admin consent for the permissions")
        if create_secret:
            click.echo("\n8. Go to Certificates & secrets → New client secret")
            click.echo("   - Description: Azure Tenant Grapher")
            click.echo("   - Expires: Choose appropriate expiration")
            click.echo("\n9. Copy the following values to your .env file:")
            click.echo("   - AZURE_CLIENT_ID = <Application (client) ID>")
            click.echo("   - AZURE_CLIENT_SECRET = <Client secret value>")
            click.echo("   - AZURE_TENANT_ID = <Directory (tenant) ID>")
        return

    # Azure CLI is available, proceed with automated creation
    click.echo("✅ Azure CLI detected. Proceeding with automated setup...")

    # Check current user's permissions
    click.echo("\n🔍 Checking your permissions...")

    # Get current user info
    user_result = subprocess.run(
        [
            "az",
            "ad",
            "signed-in-user",
            "show",
            "--query",
            "{id:id,displayName:displayName,userPrincipalName:userPrincipalName}",
            "-o",
            "json",
        ],
        capture_output=True,
        text=True,
    )

    if user_result.returncode == 0:
        user_info = json.loads(user_result.stdout)
        click.echo(
            f"   Signed in as: {user_info.get('displayName', 'Unknown')} ({user_info.get('userPrincipalName', 'Unknown')})"
        )

        # Check if user has admin roles
        roles_result = subprocess.run(
            [
                "az",
                "role",
                "assignment",
                "list",
                "--assignee",
                user_info["id"],
                "--query",
                "[].roleDefinitionName",
                "-o",
                "json",
            ],
            capture_output=True,
            text=True,
        )

        if roles_result.returncode == 0:
            roles = json.loads(roles_result.stdout)
            admin_roles = [
                r
                for r in roles
                if any(
                    admin in r.lower()
                    for admin in ["administrator", "owner", "contributor"]
                )
            ]

            if admin_roles:
                click.echo(f"   Your roles: {', '.join(admin_roles[:3])}")
                if (
                    "Global Administrator" in roles
                    or "Application Administrator" in roles
                ):
                    click.echo(
                        "   ✅ You have sufficient permissions to grant admin consent"
                    )
                else:
                    click.echo(
                        "   ⚠️  You can create apps but may need a Global Admin to grant consent"
                    )
            else:
                click.echo(
                    "   ⚠️  Limited permissions detected - some operations may fail"
                )

        # Check if user can create applications
        can_create_apps = subprocess.run(
            ["az", "ad", "app", "list", "--query", "[0].id", "-o", "tsv"],
            capture_output=True,
            text=True,
        )

        if can_create_apps.returncode != 0:
            click.echo("   ❌ You don't have permission to create app registrations")
            click.echo("   Please contact your Azure AD administrator")
            return

    # Get or use provided tenant ID
    if not tenant_id:
        try:
            result = subprocess.run(
                ["az", "account", "show", "--query", "tenantId", "-o", "tsv"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                tenant_id = result.stdout.strip()
                click.echo(f"📍 Using current tenant: {tenant_id}")
            else:
                click.echo(
                    "❌ Could not determine tenant ID. Please provide --tenant-id",
                    err=True,
                )
                return
        except subprocess.SubprocessError as e:
            click.echo(f"❌ Failed to get tenant ID: {e}", err=True)
            return

    # Create the app registration
    click.echo(f"\n📝 Creating app registration '{name}'...")

    manifest = {
        "requiredResourceAccess": [
            {
                "resourceAppId": "00000003-0000-0000-c000-000000000000",  # Microsoft Graph
                "resourceAccess": [
                    {
                        "id": "e1fe6dd8-ba31-4d61-89e7-88639da4683d",  # User.Read
                        "type": "Scope",
                    },
                    {
                        "id": "7ab1d382-f21e-4acd-a863-ba3e13f7da61",  # Directory.Read.All
                        "type": "Role",
                    },
                ],
            },
            {
                "resourceAppId": "797f4846-ba00-4fd7-ba43-dac1f8f63013",  # Azure Service Management
                "resourceAccess": [
                    {
                        "id": "41094075-9dad-400e-a0bd-54e686782033",  # user_impersonation
                        "type": "Scope",
                    }
                ],
            },
        ],
        "web": {"redirectUris": [redirect_uri]},
    }

    # Save manifest to temp file
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(manifest, f)
        manifest_path = f.name

    try:
        # Create the app
        result = subprocess.run(
            [
                "az",
                "ad",
                "app",
                "create",
                "--display-name",
                name,
                "--sign-in-audience",
                "AzureADMyOrg",
                "--required-resource-accesses",
                f"@{manifest_path}",
                "--query",
                "{appId:appId, objectId:id}",
                "-o",
                "json",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            click.echo(
                f"❌ Failed to create app registration: {result.stderr}", err=True
            )
            return

        app_info = json.loads(result.stdout)
        app_id = app_info["appId"]
        object_id = app_info["objectId"]

        click.echo("✅ App registration created successfully!")
        click.echo(f"   Client ID: {app_id}")
        click.echo(f"   Object ID: {object_id}")

        # Create service principal
        click.echo("\n📝 Creating service principal...")
        result = subprocess.run(
            ["az", "ad", "sp", "create", "--id", app_id],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            click.echo(
                f"⚠️  Failed to create service principal: {result.stderr}", err=True
            )
        else:
            click.echo("✅ Service principal created")

        # Create client secret if requested
        client_secret = None
        if create_secret:
            click.echo("\n🔑 Creating client secret...")
            result = subprocess.run(
                [
                    "az",
                    "ad",
                    "app",
                    "credential",
                    "reset",
                    "--id",
                    app_id,
                    "--display-name",
                    "Azure Tenant Grapher Secret",
                    "--years",
                    "2",  # Valid for 2 years
                    "--query",
                    "password",
                    "-o",
                    "tsv",
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                click.echo(
                    f"❌ Failed to create client secret: {result.stderr}", err=True
                )
            else:
                client_secret = result.stdout.strip()
                click.echo("✅ Client secret created successfully!")

        # Try to grant admin consent automatically
        click.echo("\n🔐 Attempting to grant admin consent...")
        consent_result = subprocess.run(
            ["az", "ad", "app", "permission", "admin-consent", "--id", app_id],
            capture_output=True,
            text=True,
        )

        consent_granted = False
        if consent_result.returncode == 0:
            click.echo("✅ Admin consent granted successfully!")
            consent_granted = True
        else:
            if (
                "AADSTS50058" in consent_result.stderr
                or "signed in" in consent_result.stderr.lower()
            ):
                click.echo(
                    "⚠️  Cannot grant admin consent automatically - requires interactive login as Global Administrator"
                )
            else:
                click.echo(f"⚠️  Admin consent failed: {consent_result.stderr}")

        # Save to .env file if requested
        if save_to_env:
            env_file_path = os.path.join(os.getcwd(), ".env")
            click.echo(f"\n💾 Saving configuration to {env_file_path}...")

            # Read existing .env file if it exists
            env_vars = {}
            if os.path.exists(env_file_path):
                with open(env_file_path) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, value = line.split("=", 1)
                            env_vars[key.strip()] = value.strip()

            # Update with new values
            env_vars["AZURE_TENANT_ID"] = tenant_id
            env_vars["AZURE_CLIENT_ID"] = app_id
            if client_secret:
                env_vars["AZURE_CLIENT_SECRET"] = client_secret

            # Write back to file
            with open(env_file_path, "w") as f:
                for key, value in env_vars.items():
                    f.write(f"{key}={value}\n")

            click.echo("✅ Configuration saved to .env file!")

        # Display configuration
        click.echo("\n" + "=" * 50)
        click.echo("📋 Configuration for .env file:")
        click.echo("=" * 50)
        click.echo(f"AZURE_TENANT_ID={tenant_id}")
        click.echo(f"AZURE_CLIENT_ID={app_id}")
        if client_secret:
            click.echo(f"AZURE_CLIENT_SECRET={client_secret}")
        click.echo("=" * 50)

        # Display next steps with proper numbering
        click.echo("\n✅ Next steps:")
        step_num = 1

        if not save_to_env:
            click.echo(f"{step_num}. Copy the above configuration to your .env file")
            step_num += 1

        if client_secret:
            click.echo(
                f"{step_num}. Store the client secret securely - it won't be shown again"
            )
            step_num += 1

        if not consent_granted:
            click.echo(f"{step_num}. Grant admin consent for the API permissions:")
            click.echo(
                f"   Option A: Run as Global Admin: az ad app permission admin-consent --id {app_id}"
            )
            click.echo(
                f"   Option B: Use Azure Portal: Azure AD → App registrations → {name} → API permissions → Grant admin consent"
            )
            click.echo(
                f"   Option C: Use consent URL: https://login.microsoftonline.com/{tenant_id}/adminconsent?client_id={app_id}"
            )
            step_num += 1

        click.echo("\n✨ App registration setup complete!")

    finally:
        # Clean up temp file
        if os.path.exists(manifest_path):
            os.remove(manifest_path)


async def mcp_query_command(
    ctx: click.Context,
    query: str,
    tenant_id: Optional[str] = None,
    use_fallback: bool = True,
    output_format: str = "json",
    debug: bool = False,
) -> None:
    """
    Execute natural language queries using MCP (Model Context Protocol).
    
    This command ensures MCP server is running and executes natural language
    queries against Azure resources.
    """
    from src.config_manager import MCPConfig, create_config_from_env
    from src.services.mcp_integration import MCPIntegrationService
    from src.services.azure_discovery_service import AzureDiscoveryService
    from src.utils.mcp_startup import ensure_mcp_running_async
    
    # Set up logging
    log_level = ctx.obj.get("log_level", "INFO")
    if debug:
        log_level = "DEBUG"
    
    # Get tenant ID
    effective_tenant_id = tenant_id or os.environ.get("AZURE_TENANT_ID")
    if not effective_tenant_id:
        click.echo(
            "❌ No tenant ID provided and AZURE_TENANT_ID not set in environment.",
            err=True,
        )
        sys.exit(1)
    
    # Create configuration
    config = create_config_from_env(effective_tenant_id, debug=debug)
    setup_logging(config.logging)
    
    # Check if MCP is configured
    if not config.mcp.enabled:
        click.echo("ℹ️  MCP is not enabled. Set MCP_ENABLED=true in your .env file to enable.")
        click.echo("❌ MCP is required for natural language queries. Please enable it first.")
        sys.exit(1)
    
    # Ensure MCP server is running
    click.echo("🚀 Ensuring MCP server is running...")
    try:
        await ensure_mcp_running_async(debug=debug)
        click.echo("✅ MCP server is ready")
    except RuntimeError as e:
        click.echo(f"❌ Failed to start MCP server: {e}", err=True)
        sys.exit(1)
    
    # Initialize services
    discovery_service = None
    if use_fallback:
        try:
            discovery_service = AzureDiscoveryService(config)
            click.echo("✅ Traditional discovery service initialized as fallback")
        except Exception as e:
            click.echo(f"⚠️  Warning: Could not initialize discovery service: {e}")
    
    mcp_service = MCPIntegrationService(config.mcp, discovery_service)
    
    try:
        # Connect to MCP
        click.echo(f"🔌 Connecting to MCP at {config.mcp.endpoint}...")
        connected = await mcp_service.initialize()
        
        if not connected:
            click.echo("❌ MCP connection failed after server startup", err=True)
            click.echo("Please check the MCP server logs for errors.")
            sys.exit(1)
        
        click.echo("✅ MCP connection established")
        
        # Execute the query
        click.echo(f"\n📝 Executing query: {query}")
        click.echo("-" * 60)
        
        success, result = await mcp_service.natural_language_command(query)
        
        if success:
            click.echo("✅ Query executed successfully\n")
            
            # Format and display results
            if output_format == "json":
                formatted_result = json.dumps(result, indent=2)
                click.echo(formatted_result)
            elif output_format == "table":
                # Simple table formatting for resource lists
                if isinstance(result, dict) and "response" in result:
                    response = result["response"]
                    if isinstance(response, list):
                        click.echo("Resources found:")
                        click.echo("-" * 60)
                        for item in response:
                            if isinstance(item, dict):
                                name = item.get("name", "Unknown")
                                res_type = item.get("type", "Unknown")
                                location = item.get("location", "Unknown")
                                click.echo(f"  • {name} ({res_type}) - {location}")
                    else:
                        click.echo(str(response))
                else:
                    click.echo(str(result))
            else:
                # Plain text output
                if isinstance(result, dict):
                    if "response" in result:
                        click.echo(str(result["response"]))
                    else:
                        for key, value in result.items():
                            click.echo(f"{key}: {value}")
                else:
                    click.echo(str(result))
        else:
            click.echo("❌ Query failed\n")
            if isinstance(result, dict):
                if "error" in result:
                    click.echo(f"Error: {result['error']}")
                if "suggestion" in result:
                    click.echo(f"💡 Suggestion: {result['suggestion']}")
            else:
                click.echo(f"Error: {result}")
    
    except KeyboardInterrupt:
        click.echo("\n⚠️  Query interrupted by user")
        sys.exit(130)
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}", err=True)
        if debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)
    finally:
        # Clean up
        await mcp_service.close()
        click.echo("\n✅ MCP session closed")
