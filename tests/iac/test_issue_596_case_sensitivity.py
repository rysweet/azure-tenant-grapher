"""Tests for Issue #596: Terraform validation errors - case sensitivity issues.

This test suite verifies that all resource handlers properly normalize SKU and property
casing to match Terraform provider requirements.

Issue #596 identified three main problems:
1. Key Vault sku_name: "Standard" from Azure should be "standard" for Terraform
2. Log Analytics sku: "pergb2018" from Azure should be "PerGB2018" for Terraform
3. Storage Account: Property renaming for provider v4+

All fixes have been implemented in the handlers. These tests ensure the fixes work correctly.
"""

import json

from src.iac.emitters.terraform_emitter import TerraformEmitter


class TestKeyVaultSkuCaseNormalization:
    """Test that Key Vault SKU names are normalized to lowercase for Terraform."""

    def test_keyvault_standard_sku_normalized_to_lowercase(self):
        """Test that 'Standard' SKU from Azure is normalized to 'standard' for Terraform."""
        emitter = TerraformEmitter()
        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/test-kv",
            "name": "test-kv",
            "type": "Microsoft.KeyVault/vaults",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "sku": {
                        "name": "Standard",  # Capitalized from Azure
                    },
                    "tenantId": "00000000-0000-0000-0000-000000000000",
                }
            ),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        # Fix #596: Should be lowercase for Terraform
        assert config["sku_name"] == "standard"
        assert terraform_type == "azurerm_key_vault"

    def test_keyvault_premium_sku_normalized_to_lowercase(self):
        """Test that 'Premium' SKU from Azure is normalized to 'premium' for Terraform."""
        emitter = TerraformEmitter()
        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/test-kv-premium",
            "name": "test-kv-premium",
            "type": "Microsoft.KeyVault/vaults",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "sku": {
                        "name": "Premium",  # Capitalized from Azure
                    },
                    "tenantId": "00000000-0000-0000-0000-000000000000",
                }
            ),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        # Fix #596: Should be lowercase for Terraform
        assert config["sku_name"] == "premium"
        assert terraform_type == "azurerm_key_vault"

    def test_keyvault_lowercase_sku_unchanged(self):
        """Test that already-lowercase SKU remains lowercase."""
        emitter = TerraformEmitter()
        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/test-kv-lower",
            "name": "test-kv-lower",
            "type": "Microsoft.KeyVault/vaults",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "sku": {
                        "name": "standard",  # Already lowercase
                    },
                    "tenantId": "00000000-0000-0000-0000-000000000000",
                }
            ),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        assert config["sku_name"] == "standard"
        assert terraform_type == "azurerm_key_vault"

    def test_keyvault_missing_sku_defaults_to_standard(self):
        """Test that missing SKU defaults to 'standard'."""
        emitter = TerraformEmitter()
        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/test-kv-no-sku",
            "name": "test-kv-no-sku",
            "type": "Microsoft.KeyVault/vaults",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "tenantId": "00000000-0000-0000-0000-000000000000",
                }
            ),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        # Should default to 'standard'
        assert config["sku_name"] == "standard"
        assert terraform_type == "azurerm_key_vault"


class TestLogAnalyticsSkuCaseNormalization:
    """Test that Log Analytics SKU names are normalized to PascalCase for Terraform."""

    def test_log_analytics_pergb2018_normalized_to_pascalcase(self):
        """Test that 'pergb2018' SKU from Azure is normalized to 'PerGB2018' for Terraform."""
        emitter = TerraformEmitter()
        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.OperationalInsights/workspaces/test-workspace",
            "name": "test-workspace",
            "type": "Microsoft.OperationalInsights/workspaces",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "sku": {
                        "name": "pergb2018",  # Lowercase from Azure
                    },
                    "retentionInDays": 90,
                }
            ),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        # Fix #596: Should be PascalCase for Terraform
        assert config["sku"] == "PerGB2018"
        assert config["retention_in_days"] == 90
        assert terraform_type == "azurerm_log_analytics_workspace"

    def test_log_analytics_pernode_normalized_to_pascalcase(self):
        """Test that 'pernode' SKU from Azure is normalized to 'PerNode' for Terraform."""
        emitter = TerraformEmitter()
        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.OperationalInsights/workspaces/test-workspace-pernode",
            "name": "test-workspace-pernode",
            "type": "Microsoft.OperationalInsights/workspaces",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "sku": {
                        "name": "pernode",  # Lowercase from Azure
                    },
                }
            ),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        # Fix #596: Should be PascalCase for Terraform
        assert config["sku"] == "PerNode"
        assert terraform_type == "azurerm_log_analytics_workspace"

    def test_log_analytics_standalone_normalized_to_pascalcase(self):
        """Test that 'standalone' SKU from Azure is normalized to 'Standalone' for Terraform."""
        emitter = TerraformEmitter()
        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.OperationalInsights/workspaces/test-workspace-standalone",
            "name": "test-workspace-standalone",
            "type": "Microsoft.OperationalInsights/workspaces",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "sku": {
                        "name": "standalone",  # Lowercase from Azure
                    },
                }
            ),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        # Fix #596: Should be PascalCase for Terraform
        assert config["sku"] == "Standalone"
        assert terraform_type == "azurerm_log_analytics_workspace"

    def test_log_analytics_capacityreservation_normalized_to_pascalcase(self):
        """Test that 'capacityreservation' SKU from Azure is normalized to 'CapacityReservation' for Terraform."""
        emitter = TerraformEmitter()
        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.OperationalInsights/workspaces/test-workspace-capacity",
            "name": "test-workspace-capacity",
            "type": "Microsoft.OperationalInsights/workspaces",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "sku": {
                        "name": "capacityreservation",  # Lowercase from Azure
                    },
                }
            ),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        # Fix #596: Should be PascalCase for Terraform
        assert config["sku"] == "CapacityReservation"
        assert terraform_type == "azurerm_log_analytics_workspace"


