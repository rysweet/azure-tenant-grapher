"""Scan/build commands.

This module provides the core scanning commands:
- 'build': Build Azure tenant graph
- 'scan': Alias for build
- 'test': Run a quick test scan with limited resources

Issue #482: CLI Modularization
Issue #722: Core scan logic migrated from cli_commands.py
"""

import logging
import os
import sys
from typing import TYPE_CHECKING, Optional

import click
import structlog  # type: ignore[import-untyped]

from src.azure_tenant_grapher import AzureTenantGrapher
from src.cli_dashboard_manager import CLIDashboardManager
from src.commands.base import async_command
from src.config_manager import (
    create_config_from_env,
    setup_logging,
)
from src.logging_config import configure_logging
from src.models.filter_config import FilterConfig
from src.rich_dashboard import RichDashboard
from src.utils.graph_id_resolver import split_and_detect_ids
from src.utils.neo4j_startup import ensure_neo4j_running

configure_logging()

if TYPE_CHECKING:
    from src.config_manager import AzureTenantGrapherConfig


async def build_command_handler(
    ctx: click.Context,
    tenant_id: str,
    resource_limit: Optional[int],
    max_llm_threads: int,
    max_build_threads: int,
    max_retries: int,
    max_concurrency: int,
    no_container: bool,
    generate_spec: bool,
    visualize: bool,
    no_dashboard: bool,
    test_keypress_queue: bool,
    test_keypress_file: str,
    rebuild_edges: bool = False,
    no_aad_import: bool = False,
    debug: bool = False,
    filter_by_subscriptions: Optional[str] = None,
    filter_by_rgs: Optional[str] = None,
    no_include_references: bool = False,
) -> str | None:
    """Handle the build command logic."""
    if debug:
        print("[DEBUG][CLI] Entered build_command_handler", flush=True)
    ensure_neo4j_running(debug)
    if debug:
        print("[DEBUG][CLI] ensure_neo4j_running() complete", flush=True)

    # Version check (Issue #706) - non-blocking warning
    try:
        # Get Neo4j config for version check
        from src.commands.base import get_neo4j_config_from_env
        from src.neo4j_session_manager import Neo4jSessionManager
        from src.version_tracking.detector import VersionDetector
        from src.version_tracking.metadata import GraphMetadataService

        uri, user, password = get_neo4j_config_from_env()
        session_manager = Neo4jSessionManager(uri=uri, user=user, password=password)
        metadata_service = GraphMetadataService(session_manager)
        detector = VersionDetector()

        # Detect version mismatch
        mismatch = detector.detect_mismatch(metadata_service)

        if mismatch:
            click.echo()
            click.echo("⚠️  " + "=" * 70)
            click.echo("⚠️  VERSION MISMATCH DETECTED")
            click.echo("⚠️  " + "=" * 70)
            click.echo(
                f"⚠️  Semaphore version: {mismatch.get('semaphore_version', 'N/A')}"
            )
            click.echo(
                f"⚠️  Metadata version:  {mismatch.get('metadata_version', 'N/A')}"
            )
            click.echo(f"⚠️  Reason: {mismatch.get('reason', 'Unknown')}")
            click.echo()
            click.echo(
                "⚠️  The graph will be updated with the current version after scanning."
            )
            click.echo("⚠️  To rebuild the graph from scratch, run:")
            click.echo("⚠️    atg rebuild-graph --tenant-id <YOUR_TENANT_ID>")
            click.echo("⚠️  " + "=" * 70)
            click.echo()
    except Exception as e:
        if debug:
            click.echo(f"[DEBUG] Version check warning (non-fatal): {e}", err=True)

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
            effective_tenant_id,
            resource_limit,
            max_retries,
            max_build_threads,
            max_concurrency,
            debug,
        )
        # max_concurrency already set by create_config_from_env, don't override
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

        # Create FilterConfig from CLI parameters
        filter_config = None
        if filter_by_subscriptions or filter_by_rgs:
            subscription_ids = []
            resource_group_names = []

            if filter_by_subscriptions:
                subscription_ids = [
                    s.strip() for s in filter_by_subscriptions.split(",")
                ]
                logger.info(str(f"📋 Filtering by subscriptions: {subscription_ids}"))

            if filter_by_rgs:
                # Split and detect which values are graph IDs vs actual names
                regular_names, graph_ids = split_and_detect_ids(filter_by_rgs)

                if graph_ids:
                    logger.warning(
                        f"⚠️  Detected graph database IDs in resource group filter: {graph_ids}\n"
                        f"   These appear to be internal database IDs rather than Azure resource group names.\n"
                        f"   Please use actual resource group names (e.g., 'Ballista_UCAScenario') instead.\n"
                        f"   You can find the actual names in the Neo4j database or Azure portal."
                    )

                    # For now, we'll skip the graph IDs and only use the regular names
                    # In a future improvement, we could resolve these IDs to actual names
                    if regular_names:
                        logger.info(
                            f"📋 Using valid resource group names: {regular_names}"
                        )
                        resource_group_names = regular_names
                    else:
                        logger.error(
                            "❌ No valid resource group names found. All provided values appear to be graph IDs.\n"
                            "   Please provide actual Azure resource group names."
                        )
                        resource_group_names = []
                else:
                    resource_group_names = regular_names
                    logger.info(
                        f"📋 Filtering by resource groups: {resource_group_names}"
                    )

            try:
                filter_config = FilterConfig(
                    subscription_ids=subscription_ids,
                    resource_group_names=resource_group_names,
                    include_referenced_resources=not no_include_references,
                )
            except ValueError as e:
                logger.error(str(f"❌ Invalid filter configuration: {e}"))
                logger.info(
                    "💡 Tip: Make sure you're using actual Azure resource names, not database IDs.\n"
                    "   Resource group names should only contain alphanumeric characters, hyphens, underscores, periods, and parentheses."
                )
                # Create an empty filter config to continue without filtering
                filter_config = FilterConfig(
                    include_referenced_resources=not no_include_references
                )

        if no_dashboard:
            print("[DEBUG][CLI] Entering _run_no_dashboard_mode", flush=True)
            await _run_no_dashboard_mode(
                ctx, grapher, logger, rebuild_edges, filter_config
            )
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
                filter_config,
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
    filter_config: Optional[FilterConfig] = None,
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

    # Check if we're running from Electron app (SPA)
    is_electron = (
        os.environ.get("ELECTRON_RUN_AS_NODE") == "1"
        or os.environ.get("IS_ELECTRON_APP") == "true"
        or os.environ.get("PYTHONUNBUFFERED") == "1"
    )

    if is_electron:
        # Use simple StreamHandler for Electron to capture all output
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        handler.setLevel(level_map.get(cli_log_level, logging.INFO))
        root_logger.addHandler(handler)
        # Force flush for immediate output
        sys.stdout = sys.stdout
        sys.stderr = sys.stderr
    else:
        # Use RichHandler for terminal output
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
                result = await grapher.build_graph(
                    force_rebuild_edges=True, filter_config=filter_config
                )
                print(
                    "[DEBUG][CLI] Awaited grapher.build_graph(force_rebuild_edges=True)",
                    flush=True,
                )
            else:
                result = await grapher.build_graph(filter_config=filter_config)
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
            "You can start the container with 'atg container' or 'docker-compose -f docker/docker-compose.yml up -d neo4j'.",
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
    filter_config: Optional[FilterConfig] = None,
) -> str | None:
    """Run build in dashboard mode with Rich UI."""
    print("[DEBUG][CLI] Entered _run_dashboard_mode", flush=True)

    logger.info("[DEBUG] Entered _run_dashboard_mode")
    # Setup RichDashboard with both thread parameters and filter config
    dashboard = RichDashboard(
        config=config.to_dict(),
        max_llm_threads=max_llm_threads,
        max_build_threads=getattr(config.processing, "max_build_threads", 20),
        filter_config=filter_config,
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
            "You can start the container with 'atg container' or 'docker-compose -f docker/docker-compose.yml up -d neo4j'."
        )
        click.echo(
            f"❌ Failed to connect to Neo4j: {e}\n"
            "Action: Ensure Neo4j is running and accessible at the configured URI.\n"
            "If using Docker, check that the container is started and healthy.\n"
            "You can start the container with 'atg container' or 'docker-compose -f docker/docker-compose.yml up -d neo4j'.",
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

    # Create dashboard manager with filter config
    dashboard_manager = CLIDashboardManager(dashboard, filter_config=filter_config)

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
                    progress_callback=progress_callback,
                    force_rebuild_edges=True,
                    filter_config=filter_config,
                )
            )
        else:
            build_task = asyncio.create_task(
                grapher.build_graph(
                    progress_callback=progress_callback, filter_config=filter_config
                )
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
            logger.error(str(f"[DEBUG] Error during cleanup: {e}"))
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


@click.command("build")
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
@click.option(
    "--max-build-threads",
    type=int,
    default=20,
    help="Maximum concurrent API calls for fetching resource details (default: 20)",
)
@click.option(
    "--max-retries",
    type=int,
    default=3,
    help="Maximum number of retries for failed resources (default: 3)",
)
@click.option(
    "--max-concurrency",
    type=int,
    default=100,
    help="Maximum concurrent resource processing workers (default: 100)",
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
@click.option(
    "--test-keypress-queue",
    is_flag=True,
    help="Enable test mode for dashboard keypresses (for integration tests only)",
)
@click.option(
    "--test-keypress-file",
    type=str,
    default="",
    help="Path to file containing simulated keypresses (for integration tests only)",
)
@click.option(
    "--rebuild-edges",
    is_flag=True,
    help="Force re-evaluation of all relationships/edges for all resources in the graph database",
)
@click.option(
    "--no-aad-import",
    is_flag=True,
    help="Disable Azure AD user/group import from Microsoft Graph API",
)
@click.option(
    "--filter-by-subscriptions",
    type=str,
    help="Comma-separated list of subscription IDs to include (filters discovery)",
)
@click.option(
    "--filter-by-rgs",
    type=str,
    help="Comma-separated list of resource group names to include (filters discovery)",
)
@click.option(
    "--no-include-references",
    is_flag=True,
    help="Disable automatic inclusion of referenced resources (identities, RBAC principals)",
)
@click.pass_context
@async_command
async def build(
    ctx: click.Context,
    tenant_id: str,
    resource_limit: Optional[int],
    max_llm_threads: int,
    max_build_threads: int,
    max_retries: int,
    max_concurrency: int,
    no_container: bool,
    generate_spec: bool,
    visualize: bool,
    no_dashboard: bool,
    test_keypress_queue: bool,
    test_keypress_file: str,
    rebuild_edges: bool = False,
    no_aad_import: bool = False,
    filter_by_subscriptions: Optional[str] = None,
    filter_by_rgs: Optional[str] = None,
    no_include_references: bool = False,
) -> Optional[str]:
    """
    Build the complete Azure tenant graph with enhanced processing.

    By default, shows a live Rich dashboard with progress, logs, and interactive controls:
      - Press 'x' to exit the dashboard at any time.
      - Press 'i', 'd', or 'w' to set log level to INFO, DEBUG, or WARNING.

    Use --no-dashboard to disable the dashboard and emit logs line by line to the terminal.
    """
    # Import the handler from cli_commands to maintain backward compatibility

    debug = ctx.obj.get("debug", False)
    if debug:
        print("[DEBUG] CLI build command called", flush=True)
    result = await build_command_handler(
        ctx,
        tenant_id,
        resource_limit,
        max_llm_threads,
        max_build_threads,
        max_retries,
        max_concurrency,
        no_container,
        generate_spec,
        visualize,
        no_dashboard,
        test_keypress_queue,
        test_keypress_file,
        rebuild_edges,
        no_aad_import,
        debug,
        filter_by_subscriptions,
        filter_by_rgs,
        no_include_references,
    )
    if debug:
        print(f"[DEBUG] build_command_handler returned: {result!r}", flush=True)
    return result


@click.command("scan")
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
@click.option(
    "--max-build-threads",
    type=int,
    default=20,
    help="Maximum concurrent API calls for fetching resource details (default: 20)",
)
@click.option(
    "--max-retries",
    type=int,
    default=3,
    help="Maximum number of retries for failed resources (default: 3)",
)
@click.option(
    "--max-concurrency",
    type=int,
    default=100,
    help="Maximum concurrent resource processing workers (default: 100)",
)
@click.option("--no-container", is_flag=True, help="Do not auto-start Neo4j container")
@click.option(
    "--generate-spec",
    is_flag=True,
    help="Generate tenant specification after graph scanning",
)
@click.option(
    "--visualize",
    is_flag=True,
    help="Generate graph visualization after scanning",
)
@click.option(
    "--no-dashboard",
    is_flag=True,
    help="Disable the Rich dashboard and emit logs line by line",
)
@click.option(
    "--test-keypress-queue",
    is_flag=True,
    help="Enable test mode for dashboard keypresses (for integration tests only)",
)
@click.option(
    "--test-keypress-file",
    type=str,
    default="",
    help="Path to file containing simulated keypresses (for integration tests only)",
)
@click.option(
    "--rebuild-edges",
    is_flag=True,
    help="Force re-evaluation of all relationships/edges for all resources in the graph database",
)
@click.option(
    "--no-aad-import",
    is_flag=True,
    help="Disable Azure AD user/group import from Microsoft Graph API",
)
@click.option(
    "--filter-by-subscriptions",
    type=str,
    help="Comma-separated list of subscription IDs to include (filters discovery)",
)
@click.option(
    "--filter-by-rgs",
    type=str,
    help="Comma-separated list of resource group names to include (filters discovery)",
)
@click.pass_context
@async_command
async def scan(
    ctx: click.Context,
    tenant_id: str,
    resource_limit: Optional[int],
    max_llm_threads: int,
    max_build_threads: int,
    max_retries: int,
    max_concurrency: int,
    no_container: bool,
    generate_spec: bool,
    visualize: bool,
    no_dashboard: bool,
    test_keypress_queue: bool,
    test_keypress_file: str,
    rebuild_edges: bool = False,
    no_aad_import: bool = False,
    filter_by_subscriptions: Optional[str] = None,
    filter_by_rgs: Optional[str] = None,
) -> Optional[str]:
    """
    Scan the complete Azure tenant graph with enhanced processing.

    This command discovers all resources in your Azure tenant and builds a comprehensive
    Neo4j graph database. By default, shows a live Rich dashboard with progress, logs,
    and interactive controls:
      - Press 'x' to exit the dashboard at any time.
      - Press 'i', 'd', or 'w' to set log level to INFO, DEBUG, or WARNING.

    Use --no-dashboard to disable the dashboard and emit logs line by line to the terminal.
    """
    # Import the handler from cli_commands to maintain backward compatibility

    debug = ctx.obj.get("debug", False)
    if debug:
        print("[DEBUG] CLI scan command called", flush=True)
    result = await build_command_handler(
        ctx,
        tenant_id,
        resource_limit,
        max_llm_threads,
        max_build_threads,
        max_retries,
        max_concurrency,
        no_container,
        generate_spec,
        visualize,
        no_dashboard,
        test_keypress_queue,
        test_keypress_file,
        rebuild_edges,
        no_aad_import,
        debug,
        filter_by_subscriptions,
        filter_by_rgs,
        no_include_references,
    )
    if debug:
        print(
            f"[DEBUG] scan command (via build_command_handler) returned: {result!r}",
            flush=True,
        )
    return result


@click.command("test")
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
            "No tenant ID provided and AZURE_TENANT_ID not set in environment.",
            err=True,
        )
        sys.exit(1)

    click.echo(f"Running test mode with up to {limit} resources...")

    debug = ctx.obj.get("debug", False)
    await build_command_handler(
        ctx,
        effective_tenant_id,
        limit,  # resource_limit
        3,  # max_llm_threads
        20,  # max_build_threads
        3,  # max_retries
        100,  # max_concurrency
        False,  # no_container
        False,  # generate_spec
        False,  # visualize
        False,  # no_dashboard
        False,  # test_keypress_queue
        "",  # test_keypress_file
        False,  # rebuild_edges
        False,  # no_aad_import
        debug,  # debug
        None,  # filter_by_subscriptions
        None,  # filter_by_rgs
    )


# For backward compatibility
build_command = build
scan_command = scan
test_command = test

__all__ = [
    "build",
    "build_command",
    "scan",
    "scan_command",
    "test",
    "test_command",
]
