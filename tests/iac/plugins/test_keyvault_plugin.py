"""
Unit tests for Key Vault data plane plugin.

Tests cover:
- Key Vault resource validation
- Discovery stub functionality
- Terraform code generation
- Replication stub functionality
"""

import pytest

from src.iac.plugins.base_plugin import DataPlaneItem, ReplicationResult
from src.iac.plugins.keyvault_plugin import KeyVaultPlugin


class TestKeyVaultPlugin:
    """Test cases for KeyVaultPlugin."""

    def test_plugin_instantiation(self):
        """Test that KeyVaultPlugin can be instantiated."""
        plugin = KeyVaultPlugin()
        assert plugin is not None
        assert plugin.plugin_name == "KeyVaultPlugin"

    def test_supported_resource_type(self):
        """Test that plugin supports correct resource type."""
        plugin = KeyVaultPlugin()
        assert plugin.supported_resource_type == "Microsoft.KeyVault/vaults"

    def test_supports_terraform_format(self):
        """Test that plugin supports Terraform output format."""
        plugin = KeyVaultPlugin()
        assert plugin.supports_output_format("terraform") is True
        assert plugin.supports_output_format("TERRAFORM") is True

    def test_does_not_support_other_formats(self):
        """Test that plugin doesn't support other formats yet."""
        plugin = KeyVaultPlugin()
        assert plugin.supports_output_format("bicep") is False
        assert plugin.supports_output_format("arm") is False


class TestKeyVaultValidation:
    """Test resource validation for Key Vault plugin."""

    def test_validate_valid_keyvault_resource(self):
        """Test validation succeeds for valid Key Vault resource."""
        plugin = KeyVaultPlugin()
        resource = {
            "id": "/subscriptions/123/resourceGroups/rg/providers/Microsoft.KeyVault/vaults/my-kv",
            "type": "Microsoft.KeyVault/vaults",
            "name": "my-kv",
            "properties": {"vaultUri": "https://my-kv.vault.azure.net/"},
        }

        assert plugin.validate_resource(resource) is True

    def test_validate_wrong_resource_type(self):
        """Test validation fails for wrong resource type."""
        plugin = KeyVaultPlugin()
        resource = {
            "id": "/subscriptions/123",
            "type": "Microsoft.Storage/storageAccounts",  # Wrong type
            "name": "storage",
        }

        assert plugin.validate_resource(resource) is False

    def test_validate_missing_id(self):
        """Test validation fails for missing resource ID."""
        plugin = KeyVaultPlugin()
        resource = {
            "type": "Microsoft.KeyVault/vaults",
            "name": "my-kv",
            # Missing 'id'
        }

        assert plugin.validate_resource(resource) is False

    def test_validate_none_resource(self):
        """Test validation fails for None resource."""
        plugin = KeyVaultPlugin()
        assert plugin.validate_resource(None) is False


class TestKeyVaultDiscovery:
    """Test discovery functionality for Key Vault plugin."""

    def test_discover_with_valid_resource_returns_list(self):
        """Test discover returns a list (currently empty stub)."""
        plugin = KeyVaultPlugin()
        resource = {
            "id": "/subscriptions/123/resourceGroups/rg/providers/Microsoft.KeyVault/vaults/my-kv",
            "type": "Microsoft.KeyVault/vaults",
            "name": "my-kv",
            "properties": {"vaultUri": "https://my-kv.vault.azure.net/"},
        }

        items = plugin.discover(resource)

        # Stub implementation returns empty list
        assert isinstance(items, list)
        assert len(items) == 0

    def test_discover_with_invalid_resource_raises_error(self):
        """Test discover raises ValueError for invalid resource."""
        plugin = KeyVaultPlugin()
        invalid_resource = {
            "type": "Microsoft.Storage/storageAccounts",  # Wrong type
            "name": "storage",
        }

        with pytest.raises(ValueError, match="Invalid resource"):
            plugin.discover(invalid_resource)

    def test_discover_with_missing_properties(self):
        """Test discover handles resource without properties."""
        plugin = KeyVaultPlugin()
        resource = {
            "id": "/subscriptions/123/resourceGroups/rg/providers/Microsoft.KeyVault/vaults/my-kv",
            "type": "Microsoft.KeyVault/vaults",
            "name": "my-kv",
            # No properties
        }

        # Should not raise error, just return empty list (stub)
        items = plugin.discover(resource)
        assert len(items) == 0


