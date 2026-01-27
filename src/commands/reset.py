"""Reset command for tenant, subscription, resource group, or resource deletion.

This module provides the 'reset' command group for deleting Azure resources
and Entra ID objects with comprehensive safety mechanisms.

CRITICAL SAFETY REQUIREMENTS:
1. This command DELETES ACTUAL Azure resources and Entra ID objects
2. Interactive confirmation required - user must type "DELETE" exactly
3. Preview shown before deletion with counts and warnings
4. ATG service principal is preserved (never deleted)
5. Dry-run mode available for testing

Issue #627: Tenant Reset Feature with Granular Scopes
"""

import asyncio
import sys
from typing import Optional

import click

from src.services.tenant_reset_service import (
    InvalidConfirmationTokenError,
    TenantResetService,
)
from src.utils.neo4j_startup import ensure_neo4j_running


def print_warning_box(lines: list[str]) -> None:
    """Print a prominent warning box.

    Args:
        lines: Lines of text to display in the box
    """
    width = max(len(line) for line in lines) + 4
    border = "═" * width

    click.echo()
    click.echo(f"╔{border}╗")
    click.echo(f"║{' ' * width}║")
    for line in lines:
        padding = width - len(line) - 2
        click.echo(f"║  {line}{' ' * padding}║")
    click.echo(f"║{' ' * width}║")
    click.echo(f"╚{border}╝")
    click.echo()


def print_preview(preview) -> None:
    """Print preview details.

    Args:
        preview: ResetPreview object
    """
    click.echo()
    click.echo("Deletion Preview:")
    click.echo("-" * 60)
    click.echo(f"Scope: {preview.scope.scope_type.value}")

    if preview.scope.subscription_id:
        click.echo(f"Subscription: {preview.scope.subscription_id}")
    if preview.scope.resource_group_name:
        click.echo(f"Resource Group: {preview.scope.resource_group_name}")
    if preview.scope.resource_id:
        click.echo(f"Resource: {preview.scope.resource_id}")

    click.echo()
    click.echo(f"Azure Resources: {preview.azure_resources_count}")
    if preview.entra_users_count > 0:
        click.echo(f"Entra ID Users: {preview.entra_users_count}")
    if preview.entra_groups_count > 0:
        click.echo(f"Entra ID Groups: {preview.entra_groups_count}")
    if preview.entra_service_principals_count > 0:
        click.echo(
            f"Entra ID Service Principals: {preview.entra_service_principals_count} (excluding ATG SP)"
        )
    if preview.graph_nodes_count > 0:
        click.echo(f"Graph Nodes: {preview.graph_nodes_count}")

    click.echo()
    click.echo(f"Estimated Duration: {preview.estimated_duration_seconds} seconds")
    click.echo()

    if preview.warnings:
        for warning in preview.warnings:
            click.echo(click.style(warning, fg="red", bold=True))


def print_result(result) -> None:
    """Print result details.

    Args:
        result: ResetResult object
    """
    click.echo()
    click.echo("Reset Operation Result:")
    click.echo("-" * 60)
    click.echo(f"Status: {result.status.value}")
    click.echo(f"Success: {result.success}")
    click.echo()

    click.echo("Deleted:")
    click.echo(f"  Azure Resources: {result.deleted_azure_resources}")
    if result.deleted_entra_users > 0:
        click.echo(f"  Entra ID Users: {result.deleted_entra_users}")
    if result.deleted_entra_groups > 0:
        click.echo(f"  Entra ID Groups: {result.deleted_entra_groups}")
    if result.deleted_entra_service_principals > 0:
        click.echo(
            f"  Entra ID Service Principals: {result.deleted_entra_service_principals}"
        )
    if result.deleted_graph_nodes > 0:
        click.echo(f"  Graph Nodes: {result.deleted_graph_nodes}")
    if result.deleted_graph_relationships > 0:
        click.echo(f"  Graph Relationships: {result.deleted_graph_relationships}")

    click.echo()
    click.echo(f"Duration: {result.duration_seconds:.2f} seconds")

    if result.errors:
        click.echo()
        click.echo(click.style("Errors:", fg="red", bold=True))
        for error in result.errors:
            click.echo(click.style(f"  - {error}", fg="red"))


def confirm_deletion() -> bool:
    """Prompt user to confirm deletion by typing DELETE.

    Returns:
        True if user confirms (types "DELETE"), False otherwise
    """
    click.echo()
    confirmation = click.prompt(
        click.style(
            'Type DELETE to confirm (or anything else to cancel)',
            fg="yellow",
            bold=True,
        ),
        type=str,
    )

    if confirmation == "DELETE":
        return True
    else:
        click.echo("Cancelled - confirmation token did not match 'DELETE'")
        return False


@click.group("reset")
def reset():
    """Reset operations for deleting Azure resources and Entra ID objects.

    CRITICAL: These commands DELETE actual resources. Use with extreme caution.
    """
    pass


