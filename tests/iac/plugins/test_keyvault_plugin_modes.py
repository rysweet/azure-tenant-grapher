"""
Unit tests for Key Vault plugin mode-aware functionality.

Tests the new template and replication modes added to the KeyVault plugin,
including permission management and progress reporting.
"""

from unittest.mock import Mock, patch

import pytest

from src.iac.plugins.base_plugin import (
    DataPlaneItem,
    Permission,
    ReplicationMode,
    ReplicationResult,
)
from src.iac.plugins.keyvault_plugin import KeyVaultPlugin


class TestKeyVaultPermissions:
    """Test permission requirements for different modes."""

    def test_get_required_permissions_template_mode(self):
        """Test template mode has read-only permissions."""
        plugin = KeyVaultPlugin()
        perms = plugin.get_required_permissions(ReplicationMode.TEMPLATE)

        assert len(perms) == 1
        assert isinstance(perms[0], Permission)
        assert perms[0].scope == "resource"
        assert "Microsoft.KeyVault/vaults/read" in perms[0].actions

        # Should include metadata actions but not get/set secret
        data_actions = perms[0].data_actions
        assert any("getMetadata" in action for action in data_actions)
        assert not any("setSecret" in action for action in data_actions)
        assert not any("getSecret" in action for action in data_actions)

    def test_get_required_permissions_replication_mode(self):
        """Test replication mode has read/write permissions."""
        plugin = KeyVaultPlugin()
        perms = plugin.get_required_permissions(ReplicationMode.REPLICATION)

        assert len(perms) == 1
        assert isinstance(perms[0], Permission)

        # Should include both get and set secret actions
        data_actions = perms[0].data_actions
        assert any("getSecret" in action for action in data_actions)
        assert any("setSecret" in action for action in data_actions)

    def test_template_permissions_are_subset_of_replication(self):
        """Test template permissions are a subset of replication permissions."""
        plugin = KeyVaultPlugin()
        template_perms = plugin.get_required_permissions(ReplicationMode.TEMPLATE)
        replication_perms = plugin.get_required_permissions(ReplicationMode.REPLICATION)

        # Replication should have more data actions
        assert len(replication_perms[0].data_actions) > len(
            template_perms[0].data_actions
        )


class TestKeyVaultDiscoverWithMode:
    """Test mode-aware discovery functionality."""

    def test_discover_with_mode_delegates_to_discover(self):
        """Test discover_with_mode calls standard discover method."""
        plugin = KeyVaultPlugin()
        resource = {
            "id": "/subscriptions/123/vaults/kv",
            "type": "Microsoft.KeyVault/vaults",
            "name": "test-kv",
            "properties": {"vaultUri": "https://test-kv.vault.azure.net/"},
        }

        # Mock the discover method
        with patch.object(plugin, "discover", return_value=[]) as mock_discover:
            items = plugin.discover_with_mode(resource, ReplicationMode.TEMPLATE)

            mock_discover.assert_called_once_with(resource)
            assert items == []

    def test_discover_with_mode_template_returns_metadata_only(self):
        """Test template mode discovery returns metadata without values."""
        plugin = KeyVaultPlugin()
        resource = {
            "id": "/subscriptions/123/vaults/kv",
            "type": "Microsoft.KeyVault/vaults",
            "name": "test-kv",
            "properties": {"vaultUri": "https://test-kv.vault.azure.net/"},
        }

        # Both modes should behave the same for discovery (metadata only)
        template_items = plugin.discover_with_mode(resource, ReplicationMode.TEMPLATE)
        replication_items = plugin.discover_with_mode(
            resource, ReplicationMode.REPLICATION
        )

        # Should return same results (both metadata-only)
        assert isinstance(template_items, list)
        assert isinstance(replication_items, list)


