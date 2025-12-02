"""
Azure Sentinel and Log Analytics Automation (Issue #518)

This module provides automation for setting up Azure Sentinel and Log Analytics
workspaces with diagnostic settings for discovered resources.

Key Components:
- SentinelConfig: Configuration management with validation
- ResourceDiscovery: Resource discovery from Neo4j and Azure API
- SentinelSetupOrchestrator: Workflow orchestration for Sentinel setup

Philosophy:
- Modular design with clear responsibilities
- Idempotent operations (safe to re-run)
- Error handling with graceful fallbacks
- Zero-BS implementation (no stubs or placeholders)
"""

import json
import logging
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import click
from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient

logger = logging.getLogger(__name__)

# GUID validation pattern (Fix #4)
GUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


# ============================================================================
# Configuration Management
# ============================================================================


@dataclass
class SentinelConfig:
    """
    Configuration for Azure Sentinel and Log Analytics setup.

    Handles auto-generation of workspace names, validation of parameters,
    and conversion to environment dict for bash script execution.

    Philosophy:
    - Auto-generate sensible defaults from tenant/subscription IDs
    - Validate all inputs before execution
    - Convert to environment variables for bash interop
    """

    # Required fields
    tenant_id: str
    subscription_id: str

    # Workspace configuration (with defaults)
    workspace_name: Optional[str] = None
    resource_group: Optional[str] = None
    location: str = "eastus"
    retention_days: int = 90
    sku: str = "PerGB2018"

    # Sentinel configuration
    enable_sentinel: bool = True
    data_connectors: List[str] = field(
        default_factory=lambda: ["AzureActiveDirectory", "AzureActivity"]
    )
    content_packs: List[str] = field(default_factory=list)

    # Cross-tenant support
    target_tenant_id: Optional[str] = None

    # Execution options
    dry_run: bool = False
    strict_mode: bool = False
    skip_provider_check: bool = False

    # Supported SKUs
    VALID_SKUS = ["PerGB2018", "CapacityReservation", "Free"]

    def __post_init__(self):
        """Auto-generate workspace name and resource group if not provided."""
        if self.workspace_name is None:
            # Format: <first-8-chars-of-tenant>-sentinel-law-<location>
            tenant_short = self.tenant_id.split("-")[0]
            self.workspace_name = f"{tenant_short}-sentinel-law-{self.location}"

        if self.resource_group is None:
            # Format: sentinel-<location>-rg
            self.resource_group = f"sentinel-{self.location}-rg"

    def validate(self) -> None:
        """
        Validate configuration parameters.

        Raises:
            ValueError: If any validation fails
        """
        # Validate GUIDs (Fix #4)
        if not GUID_PATTERN.match(self.tenant_id):
            raise ValueError(
                f"Invalid tenant_id format (must be GUID): {self.tenant_id}"
            )

        if not GUID_PATTERN.match(self.subscription_id):
            raise ValueError(
                f"Invalid subscription_id format (must be GUID): {self.subscription_id}"
            )

        # Validate retention days
        if not (30 <= self.retention_days <= 730):
            raise ValueError(
                f"Retention days must be between 30 and 730, got {self.retention_days}"
            )

        # Validate SKU
        if self.sku not in self.VALID_SKUS:
            raise ValueError(
                f"Invalid SKU '{self.sku}'. Must be one of: {', '.join(self.VALID_SKUS)}"
            )

    def to_env_dict(self) -> Dict[str, str]:
        """
        Convert configuration to environment variable dictionary.

        Used to pass configuration to bash scripts via config.env file.

        Returns:
            Dictionary of environment variable names to values
        """
        return {
            "TENANT_ID": self.tenant_id,
            "AZURE_SUBSCRIPTION_ID": self.subscription_id,
            "WORKSPACE_NAME": self.workspace_name,
            "WORKSPACE_RESOURCE_GROUP": self.resource_group,
            "WORKSPACE_LOCATION": self.location,
            "WORKSPACE_RETENTION_DAYS": str(self.retention_days),
            "WORKSPACE_SKU": self.sku,
            "ENABLE_SENTINEL": "true" if self.enable_sentinel else "false",
            "DATA_CONNECTORS": ",".join(self.data_connectors),
            "CONTENT_PACKS": ",".join(self.content_packs),
            "TARGET_TENANT_ID": self.target_tenant_id or "",
            "DRY_RUN": "true" if self.dry_run else "false",
            "STRICT_MODE": "true" if self.strict_mode else "false",
            "SKIP_PROVIDER_CHECK": "true" if self.skip_provider_check else "false",
        }


# ============================================================================
# Resource Discovery
# ============================================================================


