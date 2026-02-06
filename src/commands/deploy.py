"""CLI command for deploying IaC."""

import asyncio
import logging
import os
from pathlib import Path
from typing import cast

import click
from neo4j import AsyncGraphDatabase, AsyncSession

from ..architectural_pattern_analyzer import ArchitecturalPatternAnalyzer
from ..architecture_based_replicator import ArchitecturePatternReplicator
from ..deployment.agent_deployer import AgentDeployer, DeploymentResult
from ..deployment.format_detector import IaCFormat
from ..deployment.orchestrator import deploy_iac
from ..iac.emitters.terraform_emitter import TerraformEmitter
from ..iac.emitters.bicep_emitter import BicepEmitter
from ..iac.emitters.arm_emitter import ArmEmitter
from ..services.replication_plan_converter import replication_plan_to_tenant_graph

logger = logging.getLogger(__name__)


@click.command(name="deploy")
@click.option(
    "--iac-dir",
    required=False,
    type=click.Path(exists=True),
    help="IaC directory path (not required when using --from-replication-plan)",
)
@click.option(
    "--target-tenant-id",
    required=False,
    help="Target Azure tenant ID (defaults to AZURE_TENANT_ID from .env)",
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
@click.option(
    "--from-replication-plan",
    is_flag=True,
    help="Generate deployment from architecture-based replication plan",
)
@click.option(
    "--pattern-filter",
    multiple=True,
    help="Filter patterns to deploy (can specify multiple, e.g., --pattern-filter 'Web Application' --pattern-filter 'VM Workload')",
)
@click.option(
    "--instance-filter",
    type=str,
    help="Filter instances by index (e.g., '0,2,5' or '0-3')",
)
def deploy_command(
    iac_dir: str,
    target_tenant_id: str | None,
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
    from_replication_plan: bool,
    pattern_filter: tuple[str, ...],
    instance_filter: str | None,
):
    """Deploy generated IaC to target tenant.

    This command deploys Infrastructure-as-Code (IaC) to a target Azure tenant.
    It supports multiple IaC formats (Terraform, Bicep, ARM) and can auto-detect
    the format from the directory contents.

    Examples:

        # Deploy Terraform with auto-detection (using AZURE_TENANT_ID from .env)
        atg deploy --iac-dir ./output/iac --resource-group my-rg

        # Deploy Terraform with explicit tenant ID
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
        # Validate iac-dir requirement based on mode
        if not from_replication_plan:
            # Normal mode requires --iac-dir
            if not iac_dir:
                click.echo(
                    "Error: --iac-dir is required (unless using --from-replication-plan)",
                    err=True,
                )
                raise SystemExit(1)

            # Check if IaC directory exists
            iac_path = Path(iac_dir)
            if not iac_path.exists():
                click.echo(f"Error: IaC directory does not exist: {iac_dir}", err=True)
                raise SystemExit(1)
        else:
            # Replication plan mode doesn't need iac-dir
            iac_path = None  # type: ignore

        # Use tenant ID from flag or fall back to environment variable
        effective_tenant_id = target_tenant_id or os.environ.get("AZURE_TENANT_ID")
        if not effective_tenant_id:
            click.echo(
                "❌ No target tenant ID provided and AZURE_TENANT_ID not set in environment.",
                err=True,
            )
            raise SystemExit(1)

        # Route to replication plan deployment if --from-replication-plan flag is set
        if from_replication_plan:
            click.echo("Deploying from architecture-based replication plan...")

            # Validate: iac-dir is not required for replication plan mode
            # (IaC will be generated from the replication plan)

            # Run async deployment workflow
            result = asyncio.run(
                _deploy_from_replication_plan(
                    target_tenant_id=effective_tenant_id,
                    resource_group=resource_group,
                    location=location,
                    subscription_id=subscription_id,
                    iac_format=iac_format,
                    dry_run=dry_run,
                    pattern_filter=pattern_filter if pattern_filter else None,
                    instance_filter=instance_filter,
                )
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
                click.echo(f"\nDeployment completed successfully ({format_type} format)")
                click.echo(f"Status: {status}")

            # Show output if available
            if result.get("output"):
                click.echo("\nDeployment output:")
                click.echo("-" * 80)
                click.echo(result["output"])
                click.echo("-" * 80)

            return

        # Route to agent mode if --agent flag is set
        if agent:
            click.echo(f"Starting autonomous deployment agent from {iac_dir}...")
            click.echo(
                f"Agent configuration: max_iterations={max_iterations}, timeout={agent_timeout}s"
            )

            # Create agent deployer
            deployer = AgentDeployer(
                iac_dir=iac_path,
                target_tenant_id=effective_tenant_id,
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
            target_tenant_id=effective_tenant_id,
            resource_group=resource_group,
            location=location,
            subscription_id=subscription_id,
            iac_format=cast(IaCFormat, iac_format) if iac_format else None,
            dry_run=dry_run,
            sp_client_id=sp_client_id,
            sp_client_secret=sp_client_secret,
        )

        # Deploy data plane if requested
        if dataplane != "none" and not dry_run:
            click.echo(f"\nStarting data plane replication ({dataplane} mode)...")

            # Get source subscription/tenant for replication from environment or prompt
            source_tenant_id = None
            source_subscription_id = None

            # Try to get from environment variables first
            source_tenant_id = os.getenv("ATG_SOURCE_TENANT_ID")
            source_subscription_id = os.getenv("ATG_SOURCE_SUBSCRIPTION_ID")

            # If not in environment, prompt user (interactive mode only)
            if not source_tenant_id or not source_subscription_id:
                click.echo(
                    "⚠️  Data plane replication requires source tenant/subscription IDs"
                )
                click.echo(
                    "    Set ATG_SOURCE_TENANT_ID and ATG_SOURCE_SUBSCRIPTION_ID environment variables"
                )
                click.echo("    or provide them interactively below:")

                if not source_tenant_id:
                    source_tenant_id = click.prompt(
                        "Source tenant ID", type=str, default=""
                    )
                if not source_subscription_id:
                    source_subscription_id = click.prompt(
                        "Source subscription ID", type=str, default=""
                    )

                # If still empty, skip dataplane replication
                if not source_tenant_id or not source_subscription_id:
                    click.echo(
                        "⚠️  Skipping data plane replication (missing source configuration)"
                    )
                    click.echo("    Control plane deployment completed successfully.")
                    click.echo(
                        "    See docs/DATAPLANE_PLUGIN_ARCHITECTURE.md for manual replication."
                    )
                else:
                    # Execute dataplane replication
                    from ..deployment.dataplane_orchestrator import (
                        ReplicationMode,
                        orchestrate_dataplane_replication,
                    )

                    try:
                        dataplane_result = orchestrate_dataplane_replication(
                            iac_dir=Path(iac_dir),
                            mode=ReplicationMode(dataplane),
                            source_tenant_id=source_tenant_id,
                            target_tenant_id=effective_tenant_id,
                            source_subscription_id=source_subscription_id,
                            target_subscription_id=subscription_id or "",
                            sp_client_id=sp_client_id,
                            sp_client_secret=sp_client_secret,
                        )

                        # Display dataplane results
                        click.echo(
                            f"\nData plane replication {dataplane_result['status']}"
                        )
                        click.echo(
                            f"  Resources processed: {dataplane_result['resources_processed']}"
                        )
                        click.echo(
                            f"  Plugins executed: {', '.join(dataplane_result['plugins_executed']) or 'none'}"
                        )
                        if dataplane_result["errors"]:
                            click.echo(f"  Errors: {len(dataplane_result['errors'])}")
                        if dataplane_result["warnings"]:
                            click.echo(
                                f"  Warnings: {len(dataplane_result['warnings'])}"
                            )

                    except Exception as e:
                        click.echo(f"⚠️  Data plane replication failed: {e}", err=True)
                        click.echo(
                            "    Control plane deployment completed successfully."
                        )
            else:
                # Execute dataplane replication with environment variables
                from ..deployment.dataplane_orchestrator import (
                    ReplicationMode,
                    orchestrate_dataplane_replication,
                )

                try:
                    dataplane_result = orchestrate_dataplane_replication(
                        iac_dir=Path(iac_dir),
                        mode=ReplicationMode(dataplane),
                        source_tenant_id=source_tenant_id,
                        target_tenant_id=effective_tenant_id,
                        source_subscription_id=source_subscription_id,
                        target_subscription_id=subscription_id or "",
                        sp_client_id=sp_client_id,
                        sp_client_secret=sp_client_secret,
                    )

                    # Display dataplane results
                    click.echo(f"\nData plane replication {dataplane_result['status']}")
                    click.echo(
                        f"  Resources processed: {dataplane_result['resources_processed']}"
                    )
                    click.echo(
                        f"  Plugins executed: {', '.join(dataplane_result['plugins_executed']) or 'none'}"
                    )
                    if dataplane_result["errors"]:
                        click.echo(f"  Errors: {len(dataplane_result['errors'])}")
                    if dataplane_result["warnings"]:
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


def _parse_instance_filter(instance_filter: str | None) -> list[str] | None:
    """Parse instance filter specification.

    Args:
        instance_filter: Filter specification (e.g., "0,2,5" or "0-3")
            None means include all instances

    Returns:
        List of filter specifications, or None if no filter

    Examples:
        "0,2" → ["0", "2"]
        "0-3" → ["0-3"]
        None → None
    """
    if not instance_filter:
        return None

    # Return the filter string as-is for processing by replication_plan_converter
    # The converter already has logic to parse this format
    return [instance_filter]


def _get_neo4j_connection_info() -> tuple[str, str, str]:
    """Get Neo4j connection information from environment variables.

    Returns:
        Tuple of (uri, user, password)

    Raises:
        ValueError: If required environment variables are not set
    """
    # Get NEO4J_URI or construct from NEO4J_PORT
    neo4j_uri = os.environ.get("NEO4J_URI")
    if not neo4j_uri:
        neo4j_port = os.environ.get("NEO4J_PORT", "7687")
        neo4j_uri = f"bolt://localhost:{neo4j_port}"

    neo4j_user = os.environ.get("NEO4J_USER", "neo4j")
    neo4j_password = os.environ.get("NEO4J_PASSWORD")

    if not neo4j_password:
        raise ValueError("NEO4J_PASSWORD environment variable is required")

    return neo4j_uri, neo4j_user, neo4j_password


async def _deploy_from_replication_plan(
    target_tenant_id: str,
    resource_group: str,
    location: str,
    subscription_id: str | None,
    iac_format: str | None,
    dry_run: bool,
    pattern_filter: tuple[str, ...] | None,
    instance_filter: str | None,
) -> dict:
    """Orchestrate deployment from architecture-based replication plan.

    This function:
    1. Connects to source Neo4j (from docker container)
    2. Builds pattern graph from source tenant
    3. Generates replication plan
    4. Converts to TenantGraph
    5. Generates IaC
    6. Deploys to target tenant

    Args:
        target_tenant_id: Target Azure tenant ID
        resource_group: Target resource group name
        location: Azure region
        subscription_id: Optional Azure subscription ID
        iac_format: IaC format (terraform, bicep, arm) or None for auto-detect
        dry_run: If True, plan only without deployment
        pattern_filter: Optional pattern names to include
        instance_filter: Optional instance index filter

    Returns:
        Deployment result dictionary

    Raises:
        ValueError: If Neo4j connection info not available
        Exception: If deployment fails
    """
    click.echo("Starting architecture-based replication deployment...")

    # Step 1: Get Neo4j connection info
    try:
        neo4j_uri, neo4j_user, neo4j_password = _get_neo4j_connection_info()
        click.echo(f"Connecting to Neo4j at {neo4j_uri}...")
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise

    # Step 2: Build pattern graph from source tenant
    click.echo("Analyzing source tenant architectural patterns...")
    replicator = ArchitecturePatternReplicator(neo4j_uri, neo4j_user, neo4j_password)

    analysis_result = replicator.analyze_source_tenant(
        use_configuration_coherence=True,
        coherence_threshold=0.5,
        include_colocated_orphaned_resources=True,
    )

    click.echo(f"Found {analysis_result.get('detected_patterns', 0)} architectural patterns")

    # Step 3: Generate replication plan
    click.echo("Generating replication plan...")
    replication_plan = replicator.generate_replication_plan(
        target_instance_count=50,  # Default target size
        use_configuration_coherence=False,  # Already split in analysis
    )

    selected_instances, spectral_history, metadata = replication_plan
    total_instances = sum(len(instances) for _, instances in selected_instances)
    click.echo(f"Selected {total_instances} architecture instances for replication")

    # Step 4: Convert to TenantGraph
    click.echo("Converting replication plan to deployment graph...")

    # Connect to Neo4j for relationship queries
    driver = AsyncGraphDatabase.driver(
        neo4j_uri,
        auth=(neo4j_user, neo4j_password)
    )

    try:
        async with driver.session() as session:
            tenant_graph = await replication_plan_to_tenant_graph(
                replication_plan,
                session,
                pattern_filter=list(pattern_filter) if pattern_filter else None,
                instance_filter=instance_filter,
            )

        click.echo(
            f"Deployment graph: {len(tenant_graph.resources)} resources, "
            f"{len(tenant_graph.relationships)} relationships"
        )

        # Step 5: Generate IaC
        click.echo(f"Generating IaC ({iac_format or 'auto-detect'})...")

        # Create output directory
        output_dir = Path("./output/iac-from-replication")
        output_dir.mkdir(parents=True, exist_ok=True)

        # Select emitter based on format
        if iac_format == "terraform" or not iac_format:
            emitter = TerraformEmitter(
                target_tenant_id=target_tenant_id,
                resource_group_prefix=resource_group,
            )
            emitter.emit(
                graph=tenant_graph,
                out_dir=output_dir,
                location=location,
                subscription_id=subscription_id,
            )
            iac_dir = output_dir
        elif iac_format == "bicep":
            emitter = BicepEmitter(
                target_tenant_id=target_tenant_id,
                resource_group_prefix=resource_group,
            )
            emitter.emit(
                graph=tenant_graph,
                out_dir=output_dir,
                location=location,
                subscription_id=subscription_id,
            )
            iac_dir = output_dir
        elif iac_format == "arm":
            emitter = ArmEmitter(
                target_tenant_id=target_tenant_id,
                resource_group_prefix=resource_group,
            )
            emitter.emit(
                graph=tenant_graph,
                out_dir=output_dir,
                location=location,
                subscription_id=subscription_id,
            )
            iac_dir = output_dir
        else:
            raise ValueError(f"Unsupported IaC format: {iac_format}")

        click.echo(f"IaC generated in {iac_dir}")

        # Step 6: Deploy to target tenant
        if not dry_run:
            click.echo(f"Deploying to target tenant {target_tenant_id}...")

            result = deploy_iac(
                iac_dir=iac_dir,
                target_tenant_id=target_tenant_id,
                resource_group=resource_group,
                location=location,
                subscription_id=subscription_id,
                iac_format=cast(IaCFormat, iac_format) if iac_format else None,
                dry_run=dry_run,
            )

            return result
        else:
            click.echo("Dry-run mode: IaC generated, skipping deployment")
            return {
                "status": "dry-run",
                "format": iac_format or "terraform",
                "output": f"IaC generated in {iac_dir}",
            }

    finally:
        await driver.close()


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
