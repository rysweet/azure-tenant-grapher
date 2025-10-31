"""Terraform importer for handling pre-existing Azure resources.

This module provides functionality to import existing Azure resources into
Terraform state, solving authentication errors caused by pre-existing resources.

Design Goals:
- Detect existing Azure resources in target subscription
- Generate Terraform import commands
- Execute imports with proper error handling
- Support multiple import strategies (resource_groups, all_resources, selective)
- Provide detailed reporting of import operations
"""

import logging
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from azure.core.exceptions import AzureError
from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient

logger = logging.getLogger(__name__)


class ImportStrategy(Enum):
    """Strategy for determining which resources to import."""

    RESOURCE_GROUPS = "resource_groups"  # Only import resource groups
    ALL_RESOURCES = "all_resources"  # Import all detected resources
    SELECTIVE = "selective"  # Import based on conflict detection


@dataclass
class ImportCommand:
    """Represents a single Terraform import command."""

    resource_type: str
    terraform_address: str
    azure_resource_id: str
    resource_name: str

    def to_command(self) -> str:
        """Generate the terraform import command string."""
        return f"terraform import {self.terraform_address} {self.azure_resource_id}"


@dataclass
class ImportResult:
    """Result of executing a single import command."""

    command: ImportCommand
    success: bool
    stdout: str = ""
    stderr: str = ""
    error_message: Optional[str] = None

    @property
    def failed(self) -> bool:
        """Check if import failed."""
        return not self.success


@dataclass
class ImportReport:
    """Report of all import operations."""

    subscription_id: str
    strategy: ImportStrategy
    commands_generated: int = 0
    commands_executed: int = 0
    successes: int = 0
    failures: int = 0
    results: List[ImportResult] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    dry_run: bool = False

    def add_result(self, result: ImportResult) -> None:
        """Add import result to report."""
        self.results.append(result)
        self.commands_executed += 1
        if result.success:
            self.successes += 1
        else:
            self.failures += 1

    def format_report(self) -> str:
        """Generate human-readable import report."""
        lines = [
            "=" * 60,
            "Terraform Import Report",
            f"Subscription: {self.subscription_id}",
            f"Strategy: {self.strategy.value}",
            "=" * 60,
            "",
            f"Commands Generated: {self.commands_generated}",
            f"Commands Executed: {self.commands_executed}",
            f"Successful: {self.successes}",
            f"Failed: {self.failures}",
            "",
        ]

        if self.dry_run:
            lines.append("DRY RUN MODE - No commands were executed")
            lines.append("")

        if self.failures > 0:
            lines.append("FAILED IMPORTS:")
            lines.append("-" * 60)
            for result in self.results:
                if result.failed:
                    lines.append(f"  {result.command.terraform_address}")
                    if result.error_message:
                        lines.append(f"    Error: {result.error_message}")

        if self.warnings:
            lines.append("\nWARNINGS:")
            for warning in self.warnings:
                lines.append(f"  {warning}")

        return "\n".join(lines)


