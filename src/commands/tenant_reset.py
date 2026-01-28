"""Tenant Reset Commands (Issue #627).

This module provides commands for safely resetting Azure tenants with
comprehensive safety controls:

- reset_tenant: Reset entire tenant (all subscriptions, RGs, resources, identities)
- reset_subscriptions: Reset specific subscriptions
- reset_resource_groups: Reset specific resource groups
- reset_resource: Reset single resource

Safety Features:
- 5-stage confirmation flow
- ATG Service Principal preservation
- Tamper-proof audit logging
- Rate limiting (1 reset/hour/tenant)
- Dry-run mode
- NO --force or --yes flags

Philosophy:
- Ruthless simplicity: Clear command structure, no hidden bypasses
- Zero-BS implementation: Every safety control works, no compromises
- User safety first: Multiple confirmation stages, cannot be bypassed
"""

import asyncio
import sys

import click
from azure.identity import DefaultAzureCredential

from src.services.reset_confirmation import (
    RateLimitError,
    ResetConfirmation,
    ResetScope,
    SecurityError,
)
from src.services.tenant_reset_service import TenantResetRateLimiter, TenantResetService


@click.command("reset-tenant")
@click.option(
    "--tenant-id",
    required=True,
    help="Azure tenant ID to reset (GUID format)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview what would be deleted without actually deleting",
)
def reset_tenant_command(tenant_id: str, dry_run: bool):
    """
    Reset entire Azure tenant (DESTRUCTIVE).

    This command will DELETE:
    - All subscriptions
    - All resource groups
    - All resources
    - All Entra ID identities (except ATG Service Principal)

    Safety Controls:
    - 5-stage confirmation flow
    - ATG SP preservation
    - Rate limiting (1 reset/hour)
    - Tamper-proof audit log
    - NO bypass flags allowed

    Example:
        azure-tenant-grapher reset-tenant --tenant-id 12345678-1234-1234-1234-123456789abc

    Dry-run mode:
        azure-tenant-grapher reset-tenant --tenant-id <tenant-id> --dry-run
    """
    asyncio.run(_reset_tenant(tenant_id, dry_run))


