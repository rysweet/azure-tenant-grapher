# Schema Scrapers

Extract and cache resource property schemas from Azure ARM API and Terraform providers.

## Purpose

This module provides scrapers that fetch resource schemas from:
- **Azure ARM API**: Using azure-mgmt-resource SDK for schema introspection
- **Terraform providers**: Via `terraform providers schema -json` command

Schemas are cached locally with 24-hour TTL to minimize API calls and improve performance.

## Public API

### AzureScraper

Scrapes Azure ARM API schemas using the Azure Python SDK.

```python
from schemas import AzureScraper

scraper = AzureScraper()
schema = scraper.get_resource_schema("Microsoft.Compute", "virtualMachines")
print(schema["api_versions"])  # ['2023-03-01', '2023-07-01', ...]
```

**Methods:**
- `get_resource_schema(provider, resource_type, force_refresh=False)` - Get schema for specific resource
- `list_providers()` - List all Azure resource providers
- `list_resource_types(provider)` - List resource types for a provider
- `clear_cache(provider=None)` - Clear cached schemas

### TerraformScraper

Parses Terraform provider schemas from CLI output.

```python
from schemas import TerraformScraper
from pathlib import Path

scraper = TerraformScraper(terraform_dir=Path("./terraform"))
schema = scraper.get_resource_schema("azurerm_virtual_machine")
attrs = schema["block"]["attributes"]
print(attrs["location"]["type"])  # 'string'
print(attrs["location"]["required"])  # True
```

**Methods:**
- `get_resource_schema(resource_type, force_refresh=False)` - Get schema for specific resource
- `get_provider_schema(provider_name, force_refresh=False)` - Get full provider schema
- `list_providers()` - List all configured providers
- `list_resource_types(provider=None)` - List resource types
- `extract_required_properties(resource_type)` - Get only required properties
- `extract_all_properties(resource_type, include_nested=True)` - Get all properties
- `clear_cache(provider=None)` - Clear cached schemas

## Usage Examples

### Basic Usage

```python
from schemas import AzureScraper, TerraformScraper
from pathlib import Path

# Azure scraper
azure = AzureScraper()
vm_schema = azure.get_resource_schema("Microsoft.Compute", "virtualMachines")

# Terraform scraper
terraform = TerraformScraper(terraform_dir=Path("./terraform"))
tf_schema = terraform.get_resource_schema("azurerm_virtual_machine")
```

### Property Validation Workflow

```python
# 1. Get schemas
azure_schema = azure.get_resource_schema("Microsoft.Compute", "virtualMachines")
tf_required = terraform.extract_required_properties("azurerm_virtual_machine")

# 2. Validate Terraform config
for prop_name, prop_value in tf_config.items():
    if prop_name in tf_required:
        # Validate against Terraform schema
        expected_type = tf_required[prop_name]["type"]
        validate_type(prop_value, expected_type)

# 3. Cross-reference with Azure
azure_props = azure_schema["properties"]
if prop_name in azure_props:
    validate_azure_constraints(prop_value, azure_props[prop_name])
```

### Cache Management

```python
# Custom cache location and TTL
scraper = TerraformScraper(
    terraform_dir=Path("./terraform"),
    cache_dir=Path("/custom/cache"),
    cache_ttl_hours=48
)

# Force refresh (bypass cache)
schema = scraper.get_resource_schema("azurerm_vm", force_refresh=True)

# Clear cache
scraper.clear_cache()  # All providers
scraper.clear_cache("registry.terraform.io/hashicorp/azurerm")  # Specific provider
```

## Prerequisites

### Azure Scraper

Requires Azure SDK and authentication:

```bash
pip install azure-mgmt-resource azure-identity
export AZURE_SUBSCRIPTION_ID="your-subscription-id"
az login
```

### Terraform Scraper

Requires Terraform CLI and initialized configuration:

```bash
# Install Terraform
# https://www.terraform.io/downloads

# Initialize Terraform
cd /path/to/terraform
terraform init
```

## Architecture

### Cache Structure

Schemas are cached in `~/.atg2/schemas/`:

```
~/.atg2/schemas/
├── azure/
│   ├── Microsoft_Compute_virtualMachines.json
│   └── Microsoft_Storage_storageAccounts.json
└── terraform/
    └── all_providers.json
```

### Cache Format

Each cache file contains:

```json
{
  "cached_at": "2024-01-17T10:30:00",
  "schema": {
    // Schema data
  }
}
```

### TTL Mechanism

- Default TTL: 24 hours
- Cache validity checked on every read
- Expired caches automatically refreshed
- Force refresh available via `force_refresh=True`

## Error Handling

Both scrapers raise specific exceptions:

```python
from schemas import AzureSchemaError, TerraformSchemaError

try:
    schema = azure.get_resource_schema("Invalid.Provider", "badType")
except AzureSchemaError as e:
    print(f"Azure error: {e}")

try:
    schema = terraform.get_resource_schema("nonexistent_resource")
except TerraformSchemaError as e:
    print(f"Terraform error: {e}")
```

**Common errors:**
- `AzureSchemaError`: Azure SDK not installed, authentication failed, invalid provider
- `TerraformSchemaError`: Terraform not installed, not initialized, invalid resource type

## Design Philosophy

This module follows the **brick philosophy**:

- **Self-contained**: All scraping logic in one module
- **Clear public API**: Defined via `__all__` exports
- **Standard library**: Minimal dependencies (only Azure SDK and subprocess)
- **Regeneratable**: Can be rebuilt from this specification
- **Zero-BS**: No stubs, all functions work

**Key principles:**
- Local caching with TTL to minimize external calls
- Fail-fast with clear error messages
- Comprehensive type hints
- Full docstring documentation

## Testing

Run basic tests:

```bash
cd src/iac/property_validation/schemas
python test_basic.py
```

Run example usage:

```bash
python example_usage.py
```

## Integration

This module integrates with the property validation system:

1. **Manifest Builder**: Extracts properties from Neo4j graph
2. **Schema Scrapers** ← YOU ARE HERE: Fetches schemas from Azure/Terraform
3. **Validator**: Compares manifests against schemas
4. **Reporting**: Generates validation reports

## Limitations

### Azure Scraper

- Requires Azure authentication
- SDK provides limited schema details (mainly API versions, locations)
- Full property schemas would require ARM template reference parsing
- Currently extracts metadata and capabilities

### Terraform Scraper

- Requires Terraform CLI installed
- Requires initialized Terraform configuration
- Schema output format depends on Terraform version
- Large schemas can take time to generate

## Future Enhancements

Potential improvements (not implemented):

- ARM template reference parser for full Azure schemas
- Schema comparison utilities
- Schema versioning and diff tracking
- Parallel provider fetching
- Schema validation against JSON Schema spec

## Related Documentation

- See `example_usage.py` for comprehensive examples
- See module docstrings for full API documentation
- See `../validation/` for the validation engine
- See `../manifest/` for manifest building
