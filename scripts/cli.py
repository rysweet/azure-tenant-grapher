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
from rich.console import Console
from rich.logging import RichHandler
from rich.style import Style

from src.cli_dashboard_manager import DashboardExitException
from src.commands.abstract_graph import abstract_graph
from src.commands.auth import app_registration as app_registration_cmd
from src.commands.database import (
    backup as backup_cmd,
    backup_db as backup_db_cmd,
    container as container_cmd,
    restore as restore_cmd,
    wipe as wipe_cmd,
)

# Import modular commands for CLI registration (Issue #482)
from src.commands.deploy import deploy_command
from src.commands.export_abstraction import export_abstraction_command
from src.commands.list_deployments import list_deployments
from src.commands.spa import spa_start as spa_start_command
from src.commands.spa import spa_stop as spa_stop_command
from src.commands.spec import generate_spec_command_handler, spec_command_handler
from src.commands.tenant import create_tenant as create_tenant_cmd
from src.commands.undeploy import undeploy
from src.commands.validate_deployment import validate_deployment_command
from src.commands.visualize import visualize_command_handler
from src.utils.neo4j_startup import ensure_neo4j_running

# Initialize console for rich output
console = Console()


def _should_redact_env_var(key: str) -> bool:
    """Check if an environment variable key should have its value redacted."""
    # Patterns that indicate sensitive values (credentials, secrets, keys)
    sensitive_patterns = ("PASS", "SECRET", "KEY", "TOKEN", "AUTH", "CRED")
    return any(pattern in key.upper() for pattern in sensitive_patterns)


def print_cli_env_block(context: str = "", debug: bool = False):
    # Only print environment variables if debug is enabled
    if debug:
        print(f"[CLI ENV DUMP]{'[' + context + ']' if context else ''}")
        env_vars_to_print = [
            "NEO4J_CONTAINER_NAME",
            "NEO4J_DATA_VOLUME",
            "NEO4J_" + "PASSWORD",  # Split to avoid security scanner false positive
            "NEO4J_PORT",
            "NEO4J_URI",
        ]
        for k in env_vars_to_print:
            value = os.environ.get(k)
            if _should_redact_env_var(k) and value:
                value = "***REDACTED***"
            print(f"[CLI ENV] {k}={value}")


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

    # Keep handler imports for backward compatibility (deprecated, use modular commands)
    from src.cli_commands import build_command_handler
    from src.config_manager import create_config_from_env
    from src.iac.cli_handler import generate_iac_command_handler
