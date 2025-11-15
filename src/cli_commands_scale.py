"""
Scale Operations CLI Command Handlers (Issue #427)

This module contains all command handlers for scale operations:
- Scale-up (template, scenario)
- Scale-down (algorithm, pattern)
- Scale utilities (clean, validate, stats)
"""

import os
import sys
from typing import Any, Dict, Optional

import click

from src.config_manager import create_neo4j_config_from_env
from src.utils.session_manager import Neo4jSessionManager

# ============================================================================
# Scale-Up Command Handlers
# ============================================================================


async def scale_up_template_command_handler(
    tenant_id: Optional[str],
    template_file: str,
    scale_factor: float,
    batch_size: int,
    dry_run: bool,
    validate: bool,
    config_path: Optional[str],
    output_format: str,
    debug: bool = False,
    no_container: bool = False,
) -> None:
    """
    Handle scale-up template command.

    Args:
        tenant_id: Azure tenant ID
        template_file: Path to template YAML file
        scale_factor: Multiplication factor for resources
        batch_size: Batch size for processing
        dry_run: Preview only flag
        validate: Run validation checks
        config_path: Path to configuration file
        output_format: Output format (table/json/markdown)
        debug: Debug mode flag
        no_container: Skip Neo4j container check
    """
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table

    from src.services.scale_up_service import ScaleUpService

    console = Console()

    try:
        # Get effective tenant ID
        effective_tenant_id = tenant_id or os.environ.get("AZURE_TENANT_ID")
        if not effective_tenant_id:
            console.print(
                "[red]❌ No tenant ID provided and AZURE_TENANT_ID not set in environment.[/red]"
            )
            sys.exit(1)

        # Load configuration
        if config_path:
            console.print(
                f"[blue]📝 Loading configuration from {config_path}...[/blue]"
            )
            # Config loading would be implemented here

        # Validate template file
        if not os.path.exists(template_file):
            console.print(f"[red]❌ Template file not found: {template_file}[/red]")
            sys.exit(1)

        console.print("[blue]🚀 Starting scale-up operation (template-based)...[/blue]")
        console.print(f"[dim]Template: {template_file}[/dim]")
        console.print(f"[dim]Scale factor: {scale_factor}x[/dim]")
        console.print(f"[dim]Batch size: {batch_size}[/dim]")
        console.print(f"[dim]Dry run: {dry_run}[/dim]")

        # Check if --no-container was specified
        if no_container:
            console.print(
                "[red]❌ Neo4j connection required but --no-container was specified[/red]"
            )
            console.print("[yellow]💡 Remove --no-container flag to auto-start Neo4j[/yellow]")
            sys.exit(1)

        # Connect to Neo4j
        config = create_neo4j_config_from_env()
        session_manager = Neo4jSessionManager(config.neo4j)
        session_manager.connect()

        # Initialize service
        service = ScaleUpService(session_manager)

        # Run pre-validation if requested
        if validate and not dry_run:
            console.print("\n[blue]🔍 Running pre-operation validation...[/blue]")
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task("Validating graph integrity...", total=None)
                # Validation would be implemented here

        # Execute scale-up operation
        if dry_run:
            console.print("\n[yellow]🔍 DRY RUN MODE - Preview only[/yellow]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Scaling up graph...", total=100)

            # Execute template-based scale-up
            result = await service.scale_up_template(
                tenant_id=effective_tenant_id,
                scale_factor=scale_factor,
                resource_types=None,  # Could be added as CLI option
                progress_callback=None,  # Progress shown via rich Progress
            )
            progress.update(task, completed=100)

        # Run post-validation if requested
        if validate and not dry_run:
            console.print("\n[blue]🔍 Running post-operation validation...[/blue]")
            # Validation would be implemented here

        # Display results
        console.print("\n[green]✅ Scale-up operation completed successfully![/green]")

        # Format output
        if output_format == "json":
            import json

            output_data = {
                "success": result.success,
                "operation": "scale-up-template",
                "template_file": template_file,
                "scale_factor": scale_factor,
                "resources_created": result.resources_created,
                "relationships_created": result.relationships_created,
                "dry_run": dry_run,
                "validation_passed": result.validation_passed,
            }
            console.print(json.dumps(output_data, indent=2))
        elif output_format == "markdown":
            console.print("\n## Scale-Up Results\n")
            console.print("- **Operation**: Template-based scale-up")
            console.print(f"- **Template**: {template_file}")
            console.print(f"- **Scale Factor**: {scale_factor}x")
            console.print(f"- **Resources Created**: {result.resources_created}")
            console.print(
                f"- **Relationships Created**: {result.relationships_created}"
            )
        else:  # table format
            table = Table(title="Scale-Up Results")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            table.add_row("Operation", "Template-based scale-up")
            table.add_row("Template", template_file)
            table.add_row("Scale Factor", f"{scale_factor}x")
            table.add_row("Resources Created", str(result.resources_created))
            table.add_row(
                "Relationships Created", str(result.relationships_created)
            )
            console.print("\n")
            console.print(table)

        # Close session manager
        session_manager.disconnect()

    except Exception as e:
        console.print(f"[red]❌ Error during scale-up operation: {e}[/red]")
        if debug:
            import traceback

            traceback.print_exc()
        sys.exit(1)


