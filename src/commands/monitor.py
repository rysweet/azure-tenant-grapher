"""Database monitoring command.

This module provides the 'monitor' command for monitoring
Neo4j database resource counts and relationships.

Issue #482: CLI Modularization
"""

import sys
import time
from collections import deque
from datetime import datetime, timezone
from typing import Optional

import click

from src.commands.base import async_command, get_neo4j_config_from_env
from src.utils.neo4j_startup import ensure_neo4j_running


@click.command("monitor")
@click.option(
    "--subscription-id",
    help="Filter by subscription ID",
)
@click.option(
    "--interval",
    default=30,
    type=int,
    help="Check interval in seconds (default: 30)",
)
@click.option(
    "--watch",
    is_flag=True,
    help="Continuous monitoring mode (like watch command)",
)
@click.option(
    "--detect-stabilization",
    is_flag=True,
    help="Exit when database metrics have stabilized",
)
@click.option(
    "--threshold",
    default=3,
    type=int,
    help="Number of identical checks to consider stable (default: 3)",
)
@click.option(
    "--format",
    "format_type",
    type=click.Choice(["json", "table", "compact"]),
    default="compact",
    help="Output format (default: compact)",
)
@click.option(
    "--no-container",
    is_flag=True,
    help="Do not auto-start Neo4j container",
)
@click.pass_context
@async_command
async def monitor(
    ctx: click.Context,
    subscription_id: Optional[str],
    interval: int,
    watch: bool,
    detect_stabilization: bool,
    threshold: int,
    format_type: str,
    no_container: bool,
) -> None:
    """Monitor Neo4j database resource counts and relationships.

    This command queries the Neo4j database to display current resource counts,
    relationships, resource groups, and resource types. It can run once or
    continuously monitor the database.

    Examples:

        # Single check
        atg monitor

        # Single check for specific subscription
        atg monitor --subscription-id 9b00bc5e-9abc-45de-9958-02a9d9277b16

        # Watch mode with 60 second interval
        atg monitor --watch --interval 60

        # Detect when database has stabilized
        atg monitor --watch --detect-stabilization --threshold 3

        # JSON output format
        atg monitor --format json

        # Table output format with watch
        atg monitor --watch --format table
    """
    await monitor_command_handler(
        subscription_id=subscription_id,
        interval=interval,
        watch=watch,
        detect_stabilization=detect_stabilization,
        threshold=threshold,
        format_type=format_type,
        no_container=no_container,
    )


