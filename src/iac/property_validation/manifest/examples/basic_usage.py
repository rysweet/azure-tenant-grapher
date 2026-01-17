"""Basic usage examples for the Property Manifest brick.

This demonstrates how to:
1. Create property mappings programmatically
2. Build a resource manifest
3. Save and load manifests
4. Validate manifest correctness
5. Generate manifests from schemas
"""

from pathlib import Path

from src.iac.property_validation.manifest import (
    CriticalityLevel,
    ManifestGenerator,
    ManifestValidator,
    PropertyMapping,
    PropertyType,
    ProviderVersion,
    ResourceManifest,
)


def example_create_manifest_programmatically() -> ResourceManifest:
    """Create a manifest programmatically for a storage account."""
    print("Example 1: Creating manifest programmatically")
    print("=" * 60)

    # Create individual property mappings
    properties = [
        PropertyMapping(
            azure_path="name",
            terraform_param="name",
            required=True,
            criticality=CriticalityLevel.CRITICAL,
            type=PropertyType.STRING,
            description="Storage account name",
        ),
        PropertyMapping(
            azure_path="properties.accountTier",
            terraform_param="account_tier",
            required=True,
            criticality=CriticalityLevel.CRITICAL,
            type=PropertyType.STRING,
            valid_values=["Standard", "Premium"],
            default_value="Standard",
            description="Storage account tier",
        ),
        PropertyMapping(
            azure_path="properties.replication",
            terraform_param="account_replication_type",
            required=True,
            criticality=CriticalityLevel.HIGH,
            type=PropertyType.STRING,
            valid_values=["LRS", "GRS", "RAGRS", "ZRS"],
            default_value="LRS",
            description="Replication strategy",
        ),
        PropertyMapping(
            azure_path="tags",
            terraform_param="tags",
            required=False,
            criticality=CriticalityLevel.MEDIUM,
            type=PropertyType.OBJECT,
            description="Resource tags",
        ),
    ]

    # Create the manifest
    manifest = ResourceManifest(
        resource_type={
            "azure": "Microsoft.Storage/storageAccounts",
            "terraform": "azurerm_storage_account",
        },
        provider_version=ProviderVersion(min="3.0.0", max="4.99.99"),
        properties=properties,
        metadata={
            "created_by": "example",
            "description": "Storage account property mappings",
        },
    )

    print(f"✓ Created manifest with {len(manifest.properties)} properties")
    print(f"  Critical properties: {len(manifest.get_critical_properties())}")
    print(f"  Required properties: {len(manifest.get_required_properties())}")
    print()

    return manifest


def example_save_and_load_manifest(manifest: ResourceManifest) -> None:
    """Save manifest to YAML and load it back."""
    print("Example 2: Saving and loading manifests")
    print("=" * 60)

    generator = ManifestGenerator()
    output_path = Path("/tmp/storage_account_manifest.yaml")

    # Save to YAML
    generator.save_manifest(manifest, output_path)
    print(f"✓ Saved manifest to: {output_path}")

    # Load it back
    loaded_manifest = generator.load_manifest(output_path)
    print(f"✓ Loaded manifest with {len(loaded_manifest.properties)} properties")

    # Verify property lookup works
    account_tier = loaded_manifest.get_property_by_terraform_param("account_tier")
    if account_tier:
        print(f"✓ Found 'account_tier' mapping:")
        print(f"  Azure path: {account_tier.azure_path}")
        print(f"  Required: {account_tier.required}")
        print(f"  Valid values: {account_tier.valid_values}")
    print()


def example_validate_manifest(manifest: ResourceManifest) -> None:
    """Validate manifest for correctness."""
    print("Example 3: Validating manifests")
    print("=" * 60)

    validator = ManifestValidator()
    result = validator.validate(manifest)

    print(f"Validation result: {'✓ VALID' if result.valid else '✗ INVALID'}")
    print(f"Total issues: {len(result.issues)}")

    if result.issues:
        print("\nIssues found:")
        print(result.format_issues())
    else:
        print("✓ No issues found - manifest is valid")
    print()


