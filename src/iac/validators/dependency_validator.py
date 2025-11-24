"""
Dependency Validation for Terraform IaC

Validates that all resource references in generated Terraform IaC are declared.
Uses terraform validate JSON output to detect undeclared resource errors.
"""

import json
import logging
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DependencyError:
    """Represents a dependency error in Terraform configuration."""

    resource_type: str
    """Type of resource with the error (e.g., 'azurerm_virtual_machine')"""

    resource_name: str
    """Name of resource with the error"""

    missing_reference: str
    """The missing resource reference (e.g., 'azurerm_network_interface.missing_nic')"""

    error_message: str
    """Full error message from Terraform"""


@dataclass
class DependencyValidationResult:
    """Result of dependency validation."""

    valid: bool
    """Whether all dependencies are valid (no undeclared resources)"""

    terraform_available: bool
    """Whether Terraform CLI is installed"""

    errors: List[DependencyError] = field(default_factory=list)
    """List of dependency errors found"""

    total_errors: int = 0
    """Total number of errors found"""

    validation_output: Optional[str] = None
    """Raw JSON output from terraform validate"""


class DependencyValidator:
    """
    Validates resource dependencies in Terraform configuration.

    This validator:
    1. Checks if Terraform CLI is installed
    2. Runs terraform init (if needed)
    3. Runs terraform validate -json
    4. Parses output for undeclared resource errors
    5. Returns structured dependency errors
    """

    # Pattern to extract resource references from error messages
    # Example: "Reference to undeclared resource: azurerm_network_interface.missing_nic"
    UNDECLARED_PATTERN = re.compile(
        r"Reference to undeclared (?:resource|module|input variable|output value|local value):\s+((?:azurerm|azuread)_\w+\.\w+)"
    )

    def __init__(self):
        """Initialize the dependency validator."""
        self._terraform_available = self._check_terraform_available()

    def _check_terraform_available(self) -> bool:
        """
        Check if Terraform CLI is installed.

        Returns:
            True if terraform is available in PATH
        """
        return shutil.which("terraform") is not None

    def validate(
        self, iac_output_path: Path, skip_init: bool = False
    ) -> DependencyValidationResult:
        """
        Validate dependencies in Terraform configuration.

        Args:
            iac_output_path: Path to directory containing Terraform files
            skip_init: If True, skip terraform init (assumes already initialized)

        Returns:
            DependencyValidationResult with validation status and errors
        """
        if not self._terraform_available:
            logger.warning(
                "⚠️  Terraform CLI not found. Skipping dependency validation. "
                "Install Terraform from https://www.terraform.io/downloads"
            )
            return DependencyValidationResult(
                valid=True,  # Don't fail if terraform not available
                terraform_available=False,
            )

        # Ensure path exists
        if not iac_output_path.exists():
            logger.error(f"Output path does not exist: {iac_output_path}")
            return DependencyValidationResult(
                valid=False,
                terraform_available=True,
                errors=[],
            )

        # Run terraform init if needed
        if not skip_init:
            logger.info(f"Running terraform init in {iac_output_path}...")
            init_success = self._run_terraform_init(iac_output_path)
            if not init_success:
                logger.error("❌ terraform init failed - cannot validate dependencies")
                return DependencyValidationResult(
                    valid=False,
                    terraform_available=True,
                    errors=[],
                )
            logger.info("✅ terraform init succeeded")

        # Run terraform validate with JSON output
        logger.info("Running terraform validate to check dependencies...")
        validate_result = self._run_terraform_validate_json(iac_output_path)

        if validate_result["success"]:
            logger.info("✅ No dependency errors found - all resources are declared")
            return DependencyValidationResult(
                valid=True,
                terraform_available=True,
                errors=[],
                validation_output=validate_result["output"],
            )

        # Parse errors from JSON output
        errors = self._parse_dependency_errors(validate_result["output"])

        if errors:
            logger.error(
                f"❌ Found {len(errors)} dependency error(s) - "
                f"resources reference undeclared resources"
            )
            for error in errors:
                logger.error(
                    f"  • {error.resource_type}.{error.resource_name} → "
                    f"missing {error.missing_reference}"
                )
        else:
            logger.warning(
                "⚠️  terraform validate failed but no dependency errors were parsed. "
                "There may be other validation issues."
            )

        return DependencyValidationResult(
            valid=len(errors) == 0,
            terraform_available=True,
            errors=errors,
            total_errors=len(errors),
            validation_output=validate_result["output"],
        )

    def _run_terraform_init(self, working_dir: Path) -> bool:
        """
        Run terraform init.

        Args:
            working_dir: Directory containing Terraform files

        Returns:
            True if init succeeded
        """
        try:
            result = subprocess.run(
                ["terraform", "init", "-no-color"],
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=60,  # 1 minute timeout
            )
            return result.returncode == 0

        except (subprocess.TimeoutExpired, Exception) as e:
            logger.error(f"terraform init failed: {e}")
            return False

    def _run_terraform_validate_json(self, working_dir: Path) -> Dict[str, Any]:
        """
        Run terraform validate with JSON output.

        Args:
            working_dir: Directory containing Terraform files

        Returns:
            Dict with success status and JSON output
        """
        try:
            result = subprocess.run(
                ["terraform", "validate", "-json"],
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=30,  # 30 second timeout
            )

            # terraform validate returns 0 if valid, 1 if invalid
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
            }

        except subprocess.TimeoutExpired:
            logger.error("terraform validate timed out after 30 seconds")
            return {"success": False, "output": None}
        except Exception as e:
            logger.error(f"terraform validate failed: {e}")
            return {"success": False, "output": None}

    def _parse_dependency_errors(
        self, validate_json_output: Optional[str]
    ) -> List[DependencyError]:
        """
        Parse dependency errors from terraform validate JSON output.

        Args:
            validate_json_output: JSON string from terraform validate -json

        Returns:
            List of DependencyError objects
        """
        if not validate_json_output:
            return []

        try:
            data = json.loads(validate_json_output)
        except json.JSONDecodeError:
            logger.error("Failed to parse terraform validate JSON output")
            return []

        errors = []

        # Check if validation was successful
        if data.get("valid", False):
            return []

        # Parse diagnostics for undeclared resource errors
        diagnostics = data.get("diagnostics", [])
        for diag in diagnostics:
            severity = diag.get("severity", "")
            summary = diag.get("summary", "")
            detail = diag.get("detail", "")

            # Only process errors (not warnings)
            if severity != "error":
                continue

            # Check if this is an undeclared resource error
            full_message = f"{summary} {detail}"
            match = self.UNDECLARED_PATTERN.search(full_message)

            if match:
                missing_ref = match.group(1)  # e.g., "azurerm_network_interface.nic1"

                # Try to extract the resource that has the error from address field
                address = diag.get("address", "")
                if address:
                    # Address format: "azurerm_virtual_machine.vm1"
                    parts = address.split(".", 1)
                    if len(parts) == 2:
                        resource_type, resource_name = parts
                    else:
                        resource_type, resource_name = "unknown", "unknown"
                else:
                    resource_type, resource_name = "unknown", "unknown"

                errors.append(
                    DependencyError(
                        resource_type=resource_type,
                        resource_name=resource_name,
                        missing_reference=missing_ref,
                        error_message=full_message,
                    )
                )

        return errors
