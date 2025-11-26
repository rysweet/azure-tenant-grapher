"""Agent mode command.

This module provides the 'agent-mode' command for starting
the AutoGen MCP agent mode with Neo4j and agent chat loop.

Issue #482: CLI Modularization
"""

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
    """Start AutoGen MCP agent mode (Neo4j + MCP server + agent chat loop)."""
    from src.cli_commands import agent_mode_command_handler

    await agent_mode_command_handler(ctx, question)


# For backward compatibility
agent_mode_command = agent_mode

__all__ = ["agent_mode", "agent_mode_command"]
