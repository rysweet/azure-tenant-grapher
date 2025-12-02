"""Bicep deployment operations.

This module handles Bicep-specific deployment operations including
validation and deployment of Bicep templates to Azure.

Philosophy:
- Single responsibility: Bicep deployments only
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


def deploy_bicep(
    iac_dir: Path,
    resource_group: str,
    location: str,
    subscription_id: Optional[str] = None,
    dry_run: bool = False,
    dashboard: Optional["DeploymentDashboard"] = None,
) -> dict:
    """Deploy Bicep IaC.

    Executes Bicep workflow: find template -> validate (if dry_run) or deploy.
    All output is streamed to the optional dashboard for real-time monitoring.

    Args:
        iac_dir: Directory containing Bicep files
        resource_group: Target resource group name
        location: Azure region (for context/logging)
        subscription_id: Optional Azure subscription ID
        dry_run: If True, only validate without deploying
        dashboard: Optional deployment dashboard for real-time updates

    Returns:
        Deployment result dictionary with:
            - status: 'validated' (dry_run) or 'deployed'
            - output: Command output string
            - format: 'bicep'

    Raises:
        RuntimeError: If bicep/az commands fail or timeout

    Example:
        >>> from pathlib import Path
        >>> result = deploy_bicep(
        ...     Path("/path/to/bicep"),
        ...     "my-rg",
        ...     "eastus",
        ...     dry_run=True
        ... )
        >>> result['status']
        'validated'
    """
    logger.info(f"Deploying Bicep from {iac_dir}")

    if dashboard:
        dashboard.update_phase("init")
        dashboard.log_info("Finding Bicep template...")

    # Find main bicep file (look for main.bicep or first .bicep file)
    bicep_files = list(iac_dir.glob("*.bicep"))
    if not bicep_files:
        if dashboard:
            dashboard.update_phase("failed")
            dashboard.add_error(f"No Bicep files found in {iac_dir}")
        raise RuntimeError(f"No Bicep files found in {iac_dir}")

    main_file = next((f for f in bicep_files if f.name == "main.bicep"), bicep_files[0])

    if dry_run:
        # Validate only
        logger.info(f"Validating Bicep template {main_file.name}...")
        if dashboard:
            dashboard.update_phase("plan")
            dashboard.log_info(f"Validating Bicep template {main_file.name}...")

        cmd = [
            "az",
            "deployment",
            "group",
            "validate",
            "--resource-group",
            resource_group,
            "--template-file",
            str(main_file),
        ]
        if subscription_id:
            cmd.extend(["--subscription", subscription_id])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=Timeouts.BICEP_VALIDATE,
            )
        except subprocess.TimeoutExpired as e:
            log_timeout_event("bicep_validate", Timeouts.BICEP_VALIDATE, cmd)
            if dashboard:
                dashboard.update_phase("failed")
                dashboard.add_error(
                    f"Bicep validation timed out after {Timeouts.BICEP_VALIDATE}s"
                )
            raise RuntimeError(
                f"Bicep validation timed out after {Timeouts.BICEP_VALIDATE} seconds"
            ) from e

        if dashboard:
            for line in result.stdout.splitlines():
                dashboard.stream_terraform_output(line, level="info")
            if result.stderr:
                for line in result.stderr.splitlines():
                    dashboard.stream_terraform_output(line, level="warning")

        if result.returncode != 0:
            if dashboard:
                dashboard.update_phase("failed")
                dashboard.add_error(f"Bicep validation failed: {result.stderr}")
            raise RuntimeError(f"Bicep validation failed: {result.stderr}")

        if dashboard:
            dashboard.update_phase("complete")
            dashboard.log_info("Bicep validation completed successfully")

        return {
            "status": "validated",
            "output": result.stdout,
            "format": "bicep",
        }

    # Deploy
    logger.info(f"Deploying Bicep template {main_file.name}...")
    if dashboard:
        dashboard.update_phase("apply")
        dashboard.log_info(f"Deploying Bicep template {main_file.name}...")

    cmd = [
        "az",
        "deployment",
        "group",
        "create",
        "--resource-group",
        resource_group,
        "--template-file",
        str(main_file),
    ]
    if subscription_id:
        cmd.extend(["--subscription", subscription_id])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=Timeouts.BICEP_DEPLOY,
        )
    except subprocess.TimeoutExpired as e:
        log_timeout_event("bicep_deploy", Timeouts.BICEP_DEPLOY, cmd)
        if dashboard:
            dashboard.update_phase("failed")
            dashboard.add_error(
                f"Bicep deployment timed out after {Timeouts.BICEP_DEPLOY}s"
            )
        raise RuntimeError(
            f"Bicep deployment timed out after {Timeouts.BICEP_DEPLOY} seconds"
        ) from e

    if dashboard:
        for line in result.stdout.splitlines():
            dashboard.stream_terraform_output(line, level="info")
        if result.stderr:
            for line in result.stderr.splitlines():
                dashboard.stream_terraform_output(line, level="warning")

    if result.returncode != 0:
        if dashboard:
            dashboard.update_phase("failed")
            dashboard.add_error(f"Bicep deployment failed: {result.stderr}")
        raise RuntimeError(f"Bicep deployment failed: {result.stderr}")

    if dashboard:
        dashboard.update_phase("complete")
        dashboard.log_info("Bicep deployment completed successfully")
        dashboard.set_processing(False)

    return {
        "status": "deployed",
        "output": result.stdout,
        "format": "bicep",
    }


__all__ = ["deploy_bicep"]
