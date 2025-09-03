#!/usr/bin/env python3
"""
Enhanced CLI wrapper for Azure Tenant Grapher

This script provides an improved command-line interface with better error handling,
configuration validation, and progress tracking.
"""

import asyncio
import functools

# ensure_neo4j_running import removed (module does not exist)
import logging
import os
import sys
from typing import Any, Callable, Coroutine, Optional

from dotenv import load_dotenv
from rich.console import Console
from rich.logging import RichHandler
from rich.style import Style

from src.cli_commands import DashboardExitException

# Initialize console for rich output
console = Console()


def print_cli_env_block(context: str = "", debug: bool = False):
    # Only print environment variables if debug is enabled
    if debug:
        print(f"[CLI ENV DUMP]{'[' + context + ']' if context else ''}")
        for k in [
            "NEO4J_CONTAINER_NAME",
            "NEO4J_DATA_VOLUME",
            "NEO4J_PASSWORD",
            "NEO4J_PORT",
            "NEO4J_URI",
        ]:
            print(f"[CLI ENV] {k}={os.environ.get(k)}")


# We'll call this later after parsing debug flag

# Set Azure logging levels early
# Suppress verbose HTTP logging from Azure SDK and related libraries
for name in [
    "azure",
    "azure.core",
    "azure.core.pipeline",
    "azure.core.pipeline.policies",
    "azure.core.pipeline.policies.http_logging_policy",
    "azure.core.pipeline.policies.HttpLoggingPolicy",
    "azure.identity",
    "azure.mgmt",
    "msrest",
    "urllib3",
    "urllib3.connectionpool",
    "http.client",
    "requests.packages.urllib3",
    "httpx",
    "openai",
]:
    logging.getLogger(name).setLevel(logging.WARNING)


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

# (Removed duplicate import of DashboardExitException)

try:
    import click

    # (Removed: from src.cli_commands import create_tenant_command)
    from src.cli_commands import (
        app_registration_command,
        build_command_handler,
        create_tenant_command,
        generate_spec_command_handler,
        spa_start,
        spa_stop,
        spec_command_handler,
        visualize_command_handler,
    )
    from src.config_manager import create_config_from_env
    from src.iac.cli_handler import generate_iac_command_handler
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Please ensure all required packages are installed:")
    print("pip install -r requirements.txt")
    sys.exit(1)

# --- CLI installer helper imports ---
try:
    from src.utils.cli_installer import install_tool, is_tool_installed
except ImportError:

    def is_tool_installed(name: str) -> bool:
        return False

    def install_tool(tool: str) -> bool:
        print(f"Install helper unavailable. Please install {tool} manually.")
        return False


# (Removed duplicate import of DashboardExitException)


def async_command(f: Callable[..., Coroutine[Any, Any, Any]]) -> Callable[..., Any]:
    """Decorator to make Click commands async-compatible."""

    @functools.wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                # Already in an event loop (e.g., pytest-asyncio, Jupyter)
                import nest_asyncio

                nest_asyncio.apply()
                task = loop.create_task(f(*args, **kwargs))
                result = loop.run_until_complete(task)
            else:
                result = asyncio.run(f(*args, **kwargs))
            # If the async command returns a sentinel indicating dashboard exit, exit here
            if result == "__DASHBOARD_EXIT__":
                # Extract debug flag from context if available
                debug = (
                    getattr(args[0], "obj", {}).get("debug", False) if args else False
                )
                if debug:
                    print(
                        "[DEBUG] EXIT SENTINEL '__DASHBOARD_EXIT__' detected in async_command. Exiting now.",
                        file=sys.stderr,
                    )
                sys.stderr.flush()
                sys.exit(0)
            if result == "__NO_DASHBOARD_BUILD_COMPLETE__":
                # Extract debug flag from context if available
                debug = (
                    getattr(args[0], "obj", {}).get("debug", False) if args else False
                )
                if debug:
                    print(
                        "[DEBUG] EXIT SENTINEL '__NO_DASHBOARD_BUILD_COMPLETE__' detected in async_command. Exiting now.",
                        file=sys.stderr,
                    )
                sys.stderr.flush()
                sys.exit(0)
            return result
        except DashboardExitException:
            sys.exit(0)

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
        "generate-iac": "🏗️ Generate Infrastructure-as-Code templates from graph data",
        "mcp-query": "🤖 Execute natural language queries via MCP (experimental)",
        "config": "⚙️  Show current configuration template",
        "container": "🐳 Manage Neo4j Docker container",
        "backup-db": "💾 Backup Neo4j database to a local file",
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
    click.echo("📖 For detailed help on any command, use: {command} --help")
    click.echo("🌐 Documentation: https://github.com/your-repo/azure-tenant-grapher")


