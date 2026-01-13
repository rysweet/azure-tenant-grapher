"""Terraform destroyer for safe resource cleanup.

This module provides safe wrapping of terraform destroy operations
with proper error handling and state management.
"""

import asyncio
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class TerraformDestroyer:
    """Manages safe Terraform resource destruction."""

    def __init__(self, working_dir: Path, tenant_config: Dict[str, str]):
        """Initialize the Terraform destroyer.

        Args:
            working_dir: Directory containing Terraform files
            tenant_config: Azure tenant configuration with credentials
        """
        self.working_dir = Path(working_dir)
        self.tenant_config = tenant_config

        # Verify working directory exists
        if not self.working_dir.exists():
            raise ValueError(f"Working directory {working_dir} does not exist")

        # Verify terraform.tfstate exists
        self.state_file = self.working_dir / "terraform.tfstate"
        if not self.state_file.exists():
            raise ValueError(f"Terraform state file not found in {working_dir}")

    def _get_environment(self) -> Dict[str, str]:
        """Get environment variables with Azure credentials.

        Returns:
            Environment dictionary with Azure credentials
        """
        env = os.environ.copy()

        # Set Azure credentials based on tenant config
        if "client_id" in self.tenant_config:
            env["ARM_CLIENT_ID"] = self.tenant_config["client_id"]
        if "client_secret" in self.tenant_config:
            env["ARM_CLIENT_SECRET"] = self.tenant_config["client_secret"]
        if "tenant_id" in self.tenant_config:
            env["ARM_TENANT_ID"] = self.tenant_config["tenant_id"]
        if "subscription_id" in self.tenant_config:
            env["ARM_SUBSCRIPTION_ID"] = self.tenant_config["subscription_id"]

        return env

    async def get_resources_to_destroy(self) -> List[Dict[str, Any]]:
        """Get list of resources that will be destroyed.

        Returns:
            List of resources from terraform state
        """
        try:
            # Use terraform show to get current state
            result = await self._run_terraform_command(["show", "-json"])
            if result[0] != 0:
                logger.error(str(f"Failed to get terraform state: {result[2]}"))
                return []

            state_data = json.loads(result[1])
            resources = []

            # Extract resources from state
            if "values" in state_data and "root_module" in state_data["values"]:
                root_module = state_data["values"]["root_module"]
                if "resources" in root_module:
                    for resource in root_module["resources"]:
                        resources.append(
                            {
                                "type": resource.get("type", "unknown"),
                                "name": resource.get("name", "unknown"),
                                "provider": resource.get("provider_name", "unknown"),
                                "id": resource.get("values", {}).get("id", "unknown"),
                            }
                        )

            return resources

        except Exception as e:
            logger.error(str(f"Failed to parse terraform state: {e}"))
            return []

    async def plan_destroy(self) -> Tuple[int, str, str]:
        """Run terraform plan -destroy to preview destruction.

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        return await self._run_terraform_command(["plan", "-destroy", "-no-color"])

    async def destroy(
        self, auto_approve: bool = False, timeout: int = 300
    ) -> Tuple[int, str, str]:
        """Execute terraform destroy.

        Args:
            auto_approve: Skip interactive approval
            timeout: Command timeout in seconds

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        cmd = ["destroy", "-no-color"]

        if auto_approve:
            cmd.append("-auto-approve")

        logger.info(str(f"Executing terraform destroy in {self.working_dir}"))
        return await self._run_terraform_command(cmd, timeout=timeout)

    async def _run_terraform_command(
        self, args: List[str], timeout: int = 60
    ) -> Tuple[int, str, str]:
        """Run a terraform command.

        Args:
            args: Terraform command arguments
            timeout: Command timeout in seconds

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        cmd = ["terraform", *args]
        env = self._get_environment()

        logger.debug(f"Running command: {' '.join(cmd)}")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=self.working_dir,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return (1, "", "Command timed out")

            return (
                process.returncode or 0,
                stdout.decode("utf-8") if stdout else "",
                stderr.decode("utf-8") if stderr else "",
            )

        except Exception as e:
            logger.error(str(f"Failed to run terraform command: {e}"))
            return (1, "", str(e))

    def check_terraform_installed(self) -> bool:
        """Check if terraform is installed and accessible.

        Returns:
            True if terraform is installed, False otherwise
        """
        try:
            result = subprocess.run(
                ["terraform", "version"], capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def get_terraform_version(self) -> Optional[str]:
        """Get the installed terraform version.

        Returns:
            Version string or None if not found
        """
        try:
            result = subprocess.run(
                ["terraform", "version", "-json"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                version_data = json.loads(result.stdout)
                return version_data.get("terraform_version", "unknown")
        except Exception:
            pass

        return None


class UndeploymentConfirmation:
    """Manages the confirmation flow for safe undeployment."""

    def __init__(self, deployment: Dict[str, Any], tenant: str):
        """Initialize confirmation handler.

        Args:
            deployment: Deployment record
            tenant: Target tenant for destruction
        """
        self.deployment = deployment
        self.tenant = tenant

    def verify_deployment_active(self) -> bool:
        """Verify the deployment is active and can be destroyed.

        Returns:
            True if deployment can be destroyed
        """
        if self.deployment["status"] != "active":
            print(
                f"⚠️  Deployment status is '{self.deployment['status']}', not 'active'"
            )
            if self.deployment["status"] == "destroyed":
                print("This deployment has already been destroyed.")
                return False
            elif self.deployment["status"] == "failed":
                print(
                    "This deployment is in a failed state. Manual cleanup may be required."
                )
                # Allow destruction attempt for failed deployments
                return True
        return True

    def show_resources_preview(self, resources: List[Dict[str, Any]]) -> None:
        """Show preview of resources to be destroyed.

        Args:
            resources: List of resources that will be destroyed
        """
        print("\n" + "=" * 60)
        print("🗑️  RESOURCES TO BE DESTROYED")
        print("=" * 60)

        if not resources:
            print("No resources found in state file.")
            return

        # Group resources by type
        by_type = {}
        for resource in resources:
            rtype = resource["type"]
            if rtype not in by_type:
                by_type[rtype] = []
            by_type[rtype].append(resource["name"])

        # Display grouped resources
        for rtype, names in sorted(by_type.items()):
            print(str(f"\n{rtype}:"))
            for name in names:
                print(str(f"  - {name}"))

        print(str(f"\nTotal: {len(resources)} resources"))
        print("=" * 60)

    def confirm_tenant(self) -> bool:
        """Confirm the correct tenant is selected.

        Returns:
            True if confirmed
        """
        print(str(f"\n⚠️  Target Tenant: {self.tenant}"))
        print(f"   Deployment Tenant: {self.deployment['tenant']}")

        if self.tenant != self.deployment["tenant"]:
            print("\n❌ ERROR: Tenant mismatch!")
            print("The selected tenant does not match the deployment tenant.")
            return False

        response = input("\nIs this the correct tenant? (yes/no): ").strip().lower()
        return response in ["yes", "y"]

    def get_typed_confirmation(self) -> bool:
        """Require user to type deployment ID for confirmation.

        Returns:
            True if correctly typed
        """
        print(
            f"\n⚠️  To confirm destruction, type the deployment ID: {self.deployment['id']}"
        )
        typed = input("Deployment ID: ").strip()

        if typed != self.deployment["id"]:
            print("❌ Deployment ID does not match. Aborting.")
            return False

        return True

    def final_confirmation(self) -> bool:
        """Final Y/N confirmation.

        Returns:
            True if confirmed
        """
        print("\n" + "!" * 60)
        print("⚠️  FINAL WARNING: This action cannot be undone!")
        print("!" * 60)

        response = input("\nProceed with destruction? (yes/no): ").strip().lower()
        return response in ["yes", "y"]
