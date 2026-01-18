"""CLI command for deploying IaC."""

import asyncio
import logging
from pathlib import Path
from typing import cast

import click

from ..deployment.agent_deployer import AgentDeployer, DeploymentResult
from ..deployment.format_detector import IaCFormat
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
@click.option(
    "--agent",
    is_flag=True,
    help="Enable autonomous goal-seeking agent mode for deployment",
)
@click.option(
    "--max-iterations",
    type=int,
    default=20,
    help="Maximum deployment iterations in agent mode (default: 20)",
)
@click.option(
    "--agent-timeout",
    type=int,
    default=6000,
    help="Timeout in seconds for agent mode deployment (default: 6000)",
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
    agent: bool,
    max_iterations: int,
    agent_timeout: int,
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

        # Deploy with autonomous goal-seeking agent
        atg deploy --iac-dir ./output/iac --target-tenant-id <TENANT_ID> --resource-group my-rg --agent

        # Agent mode with custom settings
        atg deploy --iac-dir ./output/iac --target-tenant-id <TENANT_ID> --resource-group my-rg --agent --max-iterations 10 --agent-timeout 600
    """
    try:
        # Check if IaC directory exists
        iac_path = Path(iac_dir)
        if not iac_path.exists():
            click.echo(f"Error: IaC directory does not exist: {iac_dir}", err=True)
            raise SystemExit(1)

        # Route to agent mode if --agent flag is set
        if agent:
            click.echo(f"Starting autonomous deployment agent from {iac_dir}...")
            click.echo(
                f"Agent configuration: max_iterations={max_iterations}, timeout={agent_timeout}s"
            )

            # Create agent deployer
            deployer = AgentDeployer(
                iac_dir=iac_path,
                target_tenant_id=target_tenant_id,
                resource_group=resource_group,
                location=location,
                subscription_id=subscription_id,
                iac_format=cast(IaCFormat, iac_format) if iac_format else None,
                dry_run=dry_run,
                max_iterations=max_iterations,
                timeout_seconds=agent_timeout,
            )

            # Run agent deployment (async)
            result = asyncio.run(deployer.deploy_with_agent())

            # Display deployment report
            _display_agent_report(result)

            # Exit with appropriate code
            if not result.success:
                raise SystemExit(1)

            return

        # Normal (non-agent) deployment path
        click.echo(f"Starting deployment from {iac_dir}...")

        # Deploy control plane (IaC)
        result = deploy_iac(
            iac_dir=iac_path,
            target_tenant_id=target_tenant_id,
            resource_group=resource_group,
            location=location,
            subscription_id=subscription_id,
            iac_format=cast(IaCFormat, iac_format) if iac_format else None,
            dry_run=dry_run,
        )

        # Deploy data plane if requested
        if dataplane != "none" and not dry_run:
            click.echo(f"\nStarting data plane replication ({dataplane} mode)...")

            # Get source subscription/tenant for replication from environment or prompt
            source_tenant_id = None
            source_subscription_id = None

            # Try to get from environment variables first
            import os
            source_tenant_id = os.getenv("ATG_SOURCE_TENANT_ID")
            source_subscription_id = os.getenv("ATG_SOURCE_SUBSCRIPTION_ID")

            # If not in environment, prompt user (interactive mode only)
            if not source_tenant_id or not source_subscription_id:
                click.echo("⚠️  Data plane replication requires source tenant/subscription IDs")
                click.echo("    Set ATG_SOURCE_TENANT_ID and ATG_SOURCE_SUBSCRIPTION_ID environment variables")
                click.echo("    or provide them interactively below:")

                if not source_tenant_id:
                    source_tenant_id = click.prompt("Source tenant ID", type=str, default="")
                if not source_subscription_id:
                    source_subscription_id = click.prompt("Source subscription ID", type=str, default="")

                # If still empty, skip dataplane replication
                if not source_tenant_id or not source_subscription_id:
                    click.echo("⚠️  Skipping data plane replication (missing source configuration)")
                    click.echo("    Control plane deployment completed successfully.")
                    click.echo("    See docs/DATAPLANE_PLUGIN_ARCHITECTURE.md for manual replication.")
                else:
                    # Execute dataplane replication
                    from ..deployment.dataplane_orchestrator import (
                        orchestrate_dataplane_replication,
                        ReplicationMode,
                    )

                    try:
                        dataplane_result = orchestrate_dataplane_replication(
                            iac_dir=Path(iac_dir),
                            mode=ReplicationMode(dataplane),
                            source_tenant_id=source_tenant_id,
                            target_tenant_id=target_tenant_id,
                            source_subscription_id=source_subscription_id,
                            target_subscription_id=subscription_id or "",
                            sp_client_id=sp_client_id,
                            sp_client_secret=sp_client_secret,
                        )

                        # Display dataplane results
                        click.echo(f"\nData plane replication {dataplane_result['status']}")
                        click.echo(f"  Resources processed: {dataplane_result['resources_processed']}")
                        click.echo(f"  Plugins executed: {', '.join(dataplane_result['plugins_executed']) or 'none'}")
                        if dataplane_result['errors']:
                            click.echo(f"  Errors: {len(dataplane_result['errors'])}")
                        if dataplane_result['warnings']:
                            click.echo(f"  Warnings: {len(dataplane_result['warnings'])}")

                    except Exception as e:
                        click.echo(f"⚠️  Data plane replication failed: {e}", err=True)
                        click.echo("    Control plane deployment completed successfully.")
            else:
                # Execute dataplane replication with environment variables
                from ..deployment.dataplane_orchestrator import (
                    orchestrate_dataplane_replication,
                    ReplicationMode,
                )

                try:
                    dataplane_result = orchestrate_dataplane_replication(
                        iac_dir=Path(iac_dir),
                        mode=ReplicationMode(dataplane),
                        source_tenant_id=source_tenant_id,
                        target_tenant_id=target_tenant_id,
                        source_subscription_id=source_subscription_id,
                        target_subscription_id=subscription_id or "",
                        sp_client_id=sp_client_id,
                        sp_client_secret=sp_client_secret,
                    )

                    # Display dataplane results
                    click.echo(f"\nData plane replication {dataplane_result['status']}")
                    click.echo(f"  Resources processed: {dataplane_result['resources_processed']}")
                    click.echo(f"  Plugins executed: {', '.join(dataplane_result['plugins_executed']) or 'none'}")
                    if dataplane_result['errors']:
                        click.echo(f"  Errors: {len(dataplane_result['errors'])}")
                    if dataplane_result['warnings']:
                        click.echo(f"  Warnings: {len(dataplane_result['warnings'])}")

                except Exception as e:
                    click.echo(f"⚠️  Data plane replication failed: {e}", err=True)
                    click.echo("    Control plane deployment completed successfully.")

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
        raise SystemExit(1) from e


def _display_agent_report(result: DeploymentResult) -> None:
    """Display deployment report for agent mode.

    Args:
        result: DeploymentResult from agent deployment
    """
    click.echo("\n" + "=" * 80)
    click.echo("AUTONOMOUS DEPLOYMENT REPORT")
    click.echo("=" * 80)

    # Status
    status_emoji = "✅" if result.success else "❌"
    click.echo(f"\nStatus: {status_emoji} {result.final_status.upper()}")
    click.echo(f"Iterations: {result.iteration_count}")

    # Error summary
    if result.error_log:
        click.echo(f"\nErrors encountered: {len(result.error_log)}")
        click.echo("\nError Summary:")
        for i, error in enumerate(result.error_log, 1):
            iteration = error.get("iteration", "?")
            error_type = error.get("error_type", "Error")
            message = str(error.get("message", ""))[:100]
            click.echo(f"  {i}. [Iteration {iteration}] {error_type}: {message}")

    # Deployment output
    if result.deployment_output:
        click.echo("\nDeployment Output:")
        click.echo(f"  Format: {result.deployment_output.get('format', 'unknown')}")
        click.echo(f"  Status: {result.deployment_output.get('status', 'unknown')}")
        if output := result.deployment_output.get("output"):
            click.echo(f"\n{output[:500]}")

    click.echo("\n" + "=" * 80)