@click.group(invoke_without_command=True)
@click.option(
    "--log-level",
    default="INFO",
    help="Logging level (DEBUG, INFO, WARNING, ERROR)",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug output including environment variables",
)
@click.pass_context
def cli(ctx: click.Context, log_level: str, debug: bool) -> None:
    """Azure Tenant Grapher - Enhanced CLI for building Neo4j graphs of Azure resources."""
    ctx.ensure_object(dict)
    ctx.obj["log_level"] = log_level.upper()
    ctx.obj["debug"] = debug

    # Print debug environment block if debug is enabled
    print_cli_env_block("STARTUP", debug)

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
@click.pass_context
@async_command
async def build(
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
) -> str | None:
    """
    Build the complete Azure tenant graph with enhanced processing.

    By default, shows a live Rich dashboard with progress, logs, and interactive controls:
      - Press 'x' to exit the dashboard at any time.
      - Press 'i', 'd', or 'w' to set log level to INFO, DEBUG, or WARNING.

    Use --no-dashboard to disable the dashboard and emit logs line by line to the terminal.
    """
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
        no_container,
        generate_spec,
        visualize,
        no_dashboard,
        test_keypress_queue,
        test_keypress_file,
        rebuild_edges,
        no_aad_import,
        debug,
    )
    if debug:
        print(f"[DEBUG] build_command_handler returned: {result!r}", flush=True)
    return result


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
        max_llm_threads=3,
        no_container=False,
        generate_spec=False,
        visualize=False,
    )


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
    await visualize_command_handler(ctx, link_hierarchy, no_container)


@cli.command()
@click.option(
    "--tenant-id",
    required=False,
    help="Azure tenant ID (defaults to AZURE_TENANT_ID from .env)",
)
@click.pass_context
@async_command
@click.option(
    "--domain-name",
    required=False,
    help="Domain name to use for all entities that require one (e.g., user accounts)",
)
async def spec(
    ctx: click.Context, tenant_id: str, domain_name: Optional[str] = None
) -> None:
    """Generate only the tenant specification (requires existing graph)."""
    await spec_command_handler(ctx, tenant_id, domain_name)


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
    generate_spec_command_handler(ctx, limit, output)


