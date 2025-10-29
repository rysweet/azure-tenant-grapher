"""
Unit tests for Azure Container Registry data plane plugin.

Tests cover:
- Discovery of repositories, tags, and images
- Code generation for Terraform output
- Replication with both template and replication modes
- Error handling and edge cases
- Size warnings and progress tracking
"""

import json
import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch, call
from typing import Any, Dict, List

import sys
sys.path.insert(0, '/home/azureuser/src/azure-tenant-grapher/src/iac/data_plane_plugins')
sys.path.insert(0, '/home/azureuser/src/azure-tenant-grapher/src/iac/plugins')
from acr_plugin import ContainerRegistryPlugin
from base_plugin import DataPlaneItem, ReplicationMode, ReplicationResult


class TestContainerRegistryPlugin:
    """Test suite for ContainerRegistryPlugin."""

    @pytest.fixture
    def plugin(self):
        """Create plugin instance for testing."""
        return ContainerRegistryPlugin()

    @pytest.fixture
    def sample_registry_resource(self):
        """Sample Container Registry resource for testing."""
        return {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.ContainerRegistry/registries/testacr",
            "type": "Microsoft.ContainerRegistry/registries",
            "name": "testacr",
            "properties": {
                "loginServer": "testacr.azurecr.io",
                "adminUserEnabled": False,
                "sku": {"name": "Standard"}
            }
        }

    @pytest.fixture
    def mock_repository_properties(self):
        """Mock repository properties."""
        mock_props = Mock()
        mock_props.tag_count = 3
        mock_props.manifest_count = 3
        mock_props.created_on = datetime(2024, 1, 1, 12, 0, 0)
        mock_props.last_updated_on = datetime(2024, 1, 10, 12, 0, 0)
        return mock_props

    @pytest.fixture
    def mock_tag_properties(self):
        """Mock tag properties."""
        def create_tag(name: str):
            mock_tag = Mock()
            mock_tag.name = name
            mock_tag.created_on = datetime(2024, 1, 5, 12, 0, 0)
            mock_tag.last_updated_on = datetime(2024, 1, 10, 12, 0, 0)
            return mock_tag
        return create_tag

    @pytest.fixture
    def mock_manifest_properties(self):
        """Mock manifest properties."""
        def create_manifest(size: int = 1048576):
            mock_manifest = Mock()
            mock_manifest.size = size
            mock_manifest.digest = "sha256:abcd1234"
            mock_manifest.architecture = "linux/amd64"
            return mock_manifest
        return create_manifest

    def test_supported_resource_type(self, plugin):
        """Test that plugin reports correct resource type."""
        assert plugin.supported_resource_type == "Microsoft.ContainerRegistry/registries"

    def test_plugin_name(self, plugin):
        """Test plugin name property."""
        assert plugin.plugin_name == "ContainerRegistryPlugin"

    def test_validate_resource_valid(self, plugin, sample_registry_resource):
        """Test resource validation with valid resource."""
        assert plugin.validate_resource(sample_registry_resource) is True

    def test_validate_resource_invalid_type(self, plugin):
        """Test resource validation with wrong resource type."""
        resource = {
            "id": "/subscriptions/test/resourceGroups/rg/providers/Microsoft.KeyVault/vaults/kv",
            "type": "Microsoft.KeyVault/vaults",
            "name": "kv"
        }
        assert plugin.validate_resource(resource) is False

    def test_validate_resource_missing_id(self, plugin):
        """Test resource validation with missing ID."""
        resource = {
            "type": "Microsoft.ContainerRegistry/registries",
            "name": "testacr"
        }
        assert plugin.validate_resource(resource) is False

    def test_validate_resource_empty(self, plugin):
        """Test resource validation with empty resource."""
        assert plugin.validate_resource({}) is False
        assert plugin.validate_resource(None) is False

    def test_get_required_permissions_template_mode(self, plugin):
        """Test required permissions for template mode."""
        perms = plugin.get_required_permissions(ReplicationMode.TEMPLATE)

        assert len(perms) == 1
        assert "Microsoft.ContainerRegistry/registries/read" in perms[0].actions
        assert "Microsoft.ContainerRegistry/registries/metadata/read" in perms[0].data_actions
        assert perms[0].scope == "resource"

    def test_get_required_permissions_replication_mode(self, plugin):
        """Test required permissions for replication mode."""
        perms = plugin.get_required_permissions(ReplicationMode.REPLICATION)

        assert len(perms) == 1
        assert "Microsoft.ContainerRegistry/registries/read" in perms[0].actions
        assert "Microsoft.ContainerRegistry/registries/importImage/action" in perms[0].actions
        assert "Microsoft.ContainerRegistry/registries/pull/read" in perms[0].data_actions
        assert "Microsoft.ContainerRegistry/registries/push/write" in perms[0].data_actions

    @patch('azure.containerregistry.ContainerRegistryClient')
    @patch('azure.identity.DefaultAzureCredential')
    def test_discover_empty_registry(
        self,
        mock_credential,
        mock_client_class,
        plugin,
        sample_registry_resource
    ):
        """Test discovery with registry that has no repositories."""
        # Setup mock client
        mock_client = Mock()
        mock_client.list_repository_names.return_value = iter([])
        mock_client_class.return_value = mock_client

        # Execute discovery
        items = plugin.discover(sample_registry_resource)

        # Verify results
        assert len(items) == 0
        mock_client.list_repository_names.assert_called_once()

    @patch('azure.containerregistry.ContainerRegistryClient')
    @patch('azure.identity.DefaultAzureCredential')
    def test_discover_single_repository(
        self,
        mock_credential,
        mock_client_class,
        plugin,
        sample_registry_resource,
        mock_repository_properties,
        mock_tag_properties,
        mock_manifest_properties
    ):
        """Test discovery with single repository and multiple tags."""
        # Setup mock client
        mock_client = Mock()
        mock_client.list_repository_names.return_value = iter(["myapp"])
        mock_client.get_repository_properties.return_value = mock_repository_properties

        # Setup tag mocks
        tags = [mock_tag_properties("v1.0"), mock_tag_properties("v1.1"), mock_tag_properties("latest")]
        mock_client.list_tag_properties.return_value = iter(tags)

        # Setup manifest mocks
        mock_client.get_manifest_properties.return_value = mock_manifest_properties(1048576)

        mock_client_class.return_value = mock_client

        # Execute discovery
        items = plugin.discover(sample_registry_resource)

        # Verify results
        assert len(items) == 1
        assert items[0].name == "myapp"
        assert items[0].item_type == "repository"
        assert items[0].properties["tag_count"] == 3
        assert "v1.0" in items[0].properties["tags"]
        assert "v1.1" in items[0].properties["tags"]
        assert "latest" in items[0].properties["tags"]
        assert items[0].metadata["registry_name"] == "testacr"
        assert items[0].metadata["login_server"] == "testacr.azurecr.io"
        assert len(items[0].metadata["tag_details"]) == 3

        # Verify size is calculated
        assert items[0].size_bytes == 3 * 1048576  # 3 tags * 1MB each

    @patch('azure.containerregistry.ContainerRegistryClient')
    @patch('azure.identity.DefaultAzureCredential')
    def test_discover_multiple_repositories(
        self,
        mock_credential,
        mock_client_class,
        plugin,
        sample_registry_resource,
        mock_repository_properties,
        mock_tag_properties,
        mock_manifest_properties
    ):
        """Test discovery with multiple repositories."""
        # Setup mock client
        mock_client = Mock()
        mock_client.list_repository_names.return_value = iter(["app1", "app2", "app3"])

        # Each repository has different tags
        def get_repo_props(repo_name):
            mock_props = Mock()
            mock_props.tag_count = 2 if repo_name == "app1" else 1
            mock_props.manifest_count = mock_props.tag_count
            mock_props.created_on = datetime(2024, 1, 1)
            mock_props.last_updated_on = datetime(2024, 1, 10)
            return mock_props

        mock_client.get_repository_properties.side_effect = get_repo_props

        def list_tags(repo_name):
            if repo_name == "app1":
                return iter([mock_tag_properties("v1.0"), mock_tag_properties("v2.0")])
            else:
                return iter([mock_tag_properties("latest")])

        mock_client.list_tag_properties.side_effect = list_tags
        mock_client.get_manifest_properties.return_value = mock_manifest_properties(2097152)

        mock_client_class.return_value = mock_client

        # Execute discovery
        items = plugin.discover(sample_registry_resource)

        # Verify results
        assert len(items) == 3
        repo_names = [item.name for item in items]
        assert "app1" in repo_names
        assert "app2" in repo_names
        assert "app3" in repo_names

        # Verify app1 has 2 tags
        app1_item = next(item for item in items if item.name == "app1")
        assert len(app1_item.properties["tags"]) == 2

        # Verify app2 and app3 have 1 tag each
        app2_item = next(item for item in items if item.name == "app2")
        assert len(app2_item.properties["tags"]) == 1

    @patch('azure.containerregistry.ContainerRegistryClient')
    @patch('azure.identity.DefaultAzureCredential')
    def test_discover_with_progress_reporter(
        self,
        mock_credential,
        mock_client_class,
        sample_registry_resource,
        mock_repository_properties,
        mock_tag_properties,
        mock_manifest_properties
    ):
        """Test discovery with progress reporting."""
        # Create plugin with progress reporter
        mock_progress = Mock()
        plugin = ContainerRegistryPlugin(progress_reporter=mock_progress)

        # Setup mock client
        mock_client = Mock()
        mock_client.list_repository_names.return_value = iter(["app1", "app2"])
        mock_client.get_repository_properties.return_value = mock_repository_properties
        mock_client.list_tag_properties.return_value = iter([mock_tag_properties("latest")])
        mock_client.get_manifest_properties.return_value = mock_manifest_properties()
        mock_client_class.return_value = mock_client

        # Execute discovery
        items = plugin.discover(sample_registry_resource)

        # Verify progress was reported
        assert mock_progress.report_discovery.called
        call_args = mock_progress.report_discovery.call_args[0]
        assert call_args[0] == sample_registry_resource["id"]
        assert call_args[1] == 2  # 2 repositories

    @patch('azure.containerregistry.ContainerRegistryClient')
    @patch('azure.identity.DefaultAzureCredential')
    def test_discover_handles_sdk_errors(
        self,
        mock_credential,
        mock_client_class,
        plugin,
        sample_registry_resource
    ):
        """Test discovery handles Azure SDK errors gracefully."""
        from azure.core.exceptions import HttpResponseError

        # Setup mock client to raise error
        mock_client = Mock()
        mock_client.list_repository_names.side_effect = HttpResponseError("Authentication failed")
        mock_client_class.return_value = mock_client

        # Execute discovery - should not raise, but return empty list
        items = plugin.discover(sample_registry_resource)

        # Verify empty result
        assert len(items) == 0

    def test_discover_without_azure_sdk(self, plugin, sample_registry_resource):
        """Test discovery when Azure SDK is not installed."""
        with patch.dict('sys.modules', {'azure.containerregistry': None}):
            # This should handle ImportError gracefully
            items = plugin.discover(sample_registry_resource)
            assert len(items) == 0

    def test_generate_replication_code_empty(self, plugin):
        """Test code generation with no repositories."""
        code = plugin.generate_replication_code([])

        assert "# No Container Registry repositories to replicate" in code

    def test_generate_replication_code_single_repo(self, plugin):
        """Test code generation with single repository."""
        items = [
            DataPlaneItem(
                name="myapp",
                item_type="repository",
                properties={
                    "tag_count": 2,
                    "tags": ["v1.0", "latest"]
                },
                source_resource_id="/subscriptions/test/resourceGroups/rg/providers/Microsoft.ContainerRegistry/registries/acr",
                metadata={
                    "registry_name": "testacr",
                    "login_server": "testacr.azurecr.io",
                    "tag_details": [
                        {"tag": "v1.0", "size_bytes": 1048576},
                        {"tag": "latest", "size_bytes": 1048576}
                    ]
                },
                size_bytes=2097152
            )
        ]

        code = plugin.generate_replication_code(items)

        # Verify content
        assert "# Container Registry Repositories" in code
        assert "# Repository: myapp" in code
        assert "#   Tags: 2" in code
        assert "#     - v1.0" in code
        assert "#     - latest" in code
        assert "az acr import" in code
        assert "docker pull" in code

    def test_generate_replication_code_large_registry_warnings(self, plugin):
        """Test code generation includes size warnings for large registries."""
        # Create items totaling 60GB
        large_size = 60 * 1024 * 1024 * 1024  # 60GB
        items = [
            DataPlaneItem(
                name=f"repo{i}",
                item_type="repository",
                properties={"tag_count": 1, "tags": ["latest"]},
                source_resource_id="/subscriptions/test/resourceGroups/rg/providers/Microsoft.ContainerRegistry/registries/acr",
                metadata={},
                size_bytes=large_size // 10
            )
            for i in range(10)
        ]

        code = plugin.generate_replication_code(items)

        # Should have 50GB warning
        assert "VERY LARGE REGISTRY" in code or "50GB" in code.lower()

    def test_generate_replication_code_unsupported_format(self, plugin):
        """Test code generation with unsupported format."""
        items = [
            DataPlaneItem(
                name="myapp",
                item_type="repository",
                properties={},
                source_resource_id="/test",
                metadata={}
            )
        ]

        with pytest.raises(ValueError, match="not supported"):
            plugin.generate_replication_code(items, "bicep")

    def test_replicate_template_mode(self, plugin, sample_registry_resource):
        """Test replication in template mode."""
        target_resource = sample_registry_resource.copy()
        target_resource["name"] = "targetacr"

        with patch.object(plugin, 'discover') as mock_discover:
            # Mock discovery to return sample items
            mock_discover.return_value = [
                DataPlaneItem(
                    name="app1",
                    item_type="repository",
                    properties={"tags": ["v1.0"]},
                    source_resource_id=sample_registry_resource["id"],
                    metadata={},
                    size_bytes=1048576
                )
            ]

            result = plugin.replicate_with_mode(
                sample_registry_resource,
                target_resource,
                ReplicationMode.TEMPLATE
            )

            # Verify result
            assert result.success is True
            assert result.items_discovered == 1
            assert result.items_replicated == 0  # Template mode doesn't copy
            assert len(result.warnings) > 0
            assert "Template mode" in result.warnings[0]

    def test_replicate_replication_mode(self, plugin, sample_registry_resource):
        """Test replication in replication mode."""
        target_resource = sample_registry_resource.copy()
        target_resource["name"] = "targetacr"

        with patch.object(plugin, 'discover') as mock_discover:
            # Mock discovery to return sample items
            mock_discover.return_value = [
                DataPlaneItem(
                    name="app1",
                    item_type="repository",
                    properties={"tags": ["v1.0", "latest"]},
                    source_resource_id=sample_registry_resource["id"],
                    metadata={},
                    size_bytes=2097152
                )
            ]

            result = plugin.replicate_with_mode(
                sample_registry_resource,
                target_resource,
                ReplicationMode.REPLICATION
            )

            # Verify result
            assert result.success is True
            assert result.items_discovered == 1
            assert result.items_replicated == 0  # Script generated, not executed
            assert len(result.warnings) > 0
            assert "Generated commands" in result.warnings[0]

    def test_replicate_with_progress_reporter(self, sample_registry_resource):
        """Test replication with progress reporting."""
        mock_progress = Mock()
        plugin = ContainerRegistryPlugin(progress_reporter=mock_progress)

        target_resource = sample_registry_resource.copy()
        target_resource["name"] = "targetacr"

        with patch.object(plugin, 'discover') as mock_discover:
            mock_discover.return_value = [
                DataPlaneItem(
                    name="app1",
                    item_type="repository",
                    properties={"tags": ["v1.0"]},
                    source_resource_id=sample_registry_resource["id"],
                    metadata={},
                    size_bytes=1048576
                )
            ]

            result = plugin.replicate_with_mode(
                sample_registry_resource,
                target_resource,
                ReplicationMode.TEMPLATE
            )

            # Verify progress was reported
            assert mock_progress.report_completion.called

    def test_replicate_discovery_failure(self, plugin, sample_registry_resource):
        """Test replication handles discovery failures."""
        target_resource = sample_registry_resource.copy()
        target_resource["name"] = "targetacr"

        with patch.object(plugin, 'discover') as mock_discover:
            mock_discover.side_effect = Exception("Connection timeout")

            result = plugin.replicate_with_mode(
                sample_registry_resource,
                target_resource,
                ReplicationMode.TEMPLATE
            )

            # Verify error handling
            assert result.success is False
            assert result.items_discovered == 0
            assert len(result.errors) > 0
            assert "Connection timeout" in result.errors[0]

    def test_replicate_invalid_source(self, plugin, sample_registry_resource):
        """Test replication with invalid source resource."""
        target_resource = sample_registry_resource.copy()
        invalid_source = {"id": "test", "type": "Microsoft.KeyVault/vaults"}

        with pytest.raises(ValueError, match="Invalid source resource"):
            plugin.replicate_with_mode(
                invalid_source,
                target_resource,
                ReplicationMode.TEMPLATE
            )

    def test_replicate_invalid_target(self, plugin, sample_registry_resource):
        """Test replication with invalid target resource."""
        invalid_target = {"id": "test", "type": "Microsoft.KeyVault/vaults"}

        with pytest.raises(ValueError, match="Invalid target resource"):
            plugin.replicate_with_mode(
                sample_registry_resource,
                invalid_target,
                ReplicationMode.TEMPLATE
            )

    def test_estimate_operation_time_template(self, plugin):
        """Test operation time estimation for template mode."""
        items = [
            DataPlaneItem(
                name=f"repo{i}",
                item_type="repository",
                properties={},
                source_resource_id="/test",
                metadata={}
            )
            for i in range(5)
        ]

        estimate = plugin.estimate_operation_time(items, ReplicationMode.TEMPLATE)

        # Should be quick (2 seconds per repo)
        assert estimate == 10.0  # 5 repos * 2 seconds

    def test_estimate_operation_time_replication(self, plugin):
        """Test operation time estimation for replication mode."""
        # Create items with known size (10MB total)
        items = [
            DataPlaneItem(
                name="repo1",
                item_type="repository",
                properties={"tags": ["v1.0", "v2.0"]},
                source_resource_id="/test",
                metadata={},
                size_bytes=10 * 1024 * 1024  # 10MB
            )
        ]

        estimate = plugin.estimate_operation_time(items, ReplicationMode.REPLICATION)

        # Should estimate based on size + overhead
        # 10MB at 10MB/s = 1 second + (2 tags * 5 seconds) = 11 seconds
        assert estimate == pytest.approx(11.0, rel=0.1)

    def test_format_size(self, plugin):
        """Test size formatting helper method."""
        assert plugin._format_size(0) == "0 B"
        assert plugin._format_size(1024) == "1.00 KB"
        assert plugin._format_size(1048576) == "1.00 MB"
        assert plugin._format_size(1073741824) == "1.00 GB"
        assert plugin._format_size(1099511627776) == "1.00 TB"

    def test_log_size_warnings(self, plugin, caplog):
        """Test size warning logging."""
        import logging
        caplog.set_level(logging.WARNING)

        # Test 100GB warning
        plugin._log_size_warnings("testreg", 100 * 1024 * 1024 * 1024)
        assert "EXTREMELY LARGE" in caplog.text

        caplog.clear()

        # Test 50GB warning
        plugin._log_size_warnings("testreg", 50 * 1024 * 1024 * 1024)
        assert "VERY LARGE" in caplog.text

        caplog.clear()

        # Test 10GB warning (info level)
        caplog.set_level(logging.INFO)
        plugin._log_size_warnings("testreg", 10 * 1024 * 1024 * 1024)
        assert "large" in caplog.text.lower()

    def test_generate_replication_script(self, plugin):
        """Test replication script generation."""
        items = [
            DataPlaneItem(
                name="app1",
                item_type="repository",
                properties={"tags": ["v1.0", "latest"]},
                source_resource_id="/test",
                metadata={},
                size_bytes=2097152
            ),
            DataPlaneItem(
                name="app2",
                item_type="repository",
                properties={"tags": ["v2.0"]},
                source_resource_id="/test",
                metadata={},
                size_bytes=1048576
            )
        ]

        script = plugin._generate_replication_script(
            "sourceacr",
            "targetacr",
            items,
            "sourceacr.azurecr.io",
            "targetacr.azurecr.io"
        )

        # Verify script content
        assert "#!/bin/bash" in script
        assert "SOURCE_REGISTRY=" in script
        assert "TARGET_REGISTRY=" in script
        assert "az acr import" in script
        assert "app1:v1.0" in script
        assert "app1:latest" in script
        assert "app2:v2.0" in script
        assert "set -e" in script  # Error handling

    def test_supports_mode(self, plugin):
        """Test that plugin supports both modes."""
        assert plugin.supports_mode(ReplicationMode.TEMPLATE) is True
        assert plugin.supports_mode(ReplicationMode.REPLICATION) is True

    def test_supports_output_format(self, plugin):
        """Test output format support."""
        assert plugin.supports_output_format("terraform") is True
        assert plugin.supports_output_format("Terraform") is True
        assert plugin.supports_output_format("bicep") is False
        assert plugin.supports_output_format("arm") is False