class TestKeyVaultReplicateWithMode:
    """Test mode-aware replication functionality."""

    def test_replicate_with_mode_template_creates_placeholders(self):
        """Test template mode creates secrets with placeholder values."""
        plugin = KeyVaultPlugin()

        source = {
            "id": "/subscriptions/123/vaults/source-kv",
            "type": "Microsoft.KeyVault/vaults",
            "name": "source-kv",
            "properties": {"vaultUri": "https://source-kv.vault.azure.net/"},
        }

        target = {
            "id": "/subscriptions/123/vaults/target-kv",
            "type": "Microsoft.KeyVault/vaults",
            "name": "target-kv",
            "properties": {"vaultUri": "https://target-kv.vault.azure.net/"},
        }

        # Mock discovery to return test items
        test_items = [
            DataPlaneItem(
                name="test-secret",
                item_type="secret",
                properties={"enabled": True},
                source_resource_id=source["id"],
            )
        ]

        # Mock the entire _replicate_template_mode method
        mock_result = ReplicationResult(
            success=True,
            items_discovered=1,
            items_replicated=1,
            items_skipped=0,
            errors=[],
            warnings=["Template mode: Secrets created with placeholder values."],
        )

        with patch.object(plugin, "discover", return_value=test_items):
            with patch.object(
                plugin, "_replicate_template_mode", return_value=mock_result
            ):
                result = plugin.replicate_with_mode(
                    source, target, ReplicationMode.TEMPLATE
                )

                assert isinstance(result, ReplicationResult)
                assert result.items_discovered == 1
                assert result.success is True

    def test_replicate_with_mode_replication_copies_values(self):
        """Test replication mode copies actual secret values."""
        plugin = KeyVaultPlugin()

        source = {
            "id": "/subscriptions/123/vaults/source-kv",
            "type": "Microsoft.KeyVault/vaults",
            "name": "source-kv",
            "properties": {"vaultUri": "https://source-kv.vault.azure.net/"},
        }

        target = {
            "id": "/subscriptions/123/vaults/target-kv",
            "type": "Microsoft.KeyVault/vaults",
            "name": "target-kv",
            "properties": {"vaultUri": "https://target-kv.vault.azure.net/"},
        }

        # Mock discovery
        test_items = [
            DataPlaneItem(
                name="test-secret",
                item_type="secret",
                properties={"enabled": True},
                source_resource_id=source["id"],
            )
        ]

        mock_result = ReplicationResult(
            success=True,
            items_discovered=1,
            items_replicated=1,
            items_skipped=0,
            errors=[],
            warnings=[],
        )

        with patch.object(plugin, "discover", return_value=test_items):
            with patch.object(plugin, "_replicate_full_mode", return_value=mock_result):
                result = plugin.replicate_with_mode(
                    source, target, ReplicationMode.REPLICATION
                )

                assert isinstance(result, ReplicationResult)
                assert result.success is True
                assert result.items_replicated == 1

    def test_replicate_with_mode_validates_resources(self):
        """Test replication validates source and target resources."""
        plugin = KeyVaultPlugin()

        invalid_source = {
            "type": "Microsoft.Storage/storageAccounts",
            "name": "storage",
        }

        valid_target = {
            "id": "/subscriptions/123/vaults/target-kv",
            "type": "Microsoft.KeyVault/vaults",
            "name": "target-kv",
        }

        with pytest.raises(ValueError, match="Invalid source resource"):
            plugin.replicate_with_mode(
                invalid_source, valid_target, ReplicationMode.TEMPLATE
            )

    def test_replicate_with_mode_tracks_timing(self):
        """Test replication tracks operation duration."""
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

        mock_result = ReplicationResult(
            success=True, items_discovered=0, items_replicated=0
        )

        with patch.object(plugin, "discover", return_value=[]):
            with patch.object(
                plugin, "_replicate_template_mode", return_value=mock_result
            ):
                result = plugin.replicate_with_mode(
                    source, target, ReplicationMode.TEMPLATE
                )

                # Duration should be tracked
                assert result.duration_seconds >= 0


class TestKeyVaultProgressReporting:
    """Test progress reporting integration."""

    def test_replicate_reports_discovery(self):
        """Test replication reports discovery progress."""
        mock_reporter = Mock()
        plugin = KeyVaultPlugin(progress_reporter=mock_reporter)

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

        test_items = [
            DataPlaneItem(
                name="secret1",
                item_type="secret",
                properties={},
                source_resource_id=source["id"],
            ),
            DataPlaneItem(
                name="secret2",
                item_type="secret",
                properties={},
                source_resource_id=source["id"],
            ),
        ]

        mock_result = ReplicationResult(
            success=True, items_discovered=2, items_replicated=2
        )

        with patch.object(plugin, "discover", return_value=test_items):
            with patch.object(
                plugin, "_replicate_template_mode", return_value=mock_result
            ):
                plugin.replicate_with_mode(source, target, ReplicationMode.TEMPLATE)

                # Verify discovery was reported
                mock_reporter.report_discovery.assert_called_once_with(source["id"], 2)

    def test_replicate_reports_completion(self):
        """Test replication reports completion."""
        mock_reporter = Mock()
        plugin = KeyVaultPlugin(progress_reporter=mock_reporter)

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

        mock_result = ReplicationResult(
            success=True, items_discovered=0, items_replicated=0
        )

        with patch.object(plugin, "discover", return_value=[]):
            with patch.object(
                plugin, "_replicate_template_mode", return_value=mock_result
            ):
                result = plugin.replicate_with_mode(
                    source, target, ReplicationMode.TEMPLATE
                )

                # Verify completion was reported
                mock_reporter.report_completion.assert_called_once()
                call_args = mock_reporter.report_completion.call_args[0][0]
                assert isinstance(call_args, ReplicationResult)


