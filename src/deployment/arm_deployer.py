"""ARM template deployment operations.

This module handles ARM (Azure Resource Manager) template deployment operations
including validation and deployment to Azure.

Philosophy:
- Single responsibility: ARM template deployments only
- Standard library focus where possible
- Self-contained and regeneratable
"""

import json
import logging
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from src.timeout_config import Timeouts, log_timeout_event

if TYPE_CHECKING:
    from src.deployment.deployment_dashboard import DeploymentDashboard

logger = logging.getLogger(__name__)


def deploy_arm(
    iac_dir: Path,
    resource_group: str,
    location: str,
    subscription_id: Optional[str] = None,
    dry_run: bool = False,
    dashboard: Optional["DeploymentDashboard"] = None,
) -> dict:
    """Deploy ARM template IaC.

    Executes ARM workflow: find template -> validate (if dry_run) or deploy.
    All output is streamed to the optional dashboard for real-time monitoring.

    Args:
        iac_dir: Directory containing ARM template files
        resource_group: Target resource group name
        location: Azure region (for context/logging)
        subscription_id: Optional Azure subscription ID
        dry_run: If True, only validate without deploying
        dashboard: Optional deployment dashboard for real-time updates

    Returns:
        Deployment result dictionary with:
            - status: 'validated' (dry_run) or 'deployed'
            - output: Command output string
            - format: 'arm'

    Raises:
        RuntimeError: If az commands fail or timeout

    Example:
        >>> from pathlib import Path
        >>> result = deploy_arm(
        ...     Path("/path/to/arm"),
        ...     "my-rg",
        ...     "eastus",
        ...     dry_run=True
        ... )
        >>> result['status']
        'validated'
    """
    logger.info(str(f"Deploying ARM template from {iac_dir}"))

    if dashboard is not None:
        dashboard.update_phase("init")
        dashboard.log_info("Finding ARM template...")

    # Find ARM template file
    arm_files = []
    for json_file in iac_dir.glob("*.json"):
        try:
            with open(json_file) as f:
                data = json.load(f)
                if "$schema" in data and "deploymentTemplate" in data.get(
                    "$schema", ""
                ):
                    arm_files.append(json_file)
        except Exception:
            continue

    if not arm_files:
        if dashboard is not None:
            dashboard.update_phase("failed")
            dashboard.add_error(f"No ARM template files found in {iac_dir}")
        raise RuntimeError(f"No ARM template files found in {iac_dir}")

    template_file = arm_files[0]

    if dry_run:
        # Validate only
        logger.info(str(f"Validating ARM template {template_file.name}..."))
        if dashboard is not None:
            dashboard.update_phase("plan")
            dashboard.log_info(f"Validating ARM template {template_file.name}...")

        cmd = [
            "az",
            "deployment",
            "group",
            "validate",
            "--resource-group",
            resource_group,
            "--template-file",
            str(template_file),
        ]
        if subscription_id:
            cmd.extend(["--subscription", subscription_id])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=Timeouts.ARM_VALIDATE,
            )
        except subprocess.TimeoutExpired as e:
            log_timeout_event("arm_validate", Timeouts.ARM_VALIDATE, cmd)
            if dashboard is not None:
                dashboard.update_phase("failed")
                dashboard.add_error(
                    f"ARM validation timed out after {Timeouts.ARM_VALIDATE}s"
                )
            raise RuntimeError(
                f"ARM validation timed out after {Timeouts.ARM_VALIDATE} seconds"
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
                dashboard.add_error(f"ARM validation failed: {result.stderr}")
            raise RuntimeError(f"ARM validation failed: {result.stderr}")

        if dashboard is not None:
            dashboard.update_phase("complete")
            dashboard.log_info("ARM validation completed successfully")

        return {
            "status": "validated",
            "output": result.stdout,
            "format": "arm",
        }

    # Deploy
    logger.info(str(f"Deploying ARM template {template_file.name}..."))
    if dashboard is not None:
        dashboard.update_phase("apply")
        dashboard.log_info(f"Deploying ARM template {template_file.name}...")

    cmd = [
        "az",
        "deployment",
        "group",
        "create",
        "--resource-group",
        resource_group,
        "--template-file",
        str(template_file),
    ]
    if subscription_id:
        cmd.extend(["--subscription", subscription_id])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=Timeouts.ARM_DEPLOY,
        )
    except subprocess.TimeoutExpired as e:
        log_timeout_event("arm_deploy", Timeouts.ARM_DEPLOY, cmd)
        if dashboard is not None:
            dashboard.update_phase("failed")
            dashboard.add_error(
                f"ARM deployment timed out after {Timeouts.ARM_DEPLOY}s"
            )
        raise RuntimeError(
            f"ARM deployment timed out after {Timeouts.ARM_DEPLOY} seconds"
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
            dashboard.add_error(f"ARM deployment failed: {result.stderr}")
        raise RuntimeError(f"ARM deployment failed: {result.stderr}")

    if dashboard is not None:
        dashboard.update_phase("complete")
        dashboard.log_info("ARM deployment completed successfully")
        dashboard.set_processing(False)

    return {
        "status": "deployed",
        "output": result.stdout,
        "format": "arm",
    }


__all__ = ["deploy_arm"]
