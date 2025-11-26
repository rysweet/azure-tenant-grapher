"""Tenant specification commands.

This module provides commands for tenant specification generation:
- 'spec': Generate tenant specification from existing graph
- 'generate-spec': Generate anonymized tenant specification

Issue #482: CLI Modularization
"""

import os
import sys
from datetime import datetime, timezone
from typing import Optional

import click

from src.azure_tenant_grapher import AzureTenantGrapher
from src.commands.base import async_command
from src.config_manager import (
    create_config_from_env,
    create_neo4j_config_from_env,
    setup_logging,
)
from src.utils.neo4j_startup import ensure_neo4j_running


@click.command("spec")
@click.option(
    "--tenant-id",
    required=False,
    help="Azure tenant ID (defaults to AZURE_TENANT_ID from .env)",
)
@click.option(
    "--domain-name",
    required=False,
    help="Domain name to use for all entities that require one (e.g., user accounts)",
)
@click.pass_context
@async_command
async def spec(
    ctx: click.Context, tenant_id: str, domain_name: Optional[str] = None
) -> None:
    """Generate only the tenant specification (requires existing graph)."""
    await spec_command_handler(ctx, tenant_id, domain_name)


async def spec_command_handler(
    ctx: click.Context, tenant_id: str, domain_name: Optional[str] = None
) -> None:
    """Handle the spec command logic."""
    ensure_neo4j_running()
    effective_tenant_id = tenant_id or os.environ.get("AZURE_TENANT_ID")
    if not effective_tenant_id:
        click.echo(
            "No tenant ID provided and AZURE_TENANT_ID not set in environment.",
            err=True,
        )
        sys.exit(1)

    try:
        # Create configuration
        config = create_config_from_env(effective_tenant_id)
        config.logging.level = ctx.obj["log_level"]

        # Setup logging
        setup_logging(config.logging)

        # Validate Azure OpenAI configuration
        if not config.azure_openai.is_configured():
            click.echo(
                "Azure OpenAI not configured. Tenant specification requires LLM capabilities.\n"
                "Action: Set the required Azure OpenAI environment variables (AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY, AZURE_OPENAI_API_VERSION) and try again.",
                err=True,
            )
            sys.exit(1)

        # Create grapher and generate specification
        grapher = AzureTenantGrapher(config)

        click.echo("Generating tenant specification from existing graph...")
        # Pass domain_name to the grapher if/when supported
        await grapher.generate_tenant_specification(domain_name=domain_name)
        click.echo("Tenant specification generated successfully")

    except Exception as e:
        click.echo(
            f"Failed to generate specification: {e}\n"
            "Action: Check that Neo4j and Azure OpenAI are configured correctly. Run with --log-level DEBUG for more details.",
            err=True,
        )
        sys.exit(1)


@click.command("generate-spec")
@click.option(
    "--limit", type=int, default=None, help="Resource limit (overrides config)"
)
@click.option("--output", type=str, default=None, help="Custom output path")
@click.option(
    "--hierarchical",
    is_flag=True,
    help="Generate hierarchical specification organized by Tenant->Subscription->Region->ResourceGroup",
)
@click.pass_context
def generate_spec(
    ctx: click.Context, limit: Optional[int], output: Optional[str], hierarchical: bool
) -> None:
    """Generate anonymized tenant Markdown specification (no tenant-id required)."""
    generate_spec_command_handler(ctx, limit, output, hierarchical)


def generate_spec_command_handler(
    ctx: click.Context,
    limit: Optional[int],
    output: Optional[str],
    hierarchical: bool = False,
) -> None:
    """Handle the generate-spec command logic."""
    ensure_neo4j_running()

    try:
        # Load config (Neo4j-only)
        config = create_neo4j_config_from_env()
        config.logging.level = ctx.obj["log_level"]
        setup_logging(config.logging)

        # Neo4j connection info
        neo4j_uri = config.neo4j.uri or ""
        neo4j_user = config.neo4j.user
        neo4j_password = config.neo4j.password

        # Spec config
        spec_config = config.specification
        if limit is not None:
            spec_config.resource_limit = limit

        # Ensure outputs/ dir exists for defaulting
        os.makedirs("outputs", exist_ok=True)

        # Choose generator based on hierarchical flag
        from src.tenant_spec_generator import ResourceAnonymizer

        # Anonymizer
        anonymizer = ResourceAnonymizer(seed=spec_config.anonymization_seed)

        if hierarchical:
            from src.hierarchical_spec_generator import HierarchicalSpecGenerator

            # Generator
            generator = HierarchicalSpecGenerator(
                neo4j_uri, neo4j_user, neo4j_password, anonymizer, spec_config
            )

            click.echo("Generating hierarchical tenant specification...")
        else:
            from src.tenant_spec_generator import TenantSpecificationGenerator

            # Generator
            generator = TenantSpecificationGenerator(
                neo4j_uri, neo4j_user, neo4j_password, anonymizer, spec_config
            )

        # Default output to outputs/ if not specified
        effective_output = output
        if not effective_output:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            prefix = "hierarchical_" if hierarchical else ""
            effective_output = os.path.join("outputs", f"{prefix}{ts}_tenant_spec.md")

        output_path = generator.generate_specification(output_path=effective_output)
        click.echo(f"Tenant Markdown specification generated: {output_path}")

    except Exception as e:
        import traceback

        click.echo(f"Failed to generate tenant specification: {e}", err=True)
        traceback.print_exc()
        sys.exit(1)


# For backward compatibility
spec_command = spec
generate_spec_command = generate_spec

__all__ = [
    "generate_spec",
    "generate_spec_command",
    "generate_spec_command_handler",
    "spec",
    "spec_command",
    "spec_command_handler",
]