@cli.command()
@click.option(
    "--tenant-id",
    required=False,
    help="Azure tenant ID (defaults to AZURE_TENANT_ID from .env)",
)
@click.option(
    "--format",
    "format_type",
    default="terraform",
    type=click.Choice(["terraform", "arm", "bicep"], case_sensitive=False),
    help="Target IaC format (default: terraform)",
)
@click.option(
    "--output",
    "output_path",
    help="Output directory for generated templates",
)
@click.option(
    "--rules-file",
    help="Path to transformation rules configuration file",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Validate inputs without generating templates",
)
@click.option(
    "--resource-filters",
    help="Resource type filters (comma-separated)",
)
@click.option(
    "--subset-filter",
    help="Subset filter string (e.g., 'types=Microsoft.Storage/*;nodeIds=abc123')",
)
@click.option(
    "--dest-rg",
    help="Target resource group name for Bicep module deployment",
)
@click.option(
    "--location",
    help="Target location/region for resource deployment",
)
# AAD mode is now always 'manual' (default behavior, flag removed)
@click.pass_context
@async_command
@click.option(
    "--domain-name",
    required=False,
    help="Domain name to use for all entities that require one (e.g., user accounts)",
)
async def generate_iac(
    ctx: click.Context,
    tenant_id: str,
    format_type: str,
    output_path: Optional[str],
    rules_file: Optional[str],
    dry_run: bool,
    resource_filters: Optional[str],
    subset_filter: Optional[str],
    dest_rg: Optional[str],
    location: Optional[str],
    domain_name: Optional[str] = None,
) -> None:
    """
    Generate Infrastructure-as-Code templates from graph data.

    Options:
      --aad-mode [none|manual|auto]  Control AAD object creation/replication mode.
        - none:   Do not create or replicate AAD objects.
        - manual: Only create/replicate AAD objects when explicitly specified (default).
        - auto:   Automatically create/replicate required AAD objects.

    All other standard IaC options are supported. See --help for details.
    """
    from src.utils.cli_installer import ensure_tool

    if format_type.lower() == "terraform":
        try:
            ensure_tool("terraform", auto_prompt=True)
        except SystemExit:
            click.echo("Aborting: 'terraform' is required but was not installed.")
            sys.exit(1)
    elif format_type.lower() == "arm":
        try:
            ensure_tool("az", auto_prompt=True)
        except SystemExit:
            click.echo("Aborting: 'az' is required but was not installed.")
            sys.exit(1)
    elif format_type.lower() == "bicep":
        try:
            ensure_tool("bicep", auto_prompt=True)
        except SystemExit:
            click.echo("Aborting: 'bicep' is required but was not installed.")
            sys.exit(1)
    await generate_iac_command_handler(
        tenant_id=tenant_id,
        format_type=format_type,
        output_path=output_path,
        rules_file=rules_file,
        dry_run=dry_run,
        resource_filters=resource_filters,
        subset_filter=subset_filter,
        dest_rg=dest_rg,
        location=location,
        # aad_mode removed, now always manual by default
        domain_name=domain_name,
    )


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
def container() -> None:
    """Manage Neo4j container."""
    # Note: Container management subcommands (start, stop, status) have been removed
    # as they were unused. Container management is handled automatically by the
    # build command when needed.
    click.echo("Container management is handled automatically by build commands.")
    click.echo("Use 'build --no-container' to disable automatic container management.")


