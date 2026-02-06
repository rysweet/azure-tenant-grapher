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
    required=False,
    default=None,
    help="Source subscription ID to compare from (optional for resource-level)",
)
@click.option(
    "--target-subscription",
    required=False,
    default=None,
    help="Target subscription ID to compare to (optional for resource-level)",
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
@click.option(
    "--resource-level",
    is_flag=True,
    help="Enable resource-level fidelity validation (property-level comparison)",
)
@click.option(
    "--resource-type",
    help="Filter validation to specific resource type (e.g., Microsoft.Storage/storageAccounts)",
)
@click.option(
    "--redaction-level",
    type=click.Choice(["FULL", "MINIMAL", "NONE"], case_sensitive=False),
    default="FULL",
    help="Security redaction level for sensitive properties (default: FULL)",
)
@click.pass_context
@async_command
async def fidelity(
    ctx: click.Context,
    source_subscription: Optional[str],
    target_subscription: Optional[str],
    track: bool,
    output: Optional[str],
    check_objective: Optional[str],
    no_container: bool,
    resource_level: bool,
    resource_type: Optional[str],
    redaction_level: str,
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

        # Resource-level validation (property comparison)
        atg fidelity --source-subscription SOURCE_ID \\
                     --target-subscription TARGET_ID \\
                     --resource-level

        # Filter by resource type with minimal redaction
        atg fidelity --source-subscription SOURCE_ID \\
                     --target-subscription TARGET_ID \\
                     --resource-level \\
                     --resource-type Microsoft.Storage/storageAccounts \\
                     --redaction-level MINIMAL
    """
    await fidelity_command_handler(
        source_subscription=source_subscription,
        target_subscription=target_subscription,
        track=track,
        output=output,
        check_objective=check_objective,
        no_container=no_container,
        resource_level=resource_level,
        resource_type=resource_type,
        redaction_level=redaction_level,
    )


async def fidelity_command_handler(
    source_subscription: str,
    target_subscription: str,
    track: bool = False,
    output: Optional[str] = None,
    check_objective: Optional[str] = None,
    no_container: bool = False,
    resource_level: bool = False,
    resource_type: Optional[str] = None,
    redaction_level: str = "FULL",
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
        resource_level: Enable resource-level validation with property comparison
        resource_type: Filter to specific resource type
        redaction_level: Security redaction level (FULL, MINIMAL, NONE)
    """
    # Route to resource-level handler if requested
    if resource_level:
        await fidelity_resource_level_handler(
            source_subscription=source_subscription,
            target_subscription=target_subscription,
            output=output,
            no_container=no_container,
            resource_type=resource_type,
            redaction_level=redaction_level,
        )
        return

    # Original subscription-level fidelity logic continues below
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
                click.echo("\nFidelity metrics tracked to demos/fidelity_history.jsonl")
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


async def fidelity_resource_level_handler(
    source_subscription: Optional[str],
    target_subscription: Optional[str],
    output: Optional[str] = None,
    no_container: bool = False,
    resource_type: Optional[str] = None,
    redaction_level: str = "FULL",
) -> None:
    """
    Handle resource-level fidelity validation with property comparison.

    Args:
        source_subscription: Source subscription ID (defaults to "source" if not provided)
        target_subscription: Target subscription ID (defaults to "target" if not provided)
        output: Output file path for JSON export
        no_container: Skip auto-starting Neo4j container
        resource_type: Filter to specific resource type
        redaction_level: Security redaction level (FULL, MINIMAL, NONE)
    """
    import json
    from datetime import datetime

    from rich.console import Console
    from rich.table import Table

    from src.config_manager import Neo4jConfig
    from src.utils.session_manager import Neo4jSessionManager
    from src.validation.resource_fidelity_calculator import (
        RedactionLevel,
        ResourceFidelityCalculator,
        ResourceStatus,
    )

    # Ensure Neo4j is running
    if not no_container:
        ensure_neo4j_running()

    # Get Neo4j connection details
    neo4j_uri, neo4j_user, neo4j_password = get_neo4j_config_from_env()

    # Use defaults if subscriptions not provided (for testing)
    source_sub = source_subscription or "source-subscription"
    target_sub = target_subscription or "target-subscription"

    # Map string to enum
    redaction_enum = RedactionLevel[redaction_level.upper()]

    console = Console()

    try:
        # Create Neo4j config and session manager
        neo4j_config = Neo4jConfig(uri=neo4j_uri, user=neo4j_user, password=neo4j_password)
        async with Neo4jSessionManager(neo4j_config) as session_manager:
            # Create calculator
            calculator = ResourceFidelityCalculator(
                session_manager=session_manager,
                source_subscription_id=source_sub,
                target_subscription_id=target_sub,
            )

            # Show security warning for NONE redaction
            if redaction_enum == RedactionLevel.NONE:
                console.print("\n[bold red]WARNING: NO REDACTION ENABLED![/bold red]")
                console.print("[yellow]All sensitive data (passwords, keys, secrets) will be visible.[/yellow]")
                console.print("[yellow]Only use this mode in secure environments for debugging.[/yellow]\n")

            # Calculate fidelity
            console.print("Calculating resource-level fidelity...")
            if resource_type:
                console.print(f"Filtering by resource type: {resource_type}")

            result = calculator.calculate_fidelity(
                resource_type=resource_type, redaction_level=redaction_enum
            )

            # Display console table
            console.print("\n")
            console.print("=" * 80)
            console.print("[bold]Resource-Level Fidelity Validation Report[/bold]")
            console.print("=" * 80)

            # Metadata
            console.print(f"\nTimestamp: {result.validation_timestamp}")
            console.print(f"Source Subscription: {result.source_subscription}")
            console.print(f"Target Subscription: {result.target_subscription}")
            console.print(f"Redaction Level: {result.redaction_level.value.upper()}")
            if resource_type:
                console.print(f"Resource Type Filter: {resource_type}")

            # Summary metrics
            console.print("\n[bold]Summary Metrics:[/bold]")
            metrics_table = Table(show_header=False)
            metrics_table.add_row("Total Resources", str(result.metrics.total_resources))
            metrics_table.add_row("Exact Match", f"[green]{result.metrics.exact_match}[/green]")
            metrics_table.add_row("Drifted", f"[yellow]{result.metrics.drifted}[/yellow]")
            metrics_table.add_row("Missing in Target", f"[red]{result.metrics.missing_target}[/red]")
            metrics_table.add_row("Missing in Source", f"[blue]{result.metrics.missing_source}[/blue]")
            metrics_table.add_row("Match Percentage", f"{result.metrics.match_percentage:.1f}%")
            console.print(metrics_table)

            # Resource details
            if result.classifications:
                console.print("\n[bold]Resource Details:[/bold]")
                resource_table = Table(show_header=True, header_style="bold")
                resource_table.add_column("Resource Name", style="cyan")
                resource_table.add_column("Type", style="magenta")
                resource_table.add_column("Status", style="bold")
                resource_table.add_column("Mismatches", justify="right")

                for classification in result.classifications:
                    status_style = {
                        ResourceStatus.EXACT_MATCH: "[green]✓ MATCH[/green]",
                        ResourceStatus.DRIFTED: "[yellow]⚠ DRIFT[/yellow]",
                        ResourceStatus.MISSING_TARGET: "[red]✗ MISSING TARGET[/red]",
                        ResourceStatus.MISSING_SOURCE: "[blue]• MISSING SOURCE[/blue]",
                    }.get(classification.status, classification.status.value)

                    resource_table.add_row(
                        classification.resource_name,
                        classification.resource_type,
                        status_style,
                        str(classification.mismatch_count) if classification.mismatch_count > 0 else "-",
                    )

                console.print(resource_table)

                # Show property mismatches for drifted resources
                drifted = [c for c in result.classifications if c.status == ResourceStatus.DRIFTED]
                if drifted:
                    console.print("\n[bold]Property Mismatches (Drifted Resources):[/bold]")
                    for classification in drifted[:5]:  # Show top 5
                        console.print(f"\n[cyan]{classification.resource_name}[/cyan]:")
                        mismatches = [c for c in classification.property_comparisons if not c.match and not c.redacted]
                        for mismatch in mismatches[:5]:  # Show top 5 properties per resource
                            console.print(f"  • {mismatch.property_path}")
                            console.print(f"    Source: {mismatch.source_value}")
                            console.print(f"    Target: {mismatch.target_value}")

            # Top mismatched properties
            if result.metrics.top_mismatched_properties:
                console.print("\n[bold]Top Mismatched Properties:[/bold]")
                top_props_table = Table(show_header=True)
                top_props_table.add_column("Property Path", style="cyan")
                top_props_table.add_column("Count", justify="right")

                for prop in result.metrics.top_mismatched_properties:
                    top_props_table.add_row(prop["property"], str(prop["count"]))

                console.print(top_props_table)

            # Security warnings
            if result.security_warnings:
                console.print("\n[bold]Security Warnings:[/bold]")
                for warning in result.security_warnings:
                    console.print(f"  {warning}")

            console.print("\n" + "=" * 80 + "\n")

            # Export to JSON if requested
            if output:
                try:
                    # Build security warnings for export
                    export_security_warnings = list(result.security_warnings)

                    # Add handling instructions based on redaction level
                    if redaction_enum == RedactionLevel.NONE:
                        export_security_warnings.extend([
                            "CRITICAL: This export contains UNREDACTED sensitive data!",
                            "Handle with extreme care - contains passwords, keys, and secrets.",
                            "Do NOT share this file or commit to version control.",
                            "Delete this file when no longer needed.",
                            "Consider re-exporting with FULL redaction for sharing.",
                        ])
                    elif redaction_enum == RedactionLevel.MINIMAL:
                        export_security_warnings.extend([
                            "This export contains partially redacted data.",
                            "Server information may be visible in connection strings.",
                            "Review carefully before sharing.",
                        ])
                    else:  # FULL
                        export_security_warnings.append(
                            "This export has FULL redaction - safe for sharing in most contexts."
                        )

                    output_data = {
                        "metadata": {
                            "validation_timestamp": result.validation_timestamp,
                            "source_subscription": result.source_subscription,
                            "target_subscription": result.target_subscription,
                            "redaction_level": result.redaction_level.value,
                            "resource_type_filter": resource_type,
                            "security_level": "FULL" if redaction_enum == RedactionLevel.FULL else
                                             "MINIMAL" if redaction_enum == RedactionLevel.MINIMAL else "NONE",
                        },
                        "security_warnings": export_security_warnings,
                        "summary": {
                            "total_resources": result.metrics.total_resources,
                            "exact_match": result.metrics.exact_match,
                            "drifted": result.metrics.drifted,
                            "missing_target": result.metrics.missing_target,
                            "missing_source": result.metrics.missing_source,
                            "match_percentage": result.metrics.match_percentage,
                        },
                        "resources": [
                            {
                                "id": c.resource_id,
                                "name": c.resource_name,
                                "type": c.resource_type,
                                "status": c.status.value,
                                "source_exists": c.source_exists,
                                "target_exists": c.target_exists,
                                "mismatch_count": c.mismatch_count,
                                "match_count": c.match_count,
                                "property_comparisons": [
                                    {
                                        "property_path": p.property_path,
                                        "source_value": p.source_value,
                                        "target_value": p.target_value,
                                        "match": p.match,
                                        "redacted": p.redacted,
                                    }
                                    for p in c.property_comparisons
                                ],
                            }
                            for c in result.classifications
                        ],
                        "top_mismatched_properties": result.metrics.top_mismatched_properties,
                    }

                    with open(output, "w") as f:
                        json.dump(output_data, f, indent=2)

                    console.print(f"[green]Report exported to: {output}[/green]")

                except Exception as e:
                    console.print(f"[red]Failed to export report: {e}[/red]")

    except Exception as e:
        console.print(f"\n[red]Error calculating resource-level fidelity: {e}[/red]")
        import traceback

        traceback.print_exc()
        sys.exit(1)


# For backward compatibility
fidelity_command = fidelity

__all__ = ["fidelity", "fidelity_command", "fidelity_command_handler", "fidelity_resource_level_handler"]
