"""Layer management command group.

This module provides the layer command group for multi-layer graph projection management:
- layer list: List all layers with filtering and sorting
- layer show: Display detailed layer information
- layer active: Show or set active layer
- layer create: Create new empty layer
- layer copy: Duplicate layer with all nodes/relationships
- layer delete: Remove layer and its data
- layer diff: Compare two layers
- layer validate: Check layer integrity
- layer refresh-stats: Update layer metadata counts
- layer archive: Export layer to JSON
- layer restore: Import layer from JSON archive

Issue #482: CLI Modularization - Phase 3 (Layer Commands)
"""

from typing import Optional

import click

from src.cli_commands_layer import (
    layer_active_command_handler,
    layer_archive_command_handler,
    layer_copy_command_handler,
    layer_create_command_handler,
    layer_delete_command_handler,
    layer_diff_command_handler,
    layer_list_command_handler,
    layer_refresh_stats_command_handler,
    layer_restore_command_handler,
    layer_show_command_handler,
    layer_validate_command_handler,
)


def async_command(f):
    """Decorator to run async command handlers."""
    import asyncio
    import functools

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))

    return wrapper


# =============================================================================
# Layer Command Group
# =============================================================================


@click.group(name="layer")
def layer() -> None:
    """Layer management commands for multi-layer graph projections."""
    pass


# =============================================================================
# layer list
# =============================================================================


@layer.command(name="list")
@click.option(
    "--tenant-id",
    help="Filter by tenant ID",
)
@click.option(
    "--include-inactive/--active-only",
    default=True,
    help="Show inactive layers (default: true)",
)
@click.option(
    "--type",
    "layer_type",
    type=click.Choice(
        ["baseline", "scaled", "experimental", "snapshot"], case_sensitive=False
    ),
    help="Filter by layer type",
)
@click.option(
    "--sort-by",
    type=click.Choice(["name", "created_at", "node_count"], case_sensitive=False),
    default="created_at",
    help="Sort field (default: created_at)",
)
@click.option(
    "--ascending/--descending",
    default=False,
    help="Sort order (default: descending)",
)
@click.option(
    "--format",
    "format_type",
    type=click.Choice(["table", "json", "yaml"], case_sensitive=False),
    default="table",
    help="Output format (default: table)",
)
@click.option(
    "--no-container",
    is_flag=True,
    help="Do not auto-start Neo4j container",
)
@click.pass_context
@async_command
async def layer_list(
    ctx: click.Context,
    tenant_id: Optional[str],
    include_inactive: bool,
    layer_type: Optional[str],
    sort_by: str,
    ascending: bool,
    format_type: str,
    no_container: bool,
) -> None:
    """List all layers with summary information."""
    debug = ctx.obj.get("debug", False)
    await layer_list_command_handler(
        tenant_id=tenant_id,
        include_inactive=include_inactive,
        layer_type=layer_type,
        sort_by=sort_by,
        ascending=ascending,
        format_type=format_type,
        no_container=no_container,
        debug=debug,
    )


# =============================================================================
# layer show
# =============================================================================


@layer.command(name="show")
@click.argument("layer_id")
@click.option(
    "--format",
    "format_type",
    type=click.Choice(["text", "json", "yaml"], case_sensitive=False),
    default="text",
    help="Output format (default: text)",
)
@click.option(
    "--show-stats",
    is_flag=True,
    help="Include detailed statistics",
)
@click.option(
    "--show-lineage",
    is_flag=True,
    help="Show parent/child layers",
)
@click.option(
    "--no-container",
    is_flag=True,
    help="Do not auto-start Neo4j container",
)
@click.pass_context
@async_command
async def layer_show(
    ctx: click.Context,
    layer_id: str,
    format_type: str,
    show_stats: bool,
    show_lineage: bool,
    no_container: bool,
) -> None:
    """Show detailed information about a specific layer."""
    debug = ctx.obj.get("debug", False)
    await layer_show_command_handler(
        layer_id=layer_id,
        format_type=format_type,
        show_stats=show_stats,
        show_lineage=show_lineage,
        no_container=no_container,
        debug=debug,
    )


# =============================================================================
# layer active
# =============================================================================


@layer.command(name="active")
@click.argument("layer_id", required=False)
@click.option(
    "--tenant-id",
    help="Tenant context (for multi-tenant)",
)
@click.option(
    "--format",
    "format_type",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    help="Output format",
)
@click.option(
    "--no-container",
    is_flag=True,
    help="Do not auto-start Neo4j container",
)
@click.pass_context
@async_command
async def layer_active(
    ctx: click.Context,
    layer_id: Optional[str],
    tenant_id: Optional[str],
    format_type: str,
    no_container: bool,
) -> None:
    """Show or set the active layer."""
    debug = ctx.obj.get("debug", False)
    await layer_active_command_handler(
        layer_id=layer_id,
        tenant_id=tenant_id,
        format_type=format_type,
        no_container=no_container,
        debug=debug,
    )


