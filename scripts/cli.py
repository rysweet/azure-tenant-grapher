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
from src.commands.deploy import deploy_command
from src.commands.list_deployments import list_deployments
from src.commands.undeploy import undeploy
from src.commands.validate_deployment import validate_deployment_command

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
    "--batch-mode",
    is_flag=True,
    help="Enable batch mode for Neo4j writes (significantly faster for large tenants)",
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
    filter_by_subscriptions: Optional[str] = None,
    filter_by_rgs: Optional[str] = None,
    batch_mode: bool = False,
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
        filter_by_subscriptions,
        filter_by_rgs,
        batch_mode,
    )
    if debug:
        print(f"[DEBUG] build_command_handler returned: {result!r}", flush=True)
    return result


# Add "scan" as an alias to the "build" command for consistency with documentation and UI
@cli.command(name="scan")
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
) -> str | None:
    """
    Scan the complete Azure tenant graph with enhanced processing.

    This command discovers all resources in your Azure tenant and builds a comprehensive
    Neo4j graph database. By default, shows a live Rich dashboard with progress, logs,
    and interactive controls:
      - Press 'x' to exit the dashboard at any time.
      - Press 'i', 'd', or 'w' to set log level to INFO, DEBUG, or WARNING.

    Use --no-dashboard to disable the dashboard and emit logs line by line to the terminal.
    """
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
    )
    if debug:
        print(
            f"[DEBUG] scan command (via build_command_handler) returned: {result!r}",
            flush=True,
        )
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
@click.option(
    "--hierarchical",
    is_flag=True,
    help="Generate hierarchical specification organized by Tenant→Subscription→Region→ResourceGroup",
)
@click.pass_context
def generate_spec(
    ctx: click.Context, limit: Optional[int], output: Optional[str], hierarchical: bool
) -> None:
    """Generate anonymized tenant Markdown specification (no tenant-id required)."""
    generate_spec_command_handler(ctx, limit, output, hierarchical)


@cli.command()
@click.option(
    "--tenant-id",
    required=False,
    help="Azure tenant ID (defaults to AZURE_TENANT_ID from .env)",
)
@click.option(
    "--target-subscription",
    required=False,
    help="Target Azure subscription ID for deployment (overrides auto-detection from source resources)",
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
    "--node-id",
    "node_ids",
    multiple=True,
    help="Specific node IDs to generate IaC for (can be specified multiple times)",
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
@click.option(
    "--skip-validation",
    is_flag=True,
    help="Skip Terraform validation after generation (for terraform format only)",
)
@click.option(
    "--skip-subnet-validation",
    is_flag=True,
    help="Skip subnet address space containment validation (not recommended, Issue #333)",
)
@click.option(
    "--auto-fix-subnets",
    is_flag=True,
    help="Automatically fix subnet addresses that fall outside VNet address range (Issue #333)",
)
@click.option(
    "--preserve-rg-structure",
    is_flag=True,
    help="Preserve source resource group structure in target deployment (creates target RGs matching source structure)",
)
@click.option(
    "--naming-suffix",
    help="Custom naming suffix for resolving global name conflicts (default: random 6-char alphanumeric)",
)
@click.option(
    "--skip-name-validation",
    is_flag=True,
    help="Skip global resource name conflict validation (for terraform format only)",
)
@click.option(
    "--preserve-names",
    is_flag=True,
    help="Preserve original resource names; fail on conflicts instead of auto-fixing (for terraform format only)",
)
@click.option(
    "--auto-purge-soft-deleted",
    is_flag=True,
    help="Automatically purge soft-deleted Key Vaults before deployment (for terraform format only, GAP-016)",
)
@click.option(
    "--check-conflicts/--no-check-conflicts",
    default=True,
    help="Enable/disable pre-deployment conflict detection (default: enabled, Issue #336)",
)
@click.option(
    "--skip-conflict-check",
    is_flag=True,
    help="Skip pre-deployment conflict detection (shorthand for --no-check-conflicts)",
)
@click.option(
    "--auto-cleanup",
    is_flag=True,
    help="Automatically run cleanup script if conflicts are detected (Issue #336)",
)
@click.option(
    "--fail-on-conflicts/--no-fail-on-conflicts",
    default=True,
    help="Fail deployment if conflicts are detected (default: fail, Issue #336)",
)
@click.option(
    "--resource-group-prefix",
    help="Prefix to add to all resource group names (e.g., 'ITERATION15_') for non-destructive iterations",
)
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
    target_subscription: Optional[str],
    format_type: str,
    output_path: Optional[str],
    rules_file: Optional[str],
    dry_run: bool,
    resource_filters: Optional[str],
    subset_filter: Optional[str],
    node_ids: tuple,
    dest_rg: Optional[str],
    location: Optional[str],
    skip_validation: bool,
    skip_subnet_validation: bool,
    auto_fix_subnets: bool,
    preserve_rg_structure: bool,
    naming_suffix: Optional[str],
    skip_name_validation: bool,
    preserve_names: bool,
    auto_purge_soft_deleted: bool,
    check_conflicts: bool,
    skip_conflict_check: bool,
    auto_cleanup: bool,
    fail_on_conflicts: bool,
    resource_group_prefix: Optional[str],
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
        target_subscription=target_subscription,
        format_type=format_type,
        output_path=output_path,
        rules_file=rules_file,
        dry_run=dry_run,
        resource_filters=resource_filters,
        subset_filter=subset_filter,
        node_ids=list(node_ids) if node_ids else None,
        dest_rg=dest_rg,
        location=location,
        skip_validation=skip_validation,
        skip_subnet_validation=skip_subnet_validation,
        auto_fix_subnets=auto_fix_subnets,
        preserve_rg_structure=preserve_rg_structure,
        domain_name=domain_name,
        naming_suffix=naming_suffix,
        skip_name_validation=skip_name_validation,
        preserve_names=preserve_names,
        auto_purge_soft_deleted=auto_purge_soft_deleted,
        check_conflicts=check_conflicts,
        skip_conflict_check=skip_conflict_check,
        auto_cleanup=auto_cleanup,
        fail_on_conflicts=fail_on_conflicts,
        resource_group_prefix=resource_group_prefix,
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
    "--output",
    type=click.Path(dir_okay=False, writable=True),
    required=False,
    help="Output markdown file (default: outputs/simdoc-<timestamp>.md)",
)
@click.pass_context
@async_command
async def generate_sim_doc(
    ctx: click.Context,
    size: Optional[int],
    seed: Optional[str],
    output: Optional[str],
) -> None:
    """
    Generate a simulated Azure customer profile as a Markdown narrative.
    """
    from src.cli_commands import generate_sim_doc_command_handler

    await generate_sim_doc_command_handler(
        ctx, size=size, seed_path=seed, out_path=output
    )


