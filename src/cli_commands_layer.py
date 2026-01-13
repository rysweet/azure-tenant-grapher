"""
CLI Command Handlers for Layer Management

Implements all layer management commands per LAYER_CLI_SPECIFICATION.md:
- atg layer list: List all layers with filtering and sorting
- atg layer create: Create new empty layer
- atg layer show: Display detailed layer information
- atg layer active: Show or set active layer
- atg layer delete: Remove layer and its data
- atg layer copy: Duplicate layer with all nodes/relationships
- atg layer diff: Compare two layers
- atg layer validate: Check layer integrity
- atg layer refresh-stats: Update layer metadata counts
- atg layer archive: Export layer to JSON
- atg layer restore: Import layer from JSON archive

All commands follow patterns from existing CLI commands and use Rich for formatting.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import click
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.config_manager import create_neo4j_config_from_env
from src.models.layer_metadata import (
    LayerType,
)
from src.services.layer import (
    LayerAlreadyExistsError,
    LayerLockedError,
    LayerManagementService,
    LayerNotFoundError,
)
from src.utils.neo4j_startup import ensure_neo4j_running
from src.utils.session_manager import Neo4jSessionManager

logger = logging.getLogger(__name__)
console = Console()


# =============================================================================
# Helper Functions
# =============================================================================


def format_timestamp(dt: Optional[datetime]) -> str:
    """Format datetime for display."""
    if not dt:
        return "N/A"
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def format_number(num: int) -> str:
    """Format number with thousands separator."""
    return f"{num:,}"


def get_layer_service() -> LayerManagementService:
    """Create layer management service instance."""
    config = create_neo4j_config_from_env()
    session_manager = Neo4jSessionManager(config.neo4j)
    session_manager.connect()
    return LayerManagementService(session_manager)


def print_json(data: Dict[str, Any]) -> None:
    """Print data as formatted JSON."""
    console.print_json(json.dumps(data, indent=2, default=str))


def print_yaml(data: Dict[str, Any]) -> None:
    """Print data as formatted YAML."""
    console.print(yaml.dump(data, default_flow_style=False, sort_keys=False))


def get_available_layers(service: LayerManagementService) -> List[str]:
    """Get list of available layer IDs."""
    try:
        layers = asyncio.run(service.list_layers())
        return [layer.layer_id for layer in layers]
    except Exception:
        return []


def suggest_similar_layers(layer_id: str, available: List[str]) -> List[str]:
    """Find similar layer names using simple string matching."""
    suggestions = []
    layer_id_lower = layer_id.lower()

    for available_id in available:
        available_lower = available_id.lower()
        # Check for substring matches
        if layer_id_lower in available_lower or available_lower in layer_id_lower:
            suggestions.append(available_id)
        # Check for prefix matches
        elif available_lower.startswith(layer_id_lower[:3]):
            suggestions.append(available_id)

    return suggestions[:3]  # Return top 3 suggestions


# =============================================================================
# Command: atg layer list
# =============================================================================


async def layer_list_command_handler(
    tenant_id: Optional[str],
    include_inactive: bool,
    layer_type: Optional[str],
    sort_by: str,
    ascending: bool,
    format_type: str,
    no_container: bool,
    debug: bool,
) -> None:
    """
    List all layers with optional filtering and sorting.

    Displays layers in table, JSON, or YAML format with statistics.
    """
    if not no_container:
        ensure_neo4j_running(debug)

    service = get_layer_service()

    # Convert string layer_type to enum
    layer_type_enum = None
    if layer_type:
        try:
            layer_type_enum = LayerType(layer_type.lower())
        except ValueError:
            console.print(str(f"[red]Invalid layer type: {layer_type}[/red]"))
            console.print(f"Valid types: {', '.join([t.value for t in LayerType])}")
            sys.exit(1)

    try:
        layers = await service.list_layers(
            tenant_id=tenant_id,
            include_inactive=include_inactive,
            layer_type=layer_type_enum,
            sort_by=sort_by,
            ascending=ascending,
        )

        if not layers:
            console.print("[yellow]No layers found.[/yellow]")
            console.print("\nCreate a layer with: atg layer create <LAYER_ID>")
            return

        # Find active layer
        active_layer_id = None
        for layer in layers:
            if layer.is_active:
                active_layer_id = layer.layer_id
                break

        # Output in requested format
        if format_type == "json":
            output = {
                "layers": [layer.to_dict() for layer in layers],
                "total": len(layers),
                "active_layer": active_layer_id,
            }
            print_json(output)

        elif format_type == "yaml":
            output = {
                "layers": [layer.to_dict() for layer in layers],
                "total": len(layers),
                "active_layer": active_layer_id,
            }
            print_yaml(output)

        else:  # table format
            table = Table(title="Graph Layers")
            table.add_column("Layer ID", style="cyan", no_wrap=True)
            table.add_column("Name", style="green")
            table.add_column("Type", style="magenta")
            table.add_column("Active", style="yellow", justify="center")
            table.add_column("Nodes", style="blue", justify="right")
            table.add_column("Created", style="white")

            for layer in layers:
                active_marker = "✓" if layer.is_active else ""
                table.add_row(
                    layer.layer_id,
                    layer.name[:30] + "..." if len(layer.name) > 30 else layer.name,
                    layer.layer_type.value,
                    active_marker,
                    format_number(layer.node_count),
                    format_timestamp(layer.created_at),
                )

            console.print(table)
            console.print(str(f"\nTotal layers: {len(layers)}"))
            if active_layer_id:
                console.print(str(f"Active layer: [cyan]{active_layer_id}[/cyan]"))

    except Exception as e:
        console.print(str(f"[red]Error listing layers: {e}[/red]"))
        if debug:
            console.print_exception()
        sys.exit(1)


# =============================================================================
# Command: atg layer show
# =============================================================================


async def layer_show_command_handler(
    layer_id: str,
    format_type: str,
    show_stats: bool,
    show_lineage: bool,
    no_container: bool,
    debug: bool,
) -> None:
    """
    Show detailed information about a specific layer.
    """
    if not no_container:
        ensure_neo4j_running(debug)

    service = get_layer_service()

    try:
        layer = await service.get_layer(layer_id)

        if not layer:
            console.print(str(f"[red]Layer not found: {layer_id}[/red]"))

            # Show available layers
            available = get_available_layers(service)
            if available:
                console.print(f"\nAvailable layers: {', '.join(available)}")

                # Suggest similar layers
                suggestions = suggest_similar_layers(layer_id, available)
                if suggestions:
                    console.print("\nDid you mean one of these?")
                    for suggestion in suggestions:
                        console.print(str(f"  - {suggestion}"))

            sys.exit(1)

        # Get lineage information if requested
        parent_layer = None
        child_layers = []
        if show_lineage:
            if layer.parent_layer_id:
                parent_layer = await service.get_layer(layer.parent_layer_id)

            # Find child layers
            all_layers = await service.list_layers()
            child_layers = [
                layer for layer in all_layers if layer.parent_layer_id == layer_id
            ]

        # Output in requested format
        if format_type == "json":
            output = layer.to_dict()
            if show_lineage:
                output["parent_layer"] = (
                    parent_layer.to_dict() if parent_layer else None
                )
                output["child_layers"] = [c.to_dict() for c in child_layers]
            print_json(output)

        elif format_type == "yaml":
            output = layer.to_dict()
            if show_lineage:
                output["parent_layer"] = (
                    parent_layer.to_dict() if parent_layer else None
                )
                output["child_layers"] = [c.to_dict() for c in child_layers]
            print_yaml(output)

        else:  # text format
            # Build status line
            status_parts = []
            if layer.is_active:
                status_parts.append("[green]Active[/green]")
            if layer.is_baseline:
                status_parts.append("[blue]Baseline[/blue]")
            if layer.is_locked:
                status_parts.append("[red]Locked[/red]")
            status = ", ".join(status_parts) if status_parts else "[dim]Inactive[/dim]"

            # Build panel content
            content = f"""[bold]Name:[/bold] {layer.name}
