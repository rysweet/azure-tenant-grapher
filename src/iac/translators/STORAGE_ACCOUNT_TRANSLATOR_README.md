# StorageAccountTranslator Implementation

## Overview

The `StorageAccountTranslator` is part of the Phase 2 implementation of the cross-tenant translation system for Azure Tenant Grapher. It handles translation of Azure Storage Account cross-tenant references during Infrastructure-as-Code (IaC) generation.

## Files Created

### 1. `base_translator.py`
**Purpose**: Abstract base class for all resource translators

**Key Components**:
- `TranslationContext`: Context data passed to all translators (subscription IDs, tenant IDs, available resources)
- `TranslationResult`: Represents the result of translating a single property
- `BaseTranslator`: Abstract base class with common functionality

**Key Methods**:
- `supported_resource_types`: Property declaring which resource types the translator handles
- `can_translate()`: Determines if a resource needs translation
- `translate()`: Performs the actual translation
- `get_translation_results()`: Returns list of translation results for reporting
- `get_report()`: Generates statistics report

**Helper Methods**:
- `_parse_resource_id()`: Parses Azure resource IDs into components
- `_is_cross_subscription_reference()`: Checks if a resource ID references another subscription
- `_translate_resource_id()`: Translates resource IDs between subscriptions
- `_check_target_exists()`: Validates that target resources exist in generated IaC
- `_azure_type_to_terraform_type()`: Maps Azure resource types to Terraform types
- `_add_result()`: Tracks translation results for reporting

### 2. `storage_account_translator.py`
**Purpose**: Concrete translator for Azure Storage Account resources

**Supported Resource Types**:
- `azurerm_storage_account`

**Translation Capabilities**:

1. **Resource IDs**
   - Translates storage account resource IDs from source to target subscription
   - Example: `/subscriptions/SOURCE/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/storage1` → `/subscriptions/TARGET/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/storage1`

2. **Connection Strings**
   - Parses Azure Storage connection strings
   - Validates account names against available resources
   - Warns if referenced accounts don't exist in target
   - Format: `DefaultEndpointsProtocol=https;AccountName=xxx;AccountKey=xxx;EndpointSuffix=core.windows.net`

3. **Endpoint URIs**
   - Handles blob, file, table, queue, and DFS endpoints
   - Validates storage account names in URIs
   - Supports patterns:
     - `https://{account}.blob.core.windows.net/`
     - `https://{account}.file.core.windows.net/`
     - `https://{account}.table.core.windows.net/`
     - `https://{account}.queue.core.windows.net/`
     - `https://{account}.dfs.core.windows.net/`
   - Warns about custom domains that may need manual review

**Key Methods**:
- `can_translate()`: Checks if resource has translatable properties
- `translate()`: Translates all storage account references
- `_translate_connection_string()`: Parses and validates connection strings
- `_translate_endpoint_uri()`: Translates storage endpoint URIs

**Properties Translated**:
- `id`: Resource ID
- `primary_connection_string`: Primary connection string
- `secondary_connection_string`: Secondary connection string
- `primary_blob_endpoint`: Primary blob endpoint URI
- `secondary_blob_endpoint`: Secondary blob endpoint URI
- `primary_file_endpoint`: Primary file share endpoint URI
- `secondary_file_endpoint`: Secondary file share endpoint URI
- `primary_table_endpoint`: Primary table endpoint URI
- `secondary_table_endpoint`: Secondary table endpoint URI
- `primary_queue_endpoint`: Primary queue endpoint URI
- `secondary_queue_endpoint`: Secondary queue endpoint URI
- `primary_dfs_endpoint`: Primary Data Lake Storage Gen2 endpoint URI
- `secondary_dfs_endpoint`: Secondary Data Lake Storage Gen2 endpoint URI

## Design Philosophy

### Conservative Approach
- Only translates when necessary (cross-subscription references)
- Skips Terraform variables (e.g., `${var.storage_account}`)
- Preserves original values when translation is not needed

### Defensive Programming
- Validates all inputs
- Handles malformed data gracefully
- Comprehensive error handling with try-catch blocks
- Returns original values on errors

### Informative Warnings
- Warns when referenced resources don't exist in target
- Warns when connection strings reference different accounts
- Warns about custom domains needing manual review
- All warnings are tracked and included in reports

### Comprehensive Tracking
- Records all translation attempts
- Tracks modified vs. unmodified properties
- Generates detailed reports with statistics
- Supports debugging and auditing

## Integration with Translation System

### Registration
The translator registers itself automatically using the `@register_translator` decorator:

