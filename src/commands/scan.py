"""Scan/build commands.

This module provides the core scanning commands:
- 'build': Build Azure tenant graph
- 'scan': Alias for build
- 'test': Run a quick test scan with limited resources

Issue #482: CLI Modularization
"""

import os
import sys
from typing import Optional

import click

from src.commands.base import async_command


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
) -> Optional[str]:
    """
    Build the complete Azure tenant graph with enhanced processing.

    By default, shows a live Rich dashboard with progress, logs, and interactive controls:
      - Press 'x' to exit the dashboard at any time.
      - Press 'i', 'd', or 'w' to set log level to INFO, DEBUG, or WARNING.

    Use --no-dashboard to disable the dashboard and emit logs line by line to the terminal.
    """
    # Import the handler from cli_commands to maintain backward compatibility
    from src.cli_commands import build_command_handler

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
    from src.cli_commands import build_command_handler

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
    from src.cli_commands import build_command_handler

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