[bold]Description:[/bold] {layer.description}
[bold]Type:[/bold] {layer.layer_type.value}
[bold]Status:[/bold] {status}

[bold]Created:[/bold] {format_timestamp(layer.created_at)}
[bold]Created by:[/bold] {layer.created_by}
[bold]Last updated:[/bold] {format_timestamp(layer.updated_at)}

[bold]Tenant ID:[/bold] {layer.tenant_id}
[bold]Subscriptions:[/bold] {", ".join(layer.subscription_ids) if layer.subscription_ids else "None"}

[bold]Statistics:[/bold]
  Nodes:           {format_number(layer.node_count)} resources
  Relationships:   {format_number(layer.relationship_count)} connections
"""

            if layer.tags:
                content += f"\n[bold]Tags:[/bold] {', '.join(layer.tags)}"

            if show_lineage:
                content += "\n\n[bold]Lineage:[/bold]"
                if parent_layer:
                    content += (
                        f"\n  Parent:  {parent_layer.layer_id} ({parent_layer.name})"
                    )
                else:
                    content += "\n  Parent:  (none - baseline layer)"

                if child_layers:
                    content += (
                        f"\n  Children: {', '.join([c.layer_id for c in child_layers])}"
                    )
                else:
                    content += "\n  Children: (none)"

            panel = Panel(content, title=f"Layer: {layer_id}", border_style="cyan")
            console.print(panel)

    except Exception as e:
        console.print(str(f"[red]Error showing layer: {e}[/red]"))
        if debug:
            console.print_exception()
        sys.exit(2)


# =============================================================================
# Command: atg layer active
# =============================================================================


async def layer_active_command_handler(
    layer_id: Optional[str],
    tenant_id: Optional[str],
    format_type: str,
    no_container: bool,
    debug: bool,
) -> None:
    """
    Show or set the active layer.
    """
    if not no_container:
        ensure_neo4j_running(debug)

    service = get_layer_service()

    try:
        if layer_id:
            # Set active layer
            old_active = await service.get_active_layer(tenant_id)
            old_active_id = old_active.layer_id if old_active else None

            try:
                new_active = await service.set_active_layer(layer_id, tenant_id)

                if format_type == "json":
                    output = {
                        "previous_active": old_active_id,
                        "new_active": new_active.to_dict(),
                    }
                    print_json(output)
                else:
                    if old_active_id:
                        console.print(
                            f"[green]✓[/green] Active layer changed: {old_active_id} → {layer_id}"
                        )
                    else:
                        console.print(
                            f"[green]✓[/green] Active layer set to: {layer_id}"
                        )
                    console.print()

                    content = f"""[bold]Name:[/bold] {new_active.name}
