"""Scaling operations commands.

This module provides commands for graph scaling operations:
- 'scale-up': Add synthetic nodes to the graph
  - 'template': Template-based generation
  - 'scenario': Scenario-based generation
- 'scale-down': Sample/reduce the graph
  - 'algorithm': Algorithm-based sampling
  - 'pattern': Pattern-based filtering
- 'scale-clean': Clean up synthetic data
- 'scale-validate': Validate graph integrity
- 'scale-stats': Show graph statistics

Issue #427: Scaling Operations
Issue #482: CLI Modularization (Phase 2)
"""

from typing import Optional

import click

from src.utils.neo4j_startup import ensure_neo4j_running


@click.group(name="scale-up")
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
def scale_up_template(
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

    # Import asyncio to run async handler
    import asyncio

    asyncio.run(
        scale_up_template_command_handler(
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
def scale_up_scenario(
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

    # Import asyncio to run async handler
    import asyncio

    asyncio.run(
        scale_up_scenario_command_handler(
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
    )


@click.group(name="scale-down")
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
def scale_down_algorithm(
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

    # Import asyncio to run async handler
    import asyncio

    asyncio.run(
        scale_down_algorithm_command_handler(
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
def scale_down_pattern(
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

    # Import asyncio to run async handler
    import asyncio

    asyncio.run(
        scale_down_pattern_command_handler(
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
    )


@click.command(name="scale-clean")
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
def scale_clean(
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

    # Import asyncio to run async handler
    import asyncio

    asyncio.run(
        scale_clean_command_handler(
            tenant_id=tenant_id,
            force=force,
            dry_run=dry_run,
            output_format=output_format,
            debug=debug,
            no_container=no_container,
        )
    )


@click.command(name="scale-validate")
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
def scale_validate(
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

    # Import asyncio to run async handler
    import asyncio

    asyncio.run(
        scale_validate_command_handler(
            tenant_id=tenant_id,
            fix=fix,
            output_format=output_format,
            debug=debug,
            no_container=no_container,
        )
    )


@click.command(name="scale-stats")
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
def scale_stats(
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

    # Import asyncio to run async handler
    import asyncio

    asyncio.run(
        scale_stats_command_handler(
            tenant_id=tenant_id,
            detailed=detailed,
            output_format=output_format,
            debug=debug,
            no_container=no_container,
        )
    )


# For backward compatibility - export command groups
scale_up_group = scale_up
scale_down_group = scale_down

# Export individual commands for direct registration
scale_clean_command = scale_clean
scale_validate_command = scale_validate
scale_stats_command = scale_stats

__all__ = [
    "scale_clean",
    "scale_clean_command",
    "scale_down",
    "scale_down_algorithm",
    "scale_down_group",
    "scale_down_pattern",
    "scale_stats",
    "scale_stats_command",
    # Command groups
    "scale_up",
    "scale_up_group",
    "scale_up_scenario",
    # Individual commands
    "scale_up_template",
    "scale_validate",
    "scale_validate_command",
]
