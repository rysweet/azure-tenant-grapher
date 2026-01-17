# Property Manifest Brick

## Overview

The Property Manifest brick provides YAML-based property mapping definitions between Azure resources and Terraform configurations. It follows the **Bricks & Studs** philosophy - a self-contained, regeneratable module with clear public interfaces.

## Philosophy

- **Self-contained**: All functionality in one module
- **Standard library focus**: Uses only PyYAML beyond standard library
- **Clear separation**: Schema, Generator, Validator are distinct concerns
- **Regeneratable**: Can be rebuilt from specification

## Public API (The "Studs")

### Data Models (`schema.py`)

- `PropertyMapping`: Individual property mapping definition
- `ResourceManifest`: Complete resource type manifest
- `ProviderVersion`: Terraform provider version constraints
- `CriticalityLevel`: Property criticality enumeration (CRITICAL, HIGH, MEDIUM, LOW)
- `PropertyType`: Property type enumeration (STRING, INTEGER, BOOLEAN, OBJECT, ARRAY, NUMBER)

### Generator (`generator.py`)

- `ManifestGenerator`: Generate manifests from Azure/Terraform schemas
  - `generate_from_schemas()`: Create manifest from schema definitions
  - `save_manifest()`: Save manifest to YAML file
  - `load_manifest()`: Load manifest from YAML file
  - `generate_template_manifest()`: Create empty template for manual completion

### Validator (`validator.py`)

- `ManifestValidator`: Validate manifest correctness
  - `validate()`: Validate manifest structure and content
  - `validate_file()`: Validate manifest from file
- `ValidationResult`: Result of validation with issues
- `ValidationIssue`: Individual validation issue

## YAML Schema Format

```yaml
resource_type:
  azure: Microsoft.Storage/storageAccounts
  terraform: azurerm_storage_account

provider_version:
  min: "3.0.0"
  max: "4.99.99"

metadata:
  description: "Storage account property mappings"
  last_updated: "2026-01-17"

properties:
  - azure_path: properties.accountTier
    terraform_param: account_tier
    required: true
    criticality: CRITICAL
    type: string
    valid_values: [Standard, Premium]
    default_value: Standard
    description: "Storage account tier"
    notes: "Additional context about mapping"
```

## Usage Examples

### Creating a Manifest Programmatically

```python
from src.iac.property_validation.manifest import (
    CriticalityLevel,
    PropertyMapping,
    PropertyType,
    ProviderVersion,
    ResourceManifest,
)

# Create property mappings
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
    ),
]

# Create manifest
manifest = ResourceManifest(
    resource_type={
        "azure": "Microsoft.Storage/storageAccounts",
        "terraform": "azurerm_storage_account",
    },
    provider_version=ProviderVersion(min="3.0.0", max="4.99.99"),
    properties=properties,
)
```

### Saving and Loading Manifests

```python
from pathlib import Path
from src.iac.property_validation.manifest import ManifestGenerator

generator = ManifestGenerator()

# Save to YAML
output_path = Path("manifests/storage_account.yaml")
generator.save_manifest(manifest, output_path)

# Load from YAML
loaded_manifest = generator.load_manifest(output_path)
```

### Validating Manifests

```python
from src.iac.property_validation.manifest import ManifestValidator

validator = ManifestValidator()

# Validate manifest object
result = validator.validate(manifest)

if result.valid:
    print("✓ Manifest is valid")
else:
    print(f"✗ Found {len(result.get_errors())} errors")
    print(result.format_issues())

# Validate from file
file_result = validator.validate_file(Path("manifests/storage_account.yaml"))
```

### Generating from Schemas

```python
from src.iac.property_validation.manifest import ManifestGenerator

generator = ManifestGenerator()

# Generate from Azure and Terraform schemas
manifest = generator.generate_from_schemas(
    azure_schema=azure_resource_schema,
    terraform_schema=terraform_provider_schema,
    azure_resource_type="Microsoft.Storage/storageAccounts",
    terraform_resource_type="azurerm_storage_account",
    provider_version_min="3.0.0",
    provider_version_max="4.99.99",
)
```