class TestContainerRegistryPluginIntegration:
    """Integration tests for ACR plugin with more realistic scenarios."""

    @pytest.fixture
    def plugin(self):
        """Create plugin instance."""
        return ContainerRegistryPlugin()

    def test_full_workflow_template_mode(self, plugin):
        """Test complete workflow in template mode."""
        # This test simulates a full workflow without actual Azure calls
        resource = {
            "id": "/subscriptions/test/resourceGroups/rg/providers/Microsoft.ContainerRegistry/registries/myacr",
            "type": "Microsoft.ContainerRegistry/registries",
            "name": "myacr",
            "properties": {"loginServer": "myacr.azurecr.io"}
        }

        # 1. Check permissions
        perms = plugin.get_required_permissions(ReplicationMode.TEMPLATE)
        assert len(perms) > 0

        # 2. Discover (mocked)
        with patch.object(plugin, 'discover') as mock_discover:
            mock_discover.return_value = [
                DataPlaneItem(
                    name="webapp",
                    item_type="repository",
                    properties={"tags": ["v1.0", "v1.1", "latest"]},
                    source_resource_id=resource["id"],
                    metadata={"registry_name": "myacr"},
                    size_bytes=3145728
                )
            ]

            items = plugin.discover(resource)

        # 3. Generate code
        code = plugin.generate_replication_code(items)
        assert "# Repository: webapp" in code
        assert len(code) > 0

        # 4. Replicate
        target = resource.copy()
        target["name"] = "targetacr"

        with patch.object(plugin, 'discover') as mock_discover:
            mock_discover.return_value = items

            result = plugin.replicate_with_mode(resource, target, ReplicationMode.TEMPLATE)

        assert result.success is True
        assert result.items_discovered == 1

    def test_large_registry_workflow(self, plugin):
        """Test workflow with a large registry (many repositories)."""
        resource = {
            "id": "/subscriptions/test/resourceGroups/rg/providers/Microsoft.ContainerRegistry/registries/largacr",
            "type": "Microsoft.ContainerRegistry/registries",
            "name": "largeacr",
            "properties": {"loginServer": "largeacr.azurecr.io"}
        }

        # Simulate 100 repositories
        items = [
            DataPlaneItem(
                name=f"app-{i}",
                item_type="repository",
                properties={"tags": ["latest", f"v{i}.0"]},
                source_resource_id=resource["id"],
                metadata={},
                size_bytes=524288000  # 500MB each
            )
            for i in range(100)
        ]

        # Generate code - should handle large number of repos
        code = plugin.generate_replication_code(items)
        assert "Total Repositories: 100" in code

        # Estimate time
        estimate = plugin.estimate_operation_time(items, ReplicationMode.REPLICATION)
        assert estimate > 0  # Should have reasonable estimate

        # Check for size warnings (100 repos * 500MB = 50GB)
        assert "LARGE" in code or "large" in code.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