class TestKeyVaultCodeGeneration:
    """Test IaC code generation for Key Vault plugin."""

    def test_generate_code_for_empty_items(self):
        """Test code generation with no items."""
        plugin = KeyVaultPlugin()
        code = plugin.generate_replication_code([], "terraform")

        assert "No Key Vault data plane items" in code

    def test_generate_code_for_single_secret(self):
        """Test code generation for a single secret."""
        plugin = KeyVaultPlugin()
        items = [
            DataPlaneItem(
                name="db-password",
                item_type="secret",
                properties={"enabled": True, "content_type": "text/plain"},
                source_resource_id="/subscriptions/123/vaults/kv",
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Check for Terraform resource
        assert "azurerm_key_vault_secret" in code
        assert "db_password" in code  # Sanitized name
        assert "SECURITY" in code  # Security warning

        # Check for variable declaration
        assert "variable" in code
        assert "keyvault_secret_db_password" in code
        assert "sensitive   = true" in code

    def test_generate_code_for_multiple_secrets(self):
        """Test code generation for multiple secrets."""
        plugin = KeyVaultPlugin()
        items = [
            DataPlaneItem(
                name="db-password",
                item_type="secret",
                properties={},
                source_resource_id="/subscriptions/123/vaults/kv",
            ),
            DataPlaneItem(
                name="api-key",
                item_type="secret",
                properties={"content_type": "application/json"},
                source_resource_id="/subscriptions/123/vaults/kv",
            ),
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Check both secrets are present
        assert "db_password" in code
        assert "api_key" in code

        # Check both variables are declared
        assert "keyvault_secret_db_password" in code
        assert "keyvault_secret_api_key" in code

    def test_generate_code_with_secret_tags(self):
        """Test code generation includes secret tags."""
        plugin = KeyVaultPlugin()
        items = [
            DataPlaneItem(
                name="tagged-secret",
                item_type="secret",
                properties={"tags": {"env": "production", "owner": "team-a"}},
                source_resource_id="/subscriptions/123/vaults/kv",
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Check tags are included
        assert "tags = {" in code
        assert '"env" = "production"' in code
        assert '"owner" = "team-a"' in code

    def test_generate_code_with_content_type(self):
        """Test code generation includes content_type."""
        plugin = KeyVaultPlugin()
        items = [
            DataPlaneItem(
                name="json-secret",
                item_type="secret",
                properties={"content_type": "application/json"},
                source_resource_id="/subscriptions/123/vaults/kv",
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        assert "content_type" in code
        assert "application/json" in code

    def test_generate_code_for_keys_placeholder(self):
        """Test code generation for keys (placeholder)."""
        plugin = KeyVaultPlugin()
        items = [
            DataPlaneItem(
                name="encryption-key",
                item_type="key",
                properties={},
                source_resource_id="/subscriptions/123/vaults/kv",
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Keys are not fully implemented yet
        assert "Keys" in code or "TODO" in code
        assert "encryption-key" in code

    def test_generate_code_for_certificates_placeholder(self):
        """Test code generation for certificates (placeholder)."""
        plugin = KeyVaultPlugin()
        items = [
            DataPlaneItem(
                name="ssl-cert",
                item_type="certificate",
                properties={},
                source_resource_id="/subscriptions/123/vaults/kv",
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Certificates are not fully implemented yet
        assert "Certificates" in code or "TODO" in code
        assert "ssl-cert" in code

    def test_generate_code_mixed_item_types(self):
        """Test code generation with secrets, keys, and certificates."""
        plugin = KeyVaultPlugin()
        items = [
            DataPlaneItem(
                name="my-secret",
                item_type="secret",
                properties={},
                source_resource_id="/subscriptions/123/vaults/kv",
            ),
            DataPlaneItem(
                name="my-key",
                item_type="key",
                properties={},
                source_resource_id="/subscriptions/123/vaults/kv",
            ),
            DataPlaneItem(
                name="my-cert",
                item_type="certificate",
                properties={},
                source_resource_id="/subscriptions/123/vaults/kv",
            ),
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # All sections should be present
        assert "Secrets" in code
        assert "Keys" in code
        assert "Certificates" in code
        assert "my-secret" in code
        assert "my-key" in code
        assert "my-cert" in code

    def test_generate_code_unsupported_format_raises_error(self):
        """Test code generation raises error for unsupported format."""
        plugin = KeyVaultPlugin()
        items = [
            DataPlaneItem(
                name="secret",
                item_type="secret",
                properties={},
                source_resource_id="/subscriptions/123/vaults/kv",
            )
        ]

        with pytest.raises(ValueError, match="not supported"):
            plugin.generate_replication_code(items, "bicep")


class TestKeyVaultReplication:
    """Test replication functionality for Key Vault plugin."""

    def test_replicate_with_valid_resources_returns_result(self):
        """Test replicate returns ReplicationResult (stub)."""
        plugin = KeyVaultPlugin()
        source = {
            "id": "/subscriptions/123/vaults/source-kv",
            "type": "Microsoft.KeyVault/vaults",
            "name": "source-kv",
        }
        target = {
            "id": "/subscriptions/123/vaults/target-kv",
            "type": "Microsoft.KeyVault/vaults",
            "name": "target-kv",
        }

        result = plugin.replicate(source, target)

        assert isinstance(result, ReplicationResult)
        # Stub implementation returns unsuccessful result
        assert result.success is False
        assert "not yet implemented" in result.errors[0].lower()
        assert len(result.warnings) > 0

    def test_replicate_with_invalid_source_raises_error(self):
        """Test replicate raises error for invalid source."""
        plugin = KeyVaultPlugin()
        invalid_source = {
            "type": "Microsoft.Storage/storageAccounts",  # Wrong type
            "name": "storage",
        }
        target = {
            "id": "/subscriptions/123/vaults/target-kv",
            "type": "Microsoft.KeyVault/vaults",
            "name": "target-kv",
        }

        with pytest.raises(ValueError, match="Invalid source resource"):
            plugin.replicate(invalid_source, target)

    def test_replicate_with_invalid_target_raises_error(self):
        """Test replicate raises error for invalid target."""
        plugin = KeyVaultPlugin()
        source = {
            "id": "/subscriptions/123/vaults/source-kv",
            "type": "Microsoft.KeyVault/vaults",
            "name": "source-kv",
        }
        invalid_target = {
            "type": "Microsoft.Storage/storageAccounts",  # Wrong type
            "name": "storage",
        }

        with pytest.raises(ValueError, match="Invalid target resource"):
            plugin.replicate(source, invalid_target)


class TestKeyVaultNameSanitization:
    """Test name sanitization for Terraform identifiers."""

    def test_sanitize_name_with_hyphens(self):
        """Test sanitization replaces hyphens with underscores."""
        plugin = KeyVaultPlugin()
        sanitized = plugin._sanitize_name("my-secret-name")
        assert sanitized == "my_secret_name"
        assert "-" not in sanitized

    def test_sanitize_name_with_dots(self):
        """Test sanitization replaces dots with underscores."""
        plugin = KeyVaultPlugin()
        sanitized = plugin._sanitize_name("config.json")
        assert sanitized == "config_json"
        assert "." not in sanitized

    def test_sanitize_name_with_spaces(self):
        """Test sanitization replaces spaces with underscores."""
        plugin = KeyVaultPlugin()
        sanitized = plugin._sanitize_name("my secret name")
        assert sanitized == "my_secret_name"
        assert " " not in sanitized

    def test_sanitize_name_starting_with_number(self):
        """Test sanitization adds prefix for names starting with number."""
        plugin = KeyVaultPlugin()
        sanitized = plugin._sanitize_name("123-secret")
        assert sanitized.startswith("kv_")
        assert sanitized == "kv_123_secret"

    def test_sanitize_name_uppercase(self):
        """Test sanitization converts to lowercase."""
        plugin = KeyVaultPlugin()
        sanitized = plugin._sanitize_name("MY-SECRET")
        assert sanitized == "my_secret"
        assert sanitized.islower()

    def test_sanitize_name_complex(self):
        """Test sanitization handles complex names."""
        plugin = KeyVaultPlugin()
        sanitized = plugin._sanitize_name("123-My.Secret Name")
        assert sanitized == "kv_123_my_secret_name"

    def test_sanitize_name_already_valid(self):
        """Test sanitization preserves already valid names."""
        plugin = KeyVaultPlugin()
        sanitized = plugin._sanitize_name("my_secret_name")
        assert sanitized == "my_secret_name"


class TestKeyVaultPluginEdgeCases:
    """Test edge cases for Key Vault plugin."""

    def test_empty_vault_uri_in_properties(self):
        """Test handling of resource with empty vault URI."""
        plugin = KeyVaultPlugin()
        resource = {
            "id": "/subscriptions/123/vaults/kv",
            "type": "Microsoft.KeyVault/vaults",
            "name": "kv",
            "properties": {"vaultUri": ""},  # Empty URI
        }

        # Should still validate (stub doesn't actually use URI yet)
        assert plugin.validate_resource(resource) is True

    def test_generate_code_with_empty_secret_name(self):
        """Test code generation with empty secret name."""
        plugin = KeyVaultPlugin()
        items = [
            DataPlaneItem(
                name="",  # Empty name
                item_type="secret",
                properties={},
                source_resource_id="/subscriptions/123/vaults/kv",
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Should handle empty name gracefully
        assert "azurerm_key_vault_secret" in code

    def test_generate_code_with_special_characters_in_name(self):
        """Test code generation with special characters in secret name."""
        plugin = KeyVaultPlugin()
        items = [
            DataPlaneItem(
                name="my-special@secret#123",
                item_type="secret",
                properties={},
                source_resource_id="/subscriptions/123/vaults/kv",
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Name should be sanitized in Terraform resource
        assert "azurerm_key_vault_secret" in code
        # Original name should still appear in the name parameter
        assert "my-special@secret#123" in code

    def test_generate_code_preserves_original_name_in_resource(self):
        """Test that original secret name is preserved in resource definition."""
        plugin = KeyVaultPlugin()
        items = [
            DataPlaneItem(
                name="original-name",
                item_type="secret",
                properties={},
                source_resource_id="/subscriptions/123/vaults/kv",
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Original name should appear in the name parameter
        assert 'name         = "original-name"' in code