class TestStorageAccountPropertyNaming:
    """Test that Storage Account properties use correct naming for Terraform provider v4+."""

    def test_storage_account_https_traffic_only_enabled(self):
        """Test that 'supportsHttpsTrafficOnly' from Azure becomes 'https_traffic_only_enabled' for Terraform."""
        emitter = TerraformEmitter()
        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/teststorageaccount",
            "name": "teststorageaccount",
            "type": "Microsoft.Storage/storageAccounts",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "sku": {
                        "name": "Standard_LRS",
                    },
                    "supportsHttpsTrafficOnly": True,  # Azure property name
                    "minimumTlsVersion": "TLS1_2",
                }
            ),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        # Fix #596: Property renamed in provider v4+
        assert "https_traffic_only_enabled" in config
        assert config["https_traffic_only_enabled"] is True
        assert "supportsHttpsTrafficOnly" not in config  # Old property should not exist
        assert terraform_type == "azurerm_storage_account"

    def test_storage_account_https_traffic_only_disabled(self):
        """Test that 'supportsHttpsTrafficOnly=false' is correctly translated."""
        emitter = TerraformEmitter()
        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/teststoragehttp",
            "name": "teststoragehttp",
            "type": "Microsoft.Storage/storageAccounts",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "sku": {
                        "name": "Standard_LRS",
                    },
                    "supportsHttpsTrafficOnly": False,  # Disabled
                }
            ),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        # Fix #596: Property renamed and value preserved
        assert "https_traffic_only_enabled" in config
        assert config["https_traffic_only_enabled"] is False
        assert terraform_type == "azurerm_storage_account"

    def test_storage_account_min_tls_version(self):
        """Test that TLS version is correctly handled."""
        emitter = TerraformEmitter()
        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/teststoragetls",
            "name": "teststoragetls",
            "type": "Microsoft.Storage/storageAccounts",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "sku": {
                        "name": "Standard_LRS",
                    },
                    "minimumTlsVersion": "TLS1_2",
                }
            ),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        assert "min_tls_version" in config
        assert config["min_tls_version"] == "TLS1_2"
        assert terraform_type == "azurerm_storage_account"


class TestCaseSensitivityRegressionPrevention:
    """Regression tests to ensure case sensitivity fixes remain in place."""

    def test_multiple_keyvaults_with_different_skus(self):
        """Test that multiple Key Vaults with different SKUs all normalize correctly."""
        emitter = TerraformEmitter()

        resources = [
            {
                "id": f"/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/test-kv-{i}",
                "name": f"test-kv-{i}",
                "type": "Microsoft.KeyVault/vaults",
                "location": "eastus",
                "resource_group": "test-rg",
                "properties": json.dumps(
                    {
                        "sku": {"name": sku},
                        "tenantId": "00000000-0000-0000-0000-000000000000",
                    }
                ),
            }
            for i, sku in enumerate(["Standard", "Premium", "standard", "PREMIUM"])
        ]

        for resource in resources:
            result = emitter._convert_resource(resource, {"resource": {}})
            assert result is not None
            _, _, config = result
            # All should be lowercase
            assert config["sku_name"] in ["standard", "premium"]
            assert config["sku_name"].islower()

    def test_log_analytics_sku_map_completeness(self):
        """Test that all common Log Analytics SKU values are handled correctly."""
        emitter = TerraformEmitter()

        # Test all SKU mappings from the handler
        sku_mappings = {
            "pergb2018": "PerGB2018",
            "pernode": "PerNode",
            "premium": "Premium",
            "standalone": "Standalone",
            "standard": "Standard",
            "capacityreservation": "CapacityReservation",
            "lacluster": "LACluster",
            "unlimited": "Unlimited",
        }

        for azure_sku, expected_terraform_sku in sku_mappings.items():
            resource = {
                "id": f"/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.OperationalInsights/workspaces/test-{azure_sku}",
                "name": f"test-{azure_sku}",
                "type": "Microsoft.OperationalInsights/workspaces",
                "location": "eastus",
                "resource_group": "test-rg",
                "properties": json.dumps({"sku": {"name": azure_sku}}),
            }

            result = emitter._convert_resource(resource, {"resource": {}})
            assert result is not None
            _, _, config = result
            assert config["sku"] == expected_terraform_sku, (
                f"SKU '{azure_sku}' should map to '{expected_terraform_sku}', got '{config['sku']}'"
            )