### Property Lookup

```python
# Find property by Terraform parameter name
prop = manifest.get_property_by_terraform_param("account_tier")
if prop:
    print(f"Azure path: {prop.azure_path}")
    print(f"Criticality: {prop.criticality.value}")

# Find property by Azure JSON path
prop = manifest.get_property_by_azure_path("properties.accountTier")

# Get filtered properties
critical_props = manifest.get_critical_properties()
required_props = manifest.get_required_properties()
```

## Validation Rules

The validator checks:

1. **Resource Type**: Valid Azure and Terraform resource type format
2. **Provider Version**: Valid semantic version format (X.Y.Z)
3. **Property Paths**: Valid Azure path format (alphanumeric with dots)
4. **Terraform Parameters**: Valid snake_case naming
5. **No Duplicates**: No duplicate Azure paths or Terraform parameters
6. **Consistency**: Required properties should have appropriate criticality
7. **Valid Values**: Consistent with property types
8. **Coverage**: Reasonable distribution of criticality levels

## Criticality Levels

| Level    | Usage                              | Examples                              |
| -------- | ---------------------------------- | ------------------------------------- |
| CRITICAL | Must match exactly                 | Names, IDs, SKUs, core configurations |
| HIGH     | Should match                       | Security settings, compliance configs |
| MEDIUM   | Important but flexible             | Tags, descriptions, optional features |
| LOW      | Nice to have                       | Display settings, UI preferences      |

## Pre-defined Manifests

Pre-defined manifests are stored in `mappings/`:

- `storage_account.yaml`: Azure Storage Account mappings

## Module Structure

```
manifest/
├── __init__.py           # Public interface via __all__
├── README.md            # This file
├── schema.py            # Data classes for manifest structure
├── generator.py         # Generate manifests from schemas
├── validator.py         # Validate manifest correctness
├── examples/
│   └── basic_usage.py   # Usage examples
└── mappings/
    └── storage_account.yaml  # Pre-defined manifests
```

## Testing

Run the basic usage example:

```bash
python -c "
import sys
from pathlib import Path
sys.path.insert(0, 'src/iac/property_validation')
from manifest.generator import ManifestGenerator
from manifest.validator import ManifestValidator

# Load pre-defined manifest
generator = ManifestGenerator()
manifest = generator.load_manifest(Path('src/iac/property_validation/manifest/mappings/storage_account.yaml'))

# Validate it
validator = ManifestValidator()
result = validator.validate(manifest)
print(f'Valid: {result.valid}')
print(f'Properties: {len(manifest.properties)}')
"
```

## Design Decisions

### Why YAML?

- Human-readable and editable
- Standard format for configuration
- Good balance between structure and simplicity
- Easy to version control

### Why Dataclasses?

- Type safety with Python 3.7+ type hints
- Automatic `__init__`, `__repr__`, `__eq__`
- Clear, explicit structure
- Easy to serialize/deserialize

### Why Separate Generator and Validator?

- Single Responsibility Principle
- Generator can be used without validation (trusted sources)
- Validator can validate manually-created manifests
- Different concerns, different modules

## Future Enhancements

Possible future additions (following ruthless simplicity):

1. **Fuzzy Matching**: Better property name matching between Azure/Terraform
2. **Diff Tool**: Compare two manifests to identify changes
3. **Merge Tool**: Combine multiple manifests intelligently
4. **CLI Tool**: Command-line interface for common operations
5. **Schema Inference**: Automatically infer schemas from live resources

Each enhancement should be evaluated against the philosophy: does it add proportional value?

## Related Modules

- **Schema Loader**: Loads Azure resource schemas
- **Validation Engine**: Uses manifests to validate property coverage
- **Reporter**: Generates reports based on manifest data

## Contributing

When modifying this brick:

1. Maintain the public API (`__all__` in `__init__.py`)
2. Ensure all code has full type hints
3. Keep it self-contained (minimal dependencies)
4. Update README with any API changes
5. Follow the philosophy: ruthless simplicity

## License

Part of Azure Tenant Grapher project.
