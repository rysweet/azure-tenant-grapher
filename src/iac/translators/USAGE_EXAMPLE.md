# TranslatorRegistry Usage Guide

This document demonstrates how to use the `TranslatorRegistry` for auto-discovery and management of resource translators.

## Quick Start

### 1. Creating a Translator

Create a new translator by inheriting from `BaseTranslator` and using the `@register_translator` decorator:

```python
from src.iac.translators.registry import register_translator

@register_translator
class MyResourceTranslator(BaseTranslator):
    """Translator for my Azure resource type."""

    # Optional: Define supported resource types as a class attribute
    supported_resource_types = ["Microsoft.MyService/myResources"]

    def __init__(self, context):
        super().__init__(context)
        # Add any custom initialization here

    def can_translate(self, resource):
        """Check if this translator can handle the given resource."""
        resource_type = resource.get("type", "")
        return resource_type in self.supported_resource_types

    def translate(self, resource):
        """Translate resource references for cross-tenant deployment."""
        # Your translation logic here
        translated = resource.copy()

        # Example: Translate subscription IDs in resource IDs
        if "id" in translated:
            old_id = translated["id"]
            new_id = old_id.replace(
                self.context.source_subscription_id,
                self.context.target_subscription_id
            )
            translated["id"] = new_id

            # Record the translation
            result = TranslationResult(
                original_value=old_id,
                translated_value=new_id,
                was_translated=True,
                translator_name=self.__class__.__name__,
                resource_type=resource.get("type", ""),
            )
            self._record_translation(result)

        return translated

    def get_translation_results(self):
        """Get all translation results."""
        return self.translation_results
```

### 2. Using the Registry

The translator is automatically registered when the module is imported:

```python
from src.iac.translators import TranslatorRegistry
from src.iac.translators.base_translator import TranslationContext

# Create a translation context
context = TranslationContext(
    source_subscription_id="source-sub-123",
    target_subscription_id="target-sub-456",
)

# Get all registered translators
translator_names = TranslatorRegistry.get_registered_translators()
print(f"Registered translators: {translator_names}")

# Create instances of all translators
translators = TranslatorRegistry.create_translators(context)

# Get a specific translator by resource type
translator_class = TranslatorRegistry.get_translator("Microsoft.MyService/myResources")
if translator_class:
    translator = translator_class(context)
```

### 3. Translating Resources

```python
# Example resource
resource = {
    "type": "Microsoft.MyService/myResources",
    "name": "my-resource",
    "id": "/subscriptions/source-sub-123/resourceGroups/rg1/providers/Microsoft.MyService/myResources/my-resource",
}

# Translate using all applicable translators
translated_resource = resource
for translator in translators:
    if translator.can_translate(translated_resource):
        translated_resource = translator.translate(translated_resource)

print(f"Original ID: {resource['id']}")
print(f"Translated ID: {translated_resource['id']}")
```

## Advanced Features

### Multiple Resource Types

A single translator can handle multiple resource types:

```python
@register_translator
class MultiTypeTranslator(BaseTranslator):
    supported_resource_types = [
        "Microsoft.Storage/storageAccounts",
        "Microsoft.Storage/blobServices",
        "Microsoft.Storage/fileServices",
    ]

    def can_translate(self, resource):
        return resource.get("type") in self.supported_resource_types
```

### Getting Supported Resource Types

```python
supported_types = TranslatorRegistry.get_supported_resource_types()
print(f"All supported types: {supported_types}")
```

### Thread Safety

The registry is thread-safe and uses locks internally:

```python
import threading

def register_my_translator():
    @register_translator
    class ThreadSafeTranslator(BaseTranslator):
        # Implementation here
        pass

# Safe to call from multiple threads
threads = [threading.Thread(target=register_my_translator) for _ in range(10)]
for t in threads:
    t.start()
for t in threads:
    t.join()
```

### Testing with the Registry

For tests, you can clear the registry between test cases:

```python
import pytest
from src.iac.translators import TranslatorRegistry

@pytest.fixture(autouse=True)
def clean_registry():
    """Clear registry before and after each test."""
    TranslatorRegistry.clear()
    yield
    TranslatorRegistry.clear()
```

## Integration with IaC Pipeline

The registry is designed to integrate seamlessly with the Terraform emitter:

```python
from src.iac.emitters.terraform_emitter import TerraformEmitter
from src.iac.translators import TranslatorRegistry
from src.iac.translators.base_translator import TranslationContext

# Create translation context
context = TranslationContext(
    source_subscription_id=source_sub,
    target_subscription_id=target_sub,
)

# Create all translators
translators = TranslatorRegistry.create_translators(context)

# In the emitter's emit() method:
for resource in resources:
    # Apply all applicable translators
    for translator in translators:
        if translator.can_translate(resource):
            resource = translator.translate(resource)

    # Emit the translated resource
    emit_resource(resource)

# Generate translation report
for translator in translators:
    report = translator.get_report()
    print(f"Translator: {report['translator']}")
    print(f"  Translations: {report['translations_performed']}")
    print(f"  Warnings: {report['warnings']}")
```

