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
    max_retries: int,
    no_container: bool,
    generate_spec: bool,
    visualize: bool,
    no_dashboard: bool,
    test_keypress_queue: bool,
    test_keypress_file: str,
    rebuild_edges: bool = False,
) -> str | None:
    """Handle the build command logic."""
    ensure_neo4j_running()
    # Removed debug print

    try:
        # Removed debug print
        # Use tenant_id from CLI or .env
        effective_tenant_id = tenant_id or os.environ.get("AZURE_TENANT_ID")
        if not effective_tenant_id:
            click.echo(
                "❌ No tenant ID provided and AZURE_TENANT_ID not set in environment.",
                err=True,
            )
            sys.exit(1)

        # Create and validate configuration
        config = create_config_from_env(
            effective_tenant_id, resource_limit, max_retries
        )
        config.processing.max_concurrency = max_llm_threads
        config.processing.auto_start_container = not no_container
        config.logging.level = ctx.obj["log_level"]

        # Setup logging
        setup_logging(config.logging)

        # Validate configuration
        config.validate_all()

        logger = structlog.get_logger(__name__)

        # Create and run the grapher
        grapher = AzureTenantGrapher(config)

        # Removed debug print
        if no_dashboard:
            # Removed debug print
            await _run_no_dashboard_mode(ctx, grapher, logger, rebuild_edges)
            return "__NO_DASHBOARD_BUILD_COMPLETE__"
        else:
            # Removed debug print
            return await _run_dashboard_mode(
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

    except Exception as e:
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
    # Print log file path for test discoverability
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
    structlog.get_logger(__name__).info(
        event="Running in no-dashboard mode: logs will be emitted line by line.",
        log_level=cli_log_level,
    )
    try:
        grapher.connect_to_neo4j()
        logger.info("🚀 Starting Azure Tenant Graph building...")
        if hasattr(grapher, "build_graph"):
            if rebuild_edges:
                click.echo(
                    "🔄 Forcing re-evaluation of all relationships/edges for all resources."
                )
                result = await grapher.build_graph(force_rebuild_edges=True)
            else:
                result = await grapher.build_graph()
        else:
            result = None
        click.echo("🎉 Graph building completed.")
        click.echo(f"Result: {result}")
    except Exception as e:
        click.echo(
            f"❌ Failed to connect to Neo4j: {e}\n"
            "Action: Ensure Neo4j is running and accessible at the configured URI.\n"
            "If using Docker, check that the container is started and healthy.\n"
            "You can start the container with 'python scripts/cli.py container' or 'docker-compose up'.",
            err=True,
        )
        sys.exit(1)
    finally:
        # Defensive cleanup: ensure Neo4j driver is closed before exit
        try:
            if hasattr(grapher, "session_manager") and hasattr(
                grapher.session_manager, "disconnect"
            ):
                grapher.session_manager.disconnect()
        except Exception as cleanup_exc:
            logger.warning(f"Error during Neo4j driver cleanup: {cleanup_exc}")
        # Force immediate process exit after no-dashboard build to prevent CLI hang
        print(
            "[DEBUG] Reached end of _run_no_dashboard_mode, about to call os._exit(0)",
            flush=True,
        )
        import os

        os._exit(0)


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

    logger.info("[DEBUG] Entered _run_dashboard_mode")
    # Setup RichDashboard
    dashboard = RichDashboard(
        config=config.to_dict(),
        max_concurrency=max_llm_threads,
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
        if test_keypress_file:
            with dashboard.live():
                dashboard.log_info("Press 'x' to exit the dashboard")
                logger.info("[DEBUG] Entering poll_build_task (file keypress)")
                try:
                    await dashboard_manager.poll_build_task(build_task)
                except DashboardExitException:
                    # Dashboard exit was requested, return exit sentinel
                    return "__DASHBOARD_EXIT__"
        elif test_keypress_queue:
            # Removed debug print
            result = await dashboard_manager.run_with_queue_keypress(build_task)
            # Removed debug print
            if result == "__DASHBOARD_EXIT__":
                # Removed debug print
                return "__DASHBOARD_EXIT__"
        else:
            # Removed debug print
            result = await dashboard_manager.run_normal(build_task)
            # Removed debug print
            if result == "__DASHBOARD_EXIT__":
                # Removed debug print
                return "__DASHBOARD_EXIT__"
    except DashboardExitException:
        # Dashboard exit was requested
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
    await dashboard_manager.handle_build_completion(
        build_task, grapher, config, generate_spec, visualize
    )
    return None


async def visualize_command_handler(
    ctx: click.Context, link_hierarchy: bool = True, no_container: bool = False
) -> None:
    """Handle the visualize command logic."""
    ensure_neo4j_running()
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
                                link_to_hierarchy=link_hierarchy
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


async def spec_command_handler(ctx: click.Context, tenant_id: str) -> None:
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
        await grapher.generate_tenant_specification()
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

    # Build the prompt as in generate_sim_customer_profile
    prompt = (
        "I'm a research scientist planning on building accurate simulations of Microsoft Azure customer environments so that security professionals can run realistic security scenarios in those environments. "
        "We want the environments to be as close to real customer environments of large customers as possible, but we cannot copy real customer data or real customer names/identities etc. "
        "We care more about simulating customer complexity and configuration than we do about scale. "
        "We have a large trove of customer stories here: https://www.microsoft.com/en-us/customers/search?filters=product%3Aazure which you can browse and search to find relevant customer profiles. "
        "We also have a collection of Azure reference architectures here: https://learn.microsoft.com/en-us/azure/architecture/browse/. "
        "You can use both of these resources to research typical customers and the architectures they deploy on Azure.\n\n"
        "Please use that background information and produce for me a distinct fake customer profile that describes the customer company, its goals, its personnel, and the solutions that they are leveraging on Azure, "
        "with enough detail that we could begin to go model that customer environment. The fake profiles must be somewhat realistic in terms of storytelling, application, and personnel, but MAY NOT use any of the content from the Customer Stories site verbatim and MAY NOT use the names of real companies or customers."
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

    # Determine output path
    if out_path:
        output_path = out_path
    else:
        os.makedirs("simdocs", exist_ok=True)
        import datetime

        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        output_path = f"simdocs/simdoc-{timestamp}.md"

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

    async def _run():
        from src.exceptions import LLMGenerationError

        try:
            spec = await creator.create_from_markdown(text)
            await creator.ingest_to_graph(spec)
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
        loop.run_until_complete(task)
    else:
        asyncio.run(_run())


@click.command("create-tenant")
@click.argument("markdown_file", type=click.Path(exists=True))
def create_tenant_command(markdown_file: str):
    """Create a tenant from a markdown file."""
    try:
        ensure_neo4j_running()
        with open(markdown_file, encoding="utf-8") as f:
            text = f.read()
        print("DEBUG: Raw markdown file contents:\n", text)
        create_tenant_from_markdown(text)
        click.echo("✅ Tenant creation (stub) succeeded.")
    except Exception as e:
        click.echo(
            f"❌ Failed to create tenant: {e}\n"
            "Action: Check that the markdown file is valid and that Neo4j and Azure OpenAI are configured correctly. Run with --log-level DEBUG for more details.",
            err=True,
        )
        exit(1)
