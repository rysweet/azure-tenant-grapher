"""Validate property manifest correctness.

This module validates manifest files for completeness, consistency, and
correctness of property mappings.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .schema import CriticalityLevel, PropertyMapping, ResourceManifest


@dataclass
class ValidationIssue:
    """Single validation issue.

    Attributes:
        severity: Issue severity (error, warning, info)
        message: Human-readable description
        property_path: Property path if issue relates to specific property
        code: Machine-readable issue code
    """

    severity: str  # "error", "warning", "info"
    message: str
    property_path: Optional[str] = None
    code: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of manifest validation.

    Attributes:
        valid: Whether manifest passed all checks
        issues: List of validation issues found
        manifest_path: Path to validated manifest (if from file)
    """

    valid: bool
    issues: list[ValidationIssue]
    manifest_path: Optional[Path] = None

    def has_errors(self) -> bool:
        """Check if any errors were found."""
        return any(issue.severity == "error" for issue in self.issues)

    def has_warnings(self) -> bool:
        """Check if any warnings were found."""
        return any(issue.severity == "warning" for issue in self.issues)

    def get_errors(self) -> list[ValidationIssue]:
        """Get all error issues."""
        return [issue for issue in self.issues if issue.severity == "error"]

    def get_warnings(self) -> list[ValidationIssue]:
        """Get all warning issues."""
        return [issue for issue in self.issues if issue.severity == "warning"]

    def format_issues(self) -> str:
        """Format issues as human-readable text."""
        if not self.issues:
            return "✓ No issues found"

        lines = []
        for issue in self.issues:
            prefix = {"error": "✗", "warning": "⚠", "info": "ℹ"}[issue.severity]
            location = f" [{issue.property_path}]" if issue.property_path else ""
            code = f" ({issue.code})" if issue.code else ""
            lines.append(f"{prefix} {issue.severity.upper()}{location}: {issue.message}{code}")

        return "\n".join(lines)


