"""Azure Lighthouse delegation management commands.

This module provides commands for managing Azure Lighthouse delegations:
- lighthouse setup: Setup delegation for a customer tenant
- lighthouse list: List all delegations with status
- lighthouse verify: Verify delegation is active
- lighthouse revoke: Revoke a delegation

Issue #588: Azure Lighthouse Foundation (Phase 1)
"""

import os
import sys
from typing import Optional

import click
from azure.identity import DefaultAzureCredential
from rich.console import Console
from rich.table import Table

from src.config_manager import create_neo4j_config_from_env
from src.sentinel.multi_tenant.exceptions import (
    DelegationExistsError,
    DelegationNotFoundError,
    LighthouseError,
)
from src.sentinel.multi_tenant.lighthouse_manager import LighthouseManager
from src.sentinel.multi_tenant.models import LighthouseStatus
from src.utils.neo4j_startup import ensure_neo4j_running

console = Console()


def get_lighthouse_manager() -> LighthouseManager:
    """Get LighthouseManager instance with Neo4j connection.

    Returns:
        Configured LighthouseManager instance

    Raises:
        SystemExit: If configuration is invalid
    """
    # Get managing tenant ID from environment
    managing_tenant_id = os.getenv("AZURE_LIGHTHOUSE_MANAGING_TENANT_ID")
    if not managing_tenant_id:
        console.print(
            "[red]Error:[/red] AZURE_LIGHTHOUSE_MANAGING_TENANT_ID environment variable not set"
        )
        console.print("\nSet the environment variable:")
        console.print(
            "  export AZURE_LIGHTHOUSE_MANAGING_TENANT_ID=<your-managing-tenant-id>"
        )
        sys.exit(1)

    # Get Bicep output directory
    bicep_output_dir = os.getenv("AZURE_LIGHTHOUSE_BICEP_DIR", "./lighthouse_bicep")

    # Ensure Neo4j is running
    try:
        ensure_neo4j_running()
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to start Neo4j: {e}")
        sys.exit(1)

    # Get Neo4j connection
    try:
        neo4j_config = create_neo4j_config_from_env()
        from neo4j import GraphDatabase

        neo4j_driver = GraphDatabase.driver(
            neo4j_config.uri, auth=(neo4j_config.username, neo4j_config.password)
        )
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to connect to Neo4j: {e}")
        sys.exit(1)

    return LighthouseManager(
        managing_tenant_id=managing_tenant_id,
        neo4j_connection=neo4j_driver,
        bicep_output_dir=bicep_output_dir,
    )


def get_azure_credential():
    """Get Azure credential using DefaultAzureCredential.

    Returns:
        Azure credential instance

    Raises:
        SystemExit: If authentication fails
    """
    try:
        return DefaultAzureCredential()
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to authenticate with Azure: {e}")
        console.print("\nMake sure you're logged in:")
        console.print("  az login")
        sys.exit(1)


# =============================================================================
# Lighthouse Command Group
# =============================================================================


@click.group(name="lighthouse")
def lighthouse() -> None:
    """Azure Lighthouse delegation management commands."""
    pass


# =============================================================================
# lighthouse setup
# =============================================================================