async def _reset_tenant(tenant_id: str, dry_run: bool):
    """Internal async implementation for tenant reset."""
    try:
        # Initialize service
        credential = DefaultAzureCredential()
        service = TenantResetService(
            credential=credential,
            tenant_id=tenant_id,
            concurrency=10,
        )

        # Rate limiting check
        rate_limiter = TenantResetRateLimiter()
        allowed, wait_seconds = rate_limiter.check_rate_limit(tenant_id)

        if not allowed:
            click.echo("\n❌ Rate limit exceeded.", err=True)
            click.echo(
                f"   You must wait {wait_seconds} seconds ({wait_seconds // 60} minutes) before the next reset.",
                err=True,
            )
            click.echo(
                "   Rate limit: 1 reset per hour per tenant (safety control).",
                err=True,
            )
            sys.exit(1)

        # Calculate scope
        click.echo("\n🔍 Calculating reset scope...")
        scope_data = await service.calculate_scope_tenant(tenant_id)

        # Confirmation flow
        confirmation = ResetConfirmation(
            scope=ResetScope.TENANT,
            dry_run=dry_run,
            tenant_id=tenant_id,
        )

        if dry_run:
            # Dry-run mode: Just display preview
            confirmation.display_dry_run(scope_data)
            click.echo("\n✅ Dry-run complete. No resources were deleted.")
            return

        # Interactive confirmation
        confirmed = await confirmation.confirm(scope_data)

        if not confirmed:
            click.echo("\n❌ Reset cancelled by user.")
            sys.exit(0)

        # Pre-flight validation
        click.echo("\n🛡️  Pre-flight validation...")
        atg_sp_fingerprint = await service.validate_atg_sp_before_deletion(tenant_id)
        click.echo(f"✓ ATG SP verified: {atg_sp_fingerprint['display_name']}")

        # Order resources by dependencies
        deletion_waves = await service.order_by_dependencies(scope_data["to_delete"])
        click.echo(f"\n🔄 Deletion waves: {len(deletion_waves)}")

        # Execute deletion
        click.echo("\n🗑️  Deleting resources...")
        results = await service.delete_resources(deletion_waves, concurrency=10)

        # Post-deletion verification
        click.echo("\n🛡️  Post-deletion verification...")
        await service.verify_atg_sp_after_deletion(atg_sp_fingerprint, tenant_id)
        click.echo("✓ ATG SP verified (still exists)")

        # Display results
        click.echo("\n" + "=" * 80)
        click.echo("RESET COMPLETE")
        click.echo("=" * 80)
        click.echo(f"Deleted: {len(results['deleted'])} resources")
        click.echo(f"Failed: {len(results['failed'])} resources")

        if results["failed"]:
            click.echo("\nFailed deletions:")
            for resource_id in results["failed"][:10]:
                error = results["errors"].get(resource_id, "Unknown error")
                click.echo(f"  - {resource_id}")
                click.echo(f"    Error: {error}")

            if len(results["failed"]) > 10:
                click.echo(f"  ... and {len(results['failed']) - 10} more")

    except SecurityError as e:
        click.echo(f"\n🛡️  SECURITY ERROR: {e}", err=True)
        sys.exit(1)
    except RateLimitError as e:
        click.echo(f"\n⏱️  RATE LIMIT ERROR: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"\n❌ ERROR: {e}", err=True)
        sys.exit(1)


@click.command("reset-subscriptions")
@click.option(
    "--tenant-id",
    required=True,
    help="Azure tenant ID",
)
@click.option(
    "--subscription-ids",
    required=True,
    help="Comma-separated list of subscription IDs to reset",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview what would be deleted without actually deleting",
)
def reset_subscriptions_command(tenant_id: str, subscription_ids: str, dry_run: bool):
    """
    Reset specific Azure subscriptions (DESTRUCTIVE).

    This command will DELETE:
    - All resource groups in specified subscriptions
    - All resources in specified subscriptions

    Preserves:
    - ATG Service Principal
    - Other subscriptions
    - Entra ID identities

    Example:
        azure-tenant-grapher reset-subscriptions \\
            --tenant-id <tenant-id> \\
            --subscription-ids sub-1,sub-2,sub-3
    """
    sub_ids = [sid.strip() for sid in subscription_ids.split(",")]
    asyncio.run(_reset_subscriptions(tenant_id, sub_ids, dry_run))


async def _reset_subscriptions(tenant_id: str, subscription_ids: list, dry_run: bool):
    """Internal async implementation for subscription reset."""
    try:
        credential = DefaultAzureCredential()
        service = TenantResetService(
            credential=credential,
            tenant_id=tenant_id,
            concurrency=10,
        )

        # Rate limiting
        rate_limiter = TenantResetRateLimiter()
        allowed, wait_seconds = rate_limiter.check_rate_limit(tenant_id)

        if not allowed:
            click.echo(
                f"\n❌ Rate limit exceeded. Wait {wait_seconds} seconds.", err=True
            )
            sys.exit(1)

        # Calculate scope
        click.echo("\n🔍 Calculating reset scope...")
        scope_data = await service.calculate_scope_subscription(subscription_ids)

        # Confirmation
        confirmation = ResetConfirmation(
            scope=ResetScope.SUBSCRIPTION,
            dry_run=dry_run,
            tenant_id=tenant_id,
        )

        if dry_run:
            confirmation.display_dry_run(scope_data)
            return

        confirmed = await confirmation.confirm(scope_data)
        if not confirmed:
            click.echo("\n❌ Reset cancelled.")
            sys.exit(0)

        # Execute
        deletion_waves = await service.order_by_dependencies(scope_data["to_delete"])
        results = await service.delete_resources(deletion_waves, concurrency=10)

        # Display results
        click.echo("\n✅ Reset complete")
        click.echo(f"Deleted: {len(results['deleted'])} resources")
        click.echo(f"Failed: {len(results['failed'])} resources")

    except Exception as e:
        click.echo(f"\n❌ ERROR: {e}", err=True)
        sys.exit(1)


@click.command("reset-resource-groups")
@click.option(
    "--tenant-id",
    required=True,
    help="Azure tenant ID",
)
@click.option(
    "--subscription-id",
    required=True,
    help="Subscription ID containing the resource groups",
)
@click.option(
    "--resource-groups",
    required=True,
    help="Comma-separated list of resource group names to reset",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview what would be deleted without actually deleting",
)
def reset_resource_groups_command(
    tenant_id: str, subscription_id: str, resource_groups: str, dry_run: bool
):
    """
    Reset specific Azure resource groups (DESTRUCTIVE).

    This command will DELETE:
    - All resources in specified resource groups

    Preserves:
    - ATG Service Principal
    - Other resource groups
    - Other subscriptions
    - Entra ID identities

    Example:
        azure-tenant-grapher reset-resource-groups \\
            --tenant-id <tenant-id> \\
            --subscription-id <sub-id> \\
            --resource-groups rg-1,rg-2,rg-3
    """
    rg_names = [rg.strip() for rg in resource_groups.split(",")]
    asyncio.run(_reset_resource_groups(tenant_id, subscription_id, rg_names, dry_run))


async def _reset_resource_groups(
    tenant_id: str, subscription_id: str, resource_group_names: list, dry_run: bool
):
    """Internal async implementation for resource group reset."""
    try:
        credential = DefaultAzureCredential()
        service = TenantResetService(
            credential=credential,
            tenant_id=tenant_id,
            concurrency=10,
        )

        # Rate limiting
        rate_limiter = TenantResetRateLimiter()
        allowed, wait_seconds = rate_limiter.check_rate_limit(tenant_id)

        if not allowed:
            click.echo(
                f"\n❌ Rate limit exceeded. Wait {wait_seconds} seconds.", err=True
            )
            sys.exit(1)

        # Calculate scope
        click.echo("\n🔍 Calculating reset scope...")
        scope_data = await service.calculate_scope_resource_group(
            resource_group_names, subscription_id
        )

        # Confirmation
        confirmation = ResetConfirmation(
            scope=ResetScope.RESOURCE_GROUP,
            dry_run=dry_run,
            tenant_id=tenant_id,
        )

        if dry_run:
            confirmation.display_dry_run(scope_data)
            return

        confirmed = await confirmation.confirm(scope_data)
        if not confirmed:
            click.echo("\n❌ Reset cancelled.")
            sys.exit(0)

        # Execute
        deletion_waves = await service.order_by_dependencies(scope_data["to_delete"])
        results = await service.delete_resources(deletion_waves, concurrency=10)

        # Display results
        click.echo("\n✅ Reset complete")
        click.echo(f"Deleted: {len(results['deleted'])} resources")
        click.echo(f"Failed: {len(results['failed'])} resources")

    except Exception as e:
        click.echo(f"\n❌ ERROR: {e}", err=True)
        sys.exit(1)


@click.command("reset-resource")
@click.option(
    "--tenant-id",
    required=True,
    help="Azure tenant ID",
)
@click.option(
    "--resource-id",
    required=True,
    help="Full Azure resource ID to delete",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview what would be deleted without actually deleting",
)
def reset_resource_command(tenant_id: str, resource_id: str, dry_run: bool):
    """
    Delete a single Azure resource (DESTRUCTIVE).

    Security:
    - Blocks deletion of ATG Service Principal
    - Rate limited
    - Audit logged

    Example:
        azure-tenant-grapher reset-resource \\
            --tenant-id <tenant-id> \\
            --resource-id /subscriptions/.../resourceGroups/.../providers/.../vm-1
    """
    asyncio.run(_reset_resource(tenant_id, resource_id, dry_run))


async def _reset_resource(tenant_id: str, resource_id: str, dry_run: bool):
    """Internal async implementation for single resource deletion."""
    try:
        credential = DefaultAzureCredential()
        service = TenantResetService(
            credential=credential,
            tenant_id=tenant_id,
            concurrency=10,
        )

        # Rate limiting
        rate_limiter = TenantResetRateLimiter()
        allowed, wait_seconds = rate_limiter.check_rate_limit(tenant_id)

        if not allowed:
            click.echo(
                f"\n❌ Rate limit exceeded. Wait {wait_seconds} seconds.", err=True
            )
            sys.exit(1)

        # Calculate scope
        click.echo("\n🔍 Validating resource...")
        scope_data = await service.calculate_scope_resource(resource_id)

        # Confirmation
        confirmation = ResetConfirmation(
            scope=ResetScope.RESOURCE,
            dry_run=dry_run,
            tenant_id=tenant_id,
        )

        if dry_run:
            confirmation.display_dry_run(scope_data)
            return

        confirmed = await confirmation.confirm(scope_data)
        if not confirmed:
            click.echo("\n❌ Deletion cancelled.")
            sys.exit(0)

        # Execute
        deletion_waves = await service.order_by_dependencies(scope_data["to_delete"])
        results = await service.delete_resources(deletion_waves, concurrency=1)

        # Display results
        if results["deleted"]:
            click.echo("\n✅ Resource deleted successfully")
        elif results["failed"]:
            click.echo("\n❌ Resource deletion failed")
            error = results["errors"].get(resource_id, "Unknown error")
            click.echo(f"Error: {error}")

    except Exception as e:
        click.echo(f"\n❌ ERROR: {e}", err=True)
        sys.exit(1)


# Export all commands for registration
__all__ = [
    "reset_resource_command",
    "reset_resource_groups_command",
    "reset_subscriptions_command",
    "reset_tenant_command",
]
