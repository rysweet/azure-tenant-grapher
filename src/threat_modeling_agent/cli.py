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
@click.option(
    "--spec-path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, readable=True),
    help="Path to the tenant specification file (Markdown or JSON).",
)
@click.option(
    "--summaries-path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, readable=True),
    help="Path to the LLM summaries file (JSON).",
)
def generate_threat_model_cmd(spec_path, summaries_path):
    """Run the Threat Modeling Agent workflow."""
    asyncio.run(generate_threat_model_command_handler(None, spec_path, summaries_path))