@lighthouse.command(name="setup")
@click.option(
    "--customer-tenant-id", required=True, help="Customer tenant ID to delegate to"
)
@click.option(
    "--customer-tenant-name", required=True, help="Customer tenant display name"
)
@click.option(
    "--subscription-id", required=True, help="Customer subscription ID for delegation"
)
@click.option(
    "--resource-group",
    help="Optional resource group to scope delegation (omit for subscription-level)",
)
@click.option(
    "--role",
    "roles",
    multiple=True,
    default=["Contributor"],
    help="Azure RBAC roles to grant (can specify multiple, default: Contributor)",
)
@click.option(
    "--principal-id",
    "principal_ids",
    multiple=True,
    help="Principal IDs from managing tenant to grant access (can specify multiple)",
)
def setup(
    customer_tenant_id: str,
    customer_tenant_name: str,
    subscription_id: str,
    resource_group: Optional[str],
    roles: tuple,
    principal_ids: tuple,
) -> None:
    """Setup Azure Lighthouse delegation for a customer tenant.

    This command:
    1. Generates a Bicep template for the delegation
    2. Stores delegation info in Neo4j with status=pending
    3. Displays next steps for deploying the template

    Example:
        atg lighthouse setup \\
            --customer-tenant-id 22222222-2222-2222-2222-222222222222 \\
            --customer-tenant-name "Acme Corp" \\
            --subscription-id 33333333-3333-3333-3333-333333333333 \\
            --role Contributor \\
            --role Reader \\
            --principal-id 44444444-4444-4444-4444-444444444444
    """
    console.print(
        "\n[bold cyan]Setting up Azure Lighthouse delegation...[/bold cyan]\n"
    )

    # Validate inputs
    if not principal_ids:
        console.print("[red]Error:[/red] At least one --principal-id must be specified")
        sys.exit(1)

    # Create authorizations from roles and principal IDs
    # For simplicity, grant all roles to all principals
    # In production, you'd want more granular control
    role_definition_ids = {
        "Owner": "8e3af657-a8ff-443c-a75c-2fe8c4bcb635",
        "Contributor": "b24988ac-6180-42a0-ab88-20f7382dd24c",
        "Reader": "acdd72a7-3385-48ef-bd42-f606fba81ae7",
        "User Access Administrator": "18d7d88d-d35e-4fb5-a5c3-7773c20a72d9",
    }

    authorizations = []
    for principal_id in principal_ids:
        for role in roles:
            role_definition_id = role_definition_ids.get(role)
            if not role_definition_id:
                console.print(
                    f"[yellow]Warning:[/yellow] Unknown role '{role}', using as custom role definition ID"
                )
                role_definition_id = role

            authorizations.append(
                {
                    "principalId": principal_id,
                    "principalIdDisplayName": f"Principal {principal_id[:8]}",
                    "roleDefinitionId": role_definition_id,
                }
            )

    # Get manager
    manager = get_lighthouse_manager()

    # Generate delegation template
    try:
        delegation = manager.generate_delegation_template(
            customer_tenant_id=customer_tenant_id,
            customer_tenant_name=customer_tenant_name,
            subscription_id=subscription_id,
            resource_group=resource_group,
            authorizations=authorizations,
        )

        console.print("[green]✓[/green] Delegation template generated successfully")
        console.print(
            f"[green]✓[/green] Bicep template: {delegation.bicep_template_path}"
        )
        console.print(
            f"[green]✓[/green] Status stored in Neo4j: {delegation.status.value}"
        )

        # Display next steps
        console.print("\n[bold]Next steps:[/bold]")
        console.print(f"1. Review the Bicep template: {delegation.bicep_template_path}")
        console.print("2. Deploy to customer subscription:")
        console.print("   az deployment sub create \\")
        console.print("     --location <region> \\")
        console.print(f"     --template-file {delegation.bicep_template_path}")
        console.print("3. Verify delegation after deployment:")
        console.print(
            f"   atg lighthouse verify --customer-tenant-id {customer_tenant_id}"
        )

    except DelegationExistsError as e:
        console.print(f"[red]Error:[/red] {e}")
        console.print("\nUse 'atg lighthouse list' to see existing delegations")
        sys.exit(1)
    except LighthouseError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


# =============================================================================
# lighthouse list
# =============================================================================