class ManifestValidator:
    """Validate property manifests for correctness and completeness.

    Validates:
    - Schema structure
    - Required fields
    - Property path format
    - Terraform parameter naming
    - Version constraint format
    - Duplicate mappings
    - Criticality assignment
    """

    def __init__(self) -> None:
        """Initialize validator."""
        self._version_pattern = re.compile(r"^\d+\.\d+\.\d+$")
        self._terraform_param_pattern = re.compile(r"^[a-z][a-z0-9_]*$")
        self._azure_path_pattern = re.compile(r"^[a-zA-Z][a-zA-Z0-9_.]*$")

    def validate(self, manifest: ResourceManifest) -> ValidationResult:
        """Validate manifest completeness and correctness.

        Args:
            manifest: Manifest to validate

        Returns:
            ValidationResult with any issues found
        """
        issues: list[ValidationIssue] = []

        # Validate resource type
        issues.extend(self._validate_resource_type(manifest))

        # Validate provider version
        issues.extend(self._validate_provider_version(manifest))

        # Validate properties
        issues.extend(self._validate_properties(manifest))

        # Check for duplicates
        issues.extend(self._check_duplicates(manifest))

        # Validate criticality distribution
        issues.extend(self._validate_criticality_distribution(manifest))

        # Check required property coverage
        issues.extend(self._check_required_coverage(manifest))

        # Determine if valid (no errors)
        valid = not any(issue.severity == "error" for issue in issues)

        return ValidationResult(valid=valid, issues=issues)

    def validate_file(self, manifest_path: Path) -> ValidationResult:
        """Validate manifest from file.

        Args:
            manifest_path: Path to manifest YAML file

        Returns:
            ValidationResult with any issues found
        """
        from .generator import ManifestGenerator

        generator = ManifestGenerator()
        try:
            manifest = generator.load_manifest(manifest_path)
            result = self.validate(manifest)
            result.manifest_path = manifest_path
            return result
        except Exception as e:
            return ValidationResult(
                valid=False,
                issues=[
                    ValidationIssue(
                        severity="error",
                        message=f"Failed to load manifest: {e}",
                        code="LOAD_ERROR",
                    )
                ],
                manifest_path=manifest_path,
            )

    def _validate_resource_type(self, manifest: ResourceManifest) -> list[ValidationIssue]:
        """Validate resource type definitions."""
        issues: list[ValidationIssue] = []

        if not manifest.resource_type.get("azure"):
            issues.append(
                ValidationIssue(
                    severity="error",
                    message="Missing Azure resource type",
                    code="MISSING_AZURE_TYPE",
                )
            )

        if not manifest.resource_type.get("terraform"):
            issues.append(
                ValidationIssue(
                    severity="error",
                    message="Missing Terraform resource type",
                    code="MISSING_TERRAFORM_TYPE",
                )
            )

        # Validate Azure resource type format (e.g., Microsoft.Storage/storageAccounts)
        azure_type = manifest.resource_type.get("azure", "")
        if azure_type and "/" not in azure_type:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    message=f"Azure resource type may be invalid: {azure_type}",
                    code="INVALID_AZURE_TYPE_FORMAT",
                )
            )

        # Validate Terraform resource type format (e.g., azurerm_storage_account)
        terraform_type = manifest.resource_type.get("terraform", "")
        if terraform_type and not terraform_type.startswith("azurerm_"):
            issues.append(
                ValidationIssue(
                    severity="warning",
                    message=f"Terraform resource type should start with 'azurerm_': {terraform_type}",
                    code="INVALID_TERRAFORM_TYPE_PREFIX",
                )
            )

        return issues

    def _validate_provider_version(self, manifest: ResourceManifest) -> list[ValidationIssue]:
        """Validate provider version constraints."""
        issues: list[ValidationIssue] = []

        # Validate minimum version format
        if not self._version_pattern.match(manifest.provider_version.min):
            issues.append(
                ValidationIssue(
                    severity="error",
                    message=f"Invalid minimum version format: {manifest.provider_version.min}",
                    code="INVALID_VERSION_FORMAT",
                )
            )

        # Validate maximum version format if present
        if manifest.provider_version.max:
            if not self._version_pattern.match(manifest.provider_version.max):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        message=f"Invalid maximum version format: {manifest.provider_version.max}",
                        code="INVALID_VERSION_FORMAT",
                    )
                )

            # Check max > min
            try:
                min_parts = [int(x) for x in manifest.provider_version.min.split(".")]
                max_parts = [int(x) for x in manifest.provider_version.max.split(".")]
                if max_parts <= min_parts:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            message="Maximum version must be greater than minimum version",
                            code="INVALID_VERSION_RANGE",
                        )
                    )
            except ValueError:
                pass  # Already caught by format validation

        return issues

    def _validate_properties(self, manifest: ResourceManifest) -> list[ValidationIssue]:
        """Validate individual property mappings."""
        issues: list[ValidationIssue] = []

        if not manifest.properties:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    message="Manifest has no property mappings",
                    code="NO_PROPERTIES",
                )
            )
            return issues

        for prop in manifest.properties:
            # Validate Azure path format
            if not self._azure_path_pattern.match(prop.azure_path):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        message=f"Invalid Azure path format: {prop.azure_path}",
                        property_path=prop.azure_path,
                        code="INVALID_AZURE_PATH",
                    )
                )

            # Validate Terraform parameter naming (snake_case)
            if not self._terraform_param_pattern.match(prop.terraform_param):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        message=f"Invalid Terraform parameter name: {prop.terraform_param} (must be snake_case)",
                        property_path=prop.terraform_param,
                        code="INVALID_TERRAFORM_PARAM",
                    )
                )

            # Validate valid_values consistency with type
            if prop.valid_values:
                if prop.type.value == "boolean" and len(prop.valid_values) > 2:
                    issues.append(
                        ValidationIssue(
                            severity="warning",
                            message=f"Boolean property has more than 2 valid values: {prop.terraform_param}",
                            property_path=prop.terraform_param,
                            code="INVALID_VALID_VALUES",
                        )
                    )

            # Check required properties have appropriate criticality
            if prop.required and prop.criticality == CriticalityLevel.LOW:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        message=f"Required property marked as LOW criticality: {prop.terraform_param}",
                        property_path=prop.terraform_param,
                        code="INCONSISTENT_CRITICALITY",
                    )
                )

        return issues

    def _check_duplicates(self, manifest: ResourceManifest) -> list[ValidationIssue]:
        """Check for duplicate property mappings."""
        issues: list[ValidationIssue] = []

        # Check for duplicate Azure paths
        azure_paths: set[str] = set()
        for prop in manifest.properties:
            if prop.azure_path in azure_paths:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        message=f"Duplicate Azure path: {prop.azure_path}",
                        property_path=prop.azure_path,
                        code="DUPLICATE_AZURE_PATH",
                    )
                )
            azure_paths.add(prop.azure_path)

        # Check for duplicate Terraform parameters
        terraform_params: set[str] = set()
        for prop in manifest.properties:
            if prop.terraform_param in terraform_params:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        message=f"Duplicate Terraform parameter: {prop.terraform_param}",
                        property_path=prop.terraform_param,
                        code="DUPLICATE_TERRAFORM_PARAM",
                    )
                )
            terraform_params.add(prop.terraform_param)

        return issues

    def _validate_criticality_distribution(
        self, manifest: ResourceManifest
    ) -> list[ValidationIssue]:
        """Validate reasonable distribution of criticality levels."""
        issues: list[ValidationIssue] = []

        if not manifest.properties:
            return issues

        # Count by criticality
        counts = {level: 0 for level in CriticalityLevel}
        for prop in manifest.properties:
            counts[prop.criticality] += 1

        total = len(manifest.properties)

        # Warn if all properties have same criticality
        if any(count == total for count in counts.values()):
            issues.append(
                ValidationIssue(
                    severity="info",
                    message="All properties have same criticality level - consider reviewing",
                    code="UNIFORM_CRITICALITY",
                )
            )

        # Warn if too many CRITICAL properties (> 30%)
        if counts[CriticalityLevel.CRITICAL] > total * 0.3:
            issues.append(
                ValidationIssue(
                    severity="info",
                    message=f"{counts[CriticalityLevel.CRITICAL]} of {total} properties marked CRITICAL (>{30}%) - consider reviewing",
                    code="EXCESSIVE_CRITICAL_PROPERTIES",
                )
            )

        return issues

    def _check_required_coverage(self, manifest: ResourceManifest) -> list[ValidationIssue]:
        """Check that required properties are covered."""
        issues: list[ValidationIssue] = []

        required_count = sum(1 for prop in manifest.properties if prop.required)

        if required_count == 0:
            issues.append(
                ValidationIssue(
                    severity="info",
                    message="No required properties defined - verify this is correct",
                    code="NO_REQUIRED_PROPERTIES",
                )
            )

        # All required properties should be at least MEDIUM criticality
        for prop in manifest.properties:
            if prop.required and prop.criticality == CriticalityLevel.LOW:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        message=f"Required property has LOW criticality: {prop.terraform_param}",
                        property_path=prop.terraform_param,
                        code="LOW_CRITICALITY_REQUIRED",
                    )
                )

        return issues