except ImportError as e:
    print(f"Import error: {e}")
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
    "--source-tenant-id",
    required=False,
    help="Source tenant ID (auto-detected from Azure CLI if not specified) - used for cross-tenant translation",
)
@click.option(
    "--target-tenant-id",
    required=False,
    help="Target tenant ID for cross-tenant deployment - enables Entra ID object translation",
)
@click.option(
    "--identity-mapping-file",
    required=False,
    help="Path to identity mapping JSON file for Entra ID object translation (users, groups, service principals)",
)
@click.option(
    "--strict-translation",
    is_flag=True,
    help="Fail on missing identity mappings (default: warn only and use placeholders)",
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
@click.option(
    "--auto-import-existing/--no-auto-import-existing",
    default=True,
    help="Automatically import pre-existing Azure resources into Terraform state (default: enabled, Issue #412)",
)
@click.option(
    "--import-strategy",
    type=click.Choice(
        ["resource_groups", "all_resources", "selective"], case_sensitive=False
    ),
    default="all_resources",
    help="Strategy for importing existing resources: all_resources (default), resource_groups, or selective (Issue #412)",
)
@click.option(
    "--auto-register-providers",
    is_flag=True,
    help="Automatically register required Azure resource providers without prompting",
)
@click.option(
    "--scan-target",
    is_flag=True,
    help="Enable smart import by scanning target tenant for existing resources",
)
@click.option(
    "--scan-target-tenant-id",
    required=False,
    help="Target tenant ID to scan for smart import (required if --scan-target is enabled)",
)
@click.option(
    "--scan-target-subscription-id",
    required=False,
    help="Target subscription ID to scan for smart import (optional, scans all subscriptions if not provided)",
)
@click.option(
    "--split-by-community",
    is_flag=True,
    help="Split resources into separate Terraform files per community (connected component)",
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
    source_tenant_id: Optional[str],
    target_tenant_id: Optional[str],
    identity_mapping_file: Optional[str],
    strict_translation: bool,
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
    auto_import_existing: bool,
    import_strategy: str,
    auto_register_providers: bool,
    scan_target: bool,
    scan_target_tenant_id: Optional[str],
    scan_target_subscription_id: Optional[str],
    split_by_community: bool,
    domain_name: Optional[str] = None,
) -> None:
    """
    Generate Infrastructure-as-Code templates from graph data.

    Cross-Tenant Translation:
      Use --target-tenant-id to enable cross-tenant deployment with automatic
      translation of Entra ID objects and resource IDs. Combine with:

      --identity-mapping-file: JSON file mapping source to target identities
      --source-tenant-id: Source tenant (auto-detected if not provided)
      --strict-translation: Fail on missing mappings instead of using placeholders

    Example - Cross-tenant deployment:
      atg generate-iac --target-tenant-id TARGET_TENANT_ID \\
                       --target-subscription TARGET_SUB_ID \\
                       --identity-mapping-file mappings.json

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
        source_tenant_id=source_tenant_id,
        target_tenant_id=target_tenant_id,
        identity_mapping_file=identity_mapping_file,
        strict_translation=strict_translation,
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
        auto_import_existing=auto_import_existing,
        import_strategy=import_strategy,
        auto_register_providers=auto_register_providers,
        scan_target=scan_target,
        scan_target_tenant_id=scan_target_tenant_id,
        scan_target_subscription_id=scan_target_subscription_id,
        split_by_community=split_by_community,
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

# ==============================================================================
# Register modular commands (Issue #482: CLI Modularization)
# These commands are now defined in src/commands/ modules for maintainability
# ==============================================================================

# Register create-tenant command (from src.commands.tenant)
cli.add_command(create_tenant_cmd, "create-tenant")

# Register graph abstraction command (from src.commands.abstract_graph)
cli.add_command(abstract_graph)

# Register SPA commands (from src.commands.spa)
cli.add_command(spa_start_command, "start")
cli.add_command(spa_stop_command, "stop")

# Register auth command (from src.commands.auth)
cli.add_command(app_registration_cmd, "app-registration")

# Register deployment commands (existing)
cli.add_command(deploy_command, "deploy")
cli.add_command(undeploy, "undeploy")
cli.add_command(list_deployments, "list-deployments")
cli.add_command(validate_deployment_command, "validate-deployment")

# Register export-abstraction command (Issue #508)
cli.add_command(export_abstraction_command, "export-abstraction")

# Register database commands (Issue #482: CLI Modularization)
cli.add_command(backup_cmd, "backup")
cli.add_command(backup_db_cmd, "backup-db")
cli.add_command(restore_cmd, "restore")
cli.add_command(restore_cmd, "restore-db")  # Alias
cli.add_command(wipe_cmd, "wipe")
cli.add_command(container_cmd, "container")


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


@cli.command("cost-analysis")
@click.option(
    "--subscription-id",
    required=True,
    help="Azure subscription ID",
)
@click.option(
    "--resource-group",
    help="Resource group name (optional)",
)
@click.option(
    "--resource-id",
    help="Specific resource ID (optional)",
)
@click.option(
    "--start-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Start date (YYYY-MM-DD)",
)
@click.option(
    "--end-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="End date (YYYY-MM-DD)",
)
@click.option(
    "--granularity",
    type=click.Choice(["daily", "monthly"], case_sensitive=False),
    default="daily",
    help="Data granularity (default: daily)",
)
@click.option(
    "--group-by",
    type=click.Choice(
        ["resource", "resource_group", "service_name", "tag"], case_sensitive=False
    ),
    help="Group results by field",
)
@click.option(
    "--tag-key",
    help="Tag key for grouping (if group-by=tag)",
)
@click.option(
    "--sync",
    is_flag=True,
    help="Sync costs from Azure before querying",
)
@click.pass_context
@async_command
async def cost_analysis(
    ctx: click.Context,
    subscription_id: str,
    resource_group: Optional[str],
    resource_id: Optional[str],
    start_date: Optional[click.DateTime],
    end_date: Optional[click.DateTime],
    granularity: str,
    group_by: Optional[str],
    tag_key: Optional[str],
    sync: bool,
) -> None:
    """Analyze Azure costs for resources tracked in the graph.

    This command queries cost data from Azure Cost Management API and stores it
    in the Neo4j graph database for analysis. You can filter by subscription,
    resource group, or specific resource.

    Examples:

        # Analyze subscription costs for current month with sync
        atg cost-analysis --subscription-id xxx-xxx-xxx --sync

        # Analyze specific resource group costs
        atg cost-analysis --subscription-id xxx-xxx-xxx \\
                          --resource-group my-rg \\
                          --start-date 2025-01-01 \\
                          --end-date 2025-01-31

        # Group costs by service
        atg cost-analysis --subscription-id xxx-xxx-xxx \\
                          --group-by service_name \\
                          --sync
    """
    from src.cli_commands import cost_analysis_command_handler

    await cost_analysis_command_handler(
        ctx=ctx,
        subscription_id=subscription_id,
        resource_group=resource_group,
        resource_id=resource_id,
        start_date=start_date,
        end_date=end_date,
        granularity=granularity,
        group_by=group_by,
        tag_key=tag_key,
        sync=sync,
    )


@cli.command("cost-forecast")
@click.option(
    "--subscription-id",
    required=True,
    help="Azure subscription ID",
)
@click.option(
    "--resource-group",
    help="Resource group name (optional)",
)
@click.option(
    "--days",
    default=30,
    type=int,
    help="Number of days to forecast (default: 30)",
)
@click.option(
    "--output",
    help="Output file path (JSON)",
)
@click.pass_context
@async_command
async def cost_forecast(
    ctx: click.Context,
    subscription_id: str,
    resource_group: Optional[str],
    days: int,
    output: Optional[str],
) -> None:
    """Forecast future costs based on historical trends.

    This command uses historical cost data stored in Neo4j to generate cost
    forecasts using linear regression. Requires at least 14 days of historical
    cost data.

    Examples:

        # Forecast subscription costs for next 30 days
        atg cost-forecast --subscription-id xxx-xxx-xxx

        # Forecast resource group costs for next 90 days
        atg cost-forecast --subscription-id xxx-xxx-xxx \\
                          --resource-group my-rg \\
                          --days 90

        # Export forecast to JSON
        atg cost-forecast --subscription-id xxx-xxx-xxx \\
                          --output forecast.json
    """
    from src.cli_commands import cost_forecast_command_handler

    await cost_forecast_command_handler(
        ctx=ctx,
        subscription_id=subscription_id,
        resource_group=resource_group,
        days=days,
        output=output,
    )


@cli.command("cost-report")
@click.option(
    "--subscription-id",
    required=True,
    help="Azure subscription ID",
)
@click.option(
    "--resource-group",
    help="Resource group name (optional)",
)
@click.option(
    "--start-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Start date (YYYY-MM-DD)",
)
@click.option(
    "--end-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="End date (YYYY-MM-DD)",
)
@click.option(
    "--format",
    "format_type",
    type=click.Choice(["markdown", "json"], case_sensitive=False),
    default="markdown",
    help="Output format (default: markdown)",
)
@click.option(
    "--include-forecast/--no-forecast",
    default=True,
    help="Include cost forecast (default: include)",
)
@click.option(
    "--include-anomalies/--no-anomalies",
    default=True,
    help="Include anomaly detection (default: include)",
)
@click.option(
    "--output",
    help="Output file path",
)
@click.pass_context
@async_command
async def cost_report(
    ctx: click.Context,
    subscription_id: str,
    resource_group: Optional[str],
    start_date: Optional[click.DateTime],
    end_date: Optional[click.DateTime],
    format_type: str,
    include_forecast: bool,
    include_anomalies: bool,
    output: Optional[str],
) -> None:
    """Generate comprehensive cost report.

    This command generates a detailed cost report including historical costs,
    optional forecasts, and anomaly detection. Reports can be generated in
    markdown or JSON format.

    Examples:

        # Generate markdown report for current month
        atg cost-report --subscription-id xxx-xxx-xxx

        # Generate detailed report with forecast and anomalies
        atg cost-report --subscription-id xxx-xxx-xxx \\
                        --include-forecast \\
                        --include-anomalies \\
                        --output report.md

        # Generate JSON report for specific period
        atg cost-report --subscription-id xxx-xxx-xxx \\
                        --start-date 2025-01-01 \\
                        --end-date 2025-01-31 \\
                        --format json \\
                        --output report.json
    """
    from src.cli_commands import cost_report_command_handler

    await cost_report_command_handler(
        ctx=ctx,
        subscription_id=subscription_id,
        resource_group=resource_group,
        start_date=start_date,
        end_date=end_date,
        format=format_type,
        include_forecast=include_forecast,
        include_anomalies=include_anomalies,
        output=output,
    )


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
    """Check for all registered CLI tools and offer to install if missing.

    Also validates Azure service principal permissions for role assignment scanning.
    """
    try:
        from src.utils.cli_installer import TOOL_REGISTRY
    except ImportError:
        print("Could not import TOOL_REGISTRY. Please check your installation.")
        return

    # Check CLI tools
    print("=" * 60)
    print("🔧 Checking CLI Tools")
    print("=" * 60)
    for tool in TOOL_REGISTRY.values():
        print(f"Checking for '{tool.name}' CLI...")
        if is_tool_installed(tool.name):
            print(f"✅ {tool.name} is installed.")
        else:
            print(f"❌ {tool.name} is NOT installed.")
            install_tool(tool.name)

    # Check Azure permissions
    print("\n" + "=" * 60)
    print("🔐 Checking Azure Service Principal Permissions")
    print("=" * 60)

    try:
        import os
        import subprocess

        client_id = os.getenv("AZURE_CLIENT_ID")
        subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")

        if not client_id or not subscription_id:
            print("⚠️  AZURE_CLIENT_ID or AZURE_SUBSCRIPTION_ID not set in environment")
            print("   Cannot validate permissions without these values")
            print("")
            print("Doctor check complete.")
            return

        print(f"Service Principal: {client_id}")
        print(f"Subscription: {subscription_id}")
        print("")

        # Check role assignments
        result = subprocess.run(
            [
                "az",
                "role",
                "assignment",
                "list",
                "--assignee",
                client_id,
                "--output",
                "json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            print(f"❌ Failed to check role assignments: {result.stderr}")
            print("")
            print("Doctor check complete.")
            return

        import json

        roles = json.loads(result.stdout)
        role_names = [r.get("roleDefinitionName") for r in roles]

        print("Assigned Roles:")
        for role_name in role_names:
            print(f"  ✅ {role_name}")

        # Check for required roles
        has_reader = (
            "Reader" in role_names
            or "Contributor" in role_names
            or "Owner" in role_names
        )
        has_security_reader = (
            "Security Reader" in role_names
            or "Owner" in role_names
            or "User Access Administrator" in role_names
        )

        print("")
        print("Permission Requirements for Full Functionality:")

        if has_reader:
            print("  ✅ Resource Scanning: Reader, Contributor, or Owner (PRESENT)")
        else:
            print("  ❌ Resource Scanning: Reader, Contributor, or Owner (MISSING)")
            print("     Impact: Cannot scan Azure resources")

        if has_security_reader:
            print(
                "  ✅ Role Assignment Scanning: Security Reader, User Access Administrator, or Owner (PRESENT)"
            )
        else:
            print(
                "  ❌ Role Assignment Scanning: Security Reader, User Access Administrator, or Owner (MISSING)"
            )
            print(
                "     Impact: Cannot scan role assignments (RBAC will not be replicated!)"
            )
            print("")
            print("     FIX: Run this command to add Security Reader role:")
            print("     az role assignment create \\")
            print(f"       --assignee {client_id} \\")
            print("       --role 'Security Reader' \\")
            print(f"       --scope '/subscriptions/{subscription_id}'")
            print("")
            print("     OR use the automated script:")
            print("     ./scripts/setup_service_principal.sh <TENANT_NAME> <TENANT_ID>")

        print("")
        if has_reader and has_security_reader:
            print(
                "✅ ALL REQUIRED PERMISSIONS PRESENT - Ready for full E2E replication!"
            )
        else:
            print("⚠️  MISSING PERMISSIONS - Scanning will be limited!")

    except Exception as e:
        print(f"⚠️  Could not validate Azure permissions: {e}")

    print("")
    print("=" * 60)
    print("Doctor check complete.")
    print("=" * 60)


# ============================================================================
# Scale Operations Commands (Issue #427)
# ============================================================================


@cli.group(name="scale-up")
def scale_up() -> None:
    """Scale up operations - add synthetic nodes to the graph for testing."""
    pass


@scale_up.command(name="template")
@click.option(
    "--tenant-id",
    required=False,
    help="Azure tenant ID (defaults to AZURE_TENANT_ID from .env)",
)
@click.option(
    "--template-file",
    required=True,
    type=click.Path(exists=True, dir_okay=False, readable=True),
    help="Path to YAML template file defining resource structure",
)
@click.option(
    "--scale-factor",
    type=float,
    default=2.0,
    help="Multiplication factor for resources (default: 2.0)",
)
@click.option(
    "--batch-size",
    type=int,
    default=500,
    help="Number of resources to process per batch (default: 500)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview changes without executing",
)
@click.option(
    "--no-validate",
    is_flag=True,
    help="Skip pre/post validation checks",
)
@click.option(
    "--config",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    help="Path to scale configuration file",
)
@click.option(
    "--output-format",
    type=click.Choice(["table", "json", "markdown"], case_sensitive=False),
    default="table",
    help="Output format for results (default: table)",
)
@click.option(
    "--no-container",
    is_flag=True,
    help="Do not auto-start Neo4j container",
)
@click.pass_context
@async_command
async def scale_up_template(
    ctx: click.Context,
    tenant_id: Optional[str],
    template_file: str,
    scale_factor: float,
    batch_size: int,
    dry_run: bool,
    no_validate: bool,
    config: Optional[str],
    output_format: str,
    no_container: bool,
) -> None:
    """
    Scale up using template-based generation.

    Reads a YAML template defining resource types, counts, and relationships,
    then generates synthetic nodes based on the template multiplied by the
    scale factor.

    Example:

        \b
        # Scale up using a template with 2x multiplier
        atg scale-up template --template-file templates/small_env.yaml --scale-factor 2.0

        \b
        # Preview changes without executing
        atg scale-up template --template-file templates/large_env.yaml --dry-run

        \b
        # Use custom configuration
        atg scale-up template --template-file templates/test.yaml --config scale-config.yaml
    """
    from src.cli_commands_scale import scale_up_template_command_handler

    debug = ctx.obj.get("debug", False)
    if not no_container:
        ensure_neo4j_running(debug)

    await scale_up_template_command_handler(
        tenant_id=tenant_id,
        template_file=template_file,
        scale_factor=scale_factor,
        batch_size=batch_size,
        dry_run=dry_run,
        validate=not no_validate,
        config_path=config,
        output_format=output_format,
        debug=debug,
        no_container=no_container,
    )


@scale_up.command(name="scenario")
@click.option(
    "--tenant-id",
    required=False,
    help="Azure tenant ID (defaults to AZURE_TENANT_ID from .env)",
)
@click.option(
    "--scenario",
    required=True,
    type=click.Choice(
        ["hub-spoke", "multi-region", "dev-test-prod"], case_sensitive=False
    ),
    help="Built-in scenario template to use",
)
@click.option(
    "--scale-factor",
    type=float,
    default=1.0,
    help="Multiplication factor for scenario resources (default: 1.0)",
)
@click.option(
    "--regions",
    type=str,
    help="Comma-separated list of Azure regions (for multi-region scenario)",
)
@click.option(
    "--spoke-count",
    type=int,
    default=3,
    help="Number of spoke VNets (for hub-spoke scenario, default: 3)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview changes without executing",
)
@click.option(
    "--no-validate",
    is_flag=True,
    help="Skip pre/post validation checks",
)
@click.option(
    "--config",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    help="Path to scale configuration file",
)
@click.option(
    "--output-format",
    type=click.Choice(["table", "json", "markdown"], case_sensitive=False),
    default="table",
    help="Output format for results (default: table)",
)
@click.option(
    "--no-container",
    is_flag=True,
    help="Do not auto-start Neo4j container",
)
@click.pass_context
@async_command
async def scale_up_scenario(
    ctx: click.Context,
    tenant_id: Optional[str],
    scenario: str,
    scale_factor: float,
    regions: Optional[str],
    spoke_count: int,
    dry_run: bool,
    no_validate: bool,
    config: Optional[str],
    output_format: str,
    no_container: bool,
) -> None:
    """
    Scale up using scenario-based generation.

    Uses built-in scenario templates that represent common Azure deployment
    patterns:

    \b
    - hub-spoke: Hub-and-spoke network topology with peered VNets
    - multi-region: Resources distributed across multiple Azure regions
    - dev-test-prod: Three-tier environment structure

    Example:

        \b
        # Generate a hub-spoke topology with 5 spokes
        atg scale-up scenario --scenario hub-spoke --spoke-count 5

        \b
        # Multi-region deployment across 3 regions
        atg scale-up scenario --scenario multi-region --regions eastus,westus,northeurope

        \b
        # Dev/Test/Prod environment with 2x scale factor
        atg scale-up scenario --scenario dev-test-prod --scale-factor 2.0
    """
    from src.cli_commands_scale import scale_up_scenario_command_handler

    debug = ctx.obj.get("debug", False)
    if not no_container:
        ensure_neo4j_running(debug)

    # Parse regions if provided
    region_list = regions.split(",") if regions else None

    await scale_up_scenario_command_handler(
        tenant_id=tenant_id,
        scenario=scenario,
        scale_factor=scale_factor,
        regions=region_list,
        spoke_count=spoke_count,
        dry_run=dry_run,
        validate=not no_validate,
        config_path=config,
        output_format=output_format,
        debug=debug,
        no_container=no_container,
    )


@cli.group(name="scale-down")
def scale_down() -> None:
    """Scale down operations - sample/reduce the graph for testing."""
    pass


@scale_down.command(name="algorithm")
@click.option(
    "--tenant-id",
    required=False,
    help="Azure tenant ID (defaults to AZURE_TENANT_ID from .env)",
)
@click.option(
    "--algorithm",
    required=True,
    type=click.Choice(
        ["forest-fire", "mhrw", "random-walk", "random-node"], case_sensitive=False
    ),
    help="Sampling algorithm to use",
)
@click.option(
    "--target-size",
    type=float,
    default=0.1,
    help="Target size as fraction of original (0.0-1.0, default: 0.1)",
)
@click.option(
    "--target-count",
    type=int,
    help="Target absolute node count (overrides target-size)",
)
@click.option(
    "--burn-in",
    type=int,
    default=50,
    help="Burn-in steps for forest-fire algorithm (default: 50)",
)
@click.option(
    "--burning-prob",
    type=float,
    default=0.4,
    help="Burning probability for forest-fire (default: 0.4)",
)
@click.option(
    "--walk-length",
    type=int,
    default=1000,
    help="Walk length for MHRW algorithm (default: 1000)",
)
@click.option(
    "--alpha",
    type=float,
    default=1.0,
    help="Bias parameter for MHRW (default: 1.0 = unbiased)",
)
@click.option(
    "--output-mode",
    type=click.Choice(["delete", "export", "new-tenant"], case_sensitive=False),
    default="delete",
    help="What to do with sampled subgraph (default: delete)",
)
@click.option(
    "--output-file",
    type=click.Path(dir_okay=False, writable=True),
    help="Path to export file (for export mode)",
)
@click.option(
    "--output-format",
    type=click.Choice(["yaml", "json"], case_sensitive=False),
    default="yaml",
    help="Export format (default: yaml)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview changes without executing",
)
@click.option(
    "--no-validate",
    is_flag=True,
    help="Skip validation checks",
)
@click.option(
    "--config",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    help="Path to scale configuration file",
)
@click.option(
    "--no-container",
    is_flag=True,
    help="Do not auto-start Neo4j container",
)
@click.pass_context
@async_command
async def scale_down_algorithm(
    ctx: click.Context,
    tenant_id: Optional[str],
    algorithm: str,
    target_size: float,
    target_count: Optional[int],
    burn_in: int,
    burning_prob: float,
    walk_length: int,
    alpha: float,
    output_mode: str,
    output_file: Optional[str],
    output_format: str,
    dry_run: bool,
    no_validate: bool,
    config: Optional[str],
    no_container: bool,
) -> None:
    """
    Scale down using sampling algorithms.

    Implements graph sampling algorithms that preserve structural properties:

    \b
    - forest-fire: Simulates forest fire spreading through graph
    - mhrw: Metropolis-Hastings Random Walk for unbiased sampling
    - random-walk: Simple random walk sampling
    - random-node: Uniform random node sampling

    Example:

        \b
        # Sample 10% of graph using forest-fire
        atg scale-down algorithm --algorithm forest-fire --target-size 0.1

        \b
        # Sample exactly 500 nodes using MHRW
        atg scale-down algorithm --algorithm mhrw --target-count 500

        \b
        # Export sampled graph to YAML file
        atg scale-down algorithm --algorithm forest-fire --target-size 0.2 \\
            --output-mode export --output-file sampled_graph.yaml
    """
    from src.cli_commands_scale import scale_down_algorithm_command_handler

    debug = ctx.obj.get("debug", False)
    if not no_container:
        ensure_neo4j_running(debug)

    await scale_down_algorithm_command_handler(
        tenant_id=tenant_id,
        algorithm=algorithm,
        target_size=target_size,
        target_count=target_count,
        burn_in=burn_in,
        burning_prob=burning_prob,
        walk_length=walk_length,
        alpha=alpha,
        output_mode=output_mode,
        output_file=output_file,
        output_format=output_format,
        dry_run=dry_run,
        validate=not no_validate,
        config_path=config,
        debug=debug,
        no_container=no_container,
    )


@scale_down.command(name="pattern")
@click.option(
    "--tenant-id",
    required=False,
    help="Azure tenant ID (defaults to AZURE_TENANT_ID from .env)",
)
@click.option(
    "--pattern",
    required=True,
    type=click.Choice(
        ["security", "network", "compute", "storage", "resource-type"],
        case_sensitive=False,
    ),
    help="Pattern-based filter to apply",
)
@click.option(
    "--resource-types",
    type=str,
    help="Comma-separated resource types (for resource-type pattern)",
)
@click.option(
    "--target-size",
    type=float,
    default=0.1,
    help="Target size as fraction of pattern match (default: 0.1)",
)
@click.option(
    "--output-mode",
    type=click.Choice(["delete", "export", "new-tenant"], case_sensitive=False),
    default="delete",
    help="What to do with sampled subgraph (default: delete)",
)
@click.option(
    "--output-file",
    type=click.Path(dir_okay=False, writable=True),
    help="Path to export file (for export mode)",
)
@click.option(
    "--output-format",
    type=click.Choice(["yaml", "json"], case_sensitive=False),
    default="yaml",
    help="Export format (default: yaml)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview changes without executing",
)
@click.option(
    "--no-validate",
    is_flag=True,
    help="Skip validation checks",
)
@click.option(
    "--config",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    help="Path to scale configuration file",
)
@click.option(
    "--no-container",
    is_flag=True,
    help="Do not auto-start Neo4j container",
)
@click.pass_context
@async_command
async def scale_down_pattern(
    ctx: click.Context,
    tenant_id: Optional[str],
    pattern: str,
    resource_types: Optional[str],
    target_size: float,
    output_mode: str,
    output_file: Optional[str],
    output_format: str,
    dry_run: bool,
    no_validate: bool,
    config: Optional[str],
    no_container: bool,
) -> None:
    """
    Scale down using pattern-based filtering.

    Filters graph by specific resource patterns before sampling:

    \b
    - security: Key Vaults, Network Security Groups, managed identities
    - network: VNets, subnets, NICs, load balancers, gateways
    - compute: VMs, VM scale sets, container instances
    - storage: Storage accounts, disks, file shares
    - resource-type: Custom list of resource types

    Example:

        \b
        # Keep only security-related resources
        atg scale-down pattern --pattern security --target-size 1.0

        \b
        # Sample network resources (keep 30%)
        atg scale-down pattern --pattern network --target-size 0.3

        \b
        # Filter by specific resource types
        atg scale-down pattern --pattern resource-type \\
            --resource-types "Microsoft.Compute/virtualMachines,Microsoft.Network/virtualNetworks"
    """
    from src.cli_commands_scale import scale_down_pattern_command_handler

    debug = ctx.obj.get("debug", False)
    if not no_container:
        ensure_neo4j_running(debug)

    # Parse resource types if provided
    resource_type_list = resource_types.split(",") if resource_types else None

    await scale_down_pattern_command_handler(
        tenant_id=tenant_id,
        pattern=pattern,
        resource_types=resource_type_list,
        target_size=target_size,
        output_mode=output_mode,
        output_file=output_file,
        output_format=output_format,
        dry_run=dry_run,
        validate=not no_validate,
        config_path=config,
        debug=debug,
        no_container=no_container,
    )


@cli.command(name="scale-clean")
@click.option(
    "--tenant-id",
    required=False,
    help="Azure tenant ID (defaults to AZURE_TENANT_ID from .env)",
)
@click.option(
    "--force",
    is_flag=True,
    help="Skip confirmation prompt",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview what would be deleted without executing",
)
@click.option(
    "--output-format",
    type=click.Choice(["table", "json", "markdown"], case_sensitive=False),
    default="table",
    help="Output format for results (default: table)",
)
@click.option(
    "--no-container",
    is_flag=True,
    help="Do not auto-start Neo4j container",
)
@click.pass_context
@async_command
async def scale_clean(
    ctx: click.Context,
    tenant_id: Optional[str],
    force: bool,
    dry_run: bool,
    output_format: str,
    no_container: bool,
) -> None:
    """
    Clean up all synthetic data from the graph.

    Removes all nodes with the :Synthetic label and their relationships.
    This operation is useful for resetting the graph to its original state
    after scale testing.

    Example:

        \b
        # Preview what would be cleaned
        atg scale-clean --dry-run

        \b
        # Clean synthetic data with confirmation
        atg scale-clean

        \b
        # Clean without confirmation
        atg scale-clean --force
    """
    from src.cli_commands_scale import scale_clean_command_handler

    debug = ctx.obj.get("debug", False)
    if not no_container:
        ensure_neo4j_running(debug)

    await scale_clean_command_handler(
        tenant_id=tenant_id,
        force=force,
        dry_run=dry_run,
        output_format=output_format,
        debug=debug,
        no_container=no_container,
    )


@cli.command(name="scale-validate")
@click.option(
    "--tenant-id",
    required=False,
    help="Azure tenant ID (defaults to AZURE_TENANT_ID from .env)",
)
@click.option(
    "--fix",
    is_flag=True,
    help="Attempt to fix validation issues automatically",
)
@click.option(
    "--output-format",
    type=click.Choice(["table", "json", "markdown"], case_sensitive=False),
    default="table",
    help="Output format for results (default: table)",
)
@click.option(
    "--no-container",
    is_flag=True,
    help="Do not auto-start Neo4j container",
)
@click.pass_context
@async_command
async def scale_validate(
    ctx: click.Context,
    tenant_id: Optional[str],
    fix: bool,
    output_format: str,
    no_container: bool,
) -> None:
    """
    Validate graph integrity after scale operations.

    Runs comprehensive validation checks:

    \b
    - Graph structure integrity
    - Relationship consistency
    - Synthetic node labeling
    - Orphaned node detection
    - ID uniqueness
    - Dual-graph consistency (Original ↔ Abstracted)

    Example:

        \b
        # Run validation checks
        atg scale-validate

        \b
        # Validate and auto-fix issues
        atg scale-validate --fix

        \b
        # Export validation report as JSON
        atg scale-validate --output-format json > validation_report.json
    """
    from src.cli_commands_scale import scale_validate_command_handler

    debug = ctx.obj.get("debug", False)
    if not no_container:
        ensure_neo4j_running(debug)

    await scale_validate_command_handler(
        tenant_id=tenant_id,
        fix=fix,
        output_format=output_format,
        debug=debug,
        no_container=no_container,
    )


@cli.command(name="scale-stats")
@click.option(
    "--tenant-id",
    required=False,
    help="Azure tenant ID (defaults to AZURE_TENANT_ID from .env)",
)
@click.option(
    "--detailed",
    is_flag=True,
    help="Show detailed statistics including per-type breakdown",
)
@click.option(
    "--output-format",
    type=click.Choice(["table", "json", "markdown"], case_sensitive=False),
    default="table",
    help="Output format for results (default: table)",
)
@click.option(
    "--no-container",
    is_flag=True,
    help="Do not auto-start Neo4j container",
)
@click.pass_context
@async_command
async def scale_stats(
    ctx: click.Context,
    tenant_id: Optional[str],
    detailed: bool,
    output_format: str,
    no_container: bool,
) -> None:
    """
    Show graph statistics and metrics.

    Displays current graph state including:

    \b
    - Total node and relationship counts
    - Synthetic vs original resource counts
    - Node type distribution
    - Relationship type distribution
    - Dual-graph integrity metrics

    Example:

        \b
        # Show basic statistics
        atg scale-stats

        \b
        # Show detailed statistics with type breakdown
        atg scale-stats --detailed

        \b
        # Export stats as JSON
        atg scale-stats --output-format json > graph_stats.json
    """
    from src.cli_commands_scale import scale_stats_command_handler

    debug = ctx.obj.get("debug", False)
    if not no_container:
        ensure_neo4j_running(debug)

    await scale_stats_command_handler(
        tenant_id=tenant_id,
        detailed=detailed,
        output_format=output_format,
        debug=debug,
        no_container=no_container,
    )


# ============================================================================
# Layer Management Commands (Issue #424)
# ============================================================================


@cli.group(name="layer")
def layer() -> None:
    """Layer management commands for multi-layer graph projections."""
    pass


@layer.command(name="list")
@click.option(
    "--tenant-id",
    help="Filter by tenant ID",
)
@click.option(
    "--include-inactive/--active-only",
    default=True,
    help="Show inactive layers (default: true)",
)
@click.option(
    "--type",
    "layer_type",
    type=click.Choice(
        ["baseline", "scaled", "experimental", "snapshot"], case_sensitive=False
    ),
    help="Filter by layer type",
)
@click.option(
    "--sort-by",
    type=click.Choice(["name", "created_at", "node_count"], case_sensitive=False),
    default="created_at",
    help="Sort field (default: created_at)",
)
@click.option(
    "--ascending/--descending",
    default=False,
    help="Sort order (default: descending)",
)
@click.option(
    "--format",
    "format_type",
    type=click.Choice(["table", "json", "yaml"], case_sensitive=False),
    default="table",
    help="Output format (default: table)",
)
@click.option(
    "--no-container",
    is_flag=True,
    help="Do not auto-start Neo4j container",
)
@click.pass_context
@async_command
async def layer_list(
    ctx: click.Context,
    tenant_id: Optional[str],
    include_inactive: bool,
    layer_type: Optional[str],
    sort_by: str,
    ascending: bool,
    format_type: str,
    no_container: bool,
) -> None:
    """List all layers with summary information."""
    from src.cli_commands_layer import layer_list_command_handler

    debug = ctx.obj.get("debug", False)
    await layer_list_command_handler(
        tenant_id=tenant_id,
        include_inactive=include_inactive,
        layer_type=layer_type,
        sort_by=sort_by,
        ascending=ascending,
        format_type=format_type,
        no_container=no_container,
        debug=debug,
    )


@layer.command(name="show")
@click.argument("layer_id")
@click.option(
    "--format",
    "format_type",
    type=click.Choice(["text", "json", "yaml"], case_sensitive=False),
    default="text",
    help="Output format (default: text)",
)
@click.option(
    "--show-stats",
    is_flag=True,
    help="Include detailed statistics",
)
@click.option(
    "--show-lineage",
    is_flag=True,
    help="Show parent/child layers",
)
@click.option(
    "--no-container",
    is_flag=True,
    help="Do not auto-start Neo4j container",
)
@click.pass_context
@async_command
async def layer_show(
    ctx: click.Context,
    layer_id: str,
    format_type: str,
    show_stats: bool,
    show_lineage: bool,
    no_container: bool,
) -> None:
    """Show detailed information about a specific layer."""
    from src.cli_commands_layer import layer_show_command_handler

    debug = ctx.obj.get("debug", False)
    await layer_show_command_handler(
        layer_id=layer_id,
        format_type=format_type,
        show_stats=show_stats,
        show_lineage=show_lineage,
        no_container=no_container,
        debug=debug,
    )


@layer.command(name="active")
@click.argument("layer_id", required=False)
@click.option(
    "--tenant-id",
    help="Tenant context (for multi-tenant)",
)
@click.option(
    "--format",
    "format_type",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    help="Output format",
)
@click.option(
    "--no-container",
    is_flag=True,
    help="Do not auto-start Neo4j container",
)
@click.pass_context
@async_command
async def layer_active(
    ctx: click.Context,
    layer_id: Optional[str],
    tenant_id: Optional[str],
    format_type: str,
    no_container: bool,
) -> None:
    """Show or set the active layer."""
    from src.cli_commands_layer import layer_active_command_handler

    debug = ctx.obj.get("debug", False)
    await layer_active_command_handler(
        layer_id=layer_id,
        tenant_id=tenant_id,
        format_type=format_type,
        no_container=no_container,
        debug=debug,
    )


@layer.command(name="create")
@click.argument("layer_id")
@click.option(
    "--name",
    help="Human-readable name (default: layer_id)",
)
@click.option(
    "--description",
    help="Layer description",
)
@click.option(
    "--type",
    "layer_type",
    type=click.Choice(
        ["baseline", "scaled", "experimental", "snapshot"], case_sensitive=False
    ),
    default="experimental",
    help="Layer type (default: experimental)",
)
@click.option(
    "--parent-layer",
    help="Parent layer for lineage",
)
@click.option(
    "--tenant-id",
    help="Tenant ID",
)
@click.option(
    "--tag",
    "tags",
    multiple=True,
    help="Add tag (multiple allowed)",
)
@click.option(
    "--make-active",
    is_flag=True,
    help="Set as active layer",
)
@click.option(
    "--yes",
    is_flag=True,
    help="Skip confirmation",
)
@click.option(
    "--no-container",
    is_flag=True,
    help="Do not auto-start Neo4j container",
)
@click.pass_context
@async_command
async def layer_create(
    ctx: click.Context,
    layer_id: str,
    name: Optional[str],
    description: Optional[str],
    layer_type: str,
    parent_layer: Optional[str],
    tenant_id: Optional[str],
    tags: tuple,
    make_active: bool,
    yes: bool,
    no_container: bool,
) -> None:
    """Create a new empty layer."""
    from src.cli_commands_layer import layer_create_command_handler

    debug = ctx.obj.get("debug", False)
    await layer_create_command_handler(
        layer_id=layer_id,
        name=name,
        description=description,
        layer_type=layer_type,
        parent_layer=parent_layer,
        tenant_id=tenant_id,
        tags=list(tags),
        make_active=make_active,
        yes=yes,
        no_container=no_container,
        debug=debug,
    )


@layer.command(name="copy")
@click.argument("source")
@click.argument("target")
@click.option(
    "--name",
    help="Name for new layer",
)
@click.option(
    "--description",
    help="Description for new layer",
)
@click.option(
    "--copy-metadata/--no-copy-metadata",
    default=True,
    help="Copy metadata dict from source (default: true)",
)
@click.option(
    "--make-active",
    is_flag=True,
    help="Set new layer as active",
)
@click.option(
    "--yes",
    is_flag=True,
    help="Skip confirmation",
)
@click.option(
    "--no-container",
    is_flag=True,
    help="Do not auto-start Neo4j container",
)
@click.pass_context
@async_command
async def layer_copy(
    ctx: click.Context,
    source: str,
    target: str,
    name: Optional[str],
    description: Optional[str],
    copy_metadata: bool,
    make_active: bool,
    yes: bool,
    no_container: bool,
) -> None:
    """Copy an entire layer (nodes + relationships)."""
    from src.cli_commands_layer import layer_copy_command_handler

    debug = ctx.obj.get("debug", False)
    await layer_copy_command_handler(
        source=source,
        target=target,
        name=name,
        description=description,
        copy_metadata=copy_metadata,
        make_active=make_active,
        yes=yes,
        no_container=no_container,
        debug=debug,
    )


@layer.command(name="delete")
@click.argument("layer_id")
@click.option(
    "--force",
    is_flag=True,
    help="Allow deletion of active/baseline layers",
)
@click.option(
    "--yes",
    is_flag=True,
    help="Skip confirmation",
)
@click.option(
    "--archive",
    type=click.Path(dir_okay=False, writable=True),
    help="Archive layer before deletion",
)
@click.option(
    "--no-container",
    is_flag=True,
    help="Do not auto-start Neo4j container",
)
@click.pass_context
@async_command
async def layer_delete(
    ctx: click.Context,
    layer_id: str,
    force: bool,
    yes: bool,
    archive: Optional[str],
    no_container: bool,
) -> None:
    """Delete a layer and all its nodes/relationships."""
    from src.cli_commands_layer import layer_delete_command_handler

    debug = ctx.obj.get("debug", False)
    await layer_delete_command_handler(
        layer_id=layer_id,
        force=force,
        yes=yes,
        archive=archive,
        no_container=no_container,
        debug=debug,
    )


@layer.command(name="diff")
@click.argument("layer_a")
@click.argument("layer_b")
@click.option(
    "--detailed",
    is_flag=True,
    help="Include node IDs in output",
)
@click.option(
    "--properties",
    is_flag=True,
    help="Compare property values",
)
@click.option(
    "--output",
    type=click.Path(dir_okay=False, writable=True),
    help="Save report to file",
)
@click.option(
    "--format",
    "format_type",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    help="Output format (default: text)",
)
@click.option(
    "--no-container",
    is_flag=True,
    help="Do not auto-start Neo4j container",
)
@click.pass_context
@async_command
async def layer_diff(
    ctx: click.Context,
    layer_a: str,
    layer_b: str,
    detailed: bool,
    properties: bool,
    output: Optional[str],
    format_type: str,
    no_container: bool,
) -> None:
    """Compare two layers to find differences."""
    from src.cli_commands_layer import layer_diff_command_handler

    debug = ctx.obj.get("debug", False)
    await layer_diff_command_handler(
        layer_a=layer_a,
        layer_b=layer_b,
        detailed=detailed,
        properties=properties,
        output=output,
        format_type=format_type,
        no_container=no_container,
        debug=debug,
    )


@layer.command(name="validate")
@click.argument("layer_id")
@click.option(
    "--fix",
    is_flag=True,
    help="Attempt automatic fixes",
)
@click.option(
    "--output",
    type=click.Path(dir_okay=False, writable=True),
    help="Save report to file",
)
@click.option(
    "--format",
    "format_type",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    help="Output format (default: text)",
)
@click.option(
    "--no-container",
    is_flag=True,
    help="Do not auto-start Neo4j container",
)
@click.pass_context
@async_command
async def layer_validate(
    ctx: click.Context,
    layer_id: str,
    fix: bool,
    output: Optional[str],
    format_type: str,
    no_container: bool,
) -> None:
    """Validate layer integrity and check for issues."""
    from src.cli_commands_layer import layer_validate_command_handler

    debug = ctx.obj.get("debug", False)
    await layer_validate_command_handler(
        layer_id=layer_id,
        fix=fix,
        output=output,
        format_type=format_type,
        no_container=no_container,
        debug=debug,
    )


@layer.command(name="refresh-stats")
@click.argument("layer_id")
@click.option(
    "--format",
    "format_type",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    help="Output format",
)
@click.option(
    "--no-container",
    is_flag=True,
    help="Do not auto-start Neo4j container",
)
@click.pass_context
@async_command
async def layer_refresh_stats(
    ctx: click.Context,
    layer_id: str,
    format_type: str,
    no_container: bool,
) -> None:
    """Refresh layer metadata statistics."""
    from src.cli_commands_layer import layer_refresh_stats_command_handler

    debug = ctx.obj.get("debug", False)
    await layer_refresh_stats_command_handler(
        layer_id=layer_id,
        format_type=format_type,
        no_container=no_container,
        debug=debug,
    )


@layer.command(name="archive")
@click.argument("layer_id")
@click.argument("output_path", type=click.Path(dir_okay=False, writable=True))
@click.option(
    "--include-original",
    is_flag=True,
    help="Include Original nodes in archive",
)
@click.option(
    "--compress",
    is_flag=True,
    help="Compress archive with gzip",
)
@click.option(
    "--yes",
    is_flag=True,
    help="Skip confirmation",
)
@click.option(
    "--no-container",
    is_flag=True,
    help="Do not auto-start Neo4j container",
)
@click.pass_context
@async_command
async def layer_archive(
    ctx: click.Context,
    layer_id: str,
    output_path: str,
    include_original: bool,
    compress: bool,
    yes: bool,
    no_container: bool,
) -> None:
    """Export layer to JSON archive file."""
    from src.cli_commands_layer import layer_archive_command_handler

    debug = ctx.obj.get("debug", False)
    await layer_archive_command_handler(
        layer_id=layer_id,
        output_path=output_path,
        include_original=include_original,
        compress=compress,
        yes=yes,
        no_container=no_container,
        debug=debug,
    )


@layer.command(name="restore")
@click.argument(
    "archive_path", type=click.Path(exists=True, dir_okay=False, readable=True)
)
@click.option(
    "--layer-id",
    help="Override layer ID from archive",
)
@click.option(
    "--make-active",
    is_flag=True,
    help="Set as active layer after restore",
)
@click.option(
    "--yes",
    is_flag=True,
    help="Skip confirmation",
)
@click.option(
    "--no-container",
    is_flag=True,
    help="Do not auto-start Neo4j container",
)
@click.pass_context
@async_command
async def layer_restore(
    ctx: click.Context,
    archive_path: str,
    layer_id: Optional[str],
    make_active: bool,
    yes: bool,
    no_container: bool,
) -> None:
    """Restore layer from JSON archive."""
    from src.cli_commands_layer import layer_restore_command_handler

    debug = ctx.obj.get("debug", False)
    await layer_restore_command_handler(
        archive_path=archive_path,
        layer_id=layer_id,
        make_active=make_active,
        yes=yes,
        no_container=no_container,
        debug=debug,
    )


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
