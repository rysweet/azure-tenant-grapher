"""Agent mode command.

This module provides the 'agent-mode' command for starting
the AutoGen MCP agent mode with Neo4j and agent chat loop.

Issue #716: Complete CLI command migration
"""

import logging
import traceback
from typing import Optional

import click

from src.commands.base import async_command


@click.command("agent-mode")
@click.option(
    "--question",
    help="Ask a single question and exit (non-interactive mode)",
)
@click.pass_context
@async_command
async def agent_mode(ctx: click.Context, question: Optional[str]) -> None:
    """Start AutoGen MCP agent mode (Neo4j + MCP server + agent chat loop).

    This command starts:
    - Neo4j database (if not running)
    - MCP server for graph access
    - AutoGen agent chat loop for interactive queries

    Examples:
        # Interactive mode
        atg agent-mode

        # Single question mode
        atg agent-mode --question "Show all VMs in subscription X"
    """
    await agent_mode_command_handler(ctx, question)


async def agent_mode_command_handler(
    ctx: click.Context, question: Optional[str] = None
) -> None:
    """
    Start Neo4j, MCP server, and launch AutoGen MCP agent chat loop.

    Args:
        ctx: Click context
        question: Optional single question for non-interactive mode
    """
    from src.agent_mode import run_agent_mode

    try:
        logging.basicConfig(level=ctx.obj.get("log_level", "INFO"))
        await run_agent_mode(question=question)
    except Exception as e:
        click.echo(f"❌ Failed to start agent mode: {e}", err=True)
        traceback.print_exc()


# For backward compatibility
agent_mode_command = agent_mode

__all__ = ["agent_mode", "agent_mode_command_handler"]
