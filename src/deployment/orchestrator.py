"""Deployment orchestration for IaC templates."""

import json
import logging
import subprocess
from pathlib import Path
from typing import Literal, Optional

logger = logging.getLogger(__name__)

IaCFormat = Literal["terraform", "bicep", "arm"]


def detect_iac_format(iac_dir: Path) -> Optional[IaCFormat]:
    """Auto-detect IaC format from directory contents.

    Args:
        iac_dir: Directory containing IaC files

    Returns:
        Detected format or None if unknown
    """
    if not iac_dir.exists() or not iac_dir.is_dir():
        return None

    # Check for Terraform files (both .tf and .tf.json)
    if list(iac_dir.glob("*.tf")) or list(iac_dir.glob("*.tf.json")):
        return "terraform"

    # Check for Bicep files
    if list(iac_dir.glob("*.bicep")):
        return "bicep"

    # Check for ARM templates (JSON with deployment schema)
    for json_file in iac_dir.glob("*.json"):
        try:
            with open(json_file) as f:
                data = json.load(f)
                if "$schema" in data and "deploymentTemplate" in data.get("$schema", ""):
                    return "arm"
        except Exception:
            continue

    return None


def deploy_terraform(
    iac_dir: Path, resource_group: str, location: str, dry_run: bool = False
) -> dict:
    """Deploy Terraform IaC.

    Args:
        iac_dir: Directory containing Terraform files
        resource_group: Target resource group name
        location: Azure region
        dry_run: If True, only run plan without apply

    Returns:
        Deployment result dictionary

    Raises:
        RuntimeError: If terraform commands fail
    """
    logger.info(f"Deploying Terraform from {iac_dir}")

    # Initialize Terraform
    logger.debug("Running terraform init...")
    result = subprocess.run(
        ["terraform", "init"],
        cwd=iac_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Terraform init failed: {result.stderr}")

    if dry_run:
        # Plan only
        logger.info("Running terraform plan (dry-run mode)...")
        result = subprocess.run(
            ["terraform", "plan", "-input=false"],
            cwd=iac_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Terraform plan failed: {result.stderr}")

        return {
            "status": "planned",
            "output": result.stdout,
            "format": "terraform",
        }

    # Apply changes
    logger.info("Running terraform apply...")
    result = subprocess.run(
        ["terraform", "apply", "-auto-approve", "-input=false"],
        cwd=iac_dir,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Terraform apply failed: {result.stderr}")

    return {
        "status": "deployed",
        "output": result.stdout,
        "format": "terraform",
    }


def deploy_bicep(
    iac_dir: Path,
    resource_group: str,
    location: str,
    subscription_id: Optional[str] = None,
    dry_run: bool = False,
) -> dict:
    """Deploy Bicep IaC.

    Args:
        iac_dir: Directory containing Bicep files
        resource_group: Target resource group name
        location: Azure region
        subscription_id: Optional subscription ID
        dry_run: If True, only validate without deploying

    Returns:
        Deployment result dictionary

    Raises:
        RuntimeError: If bicep/az commands fail
    """
    logger.info(f"Deploying Bicep from {iac_dir}")

    # Find main bicep file (look for main.bicep or first .bicep file)
    bicep_files = list(iac_dir.glob("*.bicep"))
    if not bicep_files:
        raise RuntimeError(f"No Bicep files found in {iac_dir}")

    main_file = next(
        (f for f in bicep_files if f.name == "main.bicep"), bicep_files[0]
    )

    if dry_run:
        # Validate only
        logger.info(f"Validating Bicep template {main_file.name}...")
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

        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.returncode != 0:
            raise RuntimeError(f"Bicep validation failed: {result.stderr}")

        return {
            "status": "validated",
            "output": result.stdout,
            "format": "bicep",
        }

    # Deploy
    logger.info(f"Deploying Bicep template {main_file.name}...")
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

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)

    if result.returncode != 0:
        raise RuntimeError(f"Bicep deployment failed: {result.stderr}")

    return {
        "status": "deployed",
        "output": result.stdout,
        "format": "bicep",
    }


def deploy_arm(
    iac_dir: Path,
    resource_group: str,
    location: str,
    subscription_id: Optional[str] = None,
    dry_run: bool = False,
) -> dict:
    """Deploy ARM template IaC.

    Args:
        iac_dir: Directory containing ARM template files
        resource_group: Target resource group name
        location: Azure region
        subscription_id: Optional subscription ID
        dry_run: If True, only validate without deploying

    Returns:
        Deployment result dictionary

    Raises:
        RuntimeError: If az commands fail
    """
    logger.info(f"Deploying ARM template from {iac_dir}")

    # Find ARM template file
    arm_files = []
    for json_file in iac_dir.glob("*.json"):
        try:
            with open(json_file) as f:
                data = json.load(f)
                if "$schema" in data and "deploymentTemplate" in data.get("$schema", ""):
                    arm_files.append(json_file)
        except Exception:
            continue

    if not arm_files:
        raise RuntimeError(f"No ARM template files found in {iac_dir}")

    template_file = arm_files[0]

    if dry_run:
        # Validate only
        logger.info(f"Validating ARM template {template_file.name}...")
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

        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.returncode != 0:
            raise RuntimeError(f"ARM validation failed: {result.stderr}")

        return {
            "status": "validated",
            "output": result.stdout,
            "format": "arm",
        }

    # Deploy
    logger.info(f"Deploying ARM template {template_file.name}...")
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

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)

    if result.returncode != 0:
        raise RuntimeError(f"ARM deployment failed: {result.stderr}")

    return {
        "status": "deployed",
        "output": result.stdout,
        "format": "arm",
    }


def deploy_iac(
    iac_dir: Path,
    target_tenant_id: str,
    resource_group: str,
    location: str = "eastus",
    subscription_id: Optional[str] = None,
    iac_format: Optional[IaCFormat] = None,
    dry_run: bool = False,
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
    current_tenant_result = subprocess.run(
        ["az", "account", "show", "--query", "tenantId", "-o", "tsv"],
        capture_output=True,
        text=True,
        check=False,
    )

    current_tenant = current_tenant_result.stdout.strip() if current_tenant_result.returncode == 0 else None

    if current_tenant == target_tenant_id:
        logger.info(f"Already authenticated to target tenant {target_tenant_id}")
    elif subscription_id:
        # Try switching subscription (works for multi-tenant users)
        logger.info(f"Switching to subscription {subscription_id} in tenant {target_tenant_id}...")
        switch_result = subprocess.run(
            ["az", "account", "set", "--subscription", subscription_id],
            capture_output=True,
            text=True,
            check=False,
        )
        if switch_result.returncode != 0:
            logger.warning(f"Subscription switch failed: {switch_result.stderr}")
            logger.info("Attempting interactive login...")
            auth_result = subprocess.run(
                ["az", "login", "--tenant", target_tenant_id, "--output", "none"],
                capture_output=True,
                text=True,
                check=False,
            )
            if auth_result.returncode != 0:
                raise RuntimeError(f"Azure login failed: {auth_result.stderr}")
    else:
        # No subscription ID provided, attempt login
        logger.info(f"Authenticating to tenant {target_tenant_id}...")
        auth_result = subprocess.run(
            ["az", "login", "--tenant", target_tenant_id, "--output", "none"],
            capture_output=True,
            text=True,
            check=False,
        )
        if auth_result.returncode != 0:
            logger.warning(f"Azure login may have failed: {auth_result.stderr}")
            # Don't raise - may already be authenticated

    # Deploy based on format
    if iac_format == "terraform":
        return deploy_terraform(iac_dir, resource_group, location, dry_run)
    elif iac_format == "bicep":
        return deploy_bicep(iac_dir, resource_group, location, subscription_id, dry_run)
    elif iac_format == "arm":
        return deploy_arm(iac_dir, resource_group, location, subscription_id, dry_run)
    else:
        raise ValueError(f"Unsupported IaC format: {iac_format}")
