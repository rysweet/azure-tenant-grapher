"""Fidelity calculation command.

This module provides the 'fidelity' command for calculating and tracking
resource replication fidelity between subscriptions.

Issue #482: CLI Modularization
"""

import sys
from typing import Optional

import click

from src.commands.base import async_command, get_neo4j_config_from_env
from src.utils.neo4j_startup import ensure_neo4j_running


@click.command("fidelity")
@click.option(
    "--source-subscription",
    required=True,
    help="Source subscription ID to compare from",
)
@click.option(
    "--target-subscription",
    required=True,
    help="Target subscription ID to compare to",
)
@click.option(
    "--track",
    is_flag=True,
    help="Track fidelity metrics to demos/fidelity_history.jsonl",
)
@click.option(
    "--output",
    help="Export fidelity metrics to JSON file",
)
@click.option(
    "--check-objective",
    help="Path to OBJECTIVE.md file for compliance checking",
)
@click.option(
    "--no-container",
    is_flag=True,
    help="Do not auto-start Neo4j container",
)
@click.pass_context
@async_command
async def fidelity(
    ctx: click.Context,
    source_subscription: str,
    target_subscription: str,
    track: bool,
    output: Optional[str],
    check_objective: Optional[str],
    no_container: bool,
) -> None:
    """Calculate and track resource replication fidelity between subscriptions.

    This command compares resource counts, types, and relationships between a source
    and target subscription to measure replication fidelity.

    Examples:

        # Calculate current fidelity
        atg fidelity --source-subscription 9b00bc5e-9abc-45de-9958-02a9d9277b16 \\
                     --target-subscription c190c55a-9ab2-4b1e-92c4-cc8b1a032285

        # Track fidelity over time
        atg fidelity --source-subscription SOURCE_ID \\
                     --target-subscription TARGET_ID \\
                     --track

        # Export to JSON
        atg fidelity --source-subscription SOURCE_ID \\
                     --target-subscription TARGET_ID \\
                     --output fidelity_report.json

        # Check against objective
        atg fidelity --source-subscription SOURCE_ID \\
                     --target-subscription TARGET_ID \\
                     --check-objective demos/OBJECTIVE.md
    """
    await fidelity_command_handler(
        source_subscription=source_subscription,
        target_subscription=target_subscription,
        track=track,
        output=output,
        check_objective=check_objective,
        no_container=no_container,
    )


async def fidelity_command_handler(
    source_subscription: str,
    target_subscription: str,
    track: bool = False,
    output: Optional[str] = None,
    check_objective: Optional[str] = None,
    no_container: bool = False,
) -> None:
    """
    Calculate and track resource replication fidelity between subscriptions.

    Args:
        source_subscription: Source subscription ID
        target_subscription: Target subscription ID
        track: Enable time-series tracking
        output: Output file path for JSON export
        check_objective: Path to OBJECTIVE.md file for compliance checking
        no_container: Skip auto-starting Neo4j container
    """
    from src.fidelity_calculator import FidelityCalculator

    # Ensure Neo4j is running (unless --no-container is set)
    if not no_container:
        ensure_neo4j_running()

    # Get Neo4j connection details from environment
    neo4j_uri, neo4j_user, neo4j_password = get_neo4j_config_from_env()

    try:
        # Create calculator
        calculator = FidelityCalculator(neo4j_uri, neo4j_user, neo4j_password)

        # Determine target fidelity if checking objective
        target_fidelity = 95.0  # Default
        if check_objective:
            try:
                objective_met, target_fidelity = calculator.check_objective(
                    check_objective,
                    0.0,  # Will recalculate below
                )
            except OSError:
                click.echo(
                    f"Could not read objective file: {check_objective}",
                    err=True,
                )

        # Calculate fidelity
        click.echo("Calculating fidelity between subscriptions...")
        try:
            metrics = calculator.calculate_fidelity(
                source_subscription, target_subscription, target_fidelity
            )
        except ValueError as e:
            click.echo(f"{e}", err=True)
            calculator.close()
            sys.exit(1)

        # Display results
        click.echo("\n" + "=" * 60)
        click.echo("Fidelity Report")
        click.echo("=" * 60)
        click.echo(f"\nTimestamp: {metrics.timestamp}")

        click.echo("\nSource Subscription:")
        click.echo(f"  Subscription ID: {metrics.source_subscription_id}")
        click.echo(f"  Resources: {metrics.source_resources}")
        click.echo(f"  Relationships: {metrics.source_relationships}")
        click.echo(f"  Resource Groups: {metrics.source_resource_groups}")
        click.echo(f"  Resource Types: {metrics.source_resource_types}")

        click.echo("\nTarget Subscription:")
        click.echo(f"  Subscription ID: {metrics.target_subscription_id}")
        click.echo(f"  Resources: {metrics.target_resources}")
        click.echo(f"  Relationships: {metrics.target_relationships}")
        click.echo(f"  Resource Groups: {metrics.target_resource_groups}")
        click.echo(f"  Resource Types: {metrics.target_resource_types}")

        click.echo("\nFidelity Metrics:")
        click.echo(f"  Overall Fidelity: {metrics.overall_fidelity:.1f}%")
        click.echo(f"  Missing Resources: {metrics.missing_resources}")
        click.echo(f"  Target Fidelity: {metrics.target_fidelity:.1f}%")

        # Objective status
        if metrics.objective_met:
            click.echo("  Objective MET")
        else:
            click.echo("  Objective NOT MET")

        # Show top resource types by fidelity
        if metrics.fidelity_by_type:
            click.echo("\nFidelity by Resource Type (top 10):")
            sorted_types = sorted(
                metrics.fidelity_by_type.items(), key=lambda x: x[1], reverse=True
            )[:10]
            for resource_type, fidelity_val in sorted_types:
                click.echo(f"  {resource_type}: {fidelity_val:.1f}%")

        click.echo("=" * 60)

        # Track to history file if requested
        if track:
            try:
                calculator.track_fidelity(metrics)
                click.echo(
                    "\nFidelity metrics tracked to demos/fidelity_history.jsonl"
                )
            except OSError as e:
                click.echo(f"\nFailed to track metrics: {e}", err=True)

        # Export to JSON if output path provided
        if output:
            try:
                calculator.export_to_json(metrics, output)
                click.echo(f"\nFidelity metrics exported to {output}")
            except OSError as e:
                click.echo(f"\nFailed to export metrics: {e}", err=True)

        calculator.close()

    except Exception as e:
        click.echo(f"Failed to calculate fidelity: {e}", err=True)
        import traceback

        traceback.print_exc()
        sys.exit(1)


# For backward compatibility
fidelity_command = fidelity

__all__ = ["fidelity", "fidelity_command", "fidelity_command_handler"]
