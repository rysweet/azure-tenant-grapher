"""
Unit tests for StorageAccountTranslator

Tests storage account cross-tenant translation including:
- Resource IDs
- Connection strings
- Endpoint URIs
"""

import pytest

from src.iac.translators import StorageAccountTranslator, TranslationContext


class TestStorageAccountTranslator:
    """Test cases for StorageAccountTranslator."""

    @pytest.fixture
    def source_sub_id(self):
        """Source subscription ID."""
        return "11111111-1111-1111-1111-111111111111"

    @pytest.fixture
    def target_sub_id(self):
        """Target subscription ID."""
        return "22222222-2222-2222-2222-222222222222"

    @pytest.fixture
    def available_resources(self):
        """Sample available resources in IaC."""
        return {
            "azurerm_storage_account": {
                "storage1": {
                    "name": "storage1",
                    "id": "/subscriptions/22222222-2222-2222-2222-222222222222/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1",
                }
            }
        }

    @pytest.fixture
    def context(self, source_sub_id, target_sub_id, available_resources):
        """Create translation context."""
        return TranslationContext(
            source_subscription_id=source_sub_id,
            target_subscription_id=target_sub_id,
            available_resources=available_resources,
        )

    @pytest.fixture
    def translator(self, context):
        """Create translator instance."""
        return StorageAccountTranslator(context)

    def test_supported_resource_types(self, translator):
        """Test that translator declares supported types."""
        assert translator.supported_resource_types == ["azurerm_storage_account"]

    def test_can_translate_with_connection_string(self, translator):
        """Test can_translate returns True for storage account with connection string."""
        resource = {
            "type": "azurerm_storage_account",
            "name": "storage1",
            "primary_connection_string": "DefaultEndpointsProtocol=https;AccountName=storage1;AccountKey=xxx",
        }

        assert translator.can_translate(resource) is True

    def test_can_translate_with_endpoint(self, translator):
        """Test can_translate returns True for storage account with endpoint."""
        resource = {
            "type": "azurerm_storage_account",
            "name": "storage1",
            "primary_blob_endpoint": "https://storage1.blob.core.windows.net/",
        }

        assert translator.can_translate(resource) is True

    def test_can_translate_with_id(self, translator):
        """Test can_translate returns True for storage account with ID."""
        resource = {
            "type": "azurerm_storage_account",
            "name": "storage1",
            "id": "/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1",
        }

        assert translator.can_translate(resource) is True

    def test_cannot_translate_wrong_type(self, translator):
        """Test can_translate returns False for non-storage resources."""
        resource = {
            "type": "azurerm_key_vault",
            "name": "kv1",
        }

        assert translator.can_translate(resource) is False

    def test_cannot_translate_no_translatable_properties(self, translator):
        """Test can_translate returns False when no translatable properties."""
        resource = {
            "type": "azurerm_storage_account",
            "name": "storage1",
            "location": "eastus",
        }

        assert translator.can_translate(resource) is False

    def test_translate_resource_id(self, translator, source_sub_id, target_sub_id):
        """Test translation of storage account resource ID."""
        resource = {
            "type": "azurerm_storage_account",
            "name": "storage1",
            "id": f"/subscriptions/{source_sub_id}/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1",
        }

        translated = translator.translate(resource)

        assert (
            translated["id"]
            == f"/subscriptions/{target_sub_id}/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1"
        )
        assert translated["name"] == "storage1"
        assert translated["type"] == "azurerm_storage_account"

    def test_translate_connection_string(self, translator):
        """Test translation of connection string."""
        resource = {
            "type": "azurerm_storage_account",
            "name": "storage1",
            "primary_connection_string": "DefaultEndpointsProtocol=https;AccountName=storage1;AccountKey=xxx;EndpointSuffix=core.windows.net",
        }

        translated = translator.translate(resource)

        # Connection string should remain the same (account names are globally unique)
        assert (
            translated["primary_connection_string"]
            == resource["primary_connection_string"]
        )

        # Should have results tracked
        results = translator.get_translation_results()
        assert len(results) > 0

    def test_translate_blob_endpoint(self, translator):
        """Test translation of blob endpoint URI."""
        resource = {
            "type": "azurerm_storage_account",
            "name": "storage1",
            "primary_blob_endpoint": "https://storage1.blob.core.windows.net/",
        }

        translated = translator.translate(resource)

        # Endpoint should remain the same (account names are globally unique)
        assert translated["primary_blob_endpoint"] == resource["primary_blob_endpoint"]

    def test_translate_multiple_endpoints(self, translator):
        """Test translation of multiple endpoint types."""
        resource = {
            "type": "azurerm_storage_account",
            "name": "storage1",
            "primary_blob_endpoint": "https://storage1.blob.core.windows.net/",
            "primary_file_endpoint": "https://storage1.file.core.windows.net/",
            "primary_table_endpoint": "https://storage1.table.core.windows.net/",
            "primary_queue_endpoint": "https://storage1.queue.core.windows.net/",
        }

        translated = translator.translate(resource)

        # All endpoints should remain the same
        assert translated["primary_blob_endpoint"] == resource["primary_blob_endpoint"]
        assert translated["primary_file_endpoint"] == resource["primary_file_endpoint"]
        assert (
            translated["primary_table_endpoint"] == resource["primary_table_endpoint"]
        )
        assert (
            translated["primary_queue_endpoint"] == resource["primary_queue_endpoint"]
        )

    def test_translate_connection_string_missing_account(
        self, translator, available_resources
    ):
        """Test translation warns when referenced account not in IaC."""
        resource = {
            "type": "azurerm_storage_account",
            "name": "storage1",
            "primary_connection_string": "DefaultEndpointsProtocol=https;AccountName=missing_account;AccountKey=xxx",
        }

        translated = translator.translate(resource)

        # Get results
        results = translator.get_translation_results()
        conn_str_result = next(
            r for r in results if r.property_path == "primary_connection_string"
        )

        # Should have warnings about missing account
        assert len(conn_str_result.warnings) > 0
        assert any("not found" in w.lower() for w in conn_str_result.warnings)

    def test_translate_skips_terraform_variables(self, translator):
        """Test that Terraform variables are not translated."""
        resource = {
            "type": "azurerm_storage_account",
            "name": "storage1",
            "id": "${azurerm_storage_account.storage1.id}",
            "primary_connection_string": "${var.storage_connection_string}",
        }

        translated = translator.translate(resource)

        # Variables should remain unchanged
        assert translated["id"] == resource["id"]
        assert (
            translated["primary_connection_string"]
            == resource["primary_connection_string"]
        )

    def test_translate_handles_invalid_connection_string(self, translator):
        """Test handling of malformed connection string."""
        resource = {
            "type": "azurerm_storage_account",
            "name": "storage1",
            "primary_connection_string": "invalid-connection-string",
        }

        translated = translator.translate(resource)

        # Should return original on error
        assert (
            translated["primary_connection_string"]
            == resource["primary_connection_string"]
        )

    def test_translate_handles_custom_domain(self, translator):
        """Test handling of custom domain endpoints."""
        resource = {
            "type": "azurerm_storage_account",
            "name": "storage1",
            "primary_blob_endpoint": "https://custom.domain.com/storage",
        }

        translated = translator.translate(resource)

        # Should return original for custom domains
        assert translated["primary_blob_endpoint"] == resource["primary_blob_endpoint"]

        # Should have warning about custom domain
        results = translator.get_translation_results()
        endpoint_result = next(
            r for r in results if r.property_path == "primary_blob_endpoint"
        )
        assert any("custom domain" in w.lower() for w in endpoint_result.warnings)

    def test_get_report(self, translator, source_sub_id, target_sub_id):
        """Test generation of translator report."""
        resource = {
            "type": "azurerm_storage_account",
            "name": "storage1",
            "id": f"/subscriptions/{source_sub_id}/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1",
            "primary_connection_string": "DefaultEndpointsProtocol=https;AccountName=storage1;AccountKey=xxx",
        }

        translator.translate(resource)

        report = translator.get_report()

        assert report["translator"] == "StorageAccountTranslator"
        assert report["total_resources_processed"] > 0
        assert "translations_performed" in report
        assert "warnings" in report


class TestStorageAccountTranslatorEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def context(self):
        """Create minimal translation context."""
        return TranslationContext(
            source_subscription_id="source-sub",
            target_subscription_id="target-sub",
            available_resources={},
        )

    @pytest.fixture
    def translator(self, context):
        """Create translator instance."""
        return StorageAccountTranslator(context)

    def test_translate_empty_resource(self, translator):
        """Test handling of empty resource."""
        resource = {"type": "azurerm_storage_account", "name": "storage1"}

        translated = translator.translate(resource)

        assert translated["type"] == "azurerm_storage_account"
        assert translated["name"] == "storage1"

    def test_translate_connection_string_empty(self, translator):
        """Test handling of empty connection string."""
        resource = {
            "type": "azurerm_storage_account",
            "name": "storage1",
            "primary_connection_string": "",
        }

        translated = translator.translate(resource)

        # Should handle gracefully
        assert translated["primary_connection_string"] == ""

    def test_translate_endpoint_empty(self, translator):
        """Test handling of empty endpoint."""
        resource = {
            "type": "azurerm_storage_account",
            "name": "storage1",
            "primary_blob_endpoint": "",
        }

        translated = translator.translate(resource)

        # Should handle gracefully
        assert translated["primary_blob_endpoint"] == ""

    def test_translate_preserves_extra_properties(self, translator):
        """Test that translation preserves properties it doesn't handle."""
        resource = {
            "type": "azurerm_storage_account",
            "name": "storage1",
            "location": "eastus",
            "account_tier": "Standard",
            "account_replication_type": "LRS",
            "primary_connection_string": "DefaultEndpointsProtocol=https;AccountName=storage1;AccountKey=xxx",
        }

        translated = translator.translate(resource)

        # Should preserve all properties
        assert translated["location"] == "eastus"
        assert translated["account_tier"] == "Standard"
        assert translated["account_replication_type"] == "LRS"
