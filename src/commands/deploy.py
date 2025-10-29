"""CLI command for deploying IaC."""

import logging
from pathlib import Path

import click

from ..deployment.orchestrator import deploy_iac

logger = logging.getLogger(__name__)


@click.command(name="deploy")
@click.option(
    "--iac-dir",
    required=True,
    type=click.Path(exists=True),
    help="IaC directory path",
)
@click.option(
    "--target-tenant-id",
    required=True,
    help="Target Azure tenant ID",
)
@click.option(
    "--resource-group",
    required=True,
    help="Target resource group name",
)
@click.option(
    "--location",
    default="eastus",
    help="Azure region (default: eastus)",
)
@click.option(
    "--subscription-id",
    default=None,
    help="Optional Azure subscription ID (for bicep/arm deployments)",
)
@click.option(
    "--format",
    "iac_format",
    type=click.Choice(["terraform", "bicep", "arm"]),
    help="IaC format (auto-detect if not specified)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Plan/validate only, no deployment",
)
@click.option(
    "--dataplane",
    type=click.Choice(["none", "template", "replication"]),
    default="none",
    help="Data plane replication mode: none (control plane only), template (structure only), or replication (full data copy)",
)
@click.option(
    "--sp-client-id",
    default=None,
    help="Service principal client ID for dataplane operations (optional, uses DefaultAzureCredential if not specified)",
)
@click.option(
    "--sp-client-secret",
    default=None,
    help="Service principal client secret for dataplane operations (optional)",
)
def deploy_command(
    iac_dir: str,
    target_tenant_id: str,
    resource_group: str,
    location: str,
    subscription_id: str | None,
    iac_format: str | None,
    dry_run: bool,
    dataplane: str,
    sp_client_id: str | None,
    sp_client_secret: str | None,
):
    """Deploy generated IaC to target tenant.

    This command deploys Infrastructure-as-Code (IaC) to a target Azure tenant.
    It supports multiple IaC formats (Terraform, Bicep, ARM) and can auto-detect
    the format from the directory contents.

    Examples:

        # Deploy Terraform with auto-detection
        atg deploy --iac-dir ./output/iac --target-tenant-id <TENANT_ID> --resource-group my-rg

        # Dry-run Bicep deployment
        atg deploy --iac-dir ./bicep --target-tenant-id <TENANT_ID> --resource-group my-rg --format bicep --dry-run

        # Deploy ARM template to specific subscription
        atg deploy --iac-dir ./arm --target-tenant-id <TENANT_ID> --resource-group my-rg --subscription-id <SUB_ID>
    """
    try:
        click.echo(f"Starting deployment from {iac_dir}...")

        # Deploy control plane (IaC)
        result = deploy_iac(
            iac_dir=Path(iac_dir),
            target_tenant_id=target_tenant_id,
            resource_group=resource_group,
            location=location,
            subscription_id=subscription_id,
            iac_format=iac_format,
            dry_run=dry_run,
        )

        # Deploy data plane if requested
        if dataplane != "none" and not dry_run:
            click.echo(f"\nStarting data plane replication ({dataplane} mode)...")

            from ..deployment.dataplane_orchestrator import (
                orchestrate_dataplane_replication,
                ReplicationMode,
            )

            # Need source subscription/tenant for replication
            # TODO: Get these from Neo4j or user input
            # For now, warn that this requires additional configuration
            click.echo("⚠️  Data plane replication requires source tenant/subscription configuration")
            click.echo("    This feature is in development. Control plane deployment completed successfully.")
            click.echo("    See docs/DATAPLANE_PLUGIN_ARCHITECTURE.md for manual replication instructions.")

            # Placeholder for future implementation
            # dataplane_result = orchestrate_dataplane_replication(
            #     iac_dir=Path(iac_dir),
            #     mode=ReplicationMode(dataplane),
            #     source_tenant_id=source_tenant_id,
            #     target_tenant_id=target_tenant_id,
            #     source_subscription_id=source_subscription_id,
            #     target_subscription_id=subscription_id,
            #     sp_client_id=sp_client_id,
            #     sp_client_secret=sp_client_secret,
            # )

        # Display result
        status = result["status"]
        format_type = result.get("format", "unknown")

        if dry_run:
            click.echo(
                f"\nDeployment plan completed successfully ({format_type} format)"
            )
            click.echo(f"Status: {status}")
        else:
            click.echo(f"\nDeployment completed successfully ({format_type} format)")
            click.echo(f"Status: {status}")

        # Show output if available
        if result.get("output"):
            click.echo("\nDeployment output:")
            click.echo("-" * 80)
            click.echo(result["output"])
            click.echo("-" * 80)

    except Exception as e:
        click.echo(f"Deployment failed: {e}", err=True)
        logger.exception("Deployment error")
        raise SystemExit(1)
