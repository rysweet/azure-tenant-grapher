"""
Tests for DataPlaneCodeGenerator.

Tests the code generation for data plane items including:
- Grouping items by resource type
- File naming and extension handling
- Plugin delegation
- Error handling
"""

from unittest.mock import MagicMock, patch

import pytest

from src.iac.data_plane_code_generator import DataPlaneCodeGenerator
from src.iac.plugins.base_plugin import DataPlaneItem


class TestDataPlaneCodeGenerator:
    """Tests for DataPlaneCodeGenerator class."""

    def test_init_default_format(self):
        """Test initialization with default format."""
        generator = DataPlaneCodeGenerator()
        assert generator.output_format == "terraform"

    def test_init_terraform_format(self):
        """Test initialization with terraform format."""
        generator = DataPlaneCodeGenerator(output_format="terraform")
        assert generator.output_format == "terraform"

    def test_init_bicep_format(self):
        """Test initialization with bicep format."""
        generator = DataPlaneCodeGenerator(output_format="bicep")
        assert generator.output_format == "bicep"

    def test_init_arm_format(self):
        """Test initialization with arm format."""
        generator = DataPlaneCodeGenerator(output_format="arm")
        assert generator.output_format == "arm"

    def test_init_invalid_format(self):
        """Test initialization with invalid format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid output format"):
            DataPlaneCodeGenerator(output_format="invalid")

    def test_get_file_extension_terraform(self):
        """Test file extension for terraform format."""
        generator = DataPlaneCodeGenerator(output_format="terraform")
        assert generator._get_file_extension() == ".tf"

    def test_get_file_extension_bicep(self):
        """Test file extension for bicep format."""
        generator = DataPlaneCodeGenerator(output_format="bicep")
        assert generator._get_file_extension() == ".bicep"

    def test_get_file_extension_arm(self):
        """Test file extension for ARM format."""
        generator = DataPlaneCodeGenerator(output_format="arm")
        assert generator._get_file_extension() == ".json"

    def test_sanitize_resource_type_keyvault(self):
        """Test sanitization of Key Vault resource type."""
        generator = DataPlaneCodeGenerator()
        result = generator._sanitize_resource_type("Microsoft.KeyVault/vaults")
        assert result == "keyvault"

    def test_sanitize_resource_type_storage(self):
        """Test sanitization of Storage resource type."""
        generator = DataPlaneCodeGenerator()
        result = generator._sanitize_resource_type("Microsoft.Storage/storageAccounts")
        assert result == "storage"

    def test_sanitize_resource_type_sql(self):
        """Test sanitization of SQL resource type."""
        generator = DataPlaneCodeGenerator()
        result = generator._sanitize_resource_type("Microsoft.Sql/servers/databases")
        assert result == "sql"

    def test_sanitize_resource_type_web(self):
        """Test sanitization of Web resource type."""
        generator = DataPlaneCodeGenerator()
        result = generator._sanitize_resource_type("Microsoft.Web/sites")
        assert result == "web"

    def test_get_output_filename_terraform(self):
        """Test output filename generation for terraform."""
        generator = DataPlaneCodeGenerator(output_format="terraform")
        filename = generator._get_output_filename("Microsoft.KeyVault/vaults")
        assert filename == "data_plane_keyvault.tf"

    def test_get_output_filename_bicep(self):
        """Test output filename generation for bicep."""
        generator = DataPlaneCodeGenerator(output_format="bicep")
        filename = generator._get_output_filename("Microsoft.Storage/storageAccounts")
        assert filename == "data_plane_storage.bicep"

    def test_get_output_filename_arm(self):
        """Test output filename generation for ARM."""
        generator = DataPlaneCodeGenerator(output_format="arm")
        filename = generator._get_output_filename("Microsoft.Sql/servers/databases")
        assert filename == "data_plane_sql.json"

    def test_get_output_filename_web_sites(self):
        """Test output filename for Microsoft.Web/sites."""
        generator = DataPlaneCodeGenerator()
        filename = generator._get_output_filename("Microsoft.Web/sites")
        assert filename == "data_plane_appservice.tf"

    def test_group_items_by_resource_type(self):
        """Test grouping of items by resource type."""
        generator = DataPlaneCodeGenerator()

        # Create test items
        kv_item = DataPlaneItem(
            name="secret1",
            item_type="secret",
            properties={},
            source_resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1"
        )
        storage_item = DataPlaneItem(
            name="blob1",
            item_type="blob",
            properties={},
            source_resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/sa1"
        )

        items_by_resource = {
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1": [kv_item],
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/sa1": [storage_item],
        }

        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1",
                "type": "Microsoft.KeyVault/vaults",
                "name": "kv1"
            },
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/sa1",
                "type": "Microsoft.Storage/storageAccounts",
                "name": "sa1"
            }
        ]

        result = generator._group_items_by_resource_type(items_by_resource, resources)

        assert len(result) == 2
        assert "Microsoft.KeyVault/vaults" in result
        assert "Microsoft.Storage/storageAccounts" in result
        assert len(result["Microsoft.KeyVault/vaults"]) == 1
        assert len(result["Microsoft.Storage/storageAccounts"]) == 1

    def test_group_items_by_resource_type_multiple_items_same_type(self):
        """Test grouping multiple items of same type."""
        generator = DataPlaneCodeGenerator()

        # Create test items for same resource type
        kv_item1 = DataPlaneItem(
            name="secret1",
            item_type="secret",
            properties={},
            source_resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1"
        )
        kv_item2 = DataPlaneItem(
            name="secret2",
            item_type="secret",
            properties={},
            source_resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv2"
        )

        items_by_resource = {
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1": [kv_item1],
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv2": [kv_item2],
        }

        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1",
                "type": "Microsoft.KeyVault/vaults",
                "name": "kv1"
            },
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv2",
                "type": "Microsoft.KeyVault/vaults",
                "name": "kv2"
            }
        ]

        result = generator._group_items_by_resource_type(items_by_resource, resources)

        assert len(result) == 1
        assert "Microsoft.KeyVault/vaults" in result
        assert len(result["Microsoft.KeyVault/vaults"]) == 2

    def test_generate_empty_items(self, tmp_path):
        """Test generation with no items returns empty list."""
        generator = DataPlaneCodeGenerator()
        result = generator.generate({}, [], tmp_path)
        assert result == []

    @patch('src.iac.data_plane_code_generator.PluginRegistry')
    def test_generate_with_items(self, mock_registry, tmp_path):
        """Test successful code generation with items."""
        # Setup mock plugin
        mock_plugin = MagicMock()
        mock_plugin.plugin_name = "MockPlugin"
        mock_plugin.supports_output_format.return_value = True
        mock_plugin.generate_replication_code.return_value = "# Generated code\n"
        mock_registry.get_plugin.return_value = mock_plugin

        generator = DataPlaneCodeGenerator()

        # Create test data
        kv_item = DataPlaneItem(
            name="secret1",
            item_type="secret",
            properties={},
            source_resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1"
        )

        items_by_resource = {
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1": [kv_item],
        }

        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1",
                "type": "Microsoft.KeyVault/vaults",
                "name": "kv1"
            }
        ]

        # Generate code
        result = generator.generate(items_by_resource, resources, tmp_path)

        # Verify
        assert len(result) == 1
        assert result[0].name == "data_plane_keyvault.tf"
        assert result[0].exists()

        # Verify file content
        with open(result[0]) as f:
            content = f.read()
            assert content == "# Generated code\n"

        # Verify plugin was called correctly
        mock_registry.get_plugin.assert_called_once_with("Microsoft.KeyVault/vaults")
        mock_plugin.supports_output_format.assert_called_once_with("terraform")
        mock_plugin.generate_replication_code.assert_called_once()

    @patch('src.iac.data_plane_code_generator.PluginRegistry')
    def test_generate_no_plugin_available(self, mock_registry, tmp_path):
        """Test generation when no plugin is available."""
        mock_registry.get_plugin.return_value = None

        generator = DataPlaneCodeGenerator()

        kv_item = DataPlaneItem(
            name="secret1",
            item_type="secret",
            properties={},
            source_resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1"
        )

        items_by_resource = {
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1": [kv_item],
        }

        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1",
                "type": "Microsoft.KeyVault/vaults",
                "name": "kv1"
            }
        ]

        # Generate code - should skip and return empty list
        result = generator.generate(items_by_resource, resources, tmp_path)
        assert result == []

    @patch('src.iac.data_plane_code_generator.PluginRegistry')
    def test_generate_plugin_unsupported_format(self, mock_registry, tmp_path):
        """Test generation when plugin doesn't support format."""
        mock_plugin = MagicMock()
        mock_plugin.plugin_name = "MockPlugin"
        mock_plugin.supports_output_format.return_value = False
        mock_registry.get_plugin.return_value = mock_plugin

        generator = DataPlaneCodeGenerator(output_format="bicep")

        kv_item = DataPlaneItem(
            name="secret1",
            item_type="secret",
            properties={},
            source_resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1"
        )

        items_by_resource = {
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1": [kv_item],
        }

        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1",
                "type": "Microsoft.KeyVault/vaults",
                "name": "kv1"
            }
        ]

        # Generate code - should skip and return empty list
        result = generator.generate(items_by_resource, resources, tmp_path)
        assert result == []

    @patch('src.iac.data_plane_code_generator.PluginRegistry')
    def test_generate_plugin_returns_empty_code(self, mock_registry, tmp_path):
        """Test generation when plugin returns empty code."""
        mock_plugin = MagicMock()
        mock_plugin.plugin_name = "MockPlugin"
        mock_plugin.supports_output_format.return_value = True
        mock_plugin.generate_replication_code.return_value = ""
        mock_registry.get_plugin.return_value = mock_plugin

        generator = DataPlaneCodeGenerator()

        kv_item = DataPlaneItem(
            name="secret1",
            item_type="secret",
            properties={},
            source_resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1"
        )

        items_by_resource = {
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1": [kv_item],
        }

        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1",
                "type": "Microsoft.KeyVault/vaults",
                "name": "kv1"
            }
        ]

        # Generate code - should skip and return empty list
        result = generator.generate(items_by_resource, resources, tmp_path)
        assert result == []

    @patch('src.iac.data_plane_code_generator.PluginRegistry')
    def test_generate_plugin_raises_exception(self, mock_registry, tmp_path):
        """Test generation continues after plugin exception."""
        mock_plugin = MagicMock()
        mock_plugin.plugin_name = "MockPlugin"
        mock_plugin.supports_output_format.return_value = True
        mock_plugin.generate_replication_code.side_effect = Exception("Plugin error")
        mock_registry.get_plugin.return_value = mock_plugin

        generator = DataPlaneCodeGenerator()

        kv_item = DataPlaneItem(
            name="secret1",
            item_type="secret",
            properties={},
            source_resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1"
        )

        items_by_resource = {
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1": [kv_item],
        }

        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1",
                "type": "Microsoft.KeyVault/vaults",
                "name": "kv1"
            }
        ]

        # Generate code - should handle exception and return empty list
        result = generator.generate(items_by_resource, resources, tmp_path)
        assert result == []

    @patch('src.iac.data_plane_code_generator.PluginRegistry')
    def test_generate_multiple_resource_types(self, mock_registry, tmp_path):
        """Test generation with multiple resource types."""
        # Setup mock plugins
        mock_kv_plugin = MagicMock()
        mock_kv_plugin.plugin_name = "KeyVaultPlugin"
        mock_kv_plugin.supports_output_format.return_value = True
        mock_kv_plugin.generate_replication_code.return_value = "# KeyVault code\n"

        mock_storage_plugin = MagicMock()
        mock_storage_plugin.plugin_name = "StoragePlugin"
        mock_storage_plugin.supports_output_format.return_value = True
        mock_storage_plugin.generate_replication_code.return_value = "# Storage code\n"

        def get_plugin_side_effect(resource_type):
            if resource_type == "Microsoft.KeyVault/vaults":
                return mock_kv_plugin
            elif resource_type == "Microsoft.Storage/storageAccounts":
                return mock_storage_plugin
            return None

        mock_registry.get_plugin.side_effect = get_plugin_side_effect

        generator = DataPlaneCodeGenerator()

        # Create test data
        kv_item = DataPlaneItem(
            name="secret1",
            item_type="secret",
            properties={},
            source_resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1"
        )
        storage_item = DataPlaneItem(
            name="blob1",
            item_type="blob",
            properties={},
            source_resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/sa1"
        )

        items_by_resource = {
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1": [kv_item],
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/sa1": [storage_item],
        }

        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1",
                "type": "Microsoft.KeyVault/vaults",
                "name": "kv1"
            },
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/sa1",
                "type": "Microsoft.Storage/storageAccounts",
                "name": "sa1"
            }
        ]

        # Generate code
        result = generator.generate(items_by_resource, resources, tmp_path)

        # Verify
        assert len(result) == 2
        filenames = [p.name for p in result]
        assert "data_plane_keyvault.tf" in filenames
        assert "data_plane_storage.tf" in filenames

        # Verify all files exist and have content
        for path in result:
            assert path.exists()
            with open(path) as f:
                content = f.read()
                assert len(content) > 0
