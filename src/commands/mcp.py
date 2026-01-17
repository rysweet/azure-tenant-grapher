"""MCP (Model Context Protocol) commands.

This module provides MCP-related commands:
- 'mcp-server': Start MCP server
- 'mcp-query': Execute natural language queries via MCP

Issue #482: CLI Modularization
"""

import json
import os
import sys
from typing import Optional

import click

from src.commands.base import async_command


async def mcp_server_command_handler(ctx: click.Context) -> None:
    """
    Ensure Neo4j is running, then launch MCP server (uvx mcp-neo4j-cypher).

    Issue #482: CLI Modularization - migrated from cli_commands.py
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


@click.command("mcp-server")
@click.pass_context
@async_command
async def mcp_server(ctx: click.Context) -> None:
    """Start MCP server (uvx mcp-neo4j-cypher) after ensuring Neo4j is running."""
    await mcp_server_command_handler(ctx)


@click.command("mcp-query")
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
    "output_format",
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
    output_format: str,
) -> None:
    """Execute natural language queries for Azure resources via MCP.

    Examples:
        atg mcp-query "list all virtual machines"
        atg mcp-query "show storage accounts in westus2"
        atg mcp-query "find resources with public IP addresses"
        atg mcp-query "analyze security posture of my key vaults"

    This is an experimental feature that requires MCP_ENABLED=true in your .env file.
    """
    debug = ctx.obj.get("debug", False)
    await mcp_query_command_handler(
        ctx,
        query,
        tenant_id=tenant_id,
        use_fallback=not no_fallback,
        output_format=output_format,
        debug=debug,
    )


async def mcp_query_command_handler(
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
    from src.config_manager import create_config_from_env, setup_logging
    from src.services.azure_discovery_service import AzureDiscoveryService
    from src.services.mcp_integration import MCPConfig as MCPIntegrationConfig
    from src.services.mcp_integration import MCPIntegrationService
    from src.utils.mcp_startup import ensure_mcp_running_async

    # Get tenant ID
    effective_tenant_id = tenant_id or os.environ.get("AZURE_TENANT_ID")
    if not effective_tenant_id:
        click.echo(
            "No tenant ID provided and AZURE_TENANT_ID not set in environment.",
            err=True,
        )
        sys.exit(1)

    # Create configuration
    config = create_config_from_env(effective_tenant_id, debug=debug)
    setup_logging(config.logging)

    # Check if MCP is configured
    if not config.mcp.enabled:
        click.echo(
            "[INFO] MCP is not enabled. Set MCP_ENABLED=true in your .env file to enable."
        )
        click.echo(
            "MCP is required for natural language queries. Please enable it first."
        )
        sys.exit(1)

    # Ensure MCP server is running
    click.echo("Ensuring MCP server is running...")
    try:
        await ensure_mcp_running_async(debug=debug)
        click.echo("MCP server is ready")
    except RuntimeError as e:
        click.echo(f"Failed to start MCP server: {e}", err=True)
        sys.exit(1)

    # Initialize services
    discovery_service = None
    if use_fallback:
        try:
            discovery_service = AzureDiscoveryService(config)
            click.echo("Traditional discovery service initialized as fallback")
        except Exception as e:
            click.echo(f"Warning: Could not initialize discovery service: {e}")

    # Convert config.mcp to MCPIntegrationConfig
    mcp_config = MCPIntegrationConfig(
        endpoint=config.mcp.endpoint,
        enabled=config.mcp.enabled,
        timeout=config.mcp.timeout,
        api_key=config.mcp.api_key,
    )
    mcp_service = MCPIntegrationService(mcp_config, discovery_service)

    try:
        # Connect to MCP
        click.echo(f"Connecting to MCP at {config.mcp.endpoint}...")
        connected = await mcp_service.initialize()

        if not connected:
            click.echo("MCP connection failed after server startup", err=True)
            click.echo("Please check the MCP server logs for errors.")
            sys.exit(1)

        click.echo("MCP connection established")

        # Execute the query
        click.echo(f"\nExecuting query: {query}")
        click.echo("-" * 60)

        success, result = await mcp_service.natural_language_command(query)

        if success:
            click.echo("Query executed successfully\n")

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
                                click.echo(f"  {name} ({res_type}) - {location}")
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
            click.echo("Query failed\n")
            if isinstance(result, dict):
                if "error" in result:
                    click.echo(f"Error: {result['error']}")
                if "suggestion" in result:
                    click.echo(f"Suggestion: {result['suggestion']}")
            else:
                click.echo(f"Error: {result}")

    except KeyboardInterrupt:
        click.echo("\nQuery interrupted by user")
        sys.exit(130)
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        if debug:
            import traceback

            traceback.print_exc()
        sys.exit(1)
    finally:
        # Clean up
        await mcp_service.close()
        click.echo("\nMCP session closed")


# For backward compatibility
mcp_server_command = mcp_server
mcp_query_command = mcp_query

__all__ = [
    "mcp_query",
    "mcp_query_command",
    "mcp_query_command_handler",
    "mcp_server",
    "mcp_server_command",
    "mcp_server_command_handler",
]
