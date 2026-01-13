"""Terraform deployment operations.

This module handles Terraform-specific deployment operations including
initialization, planning, and applying infrastructure changes.

Philosophy:
- Single responsibility: Terraform deployments only
- Standard library focus where possible
- Self-contained and regeneratable
"""

import logging
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from src.timeout_config import Timeouts, log_timeout_event

if TYPE_CHECKING:
    from src.deployment.deployment_dashboard import DeploymentDashboard

logger = logging.getLogger(__name__)


def deploy_terraform(
    iac_dir: Path,
    resource_group: str,
    location: str,
    dry_run: bool = False,
    dashboard: Optional["DeploymentDashboard"] = None,
) -> dict:
    """Deploy Terraform IaC.

    Executes Terraform workflow: init -> plan (if dry_run) or apply.
    All output is streamed to the optional dashboard for real-time monitoring.

    Args:
        iac_dir: Directory containing Terraform files
        resource_group: Target resource group name (for context/logging)
        location: Azure region (for context/logging)
        dry_run: If True, only run plan without apply
        dashboard: Optional deployment dashboard for real-time updates

    Returns:
        Deployment result dictionary with:
            - status: 'planned' (dry_run) or 'deployed'
            - output: Command output string
            - format: 'terraform'

    Raises:
        RuntimeError: If terraform commands fail or timeout

    Example:
        >>> from pathlib import Path
        >>> result = deploy_terraform(
        ...     Path("/path/to/terraform"),
        ...     "my-rg",
        ...     "eastus",
        ...     dry_run=True
        ... )
        >>> result['status']
        'planned'
    """
    logger.info(str(f"Deploying Terraform from {iac_dir}"))

    # Initialize Terraform
    logger.debug("Running terraform init...")
    if dashboard is not None:
        dashboard.update_phase("init")
        dashboard.log_info("Initializing Terraform...")

    try:
        result = subprocess.run(
            ["terraform", "init"],
            cwd=iac_dir,
            capture_output=True,
            text=True,
            check=False,
            timeout=Timeouts.TERRAFORM_INIT,
        )
    except subprocess.TimeoutExpired as e:
        log_timeout_event(
            "terraform_init", Timeouts.TERRAFORM_INIT, ["terraform", "init"]
        )
        if dashboard is not None:
            dashboard.update_phase("failed")
            dashboard.add_error(
                f"Terraform init timed out after {Timeouts.TERRAFORM_INIT}s"
            )
        raise RuntimeError(
            f"Terraform init timed out after {Timeouts.TERRAFORM_INIT} seconds"
        ) from e

    if dashboard:
        for line in result.stdout.splitlines():
            dashboard.stream_terraform_output(line, level="info")
        if result.stderr:
            for line in result.stderr.splitlines():
                dashboard.stream_terraform_output(line, level="warning")

    if result.returncode != 0:
        if dashboard is not None:
            dashboard.update_phase("failed")
            dashboard.add_error(f"Terraform init failed: {result.stderr}")
        raise RuntimeError(f"Terraform init failed: {result.stderr}")

    if dry_run:
        # Plan only
        logger.info("Running terraform plan (dry-run mode)...")
        if dashboard is not None:
            dashboard.update_phase("plan")
            dashboard.log_info("Running terraform plan (dry-run)...")

        try:
            result = subprocess.run(
                ["terraform", "plan", "-input=false"],
                cwd=iac_dir,
                capture_output=True,
                text=True,
                check=False,
                timeout=Timeouts.TERRAFORM_PLAN,
            )
        except subprocess.TimeoutExpired as e:
            log_timeout_event(
                "terraform_plan", Timeouts.TERRAFORM_PLAN, ["terraform", "plan"]
            )
            if dashboard is not None:
                dashboard.update_phase("failed")
                dashboard.add_error(
                    f"Terraform plan timed out after {Timeouts.TERRAFORM_PLAN}s"
                )
            raise RuntimeError(
                f"Terraform plan timed out after {Timeouts.TERRAFORM_PLAN} seconds"
            ) from e

        if dashboard:
            for line in result.stdout.splitlines():
                dashboard.stream_terraform_output(line, level="info")
                # Parse resource counts from plan output
                if "Plan:" in line:
                    try:
                        # Example: "Plan: 5 to add, 0 to change, 0 to destroy."
                        parts = line.split("Plan:")[1].split(",")
                        to_add = int(parts[0].strip().split()[0])
                        dashboard.update_resource_counts(planned=to_add)
                    except Exception:
                        pass

        if result.returncode != 0:
            if dashboard is not None:
                dashboard.update_phase("failed")
                dashboard.add_error(f"Terraform plan failed: {result.stderr}")
            raise RuntimeError(f"Terraform plan failed: {result.stderr}")

        if dashboard is not None:
            dashboard.update_phase("complete")
            dashboard.log_info("Terraform plan completed successfully")

        return {
            "status": "planned",
            "output": result.stdout,
            "format": "terraform",
        }

    # Apply changes
    logger.info("Running terraform apply...")
    if dashboard is not None:
        dashboard.update_phase("apply")
        dashboard.log_info("Applying Terraform changes...")

    try:
        result = subprocess.run(
            ["terraform", "apply", "-auto-approve", "-input=false"],
            cwd=iac_dir,
            capture_output=True,
            text=True,
            check=False,
            timeout=Timeouts.TERRAFORM_APPLY,
        )
    except subprocess.TimeoutExpired as e:
        log_timeout_event(
            "terraform_apply", Timeouts.TERRAFORM_APPLY, ["terraform", "apply"]
        )
        if dashboard is not None:
            dashboard.update_phase("failed")
            dashboard.add_error(
                f"Terraform apply timed out after {Timeouts.TERRAFORM_APPLY}s"
            )
        raise RuntimeError(
            f"Terraform apply timed out after {Timeouts.TERRAFORM_APPLY} seconds"
        ) from e

    if dashboard:
        resources_applied = 0
        for line in result.stdout.splitlines():
            dashboard.stream_terraform_output(line, level="info")
            # Parse resource creation progress
            if "Creating..." in line or "Created" in line:
                resources_applied += 1
                dashboard.update_resource_counts(applied=resources_applied)
            elif "Apply complete!" in line:
                try:
                    # Example: "Apply complete! Resources: 5 added, 0 changed, 0 destroyed."
                    parts = line.split("Resources:")[1].split(",")
                    added = int(parts[0].strip().split()[0])
                    dashboard.update_resource_counts(applied=added)
                except Exception:
                    pass

        if result.stderr:
            for line in result.stderr.splitlines():
                dashboard.stream_terraform_output(line, level="warning")

    if result.returncode != 0:
        if dashboard is not None:
            dashboard.update_phase("failed")
            dashboard.add_error(f"Terraform apply failed: {result.stderr}")
        raise RuntimeError(f"Terraform apply failed: {result.stderr}")

    if dashboard is not None:
        dashboard.update_phase("complete")
        dashboard.log_info("Terraform apply completed successfully")
        dashboard.set_processing(False)

    return {
        "status": "deployed",
        "output": result.stdout,
        "format": "terraform",
    }


__all__ = ["deploy_terraform"]