@lighthouse.command(name="list")
@click.option(
    "--status",
    type=click.Choice(["pending", "active", "error", "revoked"], case_sensitive=False),
    help="Filter by delegation status",
)
@click.option(
    "--format",
    "format_type",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    help="Output format (default: table)",
)
def list_delegations(status: Optional[str], format_type: str) -> None:
    """List all Azure Lighthouse delegations.

    Shows delegation status, customer info, and Azure resource IDs.

    Example:
        atg lighthouse list
        atg lighthouse list --status active
        atg lighthouse list --format json
    """
    manager = get_lighthouse_manager()

    try:
        delegations = manager.list_delegations()

        # Filter by status if specified
        if status:
            status_enum = LighthouseStatus(status.lower())
            delegations = [d for d in delegations if d.status == status_enum]

        if not delegations:
            console.print("[yellow]No delegations found[/yellow]")
            return

        if format_type == "json":
            import json

            output = [
                {
                    "customer_tenant_id": d.customer_tenant_id,
                    "customer_tenant_name": d.customer_tenant_name,
                    "subscription_id": d.subscription_id,
                    "resource_group": d.resource_group,
                    "status": d.status.value,
                    "registration_definition_id": d.registration_definition_id,
                    "registration_assignment_id": d.registration_assignment_id,
                    "error_message": d.error_message,
                }
                for d in delegations
            ]
            console.print(json.dumps(output, indent=2))
        else:
            # Table format
            table = Table(title="Azure Lighthouse Delegations")
            table.add_column("Customer Tenant", style="cyan")
            table.add_column("Subscription", style="blue")
            table.add_column("Resource Group", style="blue")
            table.add_column("Status", style="green")
            table.add_column("Definition ID", style="dim")

            for d in delegations:
                status_color = {
                    LighthouseStatus.PENDING: "yellow",
                    LighthouseStatus.ACTIVE: "green",
                    LighthouseStatus.ERROR: "red",
                    LighthouseStatus.REVOKED: "dim",
                }.get(d.status, "white")

                table.add_row(
                    f"{d.customer_tenant_name}\n{d.customer_tenant_id}",
                    d.subscription_id or "N/A",
                    d.resource_group or "(subscription-level)",
                    f"[{status_color}]{d.status.value}[/{status_color}]",
                    d.registration_definition_id[:50] + "..."
                    if d.registration_definition_id
                    and len(d.registration_definition_id) > 50
                    else d.registration_definition_id or "N/A",
                )

            console.print(table)
            console.print(f"\nTotal: {len(delegations)} delegation(s)")

    except LighthouseError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


# =============================================================================
# lighthouse verify
# =============================================================================


@lighthouse.command(name="verify")
@click.option(
    "--customer-tenant-id", required=True, help="Customer tenant ID to verify"
)
def verify(customer_tenant_id: str) -> None:
    """Verify Azure Lighthouse delegation is active.

    Checks Azure API to confirm delegation is active and updates Neo4j status.

    Example:
        atg lighthouse verify --customer-tenant-id 22222222-2222-2222-2222-222222222222
    """
    console.print(
        f"\n[bold cyan]Verifying delegation for {customer_tenant_id}...[/bold cyan]\n"
    )

    manager = get_lighthouse_manager()
    credential = get_azure_credential()

    try:
        is_verified = manager.verify_delegation(
            customer_tenant_id=customer_tenant_id, azure_credential=credential
        )

        if is_verified:
            console.print("[green]✓[/green] Delegation is ACTIVE")
            console.print("[green]✓[/green] Status updated in Neo4j")
        else:
            console.print("[yellow]⚠[/yellow] Delegation verification failed")
            console.print("[yellow]⚠[/yellow] Check Azure portal for deployment status")

    except DelegationNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        console.print("\nUse 'atg lighthouse list' to see available delegations")
        sys.exit(1)
    except LighthouseError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


# =============================================================================
# lighthouse revoke
# =============================================================================


@lighthouse.command(name="revoke")
@click.option(
    "--customer-tenant-id",
    required=True,
    help="Customer tenant ID to revoke delegation from",
)
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
def revoke(customer_tenant_id: str, confirm: bool) -> None:
    """Revoke Azure Lighthouse delegation.

    Removes delegation from Azure and updates status in Neo4j.

    Example:
        atg lighthouse revoke --customer-tenant-id 22222222-2222-2222-2222-222222222222
    """
    console.print(
        f"\n[bold yellow]Revoking delegation for {customer_tenant_id}...[/bold yellow]\n"
    )

    # Confirmation prompt
    if not confirm:
        response = click.prompt(
            "This will remove all Lighthouse access to the customer tenant. Continue? [y/N]",
            type=str,
            default="n",
        )
        if response.lower() not in ["y", "yes"]:
            console.print("Cancelled")
            return

    manager = get_lighthouse_manager()
    credential = get_azure_credential()

    try:
        manager.revoke_delegation(
            customer_tenant_id=customer_tenant_id, azure_credential=credential
        )

        console.print("[green]✓[/green] Delegation revoked successfully")
        console.print("[green]✓[/green] Status updated in Neo4j")

    except DelegationNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        console.print("\nUse 'atg lighthouse list' to see available delegations")
        sys.exit(1)
    except LighthouseError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


# Export for command registry
__all__ = ["lighthouse"]