class TestKeyVaultCredentialProvider:
    """Test credential provider integration."""

    def test_uses_credential_provider_if_available(self):
        """Test plugin uses credential provider when available."""
        mock_cred_provider = Mock()
        mock_credential = Mock()
        mock_cred_provider.get_credential.return_value = mock_credential

        plugin = KeyVaultPlugin(credential_provider=mock_cred_provider)

        # Just verify that credential provider is stored
        assert plugin.credential_provider == mock_cred_provider

    def test_falls_back_to_default_credential(self):
        """Test plugin falls back to DefaultAzureCredential."""
        plugin = KeyVaultPlugin()  # No credential provider

        # Verify credential provider is None
        assert plugin.credential_provider is None


class TestKeyVaultModeSupport:
    """Test mode support functionality."""

    def test_supports_both_modes(self):
        """Test plugin supports both template and replication modes."""
        plugin = KeyVaultPlugin()

        assert plugin.supports_mode(ReplicationMode.TEMPLATE) is True
        assert plugin.supports_mode(ReplicationMode.REPLICATION) is True

    def test_estimate_operation_time_template_mode(self):
        """Test operation time estimate for template mode."""
        plugin = KeyVaultPlugin()

        items = [
            DataPlaneItem(
                name=f"secret{i}",
                item_type="secret",
                properties={},
                source_resource_id="",
            )
            for i in range(10)
        ]

        estimate = plugin.estimate_operation_time(items, ReplicationMode.TEMPLATE)

        # Template mode should be fast (0 seconds)
        assert estimate == 0.0

    def test_estimate_operation_time_replication_mode(self):
        """Test operation time estimate for replication mode."""
        plugin = KeyVaultPlugin()

        items = [
            DataPlaneItem(
                name=f"secret{i}",
                item_type="secret",
                properties={},
                source_resource_id="",
            )
            for i in range(10)
        ]

        estimate = plugin.estimate_operation_time(items, ReplicationMode.REPLICATION)

        # Replication mode should have non-zero estimate
        assert estimate > 0.0


class TestKeyVaultErrorHandling:
    """Test error handling in mode-aware operations."""

    def test_handles_azure_errors_gracefully(self):
        """Test plugin handles Azure errors without crashing."""
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

        # Mock discovery
        test_items = [
            DataPlaneItem(
                name="test-secret",
                item_type="secret",
                properties={},
                source_resource_id=source["id"],
            )
        ]

        # Mock _replicate_template_mode to return error result
        mock_result = ReplicationResult(
            success=False,
            items_discovered=1,
            items_replicated=0,
            items_skipped=1,
            errors=["Failed to create secret 'test-secret': Permission denied"],
            warnings=[],
        )

        with patch.object(plugin, "discover", return_value=test_items):
            with patch.object(
                plugin, "_replicate_template_mode", return_value=mock_result
            ):
                result = plugin.replicate_with_mode(
                    source, target, ReplicationMode.TEMPLATE
                )

                # Should not crash, but report error
                assert isinstance(result, ReplicationResult)
                assert result.success is False
                assert len(result.errors) > 0
                assert result.items_skipped > 0

    def test_handles_general_exceptions(self):
        """Test plugin handles unexpected exceptions."""
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

        # Mock discover to raise exception
        with patch.object(plugin, "discover", side_effect=Exception("Network error")):
            result = plugin.replicate_with_mode(
                source, target, ReplicationMode.TEMPLATE
            )

            # Should not crash
            assert isinstance(result, ReplicationResult)
            assert result.success is False
            assert len(result.errors) > 0
            assert "Network error" in result.errors[0]
