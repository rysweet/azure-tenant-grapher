"""
Simplified unit tests for Storage Account data plane plugin.

Tests core functionality without requiring Azure SDK to be installed.
"""

import pytest
from unittest.mock import Mock, MagicMock

from src.iac.plugins.base_plugin import (
    DataPlaneItem,
    ReplicationMode,
    ReplicationResult,
    Permission,
)
from src.iac.plugins.storage_plugin import StoragePlugin


class TestStoragePluginBasics:
    """Test basic Storage plugin functionality."""

    def test_plugin_instantiation(self):
        """Test that StoragePlugin can be instantiated."""
        plugin = StoragePlugin()
        assert plugin is not None
        assert plugin.plugin_name == "StoragePlugin"

    def test_supported_resource_type(self):
        """Test that plugin supports correct resource type."""
        plugin = StoragePlugin()
        assert plugin.supported_resource_type == "Microsoft.Storage/storageAccounts"

    def test_supports_terraform_format(self):
        """Test that plugin supports Terraform output format."""
        plugin = StoragePlugin()
        assert plugin.supports_output_format("terraform") is True
        assert plugin.supports_output_format("TERRAFORM") is True

    def test_does_not_support_other_formats(self):
        """Test that plugin doesn't support other formats yet."""
        plugin = StoragePlugin()
        assert plugin.supports_output_format("bicep") is False
        assert plugin.supports_output_format("arm") is False

    def test_supports_both_modes(self):
        """Test that plugin supports both replication modes."""
        plugin = StoragePlugin()
        assert plugin.supports_mode(ReplicationMode.TEMPLATE) is True
        assert plugin.supports_mode(ReplicationMode.REPLICATION) is True


class TestStorageValidation:
    """Test resource validation for Storage plugin."""

    def test_validate_valid_storage_resource(self):
        """Test validation succeeds for valid Storage Account resource."""
        plugin = StoragePlugin()
        resource = {
            "id": "/subscriptions/123/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/mysa",
            "type": "Microsoft.Storage/storageAccounts",
            "name": "mysa",
            "properties": {},
        }

        assert plugin.validate_resource(resource) is True

    def test_validate_wrong_resource_type(self):
        """Test validation fails for wrong resource type."""
        plugin = StoragePlugin()
        resource = {
            "id": "/subscriptions/123",
            "type": "Microsoft.KeyVault/vaults",  # Wrong type
            "name": "kv",
        }

        assert plugin.validate_resource(resource) is False

    def test_validate_missing_id(self):
        """Test validation fails for missing resource ID."""
        plugin = StoragePlugin()
        resource = {
            "type": "Microsoft.Storage/storageAccounts",
            "name": "mysa",
            # Missing 'id'
        }

        assert plugin.validate_resource(resource) is False

    def test_validate_none_resource(self):
        """Test validation fails for None resource."""
        plugin = StoragePlugin()
        assert plugin.validate_resource(None) is False


class TestStoragePermissions:
    """Test permission requirements for Storage plugin."""

    def test_get_required_permissions_template_mode(self):
        """Test permissions for template mode."""
        plugin = StoragePlugin()
        permissions = plugin.get_required_permissions(ReplicationMode.TEMPLATE)

        assert len(permissions) == 1
        perm = permissions[0]
        assert isinstance(perm, Permission)
        assert perm.scope == "resource"
        assert "read" in perm.actions[0].lower()
        assert "read" in perm.data_actions[0].lower()

    def test_get_required_permissions_replication_mode(self):
        """Test permissions for replication mode."""
        plugin = StoragePlugin()
        permissions = plugin.get_required_permissions(ReplicationMode.REPLICATION)

        assert len(permissions) == 1
        perm = permissions[0]
        assert isinstance(perm, Permission)
        assert perm.scope == "resource"

        # Should include both read and write permissions
        data_actions_str = str(perm.data_actions)
        assert "read" in data_actions_str.lower()
        assert "write" in data_actions_str.lower()

        # Should include listKeys action for AzCopy
        assert any("listKeys" in action for action in perm.actions)

    def test_template_has_fewer_permissions_than_replication(self):
        """Test that template mode requires fewer permissions."""
        plugin = StoragePlugin()
        template_perms = plugin.get_required_permissions(ReplicationMode.TEMPLATE)
        replication_perms = plugin.get_required_permissions(ReplicationMode.REPLICATION)

        # Replication should have more data actions
        assert len(replication_perms[0].data_actions) > len(template_perms[0].data_actions)


