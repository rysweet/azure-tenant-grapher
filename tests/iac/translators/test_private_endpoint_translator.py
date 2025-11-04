"""
Unit tests for PrivateEndpointTranslator

Tests resource ID translation for cross-subscription private endpoint connections.
"""

import pytest

from src.iac.translators.private_endpoint_translator import (
    PrivateEndpointTranslator,
)


class TestPrivateEndpointTranslator:
    """Test cases for PrivateEndpointTranslator."""

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
            },
            "azurerm_key_vault": {
                "kv1": {
                    "name": "kv1",
                    "id": "/subscriptions/22222222-2222-2222-2222-222222222222/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1",
                }
            },
        }

    def test_should_translate_cross_subscription(
        self, source_sub_id, target_sub_id, available_resources
    ):
        """Test detection of cross-subscription references."""
        translator = PrivateEndpointTranslator(
            source_subscription_id=source_sub_id,
            target_subscription_id=target_sub_id,
            available_resources=available_resources,
        )

        resource_id = f"/subscriptions/{source_sub_id}/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1"

        assert translator.should_translate(resource_id) is True

    def test_should_not_translate_same_subscription(
        self, target_sub_id, available_resources
    ):
        """Test that same-subscription references are not translated."""
        translator = PrivateEndpointTranslator(
            source_subscription_id=target_sub_id,
            target_subscription_id=target_sub_id,
            available_resources=available_resources,
        )

        resource_id = f"/subscriptions/{target_sub_id}/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1"

        assert translator.should_translate(resource_id) is False

    def test_should_not_translate_terraform_variables(
        self, source_sub_id, target_sub_id, available_resources
    ):
        """Test that Terraform variables are not translated."""
        translator = PrivateEndpointTranslator(
            source_subscription_id=source_sub_id,
            target_subscription_id=target_sub_id,
            available_resources=available_resources,
        )

        # Terraform reference
        resource_id = "${azurerm_storage_account.storage1.id}"
        assert translator.should_translate(resource_id) is False

        # Terraform variable
        resource_id = "var.storage_account_id"
        assert translator.should_translate(resource_id) is False

    def test_should_not_translate_invalid_format(
        self, source_sub_id, target_sub_id, available_resources
    ):
        """Test that invalid resource IDs are not translated."""
        translator = PrivateEndpointTranslator(
            source_subscription_id=source_sub_id,
            target_subscription_id=target_sub_id,
            available_resources=available_resources,
        )

        # Invalid format
        assert translator.should_translate("not-a-resource-id") is False
        assert translator.should_translate("") is False

    def test_translate_resource_id_success(
        self, source_sub_id, target_sub_id, available_resources
    ):
        """Test successful resource ID translation."""
        translator = PrivateEndpointTranslator(
            source_subscription_id=source_sub_id,
            target_subscription_id=target_sub_id,
            available_resources=available_resources,
        )

        original_id = f"/subscriptions/{source_sub_id}/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1"
        expected_id = f"/subscriptions/{target_sub_id}/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1"

        result = translator.translate_resource_id(original_id)

        assert result.original_id == original_id
        assert result.translated_id == expected_id
        assert result.was_translated is True
        assert result.target_exists is True
        assert result.resource_type == "Microsoft.Storage/storageAccounts"
        assert result.resource_name == "storage1"
        assert len(result.warnings) == 0

    def test_translate_resource_id_target_missing(
        self, source_sub_id, target_sub_id, available_resources
    ):
        """Test translation when target resource doesn't exist in IaC."""
        translator = PrivateEndpointTranslator(
            source_subscription_id=source_sub_id,
            target_subscription_id=target_sub_id,
            available_resources=available_resources,
        )

        original_id = f"/subscriptions/{source_sub_id}/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/missing_storage"
        expected_id = f"/subscriptions/{target_sub_id}/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/missing_storage"

        result = translator.translate_resource_id(original_id)

        assert result.original_id == original_id
        assert result.translated_id == expected_id
        assert result.was_translated is True
        assert result.target_exists is False
        assert len(result.warnings) == 1
        assert "not found in generated IaC" in result.warnings[0]

    def test_translate_resource_id_invalid_format(
        self, source_sub_id, target_sub_id, available_resources
    ):
        """Test translation with invalid resource ID format."""
        translator = PrivateEndpointTranslator(
            source_subscription_id=source_sub_id,
            target_subscription_id=target_sub_id,
            available_resources=available_resources,
        )

        invalid_id = "not-a-valid-resource-id"
        result = translator.translate_resource_id(invalid_id)

        assert result.original_id == invalid_id
        assert result.translated_id == invalid_id
        assert result.was_translated is False
        assert result.target_exists is False
        assert len(result.warnings) == 1
        assert "Invalid Azure resource ID format" in result.warnings[0]

    def test_translate_resource_id_same_subscription(
        self, target_sub_id, available_resources
    ):
        """Test translation when source and target are the same."""
        translator = PrivateEndpointTranslator(
            source_subscription_id=target_sub_id,
            target_subscription_id=target_sub_id,
            available_resources=available_resources,
        )

        resource_id = f"/subscriptions/{target_sub_id}/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1"

        result = translator.translate_resource_id(resource_id)

        assert result.original_id == resource_id
        assert result.translated_id == resource_id
        assert result.was_translated is False
        assert result.target_exists is True

    def test_resource_id_parsing(
        self, source_sub_id, target_sub_id, available_resources
    ):
        """Test parsing of various resource ID formats."""
        translator = PrivateEndpointTranslator(
            source_subscription_id=source_sub_id,
            target_subscription_id=target_sub_id,
            available_resources=available_resources,
        )

        # Standard resource ID
        result = translator.translate_resource_id(
            f"/subscriptions/{source_sub_id}/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1"
        )
        assert result.resource_type == "Microsoft.Storage/storageAccounts"
        assert result.resource_name == "storage1"

        # Resource with sub-resources
        result = translator.translate_resource_id(
            f"/subscriptions/{source_sub_id}/resourceGroups/rg1/providers/Microsoft.Sql/servers/sqlserver1/databases/db1"
        )
        assert result.resource_type == "Microsoft.Sql/servers"
        assert result.resource_name == "sqlserver1"

    def test_azure_type_to_terraform_type(
        self, source_sub_id, target_sub_id, available_resources
    ):
        """Test Azure type to Terraform type mapping."""
        translator = PrivateEndpointTranslator(
            source_subscription_id=source_sub_id,
            target_subscription_id=target_sub_id,
            available_resources=available_resources,
        )

        # Test common mappings
        assert (
            translator._azure_type_to_terraform_type(
                "Microsoft.Storage/storageAccounts"
            )
            == "azurerm_storage_account"
        )
        assert (
            translator._azure_type_to_terraform_type("Microsoft.KeyVault/vaults")
            == "azurerm_key_vault"
        )
        assert (
            translator._azure_type_to_terraform_type("Microsoft.Sql/servers")
            == "azurerm_mssql_server"
        )

        # Test unknown type
        assert (
            translator._azure_type_to_terraform_type("Microsoft.Unknown/unknownType")
            is None
        )

    def test_check_target_exists(
        self, source_sub_id, target_sub_id, available_resources
    ):
        """Test checking if target resource exists in IaC."""
        translator = PrivateEndpointTranslator(
            source_subscription_id=source_sub_id,
            target_subscription_id=target_sub_id,
            available_resources=available_resources,
        )

        # Resource exists
        assert (
            translator._check_target_exists(
                "Microsoft.Storage/storageAccounts", "storage1"
            )
            is True
        )
        assert (
            translator._check_target_exists("Microsoft.KeyVault/vaults", "kv1") is True
        )

        # Resource doesn't exist
        assert (
            translator._check_target_exists(
                "Microsoft.Storage/storageAccounts", "missing"
            )
            is False
        )

        # Unknown type
        assert (
            translator._check_target_exists("Microsoft.Unknown/unknownType", "anything")
            is False
        )

    def test_extract_source_subscription(self, target_sub_id):
        """Test extracting source subscription from resources."""
        source_id = "33333333-3333-3333-3333-333333333333"
        resources_with_ids = {
            "azurerm_storage_account": {
                "storage1": {
                    "id": f"/subscriptions/{source_id}/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1"
                }
            }
        }

        translator = PrivateEndpointTranslator(
            source_subscription_id=None,  # Will extract from resources
            target_subscription_id=target_sub_id,
            available_resources=resources_with_ids,
        )

        assert translator.source_subscription_id == source_id

    def test_extract_source_subscription_not_found(self, target_sub_id):
        """Test handling when source subscription cannot be extracted."""
        resources_without_ids = {
            "azurerm_storage_account": {"storage1": {"name": "storage1"}}
        }

        translator = PrivateEndpointTranslator(
            source_subscription_id=None,
            target_subscription_id=target_sub_id,
            available_resources=resources_without_ids,
        )

        assert translator.source_subscription_id is None

    def test_translation_with_resource_name_override(
        self, source_sub_id, target_sub_id, available_resources
    ):
        """Test translation with explicit resource name."""
        translator = PrivateEndpointTranslator(
            source_subscription_id=source_sub_id,
            target_subscription_id=target_sub_id,
            available_resources=available_resources,
        )

        original_id = f"/subscriptions/{source_sub_id}/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1"

        result = translator.translate_resource_id(
            original_id, resource_name="custom_name"
        )

        assert result.resource_name == "custom_name"

    def test_format_translation_report_empty(
        self, source_sub_id, target_sub_id, available_resources
    ):
        """Test formatting report with no translations."""
        translator = PrivateEndpointTranslator(
            source_subscription_id=source_sub_id,
            target_subscription_id=target_sub_id,
            available_resources=available_resources,
        )

        report = translator.format_translation_report([])
        assert "No resource ID translations were needed" in report

    def test_format_translation_report_with_results(
        self, source_sub_id, target_sub_id, available_resources
    ):
        """Test formatting report with translation results."""
        translator = PrivateEndpointTranslator(
            source_subscription_id=source_sub_id,
            target_subscription_id=target_sub_id,
            available_resources=available_resources,
        )

        results = [
            translator.translate_resource_id(
                f"/subscriptions/{source_sub_id}/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1"
            ),
            translator.translate_resource_id(
                f"/subscriptions/{source_sub_id}/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/missing"
            ),
        ]

        report = translator.format_translation_report(results)

        assert "Resource ID Translation Report" in report
        assert "Total Resource IDs Checked: 2" in report
        assert "Translated: 2" in report
        assert "Missing Targets: 1" in report
        assert "storage1" in report
        assert "missing" in report

    def test_complex_resource_id_with_subresources(self, source_sub_id, target_sub_id):
        """Test translation of complex resource IDs with sub-resources."""
        available_resources = {
            "azurerm_mssql_server": {
                "sqlserver1": {
                    "name": "sqlserver1",
                    "id": f"/subscriptions/{target_sub_id}/resourceGroups/rg1/providers/Microsoft.Sql/servers/sqlserver1",
                }
            }
        }

        translator = PrivateEndpointTranslator(
            source_subscription_id=source_sub_id,
            target_subscription_id=target_sub_id,
            available_resources=available_resources,
        )

        # Resource with sub-resource (database)
        original_id = f"/subscriptions/{source_sub_id}/resourceGroups/rg1/providers/Microsoft.Sql/servers/sqlserver1/databases/db1"
        expected_id = f"/subscriptions/{target_sub_id}/resourceGroups/rg1/providers/Microsoft.Sql/servers/sqlserver1/databases/db1"

        result = translator.translate_resource_id(original_id)

        assert result.translated_id == expected_id
        assert result.was_translated is True
        assert result.resource_type == "Microsoft.Sql/servers"
        assert result.resource_name == "sqlserver1"

    def test_multiple_translations_preserve_resource_groups(
        self, source_sub_id, target_sub_id, available_resources
    ):
        """Test that resource groups are preserved during translation."""
        translator = PrivateEndpointTranslator(
            source_subscription_id=source_sub_id,
            target_subscription_id=target_sub_id,
            available_resources=available_resources,
        )

        test_cases = [
            ("rg1", "Microsoft.Storage/storageAccounts", "storage1"),
            ("different-rg", "Microsoft.KeyVault/vaults", "kv2"),
            ("rg-with-dashes", "Microsoft.Sql/servers", "sql1"),
        ]

        for rg_name, resource_type, resource_name in test_cases:
            original_id = f"/subscriptions/{source_sub_id}/resourceGroups/{rg_name}/providers/{resource_type}/{resource_name}"
            result = translator.translate_resource_id(original_id)

            # Verify resource group is preserved
            assert f"/resourceGroups/{rg_name}/" in result.translated_id
            assert result.was_translated is True


class TestPrivateEndpointTranslatorEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_resource_id(self):
        """Test handling of empty resource ID."""
        translator = PrivateEndpointTranslator(
            source_subscription_id="source-sub",
            target_subscription_id="target-sub",
            available_resources={},
        )

        assert translator.should_translate("") is False

        result = translator.translate_resource_id("")
        assert result.was_translated is False

    def test_none_available_resources(self):
        """Test handling when available_resources is None."""
        translator = PrivateEndpointTranslator(
            source_subscription_id="source-sub",
            target_subscription_id="target-sub",
            available_resources=None,
        )

        assert translator.available_resources == {}

    def test_none_source_subscription(self):
        """Test handling when source subscription is None."""
        translator = PrivateEndpointTranslator(
            source_subscription_id=None,
            target_subscription_id="target-sub",
            available_resources={},
        )

        # Should not translate when source is None
        resource_id = "/subscriptions/some-sub/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/storage1"
        assert translator.should_translate(resource_id) is False

    def test_case_sensitivity_in_resource_ids(self):
        """Test that resource IDs are case-sensitive."""
        source_sub = "11111111-1111-1111-1111-111111111111"
        target_sub = "22222222-2222-2222-2222-222222222222"

        translator = PrivateEndpointTranslator(
            source_subscription_id=source_sub,
            target_subscription_id=target_sub,
            available_resources={},
        )

        # Azure resource IDs are case-preserving
        original_id = f"/subscriptions/{source_sub}/resourceGroups/MyResourceGroup/providers/Microsoft.Storage/storageAccounts/MyStorageAccount"
        result = translator.translate_resource_id(original_id)

        # Should preserve case
        assert "/resourceGroups/MyResourceGroup/" in result.translated_id
        assert "MyStorageAccount" in result.translated_id

    def test_special_characters_in_names(self):
        """Test handling of special characters in resource names."""
        source_sub = "11111111-1111-1111-1111-111111111111"
        target_sub = "22222222-2222-2222-2222-222222222222"

        translator = PrivateEndpointTranslator(
            source_subscription_id=source_sub,
            target_subscription_id=target_sub,
            available_resources={},
        )

        # Resource with hyphens and numbers
        original_id = f"/subscriptions/{source_sub}/resourceGroups/rg-test-123/providers/Microsoft.Storage/storageAccounts/storage-account-001"
        result = translator.translate_resource_id(original_id)

        assert result.was_translated is True
        assert "/resourceGroups/rg-test-123/" in result.translated_id
        assert "storage-account-001" in result.translated_id

    def test_very_long_resource_id(self):
        """Test handling of very long resource IDs."""
        source_sub = "11111111-1111-1111-1111-111111111111"
        target_sub = "22222222-2222-2222-2222-222222222222"

        translator = PrivateEndpointTranslator(
            source_subscription_id=source_sub,
            target_subscription_id=target_sub,
            available_resources={},
        )

        # Long nested resource ID
        original_id = (
            f"/subscriptions/{source_sub}/resourceGroups/very-long-resource-group-name-123/"
            "providers/Microsoft.Sql/servers/very-long-sql-server-name-456/"
            "databases/very-long-database-name-789/"
            "transparentDataEncryption/current"
        )

        result = translator.translate_resource_id(original_id)
        assert result.was_translated is True
        assert target_sub in result.translated_id
        assert source_sub not in result.translated_id

    def test_deeply_nested_network_resource_ids(self):
        """Test handling of deeply nested network resource IDs.

        This addresses reviewer concern about regex pattern handling all
        Azure resource ID edge cases, particularly Network Interface
        IP Configurations and Virtual Network Gateway Connections.
        """
        source_sub = "11111111-1111-1111-1111-111111111111"
        target_sub = "22222222-2222-2222-2222-222222222222"

        translator = PrivateEndpointTranslator(
            source_subscription_id=source_sub,
            target_subscription_id=target_sub,
            available_resources={},
        )

        # Test 1: Network Interface IP Configuration (4 levels deep)
        nic_ip_config_id = (
            f"/subscriptions/{source_sub}/resourceGroups/network-rg/"
            "providers/Microsoft.Network/networkInterfaces/nic-01/"
            "ipConfigurations/ipconfig1"
        )
        result = translator.translate_resource_id(nic_ip_config_id)
        assert result.was_translated is True
        assert target_sub in result.translated_id
        assert source_sub not in result.translated_id
        assert (
            "networkInterfaces/nic-01/ipConfigurations/ipconfig1"
            in result.translated_id
        )

        # Test 2: Virtual Network Gateway Connection
        vng_connection_id = (
            f"/subscriptions/{source_sub}/resourceGroups/gateway-rg/"
            "providers/Microsoft.Network/virtualNetworkGateways/vng-prod/"
            "connections/conn-to-onprem"
        )
        result2 = translator.translate_resource_id(vng_connection_id)
        assert result2.was_translated is True
        assert target_sub in result2.translated_id
        assert (
            "virtualNetworkGateways/vng-prod/connections/conn-to-onprem"
            in result2.translated_id
        )

        # Test 3: Application Gateway HTTP Listener (complex sub-resource)
        appgw_listener_id = (
            f"/subscriptions/{source_sub}/resourceGroups/appgw-rg/"
            "providers/Microsoft.Network/applicationGateways/appgw-01/"
            "httpListeners/listener-443"
        )
        result3 = translator.translate_resource_id(appgw_listener_id)
        assert result3.was_translated is True
        assert target_sub in result3.translated_id
        assert (
            "applicationGateways/appgw-01/httpListeners/listener-443"
            in result3.translated_id
        )
