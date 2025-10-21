"""
Unit tests for Storage Account data plane plugin.

Tests cover:
- Storage Account resource validation
- Discovery functionality
- Terraform code generation
- Replication functionality with AzCopy
"""

import subprocess
from unittest.mock import Mock, patch

import pytest

from src.iac.plugins.base_plugin import DataPlaneItem, ReplicationResult
from src.iac.plugins.storage_plugin import StoragePlugin


class TestStoragePlugin:
    """Test cases for StoragePlugin."""

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


class TestStorageValidation:
    """Test resource validation for Storage plugin."""

    def test_validate_valid_storage_resource(self):
        """Test validation succeeds for valid Storage Account resource."""
        plugin = StoragePlugin()
        resource = {
            "id": "/subscriptions/123/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/mystorageacct",
            "type": "Microsoft.Storage/storageAccounts",
            "name": "mystorageacct",
            "properties": {},
        }

        assert plugin.validate_resource(resource) is True

    def test_validate_wrong_resource_type(self):
        """Test validation fails for wrong resource type."""
        plugin = StoragePlugin()
        resource = {
            "id": "/subscriptions/123",
            "type": "Microsoft.KeyVault/vaults",  # Wrong type
            "name": "keyvault",
        }

        assert plugin.validate_resource(resource) is False

    def test_validate_missing_id(self):
        """Test validation fails for missing resource ID."""
        plugin = StoragePlugin()
        resource = {
            "type": "Microsoft.Storage/storageAccounts",
            "name": "mystorageacct",
            # Missing 'id'
        }

        assert plugin.validate_resource(resource) is False

    def test_validate_none_resource(self):
        """Test validation fails for None resource."""
        plugin = StoragePlugin()
        assert plugin.validate_resource(None) is False


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
                properties={"public_access": "None"},
                source_resource_id="/subscriptions/123/storageAccounts/storage",
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Check for Terraform resource
        assert "azurerm_storage_container" in code
        assert '"data"' in code
        assert "container_access_type" in code

    def test_generate_code_for_multiple_containers(self):
        """Test code generation for multiple containers."""
        plugin = StoragePlugin()
        items = [
            DataPlaneItem(
                name="container1",
                item_type="container",
                properties={"public_access": "None"},
                source_resource_id="/subscriptions/123/storageAccounts/storage",
            ),
            DataPlaneItem(
                name="container2",
                item_type="container",
                properties={"public_access": "blob"},
                source_resource_id="/subscriptions/123/storageAccounts/storage",
            ),
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Check both containers are present
        assert "container1" in code
        assert "container2" in code
        assert code.count("azurerm_storage_container") == 2

    def test_generate_code_with_blobs_includes_migration_notes(self):
        """Test code generation includes migration notes for blobs."""
        plugin = StoragePlugin()
        items = [
            DataPlaneItem(
                name="data",
                item_type="container",
                properties={},
                source_resource_id="/subscriptions/123/storageAccounts/storage",
            ),
            DataPlaneItem(
                name="data/file.txt",
                item_type="blob",
                properties={"container": "data", "size": 1024},
                source_resource_id="/subscriptions/123/storageAccounts/storage",
            ),
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Check migration notes are present
        assert "AzCopy" in code
        assert "azcopy copy" in code
        assert "Discovered 1 blob(s)" in code

    def test_generate_code_unsupported_format_raises_error(self):
        """Test code generation raises error for unsupported format."""
        plugin = StoragePlugin()
        items = [
            DataPlaneItem(
                name="container",
                item_type="container",
                properties={},
                source_resource_id="/subscriptions/123/storageAccounts/storage",
            )
        ]

        with pytest.raises(ValueError, match="not supported"):
            plugin.generate_replication_code(items, "bicep")


class TestStorageReplication:
    """Test replication functionality for Storage plugin."""

    @patch("src.iac.plugins.storage_plugin.StoragePlugin.discover")
    @patch("subprocess.run")
    def test_replicate_with_no_containers_returns_success_with_warning(
        self, mock_subprocess, mock_discover
    ):
        """Test replicate returns success with warning when no containers found."""
        plugin = StoragePlugin()
        source = {
            "id": "/subscriptions/123/storageAccounts/source",
            "type": "Microsoft.Storage/storageAccounts",
            "name": "sourcestorage",
        }
        target = {
            "id": "/subscriptions/123/storageAccounts/target",
            "type": "Microsoft.Storage/storageAccounts",
            "name": "targetstorage",
        }

        # Mock discovery to return no containers (only blobs)
        mock_discover.return_value = [
            DataPlaneItem(
                name="data/file.txt",
                item_type="blob",
                properties={},
                source_resource_id=source["id"],
            )
        ]

        result = plugin.replicate(source, target)

        assert isinstance(result, ReplicationResult)
        assert result.success is True
        assert result.items_discovered == 1
        assert result.items_replicated == 0
        assert len(result.warnings) > 0
        assert "No containers to replicate" in result.warnings[0]

    @patch("src.iac.plugins.storage_plugin.StoragePlugin.discover")
    @patch("subprocess.run")
    def test_replicate_azcopy_not_found_returns_error(
        self, mock_subprocess, mock_discover
    ):
        """Test replicate returns error when AzCopy is not installed."""
        plugin = StoragePlugin()
        source = {
            "id": "/subscriptions/123/storageAccounts/source",
            "type": "Microsoft.Storage/storageAccounts",
            "name": "sourcestorage",
        }
        target = {
            "id": "/subscriptions/123/storageAccounts/target",
            "type": "Microsoft.Storage/storageAccounts",
            "name": "targetstorage",
        }

        # Mock discovery to return containers
        mock_discover.return_value = [
            DataPlaneItem(
                name="container1",
                item_type="container",
                properties={},
                source_resource_id=source["id"],
            )
        ]

        # Mock AzCopy not found
        mock_subprocess.side_effect = FileNotFoundError("azcopy not found")

        result = plugin.replicate(source, target)

        assert result.success is False
        assert result.items_discovered == 1
        assert result.items_replicated == 0
        assert len(result.errors) == 1
        assert "AzCopy not found" in result.errors[0]
        assert "Install from" in result.errors[0]

    @patch("src.iac.plugins.storage_plugin.StoragePlugin.discover")
    @patch("subprocess.run")
    def test_replicate_azcopy_version_check_fails_returns_error(
        self, mock_subprocess, mock_discover
    ):
        """Test replicate returns error when AzCopy version check fails."""
        plugin = StoragePlugin()
        source = {
            "id": "/subscriptions/123/storageAccounts/source",
            "type": "Microsoft.Storage/storageAccounts",
            "name": "sourcestorage",
        }
        target = {
            "id": "/subscriptions/123/storageAccounts/target",
            "type": "Microsoft.Storage/storageAccounts",
            "name": "targetstorage",
        }

        # Mock discovery to return containers
        mock_discover.return_value = [
            DataPlaneItem(
                name="container1",
                item_type="container",
                properties={},
                source_resource_id=source["id"],
            )
        ]

        # Mock AzCopy version check failing
        mock_subprocess.return_value = Mock(returncode=1, stdout="", stderr="error")

        result = plugin.replicate(source, target)

        assert result.success is False
        assert result.items_replicated == 0
        assert "AzCopy not available" in result.errors[0]

    @patch("src.iac.plugins.storage_plugin.StoragePlugin.discover")
    @patch("subprocess.run")
    def test_replicate_successful_single_container(
        self, mock_subprocess, mock_discover
    ):
        """Test successful replication of a single container."""
        plugin = StoragePlugin()
        source = {
            "id": "/subscriptions/123/storageAccounts/source",
            "type": "Microsoft.Storage/storageAccounts",
            "name": "sourcestorage",
        }
        target = {
            "id": "/subscriptions/123/storageAccounts/target",
            "type": "Microsoft.Storage/storageAccounts",
            "name": "targetstorage",
        }

        # Mock discovery to return one container
        mock_discover.return_value = [
            DataPlaneItem(
                name="data",
                item_type="container",
                properties={},
                source_resource_id=source["id"],
            )
        ]

        # Mock successful AzCopy version check and copy
        mock_subprocess.side_effect = [
            Mock(returncode=0, stdout="azcopy version 10.16.0", stderr=""),
            Mock(returncode=0, stdout="Copy successful", stderr=""),
        ]

        result = plugin.replicate(source, target)

        assert result.success is True
        assert result.items_discovered == 1
        assert result.items_replicated == 1
        assert len(result.errors) == 0
        assert mock_subprocess.call_count == 2

        # Verify AzCopy was called with correct arguments
        copy_call = mock_subprocess.call_args_list[1]
        args = copy_call[0][0]
        assert args[0] == "azcopy"
        assert args[1] == "copy"
        assert "sourcestorage.blob.core.windows.net/data/*" in args[2]
        assert "targetstorage.blob.core.windows.net/data/" in args[3]
        assert "--recursive" in args
        assert "--overwrite=ifSourceNewer" in args

    @patch("src.iac.plugins.storage_plugin.StoragePlugin.discover")
    @patch("subprocess.run")
    def test_replicate_multiple_containers_partial_success(
        self, mock_subprocess, mock_discover
    ):
        """Test replication with multiple containers where some fail."""
        plugin = StoragePlugin()
        source = {
            "id": "/subscriptions/123/storageAccounts/source",
            "type": "Microsoft.Storage/storageAccounts",
            "name": "sourcestorage",
        }
        target = {
            "id": "/subscriptions/123/storageAccounts/target",
            "type": "Microsoft.Storage/storageAccounts",
            "name": "targetstorage",
        }

        # Mock discovery to return three containers
        mock_discover.return_value = [
            DataPlaneItem(
                name="container1",
                item_type="container",
                properties={},
                source_resource_id=source["id"],
            ),
            DataPlaneItem(
                name="container2",
                item_type="container",
                properties={},
                source_resource_id=source["id"],
            ),
            DataPlaneItem(
                name="container3",
                item_type="container",
                properties={},
                source_resource_id=source["id"],
            ),
        ]

        # Mock AzCopy: version check succeeds, first copy succeeds, second fails, third succeeds
        mock_subprocess.side_effect = [
            Mock(returncode=0, stdout="azcopy version 10.16.0", stderr=""),
            Mock(returncode=0, stdout="Success", stderr=""),
            Mock(returncode=1, stdout="", stderr="Authentication failed"),
            Mock(returncode=0, stdout="Success", stderr=""),
        ]

        result = plugin.replicate(source, target)

        assert result.success is True  # At least one succeeded
        assert result.items_discovered == 3
        assert result.items_replicated == 2
        assert len(result.errors) == 1
        assert "container2" in result.errors[0]
        assert "Authentication failed" in result.errors[0]

    @patch("src.iac.plugins.storage_plugin.StoragePlugin.discover")
    @patch("subprocess.run")
    def test_replicate_all_containers_fail(self, mock_subprocess, mock_discover):
        """Test replication returns failure when all containers fail."""
        plugin = StoragePlugin()
        source = {
            "id": "/subscriptions/123/storageAccounts/source",
            "type": "Microsoft.Storage/storageAccounts",
            "name": "sourcestorage",
        }
        target = {
            "id": "/subscriptions/123/storageAccounts/target",
            "type": "Microsoft.Storage/storageAccounts",
            "name": "targetstorage",
        }

        # Mock discovery to return two containers
        mock_discover.return_value = [
            DataPlaneItem(
                name="container1",
                item_type="container",
                properties={},
                source_resource_id=source["id"],
            ),
            DataPlaneItem(
                name="container2",
                item_type="container",
                properties={},
                source_resource_id=source["id"],
            ),
        ]

        # Mock AzCopy: version check succeeds, both copies fail
        mock_subprocess.side_effect = [
            Mock(returncode=0, stdout="azcopy version 10.16.0", stderr=""),
            Mock(returncode=1, stdout="", stderr="Error 1"),
            Mock(returncode=1, stdout="", stderr="Error 2"),
        ]

        result = plugin.replicate(source, target)

        assert result.success is False  # All failed
        assert result.items_replicated == 0
        assert len(result.errors) == 2

    @patch("src.iac.plugins.storage_plugin.StoragePlugin.discover")
    @patch("subprocess.run")
    def test_replicate_timeout_handling(self, mock_subprocess, mock_discover):
        """Test replication handles timeout correctly."""
        plugin = StoragePlugin()
        source = {
            "id": "/subscriptions/123/storageAccounts/source",
            "type": "Microsoft.Storage/storageAccounts",
            "name": "sourcestorage",
        }
        target = {
            "id": "/subscriptions/123/storageAccounts/target",
            "type": "Microsoft.Storage/storageAccounts",
            "name": "targetstorage",
        }

        # Mock discovery to return one container
        mock_discover.return_value = [
            DataPlaneItem(
                name="largedata",
                item_type="container",
                properties={},
                source_resource_id=source["id"],
            )
        ]

        # Mock AzCopy: version check succeeds, copy times out
        mock_subprocess.side_effect = [
            Mock(returncode=0, stdout="azcopy version 10.16.0", stderr=""),
            subprocess.TimeoutExpired("azcopy", 600),
        ]

        result = plugin.replicate(source, target)

        assert result.success is False
        assert result.items_replicated == 0
        assert len(result.errors) == 1
        assert "Timeout" in result.errors[0]
        assert "exceeded 10 minutes" in result.errors[0]

    @patch("src.iac.plugins.storage_plugin.StoragePlugin.discover")
    def test_replicate_discovery_failure_returns_error(self, mock_discover):
        """Test replicate returns error when discovery fails."""
        plugin = StoragePlugin()
        source = {
            "id": "/subscriptions/123/storageAccounts/source",
            "type": "Microsoft.Storage/storageAccounts",
            "name": "sourcestorage",
        }
        target = {
            "id": "/subscriptions/123/storageAccounts/target",
            "type": "Microsoft.Storage/storageAccounts",
            "name": "targetstorage",
        }

        # Mock discovery to raise exception
        mock_discover.side_effect = Exception("Network error")

        result = plugin.replicate(source, target)

        assert result.success is False
        assert result.items_discovered == 0
        assert result.items_replicated == 0
        assert len(result.errors) == 1
        assert "Failed to discover items" in result.errors[0]

    def test_replicate_with_invalid_source_raises_error(self):
        """Test replicate raises error for invalid source."""
        plugin = StoragePlugin()
        invalid_source = {
            "type": "Microsoft.KeyVault/vaults",  # Wrong type
            "name": "keyvault",
        }
        target = {
            "id": "/subscriptions/123/storageAccounts/target",
            "type": "Microsoft.Storage/storageAccounts",
            "name": "targetstorage",
        }

        with pytest.raises(ValueError, match="Invalid source resource"):
            plugin.replicate(invalid_source, target)

    def test_replicate_with_invalid_target_raises_error(self):
        """Test replicate raises error for invalid target."""
        plugin = StoragePlugin()
        source = {
            "id": "/subscriptions/123/storageAccounts/source",
            "type": "Microsoft.Storage/storageAccounts",
            "name": "sourcestorage",
        }
        invalid_target = {
            "type": "Microsoft.KeyVault/vaults",  # Wrong type
            "name": "keyvault",
        }

        with pytest.raises(ValueError, match="Invalid target resource"):
            plugin.replicate(source, invalid_target)


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
        sanitized = plugin._sanitize_name("data.backup")
        assert sanitized == "data_backup"
        assert "." not in sanitized

    def test_sanitize_name_with_spaces(self):
        """Test sanitization replaces spaces with underscores."""
        plugin = StoragePlugin()
        sanitized = plugin._sanitize_name("my container name")
        assert sanitized == "my_container_name"
        assert " " not in sanitized

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
        sanitized = plugin._sanitize_name("123-My.Container Name")
        assert sanitized == "storage_123_my_container_name"

    def test_sanitize_name_already_valid(self):
        """Test sanitization preserves already valid names."""
        plugin = StoragePlugin()
        sanitized = plugin._sanitize_name("my_container_name")
        assert sanitized == "my_container_name"


class TestStoragePluginEdgeCases:
    """Test edge cases for Storage plugin."""

    @patch("src.iac.plugins.storage_plugin.StoragePlugin.discover")
    @patch("subprocess.run")
    def test_replicate_with_empty_container_name(self, mock_subprocess, mock_discover):
        """Test replication handles empty container name."""
        plugin = StoragePlugin()
        source = {
            "id": "/subscriptions/123/storageAccounts/source",
            "type": "Microsoft.Storage/storageAccounts",
            "name": "sourcestorage",
        }
        target = {
            "id": "/subscriptions/123/storageAccounts/target",
            "type": "Microsoft.Storage/storageAccounts",
            "name": "targetstorage",
        }

        # Mock discovery to return container with empty name
        mock_discover.return_value = [
            DataPlaneItem(
                name="",  # Empty name
                item_type="container",
                properties={},
                source_resource_id=source["id"],
            )
        ]

        # Mock AzCopy calls
        mock_subprocess.side_effect = [
            Mock(returncode=0, stdout="azcopy version 10.16.0", stderr=""),
            Mock(returncode=0, stdout="Success", stderr=""),
        ]

        result = plugin.replicate(source, target)

        # Should still attempt replication
        assert result.items_discovered == 1

    @patch("src.iac.plugins.storage_plugin.StoragePlugin.discover")
    @patch("subprocess.run")
    def test_replicate_generic_exception_handling(self, mock_subprocess, mock_discover):
        """Test replication handles unexpected exceptions."""
        plugin = StoragePlugin()
        source = {
            "id": "/subscriptions/123/storageAccounts/source",
            "type": "Microsoft.Storage/storageAccounts",
            "name": "sourcestorage",
        }
        target = {
            "id": "/subscriptions/123/storageAccounts/target",
            "type": "Microsoft.Storage/storageAccounts",
            "name": "targetstorage",
        }

        # Mock discovery to return one container
        mock_discover.return_value = [
            DataPlaneItem(
                name="data",
                item_type="container",
                properties={},
                source_resource_id=source["id"],
            )
        ]

        # Mock AzCopy: version check succeeds, copy raises unexpected exception
        mock_subprocess.side_effect = [
            Mock(returncode=0, stdout="azcopy version 10.16.0", stderr=""),
            RuntimeError("Unexpected error"),
        ]

        result = plugin.replicate(source, target)

        assert result.success is False
        assert result.items_replicated == 0
        assert len(result.errors) == 1
        assert "Unexpected error" in result.errors[0]

    def test_generate_code_preserves_original_name_in_resource(self):
        """Test that original container name is preserved in resource definition."""
        plugin = StoragePlugin()
        items = [
            DataPlaneItem(
                name="original-name",
                item_type="container",
                properties={},
                source_resource_id="/subscriptions/123/storageAccounts/storage",
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Original name should appear in the name parameter
        assert 'name                  = "original-name"' in code
