"""Generate property manifests from Azure and Terraform schemas.

This module creates YAML manifest files by analyzing Azure resource schemas
and Terraform provider schemas to identify property mappings.
"""

from pathlib import Path
from typing import Any, Optional

import yaml

from .schema import (
    CriticalityLevel,
    PropertyMapping,
    PropertyType,
    ProviderVersion,
    ResourceManifest,
)


class ManifestGenerator:
    """Generate manifest files from Azure and Terraform schemas.

    This generator analyzes resource schemas and creates property mappings
    between Azure resource properties and Terraform parameters.
    """

    def __init__(self) -> None:
        """Initialize manifest generator."""
        self._type_mappings = {
            "string": PropertyType.STRING,
            "integer": PropertyType.INTEGER,
            "int": PropertyType.INTEGER,
            "boolean": PropertyType.BOOLEAN,
            "bool": PropertyType.BOOLEAN,
            "object": PropertyType.OBJECT,
            "array": PropertyType.ARRAY,
            "number": PropertyType.NUMBER,
            "float": PropertyType.NUMBER,
        }

    def generate_from_schemas(
        self,
        azure_schema: dict[str, Any],
        terraform_schema: dict[str, Any],
        azure_resource_type: str,
        terraform_resource_type: str,
        provider_version_min: str,
        provider_version_max: Optional[str] = None,
    ) -> ResourceManifest:
        """Generate manifest from Azure and Terraform schema definitions.

        Args:
            azure_schema: Azure resource schema (JSON Schema format)
            terraform_schema: Terraform resource schema (provider schema format)
            azure_resource_type: Azure resource type (e.g., Microsoft.Storage/storageAccounts)
            terraform_resource_type: Terraform resource type (e.g., azurerm_storage_account)
            provider_version_min: Minimum provider version
            provider_version_max: Maximum provider version (optional)

        Returns:
            ResourceManifest with detected property mappings
        """
        manifest = ResourceManifest(
            resource_type={
                "azure": azure_resource_type,
                "terraform": terraform_resource_type,
            },
            provider_version=ProviderVersion(
                min=provider_version_min, max=provider_version_max
            ),
            properties=[],
        )

        # Extract properties from Azure schema
        azure_properties = self._extract_azure_properties(azure_schema)

        # Extract properties from Terraform schema
        terraform_properties = self._extract_terraform_properties(terraform_schema)

        # Match properties between schemas
        manifest.properties = self._match_properties(
            azure_properties, terraform_properties
        )

        return manifest

    def _extract_azure_properties(
        self, schema: dict[str, Any]
    ) -> dict[str, dict[str, Any]]:
        """Extract property definitions from Azure schema.

        Args:
            schema: Azure resource schema

        Returns:
            Dictionary mapping property paths to their definitions
        """
        properties: dict[str, dict[str, Any]] = {}

        def extract_recursive(obj: dict[str, Any], path: str = "") -> None:
            """Recursively extract properties from nested schema."""
            if not isinstance(obj, dict):
                return

            # Look for properties in schema
            if "properties" in obj and isinstance(obj["properties"], dict):
                for prop_name, prop_def in obj["properties"].items():
                    current_path = f"{path}.{prop_name}" if path else prop_name
                    properties[current_path] = prop_def

                    # Recurse into nested objects
                    if isinstance(prop_def, dict):
                        extract_recursive(prop_def, current_path)

        extract_recursive(schema)
        return properties

    def _extract_terraform_properties(
        self, schema: dict[str, Any]
    ) -> dict[str, dict[str, Any]]:
        """Extract property definitions from Terraform schema.

        Args:
            schema: Terraform resource schema

        Returns:
            Dictionary mapping parameter names to their definitions
        """
        properties: dict[str, dict[str, Any]] = {}

        # Terraform schema typically has "block" structure
        if "block" in schema and "attributes" in schema["block"]:
            for attr_name, attr_def in schema["block"]["attributes"].items():
                properties[attr_name] = attr_def

        # Also check for direct attributes field
        elif "attributes" in schema:
            for attr_name, attr_def in schema["attributes"].items():
                properties[attr_name] = attr_def

        return properties

    def _match_properties(
        self,
        azure_properties: dict[str, dict[str, Any]],
        terraform_properties: dict[str, dict[str, Any]],
    ) -> list[PropertyMapping]:
        """Match Azure properties to Terraform parameters.

        Args:
            azure_properties: Extracted Azure property definitions
            terraform_properties: Extracted Terraform parameter definitions

        Returns:
            List of PropertyMapping objects
        """
        mappings: list[PropertyMapping] = []

        # Simple name-based matching (can be enhanced with fuzzy matching)
        for azure_path, azure_def in azure_properties.items():
            # Try to find matching Terraform parameter
            # Convert Azure path to potential Terraform name (camelCase to snake_case)
            potential_tf_name = self._azure_path_to_terraform_name(azure_path)

            if potential_tf_name in terraform_properties:
                tf_def = terraform_properties[potential_tf_name]

                mapping = self._create_mapping(
                    azure_path, azure_def, potential_tf_name, tf_def
                )
                mappings.append(mapping)

        return mappings

    def _azure_path_to_terraform_name(self, azure_path: str) -> str:
        """Convert Azure property path to Terraform parameter name.

        Converts camelCase/PascalCase to snake_case and handles nested paths.

        Args:
            azure_path: Azure property path (e.g., 'properties.accountTier')

        Returns:
            Terraform-style parameter name (e.g., 'account_tier')
        """
        # Take the last component of the path
        parts = azure_path.split(".")
        name = parts[-1]

        # Convert camelCase/PascalCase to snake_case
        result = []
        for i, char in enumerate(name):
            if char.isupper() and i > 0:
                result.append("_")
            result.append(char.lower())

        return "".join(result)

    def _create_mapping(
        self,
        azure_path: str,
        azure_def: dict[str, Any],
        terraform_param: str,
        terraform_def: dict[str, Any],
    ) -> PropertyMapping:
        """Create PropertyMapping from schema definitions.

        Args:
            azure_path: Azure property path
            azure_def: Azure property definition
            terraform_param: Terraform parameter name
            terraform_def: Terraform parameter definition

        Returns:
            PropertyMapping object
        """
        # Determine property type
        azure_type = azure_def.get("type", "string")
        prop_type = self._type_mappings.get(azure_type.lower(), PropertyType.STRING)

        # Determine if required
        required = azure_def.get("required", False) or terraform_def.get(
            "required", False
        )

        # Determine criticality (heuristic based on property name)
        criticality = self._infer_criticality(azure_path)

        # Extract valid values if present
        valid_values = None
        if "enum" in azure_def:
            valid_values = azure_def["enum"]
        elif "enum" in terraform_def:
            valid_values = terraform_def["enum"]

        # Extract default value
        default_value = terraform_def.get("default")

        # Extract description
        description = azure_def.get("description") or terraform_def.get("description")

        return PropertyMapping(
            azure_path=azure_path,
            terraform_param=terraform_param,
            required=required,
            criticality=criticality,
            type=prop_type,
            valid_values=valid_values,
            default_value=default_value,
            description=description,
        )

    def _infer_criticality(self, property_path: str) -> CriticalityLevel:
        """Infer property criticality based on name patterns.

        Args:
            property_path: Property path (e.g., 'properties.accountTier')

        Returns:
            Inferred criticality level
        """
        path_lower = property_path.lower()

        # Critical patterns (names, IDs, core configs)
        critical_patterns = ["name", "id", "type", "kind", "sku", "tier"]
        if any(pattern in path_lower for pattern in critical_patterns):
            return CriticalityLevel.CRITICAL

        # High patterns (security, compliance)
        high_patterns = [
            "security",
            "encryption",
            "access",
            "authentication",
            "authorization",
            "compliance",
        ]
        if any(pattern in path_lower for pattern in high_patterns):
            return CriticalityLevel.HIGH

        # Low patterns (optional features)
        low_patterns = ["description", "display", "label", "color"]
        if any(pattern in path_lower for pattern in low_patterns):
            return CriticalityLevel.LOW

        # Default to MEDIUM
        return CriticalityLevel.MEDIUM

    def save_manifest(self, manifest: ResourceManifest, output_path: Path) -> None:
        """Save manifest to YAML file.

        Args:
            manifest: Manifest to save
            output_path: Path to output YAML file
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        manifest_dict = manifest.to_dict()

        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(
                manifest_dict,
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )

    def load_manifest(self, manifest_path: Path) -> ResourceManifest:
        """Load manifest from YAML file.

        Args:
            manifest_path: Path to manifest YAML file

        Returns:
            Loaded ResourceManifest
        """
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")

        with open(manifest_path, encoding="utf-8") as f:
            manifest_dict = yaml.safe_load(f)

        return ResourceManifest.from_dict(manifest_dict)

    def generate_template_manifest(
        self,
        azure_resource_type: str,
        terraform_resource_type: str,
        provider_version_min: str = "3.0.0",
    ) -> ResourceManifest:
        """Generate empty template manifest for manual completion.

        Args:
            azure_resource_type: Azure resource type
            terraform_resource_type: Terraform resource type
            provider_version_min: Minimum provider version

        Returns:
            Empty template manifest
        """
        return ResourceManifest(
            resource_type={
                "azure": azure_resource_type,
                "terraform": terraform_resource_type,
            },
            provider_version=ProviderVersion(min=provider_version_min),
            properties=[],
            metadata={
                "template": True,
                "instructions": "Add property mappings manually",
            },
        )