## Best Practices

1. **Single Responsibility**: Each translator should handle one specific translation concern
2. **Clear Naming**: Use descriptive names like `StorageAccountTranslator`, not `Translator1`
3. **Comprehensive Tests**: Test both the happy path and edge cases
4. **Error Handling**: Use try/except blocks and record warnings in `TranslationResult`
5. **Logging**: Log at appropriate levels (DEBUG for details, INFO for key actions, WARNING for issues)
6. **Documentation**: Include docstrings explaining what the translator does

## Example: Complete Translator

Here's a complete example of a storage account translator:

```python
import logging
import re
from src.iac.translators.registry import register_translator
from src.iac.translators.base_translator import (
    BaseTranslator,
    TranslationResult,
)

logger = logging.getLogger(__name__)

CONNECTION_STRING_PATTERN = re.compile(
    r"DefaultEndpointsProtocol=(?P<protocol>https?);AccountName=(?P<account>[^;]+);.*"
)

@register_translator
class StorageAccountTranslator(BaseTranslator):
    """
    Translates Azure Storage Account references.

    Handles:
    - Resource IDs in private endpoint connections
    - Connection strings in app settings
    - Storage endpoints
    """

    supported_resource_types = [
        "Microsoft.Storage/storageAccounts",
        "Microsoft.Web/sites",  # For app settings
    ]

    def can_translate(self, resource):
        return resource.get("type") in self.supported_resource_types

    def translate(self, resource):
        resource = resource.copy()
        resource_type = resource.get("type", "")

        if "Microsoft.Storage/storageAccounts" in resource_type:
            resource = self._translate_storage_account(resource)
        elif "Microsoft.Web/sites" in resource_type:
            resource = self._translate_app_settings(resource)

        return resource

    def _translate_storage_account(self, resource):
        # Translate private endpoint connections
        properties = resource.get("properties", {})
        pe_connections = properties.get("privateEndpointConnections", [])

        for connection in pe_connections:
            pe_id = connection.get("id", "")
            if self._should_translate(pe_id):
                translated_id = self._translate_resource_id(pe_id)
                connection["id"] = translated_id

                result = TranslationResult(
                    original_value=pe_id,
                    translated_value=translated_id,
                    was_translated=True,
                    translator_name=self.__class__.__name__,
                    resource_type=resource.get("type", ""),
                    property_path="properties.privateEndpointConnections[].id",
                )
                self._record_translation(result)

        return resource

    def _translate_app_settings(self, resource):
        # Translate storage connection strings
        properties = resource.get("properties", {})
        app_settings = properties.get("appSettings", [])

        for setting in app_settings:
            value = setting.get("value", "")
            if CONNECTION_STRING_PATTERN.match(value):
                # Replace with Terraform variable
                var_name = f"storage_connection_string_{setting['name']}"
                placeholder = f"${{var.{var_name}}}"

                result = TranslationResult(
                    original_value=value[:50] + "...",  # Truncate for security
                    translated_value=placeholder,
                    was_translated=True,
                    translator_name=self.__class__.__name__,
                    resource_type=resource.get("type", ""),
                    property_path=f"properties.appSettings['{setting['name']}']",
                    warnings=[
                        f"Connection string replaced with variable. "
                        f"Define '{var_name}' in terraform.tfvars"
                    ]
                )
                self._record_translation(result)
                setting["value"] = placeholder

        return resource

    def _should_translate(self, resource_id):
        if not resource_id or not self.context.source_subscription_id:
            return False
        return self.context.source_subscription_id in resource_id

    def _translate_resource_id(self, resource_id):
        return resource_id.replace(
            f"/subscriptions/{self.context.source_subscription_id}/",
            f"/subscriptions/{self.context.target_subscription_id}/"
        )
```

## Troubleshooting

### Translator Not Being Discovered

Make sure your translator module is imported before creating instances:

```python
# Import the module containing your translator
import src.iac.translators.my_resource_translator  # noqa

# Now the translator is registered
translators = TranslatorRegistry.create_translators(context)
```

### Duplicate Registrations

If a translator is registered multiple times (e.g., due to module reloading), it will be silently ignored. Check the debug logs:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Missing Methods Error

Ensure your translator implements all required methods:
- `can_translate(resource)`
- `translate(resource)`
- `get_translation_results()`

## See Also

- [UNIFIED_TRANSLATION_ARCHITECTURE.md](../../../UNIFIED_TRANSLATION_ARCHITECTURE.md) - Overall architecture design
- [base_translator.py](./base_translator.py) - Base translator interface (when implemented)
- [private_endpoint_translator.py](./private_endpoint_translator.py) - Reference implementation
