"""
Unit tests for KeyVaultTranslator

Tests Key Vault cross-tenant translation including:
- Resource IDs
- Access policies (tenant_id, object_id, application_id)
- Vault URIs
- Key/Secret/Certificate resource IDs
"""

import pytest

from src.iac.translators import KeyVaultTranslator, TranslationContext


class TestKeyVaultTranslator:
    """Test cases for KeyVaultTranslator."""

    @pytest.fixture
    def source_sub_id(self):
        """Source subscription ID."""
        return "11111111-1111-1111-1111-111111111111"

    @pytest.fixture
    def target_sub_id(self):
        """Target subscription ID."""
        return "22222222-2222-2222-2222-222222222222"

    @pytest.fixture
    def source_tenant_id(self):
        """Source tenant ID."""
        return "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

    @pytest.fixture
    def target_tenant_id(self):
        """Target tenant ID."""
        return "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

    @pytest.fixture
    def available_resources(self):
        """Sample available resources in IaC."""
        return {
            "azurerm_key_vault": {
                "kv1": {
                    "name": "kv1",
                    "id": "/subscriptions/22222222-2222-2222-2222-222222222222/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1",
                }
            }
        }

    @pytest.fixture
    def context(
        self,
        source_sub_id,
        target_sub_id,
        source_tenant_id,
        target_tenant_id,
        available_resources,
    ):
        """Create translation context."""
        return TranslationContext(
            source_subscription_id=source_sub_id,
            target_subscription_id=target_sub_id,
            source_tenant_id=source_tenant_id,
            target_tenant_id=target_tenant_id,
            available_resources=available_resources,
        )

    @pytest.fixture
    def translator(self, context):
        """Create translator instance."""
        return KeyVaultTranslator(context)

    def test_supported_resource_types(self, translator):
        """Test that translator declares supported types."""
        expected_types = [
            "azurerm_key_vault",
            "azurerm_key_vault_key",
            "azurerm_key_vault_secret",
            "azurerm_key_vault_certificate",
        ]
        assert translator.supported_resource_types == expected_types

    def test_can_translate_with_access_policy(self, translator):
        """Test can_translate returns True for Key Vault with access policies."""
        resource = {
            "type": "azurerm_key_vault",
            "name": "kv1",
            "access_policy": [
                {
                    "tenant_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                    "object_id": "11111111-1111-1111-1111-111111111111",
                }
            ],
        }

        assert translator.can_translate(resource) is True

    def test_can_translate_with_resource_id(self, translator):
        """Test can_translate returns True for Key Vault with resource ID."""
        resource = {
            "type": "azurerm_key_vault",
            "name": "kv1",
            "id": "/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1",
        }

        assert translator.can_translate(resource) is True

    def test_can_translate_with_vault_uri(self, translator):
        """Test can_translate returns True for Key Vault with vault URI."""
        resource = {
            "type": "azurerm_key_vault",
            "name": "kv1",
            "vault_uri": "https://kv1.vault.azure.net/",
        }

        assert translator.can_translate(resource) is True

    def test_can_translate_key_resource(self, translator):
        """Test can_translate returns True for Key Vault key resource."""
        resource = {
            "type": "azurerm_key_vault_key",
            "name": "key1",
            "key_vault_id": "/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1",
        }

        assert translator.can_translate(resource) is True

    def test_cannot_translate_wrong_type(self, translator):
        """Test can_translate returns False for non-Key Vault resources."""
        resource = {
            "type": "azurerm_storage_account",
            "name": "storage1",
        }

        assert translator.can_translate(resource) is False

    def test_cannot_translate_no_translatable_properties(self, translator):
        """Test can_translate returns False when no translatable properties."""
        resource = {
            "type": "azurerm_key_vault",
            "name": "kv1",
            "location": "eastus",
        }

        assert translator.can_translate(resource) is False

    def test_translate_resource_id(self, translator, source_sub_id, target_sub_id):
        """Test translation of Key Vault resource ID."""
        resource = {
            "type": "azurerm_key_vault",
            "name": "kv1",
            "id": f"/subscriptions/{source_sub_id}/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1",
        }

        translated = translator.translate(resource)

        assert (
            translated["id"]
            == f"/subscriptions/{target_sub_id}/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1"
        )
        assert translated["name"] == "kv1"
        assert translated["type"] == "azurerm_key_vault"

    def test_translate_key_vault_id_for_key(
        self, translator, source_sub_id, target_sub_id
    ):
        """Test translation of key_vault_id for Key Vault key resource."""
        resource = {
            "type": "azurerm_key_vault_key",
            "name": "key1",
            "key_vault_id": f"/subscriptions/{source_sub_id}/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1",
        }

        translated = translator.translate(resource)

        assert (
            translated["key_vault_id"]
            == f"/subscriptions/{target_sub_id}/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1"
        )

    def test_translate_access_policy_tenant_id(
        self, translator, source_tenant_id, target_tenant_id
    ):
        """Test translation of tenant_id in access policies."""
        resource = {
            "type": "azurerm_key_vault",
            "name": "kv1",
            "access_policy": [
                {
                    "tenant_id": source_tenant_id,
                    "object_id": "11111111-1111-1111-1111-111111111111",
                    "key_permissions": ["get", "list"],
                    "secret_permissions": ["get", "list"],
                }
            ],
        }

        translated = translator.translate(resource)

        assert len(translated["access_policy"]) == 1
        assert translated["access_policy"][0]["tenant_id"] == target_tenant_id
        # object_id should remain unchanged in Phase 2 (no identity mapping)
        assert (
            translated["access_policy"][0]["object_id"]
            == "11111111-1111-1111-1111-111111111111"
        )
        # Permissions should be preserved
        assert translated["access_policy"][0]["key_permissions"] == ["get", "list"]
        assert translated["access_policy"][0]["secret_permissions"] == ["get", "list"]

    def test_translate_access_policy_warns_about_object_id(
        self, translator, source_tenant_id
    ):
        """Test that translation warns when object_id cannot be translated."""
        resource = {
            "type": "azurerm_key_vault",
            "name": "kv1",
            "access_policy": [
                {
                    "tenant_id": source_tenant_id,
                    "object_id": "11111111-1111-1111-1111-111111111111",
                    "key_permissions": ["get", "list"],
                }
            ],
        }

        translated = translator.translate(resource)

        # Get results
        results = translator.get_translation_results()
        access_policy_result = next(
            r for r in results if r.property_path == "access_policy"
        )

        # Should have warnings about object IDs not being translated
        assert len(access_policy_result.warnings) > 0
        # Check for warning about identity mapping not being available
        assert any(
            "identity mapping" in w.lower() or "object id" in w.lower()
            for w in access_policy_result.warnings
        )

    def test_translate_access_policy_with_application_id(
        self, translator, source_tenant_id
    ):
        """Test translation of access policy with application_id."""
        resource = {
            "type": "azurerm_key_vault",
            "name": "kv1",
            "access_policy": [
                {
                    "tenant_id": source_tenant_id,
                    "object_id": "11111111-1111-1111-1111-111111111111",
                    "application_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                    "key_permissions": ["get", "list"],
                }
            ],
        }

        translated = translator.translate(resource)

        # application_id should remain unchanged (no mapping in Phase 2)
        assert (
            translated["access_policy"][0]["application_id"]
            == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        )

        # Should have warnings about identity mapping
        results = translator.get_translation_results()
        access_policy_result = next(
            r for r in results if r.property_path == "access_policy"
        )
        assert any(
            "application" in w.lower() or "identity mapping" in w.lower()
            for w in access_policy_result.warnings
        )

    def test_translate_multiple_access_policies(
        self, translator, source_tenant_id, target_tenant_id
    ):
        """Test translation of multiple access policies."""
        resource = {
            "type": "azurerm_key_vault",
            "name": "kv1",
            "access_policy": [
                {
                    "tenant_id": source_tenant_id,
                    "object_id": "11111111-1111-1111-1111-111111111111",
                    "key_permissions": ["get", "list"],
                },
                {
                    "tenant_id": source_tenant_id,
                    "object_id": "22222222-2222-2222-2222-222222222222",
                    "secret_permissions": ["get", "list"],
                },
            ],
        }

        translated = translator.translate(resource)

        assert len(translated["access_policy"]) == 2
        # Both tenant_ids should be translated
        assert translated["access_policy"][0]["tenant_id"] == target_tenant_id
        assert translated["access_policy"][1]["tenant_id"] == target_tenant_id
        # Permissions should be preserved
        assert translated["access_policy"][0]["key_permissions"] == ["get", "list"]
        assert translated["access_policy"][1]["secret_permissions"] == ["get", "list"]

    def test_translate_vault_uri_valid_format(self, translator):
        """Test translation of valid vault URI."""
        resource = {
            "type": "azurerm_key_vault",
            "name": "kv1",
            "vault_uri": "https://kv1.vault.azure.net/",
        }

        translated = translator.translate(resource)

        # URI should remain unchanged (vault names are globally unique)
        assert translated["vault_uri"] == "https://kv1.vault.azure.net/"

    def test_translate_vault_uri_name_mismatch(self, translator):
        """Test vault URI with mismatched vault name."""
        resource = {
            "type": "azurerm_key_vault",
            "name": "kv1",
            "vault_uri": "https://different-kv.vault.azure.net/",
        }

        translated = translator.translate(resource)

        # URI should remain unchanged
        assert translated["vault_uri"] == "https://different-kv.vault.azure.net/"

        # Should have warning about name mismatch
        results = translator.get_translation_results()
        vault_uri_result = next(r for r in results if r.property_path == "vault_uri")
        assert any("name mismatch" in w.lower() for w in vault_uri_result.warnings)

    def test_translate_vault_uri_missing_target(self, translator):
        """Test vault URI referencing vault not in target IaC."""
        resource = {
            "type": "azurerm_key_vault",
            "name": "kv1",
            "vault_uri": "https://missing-kv.vault.azure.net/",
        }

        translated = translator.translate(resource)

        # Should have warning about missing vault
        results = translator.get_translation_results()
        vault_uri_result = next(r for r in results if r.property_path == "vault_uri")
        assert any("not found" in w.lower() for w in vault_uri_result.warnings)

    def test_translate_vault_uri_invalid_format(self, translator):
        """Test vault URI with invalid format."""
        resource = {
            "type": "azurerm_key_vault",
            "name": "kv1",
            "vault_uri": "https://invalid-format.com/vault",
        }

        translated = translator.translate(resource)

        # URI should remain unchanged
        assert translated["vault_uri"] == "https://invalid-format.com/vault"

        # Should have warning about invalid format
        results = translator.get_translation_results()
        vault_uri_result = next(r for r in results if r.property_path == "vault_uri")
        assert any(
            "does not match expected format" in w.lower()
            for w in vault_uri_result.warnings
        )

    def test_translate_skips_terraform_variables(self, translator):
        """Test that Terraform variables are not translated."""
        resource = {
            "type": "azurerm_key_vault",
            "name": "kv1",
            "id": "${azurerm_key_vault.kv1.id}",
            "vault_uri": "${var.vault_uri}",
        }

        translated = translator.translate(resource)

        # Variables should remain unchanged
        assert translated["id"] == resource["id"]
        assert translated["vault_uri"] == resource["vault_uri"]

    def test_translate_preserves_all_properties(self, translator, source_sub_id):
        """Test that translation preserves properties it doesn't handle."""
        resource = {
            "type": "azurerm_key_vault",
            "name": "kv1",
            "location": "eastus",
            "sku_name": "standard",
            "enabled_for_disk_encryption": True,
            "enabled_for_template_deployment": True,
            "id": f"/subscriptions/{source_sub_id}/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1",
            "access_policy": [
                {
                    "tenant_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                    "object_id": "11111111-1111-1111-1111-111111111111",
                    "key_permissions": ["get", "list"],
                }
            ],
        }

        translated = translator.translate(resource)

        # Should preserve all properties
        assert translated["location"] == "eastus"
        assert translated["sku_name"] == "standard"
        assert translated["enabled_for_disk_encryption"] is True
        assert translated["enabled_for_template_deployment"] is True

    def test_get_report(self, translator, source_sub_id, source_tenant_id):
        """Test generation of translator report."""
        resource = {
            "type": "azurerm_key_vault",
            "name": "kv1",
            "id": f"/subscriptions/{source_sub_id}/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1",
            "access_policy": [
                {
                    "tenant_id": source_tenant_id,
                    "object_id": "11111111-1111-1111-1111-111111111111",
                    "key_permissions": ["get", "list"],
                }
            ],
        }

        translator.translate(resource)

        report = translator.get_report()

        assert report["translator"] == "KeyVaultTranslator"
        assert report["total_resources_processed"] > 0
        assert "translations_performed" in report
        assert "warnings" in report


class TestKeyVaultTranslatorEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def context(self):
        """Create minimal translation context."""
        return TranslationContext(
            source_subscription_id="source-sub",
            target_subscription_id="target-sub",
            source_tenant_id="source-tenant",
            target_tenant_id="target-tenant",
            available_resources={},
        )

    @pytest.fixture
    def translator(self, context):
        """Create translator instance."""
        return KeyVaultTranslator(context)

    def test_translate_empty_resource(self, translator):
        """Test handling of empty resource."""
        resource = {"type": "azurerm_key_vault", "name": "kv1"}

        translated = translator.translate(resource)

        assert translated["type"] == "azurerm_key_vault"
        assert translated["name"] == "kv1"

    def test_translate_access_policy_empty_list(self, translator):
        """Test handling of empty access policy list."""
        resource = {
            "type": "azurerm_key_vault",
            "name": "kv1",
            "access_policy": [],
        }

        translated = translator.translate(resource)

        assert translated["access_policy"] == []

    def test_translate_access_policy_invalid_item(self, translator):
        """Test handling of invalid access policy item."""
        resource = {
            "type": "azurerm_key_vault",
            "name": "kv1",
            "access_policy": [
                "invalid-policy",  # Not a dict
                {
                    "tenant_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                    "object_id": "11111111-1111-1111-1111-111111111111",
                },
            ],
        }

        translated = translator.translate(resource)

        # Should handle gracefully
        assert len(translated["access_policy"]) == 2

        # Should have warnings about invalid item
        results = translator.get_translation_results()
        access_policy_result = next(
            r for r in results if r.property_path == "access_policy"
        )
        assert any(
            "not a dictionary" in w.lower() for w in access_policy_result.warnings
        )

    def test_translate_access_policy_no_tenant_id(self, translator):
        """Test handling of access policy without tenant_id."""
        resource = {
            "type": "azurerm_key_vault",
            "name": "kv1",
            "access_policy": [
                {
                    "object_id": "11111111-1111-1111-1111-111111111111",
                    "key_permissions": ["get", "list"],
                }
            ],
        }

        translated = translator.translate(resource)

        # Should handle gracefully (no tenant_id to translate)
        assert len(translated["access_policy"]) == 1
        assert "object_id" in translated["access_policy"][0]

    def test_translate_vault_uri_empty(self, translator):
        """Test handling of empty vault URI."""
        resource = {
            "type": "azurerm_key_vault",
            "name": "kv1",
            "vault_uri": "",
        }

        translated = translator.translate(resource)

        # Should handle gracefully
        assert translated["vault_uri"] == ""

        # Should have warning
        results = translator.get_translation_results()
        vault_uri_result = next(r for r in results if r.property_path == "vault_uri")
        assert any("empty or invalid" in w.lower() for w in vault_uri_result.warnings)

    def test_translate_vault_uri_none(self, translator):
        """Test handling of None vault URI."""
        resource = {
            "type": "azurerm_key_vault",
            "name": "kv1",
            "vault_uri": None,
        }

        translated = translator.translate(resource)

        # Should handle gracefully
        assert translated["vault_uri"] is None

    def test_translate_access_policy_preserves_certificate_permissions(
        self, translator
    ):
        """Test that certificate permissions are preserved."""
        resource = {
            "type": "azurerm_key_vault",
            "name": "kv1",
            "access_policy": [
                {
                    "tenant_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                    "object_id": "11111111-1111-1111-1111-111111111111",
                    "key_permissions": ["get", "list", "create"],
                    "secret_permissions": ["get", "list", "set"],
                    "certificate_permissions": ["get", "list", "create", "import"],
                }
            ],
        }

        translated = translator.translate(resource)

        # All permission arrays should be preserved
        assert translated["access_policy"][0]["key_permissions"] == [
            "get",
            "list",
            "create",
        ]
        assert translated["access_policy"][0]["secret_permissions"] == [
            "get",
            "list",
            "set",
        ]
        assert translated["access_policy"][0]["certificate_permissions"] == [
            "get",
            "list",
            "create",
            "import",
        ]

    def test_translate_multiple_resources_sequential(self, translator, context):
        """Test translating multiple resources sequentially."""
        resources = [
            {
                "type": "azurerm_key_vault",
                "name": "kv1",
                "id": f"/subscriptions/{context.source_subscription_id}/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1",
            },
            {
                "type": "azurerm_key_vault_key",
                "name": "key1",
                "key_vault_id": f"/subscriptions/{context.source_subscription_id}/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1",
            },
            {
                "type": "azurerm_key_vault_secret",
                "name": "secret1",
                "key_vault_id": f"/subscriptions/{context.source_subscription_id}/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1",
            },
        ]

        for resource in resources:
            translated = translator.translate(resource)
            assert context.target_subscription_id in str(
                translated.get("id") or translated.get("key_vault_id")
            )

        # Should have results for all resources
        results = translator.get_translation_results()
        assert len(results) >= 3

    def test_translate_context_without_target_tenant(self):
        """Test translation when target tenant ID is not provided."""
        context = TranslationContext(
            source_subscription_id="source-sub",
            target_subscription_id="target-sub",
            source_tenant_id="source-tenant",
            target_tenant_id=None,  # No target tenant
            available_resources={},
        )
        translator = KeyVaultTranslator(context)

        resource = {
            "type": "azurerm_key_vault",
            "name": "kv1",
            "access_policy": [
                {
                    "tenant_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                    "object_id": "11111111-1111-1111-1111-111111111111",
                }
            ],
        }

        translated = translator.translate(resource)

        # tenant_id should remain unchanged (no target tenant to translate to)
        assert (
            translated["access_policy"][0]["tenant_id"]
            == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        )

        # Should have warnings
        results = translator.get_translation_results()
        access_policy_result = next(
            r for r in results if r.property_path == "access_policy"
        )
        assert any(
            "no target tenant" in w.lower() for w in access_policy_result.warnings
        )
