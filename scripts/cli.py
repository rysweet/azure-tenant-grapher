#!/usr/bin/env python3
"""
Enhanced CLI wrapper for Azure Tenant Grapher

This script provides an improved command-line interface with better error handling,
configuration validation, and progress tracking.
"""

import asyncio
import functools
import os
import sys
from typing import Any, Callable, Coroutine, Optional

from dotenv import load_dotenv
from rich.logging import RichHandler
from rich.style import Style


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

    from src.cli_commands import (
        build_command_handler,
        generate_spec_command_handler,
        progress_command_handler,
        spec_command_handler,
        visualize_command_handler,
    )
    from src.config_manager import create_config_from_env
    from src.container_manager import Neo4jContainerManager
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Please ensure all required packages are installed:")
    print("pip install -r requirements.txt")
    sys.exit(1)


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
    test_keypress_queue: bool,
    test_keypress_file: str,
) -> None:
    """
    Build the complete Azure tenant graph with enhanced processing.

    By default, shows a live Rich dashboard with progress, logs, and interactive controls:
      - Press 'x' to exit the dashboard at any time.
      - Press 'i', 'd', or 'w' to set log level to INFO, DEBUG, or WARNING.

    Use --no-dashboard to disable the dashboard and emit logs line by line to the terminal.
    """
    await build_command_handler(
        ctx,
        tenant_id,
        resource_limit,
        max_llm_threads,
        no_container,
        generate_spec,
        visualize,
        no_dashboard,
        test_keypress_queue,
        test_keypress_file,
    )


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
async def spec(ctx: click.Context, tenant_id: str) -> None:
    """Generate only the tenant specification (requires existing graph)."""
    await spec_command_handler(ctx, tenant_id)


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
    await progress_command_handler(ctx)


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


def main() -> None:
    """Main entry point."""
    cli()  # type: ignore[reportCallIssue]


if __name__ == "__main__":
    main()