```python
@register_translator
class StorageAccountTranslator(BaseTranslator):
    ...
```

### Discovery and Instantiation
The `TranslatorRegistry` discovers and instantiates translators:

```python
from src.iac.translators import TranslatorRegistry, TranslationContext

context = TranslationContext(
    source_subscription_id="source-sub",
    target_subscription_id="target-sub",
    available_resources={...}
)

translators = TranslatorRegistry.create_translators(context)
```

### Orchestration
The `TranslationCoordinator` orchestrates all translators:

```python
from src.iac.translators import TranslationCoordinator, TranslationContext

coordinator = TranslationCoordinator(context)
translated_resources = coordinator.translate_resources(resources)
report = coordinator.format_translation_report()
```

## Usage Examples

### Basic Usage

```python
from src.iac.translators import StorageAccountTranslator, TranslationContext

# Create context
context = TranslationContext(
    source_subscription_id="11111111-1111-1111-1111-111111111111",
    target_subscription_id="22222222-2222-2222-2222-222222222222",
    available_resources={
        "azurerm_storage_account": {
            "storage1": {
                "name": "storage1",
                "id": "/subscriptions/22222222-2222-2222-2222-222222222222/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1"
            }
        }
    }
)

# Create translator
translator = StorageAccountTranslator(context)

# Translate a resource
resource = {
    "type": "azurerm_storage_account",
    "name": "storage1",
    "id": "/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1",
    "primary_connection_string": "DefaultEndpointsProtocol=https;AccountName=storage1;AccountKey=xxx",
    "primary_blob_endpoint": "https://storage1.blob.core.windows.net/"
}

if translator.can_translate(resource):
    translated = translator.translate(resource)

    # Get results
    results = translator.get_translation_results()
    for result in results:
        if result.was_modified:
            print(f"Translated {result.property_path}:")
            print(f"  From: {result.original_value}")
            print(f"  To: {result.translated_value}")
            if result.warnings:
                print(f"  Warnings: {result.warnings}")
```

### Using with Coordinator

```python
from src.iac.translators import TranslationCoordinator, TranslationContext

# Create context
context = TranslationContext(
    source_subscription_id="source-sub",
    target_subscription_id="target-sub",
    available_resources={...}
)

# Create coordinator (automatically discovers all translators)
coordinator = TranslationCoordinator(context)

# Translate resources
resources = [...]  # List of resources from Neo4j
translated_resources = coordinator.translate_resources(resources)

# Get report
report = coordinator.format_translation_report()
print(report)
```

## Testing

The implementation is designed for testability:

1. **Unit Tests**: Test individual methods in isolation
2. **Integration Tests**: Test translator with coordinator
3. **Edge Cases**: Handle malformed data, missing fields, custom domains

### Test Coverage Areas

- Resource ID translation
- Connection string parsing and validation
- Endpoint URI translation
- Cross-subscription reference detection
- Target resource existence checking
- Warning generation
- Result tracking and reporting
- Edge cases (empty strings, None values, Terraform variables)

## Future Enhancements

Potential future improvements:

1. **Account Name Remapping**: Support for remapping storage account names between environments
2. **Custom Domain Handling**: Better support for custom domain endpoints
3. **Managed Identity Integration**: Translation of managed identity references to storage accounts
4. **Private Endpoint Support**: Enhanced integration with PrivateEndpointTranslator
5. **SAS Token Translation**: Support for translating Shared Access Signatures

## Limitations

Current limitations to be aware of:

1. **Storage Account Names**: Assumes storage account names remain the same between source and target
2. **Connection String Keys**: Does not translate AccountKey values (by design - keys are environment-specific)
3. **Custom Domains**: Custom domain endpoints generate warnings but are not automatically translated
4. **Sovereign Clouds**: Currently assumes Azure Public Cloud endpoint suffixes

## Related Components

- `BaseTranslator`: Parent class providing common functionality
- `PrivateEndpointTranslator`: Handles private endpoint connections to storage accounts
- `TranslationCoordinator`: Orchestrates all translators
- `TranslatorRegistry`: Discovers and manages translators
- `TranslationContext`: Provides context data to translators

## References

- Azure Storage Account Documentation: https://learn.microsoft.com/en-us/azure/storage/common/storage-account-overview
- Azure Storage Connection Strings: https://learn.microsoft.com/en-us/azure/storage/common/storage-configure-connection-string
- Azure Storage Endpoints: https://learn.microsoft.com/en-us/azure/storage/common/storage-account-endpoints
