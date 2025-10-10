"""IaC validators for Azure Tenant Grapher."""

from .terraform_validator import TerraformValidator, ValidationResult

__all__ = ["TerraformValidator", "ValidationResult"]
