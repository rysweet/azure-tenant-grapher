"""
Stub for Threat Modeling Agent CLI entrypoint.
"""

import asyncio

import click

from src.cli_commands import generate_threat_model_command_handler


@click.group()
def threat_modeling_agent():
    """Threat Modeling Agent CLI group."""
    pass


@threat_modeling_agent.command("generate-threat-model")
def generate_threat_model_cmd():
    """Run the Threat Modeling Agent workflow."""
    asyncio.run(generate_threat_model_command_handler(None))
