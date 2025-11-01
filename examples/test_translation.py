#!/usr/bin/env python3
"""
Test Cross-Tenant Translation Offline

This script demonstrates how to use the BaseTranslator and PrivateEndpointTranslator
classes for cross-tenant resource translation WITHOUT requiring Azure connectivity.

Use this script to:
1. Understand how translation works
2. Test custom translators
3. Validate translation logic before deployment
4. Debug translation issues

Usage:
    uv run python examples/test_translation.py
    # OR
    python examples/test_translation.py  (if dependencies are installed)
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict

# Add src to path to enable imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import only what we need from the translators module
# This avoids importing heavy dependencies like neo4j
try:
    from src.iac.translators.base_translator import (
        BaseTranslator,
        TranslationContext,
        TranslationResult,
    )
    from src.iac.translators.private_endpoint_translator import PrivateEndpointTranslator
except ImportError as e:
    print(f"Error importing translators: {e}")
    print("\nTo run this script, use: uv run python examples/test_translation.py")
    print("Or ensure dependencies are installed: uv sync")
    sys.exit(1)


def print_header(title: str) -> None:
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def print_result(result) -> None:
    """Print translation result in a formatted way."""
    # Handle both old PrivateEndpointTranslator.TranslationResult
    # and new BaseTranslator.TranslationResult
    resource_type = getattr(result, "resource_type", "Unknown")
    resource_name = getattr(result, "resource_name", "Unknown")
    was_translated = getattr(result, "was_translated", False)
    warnings = getattr(result, "warnings", [])
    errors = getattr(result, "errors", [])
    translation_details = getattr(result, "translation_details", None)

    print(f"Resource Type: {resource_type}")
    print(f"Resource Name: {resource_name}")
    print(f"Was Translated: {was_translated}")

    if was_translated:
        print("\n✓ Translation performed successfully")
    else:
        print("\n- No translation needed")

    if warnings:
        print("\n⚠ Warnings:")
        for warning in warnings:
            print(f"  - {warning}")

    if errors:
        print("\n✗ Errors:")
        for error in errors:
            print(f"  - {error}")

    if translation_details:
        print("\nTranslation Details:")
        print(json.dumps(translation_details, indent=2))


def example_1_private_endpoint_translation() -> None:
    """
    Example 1: Private Endpoint Translation

    Demonstrates translating a private endpoint resource that references
    a storage account in a different subscription.
    """
    print_header("Example 1: Private Endpoint Translation")

    # Define source and target subscriptions
    source_subscription = "aaaaaaaa-1111-1111-1111-111111111111"
    target_subscription = "bbbbbbbb-2222-2222-2222-222222222222"

    # Create translation context
    context = TranslationContext(
        source_subscription_id=source_subscription,
        target_subscription_id=target_subscription,
        source_tenant_id="source-tenant-id",
        target_tenant_id="target-tenant-id",
        available_resources={
            "azurerm_storage_account": {
                "storage1": {"name": "storage1", "location": "eastus"}
            },
            "azurerm_private_endpoint": {
                "pe1": {"name": "pe1", "location": "eastus"}
            },
        },
        strict_mode=False,
    )

    # Create a sample private endpoint resource (as it would come from Neo4j)
    private_endpoint = {
        "type": "Microsoft.Network/privateEndpoints",
        "name": "storage1-pe",
        "location": "eastus",
        "properties": {
            "privateLinkServiceConnections": [
                {
                    "properties": {
                        "privateLinkServiceId": f"/subscriptions/{source_subscription}/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1"
                    }
                }
            ],
            "subnet": {
                "id": f"/subscriptions/{source_subscription}/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1"
            },
        },
    }

    print("Source Private Endpoint Resource:")
    print(json.dumps(private_endpoint, indent=2))

    # Initialize translator
    translator = PrivateEndpointTranslator(
        source_subscription_id=source_subscription,
        target_subscription_id=target_subscription,
        available_resources=context.available_resources,
    )

    # Perform translation on the resource ID
    print("\nPerforming translation on private link service connection...")
    service_id = private_endpoint["properties"]["privateLinkServiceConnections"][0][
        "properties"
    ]["privateLinkServiceId"]
    print(f"Original Service ID: {service_id}")

    result = translator.translate_resource_id(service_id)

    print(f"\nTranslated Service ID: {result.translated_id}")

    # Also translate the subnet ID
    subnet_id = private_endpoint["properties"]["subnet"]["id"]
    print(f"\nOriginal Subnet ID: {subnet_id}")

    subnet_result = translator.translate_resource_id(subnet_id)
    print(f"Translated Subnet ID: {subnet_result.translated_id}")

    print("\n")
    print_result(result)


def example_2_custom_translator() -> None:
    """
    Example 2: Custom Translator

    Demonstrates creating a custom translator for Storage Account
    connection strings.
    """
    print_header("Example 2: Custom Storage Account Translator")

    class StorageAccountTranslator(BaseTranslator):
        """Translator for Storage Account connection strings."""

        @property
        def supported_resource_types(self):
            return ["Microsoft.Storage/storageAccounts"]

        def translate(
            self, resource: Dict[str, Any], context: TranslationContext
        ) -> TranslationResult:
            """Translate storage account connection strings."""
            import copy

            translated = copy.deepcopy(resource)
            warnings = []
            errors = []
            was_translated = False

            resource_name = resource.get("name", "unknown")
            resource_type = resource.get("type", "unknown")

            # Example: Translate connection string in tags
            if "tags" in translated and "connectionString" in translated["tags"]:
                old_connection_string = translated["tags"]["connectionString"]

                # Check if it references the source subscription
                if context.source_subscription_id in old_connection_string:
                    # Replace subscription ID in connection string
                    new_connection_string = old_connection_string.replace(
                        context.source_subscription_id,
                        context.target_subscription_id,
                    )
                    translated["tags"]["connectionString"] = new_connection_string
                    was_translated = True

                    # Log what we did
                    warnings.append(
                        f"Translated connection string for storage account '{resource_name}'"
                    )

            return TranslationResult(
                original_resource=resource,
                translated_resource=translated,
                was_translated=was_translated,
                warnings=warnings,
                errors=errors,
                resource_type=resource_type,
                resource_name=resource_name,
                translation_details={
                    "connection_string_translated": was_translated,
                },
            )

    # Create context
    context = TranslationContext(
        source_subscription_id="aaaaaaaa-1111-1111-1111-111111111111",
        target_subscription_id="bbbbbbbb-2222-2222-2222-222222222222",
    )

    # Create sample storage account resource
    storage_account = {
        "type": "Microsoft.Storage/storageAccounts",
        "name": "mystorageaccount",
        "location": "eastus",
        "tags": {
            "connectionString": "DefaultEndpointsProtocol=https;AccountName=mystorageaccount;AccountKey=XXXXX;EndpointSuffix=core.windows.net;SubscriptionId=aaaaaaaa-1111-1111-1111-111111111111"
        },
    }

    print("Source Storage Account Resource:")
    print(json.dumps(storage_account, indent=2))

    # Initialize and use translator
    translator = StorageAccountTranslator(context)

    print("\nPerforming translation...")
    result = translator.translate(storage_account, context)

    print("\nTranslated Storage Account Resource:")
    print(json.dumps(result.translated_resource, indent=2))

    print("\n")
    print_result(result)


def example_3_multiple_resources() -> None:
    """
    Example 3: Translating Multiple Resources

    Demonstrates batch translation of multiple resource types.
    """
    print_header("Example 3: Batch Translation of Multiple Resources")

    source_subscription = "aaaaaaaa-1111-1111-1111-111111111111"
    target_subscription = "bbbbbbbb-2222-2222-2222-222222222222"

    context = TranslationContext(
        source_subscription_id=source_subscription,
        target_subscription_id=target_subscription,
        available_resources={
            "azurerm_storage_account": {"storage1": {}},
            "azurerm_virtual_network": {"vnet1": {}},
            "azurerm_subnet": {"subnet1": {}},
            "azurerm_private_endpoint": {"pe1": {}},
        },
    )

    # Sample resources to translate
    resources = [
        {
            "type": "Microsoft.Storage/storageAccounts",
            "name": "storage1",
            "id": f"/subscriptions/{source_subscription}/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1",
        },
        {
            "type": "Microsoft.Network/virtualNetworks",
            "name": "vnet1",
            "id": f"/subscriptions/{source_subscription}/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1",
            "properties": {
                "subnets": [
                    {
                        "id": f"/subscriptions/{source_subscription}/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1"
                    }
                ]
            },
        },
        {
            "type": "Microsoft.Network/privateEndpoints",
            "name": "pe1",
            "properties": {
                "privateLinkServiceConnections": [
                    {
                        "properties": {
                            "privateLinkServiceId": f"/subscriptions/{source_subscription}/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1"
                        }
                    }
                ]
            },
        },
    ]

    # Initialize translator
    translator = PrivateEndpointTranslator(
        source_subscription_id=source_subscription,
        target_subscription_id=target_subscription,
        available_resources=context.available_resources,
    )

    # Translate resource IDs in resources
    print(f"Translating resource IDs in {len(resources)} resources...\n")
    results = []

    for resource in resources:
        resource_id = resource.get("id")
        if resource_id:
            print(f"Processing: {resource.get('name')} ({resource.get('type')})")
            result = translator.translate_resource_id(resource_id)
            results.append(result)
        else:
            print(f"Skipping {resource.get('name')}: no resource ID")

    # Print summary
    total_translated = sum(1 for r in results if r.was_translated)
    total_warnings = sum(len(r.warnings) for r in results)

    print(f"\nTranslation Summary:")
    print(f"  Total resource IDs processed: {len(results)}")
    print(f"  Translated: {total_translated}")
    print(f"  Unchanged: {len(results) - total_translated}")
    print(f"  Warnings: {total_warnings}")

    # Print detailed results
    for i, result in enumerate(results, 1):
        print(f"\n--- Resource ID {i}: {result.resource_name} ---")
        print(f"Original: {result.original_id}")
        print(f"Translated: {result.translated_id}")
        if result.warnings:
            for warning in result.warnings:
                print(f"  ⚠ {warning}")


def example_4_identity_mapping() -> None:
    """
    Example 4: Identity Mapping (Conceptual)

    Shows how identity mapping would work (when implemented).
    This is a conceptual example showing the expected behavior.
    """
    print_header("Example 4: Identity Mapping (Conceptual)")

    # Load identity mapping from example file
    identity_mapping_file = Path(__file__).parent / "identity_mapping_example.json"

    if identity_mapping_file.exists():
        with open(identity_mapping_file) as f:
            identity_mapping = json.load(f)
        print("Loaded identity mapping:")
        print(json.dumps(identity_mapping, indent=2))
    else:
        print("⚠ identity_mapping_example.json not found, using mock data")
        identity_mapping = {
            "users": {
                "aaaaaaaa-1111-1111-1111-111111111111": "bbbbbbbb-2222-2222-2222-222222222222",
                "alice@source.com": "alice@target.com",
            },
            "groups": {
                "cccccccc-3333-3333-3333-333333333333": "dddddddd-4444-4444-4444-444444444444",
            },
            "service_principals": {
                "eeeeeeee-5555-5555-5555-555555555555": "ffffffff-6666-6666-6666-666666666666",
            },
        }

    # Create context with identity mapping
    context = TranslationContext(
        source_subscription_id="aaaaaaaa-1111-1111-1111-111111111111",
        target_subscription_id="bbbbbbbb-2222-2222-2222-222222222222",
        source_tenant_id="source-tenant-id",
        target_tenant_id="target-tenant-id",
        identity_mapping=identity_mapping,
    )

    # Example Key Vault resource with access policies
    keyvault = {
        "type": "Microsoft.KeyVault/vaults",
        "name": "mykv",
        "properties": {
            "accessPolicies": [
                {
                    "tenantId": "source-tenant-id",
                    "objectId": "aaaaaaaa-1111-1111-1111-111111111111",  # Alice
                    "permissions": {"keys": ["get", "list"], "secrets": ["get"]},
                }
            ]
        },
    }

    print("\nOriginal Key Vault (with source tenant identities):")
    print(json.dumps(keyvault, indent=2))

    print("\n⚠ Note: Full identity translation is not yet implemented in this example.")
    print(
        "When implemented, the objectId would be translated to: bbbbbbbb-2222-2222-2222-222222222222"
    )
    print("And the tenantId would be translated to: target-tenant-id")


def main() -> None:
    """Run all examples."""
    print("\n" + "█" * 80)
    print("  Cross-Tenant Translation Test Suite")
    print("  Testing translation logic offline (no Azure connection required)")
    print("█" * 80)

    try:
        # Run examples
        example_1_private_endpoint_translation()
        example_2_custom_translator()
        example_3_multiple_resources()
        example_4_identity_mapping()

        print("\n" + "█" * 80)
        print("  All examples completed successfully!")
        print("█" * 80 + "\n")

    except Exception as e:
        print(f"\n✗ Error running examples: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
