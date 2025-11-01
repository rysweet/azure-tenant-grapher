# TranslationCoordinator Usage Guide

## Overview

The `TranslationCoordinator` orchestrates all registered translators during IaC generation to handle cross-tenant resource reference translation.

## Basic Usage

### 1. Simple Translation

```python
from src.iac.translators import TranslationContext, TranslationCoordinator

# Create translation context
context = TranslationContext(
    source_subscription_id="source-sub-123",
    target_subscription_id="target-sub-456",
    available_resources={
        "azurerm_storage_account": {
            "storage1": {"id": "/subscriptions/target-sub-456/..."}
        }
    },
)

# Initialize coordinator
coordinator = TranslationCoordinator(context)

# Translate resources
resources = [
    {"type": "azurerm_storage_account", "name": "storage1"},
    {"type": "azurerm_key_vault", "name": "keyvault1"},
]

translated_resources = coordinator.translate_resources(resources)

# Generate report
print(coordinator.format_translation_report())
```

### 2. With Identity Mapping (Entra ID Translation)

```python
context = TranslationContext(
    source_subscription_id="source-sub-123",
    target_subscription_id="target-sub-456",
    source_tenant_id="source-tenant-aaa",
    target_tenant_id="target-tenant-bbb",
    identity_mapping_file="/path/to/identity-mapping.json",
    strict_mode=True,  # Fail on missing mappings
    available_resources=resources_dict,
)

coordinator = TranslationCoordinator(context)
translated = coordinator.translate_resources(resources)
```

### 3. Integration with TerraformEmitter

```python
from pathlib import Path
from src.iac.translators import TranslationContext, TranslationCoordinator

class TerraformEmitter:
    def emit(self, graph, output_dir: Path, **kwargs):
        # Extract resources from graph
        resources = self._extract_resources(graph)

        # Create translation context
        context = TranslationContext(
            source_subscription_id=self.source_subscription_id,
            target_subscription_id=self.target_subscription_id,
            available_resources=self._build_resource_map(resources),
        )

        # Initialize coordinator and translate
        coordinator = TranslationCoordinator(context)
        translated_resources = coordinator.translate_resources(resources)

        # Emit translated resources
        self._emit_terraform(translated_resources, output_dir)

        # Save translation report
        coordinator.save_translation_report(
            output_path=str(output_dir / "translation_report.txt"),
            format="text"
        )
        coordinator.save_translation_report(
            output_path=str(output_dir / "translation_report.json"),
            format="json"
        )

        # Print report to console
        print(coordinator.format_translation_report())
```

## TranslationContext Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `source_subscription_id` | `str \| None` | Yes | Source subscription ID from discovery |
| `target_subscription_id` | `str` | Yes | Target subscription ID for deployment |
| `source_tenant_id` | `str \| None` | No | Source tenant ID for Entra ID translation |
| `target_tenant_id` | `str \| None` | No | Target tenant ID for Entra ID translation |
| `available_resources` | `dict` | No | Resources being generated (for validation) |
| `identity_mapping_file` | `str \| None` | No | Path to identity mapping JSON file |
| `strict_mode` | `bool` | No | If True, fail on missing mappings |

## Report Formats

### Text Report

```
======================================================================
Cross-Tenant Translation Report
======================================================================

Total Translators: 3
Total Translations: 47
Total Warnings: 2
Total Errors: 0

Translator Details:
----------------------------------------------------------------------

PrivateEndpointTranslator:
  Processed: 12
  Translated: 8
  Warnings: 0
  Sample Translations:
    • Microsoft.Network/privateEndpoints
      Property: properties.privateLinkServiceConnections[0].privateLinkServiceId
      Original: /subscriptions/source-sub-id/resourceGroups/rg1/providers/...
      Translated: /subscriptions/target-sub-id/resourceGroups/rg1/providers/...
```

### JSON Report

```json
{
  "summary": {
    "total_translators": 3,
    "total_translations": 47,
    "total_warnings": 2,
    "total_missing_targets": 0,
    "total_errors": 0
  },
  "translators": [
    {
      "translator": "PrivateEndpointTranslator",
      "total_resources_processed": 12,
      "translations_performed": 8,
      "warnings": 0,
      "missing_targets": 0,
      "results": [...]
    }
  ]
}
```

## Translation Statistics

Get detailed statistics programmatically:

```python
coordinator = TranslationCoordinator(context)
translated = coordinator.translate_resources(resources)

# Get statistics
stats = coordinator.get_translation_statistics()

print(f"Processed: {stats['resources_processed']}")
print(f"Translated: {stats['resources_translated']}")
print(f"Warnings: {stats['total_warnings']}")
print(f"Errors: {stats['total_errors']}")

# Per-translator stats
for translator_stat in stats['translators']:
    print(f"{translator_stat['translator']}: {translator_stat['translations_performed']} translations")
```