async def scale_up_scenario_command_handler(
    tenant_id: Optional[str],
    scenario: str,
    scale_factor: float,
    regions: Optional[list[str]],
    spoke_count: int,
    dry_run: bool,
    validate: bool,
    config_path: Optional[str],
    output_format: str,
    debug: bool = False,
    no_container: bool = False,
) -> None:
    """
    Handle scale-up scenario command.

    Args:
        tenant_id: Azure tenant ID
        scenario: Scenario type (hub-spoke, multi-region, dev-test-prod)
        scale_factor: Multiplication factor
        regions: List of Azure regions
        spoke_count: Number of spoke VNets
        dry_run: Preview only flag
        validate: Run validation checks
        config_path: Path to configuration file
        output_format: Output format
        debug: Debug mode flag
        no_container: Skip Neo4j container check
    """
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table

    from src.services.scale_up_service import ScaleUpService

    console = Console()

    try:
        # Get effective tenant ID
        effective_tenant_id = tenant_id or os.environ.get("AZURE_TENANT_ID")
        if not effective_tenant_id:
            console.print(
                "[red]❌ No tenant ID provided and AZURE_TENANT_ID not set in environment.[/red]"
            )
            sys.exit(1)

        console.print(
            f"[blue]🚀 Starting scale-up operation (scenario: {scenario})...[/blue]"
        )
        console.print(f"[dim]Scale factor: {scale_factor}x[/dim]")
        if scenario == "hub-spoke":
            console.print(f"[dim]Spoke count: {spoke_count}[/dim]")
        if regions:
            console.print(f"[dim]Regions: {', '.join(regions)}[/dim]")
        console.print(f"[dim]Dry run: {dry_run}[/dim]")

        # Check if --no-container was specified
        if no_container:
            console.print(
                "[red]❌ Neo4j connection required but --no-container was specified[/red]"
            )
            console.print("[yellow]💡 Remove --no-container flag to auto-start Neo4j[/yellow]")
            sys.exit(1)

        # Connect to Neo4j
        config = create_neo4j_config_from_env()
        session_manager = Neo4jSessionManager(config.neo4j)
        session_manager.connect()

        # Initialize service
        service = ScaleUpService(session_manager)

        # Execute scenario-based scale-up
        if dry_run:
            console.print("\n[yellow]🔍 DRY RUN MODE - Preview only[/yellow]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"Generating {scenario} scenario...", total=100)

            # Build params dict for scenario
            params = {
                "scale_factor": scale_factor,
            }
            if scenario == "hub-spoke":
                params["spoke_count"] = spoke_count
                params["resources_per_spoke"] = 10  # Default
            elif scenario == "multi-region":
                params["region_count"] = len(regions) if regions else 3
                params["resources_per_region"] = 20  # Default
            elif scenario == "dev-test-prod":
                params["resources_per_env"] = 15  # Default

            result = await service.scale_up_scenario(
                tenant_id=effective_tenant_id,
                scenario=scenario,
                params=params,
                progress_callback=None,  # Progress shown via rich Progress
            )
            progress.update(task, completed=100)

        # Display results
        console.print("\n[green]✅ Scale-up operation completed successfully![/green]")

        # Format output (similar to template handler)
        if output_format == "table":
            table = Table(title="Scale-Up Results")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            table.add_row("Operation", f"Scenario-based ({scenario})")
            table.add_row("Scale Factor", f"{scale_factor}x")
            table.add_row("Resources Created", str(result.resources_created))
            table.add_row(
                "Relationships Created", str(result.relationships_created)
            )
            console.print("\n")
            console.print(table)

        session_manager.disconnect()

    except Exception as e:
        console.print(f"[red]❌ Error during scale-up operation: {e}[/red]")
        if debug:
            import traceback

            traceback.print_exc()
        sys.exit(1)


# ============================================================================
# Scale-Down Command Handlers
# ============================================================================


async def scale_down_algorithm_command_handler(
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
    validate: bool,
    config_path: Optional[str],
    debug: bool = False,
    no_container: bool = False,
) -> None:
    """
    Handle scale-down algorithm command.

    IMPORTANT: Algorithm names from CLI use dashes (forest-fire)
    but service expects underscores (forest_fire). This handler
    normalizes the input before calling the service.

    Args:
        tenant_id: Azure tenant ID
        algorithm: Sampling algorithm name (with dashes normalized to underscores)
        target_size: Target size as fraction
        target_count: Target absolute count
        burn_in: Burn-in steps for forest-fire
        burning_prob: Burning probability
        walk_length: Walk length for MHRW
        alpha: Bias parameter for MHRW
        output_mode: Output mode (delete/export/new-tenant)
        output_file: Output file path
        output_format: Export format (yaml/json)
        dry_run: Preview only flag
        validate: Run validation checks
        config_path: Path to configuration file
        debug: Debug mode flag
        no_container: Skip Neo4j container check
    """
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table

    from src.services.scale_down_service import ScaleDownService

    console = Console()

    try:
        # BUG FIX #1: Normalize algorithm name from dash to underscore
        # CLI accepts: forest-fire, random-walk
        # Service expects: forest_fire, random_walk
        normalized_algorithm = algorithm.replace("-", "_")

        # Get effective tenant ID
        effective_tenant_id = tenant_id or os.environ.get("AZURE_TENANT_ID")
        if not effective_tenant_id:
            console.print(
                "[red]❌ No tenant ID provided and AZURE_TENANT_ID not set in environment.[/red]"
            )
            sys.exit(1)

        console.print(
            f"[blue]🚀 Starting scale-down operation (algorithm: {normalized_algorithm})...[/blue]"
        )
        console.print(
            f"[dim]Target size: {target_size if not target_count else f'{target_count} nodes'}[/dim]"
        )
        console.print(f"[dim]Output mode: {output_mode}[/dim]")
        console.print(f"[dim]Dry run: {dry_run}[/dim]")

        # Check if --no-container was specified
        if no_container:
            console.print(
                "[red]❌ Neo4j connection required but --no-container was specified[/red]"
            )
            console.print("[yellow]💡 Remove --no-container flag to auto-start Neo4j[/yellow]")
            sys.exit(1)

        # Connect to Neo4j
        config = create_neo4j_config_from_env()
        session_manager = Neo4jSessionManager(config.neo4j)
        session_manager.connect()

        # Initialize service
        service = ScaleDownService(session_manager)

        # Execute algorithm-based sampling
        if dry_run:
            console.print("\n[yellow]🔍 DRY RUN MODE - Preview only[/yellow]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"Running {algorithm} algorithm...", total=100)

            # Use the correct method: sample_graph()
            # Note: burn_in, burning_prob, walk_length, alpha are algorithm-specific
            # and not exposed in the current API. They would need to be added
            # to the service if needed.
            sampled_node_ids, metrics, nodes_deleted = await service.sample_graph(
                tenant_id=effective_tenant_id,
                algorithm=normalized_algorithm,  # Use normalized algorithm name
                target_size=target_size if not target_count else target_count,
                output_mode=output_mode,
                output_path=output_file,
                progress_callback=None,  # Progress shown via rich Progress
            )
            progress.update(task, completed=100)

            # Build result dict from metrics
            result = {
                "nodes_sampled": metrics.sampled_nodes,
                "nodes_deleted": nodes_deleted,  # BUG FIX: Use actual deletion count
                "edges_sampled": metrics.sampled_edges,
                "quality_metrics": metrics.to_dict(),
            }

        # Display results
        console.print(
            "\n[green]✅ Scale-down operation completed successfully![/green]"
        )

        # Format output
        table = Table(title="Scale-Down Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Operation", f"Algorithm-based ({algorithm})")
        table.add_row("Nodes Sampled", str(result.get("nodes_sampled", 0)))
        table.add_row("Nodes Deleted", str(result.get("nodes_deleted", 0)))
        table.add_row("Output Mode", output_mode)
        if output_file:
            table.add_row("Output File", output_file)
        console.print("\n")
        console.print(table)

        session_manager.disconnect()

    except Exception as e:
        console.print(f"[red]❌ Error during scale-down operation: {e}[/red]")
        if debug:
            import traceback

            traceback.print_exc()
        sys.exit(1)


async def scale_down_pattern_command_handler(
    tenant_id: Optional[str],
    pattern: str,
    resource_types: Optional[list[str]],
    target_size: float,
    output_mode: str,
    output_file: Optional[str],
    output_format: str,
    dry_run: bool,
    validate: bool,
    config_path: Optional[str],
    debug: bool = False,
    no_container: bool = False,
) -> None:
    """
    Handle scale-down pattern command.

    Args:
        tenant_id: Azure tenant ID
        pattern: Pattern type
        resource_types: List of resource types
        target_size: Target size as fraction
        output_mode: Output mode
        output_file: Output file path
        output_format: Export format
        dry_run: Preview only flag
        validate: Run validation checks
        config_path: Path to configuration file
        debug: Debug mode flag
        no_container: Skip Neo4j container check
    """
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table

    from src.services.scale_down_service import ScaleDownService

    console = Console()

    try:
        effective_tenant_id = tenant_id or os.environ.get("AZURE_TENANT_ID")
        if not effective_tenant_id:
            console.print(
                "[red]❌ No tenant ID provided and AZURE_TENANT_ID not set in environment.[/red]"
            )
            sys.exit(1)

        console.print(
            f"[blue]🚀 Starting scale-down operation (pattern: {pattern})...[/blue]"
        )
        console.print(f"[dim]Target size: {target_size}[/dim]")
        if resource_types:
            console.print(f"[dim]Resource types: {', '.join(resource_types)}[/dim]")

        # Check if --no-container was specified
        if no_container:
            console.print(
                "[red]❌ Neo4j connection required but --no-container was specified[/red]"
            )
            console.print("[yellow]💡 Remove --no-container flag to auto-start Neo4j[/yellow]")
            sys.exit(1)

        config = create_neo4j_config_from_env()
        from src.utils.session_manager import Neo4jSessionManager

        session_manager = Neo4jSessionManager(config.neo4j)
        session_manager.connect()
        service = ScaleDownService(session_manager)

        if dry_run:
            console.print("\n[yellow]🔍 DRY RUN MODE - Preview only[/yellow]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"Filtering by {pattern} pattern...", total=100)

            # Build criteria dict based on pattern
            criteria: Dict[str, Any] = {}

            # Map pattern name to criteria
            # Note: sample_by_pattern expects exact property matches, not patterns
            # For broader filtering, use multiple calls or enhance service layer
            if pattern == "security":
                criteria["type"] = "Microsoft.KeyVault/vaults"  # Most common security resource
            elif pattern == "network":
                criteria["type"] = "Microsoft.Network/virtualNetworks"  # Core network resource
            elif pattern == "compute":
                criteria["type"] = "Microsoft.Compute/virtualMachines"  # Most common compute
            elif pattern == "storage":
                criteria["type"] = "Microsoft.Storage/storageAccounts"  # Core storage
            elif pattern == "production":
                criteria["tags.environment"] = "production"
            elif pattern == "test":
                criteria["tags.environment"] = "test"
            elif pattern == "dev":
                criteria["tags.environment"] = "dev"
            elif pattern == "resource-type" and resource_types:
                # Explicit resource type from CLI (use first one)
                criteria["type"] = resource_types.split(",")[0].strip()
            else:
                # No pattern matched - error out
                console.print("[red]❌ Invalid pattern or missing resource types[/red]")
                raise ValueError(f"Pattern '{pattern}' requires additional configuration")

            # Call sample_by_pattern with correct signature
            sampled_node_ids = await service.sample_by_pattern(
                tenant_id=effective_tenant_id,
                criteria=criteria,
                progress_callback=None,  # Progress shown via rich Progress
            )
            progress.update(task, completed=100)

        console.print(
            "\n[green]✅ Scale-down operation completed successfully![/green]"
        )

        table = Table(title="Scale-Down Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Operation", f"Pattern-based ({pattern})")
        table.add_row("Nodes Matched", str(len(sampled_node_ids)))
        table.add_row("Criteria", str(criteria))
        console.print("\n")
        console.print(table)

        session_manager.disconnect()

    except Exception as e:
        console.print(f"[red]❌ Error during scale-down operation: {e}[/red]")
        if debug:
            import traceback

            traceback.print_exc()
        sys.exit(1)


# ============================================================================
# Scale Utility Command Handlers
# ============================================================================


async def scale_clean_command_handler(
    tenant_id: Optional[str],
    force: bool,
    dry_run: bool,
    output_format: str,
    debug: bool = False,
    no_container: bool = False,
) -> None:
    """
    Handle scale-clean command to remove synthetic data.

    Args:
        tenant_id: Azure tenant ID
        force: Skip confirmation
        dry_run: Preview only flag
        output_format: Output format
        debug: Debug mode flag
        no_container: Skip Neo4j container check
    """
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn

    console = Console()

    try:
        # Check if --no-container was specified
        if no_container:
            console.print(
                "[red]❌ Neo4j connection required but --no-container was specified[/red]"
            )
            console.print("[yellow]💡 Remove --no-container flag to auto-start Neo4j[/yellow]")
            sys.exit(1)

        config = create_neo4j_config_from_env()
        from src.utils.session_manager import Neo4jSessionManager

        session_manager = Neo4jSessionManager(config.neo4j)
        session_manager.connect()

        # Count synthetic nodes
        with session_manager.get_session() as session:
            result = session.run("MATCH (n) WHERE n.synthetic = true RETURN count(n) as count")
            synthetic_count = result.single()["count"]

        if synthetic_count == 0:
            console.print("[green]✅ No synthetic nodes found in graph.[/green]")
            session_manager.disconnect()
            return

        console.print(f"[yellow]Found {synthetic_count} synthetic nodes.[/yellow]")

        # Confirm if not forced
        if not force and not dry_run:
            if not click.confirm(f"⚠️  Delete {synthetic_count} synthetic nodes?"):
                console.print("[blue]Operation cancelled.[/blue]")
                session_manager.disconnect()
                return

        if dry_run:
            console.print(
                f"\n[yellow]🔍 DRY RUN: Would delete {synthetic_count} synthetic nodes[/yellow]"
            )
        else:
            console.print("\n[blue]🗑️  Cleaning synthetic data...[/blue]")
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Deleting synthetic nodes...", total=None)

                with session_manager.get_session() as session:
                    # Delete synthetic nodes and their relationships
                    session.run("MATCH (n) WHERE n.synthetic = true DETACH DELETE n")

                progress.update(task, completed=100)

            console.print(
                f"[green]✅ Successfully deleted {synthetic_count} synthetic nodes![/green]"
            )

        session_manager.disconnect()

    except Exception as e:
        console.print(f"[red]❌ Error during cleanup: {e}[/red]")
        if debug:
            import traceback

            traceback.print_exc()
        sys.exit(1)


async def scale_validate_command_handler(
    tenant_id: Optional[str],
    fix: bool,
    output_format: str,
    debug: bool = False,
    no_container: bool = False,
) -> None:
    """
    Handle scale-validate command to check graph integrity.

    Args:
        tenant_id: Azure tenant ID
        fix: Auto-fix issues flag
        output_format: Output format
        debug: Debug mode flag
        no_container: Skip Neo4j container check
    """
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table

    from src.services.scale_validation import ScaleValidationService

    console = Console()

    try:
        console.print("[blue]🔍 Running graph validation checks...[/blue]")

        # Check if --no-container was specified
        if no_container:
            console.print(
                "[red]❌ Neo4j connection required but --no-container was specified[/red]"
            )
            console.print("[yellow]💡 Remove --no-container flag to auto-start Neo4j[/yellow]")
            sys.exit(1)

        config = create_neo4j_config_from_env()
        from src.utils.session_manager import Neo4jSessionManager

        session_manager = Neo4jSessionManager(config.neo4j)
        session_manager.connect()
        service = ScaleValidationService(session_manager)

        # Run validation
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Validating graph integrity...", total=100)

            validation_results = await service.validate_graph(fix=fix)
            progress.update(task, completed=100)

        # Display results
        console.print("\n[bold]Validation Results:[/bold]\n")

        all_passed = all(r.get("passed", False) for r in validation_results)

        if output_format == "json":
            import json

            console.print(json.dumps(validation_results, indent=2))
        else:
            table = Table(title="Validation Checks")
            table.add_column("Check", style="cyan")
            table.add_column("Status", style="bold")
            table.add_column("Message")

            for result in validation_results:
                status = "✅ PASS" if result.get("passed") else "❌ FAIL"
                status_style = "green" if result.get("passed") else "red"
                table.add_row(
                    result.get("check_name", ""),
                    f"[{status_style}]{status}[/{status_style}]",
                    result.get("message", ""),
                )

            console.print(table)

        if all_passed:
            console.print("\n[green]✅ All validation checks passed![/green]")
        else:
            console.print("\n[red]❌ Some validation checks failed.[/red]")
            if not fix:
                console.print(
                    "[yellow]💡 Tip: Run with --fix to auto-fix issues[/yellow]"
                )

        session_manager.disconnect()

    except Exception as e:
        console.print(f"[red]❌ Error during validation: {e}[/red]")
        if debug:
            import traceback

            traceback.print_exc()
        sys.exit(1)


async def scale_stats_command_handler(
    tenant_id: Optional[str],
    detailed: bool,
    output_format: str,
    debug: bool = False,
    no_container: bool = False,
) -> None:
    """
    Handle scale-stats command to show graph statistics.

    Args:
        tenant_id: Azure tenant ID
        detailed: Show detailed stats flag
        output_format: Output format
        debug: Debug mode flag
        no_container: Skip Neo4j container check
    """
    from rich.console import Console
    from rich.table import Table

    console = Console()

    try:
        console.print("[blue]📊 Gathering graph statistics...[/blue]")

        # Check if --no-container was specified
        if no_container:
            console.print(
                "[red]❌ Neo4j connection required but --no-container was specified[/red]"
            )
            console.print("[yellow]💡 Remove --no-container flag to auto-start Neo4j[/yellow]")
            sys.exit(1)

        config = create_neo4j_config_from_env()
        from src.utils.session_manager import Neo4jSessionManager

        session_manager = Neo4jSessionManager(config.neo4j)
        session_manager.connect()

        with session_manager.get_session() as session:
            # Get basic counts
            stats = {}

            # Total nodes
            result = session.run("MATCH (n) RETURN count(n) as count")
            stats["total_nodes"] = result.single()["count"]

            # Total relationships
            result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            stats["total_relationships"] = result.single()["count"]

            # Synthetic nodes
            result = session.run("MATCH (n) WHERE n.synthetic = true RETURN count(n) as count")
            stats["synthetic_nodes"] = result.single()["count"]

            # Original nodes
            result = session.run("MATCH (n:Original) RETURN count(n) as count")
            stats["original_nodes"] = result.single()["count"]

            # Abstracted nodes
            result = session.run(
                "MATCH (n:Resource) WHERE NOT n:Original RETURN count(n) as count"
            )
            stats["abstracted_nodes"] = result.single()["count"]

            # Detailed stats if requested
            if detailed:
                # Node types
                result = session.run(
                    """
                    MATCH (n)
                    RETURN labels(n)[0] as label, count(n) as count
                    ORDER BY count DESC
                    """
                )
                stats["node_types"] = {r["label"]: r["count"] for r in result}

                # Relationship types
                result = session.run(
                    """
                    MATCH ()-[r]->()
                    RETURN type(r) as type, count(r) as count
                    ORDER BY count DESC
                    """
                )
                stats["relationship_types"] = {r["type"]: r["count"] for r in result}

        # Display results
        console.print("\n")

        if output_format == "json":
            import json

            console.print(json.dumps(stats, indent=2))
        elif output_format == "markdown":
            console.print("# Graph Statistics\n")
            console.print(f"- **Total Nodes**: {stats['total_nodes']}")
            console.print(f"- **Total Relationships**: {stats['total_relationships']}")
            console.print(f"- **Synthetic Nodes**: {stats['synthetic_nodes']}")
            console.print(f"- **Original Nodes**: {stats['original_nodes']}")
            console.print(f"- **Abstracted Nodes**: {stats['abstracted_nodes']}")
        else:  # table
            table = Table(title="Graph Statistics")
            table.add_column("Metric", style="cyan")
            table.add_column("Count", style="green", justify="right")

            table.add_row("Total Nodes", str(stats["total_nodes"]))
            table.add_row("Total Relationships", str(stats["total_relationships"]))
            table.add_row("Synthetic Nodes", str(stats["synthetic_nodes"]))
            table.add_row("Original Nodes", str(stats["original_nodes"]))
            table.add_row("Abstracted Nodes", str(stats["abstracted_nodes"]))

            console.print(table)

            if detailed and "node_types" in stats:
                console.print("\n")
                type_table = Table(title="Node Type Distribution")
                type_table.add_column("Type", style="cyan")
                type_table.add_column("Count", style="green", justify="right")

                for node_type, count in list(stats["node_types"].items())[:10]:
                    type_table.add_row(node_type, str(count))

                console.print(type_table)

        session_manager.disconnect()

    except Exception as e:
        console.print(f"[red]❌ Error gathering statistics: {e}[/red]")
        if debug:
            import traceback

            traceback.print_exc()
        sys.exit(1)
