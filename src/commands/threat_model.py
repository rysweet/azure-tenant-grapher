"""Threat modeling command.

This module provides the 'threat-model' command for running
the Threat Modeling Agent workflow.

Issue #482: CLI Modularization
"""

from typing import Optional

import click

from src.commands.base import async_command


@click.command("threat-model")
@click.pass_context
@async_command
async def threat_model(ctx: click.Context) -> None:
    """Run the Threat Modeling Agent workflow.

    Generates a DFD, enumerates threats, and produces a Markdown report
    from the current Neo4j graph.
    """
    await generate_threat_model_command_handler(ctx)


async def generate_threat_model_command_handler(
    ctx: Optional[click.Context] = None,
) -> None:
    """
    Handler for the threat-model CLI command.
    Runs the ThreatModelAgent workflow and prints/logs each stage.
    """
    from src.threat_modeling_agent.agent import ThreatModelAgent

    click.echo("Starting Threat Modeling Agent workflow...")
    agent = ThreatModelAgent()
    report_path = await agent.run()
    click.echo("Threat Modeling Agent workflow complete.")
    if report_path:
        click.echo(f"Threat modeling report saved to: {report_path}")


# For backward compatibility
threat_model_command = threat_model

__all__ = [
    "generate_threat_model_command_handler",
    "threat_model",
    "threat_model_command",
]