# =============================================================================
# layer create
# =============================================================================


@layer.command(name="create")
@click.argument("layer_id")
@click.option(
    "--name",
    help="Human-readable name (default: layer_id)",
)
@click.option(
    "--description",
    help="Layer description",
)
@click.option(
    "--type",
    "layer_type",
    type=click.Choice(
        ["baseline", "scaled", "experimental", "snapshot"], case_sensitive=False
    ),
    default="experimental",
    help="Layer type (default: experimental)",
)
@click.option(
    "--parent-layer",
    help="Parent layer for lineage",
)
@click.option(
    "--tenant-id",
    help="Tenant ID",
)
@click.option(
    "--tag",
    "tags",
    multiple=True,
    help="Add tag (multiple allowed)",
)
@click.option(
    "--make-active",
    is_flag=True,
    help="Set as active layer",
)
@click.option(
    "--yes",
    is_flag=True,
    help="Skip confirmation",
)
@click.option(
    "--no-container",
    is_flag=True,
    help="Do not auto-start Neo4j container",
)
@click.pass_context
@async_command
async def layer_create(
    ctx: click.Context,
    layer_id: str,
    name: Optional[str],
    description: Optional[str],
    layer_type: str,
    parent_layer: Optional[str],
    tenant_id: Optional[str],
    tags: tuple,
    make_active: bool,
    yes: bool,
    no_container: bool,
) -> None:
    """Create a new empty layer."""
    debug = ctx.obj.get("debug", False)
    await layer_create_command_handler(
        layer_id=layer_id,
        name=name,
        description=description,
        layer_type=layer_type,
        parent_layer=parent_layer,
        tenant_id=tenant_id,
        tags=list(tags),
        make_active=make_active,
        yes=yes,
        no_container=no_container,
        debug=debug,
    )


# =============================================================================
# layer copy
# =============================================================================


@layer.command(name="copy")
@click.argument("source")
@click.argument("target")
@click.option(
    "--name",
    help="Name for new layer",
)
@click.option(
    "--description",
    help="Description for new layer",
)
@click.option(
    "--copy-metadata/--no-copy-metadata",
    default=True,
    help="Copy metadata dict from source (default: true)",
)
@click.option(
    "--make-active",
    is_flag=True,
    help="Set new layer as active",
)
@click.option(
    "--yes",
    is_flag=True,
    help="Skip confirmation",
)
@click.option(
    "--no-container",
    is_flag=True,
    help="Do not auto-start Neo4j container",
)
@click.pass_context
@async_command
async def layer_copy(
    ctx: click.Context,
    source: str,
    target: str,
    name: Optional[str],
    description: Optional[str],
    copy_metadata: bool,
    make_active: bool,
    yes: bool,
    no_container: bool,
) -> None:
    """Copy an entire layer (nodes + relationships)."""
    debug = ctx.obj.get("debug", False)
    await layer_copy_command_handler(
        source=source,
        target=target,
        name=name,
        description=description,
        copy_metadata=copy_metadata,
        make_active=make_active,
        yes=yes,
        no_container=no_container,
        debug=debug,
    )


# =============================================================================
# layer delete
# =============================================================================


@layer.command(name="delete")
@click.argument("layer_id")
@click.option(
    "--force",
    is_flag=True,
    help="Allow deletion of active/baseline layers",
)
@click.option(
    "--yes",
    is_flag=True,
    help="Skip confirmation",
)
@click.option(
    "--archive",
    type=click.Path(dir_okay=False, writable=True),
    help="Archive layer before deletion",
)
@click.option(
    "--no-container",
    is_flag=True,
    help="Do not auto-start Neo4j container",
)
@click.pass_context
@async_command
async def layer_delete(
    ctx: click.Context,
    layer_id: str,
    force: bool,
    yes: bool,
    archive: Optional[str],
    no_container: bool,
) -> None:
    """Delete a layer and all its nodes/relationships."""
    debug = ctx.obj.get("debug", False)
    await layer_delete_command_handler(
        layer_id=layer_id,
        force=force,
        yes=yes,
        archive=archive,
        no_container=no_container,
        debug=debug,
    )


# =============================================================================
# layer diff
# =============================================================================