[bold]Nodes:[/bold] {format_number(new_active.node_count)}
[bold]Created:[/bold] {format_timestamp(new_active.created_at)}

Subsequent operations will use this layer."""

                    panel = Panel(
                        content, title=f"Active Layer: {layer_id}", border_style="green"
                    )
                    console.print(panel)

            except LayerNotFoundError:
                console.print(str(f"[red]Layer not found: {layer_id}[/red]"))

                # Show available layers
                available = get_available_layers(service)
                if available:
                    console.print(f"\nAvailable layers: {', '.join(available)}")

                sys.exit(1)

        else:
            # Show current active layer
            active = await service.get_active_layer(tenant_id)

            if not active:
                console.print("[yellow]No active layer set.[/yellow]")
                console.print("\nSet active layer with: atg layer active <LAYER_ID>")
                return

            if format_type == "json":
                print_json(active.to_dict())
            else:
                content = f"""[bold]Name:[/bold] {active.name}
[bold]Nodes:[/bold] {format_number(active.node_count)}
[bold]Created:[/bold] {format_timestamp(active.created_at)}

All operations will use this layer by default."""

                panel = Panel(
                    content,
                    title=f"Active Layer: {active.layer_id}",
                    border_style="green",
                )
                console.print(panel)

    except Exception as e:
        console.print(str(f"[red]Error managing active layer: {e}[/red]"))
        if debug:
            console.print_exception()
        sys.exit(2)


# =============================================================================
# Command: atg layer create
# =============================================================================


async def layer_create_command_handler(
    layer_id: str,
    name: Optional[str],
    description: Optional[str],
    layer_type: str,
    parent_layer: Optional[str],
    tenant_id: Optional[str],
    tags: List[str],
    make_active: bool,
    yes: bool,
    no_container: bool,
    debug: bool,
) -> None:
    """
    Create a new empty layer.
    """
    if not no_container:
        ensure_neo4j_running(debug)

    service = get_layer_service()

    # Set defaults
    if not name:
        name = layer_id
    if not description:
        description = (
            f"Layer created at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
        )
    if not tenant_id:
        tenant_id = os.environ.get("AZURE_TENANT_ID", "unknown")

    # Parse layer type
    try:
        layer_type_enum = LayerType(layer_type.lower())
    except ValueError:
        console.print(str(f"[red]Invalid layer type: {layer_type}[/red]"))
        console.print(f"Valid types: {', '.join([t.value for t in LayerType])}")
        sys.exit(2)

    # Confirm creation
    if not yes:
        console.print(str(f"Creating new layer: [cyan]{layer_id}[/cyan]"))
        console.print(str(f"  Name:   {name}"))
        console.print(str(f"  Type:   {layer_type}"))
        if parent_layer:
            console.print(str(f"  Parent: {parent_layer}"))
        console.print()

        if not click.confirm("Confirm creation?", default=True):
            console.print("Cancelled.")
            sys.exit(3)

    try:
        layer = await service.create_layer(
            layer_id=layer_id,
            name=name,
            description=description,
            created_by="cli",
            parent_layer_id=parent_layer,
            layer_type=layer_type_enum,
            tenant_id=tenant_id,
            metadata={},
            make_active=make_active,
        )

        # Add tags if provided
        if tags:
            await service.update_layer(layer_id, tags=tags)

        console.print("[green]✓[/green] Layer created successfully")
        console.print()
        console.print(str(f"[bold]Layer ID:[/bold] {layer.layer_id}"))
        console.print("[bold]Node count:[/bold] 0 (empty layer)")
        console.print()
        console.print(
            "Use 'atg layer copy' to populate this layer, or run scale operations"
        )
        console.print(str(f"with --target-layer {layer_id} to write directly to it."))

    except LayerAlreadyExistsError:
        console.print(str(f"[red]Layer already exists: {layer_id}[/red]"))
        console.print("\nUse a different layer ID or delete the existing layer first.")
        sys.exit(1)

    except ValueError as e:
        console.print(str(f"[red]Validation error: {e}[/red]"))
        sys.exit(2)

    except Exception as e:
        console.print(str(f"[red]Error creating layer: {e}[/red]"))
        if debug:
            console.print_exception()
        sys.exit(2)


# =============================================================================
# Command: atg layer copy
# =============================================================================


async def layer_copy_command_handler(
    source: str,
    target: str,
    name: Optional[str],
    description: Optional[str],
    copy_metadata: bool,
    make_active: bool,
    yes: bool,
    no_container: bool,
    debug: bool,
) -> None:
    """
    Copy an entire layer (nodes + relationships).
    """
    if not no_container:
        ensure_neo4j_running(debug)

    service = get_layer_service()

    try:
        # Validate source exists
        source_layer = await service.get_layer(source)
        if not source_layer:
            console.print(str(f"[red]Source layer not found: {source}[/red]"))
            sys.exit(1)

        # Check target doesn't exist
        if await service.get_layer(target):
            console.print(str(f"[red]Target layer already exists: {target}[/red]"))
            sys.exit(2)

        # Set defaults
        if not name:
            name = f"Copy of {source_layer.name}"
        if not description:
            description = f"Copied from {source} at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"

        # Confirm copy
        if not yes:
            console.print(
                f"Copying layer: [cyan]{source}[/cyan] → [cyan]{target}[/cyan]"
            )
            console.print()
            console.print(
                f"  Source:  {source} ({format_number(source_layer.node_count)} nodes)"
            )
            console.print(str(f"  Target:  {target}"))
            console.print()

            if not click.confirm("Confirm copy operation?", default=True):
                console.print("Cancelled.")
                sys.exit(3)

        # Perform copy with progress tracking
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Copying layer...", total=None)

            start_time = datetime.utcnow()

            layer = await service.copy_layer(
                source_layer_id=source,
                target_layer_id=target,
                name=name,
                description=description,
                copy_metadata=copy_metadata,
                batch_size=1000,
            )

            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()

            progress.update(task, completed=True)

        # Make active if requested
        if make_active:
            await service.set_active_layer(target)

        console.print()
        console.print("[green]✓[/green] Layer copied successfully")
        console.print()
        console.print(str(f"[bold]Layer:[/bold] {target}"))
        console.print(str(f"[bold]Nodes:[/bold] {format_number(layer.node_count)}"))
        console.print(
            f"[bold]Relationships:[/bold] {format_number(layer.relationship_count)}"
        )
        console.print(str(f"[bold]Time:[/bold] {duration:.1f} seconds"))

    except Exception as e:
        console.print(str(f"[red]Error copying layer: {e}[/red]"))
        if debug:
            console.print_exception()
        sys.exit(4)


# =============================================================================
# Command: atg layer delete
# =============================================================================


async def layer_delete_command_handler(
    layer_id: str,
    force: bool,
    yes: bool,
    archive: Optional[str],
    no_container: bool,
    debug: bool,
) -> None:
    """
    Delete a layer and all its nodes/relationships.
    """
    if not no_container:
        ensure_neo4j_running(debug)

    service = get_layer_service()

    try:
        # Check layer exists
        layer = await service.get_layer(layer_id)
        if not layer:
            console.print(str(f"[red]Layer not found: {layer_id}[/red]"))
            sys.exit(1)

        # Check protections
        if (layer.is_active or layer.is_baseline) and not force:
            console.print(str(f"[red]Cannot delete layer: {layer_id}[/red]"))
            console.print()

            if layer.is_active:
                console.print("[bold]Reason:[/bold] Active layer")
            if layer.is_baseline:
                console.print("[bold]Reason:[/bold] Baseline layer")

            console.print("[bold]Status:[/bold] Protected")
            console.print()
            console.print("This layer is protected. To delete:")
            console.print()

            if layer.is_active:
                console.print("  1. Switch to another layer:")
                console.print("     atg layer active <OTHER_LAYER>")
                console.print()

            console.print("  2. Delete with --force flag:")
            console.print(str(f"     atg layer delete {layer_id} --force"))
            console.print()
            console.print(
                "[yellow]⚠️  Force deletion of baseline layer is not recommended.[/yellow]"
            )
            sys.exit(2)

        # Archive before deletion if requested
        if archive:
            console.print(str(f"Archiving layer to: {archive}"))
            await service.archive_layer(layer_id, archive)
            console.print("[green]✓[/green] Layer archived")
            console.print()

        # Confirm deletion
        if not yes:
            console.print(str(f"Deleting layer: [red]{layer_id}[/red]"))
            console.print()
            console.print(str(f"  Name:         {layer.name}"))
            console.print(str(f"  Nodes:        {format_number(layer.node_count)}"))
            console.print(
                str(f"  Relationships: {format_number(layer.relationship_count)}")
            )
            console.print(
                f"  Status:       {'Active' if layer.is_active else 'Inactive'}"
            )
            console.print()
            console.print(
                "[yellow]⚠️  WARNING: This will permanently delete all nodes and relationships[/yellow]"
            )
            console.print("           in this layer. Original nodes are preserved.")
            console.print()

            if not click.confirm("Confirm deletion?", default=False):
                console.print("Cancelled.")
                sys.exit(3)

        # Perform deletion
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Deleting layer...", total=None)

            start_time = datetime.utcnow()
            await service.delete_layer(layer_id, force=force)
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()

            progress.update(task, completed=True)

        console.print()
        console.print("[green]✓[/green] Layer deleted successfully")
        console.print()
        console.print(str(f"[bold]Time:[/bold] {duration:.1f} seconds"))

    except LayerLockedError:
        console.print(str(f"[red]Layer is locked: {layer_id}[/red]"))
        console.print("\nUnlock the layer before deletion.")
        sys.exit(2)

    except Exception as e:
        console.print(str(f"[red]Error deleting layer: {e}[/red]"))
        if debug:
            console.print_exception()
        sys.exit(4)


# =============================================================================
# Command: atg layer diff
# =============================================================================


async def layer_diff_command_handler(
    layer_a: str,
    layer_b: str,
    detailed: bool,
    properties: bool,
    output: Optional[str],
    format_type: str,
    no_container: bool,
    debug: bool,
) -> None:
    """
    Compare two layers to find differences.
    """
    if not no_container:
        ensure_neo4j_running(debug)

    service = get_layer_service()

    try:
        # Validate both layers exist
        layer_a_meta = await service.get_layer(layer_a)
        layer_b_meta = await service.get_layer(layer_b)

        if not layer_a_meta:
            console.print(str(f"[red]Layer not found: {layer_a}[/red]"))
            sys.exit(1)
        if not layer_b_meta:
            console.print(str(f"[red]Layer not found: {layer_b}[/red]"))
            sys.exit(1)

        # Perform comparison
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Comparing layers...", total=None)

            diff = await service.compare_layers(
                layer_a_id=layer_a,
                layer_b_id=layer_b,
                detailed=detailed,
                include_properties=properties,
            )

            progress.update(task, completed=True)

        console.print()

        # Output in requested format
        if format_type == "json":
            output_data = {
                "layer_a_id": diff.layer_a_id,
                "layer_b_id": diff.layer_b_id,
                "compared_at": diff.compared_at.isoformat(),
                "nodes": {
                    "added": diff.nodes_added,
                    "removed": diff.nodes_removed,
                    "modified": diff.nodes_modified,
                    "unchanged": diff.nodes_unchanged,
                },
                "relationships": {
                    "added": diff.relationships_added,
                    "removed": diff.relationships_removed,
                    "modified": diff.relationships_modified,
                    "unchanged": diff.relationships_unchanged,
                },
                "total_changes": diff.total_changes,
                "change_percentage": diff.change_percentage,
            }

            if detailed:
                output_data["added_node_ids"] = diff.added_node_ids[
                    :100
                ]  # Limit to 100
                output_data["removed_node_ids"] = diff.removed_node_ids[:100]

            if output:
                with open(output, "w") as f:
                    json.dump(output_data, f, indent=2)
                console.print(str(f"[green]✓[/green] Comparison saved to: {output}"))
            else:
                print_json(output_data)

        else:  # text format
            console.print("[bold]Layer Comparison[/bold]")
            console.print("=" * 60)
            console.print()
            console.print(
                str(f"[bold]Baseline:[/bold]    {layer_a} ({layer_a_meta.name})")
            )
            console.print(
                str(f"[bold]Comparison:[/bold]  {layer_b} ({layer_b_meta.name})")
            )
            console.print()

            console.print("[bold]Node Differences[/bold]")
            console.print("─" * 60)
            console.print(str(f"  Added:      {format_number(diff.nodes_added)} nodes"))

            if diff.nodes_removed > 0:
                reduction_pct = (
                    diff.nodes_removed / max(layer_a_meta.node_count, 1)
                ) * 100
                console.print(
                    f"  Removed:    {format_number(diff.nodes_removed)} nodes ({reduction_pct:.1f}% reduction)"
                )
            else:
                console.print(
                    f"  Removed:    {format_number(diff.nodes_removed)} nodes"
                )

            console.print(
                str(f"  Modified:   {format_number(diff.nodes_modified)} nodes")
            )
            console.print(
                str(f"  Unchanged:  {format_number(diff.nodes_unchanged)} nodes")
            )
            console.print()

            console.print("[bold]Relationship Differences[/bold]")
            console.print("─" * 60)
            console.print(
                f"  Added:      {format_number(diff.relationships_added)} relationships"
            )
            console.print(
                f"  Removed:    {format_number(diff.relationships_removed)} relationships"
            )
            console.print(
                f"  Modified:   {format_number(diff.relationships_modified)} relationships"
            )
            console.print(
                f"  Unchanged:  {format_number(diff.relationships_unchanged)} relationships"
            )
            console.print()

            console.print("[bold]Summary[/bold]")
            console.print("─" * 60)
            console.print(
                str(f"  Total changes:     {format_number(diff.total_changes)}")
            )
            console.print(str(f"  Change percentage: {diff.change_percentage:.1f}%"))

            if diff.change_percentage > 50:
                impact = "Major topology change"
                color = "red"
            elif diff.change_percentage > 20:
                impact = "Significant changes"
                color = "yellow"
            else:
                impact = "Minor changes"
                color = "green"

            console.print(str(f"  Impact:            [{color}]{impact}[/{color}]"))
            console.print()

            if diff.change_percentage > 50:
                console.print("[yellow]Interpretation:[/yellow]")
                console.print("  This layer shows significant consolidation.")
                console.print("  Review IaC output carefully before deployment.")

            # Show detailed node lists if requested
            if detailed and (diff.added_node_ids or diff.removed_node_ids):
                console.print()
                console.print("[bold]Detailed Changes[/bold]")
                console.print("─" * 60)

                if diff.removed_node_ids:
                    console.print(
                        f"\n[bold]Removed Nodes ({len(diff.removed_node_ids)}):[/bold]"
                    )
                    for node_id in diff.removed_node_ids[:10]:  # Show first 10
                        console.print(str(f"  - {node_id}"))
                    if len(diff.removed_node_ids) > 10:
                        console.print(
                            str(f"  ... ({len(diff.removed_node_ids) - 10} more)")
                        )

                if diff.added_node_ids:
                    console.print(
                        f"\n[bold]Added Nodes ({len(diff.added_node_ids)}):[/bold]"
                    )
                    for node_id in diff.added_node_ids[:10]:  # Show first 10
                        console.print(str(f"  + {node_id}"))
                    if len(diff.added_node_ids) > 10:
                        console.print(
                            str(f"  ... ({len(diff.added_node_ids) - 10} more)")
                        )

            if output:
                # Save text output to file
                with open(output, "w") as f:
                    f.write("Layer Comparison\n")
                    f.write(f"={'=' * 60}\n\n")
                    f.write(f"Baseline:    {layer_a} ({layer_a_meta.name})\n")
                    f.write(f"Comparison:  {layer_b} ({layer_b_meta.name})\n\n")
                    f.write("Node Differences:\n")
                    f.write(f"  Added:      {diff.nodes_added}\n")
                    f.write(f"  Removed:    {diff.nodes_removed}\n")
                    f.write(f"  Modified:   {diff.nodes_modified}\n")
                    f.write(f"  Unchanged:  {diff.nodes_unchanged}\n\n")
                    f.write(f"Total changes: {diff.total_changes}\n")
                    f.write(f"Change percentage: {diff.change_percentage:.1f}%\n")

                console.print(str(f"\n[green]✓[/green] Comparison saved to: {output}"))

    except Exception as e:
        console.print(str(f"[red]Error comparing layers: {e}[/red]"))
        if debug:
            console.print_exception()
        sys.exit(2)


# =============================================================================
# Command: atg layer validate
# =============================================================================


async def layer_validate_command_handler(
    layer_id: str,
    fix: bool,
    output: Optional[str],
    format_type: str,
    no_container: bool,
    debug: bool,
) -> None:
    """
    Validate layer integrity and check for issues.
    """
    if not no_container:
        ensure_neo4j_running(debug)

    service = get_layer_service()

    try:
        # Validate layer
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Validating layer...", total=None)

            report = await service.validate_layer_integrity(layer_id, fix_issues=fix)

            progress.update(task, completed=True)

        console.print()

        # Output in requested format
        if format_type == "json":
            output_data = {
                "layer_id": report.layer_id,
                "validated_at": report.validated_at.isoformat(),
                "is_valid": report.is_valid,
                "checks_passed": report.checks_passed,
                "checks_failed": report.checks_failed,
                "checks_warned": report.checks_warned,
                "issues": report.issues,
                "warnings": report.warnings,
                "statistics": {
                    "orphaned_nodes": report.orphaned_nodes,
                    "orphaned_relationships": report.orphaned_relationships,
                    "cross_layer_relationships": report.cross_layer_relationships,
                    "missing_scan_source_nodes": report.missing_scan_source_nodes,
                },
            }

            if output:
                with open(output, "w") as f:
                    json.dump(output_data, f, indent=2)
                console.print(
                    str(f"[green]✓[/green] Validation report saved to: {output}")
                )
            else:
                print_json(output_data)

        else:  # text format
            console.print(str(f"[bold]Validating layer: {layer_id}[/bold]"))
            console.print("=" * 60)
            console.print()
            console.print("Running integrity checks...")
            console.print()

            # Show check results
            total_checks = report.checks_passed + report.checks_failed

            if report.is_valid:
                console.print(
                    f"[green]✓[/green] All checks passed ({total_checks}/{total_checks})"
                )
            else:
                console.print(
                    f"[red]✗[/red] Some checks failed ({report.checks_passed}/{total_checks})"
                )

            console.print()
            console.print("[bold]Summary[/bold]")
            console.print("─" * 60)
            console.print(
                f"Status:        {'[green]✓ Valid[/green]' if report.is_valid else '[red]✗ Invalid[/red]'}"
            )
            console.print(
                str(f"Checks passed: {report.checks_passed} / {total_checks}")
            )
            console.print(str(f"Checks failed: {report.checks_failed}"))
            console.print(str(f"Warnings:      {report.checks_warned}"))

            # Show issues
            if report.issues:
                console.print()
                console.print("[bold red]Issues Found[/bold red]")
                console.print("─" * 60)
                for issue in report.issues:
                    console.print(f"[red]ERROR:[/red] {issue['message']}")
                    if issue.get("details"):
                        for key, value in issue["details"].items():
                            console.print(str(f"  {key}: {value}"))

            # Show warnings
            if report.warnings:
                console.print()
                console.print("[bold yellow]Warnings[/bold yellow]")
                console.print("─" * 60)
                for warning in report.warnings:
                    console.print(f"[yellow]WARNING:[/yellow] {warning['message']}")

            # Show recommendations
            if not report.is_valid:
                console.print()
                console.print("[bold]Recommendations:[/bold]")
                console.print("  1. Run with --fix to auto-fix fixable issues")
                console.print("  2. Manually review and correct remaining issues")
                console.print()
                console.print(str(f"Use: atg layer validate {layer_id} --fix"))
            else:
                console.print()
                console.print("This layer is healthy and ready for use.")

            if output:
                # Save text report to file
                with open(output, "w") as f:
                    f.write(f"Validation Report: {layer_id}\n")
                    f.write(f"={'=' * 60}\n\n")
                    f.write(f"Validated at: {format_timestamp(report.validated_at)}\n")
                    f.write(f"Status: {'Valid' if report.is_valid else 'Invalid'}\n\n")
                    f.write(f"Checks passed: {report.checks_passed}\n")
                    f.write(f"Checks failed: {report.checks_failed}\n")
                    f.write(f"Warnings: {report.checks_warned}\n\n")

                    if report.issues:
                        f.write("Issues:\n")
                        for issue in report.issues:
                            f.write(f"  - {issue['message']}\n")

                console.print(
                    f"\n[green]✓[/green] Validation report saved to: {output}"
                )

        # Exit with error code if validation failed
        sys.exit(0 if report.is_valid else 2)

    except LayerNotFoundError:
        console.print(str(f"[red]Layer not found: {layer_id}[/red]"))
        sys.exit(1)

    except Exception as e:
        console.print(str(f"[red]Error validating layer: {e}[/red]"))
        if debug:
            console.print_exception()
        sys.exit(3)


# =============================================================================
# Command: atg layer refresh-stats
# =============================================================================


async def layer_refresh_stats_command_handler(
    layer_id: str,
    format_type: str,
    no_container: bool,
    debug: bool,
) -> None:
    """
    Refresh layer metadata statistics.
    """
    if not no_container:
        ensure_neo4j_running(debug)

    service = get_layer_service()

    try:
        # Get current stats
        old_layer = await service.get_layer(layer_id)
        if not old_layer:
            console.print(str(f"[red]Layer not found: {layer_id}[/red]"))
            sys.exit(1)

        old_node_count = old_layer.node_count
        old_rel_count = old_layer.relationship_count

        # Refresh stats
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Refreshing statistics...", total=None)

            new_layer = await service.refresh_layer_stats(layer_id)

            progress.update(task, completed=True)

        console.print()
        console.print("[green]✓[/green] Statistics refreshed")
        console.print()

        if format_type == "json":
            output = {
                "layer_id": layer_id,
                "previous": {
                    "node_count": old_node_count,
                    "relationship_count": old_rel_count,
                },
                "current": {
                    "node_count": new_layer.node_count,
                    "relationship_count": new_layer.relationship_count,
                },
                "changes": {
                    "nodes": new_layer.node_count - old_node_count,
                    "relationships": new_layer.relationship_count - old_rel_count,
                },
                "updated_at": new_layer.updated_at.isoformat()
                if new_layer.updated_at
                else None,
            }
            print_json(output)
        else:
            # Create comparison table
            table = Table(title="Statistics Update")
            table.add_column("Metric", style="cyan")
            table.add_column("Previous", style="white", justify="right")
            table.add_column("Current", style="green", justify="right")
            table.add_column("Change", style="yellow", justify="right")

            node_change = new_layer.node_count - old_node_count
            node_change_str = f"{node_change:+,}" if node_change != 0 else "no change"

            rel_change = new_layer.relationship_count - old_rel_count
            rel_change_str = f"{rel_change:+,}" if rel_change != 0 else "no change"

            table.add_row(
                "Nodes",
                format_number(old_node_count),
                format_number(new_layer.node_count),
                node_change_str,
            )
            table.add_row(
                "Relationships",
                format_number(old_rel_count),
                format_number(new_layer.relationship_count),
                rel_change_str,
            )

            console.print(table)
            console.print()
            console.print(
                f"[bold]Updated:[/bold] {format_timestamp(new_layer.updated_at)}"
            )

    except Exception as e:
        console.print(str(f"[red]Error refreshing stats: {e}[/red]"))
        if debug:
            console.print_exception()
        sys.exit(2)


# =============================================================================
# Command: atg layer archive
# =============================================================================


async def layer_archive_command_handler(
    layer_id: str,
    output_path: str,
    include_original: bool,
    compress: bool,
    yes: bool,
    no_container: bool,
    debug: bool,
) -> None:
    """
    Export layer to JSON archive file.
    """
    if not no_container:
        ensure_neo4j_running(debug)

    service = get_layer_service()

    try:
        # Validate layer exists
        layer = await service.get_layer(layer_id)
        if not layer:
            console.print(str(f"[red]Layer not found: {layer_id}[/red]"))
            sys.exit(1)

        # Confirm archiving
        if not yes:
            console.print(str(f"[bold]Archiving layer: {layer_id}[/bold]"))
            console.print("=" * 60)
            console.print()
            console.print(str(f"[bold]Output:[/bold] {output_path}"))
            console.print()
            console.print(str(f"[bold]Layer:[/bold] {layer_id} ({layer.name})"))
            console.print(str(f"[bold]Nodes:[/bold] {format_number(layer.node_count)}"))
            console.print(
                f"[bold]Relationships:[/bold] {format_number(layer.relationship_count)}"
            )
            console.print(
                f"[bold]Include Original:[/bold] {'Yes' if include_original else 'No'}"
            )
            console.print()

            if not click.confirm("Confirm archive?", default=True):
                console.print("Cancelled.")
                sys.exit(3)

        # Perform archiving
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Archiving layer...", total=None)

            start_time = datetime.utcnow()

            archive_path = await service.archive_layer(
                layer_id=layer_id,
                output_path=output_path,
                include_original=include_original,
            )

            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()

            progress.update(task, completed=True)

        # Get file size
        file_size = Path(archive_path).stat().st_size
        size_mb = file_size / (1024 * 1024)

        console.print()
        console.print("[green]✓[/green] Layer archived successfully")
        console.print()
        console.print(str(f"[bold]Archive:[/bold] {archive_path}"))
        console.print(str(f"[bold]Size:[/bold] {size_mb:.1f} MB"))
        console.print(str(f"[bold]Time:[/bold] {duration:.1f} seconds"))
        console.print()
        console.print("You can now safely delete this layer if needed:")
        console.print(str(f"  atg layer delete {layer_id}"))

    except Exception as e:
        console.print(str(f"[red]Error archiving layer: {e}[/red]"))
        if debug:
            console.print_exception()
        sys.exit(2)


# =============================================================================
# Command: atg layer restore
# =============================================================================


async def layer_restore_command_handler(
    archive_path: str,
    layer_id: Optional[str],
    make_active: bool,
    yes: bool,
    no_container: bool,
    debug: bool,
) -> None:
    """
    Restore layer from JSON archive.
    """
    if not no_container:
        ensure_neo4j_running(debug)

    service = get_layer_service()

    try:
        # Verify archive exists
        if not Path(archive_path).exists():
            console.print(str(f"[red]Archive not found: {archive_path}[/red]"))
            sys.exit(1)

        # Load archive to preview
        with open(archive_path) as f:
            archive_data = json.load(f)

        metadata = archive_data["metadata"]
        original_layer_id = metadata["layer_id"]
        target_layer_id = layer_id or original_layer_id

        # Check if target layer already exists
        if await service.get_layer(target_layer_id):
            console.print(str(f"[red]Layer already exists: {target_layer_id}[/red]"))
            console.print(
                "\nUse --layer-id to specify a different ID, or delete the existing layer first."
            )
            sys.exit(3)

        # Confirm restoration
        if not yes:
            console.print("[bold]Restoring layer from archive[/bold]")
            console.print("=" * 60)
            console.print()
            console.print(str(f"[bold]Archive:[/bold] {archive_path}"))
            console.print(f"[bold]Layer:[/bold] {target_layer_id} ({metadata['name']})")
            console.print(
                f"[bold]Nodes:[/bold] {format_number(metadata['node_count'])}"
            )
            console.print(
                f"[bold]Relationships:[/bold] {format_number(metadata['relationship_count'])}"
            )
            console.print(f"[bold]Created:[/bold] {metadata['created_at']}")
            console.print()
            console.print(
                f"[yellow]⚠️  This will create layer '{target_layer_id}' in the graph.[/yellow]"
            )
            console.print()

            if not click.confirm("Confirm restore?", default=True):
                console.print("Cancelled.")
                sys.exit(4)

        # Perform restoration
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Restoring layer...", total=None)

            start_time = datetime.utcnow()

            layer = await service.restore_layer(
                archive_path=archive_path,
                target_layer_id=layer_id,
            )

            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()

            progress.update(task, completed=True)

        # Make active if requested
        if make_active:
            await service.set_active_layer(layer.layer_id)

        console.print()
        console.print("[green]✓[/green] Layer restored successfully")
        console.print()
        console.print(str(f"[bold]Layer:[/bold] {layer.layer_id}"))
        console.print(str(f"[bold]Nodes:[/bold] {format_number(layer.node_count)}"))
        console.print(
            f"[bold]Relationships:[/bold] {format_number(layer.relationship_count)}"
        )
        console.print(str(f"[bold]Time:[/bold] {duration:.1f} seconds"))
        console.print()

        if make_active:
            console.print(
                f"Layer is now active. Use: atg generate-iac --layer {layer.layer_id}"
            )
        else:
            console.print(str(f"To activate: atg layer active {layer.layer_id}"))

    except Exception as e:
        console.print(str(f"[red]Error restoring layer: {e}[/red]"))
        if debug:
            console.print_exception()
        sys.exit(5)