class TerraformImporter:
    """Handles importing existing Azure resources into Terraform state."""

    def __init__(
        self,
        subscription_id: str,
        terraform_dir: str,
        import_strategy: ImportStrategy = ImportStrategy.RESOURCE_GROUPS,
        credential: Optional[DefaultAzureCredential] = None,
        dry_run: bool = False,
    ):
        """Initialize Terraform importer.

        Args:
            subscription_id: Target Azure subscription ID
            terraform_dir: Directory containing Terraform configuration
            import_strategy: Strategy for determining what to import
            credential: Optional Azure credential (defaults to DefaultAzureCredential)
            dry_run: If True, generate commands but don't execute

        Raises:
            ValueError: If terraform_dir doesn't exist or invalid import_strategy
        """
        self.subscription_id = subscription_id
        self.terraform_dir = Path(terraform_dir)
        self.dry_run = dry_run

        # Validate inputs
        if not self.terraform_dir.exists():
            raise ValueError(f"Terraform directory does not exist: {terraform_dir}")

        if not isinstance(import_strategy, ImportStrategy):
            raise ValueError(f"Invalid import strategy: {import_strategy}")

        self.import_strategy = import_strategy
        self.credential = credential or DefaultAzureCredential()

        # Lazy-initialized client
        self._resource_client: Optional[ResourceManagementClient] = None

    @property
    def resource_client(self) -> ResourceManagementClient:
        """Lazy-initialized resource management client."""
        if self._resource_client is None:
            self._resource_client = ResourceManagementClient(
                self.credential, self.subscription_id
            )
        return self._resource_client

    async def detect_existing_resources(self) -> List[Dict[str, Any]]:
        """Detect existing Azure resources in subscription.

        Returns:
            List of resource dictionaries with type, name, id, etc.

        Raises:
            AzureError: If Azure API calls fail
        """
        logger.info(f"Detecting existing resources in subscription {self.subscription_id}")
        resources = []

        try:
            for resource in self.resource_client.resources.list():
                resource_dict = {
                    "type": resource.type,
                    "name": resource.name,
                    "id": resource.id,
                    "location": resource.location,
                }

                # Extract resource group from ID
                if "/resourceGroups/" in resource.id:
                    rg_name = resource.id.split("/resourceGroups/")[1].split("/")[0]
                    resource_dict["resource_group"] = rg_name

                resources.append(resource_dict)

            logger.info(f"Detected {len(resources)} existing resources")
            return resources

        except Exception as e:
            logger.error(f"Failed to detect existing resources: {e}")
            raise AzureError(f"Resource detection failed: {e}")

    def filter_resources_by_strategy(
        self, resources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Filter resources based on import strategy.

        Args:
            resources: All detected resources

        Returns:
            Filtered list of resources to import
        """
        if self.import_strategy == ImportStrategy.RESOURCE_GROUPS:
            # Only return resource groups
            return [
                r for r in resources if r["type"] == "Microsoft.Resources/resourceGroups"
            ]
        elif self.import_strategy == ImportStrategy.ALL_RESOURCES:
            # Return all resources
            return resources
        elif self.import_strategy == ImportStrategy.SELECTIVE:
            # This would integrate with ConflictDetector
            # For now, just return resource groups
            logger.warning("Selective strategy not fully implemented, using resource_groups")
            return [
                r for r in resources if r["type"] == "Microsoft.Resources/resourceGroups"
            ]
        else:
            return []

    def generate_import_commands(
        self, resources: List[Dict[str, Any]]
    ) -> List[ImportCommand]:
        """Generate Terraform import commands for resources.

        Args:
            resources: Resources to generate import commands for

        Returns:
            List of ImportCommand objects
        """
        commands = []
        terraform_config = self._load_terraform_config()

        for resource in resources:
            # Check if resource exists in Terraform config
            terraform_address = self._get_terraform_address(resource, terraform_config)
            if not terraform_address:
                logger.debug(f"Skipping {resource['name']} - not in Terraform config")
                continue

            command = ImportCommand(
                resource_type=resource["type"],
                terraform_address=terraform_address,
                azure_resource_id=resource["id"],
                resource_name=resource["name"],
            )
            commands.append(command)

        logger.info(f"Generated {len(commands)} import commands")
        return commands

    def _load_terraform_config(self) -> Dict[str, Any]:
        """Load Terraform configuration to find resource addresses.

        Returns:
            Dictionary mapping resource names to Terraform addresses
        """
        config = {}

        # Look for .tf files in terraform_dir
        for tf_file in self.terraform_dir.glob("*.tf"):
            try:
                content = tf_file.read_text()
                # Simple regex to find resource blocks
                # Format: resource "type" "name"
                pattern = r'resource\s+"([^"]+)"\s+"([^"]+)"'
                for match in re.finditer(pattern, content):
                    resource_type, resource_name = match.groups()
                    # Store mapping: resource_name -> terraform_type.terraform_name
                    config[resource_name] = f"{resource_type}.{resource_name}"
            except Exception as e:
                logger.warning(f"Failed to parse {tf_file}: {e}")

        return config

    def _get_terraform_address(
        self, resource: Dict[str, Any], terraform_config: Dict[str, Any]
    ) -> Optional[str]:
        """Get Terraform address for a resource.

        Args:
            resource: Azure resource dictionary
            terraform_config: Loaded Terraform configuration

        Returns:
            Terraform address (e.g., "azurerm_resource_group.main") or None
        """
        # Convert Azure resource name to Terraform-safe name
        tf_safe_name = self._to_terraform_name(resource["name"])

        # Check if resource exists in config
        if tf_safe_name in terraform_config:
            return terraform_config[tf_safe_name]

        # Try with underscores instead of hyphens
        alt_name = tf_safe_name.replace("-", "_")
        if alt_name in terraform_config:
            return terraform_config[alt_name]

        return None

    def _to_terraform_name(self, name: str) -> str:
        """Convert Azure resource name to Terraform-safe name.

        Args:
            name: Azure resource name

        Returns:
            Terraform-safe name (lowercase, alphanumeric and underscores only)
        """
        # Replace hyphens with underscores, remove non-alphanumeric
        safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
        return safe_name.lower()

    async def execute_import_commands(
        self, commands: List[ImportCommand]
    ) -> ImportReport:
        """Execute Terraform import commands.

        Args:
            commands: List of import commands to execute

        Returns:
            ImportReport with results of all imports
        """
        report = ImportReport(
            subscription_id=self.subscription_id,
            strategy=self.import_strategy,
            commands_generated=len(commands),
            dry_run=self.dry_run,
        )

        if self.dry_run:
            logger.info("DRY RUN: Would execute the following import commands:")
            for cmd in commands:
                logger.info(f"  {cmd.to_command()}")
            return report

        # Check Terraform is installed and initialized
        if not self._check_terraform_ready():
            report.warnings.append(
                "Terraform not ready. Run 'terraform init' first."
            )
            return report

        # Backup state before importing
        try:
            self._backup_terraform_state()
        except Exception as e:
            logger.warning(f"Failed to backup Terraform state: {e}")
            report.warnings.append(f"State backup failed: {e}")

        # Execute imports sequentially (Terraform doesn't support parallel imports)
        for command in commands:
            result = await self._execute_single_import(command)
            report.add_result(result)

            if result.success:
                logger.info(f"Successfully imported {command.terraform_address}")
            else:
                logger.error(
                    f"Failed to import {command.terraform_address}: {result.error_message}"
                )

        return report

    def _check_terraform_ready(self) -> bool:
        """Check if Terraform is installed and initialized.

        Returns:
            True if Terraform is ready, False otherwise
        """
        # Check Terraform is installed
        if not shutil.which("terraform"):
            logger.error("Terraform not found in PATH")
            return False

        # Check .terraform directory exists (indicates 'terraform init' was run)
        if not (self.terraform_dir / ".terraform").exists():
            logger.error("Terraform not initialized. Run 'terraform init' first.")
            return False

        return True

    def _backup_terraform_state(self) -> None:
        """Backup current Terraform state file.

        Raises:
            Exception: If backup fails
        """
        if self.dry_run:
            return

        state_file = self.terraform_dir / "terraform.tfstate"
        if not state_file.exists():
            logger.debug("No state file to backup")
            return

        # Create backup with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.terraform_dir / f"terraform.tfstate.backup.{timestamp}"

        shutil.copy2(state_file, backup_file)
        logger.info(f"Backed up Terraform state to {backup_file}")

    async def _execute_single_import(self, command: ImportCommand) -> ImportResult:
        """Execute a single Terraform import command.

        Args:
            command: Import command to execute

        Returns:
            ImportResult with execution details
        """
        try:
            # Run terraform import command
            process = subprocess.run(
                ["terraform", "import", command.terraform_address, command.azure_resource_id],
                cwd=self.terraform_dir,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            success = process.returncode == 0
            error_message = None

            if not success:
                error_message = process.stderr or f"Command failed with code {process.returncode}"

            return ImportResult(
                command=command,
                success=success,
                stdout=process.stdout,
                stderr=process.stderr,
                error_message=error_message,
            )

        except subprocess.TimeoutExpired:
            return ImportResult(
                command=command,
                success=False,
                error_message="Command timed out after 5 minutes",
            )
        except Exception as e:
            return ImportResult(
                command=command,
                success=False,
                error_message=f"Execution failed: {e}",
            )

    async def run_import(
        self, resources: Optional[List[Dict[str, Any]]] = None
    ) -> ImportReport:
        """Run full import workflow.

        Args:
            resources: Optional list of resources to import (auto-detects if not provided)

        Returns:
            ImportReport with results
        """
        # Detect resources if not provided
        if resources is None:
            try:
                resources = await self.detect_existing_resources()
            except AzureError as e:
                report = ImportReport(
                    subscription_id=self.subscription_id,
                    strategy=self.import_strategy,
                    dry_run=self.dry_run,
                )
                report.warnings.append(f"Resource detection failed: {e}")
                return report

        # Filter by strategy
        filtered_resources = self.filter_resources_by_strategy(resources)
        logger.info(
            f"Filtered to {len(filtered_resources)} resources based on {self.import_strategy.value} strategy"
        )

        # Generate import commands
        commands = self.generate_import_commands(filtered_resources)

        # Execute imports
        report = await self.execute_import_commands(commands)

        return report