@reset.command("tenant")
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Preview only - do not actually delete resources",
)
def reset_tenant(dry_run: bool):
    """Reset tenant-level resources.

    CRITICAL: This DELETES ALL Azure resources and Entra ID objects (except ATG SP).

    \b
    Deleted:
    - All Azure resources across all subscriptions
    - All Entra ID users
    - All Entra ID groups
    - All Entra ID service principals (except ATG SP)
    - All graph data in Neo4j

    \b
    Preserved:
    - ATG service principal (used for provisioning)
    - ATG configuration and credentials

    Requires interactive confirmation by typing "DELETE".
    """
    ensure_neo4j_running()

    async def run():
        service = TenantResetService(dry_run=dry_run)

        # Show preview
        click.echo("Loading preview...")
        preview = await service.preview_tenant_reset()
        print_preview(preview)

        # Show prominent warning
        print_warning_box([
            "⚠️  WARNING: DESTRUCTIVE OPERATION",
            "",
            "This will DELETE ALL Azure resources and Entra ID objects!",
            "This action CANNOT be undone!",
            "Production data will be permanently lost!",
        ])

        # Confirm deletion
        if not confirm_deletion():
            click.echo("Operation cancelled by user.")
            sys.exit(0)

        # Execute deletion
        click.echo()
        click.echo("Executing tenant reset...")
        result = await service.execute_tenant_reset(confirmation_token="DELETE")
        print_result(result)

        if not result.success:
            sys.exit(1)

    asyncio.run(run())


@reset.command("subscription")
@click.argument("subscription_id", type=str)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Preview only - do not actually delete resources",
)
def reset_subscription(subscription_id: str, dry_run: bool):
    """Reset subscription-level resources.

    Deletes all Azure resources in the specified subscription.
    Graph data for the subscription is also removed.
    Entra ID objects are NOT affected (subscription scope only).

    Requires interactive confirmation by typing "DELETE".
    """
    ensure_neo4j_running()

    async def run():
        service = TenantResetService(dry_run=dry_run)

        # Show preview
        click.echo(f"Loading preview for subscription {subscription_id}...")
        preview = await service.preview_subscription_reset(subscription_id=subscription_id)
        print_preview(preview)

        # Show warning
        print_warning_box([
            "⚠️  WARNING: DESTRUCTIVE OPERATION",
            "",
            f"This will DELETE ALL resources in subscription {subscription_id}!",
            "This action CANNOT be undone!",
        ])

        # Confirm deletion
        if not confirm_deletion():
            click.echo("Operation cancelled by user.")
            sys.exit(0)

        # Execute deletion
        click.echo()
        click.echo(f"Executing subscription reset for {subscription_id}...")
        result = await service.execute_subscription_reset(
            subscription_id=subscription_id, confirmation_token="DELETE"
        )
        print_result(result)

        if not result.success:
            sys.exit(1)

    asyncio.run(run())


@reset.command("resource-group")
@click.argument("subscription_id", type=str)
@click.argument("rg_name", type=str)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Preview only - do not actually delete resources",
)
def reset_resource_group(subscription_id: str, rg_name: str, dry_run: bool):
    """Reset resource group resources.

    Deletes all Azure resources in the specified resource group.
    Graph data for the resource group is also removed.

    Requires interactive confirmation by typing "DELETE".
    """
    ensure_neo4j_running()

    async def run():
        service = TenantResetService(dry_run=dry_run)

        # Show preview
        click.echo(f"Loading preview for resource group {rg_name}...")
        preview = await service.preview_resource_group_reset(
            subscription_id=subscription_id, rg_name=rg_name
        )
        print_preview(preview)

        # Show warning
        print_warning_box([
            "⚠️  WARNING: DESTRUCTIVE OPERATION",
            "",
            f"This will DELETE ALL resources in resource group {rg_name}!",
            "This action CANNOT be undone!",
        ])

        # Confirm deletion
        if not confirm_deletion():
            click.echo("Operation cancelled by user.")
            sys.exit(0)

        # Execute deletion
        click.echo()
        click.echo(f"Executing resource group reset for {rg_name}...")
        result = await service.execute_resource_group_reset(
            subscription_id=subscription_id, rg_name=rg_name, confirmation_token="DELETE"
        )
        print_result(result)

        if not result.success:
            sys.exit(1)

    asyncio.run(run())


@reset.command("resource")
@click.argument("resource_id", type=str)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Preview only - do not actually delete resources",
)
def reset_resource(resource_id: str, dry_run: bool):
    """Reset individual resource.

    Deletes the specified Azure resource.
    Graph data for the resource is also removed.

    RESOURCE_ID should be the full Azure resource ID, e.g.:
    /subscriptions/{sub}/resourceGroups/{rg}/providers/{provider}/{type}/{name}

    Requires interactive confirmation by typing "DELETE".
    """
    ensure_neo4j_running()

    async def run():
        service = TenantResetService(dry_run=dry_run)

        # Show preview
        click.echo(f"Loading preview for resource {resource_id}...")
        preview = await service.preview_resource_reset(resource_id=resource_id)
        print_preview(preview)

        # Show warning
        print_warning_box([
            "⚠️  WARNING: DESTRUCTIVE OPERATION",
            "",
            f"This will DELETE resource {resource_id}!",
            "This action CANNOT be undone!",
        ])

        # Confirm deletion
        if not confirm_deletion():
            click.echo("Operation cancelled by user.")
            sys.exit(0)

        # Execute deletion
        click.echo()
        click.echo(f"Executing resource reset for {resource_id}...")
        result = await service.execute_resource_reset(
            resource_id=resource_id, confirmation_token="DELETE"
        )
        print_result(result)

        if not result.success:
            sys.exit(1)

    asyncio.run(run())
