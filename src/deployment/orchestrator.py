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
from src.exceptions import AzureAuthenticationError, AzureSubscriptionError
from src.timeout_config import Timeouts, log_timeout_event

if TYPE_CHECKING:
    from src.deployment.deployment_dashboard import DeploymentDashboard

logger = logging.getLogger(__name__)

# Re-export for backward compatibility
__all__ = [
    "IaCFormat",
    "deploy_arm",
    "deploy_bicep",
    "deploy_iac",
    "deploy_terraform",
    "detect_iac_format",
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
    sp_client_id: Optional[str] = None,
    sp_client_secret: Optional[str] = None,
    sp_tenant_id: Optional[str] = None,
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
        sp_client_id: Optional service principal client ID for headless auth
        sp_client_secret: Optional service principal client secret
        sp_tenant_id: Optional tenant ID for SP auth (defaults to target_tenant_id)

    Returns:
        Deployment result dictionary with status and output

    Raises:
        ValueError: If IaC format cannot be detected or is invalid
        AzureAuthenticationError: If Azure authentication fails
        AzureSubscriptionError: If subscription operations fail
        RuntimeError: If deployment fails
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
        raise AzureAuthenticationError(
            f"Azure account check timed out after {Timeouts.AZ_CLI_QUERY} seconds",
            tenant_id=target_tenant_id,
            context={"timeout_seconds": Timeouts.AZ_CLI_QUERY},
            cause=e,
        ) from e

    current_tenant = (
        current_tenant_result.stdout.strip()
        if current_tenant_result.returncode == 0
        else None
    )

    # Skip authentication if already authenticated to target tenant
    if current_tenant == target_tenant_id:
        logger.info(str(f"Already authenticated to target tenant {target_tenant_id}"))
    elif sp_client_id and sp_client_secret:
        # Service principal authentication (headless)
        sp_tenant = sp_tenant_id or target_tenant_id
        logger.info(f"Authenticating with service principal to tenant {sp_tenant}...")
        try:
            auth_result = subprocess.run(
                [
                    "az",
                    "login",
                    "--service-principal",
                    "-u",
                    sp_client_id,
                    "-p",
                    sp_client_secret,
                    "--tenant",
                    sp_tenant,
                    "--output",
                    "none",
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=Timeouts.STANDARD,
            )
        except subprocess.TimeoutExpired as e:
            log_timeout_event(
                "az_login_sp", Timeouts.STANDARD, ["az", "login", "--service-principal"]
            )
            raise RuntimeError(
                f"Service principal login timed out after {Timeouts.STANDARD} seconds"
            ) from e
        if auth_result.returncode != 0:
            raise RuntimeError(
                f"Service principal authentication failed: {auth_result.stderr}"
            )
    elif subscription_id:
        # Validate subscription belongs to target tenant before switching
        logger.info(
            f"Validating subscription {subscription_id} belongs to tenant {target_tenant_id}..."
        )
        try:
            sub_check_result = subprocess.run(
                [
                    "az",
                    "account",
                    "subscription",
                    "show",
                    "--subscription-id",
                    subscription_id,
                    "--query",
                    "tenantId",
                    "-o",
                    "tsv",
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=Timeouts.AZ_CLI_QUERY,
            )
        except subprocess.TimeoutExpired as e:
            log_timeout_event(
                "az_subscription_check",
                Timeouts.AZ_CLI_QUERY,
                ["az", "account", "subscription", "show"],
            )
            raise AzureSubscriptionError(
                f"Subscription validation timed out after {Timeouts.AZ_CLI_QUERY} seconds",
                subscription_id=subscription_id,
                context={
                    "timeout_seconds": Timeouts.AZ_CLI_QUERY,
                    "tenant_id": target_tenant_id,
                },
                cause=e,
            ) from e

        sub_tenant = None
        if sub_check_result.returncode == 0:
            sub_tenant = sub_check_result.stdout.strip()
            if sub_tenant != target_tenant_id:
                logger.warning(
                    f"Subscription {subscription_id} belongs to tenant {sub_tenant}, "
                    f"not target tenant {target_tenant_id}. Skipping subscription switch."
                )
                # Skip subscription switch, go directly to login
                logger.info("Attempting interactive login...")
                try:
                    auth_result = subprocess.run(
                        [
                            "az",
                            "login",
                            "--tenant",
                            target_tenant_id,
                            "--output",
                            "none",
                        ],
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=Timeouts.STANDARD,
                    )
                except subprocess.TimeoutExpired as e:
                    log_timeout_event("az_login", Timeouts.STANDARD, ["az", "login"])
                    raise AzureAuthenticationError(
                        f"Azure login timed out after {Timeouts.STANDARD} seconds",
                        tenant_id=target_tenant_id,
                        context={"timeout_seconds": Timeouts.STANDARD},
                        cause=e,
                    ) from e
                if auth_result.returncode != 0:
                    raise AzureAuthenticationError(
                        f"Azure login failed: {auth_result.stderr}",
                        tenant_id=target_tenant_id,
                    )
            else:
                # Subscription belongs to target tenant, proceed with switch
                logger.info(
                    f"Subscription validated. Switching to subscription {subscription_id}..."
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
                        "az_account_set",
                        Timeouts.AZ_CLI_QUERY,
                        ["az", "account", "set"],
                    )
                    raise AzureSubscriptionError(
                        f"Azure subscription switch timed out after {Timeouts.AZ_CLI_QUERY} seconds",
                        subscription_id=subscription_id,
                        context={
                            "timeout_seconds": Timeouts.AZ_CLI_QUERY,
                            "tenant_id": target_tenant_id,
                        },
                        cause=e,
                    ) from e

                if switch_result.returncode != 0:
                    logger.warning(
                        str(f"Subscription switch failed: {switch_result.stderr}")
                    )
                    logger.info("Attempting interactive login...")
                    try:
                        auth_result = subprocess.run(
                            [
                                "az",
                                "login",
                                "--tenant",
                                target_tenant_id,
                                "--output",
                                "none",
                            ],
                            capture_output=True,
                            text=True,
                            check=False,
                            timeout=Timeouts.STANDARD,
                        )
                    except subprocess.TimeoutExpired as e:
                        log_timeout_event(
                            "az_login", Timeouts.STANDARD, ["az", "login"]
                        )
                        raise AzureAuthenticationError(
                            f"Azure login timed out after {Timeouts.STANDARD} seconds",
                            tenant_id=target_tenant_id,
                            context={"timeout_seconds": Timeouts.STANDARD},
                            cause=e,
                        ) from e
                    if auth_result.returncode != 0:
                        raise AzureAuthenticationError(
                            f"Azure login failed: {auth_result.stderr}",
                            tenant_id=target_tenant_id,
                        )
        else:
            # Cannot validate subscription, log warning and attempt switch anyway
            logger.warning(
                f"Cannot validate subscription {subscription_id}: {sub_check_result.stderr}. "
                f"Attempting subscription switch anyway..."
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
                raise AzureSubscriptionError(
                    f"Azure subscription switch timed out after {Timeouts.AZ_CLI_QUERY} seconds",
                    subscription_id=subscription_id,
                    context={
                        "timeout_seconds": Timeouts.AZ_CLI_QUERY,
                        "tenant_id": target_tenant_id,
                    },
                    cause=e,
                ) from e

            if switch_result.returncode != 0:
                logger.warning(
                    str(f"Subscription switch failed: {switch_result.stderr}")
                )
                logger.info("Attempting interactive login...")
                try:
                    auth_result = subprocess.run(
                        [
                            "az",
                            "login",
                            "--tenant",
                            target_tenant_id,
                            "--output",
                            "none",
                        ],
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=Timeouts.STANDARD,
                    )
                except subprocess.TimeoutExpired as e:
                    log_timeout_event("az_login", Timeouts.STANDARD, ["az", "login"])
                    raise AzureAuthenticationError(
                        f"Azure login timed out after {Timeouts.STANDARD} seconds",
                        tenant_id=target_tenant_id,
                        context={"timeout_seconds": Timeouts.STANDARD},
                        cause=e,
                    ) from e
                if auth_result.returncode != 0:
                    raise AzureAuthenticationError(
                        f"Azure login failed: {auth_result.stderr}",
                        tenant_id=target_tenant_id,
                    )
    else:
        # No subscription ID provided, attempt login
        logger.info(str(f"Authenticating to tenant {target_tenant_id}..."))
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
            raise AzureAuthenticationError(
                f"Azure login timed out after {Timeouts.STANDARD} seconds",
                tenant_id=target_tenant_id,
                context={"timeout_seconds": Timeouts.STANDARD},
                cause=e,
            ) from e
        if auth_result.returncode != 0:
            logger.warning(str(f"Azure login may have failed: {auth_result.stderr}"))
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