## Error Handling

The coordinator is designed for graceful degradation:

```python
coordinator = TranslationCoordinator(context)

# Translators that fail during initialization are logged and skipped
# Translators that fail during translation are logged and skipped
# The original resource is returned if all translators fail

translated = coordinator.translate_resources(resources)

# Check for errors
stats = coordinator.get_translation_statistics()
if stats['total_errors'] > 0:
    print(f"Warning: {stats['total_errors']} translation errors occurred")
    # Resources were returned unchanged where errors occurred
```

## Registering Custom Translators

To add a new translator that will be automatically discovered:

```python
from src.iac.translators import register_translator
from src.iac.translators.base_translator import BaseTranslator

@register_translator
class MyCustomTranslator(BaseTranslator):
    """Translates custom resource references."""

    def can_translate(self, resource):
        return resource.get("type") == "azurerm_custom_resource"

    def translate(self, resource):
        # Translation logic here
        return resource

    def get_report(self):
        return {
            "translator": self.__class__.__name__,
            "total_resources_processed": len(self.translation_results),
            "translations_performed": sum(
                1 for r in self.translation_results if r.was_translated
            ),
            "warnings": 0,
            "missing_targets": 0,
        }
```

Once registered, the translator will be automatically discovered and used by the coordinator.

## Best Practices

### 1. Always Create Translation Context with Available Resources

```python
# Good: Provides resource map for validation
context = TranslationContext(
    source_subscription_id=source_sub,
    target_subscription_id=target_sub,
    available_resources=resource_map,  # For target validation
)

# Bad: Missing available_resources
context = TranslationContext(
    source_subscription_id=source_sub,
    target_subscription_id=target_sub,
)
```

### 2. Save Reports for Debugging

```python
# Save both text and JSON formats
coordinator.save_translation_report(f"{output_dir}/translation_report.txt", format="text")
coordinator.save_translation_report(f"{output_dir}/translation_report.json", format="json")
```

### 3. Check for Warnings and Errors

```python
stats = coordinator.get_translation_statistics()

if stats['total_warnings'] > 0:
    logger.warning(f"Translation completed with {stats['total_warnings']} warnings")

if stats['total_errors'] > 0:
    logger.error(f"Translation had {stats['total_errors']} errors")
    # Decide whether to proceed or abort
```

### 4. Use Strict Mode for Production

```python
# In production, use strict mode to catch missing mappings early
context = TranslationContext(
    source_subscription_id=source_sub,
    target_subscription_id=target_sub,
    strict_mode=True,  # Fail fast on missing mappings
)
```

## Performance Considerations

### Large Resource Sets

The coordinator processes resources sequentially and logs progress:

```python
# For 500+ resources, progress is logged every 100 resources
coordinator.translate_resources(large_resource_list)
# Output:
# INFO: Translated 100/500 resources...
# INFO: Translated 200/500 resources...
```

### Translator Efficiency

- Translators are instantiated once during coordinator initialization
- `can_translate()` checks are fast (dict lookups)
- Translation is only performed on applicable resources

### Memory Usage

The coordinator creates copies of resources during translation to avoid modifying originals:

```python
# Original resources remain unchanged
translated = coordinator.translate_resources(resources)
assert resources[0] is not translated[0]  # Different objects
```

## Troubleshooting

### No Translators Found

```python
coordinator = TranslationCoordinator(context)
# Warning logged: "No translators registered in TranslatorRegistry"

# Solution: Ensure translators are imported before creating coordinator
from src.iac.translators import PrivateEndpointTranslator  # Auto-registers
```

### Translator Instantiation Failures

```python
# Error logged: "Failed to instantiate translator MyTranslator: ..."
# Coordinator continues with other translators

# Solution: Check translator __init__ accepts TranslationContext
```

### Resources Not Being Translated

```python
# Check if translator is registered
from src.iac.translators.registry import TranslatorRegistry
print(TranslatorRegistry.get_registered_translators())

# Check if translator can handle the resource
translator = MyTranslator(context)
print(translator.can_translate(resource))  # Should return True
```

## Related Documentation

- **BaseTranslator**: (To be implemented) - Abstract base class for all translators
- **TranslatorRegistry**: `/src/iac/translators/registry.py` - Translator discovery and registration
- **PrivateEndpointTranslator**: `/src/iac/translators/private_endpoint_translator.py` - Example translator implementation
- **Architecture**: `/UNIFIED_TRANSLATION_ARCHITECTURE.md` - Overall design and integration

## Examples

See `/src/iac/translators/USAGE_EXAMPLE.md` for complete examples and integration patterns.
