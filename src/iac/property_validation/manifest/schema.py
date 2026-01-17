"""Data classes for property manifest structure.

This module defines the core data structures for property manifests that map
Azure resource properties to Terraform parameters.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class CriticalityLevel(str, Enum):
    """Property criticality levels for prioritization."""

    CRITICAL = "CRITICAL"  # Must match exactly (names, IDs, core configs)
    HIGH = "HIGH"  # Should match (security, compliance)
    MEDIUM = "MEDIUM"  # Important but flexible (tags, descriptions)
    LOW = "LOW"  # Nice to have (defaults, optional features)


class PropertyType(str, Enum):
    """Property data types."""

    STRING = "string"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"
    NUMBER = "number"


@dataclass
class ProviderVersion:
    """Terraform provider version constraints."""

    min: str
    max: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate version format."""
        if not self.min:
            raise ValueError("Minimum provider version is required")

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary for YAML serialization."""
        result: dict[str, str] = {"min": self.min}
        if self.max:
            result["max"] = self.max
        return result

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "ProviderVersion":
        """Create from dictionary loaded from YAML."""
        return cls(min=data["min"], max=data.get("max"))


@dataclass
class PropertyMapping:
    """Individual property mapping between Azure and Terraform.

    Attributes:
        azure_path: JSON path in Azure resource (e.g., 'properties.accountTier')
        terraform_param: Terraform parameter name (e.g., 'account_tier')
        required: Whether property must be present
        criticality: Importance level for validation
        type: Data type of the property
        valid_values: List of allowed values (optional)
        default_value: Default if not specified (optional)
        description: Human-readable description (optional)
        notes: Additional notes about mapping (optional)
    """

    azure_path: str
    terraform_param: str
    required: bool
    criticality: CriticalityLevel
    type: PropertyType
    valid_values: Optional[list[Any]] = None
    default_value: Optional[Any] = None
    description: Optional[str] = None
    notes: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate and normalize fields."""
        if not self.azure_path:
            raise ValueError("azure_path is required")
        if not self.terraform_param:
            raise ValueError("terraform_param is required")

        # Convert string enums to enum instances if needed
        if isinstance(self.criticality, str):
            self.criticality = CriticalityLevel(self.criticality)
        if isinstance(self.type, str):
            self.type = PropertyType(self.type)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        result: dict[str, Any] = {
            "azure_path": self.azure_path,
            "terraform_param": self.terraform_param,
            "required": self.required,
            "criticality": self.criticality.value,
            "type": self.type.value,
        }

        if self.valid_values is not None:
            result["valid_values"] = self.valid_values
        if self.default_value is not None:
            result["default_value"] = self.default_value
        if self.description:
            result["description"] = self.description
        if self.notes:
            result["notes"] = self.notes

        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PropertyMapping":
        """Create from dictionary loaded from YAML."""
        return cls(
            azure_path=data["azure_path"],
            terraform_param=data["terraform_param"],
            required=data["required"],
            criticality=CriticalityLevel(data["criticality"]),
            type=PropertyType(data["type"]),
            valid_values=data.get("valid_values"),
            default_value=data.get("default_value"),
            description=data.get("description"),
            notes=data.get("notes"),
        )


@dataclass
class ResourceManifest:
    """Complete manifest for a resource type mapping.

    Attributes:
        resource_type: Resource type identifiers for Azure and Terraform
        provider_version: Terraform provider version constraints
        properties: List of property mappings
        metadata: Optional metadata (creation date, author, etc.)
    """

    resource_type: dict[str, str]  # {"azure": "...", "terraform": "..."}
    provider_version: ProviderVersion
    properties: list[PropertyMapping] = field(default_factory=list)
    metadata: Optional[dict[str, Any]] = None

    def __post_init__(self) -> None:
        """Validate resource type."""
        if "azure" not in self.resource_type:
            raise ValueError("resource_type must include 'azure' key")
        if "terraform" not in self.resource_type:
            raise ValueError("resource_type must include 'terraform' key")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        result: dict[str, Any] = {
            "resource_type": self.resource_type,
            "provider_version": self.provider_version.to_dict(),
            "properties": [prop.to_dict() for prop in self.properties],
        }

        if self.metadata:
            result["metadata"] = self.metadata

        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResourceManifest":
        """Create from dictionary loaded from YAML."""
        return cls(
            resource_type=data["resource_type"],
            provider_version=ProviderVersion.from_dict(data["provider_version"]),
            properties=[
                PropertyMapping.from_dict(prop) for prop in data.get("properties", [])
            ],
            metadata=data.get("metadata"),
        )

    def get_critical_properties(self) -> list[PropertyMapping]:
        """Get all CRITICAL properties."""
        return [
            prop for prop in self.properties if prop.criticality == CriticalityLevel.CRITICAL
        ]

    def get_required_properties(self) -> list[PropertyMapping]:
        """Get all required properties."""
        return [prop for prop in self.properties if prop.required]

    def get_property_by_terraform_param(
        self, param_name: str
    ) -> Optional[PropertyMapping]:
        """Find property mapping by Terraform parameter name."""
        for prop in self.properties:
            if prop.terraform_param == param_name:
                return prop
        return None

    def get_property_by_azure_path(self, path: str) -> Optional[PropertyMapping]:
        """Find property mapping by Azure JSON path."""
        for prop in self.properties:
            if prop.azure_path == path:
                return prop
        return None