class ResourceDiscovery:
    """
    Discover Azure resources from Neo4j database or Azure API.

    Implements strategy pattern with fallback chain:
    1. Try Neo4j first (fast, uses existing graph data)
    2. Fall back to Azure API if Neo4j fails

    Philosophy:
    - Prefer Neo4j (already scanned, faster)
    - Graceful fallback to Azure API
    - Filter to supported resource types
    """

    # Supported resource types for diagnostic settings
    SUPPORTED_RESOURCE_TYPES = [
        "Microsoft.Compute/virtualMachines",
        "Microsoft.Network/networkSecurityGroups",
        "Microsoft.KeyVault/vaults",
        "Microsoft.Storage/storageAccounts",
        "Microsoft.Sql/servers",
        "Microsoft.Sql/servers/databases",
        "Microsoft.Network/applicationGateways",
        "Microsoft.Network/loadBalancers",
        "Microsoft.Network/publicIPAddresses",
        "Microsoft.Web/sites",
    ]

    def __init__(
        self,
        neo4j_driver=None,
        credential: Optional[DefaultAzureCredential] = None,
    ):
        """
        Initialize resource discovery.

        Args:
            neo4j_driver: Neo4j driver for graph queries (optional)
            credential: Azure credential for API access (optional)
        """
        self.neo4j_driver = neo4j_driver
        self.credential = credential

    async def discover_from_neo4j(
        self,
        subscription_id: str,
        resource_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Discover resources from Neo4j graph database.

        Queries abstracted Resource nodes (not Original nodes) to get
        cross-tenant compatible resource IDs.

        Args:
            subscription_id: Subscription ID to filter resources
            resource_types: Optional list of resource types to filter

        Returns:
            List of resource dictionaries with abstracted_id, type, name, location

        Raises:
            Exception: If Neo4j query fails
        """
        if not self.neo4j_driver:
            raise ValueError("Neo4j driver not provided")

        # Use supported types if not specified
        if resource_types is None:
            resource_types = self.SUPPORTED_RESOURCE_TYPES

        # Query abstracted Resource nodes
        query = """
        MATCH (r:Resource)
        WHERE r.abstracted_id CONTAINS $subscription_id
          AND r.type IN $resource_types
        RETURN r
        """

        with self.neo4j_driver.session() as session:
            result = session.run(
                query,
                subscription_id=subscription_id,
                resource_types=resource_types,
            )

            resources = []
            for record in result:
                resource_node = record["r"]
                resources.append(
                    {
                        "abstracted_id": resource_node.get("abstracted_id"),
                        "type": resource_node.get("type"),
                        "name": resource_node.get("name"),
                        "location": resource_node.get("location"),
                    }
                )

            return resources

    async def discover_from_azure_api(
        self,
        subscription_id: str,
        resource_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Discover resources from Azure API.

        Falls back to Azure API when Neo4j is unavailable.

        Args:
            subscription_id: Subscription ID to query
            resource_types: Optional list of resource types to filter

        Returns:
            List of resource dictionaries with id, type, name, location

        Raises:
            TimeoutError: If Azure API times out
        """
        if not self.credential:
            raise ValueError("Azure credential not provided")

        # Use supported types if not specified
        if resource_types is None:
            resource_types = self.SUPPORTED_RESOURCE_TYPES

        client = ResourceManagementClient(self.credential, subscription_id)

        # List all resources
        resources = []
        for resource in client.resources.list():
            # Filter to supported types
            if resource.type in resource_types:
                resources.append(
                    {
                        "id": resource.id,
                        "type": resource.type,
                        "name": resource.name,
                        "location": resource.location,
                    }
                )

        return resources

    async def discover(
        self,
        subscription_id: str,
        strategy: str = "neo4j_with_fallback",
        resource_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Discover resources using specified strategy.

        Strategies:
        - "neo4j_with_fallback": Try Neo4j first, fall back to Azure API
        - "neo4j_only": Neo4j only (fail if unavailable)
        - "azure_api_only": Azure API only

        Args:
            subscription_id: Subscription ID to query
            strategy: Discovery strategy to use
            resource_types: Optional list of resource types to filter

        Returns:
            List of discovered resources
        """
        if strategy == "neo4j_only":
            return await self.discover_from_neo4j(subscription_id, resource_types)

        elif strategy == "azure_api_only":
            return await self.discover_from_azure_api(subscription_id, resource_types)

        elif strategy == "neo4j_with_fallback":
            try:
                resources = await self.discover_from_neo4j(
                    subscription_id, resource_types
                )
                if resources:
                    logger.info(f"Discovered {len(resources)} resources from Neo4j")
                    return resources
                else:
                    logger.warning(
                        "Neo4j returned no resources, falling back to Azure API"
                    )
                    return await self.discover_from_azure_api(
                        subscription_id, resource_types
                    )
            except Exception as e:
                logger.warning(
                    f"Neo4j discovery failed: {e}, falling back to Azure API"
                )
                return await self.discover_from_azure_api(
                    subscription_id, resource_types
                )

        else:
            raise ValueError(f"Unknown discovery strategy: {strategy}")


# ============================================================================
# Orchestration
# ============================================================================


class SentinelSetupOrchestrator:
    """
    Orchestrate Sentinel setup workflow.

    Executes bash modules in sequence:
    1. Validate prerequisites
    2. Create Log Analytics workspace
    3. Enable Sentinel
    4. Configure data connectors
    5. Configure diagnostic settings

    Philosophy:
    - Each module is idempotent (safe to re-run)
    - Clear error messages with exit codes
    - Strict mode = fail-fast, non-strict = continue on error
    """

    def __init__(
        self,
        config: SentinelConfig,
        scripts_dir: Path,
        output_dir: Path,
    ):
        """
        Initialize orchestrator.

        Args:
            config: Sentinel configuration
            scripts_dir: Directory containing bash modules
            output_dir: Directory for output files
        """
        self.config = config
        self.scripts_dir = scripts_dir
        self.output_dir = output_dir

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def validate_prerequisites(self) -> bool:
        """
        Validate that all prerequisites are met.

        Checks:
        - Configuration is valid
        - All bash scripts exist and are executable
        - Output directory is writable

        Returns:
            True if all checks pass

        Raises:
            ValueError: If validation fails
        """
        # Validate configuration
        self.config.validate()

        # Check bash scripts exist and are executable (Fix #5)
        required_scripts = [
            "01-validate-prerequisites.sh",
            "02-create-workspace.sh",
            "03-enable-sentinel.sh",
            "04-configure-data-connectors.sh",
            "05-configure-diagnostics.sh",
            "lib/common.sh",
        ]

        for script_name in required_scripts:
            script_path = self.scripts_dir / script_name
            if not script_path.exists():
                raise ValueError(f"Required script not found: {script_path}")

            # Check executable permission (Fix #5)
            if not os.access(script_path, os.X_OK):
                raise ValueError(
                    f"Script is not executable: {script_path}. Run: chmod +x {script_path}"
                )

        # Check output directory is writable
        test_file = self.output_dir / ".write_test"
        try:
            test_file.write_text("test")
            test_file.unlink()
        except Exception as e:
            raise ValueError(f"Output directory not writable: {self.output_dir}: {e}") from e

        return True

    async def discover_resources(
        self,
        neo4j_driver=None,
        credential: Optional[DefaultAzureCredential] = None,
    ) -> List[Dict[str, Any]]:
        """
        Discover resources for diagnostic settings.

        Args:
            neo4j_driver: Optional Neo4j driver
            credential: Optional Azure credential

        Returns:
            List of discovered resources
        """
        discovery = ResourceDiscovery(
            neo4j_driver=neo4j_driver,
            credential=credential,
        )

        resources = await discovery.discover(
            subscription_id=self.config.subscription_id,
            strategy="neo4j_with_fallback",
        )

        # Write resources to JSON file for bash scripts
        resources_file = self.output_dir / "resources-list.json"
        resources_file.write_text(json.dumps(resources, indent=2))
        logger.info(f"Wrote {len(resources)} resources to {resources_file}")

        return resources

    def generate_config_env(self) -> Path:
        """
        Generate config.env file for bash scripts with secure permissions.

        Returns:
            Path to generated config.env file
        """
        config_env_path = self.output_dir / "config.env"

        env_dict = self.config.to_env_dict()
        env_lines = [f"{key}={value}" for key, value in env_dict.items()]

        config_env_path.write_text("\n".join(env_lines) + "\n")

        # Set secure permissions (Fix #3: owner read/write only)
        os.chmod(config_env_path, 0o600)

        logger.info(f"Generated config.env at {config_env_path} (permissions: 0600)")

        return config_env_path

    def execute_module(
        self,
        module_name: str,
        check_exit_code: bool = True,
    ) -> subprocess.CompletedProcess:
        """
        Execute a single bash module.

        Args:
            module_name: Name of module script (e.g., "01-validate-prerequisites.sh")
            check_exit_code: If True, raise exception on non-zero exit code

        Returns:
            CompletedProcess with result

        Raises:
            subprocess.CalledProcessError: If check_exit_code=True and module fails
            FileNotFoundError: If script not found
            PermissionError: If script not executable
            ValueError: If output directory is invalid
        """
        script_path = self.scripts_dir / module_name

        # Validate script exists and is executable (Fix #7)
        if not script_path.exists():
            raise FileNotFoundError(f"Bash module not found: {script_path}")

        if not os.access(script_path, os.X_OK):
            raise PermissionError(f"Bash module is not executable: {script_path}")

        # Validate output_dir is safe (Fix #7: security fix)
        output_dir_resolved = self.output_dir.resolve()
        if not output_dir_resolved.exists():
            raise ValueError(f"Output directory does not exist: {output_dir_resolved}")
        if not output_dir_resolved.is_dir():
            raise ValueError(f"Output path is not a directory: {output_dir_resolved}")

        # Build environment
        env = os.environ.copy()
        env["CONFIG_ENV_PATH"] = str(self.output_dir / "config.env")
        env["OUTPUT_DIR"] = str(output_dir_resolved)

        logger.info(f"Executing module: {module_name}")

        result = subprocess.run(
            ["bash", str(script_path)],
            cwd=output_dir_resolved,
            capture_output=True,
            text=True,
            timeout=600,
            check=check_exit_code,
            env=env,
        )

        if result.stdout:
            logger.info(f"Module output:\n{result.stdout}")

        if result.stderr:
            if result.returncode != 0:
                logger.error(f"Module errors:\n{result.stderr}")
            else:
                logger.warning(f"Module warnings:\n{result.stderr}")

        logger.info(
            f"Module {module_name} completed with exit code {result.returncode}"
        )

        return result

    async def execute_all_modules(
        self,
        neo4j_driver=None,
        credential: Optional[DefaultAzureCredential] = None,
    ) -> Dict[str, Any]:
        """
        Execute all Sentinel setup modules in sequence.

        Args:
            neo4j_driver: Optional Neo4j driver for resource discovery
            credential: Optional Azure credential

        Returns:
            Dictionary with execution results
        """
        results = {
            "success": False,
            "modules_executed": [],
            "modules_failed": [],
            "resources_configured": 0,
        }

        try:
            # Step 1: Validate prerequisites
            logger.info("Step 1/6: Validating prerequisites")
            self.validate_prerequisites()

            # Step 2: Generate config.env
            logger.info("Step 2/6: Generating configuration")
            self.generate_config_env()

            # Step 3: Discover resources
            logger.info("Step 3/6: Discovering resources")
            resources = await self.discover_resources(neo4j_driver, credential)
            results["resources_configured"] = len(resources)

            # Step 4-8: Execute bash modules
            modules = [
                "01-validate-prerequisites.sh",
                "02-create-workspace.sh",
                "03-enable-sentinel.sh",
                "04-configure-data-connectors.sh",
                "05-configure-diagnostics.sh",
            ]

            for i, module in enumerate(modules, start=4):
                logger.info(f"Step {i}/8: Executing {module}")

                try:
                    # In strict mode, fail-fast on any error
                    check_exit_code = self.config.strict_mode
                    result = self.execute_module(
                        module, check_exit_code=check_exit_code
                    )

                    if result.returncode == 0:
                        results["modules_executed"].append(module)
                    else:
                        results["modules_failed"].append(
                            {
                                "module": module,
                                "exit_code": result.returncode,
                                "stderr": result.stderr,
                            }
                        )

                        if self.config.strict_mode:
                            raise subprocess.CalledProcessError(
                                result.returncode,
                                module,
                                result.stdout,
                                result.stderr,
                            )

                except subprocess.CalledProcessError as e:
                    logger.error(f"Module {module} failed: {e}")
                    results["modules_failed"].append(
                        {
                            "module": module,
                            "exit_code": e.returncode,
                            "stderr": e.stderr,
                        }
                    )

                    if self.config.strict_mode:
                        raise

            # Success if all modules executed (or partial success in non-strict mode)
            results["success"] = len(results["modules_failed"]) == 0

        except Exception as e:
            logger.error(f"Sentinel setup failed: {e}")
            results["success"] = False
            results["error"] = str(e)

        return results


# ============================================================================
# CLI Command
# ============================================================================


@click.command(name="setup-sentinel")
@click.option(
    "--tenant-id",
    required=True,
    help="Azure tenant ID",
)
@click.option(
    "--subscription-id",
    required=True,
    help="Azure subscription ID",
)
@click.option(
    "--workspace-name",
    help="Log Analytics workspace name (auto-generated if not provided)",
)
@click.option(
    "--resource-group",
    help="Resource group for workspace (auto-generated if not provided)",
)
@click.option(
    "--location",
    default="eastus",
    help="Azure region (default: eastus)",
)
@click.option(
    "--retention-days",
    type=int,
    default=90,
    help="Log retention period in days (30-730, default: 90)",
)
@click.option(
    "--sku",
    default="PerGB2018",
    type=click.Choice(["PerGB2018", "CapacityReservation", "Free"]),
    help="Pricing tier (default: PerGB2018)",
)
@click.option(
    "--target-tenant-id",
    help="Target tenant ID for cross-tenant deployment",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview actions without making changes",
)
@click.option(
    "--strict-mode",
    is_flag=True,
    help="Fail fast on first error (default: continue on error)",
)
@click.option(
    "--skip-provider-check",
    is_flag=True,
    help="Skip Azure provider registration check",
)
@click.option(
    "--output-dir",
    type=click.Path(),
    default="./sentinel-output",
    help="Output directory for results (default: ./sentinel-output)",
)
def setup_sentinel_command(
    tenant_id: str,
    subscription_id: str,
    workspace_name: Optional[str],
    resource_group: Optional[str],
    location: str,
    retention_days: int,
    sku: str,
    target_tenant_id: Optional[str],
    dry_run: bool,
    strict_mode: bool,
    skip_provider_check: bool,
    output_dir: str,
):
    """
    Set up Azure Sentinel and Log Analytics with diagnostic settings.

    This command automates the complete Sentinel setup workflow:

    \b
    1. Validates prerequisites (Azure CLI, permissions)
    2. Creates Log Analytics workspace
    3. Enables Sentinel solution
    4. Configures data connectors
    5. Configures diagnostic settings for all resources

    Examples:

    \b
    # Basic setup (auto-generates workspace name)
    atg setup-sentinel --tenant-id <TENANT> --subscription-id <SUB>

    \b
    # Custom workspace name and location
    atg setup-sentinel --tenant-id <TENANT> --subscription-id <SUB> \\
        --workspace-name my-sentinel --location westus2

    \b
    # Cross-tenant deployment
    atg setup-sentinel --tenant-id <SOURCE> --subscription-id <SUB> \\
        --target-tenant-id <TARGET>

    \b
    # Dry run mode (preview only)
    atg setup-sentinel --tenant-id <TENANT> --subscription-id <SUB> --dry-run
    """
    import asyncio

    # Create configuration
    config = SentinelConfig(
        tenant_id=tenant_id,
        subscription_id=subscription_id,
        workspace_name=workspace_name,
        resource_group=resource_group,
        location=location,
        retention_days=retention_days,
        sku=sku,
        target_tenant_id=target_tenant_id,
        dry_run=dry_run,
        strict_mode=strict_mode,
        skip_provider_check=skip_provider_check,
    )

    # Determine scripts directory (relative to this file)
    current_file = Path(__file__)
    project_root = (
        current_file.parent.parent.parent
    )  # src/commands/sentinel.py -> project root
    scripts_dir = project_root / "scripts" / "sentinel"

    # Create output directory
    output_path = Path(output_dir)

    # Create orchestrator
    orchestrator = SentinelSetupOrchestrator(
        config=config,
        scripts_dir=scripts_dir,
        output_dir=output_path,
    )

    # Execute workflow
    click.echo("Setting up Azure Sentinel and Log Analytics...")
    click.echo(f"Workspace: {config.workspace_name}")
    click.echo(f"Location: {config.location}")
    click.echo(f"Resource Group: {config.resource_group}")

    if dry_run:
        click.echo("\n[DRY RUN MODE - No changes will be made]")

    try:
        # Run async workflow
        results = asyncio.run(orchestrator.execute_all_modules())

        # Display results
        click.echo("\n" + "=" * 60)
        if results["success"]:
            click.echo("✓ Sentinel setup completed successfully!")
            click.echo(f"  Modules executed: {len(results['modules_executed'])}")
            click.echo(f"  Resources configured: {results['resources_configured']}")
        else:
            click.echo("⚠ Sentinel setup completed with errors")
            click.echo(f"  Modules executed: {len(results['modules_executed'])}")
            click.echo(f"  Modules failed: {len(results['modules_failed'])}")

            if results["modules_failed"]:
                click.echo("\nFailed modules:")
                for failure in results["modules_failed"]:
                    click.echo(
                        f"  - {failure['module']}: exit code {failure['exit_code']}"
                    )

        click.echo("=" * 60)

        # Exit with appropriate code
        return 0 if results["success"] else 1

    except Exception as e:
        click.echo(f"\n✗ Sentinel setup failed: {e}", err=True)
        return 1