@cli.command()
@click.argument(
    "backup_path", type=click.Path(dir_okay=False, writable=True, resolve_path=True)
)
def backup_db(backup_path: str) -> None:
    """Backup the Neo4j database and save it to BACKUP_PATH."""
    from src.container_manager import Neo4jContainerManager

    container_manager = Neo4jContainerManager()
    if container_manager.backup_neo4j_database(backup_path):
        click.echo(f"✅ Neo4j backup completed and saved to {backup_path}")
    else:
        click.echo("❌ Neo4j backup failed", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
@async_command
async def mcp_server(ctx: click.Context) -> None:
    """Start MCP server (uvx mcp-neo4j-cypher) after ensuring Neo4j is running."""
    from src.cli_commands import mcp_server_command_handler

    await mcp_server_command_handler(ctx)


@cli.command()
@click.pass_context
@async_command
async def threat_model(ctx: click.Context) -> None:
    """Run the Threat Modeling Agent workflow to generate a DFD, enumerate threats, and produce a Markdown report from the current Neo4j graph."""
    from src.cli_commands import generate_threat_model_command_handler

    await generate_threat_model_command_handler(ctx)


@cli.command("generate-sim-doc")
@click.option(
    "--size",
    type=int,
    required=False,
    help="Target company size (approximate number of employees)",
)
@click.option(
    "--seed",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    required=False,
    help="Path to a markdown file with seed/suggestions for the profile",
)
@click.option(
    "--out",
    type=click.Path(dir_okay=False, writable=True),
    required=False,
    help="Output markdown file (default: simdocs/simdoc-<timestamp>.md)",
)
@click.pass_context
@async_command
async def generate_sim_doc(
    ctx: click.Context,
    size: Optional[int],
    seed: Optional[str],
    out: Optional[str],
) -> None:
    """
    Generate a simulated Azure customer profile as a Markdown narrative.
    """
    from src.cli_commands import generate_sim_doc_command_handler

    await generate_sim_doc_command_handler(ctx, size=size, seed_path=seed, out_path=out)


# Alias: gensimdoc
cli.add_command(generate_sim_doc, "gensimdoc")

# Register create-tenant command
cli.add_command(create_tenant_command, "create-tenant")
cli.add_command(spa_start, "start")
cli.add_command(spa_stop, "stop")
cli.add_command(app_registration_command, "app-registration")


@cli.command()
@click.option(
    "--question",
    help="Ask a single question and exit (non-interactive mode)",
)
@click.pass_context
@async_command
async def agent_mode(ctx: click.Context, question: Optional[str]) -> None:
    """Start AutoGen MCP agent mode (Neo4j + MCP server + agent chat loop)."""
    from src.cli_commands import agent_mode_command_handler

    await agent_mode_command_handler(ctx, question)


@cli.command("mcp-query")
@click.argument("query")
@click.option(
    "--tenant-id",
    help="Azure tenant ID (defaults to AZURE_TENANT_ID from .env)",
)
@click.option(
    "--no-fallback",
    is_flag=True,
    help="Disable fallback to traditional API methods",
)
@click.option(
    "--format",
    type=click.Choice(["json", "table", "text"]),
    default="json",
    help="Output format for query results",
)
@click.pass_context
@async_command
async def mcp_query(
    ctx: click.Context,
    query: str,
    tenant_id: Optional[str],
    no_fallback: bool,
    format: str,
) -> None:
    """Execute natural language queries for Azure resources via MCP.
    
    Examples:
        atg mcp-query "list all virtual machines"
        atg mcp-query "show storage accounts in westus2"
        atg mcp-query "find resources with public IP addresses"
        atg mcp-query "analyze security posture of my key vaults"
    
    This is an experimental feature that requires MCP_ENABLED=true in your .env file.
    """
    from src.cli_commands import mcp_query_command

    debug = ctx.obj.get("debug", False)
    await mcp_query_command(
        ctx,
        query,
        tenant_id=tenant_id,
        use_fallback=not no_fallback,
        output_format=format,
        debug=debug,
    )


@cli.command("backup")
@click.option(
    "--path",
    "-p",
    required=True,
    help="Path to save the backup file (e.g., /path/to/backup.dump)",
)
def backup_database(path: str) -> None:
    """Backup the Neo4j database to a file."""
    from src.container_manager import Neo4jContainerManager

    click.echo("🔄 Starting database backup...")
    container_manager = Neo4jContainerManager()

    if not container_manager.is_neo4j_container_running():
        click.echo("❌ Neo4j container is not running. Please start it first.")
        return

    if container_manager.backup_neo4j_database(path):
        click.echo(f"✅ Database backed up successfully to {path}")
    else:
        click.echo("❌ Database backup failed. Check the logs for details.")


@cli.command("restore")
@click.option(
    "--path",
    "-p",
    required=True,
    help="Path to the backup file to restore (e.g., /path/to/backup.dump)",
)
def restore_database(path: str) -> None:
    """Restore the Neo4j database from a backup file."""
    import os

    from src.container_manager import Neo4jContainerManager

    if not os.path.exists(path):
        click.echo(f"❌ Backup file not found: {path}")
        return

    click.echo("🔄 Starting database restore...")
    click.echo("⚠️  WARNING: This will replace all current data in the database!")

    if not click.confirm("Are you sure you want to continue?"):
        click.echo("Restore cancelled.")
        return

    container_manager = Neo4jContainerManager()

    if not container_manager.is_neo4j_container_running():
        click.echo("❌ Neo4j container is not running. Please start it first.")
        return

    if container_manager.restore_neo4j_database(path):
        click.echo("✅ Database restored successfully from backup.")
        click.echo("The Neo4j database has been restarted with the restored data.")
    else:
        click.echo("❌ Database restore failed. Check the logs for details.")


# Add alias for restore command
cli.add_command(restore_database, "restore-db")


@cli.command("wipe")
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Skip confirmation prompt",
)
def wipe_database(force: bool) -> None:
    """Wipe all data from the Neo4j database."""
    import os

    from neo4j import GraphDatabase

    if not force:
        click.echo("⚠️  WARNING: This will permanently delete ALL data in the database!")
        click.echo("This action cannot be undone.")
        if not click.confirm("Are you sure you want to wipe the database?"):
            click.echo("Wipe cancelled.")
            return

    click.echo("🔄 Wiping database...")

    try:
        # Connect to Neo4j
        uri = os.getenv("NEO4J_URI")
        if not uri:
            port = os.getenv("NEO4J_PORT")
            if not port:
                console.print(
                    "[red]❌ Either NEO4J_URI or NEO4J_PORT must be set[/red]"
                )
                return False
            uri = f"bolt://localhost:{port}"
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD")
        if not password:
            console.print(
                "[red]❌ NEO4J_PASSWORD environment variable is required[/red]"
            )
            return False

        driver = GraphDatabase.driver(uri, auth=(user, password))

        with driver.session() as session:
            # Delete all nodes and relationships
            session.run("MATCH (n) DETACH DELETE n")

            # Verify the database is empty
            result = session.run("MATCH (n) RETURN count(n) as count")
            record = result.single()
            count = record["count"] if record else 0

            if count == 0:
                click.echo("✅ Database wiped successfully. All data has been removed.")
            else:
                click.echo(f"⚠️  Database wipe incomplete. {count} nodes remain.")

        driver.close()

    except Exception as e:
        click.echo(f"❌ Failed to wipe database: {e}")


