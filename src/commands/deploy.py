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
def deploy_command(
    iac_dir: str,
    target_tenant_id: str,
    resource_group: str,
    location: str,
    subscription_id: str | None,
    iac_format: str | None,
    dry_run: bool,
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

        result = deploy_iac(
            iac_dir=Path(iac_dir),
            target_tenant_id=target_tenant_id,
            resource_group=resource_group,
            location=location,
            subscription_id=subscription_id,
            iac_format=iac_format,
            dry_run=dry_run,
        )

        # Display result
        status = result["status"]
        format_type = result.get("format", "unknown")

        if dry_run:
            click.echo(
                f"\nDeployment plan completed successfully ({format_type} format)"
            )
            click.echo(f"Status: {status}")
        else:
            click.echo(
                f"\nDeployment completed successfully ({format_type} format)"
            )
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