async def monitor_command_handler(
    subscription_id: Optional[str],
    interval: int,
    watch: bool,
    detect_stabilization: bool,
    threshold: int,
    format_type: str,
    no_container: bool = False,
) -> None:
    """
    Monitor Neo4j database resource counts and relationships.

    Args:
        subscription_id: Filter by subscription ID
        interval: Check interval in seconds
        watch: Continuous monitoring mode
        detect_stabilization: Exit when stable
        threshold: Stabilization threshold (consecutive identical counts)
        format_type: Output format (json|table|compact)
        no_container: Skip auto-starting Neo4j container
    """
    import json

    from neo4j import GraphDatabase

    # Ensure Neo4j is running (unless --no-container is set)
    if not no_container:
        ensure_neo4j_running()

    # Get Neo4j connection details from environment
    neo4j_uri, neo4j_user, neo4j_password = get_neo4j_config_from_env()

    # Connect to Neo4j
    try:
        driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        # Test connection
        driver.verify_connectivity()
    except Exception as e:
        click.echo(f"Failed to connect to Neo4j: {e}", err=True)
        sys.exit(1)

    # Track counts for stabilization detection
    count_history: deque[tuple[int, int, int]] = deque(maxlen=threshold)

    def get_metrics() -> dict[str, int]:
        """Query Neo4j for current metrics."""
        with driver.session() as session:
            metrics = {}

            # Base filter clause
            filter_clause = (
                "WHERE r.subscription_id = $sub_id" if subscription_id else ""
            )

            # Count resources
            query_resources = (
                f"MATCH (r:Resource) {filter_clause} RETURN count(r) as count"
            )
            params = {"sub_id": subscription_id} if subscription_id else {}
            result = session.run(query_resources, params)
            metrics["resources"] = result.single()["count"]  # type: ignore[misc]

            # Count relationships
            query_relationships = (
                f"MATCH (r:Resource)-[rel]-() {filter_clause} "
                "RETURN count(DISTINCT rel) as count"
            )
            result = session.run(query_relationships, params)
            metrics["relationships"] = result.single()["count"]  # type: ignore[misc]

            # Count resource groups
            query_rgs = (
                f"MATCH (r:Resource) {filter_clause} "
                "AND r.resourceGroup IS NOT NULL "
                "RETURN count(DISTINCT r.resourceGroup) as count"
            )
            result = session.run(query_rgs, params)
            metrics["resource_groups"] = result.single()["count"]  # type: ignore[misc]

            # Count resource types
            query_types = (
                f"MATCH (r:Resource) {filter_clause} "
                "RETURN count(DISTINCT r.type) as count"
            )
            result = session.run(query_types, params)
            metrics["resource_types"] = result.single()["count"]  # type: ignore[misc]

            return metrics

    def format_output(metrics: dict[str, int], is_stable: bool = False) -> str:
        """Format metrics based on output format type."""
        timestamp = datetime.now(tz=timezone.utc).strftime("%H:%M:%S")

        if format_type == "json":
            output = {
                "timestamp": timestamp,
                "resources": metrics["resources"],
                "relationships": metrics["relationships"],
                "resource_groups": metrics["resource_groups"],
                "resource_types": metrics["resource_types"],
                "stable": is_stable,
            }
            return json.dumps(output)

        if format_type == "table":
            # Table format with headers
            stable_str = "stable" if is_stable else "changing"
            return (
                f"{timestamp:<12} {metrics['resources']:<12} "
                f"{metrics['relationships']:<15} {metrics['resource_groups']:<16} "
                f"{metrics['resource_types']:<14} {stable_str}"
            )

        # compact (default)
        stable_marker = " (stable)" if is_stable else ""
        return (
            f"[{timestamp}] Resources={metrics['resources']} "
            f"Relationships={metrics['relationships']} "
            f"ResourceGroups={metrics['resource_groups']} "
            f"Types={metrics['resource_types']}{stable_marker}"
        )

    def check_stabilization(current_metrics: dict[str, int]) -> bool:
        """Check if metrics have stabilized."""
        if not detect_stabilization:
            return False

        # Add current counts to history
        current_tuple = (
            current_metrics["resources"],
            current_metrics["relationships"],
            current_metrics["resource_groups"],
        )
        count_history.append(current_tuple)

        # Need at least 'threshold' samples
        if len(count_history) < threshold:
            return False

        # Check if all recent counts are identical
        return len(set(count_history)) == 1

    try:
        # Print header for table format
        if format_type == "table":
            click.echo(
                "Timestamp    Resources    Relationships   "
                "Resource Groups  Resource Types  Status"
            )
            click.echo("-" * 90)

        # Main monitoring loop
        first_check = True
        while True:
            try:
                # Get current metrics
                metrics = get_metrics()

                # Check for stabilization
                is_stable = check_stabilization(metrics)

                # Output results
                output = format_output(metrics, is_stable)
                click.echo(output)

                # Exit if stabilized
                if is_stable and detect_stabilization:
                    if format_type != "json":
                        click.echo(
                            f"\nDatabase has stabilized "
                            f"(threshold: {threshold} identical checks)"
                        )
                    break

                # Exit if not in watch mode (single check)
                if not watch:
                    break

                # Wait for next check
                if not first_check:
                    time.sleep(interval)
                first_check = False

            except KeyboardInterrupt:
                click.echo("\nMonitoring interrupted by user")
                break
            except Exception as e:
                click.echo(f"\nError during monitoring: {e}", err=True)
                if watch:
                    click.echo("Retrying in 5 seconds...")
                    time.sleep(5)
                else:
                    break

    finally:
        driver.close()


# For backward compatibility
monitor_command = monitor

__all__ = ["monitor", "monitor_command", "monitor_command_handler"]