class TestStorageCodeGeneration:
    """Test IaC code generation for Storage plugin."""

    def test_generate_code_for_empty_items(self):
        """Test code generation with no items."""
        plugin = StoragePlugin()
        code = plugin.generate_replication_code([], "terraform")

        assert "No Storage Account data plane items" in code

    def test_generate_code_for_single_container(self):
        """Test code generation for a single container."""
        plugin = StoragePlugin()
        items = [
            DataPlaneItem(
                name="data",
                item_type="container",
                properties={"public_access": "None", "metadata": {}},
                source_resource_id="/subscriptions/123/storageAccounts/mysa",
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Check for Terraform resource
        assert "azurerm_storage_container" in code
        assert "data" in code
        assert "container_access_type" in code
        assert "DATA MIGRATION NOTE" in code

    def test_generate_code_for_file_share(self):
        """Test code generation for file shares."""
        plugin = StoragePlugin()
        items = [
            DataPlaneItem(
                name="backup",
                item_type="file_share",
                properties={"quota": 100, "metadata": {}},
                source_resource_id="/subscriptions/123/storageAccounts/mysa",
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Check for Terraform resource
        assert "azurerm_storage_share" in code
        assert "backup" in code
        assert "quota" in code
        assert "100" in code

    def test_generate_code_for_table(self):
        """Test code generation for tables."""
        plugin = StoragePlugin()
        items = [
            DataPlaneItem(
                name="logs",
                item_type="table",
                properties={},
                source_resource_id="/subscriptions/123/storageAccounts/mysa",
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Check for Terraform resource
        assert "azurerm_storage_table" in code
        assert "logs" in code

    def test_generate_code_for_queue(self):
        """Test code generation for queues."""
        plugin = StoragePlugin()
        items = [
            DataPlaneItem(
                name="processing",
                item_type="queue",
                properties={"metadata": {}},
                source_resource_id="/subscriptions/123/storageAccounts/mysa",
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Check for Terraform resource
        assert "azurerm_storage_queue" in code
        assert "processing" in code

    def test_generate_code_for_mixed_types(self):
        """Test code generation with multiple item types."""
        plugin = StoragePlugin()
        items = [
            DataPlaneItem(
                name="container1",
                item_type="container",
                properties={"public_access": "None", "metadata": {}},
                source_resource_id="/subscriptions/123/storageAccounts/mysa",
            ),
            DataPlaneItem(
                name="share1",
                item_type="file_share",
                properties={"quota": 50, "metadata": {}},
                source_resource_id="/subscriptions/123/storageAccounts/mysa",
            ),
            DataPlaneItem(
                name="table1",
                item_type="table",
                properties={},
                source_resource_id="/subscriptions/123/storageAccounts/mysa",
            ),
            DataPlaneItem(
                name="queue1",
                item_type="queue",
                properties={"metadata": {}},
                source_resource_id="/subscriptions/123/storageAccounts/mysa",
            ),
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # All sections should be present
        assert "Blob Containers" in code
        assert "File Shares" in code
        assert "Tables" in code
        assert "Queues" in code
        assert "azurerm_storage_container" in code
        assert "azurerm_storage_share" in code
        assert "azurerm_storage_table" in code
        assert "azurerm_storage_queue" in code

    def test_generate_code_includes_blob_migration_notes(self):
        """Test code generation includes AzCopy migration notes for blobs."""
        plugin = StoragePlugin()
        items = [
            DataPlaneItem(
                name="container/blob.txt",
                item_type="blob",
                properties={"container": "container", "size": 1024},
                source_resource_id="/subscriptions/123/storageAccounts/mysa",
                size_bytes=1024,
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Check for migration notes
        assert "AzCopy" in code or "azcopy" in code
        assert "Migration Script" in code

    def test_generate_code_includes_size_information(self):
        """Test code generation includes total size information."""
        plugin = StoragePlugin()
        items = [
            DataPlaneItem(
                name="container/blob1.txt",
                item_type="blob",
                properties={},
                source_resource_id="/subscriptions/123/storageAccounts/mysa",
                size_bytes=1024 * 1024 * 1024,  # 1 GB
            ),
            DataPlaneItem(
                name="container/blob2.txt",
                item_type="blob",
                properties={},
                source_resource_id="/subscriptions/123/storageAccounts/mysa",
                size_bytes=2 * 1024 * 1024 * 1024,  # 2 GB
            ),
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Should include size information
        assert "GB" in code
        assert "sampled size" in code.lower()

    def test_generate_code_unsupported_format_raises_error(self):
        """Test code generation raises error for unsupported format."""
        plugin = StoragePlugin()
        items = [
            DataPlaneItem(
                name="container",
                item_type="container",
                properties={},
                source_resource_id="/subscriptions/123/storageAccounts/mysa",
            )
        ]

        with pytest.raises(ValueError, match="not supported"):
            plugin.generate_replication_code(items, "bicep")


class TestStorageOperationTimeEstimation:
    """Test operation time estimation."""

    def test_estimate_template_mode_is_zero(self):
        """Test template mode has zero estimated time."""
        plugin = StoragePlugin()
        items = [
            DataPlaneItem(
                name="container",
                item_type="container",
                properties={},
                source_resource_id="/subscriptions/123/storageAccounts/mysa",
                size_bytes=1024 * 1024 * 1024,  # 1 GB
            )
        ]

        estimated = plugin.estimate_operation_time(items, ReplicationMode.TEMPLATE)
        assert estimated == 0.0

    def test_estimate_replication_mode_based_on_size(self):
        """Test replication mode estimation uses data size."""
        plugin = StoragePlugin()
        items = [
            DataPlaneItem(
                name="blob",
                item_type="blob",
                properties={},
                source_resource_id="/subscriptions/123/storageAccounts/mysa",
                size_bytes=10 * 1024 * 1024 * 1024,  # 10 GB
            )
        ]

        estimated = plugin.estimate_operation_time(items, ReplicationMode.REPLICATION)
        assert estimated > 0

    def test_estimate_larger_data_takes_more_time(self):
        """Test larger data has longer estimated time."""
        plugin = StoragePlugin()

        small_items = [
            DataPlaneItem(
                name="small",
                item_type="blob",
                properties={},
                source_resource_id="/subscriptions/123/storageAccounts/mysa",
                size_bytes=1 * 1024 * 1024 * 1024,  # 1 GB
            )
        ]

        large_items = [
            DataPlaneItem(
                name="large",
                item_type="blob",
                properties={},
                source_resource_id="/subscriptions/123/storageAccounts/mysa",
                size_bytes=100 * 1024 * 1024 * 1024,  # 100 GB
            )
        ]

        small_time = plugin.estimate_operation_time(small_items, ReplicationMode.REPLICATION)
        large_time = plugin.estimate_operation_time(large_items, ReplicationMode.REPLICATION)

        assert large_time > small_time


class TestStorageNameSanitization:
    """Test name sanitization for Terraform identifiers."""

    def test_sanitize_name_with_hyphens(self):
        """Test sanitization replaces hyphens with underscores."""
        plugin = StoragePlugin()
        sanitized = plugin._sanitize_name("my-container-name")
        assert sanitized == "my_container_name"
        assert "-" not in sanitized

    def test_sanitize_name_with_dots(self):
        """Test sanitization replaces dots with underscores."""
        plugin = StoragePlugin()
        sanitized = plugin._sanitize_name("config.json")
        assert sanitized == "config_json"
        assert "." not in sanitized

    def test_sanitize_name_with_spaces(self):
        """Test sanitization replaces spaces with underscores."""
        plugin = StoragePlugin()
        sanitized = plugin._sanitize_name("my container name")
        assert sanitized == "my_container_name"
        assert " " not in sanitized

    def test_sanitize_name_with_slashes(self):
        """Test sanitization replaces slashes with underscores."""
        plugin = StoragePlugin()
        sanitized = plugin._sanitize_name("container/blob/path")
        assert sanitized == "container_blob_path"
        assert "/" not in sanitized

    def test_sanitize_name_starting_with_number(self):
        """Test sanitization adds prefix for names starting with number."""
        plugin = StoragePlugin()
        sanitized = plugin._sanitize_name("123-container")
        assert sanitized.startswith("storage_")
        assert sanitized == "storage_123_container"

    def test_sanitize_name_uppercase(self):
        """Test sanitization converts to lowercase."""
        plugin = StoragePlugin()
        sanitized = plugin._sanitize_name("MY-CONTAINER")
        assert sanitized == "my_container"
        assert sanitized.islower()

    def test_sanitize_name_complex(self):
        """Test sanitization handles complex names."""
        plugin = StoragePlugin()
        sanitized = plugin._sanitize_name("123-My.Container Name/Path")
        assert sanitized == "storage_123_my_container_name_path"

    def test_sanitize_name_already_valid(self):
        """Test sanitization preserves already valid names."""
        plugin = StoragePlugin()
        sanitized = plugin._sanitize_name("my_container_name")
        assert sanitized == "my_container_name"
