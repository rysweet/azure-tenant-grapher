"""
Unit tests for AppServiceTranslator

Tests app service cross-tenant translation including:
- App Service Plan resource IDs
- App Settings with Key Vault references
- Connection Strings
- Storage connection strings
- SQL connection strings
- Edge cases and validation
"""

import pytest

from src.iac.translators import AppServiceTranslator, TranslationContext


class TestAppServiceTranslator:
    """Test cases for AppServiceTranslator."""

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
            "azurerm_app_service_plan": {
                "plan1": {
                    "name": "plan1",
                    "id": "/subscriptions/22222222-2222-2222-2222-222222222222/resourceGroups/rg1/providers/Microsoft.Web/serverFarms/plan1",
                }
            },
            "azurerm_key_vault": {
                "vault1": {
                    "name": "vault1",
                    "id": "/subscriptions/22222222-2222-2222-2222-222222222222/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/vault1",
                }
            },
            "azurerm_storage_account": {
                "storage1": {
                    "name": "storage1",
                    "id": "/subscriptions/22222222-2222-2222-2222-222222222222/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1",
                }
            },
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
        return AppServiceTranslator(context)

    def test_supported_resource_types(self, translator):
        """Test that translator declares 8 supported types."""
        supported = translator.supported_resource_types

        # Should have exactly 8 supported types
        assert len(supported) == 8

        # Verify key types are included
        assert "azurerm_app_service" in supported
        assert "azurerm_linux_web_app" in supported
        assert "azurerm_windows_web_app" in supported
        assert "azurerm_function_app" in supported
        assert "azurerm_linux_function_app" in supported
        assert "azurerm_windows_function_app" in supported
        assert "azurerm_app_service_plan" in supported
        assert "azurerm_service_plan" in supported

    def test_can_translate_app_service_with_plan_id(self, translator, source_sub_id):
        """Test can_translate returns True for app service with plan ID."""
        resource = {
            "type": "azurerm_linux_web_app",
            "name": "app1",
            "app_service_plan_id": f"/subscriptions/{source_sub_id}/resourceGroups/rg1/providers/Microsoft.Web/serverFarms/plan1",
        }

        assert translator.can_translate(resource) is True

    def test_can_translate_app_service_with_app_settings(self, translator):
        """Test can_translate returns True for app service with app settings."""
        resource = {
            "type": "azurerm_linux_web_app",
            "name": "app1",
            "app_settings": {
                "WEBSITE_NODE_DEFAULT_VERSION": "14.x",
                "KEY_VAULT_SECRET": "@Microsoft.KeyVault(SecretUri=https://vault1.vault.azure.net/secrets/secret1)",
            },
        }

        assert translator.can_translate(resource) is True

    def test_can_translate_app_service_with_connection_strings(self, translator):
        """Test can_translate returns True for app service with connection strings."""
        resource = {
            "type": "azurerm_linux_web_app",
            "name": "app1",
            "connection_string": [
                {
                    "name": "MyDb",
                    "type": "SQLAzure",
                    "value": "Server=tcp:myserver.database.windows.net,1433;Database=mydb;",
                }
            ],
        }

        assert translator.can_translate(resource) is True

    def test_can_translate_app_service_plan(self, translator, source_sub_id):
        """Test can_translate returns True for app service plan with cross-sub ID."""
        resource = {
            "type": "azurerm_app_service_plan",
            "name": "plan1",
            "id": f"/subscriptions/{source_sub_id}/resourceGroups/rg1/providers/Microsoft.Web/serverFarms/plan1",
        }

        assert translator.can_translate(resource) is True

    def test_cannot_translate_app_service_plan_same_sub(
        self, translator, target_sub_id
    ):
        """Test can_translate returns False for app service plan in same subscription."""
        resource = {
            "type": "azurerm_app_service_plan",
            "name": "plan1",
            "id": f"/subscriptions/{target_sub_id}/resourceGroups/rg1/providers/Microsoft.Web/serverFarms/plan1",
        }

        assert translator.can_translate(resource) is False

    def test_cannot_translate_wrong_resource_type(self, translator, source_sub_id):
        """Test can_translate returns False for non-supported resources."""
        resource = {
            "type": "azurerm_storage_account",
            "name": "storage1",
            "app_settings": {"KEY": "VALUE"},
        }

        assert translator.can_translate(resource) is False

    def test_cannot_translate_no_translatable_properties(self, translator):
        """Test can_translate returns False when no translatable properties."""
        resource = {
            "type": "azurerm_linux_web_app",
            "name": "app1",
            "location": "eastus",
        }

        assert translator.can_translate(resource) is False

    def test_translate_app_service_plan_id(
        self, translator, context, source_sub_id, target_sub_id
    ):
        """Test translating app service plan resource ID."""
        resource = {
            "type": "azurerm_linux_web_app",
            "name": "app1",
            "app_service_plan_id": f"/subscriptions/{source_sub_id}/resourceGroups/rg1/providers/Microsoft.Web/serverFarms/plan1",
        }

        result = translator.translate(resource)

        assert (
            result["app_service_plan_id"]
            == f"/subscriptions/{target_sub_id}/resourceGroups/rg1/providers/Microsoft.Web/serverFarms/plan1"
        )

        # Check that translation was recorded
        results = translator.get_translation_results()
        assert len(results) > 0
        assert any(r.property_path == "app_service_plan_id" for r in results)

    def test_translate_app_service_plan_resource(
        self, translator, context, source_sub_id, target_sub_id
    ):
        """Test translating app service plan resource itself."""
        resource = {
            "type": "azurerm_app_service_plan",
            "name": "plan1",
            "id": f"/subscriptions/{source_sub_id}/resourceGroups/rg1/providers/Microsoft.Web/serverFarms/plan1",
        }

        result = translator.translate(resource)

        assert (
            result["id"]
            == f"/subscriptions/{target_sub_id}/resourceGroups/rg1/providers/Microsoft.Web/serverFarms/plan1"
        )

    def test_translate_keyvault_reference_secret_uri(self, translator, context):
        """Test translating Key Vault reference in app settings (SecretUri format)."""
        resource = {
            "type": "azurerm_linux_web_app",
            "name": "app1",
            "app_settings": {
                "MY_SECRET": "@Microsoft.KeyVault(SecretUri=https://vault1.vault.azure.net/secrets/secret1/abc123)"
            },
        }

        result = translator.translate(resource)

        # Should validate vault exists but not translate (vault name stays same)
        assert (
            result["app_settings"]["MY_SECRET"]
            == "@Microsoft.KeyVault(SecretUri=https://vault1.vault.azure.net/secrets/secret1/abc123)"
        )

        # Check warnings - vault1 exists in target so no warnings expected
        results = translator.get_translation_results()
        app_settings_result = [r for r in results if r.property_path == "app_settings"]
        assert len(app_settings_result) > 0
        assert len(app_settings_result[0].warnings) == 0

    def test_translate_keyvault_reference_vault_not_found(self, translator, context):
        """Test Key Vault reference when vault not in target."""
        resource = {
            "type": "azurerm_linux_web_app",
            "name": "app1",
            "app_settings": {
                "MY_SECRET": "@Microsoft.KeyVault(SecretUri=https://missingvault.vault.azure.net/secrets/secret1)"
            },
        }

        # Translate and get results
        translator.translate(resource)
        results = translator.get_translation_results()

        # Should have warning about missing vault
        app_settings_result = [r for r in results if r.property_path == "app_settings"]
        assert len(app_settings_result) > 0
        assert len(app_settings_result[0].warnings) > 0
        warnings_text = " ".join(app_settings_result[0].warnings).lower()
        assert "missingvault" in warnings_text
        assert "not found" in warnings_text

    def test_translate_keyvault_reference_vaultname_format(self, translator, context):
        """Test translating Key Vault reference with VaultName format."""
        resource = {
            "type": "azurerm_linux_web_app",
            "name": "app1",
            "app_settings": {
                "MY_SECRET": "@Microsoft.KeyVault(VaultName=vault1;SecretName=secret1;SecretVersion=v1)"
            },
        }

        result = translator.translate(resource)

        # Should validate vault exists
        assert (
            result["app_settings"]["MY_SECRET"]
            == "@Microsoft.KeyVault(VaultName=vault1;SecretName=secret1;SecretVersion=v1)"
        )

        # Should have no warnings since vault1 exists
        results = translator.get_translation_results()
        app_settings_result = [r for r in results if r.property_path == "app_settings"]
        assert len(app_settings_result) > 0
        assert len(app_settings_result[0].warnings) == 0

    def test_translate_storage_connection_string_warning(self, translator, context):
        """Test storage connection string generates warning."""
        resource = {
            "type": "azurerm_function_app",
            "name": "func1",
            "app_settings": {
                "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=storage1;AccountKey=xxx;EndpointSuffix=core.windows.net"
            },
        }

        # Translate and get results
        translator.translate(resource)
        results = translator.get_translation_results()

        # Should have warning about storage connection string
        app_settings_result = [r for r in results if r.property_path == "app_settings"]
        assert len(app_settings_result) > 0
        assert len(app_settings_result[0].warnings) > 0
        warnings_text = " ".join(app_settings_result[0].warnings).lower()
        assert "storage" in warnings_text
        assert "storage1" in warnings_text

    def test_translate_sql_connection_string_warning(self, translator, context):
        """Test SQL connection string generates warning."""
        resource = {
            "type": "azurerm_linux_web_app",
            "name": "app1",
            "app_settings": {
                "SQL_CONN": "Server=tcp:myserver.database.windows.net,1433;Database=mydb;User Id=user;Password=pass;"
            },
        }

        # Translate and get results
        translator.translate(resource)
        results = translator.get_translation_results()

        # Should have warning about SQL connection string
        app_settings_result = [r for r in results if r.property_path == "app_settings"]
        assert len(app_settings_result) > 0
        assert len(app_settings_result[0].warnings) > 0
        warnings_text = " ".join(app_settings_result[0].warnings).lower()
        assert "sql" in warnings_text or "server" in warnings_text
        assert "myserver" in warnings_text

    def test_translate_connection_strings_block(self, translator, context):
        """Test translating connection strings block."""
        resource = {
            "type": "azurerm_linux_web_app",
            "name": "app1",
            "connection_string": [
                {
                    "name": "MyDb",
                    "type": "SQLAzure",
                    "value": "Server=tcp:myserver.database.windows.net,1433;Database=mydb;",
                },
                {
                    "name": "StorageConn",
                    "type": "Custom",
                    "value": "DefaultEndpointsProtocol=https;AccountName=storage1;AccountKey=xxx;",
                },
            ],
        }

        # Translate and get results
        translator.translate(resource)
        results = translator.get_translation_results()

        # Should have warnings for both connection strings
        conn_str_result = [r for r in results if r.property_path == "connection_string"]
        assert len(conn_str_result) > 0
        assert len(conn_str_result[0].warnings) >= 2
        warnings_text = " ".join(conn_str_result[0].warnings).lower()
        assert "myserver" in warnings_text or "mydb" in warnings_text
        assert "storage1" in warnings_text

    def test_translate_connection_string_with_keyvault_ref(self, translator, context):
        """Test connection string with Key Vault reference."""
        resource = {
            "type": "azurerm_linux_web_app",
            "name": "app1",
            "connection_string": [
                {
                    "name": "MyDb",
                    "type": "SQLAzure",
                    "value": "@Microsoft.KeyVault(SecretUri=https://vault1.vault.azure.net/secrets/dbconn)",
                }
            ],
        }

        result = translator.translate(resource)

        # Should validate vault reference
        assert (
            result["connection_string"][0]["value"]
            == "@Microsoft.KeyVault(SecretUri=https://vault1.vault.azure.net/secrets/dbconn)"
        )

    def test_translate_preserves_terraform_variables(self, translator, context):
        """Test that Terraform variables are not translated."""
        resource = {
            "type": "azurerm_linux_web_app",
            "name": "app1",
            "app_service_plan_id": "${azurerm_service_plan.plan1.id}",
            "app_settings": {
                "CONNECTION_STRING": "var.database_connection_string",
                "STORAGE_KEY": "${azurerm_storage_account.storage.primary_access_key}",
            },
        }

        result = translator.translate(resource)

        # Terraform variables should be unchanged
        assert result["app_service_plan_id"] == "${azurerm_service_plan.plan1.id}"
        assert (
            result["app_settings"]["CONNECTION_STRING"]
            == "var.database_connection_string"
        )
        assert (
            result["app_settings"]["STORAGE_KEY"]
            == "${azurerm_storage_account.storage.primary_access_key}"
        )

    def test_translate_regular_app_settings_unchanged(self, translator, context):
        """Test that regular app settings pass through unchanged."""
        resource = {
            "type": "azurerm_linux_web_app",
            "name": "app1",
            "app_settings": {
                "WEBSITE_NODE_DEFAULT_VERSION": "14.x",
                "ENVIRONMENT": "production",
                "DEBUG": "false",
                "MAX_WORKERS": "4",
            },
        }

        result = translator.translate(resource)

        # Regular settings should be unchanged
        assert result["app_settings"] == resource["app_settings"]

    def test_translate_empty_app_settings(self, translator, context):
        """Test translating empty app settings."""
        resource = {
            "type": "azurerm_linux_web_app",
            "name": "app1",
            "app_settings": {},
        }

        result = translator.translate(resource)

        assert result["app_settings"] == {}

    def test_translate_none_app_settings(self, translator, context):
        """Test translating None app settings."""
        resource = {
            "type": "azurerm_linux_web_app",
            "name": "app1",
            "app_settings": None,
        }

        result = translator.translate(resource)

        assert result["app_settings"] is None

    def test_translate_empty_connection_strings(self, translator, context):
        """Test translating empty connection strings."""
        resource = {
            "type": "azurerm_linux_web_app",
            "name": "app1",
            "connection_string": [],
        }

        result = translator.translate(resource)

        assert result["connection_string"] == []

    def test_translate_malformed_keyvault_reference(self, translator, context):
        """Test malformed Key Vault reference generates warning."""
        resource = {
            "type": "azurerm_linux_web_app",
            "name": "app1",
            "app_settings": {"BAD_REF": "@Microsoft.KeyVault(InvalidParam=value)"},
        }

        # Translate and get results
        translator.translate(resource)
        results = translator.get_translation_results()

        # Should have warning about malformed reference
        app_settings_result = [r for r in results if r.property_path == "app_settings"]
        assert len(app_settings_result) > 0
        assert len(app_settings_result[0].warnings) > 0
        warnings_text = " ".join(app_settings_result[0].warnings).lower()
        assert "malformed" in warnings_text or "unrecognized" in warnings_text

    def test_translate_connection_string_unexpected_format(self, translator, context):
        """Test connection string with unexpected format."""
        resource = {
            "type": "azurerm_linux_web_app",
            "name": "app1",
            "connection_string": "not_a_list",  # Should be a list
        }

        # Translate and get results
        translator.translate(resource)
        results = translator.get_translation_results()

        # Should have warning about unexpected format
        conn_str_result = [r for r in results if r.property_path == "connection_string"]
        assert len(conn_str_result) > 0
        assert len(conn_str_result[0].warnings) > 0
        warnings_text = " ".join(conn_str_result[0].warnings).lower()
        assert "unexpected format" in warnings_text

    def test_get_translation_results(
        self, translator, context, source_sub_id, target_sub_id
    ):
        """Test that translation results are recorded."""
        resource = {
            "type": "azurerm_linux_web_app",
            "name": "app1",
            "app_service_plan_id": f"/subscriptions/{source_sub_id}/resourceGroups/rg1/providers/Microsoft.Web/serverFarms/plan1",
        }

        translator.translate(resource)
        results = translator.get_translation_results()

        assert len(results) > 0
        assert results[0].property_path == "app_service_plan_id"
        assert results[0].was_modified is True

    def test_get_report(self, translator, context, source_sub_id):
        """Test generating translation report."""
        resource1 = {
            "type": "azurerm_linux_web_app",
            "name": "app1",
            "app_service_plan_id": f"/subscriptions/{source_sub_id}/resourceGroups/rg1/providers/Microsoft.Web/serverFarms/plan1",
        }

        resource2 = {
            "type": "azurerm_linux_web_app",
            "name": "app2",
            "app_settings": {"KEY": "VALUE"},
        }

        translator.translate(resource1)
        translator.translate(resource2)

        report = translator.get_report()

        assert report["translator"] == "AppServiceTranslator"
        assert report["total_resources_processed"] >= 2
        assert report["translations_performed"] >= 1

    def test_translate_multiple_keyvault_references(self, translator, context):
        """Test translating multiple Key Vault references in same resource."""
        resource = {
            "type": "azurerm_linux_web_app",
            "name": "app1",
            "app_settings": {
                "SECRET1": "@Microsoft.KeyVault(SecretUri=https://vault1.vault.azure.net/secrets/secret1)",
                "SECRET2": "@Microsoft.KeyVault(SecretUri=https://vault1.vault.azure.net/secrets/secret2)",
                "SECRET3": "@Microsoft.KeyVault(VaultName=vault1;SecretName=secret3)",
            },
        }

        # Translate and get results
        translator.translate(resource)
        results = translator.get_translation_results()

        # All references should be validated
        app_settings_result = [r for r in results if r.property_path == "app_settings"]
        assert len(app_settings_result) > 0
        # vault1 exists in target, so no warnings expected
        assert len(app_settings_result[0].warnings) == 0

    def test_translate_function_app_storage_settings(self, translator, context):
        """Test Function App specific storage settings generate warnings."""
        resource = {
            "type": "azurerm_linux_function_app",
            "name": "func1",
            "app_settings": {
                "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=storage1;AccountKey=xxx;",
                "WEBSITE_CONTENTAZUREFILECONNECTIONSTRING": "DefaultEndpointsProtocol=https;AccountName=storage1;AccountKey=xxx;",
                "FUNCTIONS_WORKER_RUNTIME": "node",
            },
        }

        # Translate and get results
        translator.translate(resource)
        results = translator.get_translation_results()

        # Should have warnings for storage connection strings
        app_settings_result = [r for r in results if r.property_path == "app_settings"]
        assert len(app_settings_result) > 0
        assert (
            len(app_settings_result[0].warnings) >= 2
        )  # At least 2 warnings for storage conn strings
        warnings_text = " ".join(app_settings_result[0].warnings).lower()
        assert "storage" in warnings_text
        # FUNCTIONS_WORKER_RUNTIME should not generate warning
        assert "worker_runtime" not in warnings_text

    def test_azure_type_to_terraform_type_custom_mappings(self, translator):
        """Test custom Azure to Terraform type mappings."""
        assert (
            translator._azure_type_to_terraform_type("Microsoft.Web/serverFarms")
            == "azurerm_app_service_plan"
        )
        assert (
            translator._azure_type_to_terraform_type("Microsoft.Web/serverfarms")
            == "azurerm_service_plan"
        )
        assert (
            translator._azure_type_to_terraform_type("Microsoft.KeyVault/vaults")
            == "azurerm_key_vault"
        )