@cli.command()
def check_permissions() -> None:
    """Check Microsoft Graph API permissions for AAD/Entra ID discovery."""
    click.echo("🔍 Checking Microsoft Graph API Permissions")

    # Run the test script
    import subprocess

    try:
        result = subprocess.run(
            ["uv", "run", "python", "test_graph_api.py"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Check if the command failed
        if result.returncode != 0:
            click.echo(f"❌ Error running test script: {result.stderr}")
            return

        # Combine stdout and stderr for parsing (logging might go to stderr)
        output = result.stdout + result.stderr

        # Parse the output for display
        if "✅ Can read users" in output:
            click.echo("✅ User.Read permission granted")
        else:
            click.echo("❌ User.Read permission missing")

        if "✅ Can read groups" in output:
            click.echo("✅ Group.Read permission granted")
        else:
            click.echo("❌ Group.Read permission missing")

        if "✅ Can read service principals" in output:
            click.echo("✅ Application.Read permission granted")
        else:
            click.echo("⚠️ Application.Read permission missing (optional)")

        if "✅ Can read directory roles" in output:
            click.echo("✅ RoleManagement.Read permission granted")
        else:
            click.echo("⚠️ RoleManagement.Read permission missing (optional)")

        # Show setup instructions if permissions are missing
        has_users = "✅ Can read users" in output
        has_groups = "✅ Can read groups" in output

        if not has_users or not has_groups:
            click.echo("\n📚 See docs/GRAPH_API_SETUP.md for setup instructions")
            click.echo(
                "Or run: uv run python test_graph_api.py for detailed diagnostics"
            )
        else:
            click.echo("\n✅ All required Graph API permissions are configured!")

    except subprocess.TimeoutExpired:
        click.echo("❌ Permission check timed out")
    except Exception as e:
        click.echo(f"❌ Error checking permissions: {e}")


@cli.command()
def doctor() -> None:
    """Check for all registered CLI tools and offer to install if missing."""
    try:
        from src.utils.cli_installer import TOOL_REGISTRY
    except ImportError:
        print("Could not import TOOL_REGISTRY. Please check your installation.")
        return

    for tool in TOOL_REGISTRY.values():
        print(f"Checking for '{tool.name}' CLI...")
        if is_tool_installed(tool.name):
            print(f"✅ {tool.name} is installed.")
        else:
            print(f"❌ {tool.name} is NOT installed.")
            install_tool(tool.name)
    print("Doctor check complete.")


def main() -> None:
    """Main entry point."""
    result = cli()  # type: ignore[reportCallIssue]
    # If the CLI returns a sentinel indicating dashboard exit, exit here
    if result == "__DASHBOARD_EXIT__":
        # Note: We can't access debug flag here, so no debug output
        sys.stderr.flush()
        sys.exit(0)
    # Explicitly exit cleanly after build --no-dashboard sentinel
    if result == "__NO_DASHBOARD_BUILD_COMPLETE__":
        # Note: We can't access debug flag here, so no debug output
        sys.stderr.flush()
        sys.exit(0)
    # For any other truthy result, exit as before (legacy fallback)
    if result:
        sys.exit(0)


if __name__ == "__main__":
    main()