@layer.command(name="diff")
@click.argument("layer_a")
@click.argument("layer_b")
@click.option(
    "--detailed",
    is_flag=True,
    help="Include node IDs in output",
)
@click.option(
    "--properties",
    is_flag=True,
    help="Compare property values",
)
@click.option(
    "--output",
    type=click.Path(dir_okay=False, writable=True),
    help="Save report to file",
)
@click.option(
    "--format",
    "format_type",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    help="Output format (default: text)",
)
@click.option(
    "--no-container",
    is_flag=True,
    help="Do not auto-start Neo4j container",
)
@click.pass_context
@async_command
async def layer_diff(
    ctx: click.Context,
    layer_a: str,
    layer_b: str,
    detailed: bool,
    properties: bool,
    output: Optional[str],
    format_type: str,
    no_container: bool,
) -> None:
    """Compare two layers to find differences."""
    debug = ctx.obj.get("debug", False)
    await layer_diff_command_handler(
        layer_a=layer_a,
        layer_b=layer_b,
        detailed=detailed,
        properties=properties,
        output=output,
        format_type=format_type,
        no_container=no_container,
        debug=debug,
    )


# =============================================================================
# layer validate
# =============================================================================


@layer.command(name="validate")
@click.argument("layer_id")
@click.option(
    "--fix",
    is_flag=True,
    help="Attempt automatic fixes",
)
@click.option(
    "--output",
    type=click.Path(dir_okay=False, writable=True),
    help="Save report to file",
)
@click.option(
    "--format",
    "format_type",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    help="Output format (default: text)",
)
@click.option(
    "--no-container",
    is_flag=True,
    help="Do not auto-start Neo4j container",
)
@click.pass_context
@async_command
async def layer_validate(
    ctx: click.Context,
    layer_id: str,
    fix: bool,
    output: Optional[str],
    format_type: str,
    no_container: bool,
) -> None:
    """Validate layer integrity and check for issues."""
    debug = ctx.obj.get("debug", False)
    await layer_validate_command_handler(
        layer_id=layer_id,
        fix=fix,
        output=output,
        format_type=format_type,
        no_container=no_container,
        debug=debug,
    )


# =============================================================================
# layer refresh-stats
# =============================================================================


@layer.command(name="refresh-stats")
@click.argument("layer_id")
@click.option(
    "--format",
    "format_type",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    help="Output format",
)
@click.option(
    "--no-container",
    is_flag=True,
    help="Do not auto-start Neo4j container",
)
@click.pass_context
@async_command
async def layer_refresh_stats(
    ctx: click.Context,
    layer_id: str,
    format_type: str,
    no_container: bool,
) -> None:
    """Refresh layer metadata statistics."""
    debug = ctx.obj.get("debug", False)
    await layer_refresh_stats_command_handler(
        layer_id=layer_id,
        format_type=format_type,
        no_container=no_container,
        debug=debug,
    )


# =============================================================================
# layer archive
# =============================================================================


@layer.command(name="archive")
@click.argument("layer_id")
@click.argument("output_path", type=click.Path(dir_okay=False, writable=True))
@click.option(
    "--include-original",
    is_flag=True,
    help="Include Original nodes in archive",
)
@click.option(
    "--compress",
    is_flag=True,
    help="Compress archive with gzip",
)
@click.option(
    "--yes",
    is_flag=True,
    help="Skip confirmation",
)
@click.option(
    "--no-container",
    is_flag=True,
    help="Do not auto-start Neo4j container",
)
@click.pass_context
@async_command
async def layer_archive(
    ctx: click.Context,
    layer_id: str,
    output_path: str,
    include_original: bool,
    compress: bool,
    yes: bool,
    no_container: bool,
) -> None:
    """Export layer to JSON archive file."""
    debug = ctx.obj.get("debug", False)
    await layer_archive_command_handler(
        layer_id=layer_id,
        output_path=output_path,
        include_original=include_original,
        compress=compress,
        yes=yes,
        no_container=no_container,
        debug=debug,
    )


# =============================================================================
# layer restore
# =============================================================================


@layer.command(name="restore")
@click.argument(
    "archive_path", type=click.Path(exists=True, dir_okay=False, readable=True)
)
@click.option(
    "--layer-id",
    help="Override layer ID from archive",
)
@click.option(
    "--make-active",
    is_flag=True,
    help="Set as active layer after restore",
)
@click.option(
    "--yes",
    is_flag=True,
    help="Skip confirmation",
)
@click.option(
    "--no-container",
    is_flag=True,
    help="Do not auto-start Neo4j container",
)
@click.pass_context
@async_command
async def layer_restore(
    ctx: click.Context,
    archive_path: str,
    layer_id: Optional[str],
    make_active: bool,
    yes: bool,
    no_container: bool,
) -> None:
    """Restore layer from JSON archive."""
    debug = ctx.obj.get("debug", False)
    await layer_restore_command_handler(
        archive_path=archive_path,
        layer_id=layer_id,
        make_active=make_active,
        yes=yes,
        no_container=no_container,
        debug=debug,
    )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "layer",
    "layer_list",
    "layer_show",
    "layer_active",
    "layer_create",
    "layer_copy",
    "layer_delete",
    "layer_diff",
    "layer_validate",
    "layer_refresh_stats",
    "layer_archive",
    "layer_restore",
]
