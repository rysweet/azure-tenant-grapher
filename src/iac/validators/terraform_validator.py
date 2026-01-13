"""
Terraform IaC Validation

Validates generated Terraform IaC by running terraform init and terraform validate.
Provides graceful degradation if Terraform is not installed.
"""

import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of Terraform validation."""

    valid: bool
    """Whether the Terraform configuration is valid"""

    terraform_available: bool
    """Whether Terraform CLI is installed"""

    init_success: bool
    """Whether terraform init succeeded"""

    validate_success: bool
    """Whether terraform validate succeeded"""

    error_message: Optional[str] = None
    """Error message if validation failed"""

    init_output: Optional[str] = None
    """Output from terraform init"""

    validate_output: Optional[str] = None
    """Output from terraform validate"""


class TerraformValidator:
    """
    Validates generated Terraform IaC configuration.

    This validator:
    1. Checks if Terraform CLI is installed
    2. Runs terraform init
    3. Runs terraform validate
    4. Returns structured results

    If Terraform is not installed, validation is skipped with a warning.
    """

    def __init__(self):
        """Initialize the Terraform validator."""
        self._terraform_available = self._check_terraform_available()

    def _check_terraform_available(self) -> bool:
        """
        Check if Terraform CLI is installed.

        Returns:
            True if terraform is available in PATH
        """
        return shutil.which("terraform") is not None

    def validate(self, iac_output_path: Path) -> ValidationResult:
        """
        Validate Terraform configuration at the given path.

        Args:
            iac_output_path: Path to directory containing Terraform files

        Returns:
            ValidationResult with validation status and details
        """
        if not self._terraform_available:
            logger.warning(
                "⚠️  Terraform CLI not found. Skipping validation. "
                "Install Terraform from https://www.terraform.io/downloads"
            )
            return ValidationResult(
                valid=False,
                terraform_available=False,
                init_success=False,
                validate_success=False,
                error_message="Terraform CLI not installed",
            )

        # Ensure path exists
        if not iac_output_path.exists():
            return ValidationResult(
                valid=False,
                terraform_available=True,
                init_success=False,
                validate_success=False,
                error_message=f"Output path does not exist: {iac_output_path}",
            )

        # Run terraform init
        logger.info(str(f"Running terraform init in {iac_output_path}..."))
        init_result = self._run_terraform_init(iac_output_path)

        if not init_result["success"]:
            logger.error(f"❌ terraform init failed: {init_result['error']}")
            return ValidationResult(
                valid=False,
                terraform_available=True,
                init_success=False,
                validate_success=False,
                error_message=init_result["error"],
                init_output=init_result["output"],
            )

        logger.info("✅ terraform init succeeded")

        # Run terraform validate
        logger.info("Running terraform validate...")
        validate_result = self._run_terraform_validate(iac_output_path)

        if not validate_result["success"]:
            logger.error(f"❌ terraform validate failed: {validate_result['error']}")
            return ValidationResult(
                valid=False,
                terraform_available=True,
                init_success=True,
                validate_success=False,
                error_message=validate_result["error"],
                init_output=init_result["output"],
                validate_output=validate_result["output"],
            )

        logger.info("✅ terraform validate succeeded - Generated IaC is valid")

        return ValidationResult(
            valid=True,
            terraform_available=True,
            init_success=True,
            validate_success=True,
            init_output=init_result["output"],
            validate_output=validate_result["output"],
        )

    def _run_terraform_init(self, working_dir: Path) -> dict:
        """
        Run terraform init.

        Args:
            working_dir: Directory containing Terraform files

        Returns:
            Dict with success status, output, and error message
        """
        try:
            result = subprocess.run(
                ["terraform", "init", "-no-color"],
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=60,  # 1 minute timeout
            )

            if result.returncode == 0:
                return {"success": True, "output": result.stdout, "error": None}
            else:
                return {
                    "success": False,
                    "output": result.stdout,
                    "error": result.stderr or result.stdout,
                }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": None,
                "error": "terraform init timed out after 60 seconds",
            }
        except Exception as e:
            return {"success": False, "output": None, "error": str(e)}

    def _run_terraform_validate(self, working_dir: Path) -> dict:
        """
        Run terraform validate.

        Args:
            working_dir: Directory containing Terraform files

        Returns:
            Dict with success status, output, and error message
        """
        try:
            result = subprocess.run(
                ["terraform", "validate", "-no-color", "-json"],
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=30,  # 30 second timeout
            )

            if result.returncode == 0:
                return {"success": True, "output": result.stdout, "error": None}
            else:
                return {
                    "success": False,
                    "output": result.stdout,
                    "error": result.stderr or result.stdout,
                }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": None,
                "error": "terraform validate timed out after 30 seconds",
            }
        except Exception as e:
            return {"success": False, "output": None, "error": str(e)}

    def handle_failure(self, result: ValidationResult) -> bool:
        """
        Handle validation failure with interactive prompt.

        Args:
            result: ValidationResult from validate()

        Returns:
            True if user wants to keep files, False to cleanup
        """
        if result.valid:
            return True  # Nothing to handle

        logger.error("❌ Terraform validation failed")

        if not result.terraform_available:
            logger.warning(
                "Terraform is not installed. IaC files have been generated but not validated."
            )
            logger.info(
                "Install Terraform from https://www.terraform.io/downloads to validate."
            )
            return True  # Keep files

        # Show error details
        if result.error_message:
            logger.error(str(f"Error: {result.error_message}"))

        if result.validate_output:
            logger.error(str(f"Validation output:\n{result.validate_output}"))

        # Interactive prompt
        try:
            response = input(
                "\nTerraform validation failed. Keep generated files? [y/N]: "
            )
            return response.lower() in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            # Non-interactive environment or user interrupted
            logger.info("Keeping generated files (non-interactive mode)")
            return True
