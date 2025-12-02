"""Deployment orchestration for IaC templates.

This module provides a thin facade for orchestrating Infrastructure as Code
deployments across multiple formats (Terraform, Bicep, ARM). It handles
authentication and delegates format-specific logic to specialized deployers.

Philosophy:
- Thin facade: Authentication + routing only
- Format-specific logic delegated to specialized deployers
- Self-contained and regeneratable
"""

import logging
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from src.deployment.arm_deployer import deploy_arm
from src.deployment.bicep_deployer import deploy_bicep
from src.deployment.format_detector import IaCFormat, detect_iac_format
from src.deployment.terraform_deployer import deploy_terraform
from src.timeout_config import Timeouts, log_timeout_event

if TYPE_CHECKING:
    from src.deployment.deployment_dashboard import DeploymentDashboard

logger = logging.getLogger(__name__)

# Re-export for backward compatibility
__all__ = [
    "deploy_iac",
    "deploy_terraform",
    "deploy_bicep",
    "deploy_arm",
    "detect_iac_format",
    "IaCFormat",
]


def deploy_iac(
    iac_dir: Path,
    target_tenant_id: str,
    resource_group: str,
    location: str = "eastus",
    subscription_id: Optional[str] = None,
    iac_format: Optional[IaCFormat] = None,
    dry_run: bool = False,
    dashboard: Optional["DeploymentDashboard"] = None,
) -> dict:
    """Deploy IaC to target tenant.

    Args:
        iac_dir: Directory containing IaC files
        target_tenant_id: Target Azure tenant ID
        resource_group: Target resource group name
        location: Azure region (default: eastus)
        subscription_id: Optional subscription ID for bicep/arm deployments
        iac_format: IaC format (auto-detected if None)
        dry_run: If True, plan/validate only without deploying
        dashboard: Optional deployment dashboard for real-time updates

    Returns:
        Deployment result dictionary with status and output

    Raises:
        ValueError: If IaC format cannot be detected or is invalid
        RuntimeError: If authentication or deployment fails
    """
    # Auto-detect format if not specified
    if not iac_format:
        iac_format = detect_iac_format(iac_dir)
        if not iac_format:
            raise ValueError(f"Could not detect IaC format in {iac_dir}")

    logger.info(
        f"Deploying {iac_format} to tenant {target_tenant_id}, RG {resource_group}"
    )

    # Smart tenant authentication handling
    # Check current authentication status
    try:
        current_tenant_result = subprocess.run(
            ["az", "account", "show", "--query", "tenantId", "-o", "tsv"],
            capture_output=True,
            text=True,
            check=False,
            timeout=Timeouts.AZ_CLI_QUERY,
        )
    except subprocess.TimeoutExpired as e:
        log_timeout_event(
            "az_account_show", Timeouts.AZ_CLI_QUERY, ["az", "account", "show"]
        )
        raise RuntimeError(
            f"Azure account check timed out after {Timeouts.AZ_CLI_QUERY} seconds"
        ) from e

    current_tenant = (
        current_tenant_result.stdout.strip()
        if current_tenant_result.returncode == 0
        else None
    )

    if current_tenant == target_tenant_id:
        logger.info(f"Already authenticated to target tenant {target_tenant_id}")
    elif subscription_id:
        # Try switching subscription (works for multi-tenant users)
        logger.info(
            f"Switching to subscription {subscription_id} in tenant {target_tenant_id}..."
        )
        try:
            switch_result = subprocess.run(
                ["az", "account", "set", "--subscription", subscription_id],
                capture_output=True,
                text=True,
                check=False,
                timeout=Timeouts.AZ_CLI_QUERY,
            )
        except subprocess.TimeoutExpired as e:
            log_timeout_event(
                "az_account_set", Timeouts.AZ_CLI_QUERY, ["az", "account", "set"]
            )
            raise RuntimeError(
                f"Azure subscription switch timed out after {Timeouts.AZ_CLI_QUERY} seconds"
            ) from e

        if switch_result.returncode != 0:
            logger.warning(f"Subscription switch failed: {switch_result.stderr}")
            logger.info("Attempting interactive login...")
            try:
                auth_result = subprocess.run(
                    ["az", "login", "--tenant", target_tenant_id, "--output", "none"],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=Timeouts.STANDARD,
                )
            except subprocess.TimeoutExpired as e:
                log_timeout_event("az_login", Timeouts.STANDARD, ["az", "login"])
                raise RuntimeError(
                    f"Azure login timed out after {Timeouts.STANDARD} seconds"
                ) from e
            if auth_result.returncode != 0:
                raise RuntimeError(f"Azure login failed: {auth_result.stderr}")
    else:
        # No subscription ID provided, attempt login
        logger.info(f"Authenticating to tenant {target_tenant_id}...")
        try:
            auth_result = subprocess.run(
                ["az", "login", "--tenant", target_tenant_id, "--output", "none"],
                capture_output=True,
                text=True,
                check=False,
                timeout=Timeouts.STANDARD,
            )
        except subprocess.TimeoutExpired as e:
            log_timeout_event("az_login", Timeouts.STANDARD, ["az", "login"])
            raise RuntimeError(
                f"Azure login timed out after {Timeouts.STANDARD} seconds"
            ) from e
        if auth_result.returncode != 0:
            logger.warning(f"Azure login may have failed: {auth_result.stderr}")
            # Don't raise - may already be authenticated

    # Deploy based on format
    if iac_format == "terraform":
        return deploy_terraform(iac_dir, resource_group, location, dry_run, dashboard)
    elif iac_format == "bicep":
        return deploy_bicep(
            iac_dir, resource_group, location, subscription_id, dry_run, dashboard
        )
    elif iac_format == "arm":
        return deploy_arm(
            iac_dir, resource_group, location, subscription_id, dry_run, dashboard
        )
    else:
        raise ValueError(f"Unsupported IaC format: {iac_format}")