# Alias: gensimdoc
cli.add_command(generate_sim_doc, "gensimdoc")

# Register create-tenant command
cli.add_command(create_tenant_command, "create-tenant")
cli.add_command(spa_start, "start")
cli.add_command(spa_stop, "stop")
cli.add_command(app_registration_command, "app-registration")

cli.add_command(deploy_command, "deploy")
cli.add_command(undeploy, "undeploy")
cli.add_command(list_deployments, "list-deployments")
cli.add_command(validate_deployment_command, "validate-deployment")


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


@cli.command("monitor")
@click.option(
    "--subscription-id",
    help="Filter by subscription ID",
)
@click.option(
    "--interval",
    default=30,
    type=int,
    help="Check interval in seconds (default: 30)",
)
@click.option(
    "--watch",
    is_flag=True,
    help="Continuous monitoring mode (like watch command)",
)
@click.option(
    "--detect-stabilization",
    is_flag=True,
    help="Exit when database metrics have stabilized",
)
@click.option(
    "--threshold",
    default=3,
    type=int,
    help="Number of identical checks to consider stable (default: 3)",
)
@click.option(
    "--format",
    "format_type",
    type=click.Choice(["json", "table", "compact"]),
    default="compact",
    help="Output format (default: compact)",
)
@click.option(
    "--no-container",
    is_flag=True,
    help="Do not auto-start Neo4j container",
)
@click.pass_context
@async_command
async def monitor(
    ctx: click.Context,
    subscription_id: Optional[str],
    interval: int,
    watch: bool,
    detect_stabilization: bool,
    threshold: int,
    format_type: str,
    no_container: bool,
) -> None:
    """Monitor Neo4j database resource counts and relationships.

    This command queries the Neo4j database to display current resource counts,
    relationships, resource groups, and resource types. It can run once or
    continuously monitor the database.

    Examples:

        # Single check
        atg monitor

        # Single check for specific subscription
        atg monitor --subscription-id 9b00bc5e-9abc-45de-9958-02a9d9277b16

        # Watch mode with 60 second interval
        atg monitor --watch --interval 60

        # Detect when database has stabilized
        atg monitor --watch --detect-stabilization --threshold 3

        # JSON output format
        atg monitor --format json

        # Table output format with watch
        atg monitor --watch --format table
    """
    from src.cli_commands import monitor_command_handler

    await monitor_command_handler(
        subscription_id=subscription_id,
        interval=interval,
        watch=watch,
        detect_stabilization=detect_stabilization,
        threshold=threshold,
        format_type=format_type,
        no_container=no_container,
    )


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


@cli.command("fidelity")
@click.option(
    "--source-subscription",
    required=True,
    help="Source subscription ID to compare from",
)
@click.option(
    "--target-subscription",
    required=True,
    help="Target subscription ID to compare to",
)
@click.option(
    "--track",
    is_flag=True,
    help="Track fidelity metrics to demos/fidelity_history.jsonl",
)
@click.option(
    "--output",
    help="Export fidelity metrics to JSON file",
)
@click.option(
    "--check-objective",
    help="Path to OBJECTIVE.md file for compliance checking",
)
@click.option(
    "--no-container",
    is_flag=True,
    help="Do not auto-start Neo4j container",
)
@click.pass_context
@async_command
async def fidelity(
    ctx: click.Context,
    source_subscription: str,
    target_subscription: str,
    track: bool,
    output: Optional[str],
    check_objective: Optional[str],
    no_container: bool,
) -> None:
    """Calculate and track resource replication fidelity between subscriptions.

    This command compares resource counts, types, and relationships between a source
    and target subscription to measure replication fidelity.

    Examples:

        # Calculate current fidelity
        atg fidelity --source-subscription 9b00bc5e-9abc-45de-9958-02a9d9277b16 \\
                     --target-subscription c190c55a-9ab2-4b1e-92c4-cc8b1a032285

        # Track fidelity over time
        atg fidelity --source-subscription SOURCE_ID \\
                     --target-subscription TARGET_ID \\
                     --track

        # Export to JSON
        atg fidelity --source-subscription SOURCE_ID \\
                     --target-subscription TARGET_ID \\
                     --output fidelity_report.json

        # Check against objective
        atg fidelity --source-subscription SOURCE_ID \\
                     --target-subscription TARGET_ID \\
                     --check-objective demos/OBJECTIVE.md
    """
    from src.cli_commands import fidelity_command_handler

    await fidelity_command_handler(
        source_subscription=source_subscription,
        target_subscription=target_subscription,
        track=track,
        output=output,
        check_objective=check_objective,
        no_container=no_container,
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