def example_create_invalid_manifest() -> None:
    """Create an intentionally invalid manifest to show validation."""
    print("Example 4: Validating invalid manifest")
    print("=" * 60)

    # Create manifest with issues
    manifest = ResourceManifest(
        resource_type={
            "azure": "InvalidType",  # Missing slash
            "terraform": "wrong_prefix_storage",  # Should start with azurerm_
        },
        provider_version=ProviderVersion(min="invalid.version"),  # Invalid format
        properties=[
            PropertyMapping(
                azure_path="invalid-path!",  # Invalid characters
                terraform_param="InvalidParam",  # Not snake_case
                required=True,
                criticality=CriticalityLevel.LOW,  # Inconsistent: required but low
                type=PropertyType.BOOLEAN,
                valid_values=[True, False, "Maybe"],  # Too many for boolean
            ),
            PropertyMapping(
                azure_path="name",
                terraform_param="name",
                required=True,
                criticality=CriticalityLevel.CRITICAL,
                type=PropertyType.STRING,
            ),
            PropertyMapping(
                azure_path="name",  # Duplicate!
                terraform_param="duplicate_name",
                required=False,
                criticality=CriticalityLevel.MEDIUM,
                type=PropertyType.STRING,
            ),
        ],
    )

    validator = ManifestValidator()
    result = validator.validate(manifest)

    print(f"Validation result: {'✓ VALID' if result.valid else '✗ INVALID'}")
    print(f"\nFound {len(result.get_errors())} errors and {len(result.get_warnings())} warnings:")
    print(result.format_issues())
    print()


def example_generate_from_schemas() -> None:
    """Generate manifest from schema definitions."""
    print("Example 5: Generating manifest from schemas")
    print("=" * 60)

    # Simulated Azure schema (simplified)
    azure_schema = {
        "properties": {
            "name": {"type": "string", "required": True},
            "properties": {
                "type": "object",
                "properties": {
                    "accountTier": {
                        "type": "string",
                        "enum": ["Standard", "Premium"],
                        "description": "Storage account tier",
                    },
                    "replication": {
                        "type": "string",
                        "enum": ["LRS", "GRS"],
                    },
                },
            },
        }
    }

    # Simulated Terraform schema (simplified)
    terraform_schema = {
        "block": {
            "attributes": {
                "name": {"type": "string", "required": True},
                "account_tier": {
                    "type": "string",
                    "enum": ["Standard", "Premium"],
                    "default": "Standard",
                },
                "account_replication_type": {
                    "type": "string",
                    "enum": ["LRS", "GRS"],
                },
            }
        }
    }

    generator = ManifestGenerator()
    manifest = generator.generate_from_schemas(
        azure_schema=azure_schema,
        terraform_schema=terraform_schema,
        azure_resource_type="Microsoft.Storage/storageAccounts",
        terraform_resource_type="azurerm_storage_account",
        provider_version_min="3.0.0",
        provider_version_max="4.99.99",
    )

    print(f"✓ Generated manifest with {len(manifest.properties)} properties")
    for prop in manifest.properties:
        print(f"  - {prop.terraform_param} ← {prop.azure_path} ({prop.criticality.value})")
    print()


def main() -> None:
    """Run all examples."""
    print("\n" + "=" * 60)
    print("Property Manifest Brick - Usage Examples")
    print("=" * 60 + "\n")

    # Example 1: Create programmatically
    manifest = example_create_manifest_programmatically()

    # Example 2: Save and load
    example_save_and_load_manifest(manifest)

    # Example 3: Validate valid manifest
    example_validate_manifest(manifest)

    # Example 4: Validate invalid manifest
    example_create_invalid_manifest()

    # Example 5: Generate from schemas
    example_generate_from_schemas()

    print("=" * 60)
    print("All examples completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
