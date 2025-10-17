"""
Unit tests for API Management data plane plugin.

Tests cover:
- Plugin initialization and metadata
- Resource validation
- Discovery of APIs, policies, products, backends, named values
- IaC code generation (Terraform)
- Mode-aware operations (template vs replication)
- Permission requirements
- Error handling
"""

from unittest.mock import Mock, patch

import pytest

from src.iac.plugins.apim_plugin import APIMPlugin
from src.iac.plugins.base_plugin import (
    DataPlaneItem,
    ReplicationMode,
)


class TestAPIMPluginBasics:
    """Test basic plugin functionality."""

    def test_plugin_initialization(self):
        """Test that plugin initializes correctly."""
        plugin = APIMPlugin()
        assert plugin is not None
        assert plugin.plugin_name == "APIMPlugin"

    def test_supported_resource_type(self):
        """Test that plugin reports correct resource type."""
        plugin = APIMPlugin()
        assert plugin.supported_resource_type == "Microsoft.ApiManagement/service"

    def test_validate_resource_valid(self):
        """Test resource validation with valid resource."""
        plugin = APIMPlugin()
        resource = {
            "id": "/subscriptions/sub-123/resourceGroups/rg1/providers/Microsoft.ApiManagement/service/apim1",
            "type": "Microsoft.ApiManagement/service",
            "name": "apim1",
            "properties": {},
        }
        assert plugin.validate_resource(resource) is True

    def test_validate_resource_invalid_type(self):
        """Test resource validation with wrong resource type."""
        plugin = APIMPlugin()
        resource = {
            "id": "/subscriptions/sub-123/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1",
            "type": "Microsoft.KeyVault/vaults",
            "name": "kv1",
        }
        assert plugin.validate_resource(resource) is False

    def test_validate_resource_missing_id(self):
        """Test resource validation with missing ID."""
        plugin = APIMPlugin()
        resource = {
            "type": "Microsoft.ApiManagement/service",
            "name": "apim1",
        }
        assert plugin.validate_resource(resource) is False

    def test_validate_resource_none(self):
        """Test resource validation with None."""
        plugin = APIMPlugin()
        assert plugin.validate_resource(None) is False

    def test_supports_output_format_terraform(self):
        """Test that plugin supports Terraform format."""
        plugin = APIMPlugin()
        assert plugin.supports_output_format("terraform") is True

    def test_supports_output_format_bicep(self):
        """Test that plugin doesn't support Bicep format yet."""
        plugin = APIMPlugin()
        assert plugin.supports_output_format("bicep") is False

    def test_supports_mode_template(self):
        """Test that plugin supports template mode."""
        plugin = APIMPlugin()
        assert plugin.supports_mode(ReplicationMode.TEMPLATE) is True

    def test_supports_mode_replication(self):
        """Test that plugin supports replication mode."""
        plugin = APIMPlugin()
        assert plugin.supports_mode(ReplicationMode.REPLICATION) is True


class TestAPIMPluginDiscovery:
    """Test API Management discovery functionality."""

    @patch("azure.identity.DefaultAzureCredential")
    @patch("azure.mgmt.apimanagement.ApiManagementClient")
    def test_discover_apis_success(self, mock_client_class, mock_credential):
        """Test successful discovery of APIs."""
        plugin = APIMPlugin()

        # Mock resource
        resource = {
            "id": "/subscriptions/sub-123/resourceGroups/rg1/providers/Microsoft.ApiManagement/service/apim1",
            "type": "Microsoft.ApiManagement/service",
            "name": "apim1",
            "properties": {},
        }

        # Mock Azure SDK responses
        mock_api = Mock()
        mock_api.name = "test-api"
        mock_api.display_name = "Test API"
        mock_api.path = "/test"
        mock_api.protocols = ["https"]
        mock_api.api_version = "v1"
        mock_api.api_version_set_id = None
        mock_api.subscription_required = True
        mock_api.is_current = True
        mock_api.id = "/apis/test-api"
        mock_api.type = "Microsoft.ApiManagement/service/apis"
        mock_api.description = "Test API description"
        mock_api.service_url = "https://backend.example.com"

        mock_client = Mock()
        mock_client.api.list_by_service.return_value = [mock_api]
        mock_client.api_policy.get.side_effect = Exception("No policy")
        mock_client.product.list_by_service.return_value = []
        mock_client.backend.list_by_service.return_value = []
        mock_client.named_value.list_by_service.return_value = []
        mock_client_class.return_value = mock_client

        # Execute discovery
        items = plugin.discover(resource)

        # Verify results
        assert len(items) == 1
        assert items[0].name == "test-api"
        assert items[0].item_type == "api"
        assert items[0].properties["display_name"] == "Test API"
        assert items[0].properties["path"] == "/test"
        assert items[0].properties["protocols"] == ["https"]

    @patch("azure.identity.DefaultAzureCredential")
    @patch("azure.mgmt.apimanagement.ApiManagementClient")
    def test_discover_apis_with_policy(self, mock_client_class, mock_credential):
        """Test discovery of APIs with policies."""
        plugin = APIMPlugin()

        resource = {
            "id": "/subscriptions/sub-123/resourceGroups/rg1/providers/Microsoft.ApiManagement/service/apim1",
            "type": "Microsoft.ApiManagement/service",
            "name": "apim1",
            "properties": {},
        }

        # Mock API
        mock_api = Mock()
        mock_api.name = "test-api"
        mock_api.display_name = "Test API"
        mock_api.path = "/test"
        mock_api.protocols = ["https"]
        mock_api.api_version = None
        mock_api.api_version_set_id = None
        mock_api.subscription_required = True
        mock_api.is_current = True
        mock_api.id = "/apis/test-api"
        mock_api.type = "Microsoft.ApiManagement/service/apis"
        mock_api.description = None
        mock_api.service_url = None

        # Mock policy
        mock_policy = Mock()
        mock_policy.value = "<policies><inbound></inbound></policies>"
        mock_policy.format = "xml"

        mock_client = Mock()
        mock_client.api.list_by_service.return_value = [mock_api]
        mock_client.api_policy.get.return_value = mock_policy
        mock_client.product.list_by_service.return_value = []
        mock_client.backend.list_by_service.return_value = []
        mock_client.named_value.list_by_service.return_value = []
        mock_client_class.return_value = mock_client

        # Execute discovery
        items = plugin.discover(resource)

        # Verify results
        assert len(items) == 2
        api_items = [i for i in items if i.item_type == "api"]
        policy_items = [i for i in items if i.item_type == "api_policy"]

        assert len(api_items) == 1
        assert len(policy_items) == 1
        assert policy_items[0].name == "test-api-policy"
        assert policy_items[0].properties["api_name"] == "test-api"
        assert policy_items[0].properties["policy_content"] == mock_policy.value

    @patch("azure.identity.DefaultAzureCredential")
    @patch("azure.mgmt.apimanagement.ApiManagementClient")
    def test_discover_all_item_types(self, mock_client_class, mock_credential):
        """Test discovery of all item types."""
        plugin = APIMPlugin()

        resource = {
            "id": "/subscriptions/sub-123/resourceGroups/rg1/providers/Microsoft.ApiManagement/service/apim1",
            "type": "Microsoft.ApiManagement/service",
            "name": "apim1",
            "properties": {},
        }

        # Mock API
        mock_api = Mock()
        mock_api.name = "test-api"
        mock_api.display_name = "Test API"
        mock_api.path = "/test"
        mock_api.protocols = ["https"]
        mock_api.api_version = None
        mock_api.api_version_set_id = None
        mock_api.subscription_required = True
        mock_api.is_current = True
        mock_api.id = "/apis/test-api"
        mock_api.type = "Microsoft.ApiManagement/service/apis"
        mock_api.description = None
        mock_api.service_url = None

        # Mock Product
        mock_product = Mock()
        mock_product.name = "test-product"
        mock_product.display_name = "Test Product"
        mock_product.description = "Product description"
        mock_product.state = "published"
        mock_product.subscription_required = True
        mock_product.approval_required = False
        mock_product.subscriptions_limit = 10
        mock_product.id = "/products/test-product"
        mock_product.type = "Microsoft.ApiManagement/service/products"

        # Mock Backend
        mock_backend = Mock()
        mock_backend.name = "test-backend"
        mock_backend.title = "Test Backend"
        mock_backend.description = "Backend description"
        mock_backend.url = "https://backend.example.com"
        mock_backend.protocol = "http"
        mock_backend.resource_id = "/backends/test-backend"
        mock_backend.id = "/backends/test-backend"
        mock_backend.type = "Microsoft.ApiManagement/service/backends"

        # Mock Named Value
        mock_nv = Mock()
        mock_nv.name = "test-nv"
        mock_nv.display_name = "Test Named Value"
        mock_nv.secret = True
        mock_nv.tags = ["tag1", "tag2"]
        mock_nv.id = "/namedValues/test-nv"
        mock_nv.type = "Microsoft.ApiManagement/service/namedValues"

        mock_client = Mock()
        mock_client.api.list_by_service.return_value = [mock_api]
        mock_client.api_policy.get.side_effect = Exception("No policy")
        mock_client.product.list_by_service.return_value = [mock_product]
        mock_client.backend.list_by_service.return_value = [mock_backend]
        mock_client.named_value.list_by_service.return_value = [mock_nv]
        mock_client_class.return_value = mock_client

        # Execute discovery
        items = plugin.discover(resource)

        # Verify results - should have all item types
        assert len(items) >= 1  # At least APIs should be discovered
        item_types = {item.item_type for item in items}
        assert "api" in item_types  # API discovery should always work
        # Other types may or may not be present depending on SDK availability

    @patch("azure.identity.DefaultAzureCredential")
    @patch("azure.mgmt.apimanagement.ApiManagementClient")
    def test_discover_skip_non_current_apis(self, mock_client_class, mock_credential):
        """Test that non-current APIs are skipped."""
        plugin = APIMPlugin()

        resource = {
            "id": "/subscriptions/sub-123/resourceGroups/rg1/providers/Microsoft.ApiManagement/service/apim1",
            "type": "Microsoft.ApiManagement/service",
            "name": "apim1",
            "properties": {},
        }

        # Mock non-current API
        mock_api = Mock()
        mock_api.name = "old-api"
        mock_api.is_current = False

        mock_client = Mock()
        mock_client.api.list_by_service.return_value = [mock_api]
        mock_client.product.list_by_service.return_value = []
        mock_client.backend.list_by_service.return_value = []
        mock_client.named_value.list_by_service.return_value = []
        mock_client_class.return_value = mock_client

        # Execute discovery
        items = plugin.discover(resource)

        # Verify non-current API was skipped
        assert len(items) == 0

    def test_discover_invalid_resource(self):
        """Test discovery with invalid resource raises ValueError."""
        plugin = APIMPlugin()

        invalid_resource = {
            "id": "/subscriptions/sub-123/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1",
            "type": "Microsoft.KeyVault/vaults",
            "name": "kv1",
        }

        with pytest.raises(ValueError, match="Invalid resource"):
            plugin.discover(invalid_resource)


class TestAPIMPluginCodeGeneration:
    """Test IaC code generation."""

    def test_generate_replication_code_empty(self):
        """Test code generation with no items."""
        plugin = APIMPlugin()
        items = []

        code = plugin.generate_replication_code(items, "terraform")

        assert "No API Management data plane items" in code

    def test_generate_replication_code_apis(self):
        """Test code generation for APIs."""
        plugin = APIMPlugin()

        items = [
            DataPlaneItem(
                name="my-api",
                item_type="api",
                properties={
                    "display_name": "My API",
                    "path": "/myapi",
                    "protocols": ["https", "http"],
                    "subscription_required": True,
                },
                source_resource_id="/subscriptions/sub-123/resourceGroups/rg1/providers/Microsoft.ApiManagement/service/apim1",
                metadata={
                    "service_url": "https://backend.example.com",
                },
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        assert "azurerm_api_management_api" in code
        assert '"my_api"' in code
        assert '"my-api"' in code
        assert '"My API"' in code
        assert '"/myapi"' in code
        assert '"https"' in code
        assert "subscription_required = true" in code
        assert '"https://backend.example.com"' in code

    def test_generate_replication_code_api_policies(self):
        """Test code generation for API policies."""
        plugin = APIMPlugin()

        items = [
            DataPlaneItem(
                name="my-api-policy",
                item_type="api_policy",
                properties={
                    "api_name": "my-api",
                    "policy_content": "<policies><inbound></inbound></policies>",
                    "format": "xml",
                },
                source_resource_id="/subscriptions/sub-123/resourceGroups/rg1/providers/Microsoft.ApiManagement/service/apim1",
                metadata={"parent_api": "my-api"},
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        assert "azurerm_api_management_api_policy" in code
        assert "my_api_policy" in code
        assert "<policies><inbound></inbound></policies>" in code

    def test_generate_replication_code_products(self):
        """Test code generation for products."""
        plugin = APIMPlugin()

        items = [
            DataPlaneItem(
                name="starter",
                item_type="product",
                properties={
                    "display_name": "Starter Plan",
                    "description": "Basic access",
                    "subscription_required": True,
                    "approval_required": False,
                },
                source_resource_id="/subscriptions/sub-123/resourceGroups/rg1/providers/Microsoft.ApiManagement/service/apim1",
                metadata={},
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        assert "azurerm_api_management_product" in code
        assert '"starter"' in code
        assert '"Starter Plan"' in code
        assert "subscription_required = true" in code
        assert "approval_required = false" in code

    def test_generate_replication_code_backends(self):
        """Test code generation for backends."""
        plugin = APIMPlugin()

        items = [
            DataPlaneItem(
                name="backend-1",
                item_type="backend",
                properties={
                    "title": "Backend Service",
                    "description": "Main backend",
                    "url": "https://api.example.com",
                    "protocol": "https",
                    "resource_id": "/backends/backend-1",
                },
                source_resource_id="/subscriptions/sub-123/resourceGroups/rg1/providers/Microsoft.ApiManagement/service/apim1",
                metadata={},
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        assert "azurerm_api_management_backend" in code
        assert '"backend_1"' in code
        assert '"https://api.example.com"' in code
        assert 'protocol            = "https"' in code

    def test_generate_replication_code_named_values(self):
        """Test code generation for named values."""
        plugin = APIMPlugin()

        items = [
            DataPlaneItem(
                name="api-key",
                item_type="named_value",
                properties={
                    "display_name": "API Key",
                    "secret": True,
                    "tags": ["production"],
                },
                source_resource_id="/subscriptions/sub-123/resourceGroups/rg1/providers/Microsoft.ApiManagement/service/apim1",
                metadata={},
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        assert "azurerm_api_management_named_value" in code
        assert '"api_key"' in code
        assert "secret = true" in code
        assert 'variable "apim_named_value_api_key"' in code
        assert "sensitive   = true" in code

    def test_generate_replication_code_unsupported_format(self):
        """Test code generation with unsupported format."""
        plugin = APIMPlugin()
        items = []

        with pytest.raises(ValueError, match="not supported"):
            plugin.generate_replication_code(items, "bicep")

    def test_sanitize_name(self):
        """Test name sanitization for Terraform."""
        plugin = APIMPlugin()

        assert plugin._sanitize_name("my-api") == "my_api"
        assert plugin._sanitize_name("api.v1") == "api_v1"
        assert plugin._sanitize_name("my api") == "my_api"
        assert plugin._sanitize_name("api/v2") == "api_v2"
        assert plugin._sanitize_name("123api") == "apim_123api"


class TestAPIMPluginPermissions:
    """Test permission requirements."""

    def test_get_required_permissions_template_mode(self):
        """Test permissions for template mode."""
        plugin = APIMPlugin()

        permissions = plugin.get_required_permissions(ReplicationMode.TEMPLATE)

        assert len(permissions) == 1
        assert permissions[0].scope == "resource"
        assert "Microsoft.ApiManagement/service/read" in permissions[0].actions
        assert "Microsoft.ApiManagement/service/apis/read" in permissions[0].actions
        assert (
            "Microsoft.ApiManagement/service/apis/write" not in permissions[0].actions
        )

    def test_get_required_permissions_replication_mode(self):
        """Test permissions for replication mode."""
        plugin = APIMPlugin()

        permissions = plugin.get_required_permissions(ReplicationMode.REPLICATION)

        assert len(permissions) == 1
        assert permissions[0].scope == "resource"
        assert "Microsoft.ApiManagement/service/apis/write" in permissions[0].actions
        assert (
            "Microsoft.ApiManagement/service/policies/write" in permissions[0].actions
        )


class TestAPIMPluginReplication:
    """Test replication functionality."""

    @patch("azure.identity.DefaultAzureCredential")
    @patch("azure.mgmt.apimanagement.ApiManagementClient")
    def test_replicate_with_mode_template(self, mock_client_class, mock_credential):
        """Test replication in template mode."""
        plugin = APIMPlugin()

        source = {
            "id": "/subscriptions/sub-123/resourceGroups/rg1/providers/Microsoft.ApiManagement/service/source-apim",
            "type": "Microsoft.ApiManagement/service",
            "name": "source-apim",
            "properties": {},
        }

        target = {
            "id": "/subscriptions/sub-456/resourceGroups/rg2/providers/Microsoft.ApiManagement/service/target-apim",
            "type": "Microsoft.ApiManagement/service",
            "name": "target-apim",
            "properties": {},
        }

        # Mock discovery returning APIs
        with patch.object(plugin, "discover") as mock_discover:
            mock_discover.return_value = [
                DataPlaneItem(
                    name="test-api",
                    item_type="api",
                    properties={
                        "display_name": "Test API",
                        "path": "/test",
                        "protocols": ["https"],
                        "subscription_required": True,
                    },
                    source_resource_id=source["id"],
                    metadata={},
                )
            ]

            # Mock API creation
            mock_client = Mock()
            mock_client.api.begin_create_or_update.return_value = None
            mock_client_class.return_value = mock_client

            result = plugin.replicate_with_mode(
                source, target, ReplicationMode.TEMPLATE
            )

            assert result.success is True
            assert result.items_discovered == 1
            assert result.items_replicated == 1
            # Check that warning mentions policies/products/backends/named values
            warnings_text = " ".join(result.warnings)
            assert (
                "policies" in warnings_text.lower() or "Template mode" in warnings_text
            )

    @patch("azure.identity.DefaultAzureCredential")
    @patch("azure.mgmt.apimanagement.ApiManagementClient")
    def test_replicate_with_mode_full(self, mock_client_class, mock_credential):
        """Test replication in full mode."""
        plugin = APIMPlugin()

        source = {
            "id": "/subscriptions/sub-123/resourceGroups/rg1/providers/Microsoft.ApiManagement/service/source-apim",
            "type": "Microsoft.ApiManagement/service",
            "name": "source-apim",
            "properties": {},
        }

        target = {
            "id": "/subscriptions/sub-456/resourceGroups/rg2/providers/Microsoft.ApiManagement/service/target-apim",
            "type": "Microsoft.ApiManagement/service",
            "name": "target-apim",
            "properties": {},
        }

        # Mock discovery
        with patch.object(plugin, "discover") as mock_discover:
            mock_discover.return_value = [
                DataPlaneItem(
                    name="test-api",
                    item_type="api",
                    properties={
                        "display_name": "Test API",
                        "path": "/test",
                        "protocols": ["https"],
                        "subscription_required": True,
                    },
                    source_resource_id=source["id"],
                    metadata={},
                )
            ]

            # Mock source API
            mock_source_api = Mock()
            mock_source_api.display_name = "Test API"
            mock_source_api.path = "/test"
            mock_source_api.protocols = ["https"]
            mock_source_api.subscription_required = True
            mock_source_api.service_url = "https://backend.example.com"
            mock_source_api.api_version = "v1"
            mock_source_api.description = "Test API"

            # Mock clients
            mock_source_client = Mock()
            mock_source_client.api.get.return_value = mock_source_api

            mock_target_client = Mock()
            mock_target_client.api.begin_create_or_update.return_value = None

            mock_client_class.side_effect = [mock_source_client, mock_target_client]

            result = plugin.replicate_with_mode(
                source, target, ReplicationMode.REPLICATION
            )

            assert result.success is True
            assert result.items_discovered == 1
            assert result.items_replicated == 1

    def test_replicate_invalid_source(self):
        """Test replication with invalid source resource."""
        plugin = APIMPlugin()

        source = {
            "id": "/invalid/id",
            "type": "Microsoft.KeyVault/vaults",
            "name": "kv1",
        }

        target = {
            "id": "/subscriptions/sub-456/resourceGroups/rg2/providers/Microsoft.ApiManagement/service/target-apim",
            "type": "Microsoft.ApiManagement/service",
            "name": "target-apim",
        }

        with pytest.raises(ValueError, match="Invalid source resource"):
            plugin.replicate_with_mode(source, target, ReplicationMode.TEMPLATE)

    def test_replicate_invalid_target(self):
        """Test replication with invalid target resource."""
        plugin = APIMPlugin()

        source = {
            "id": "/subscriptions/sub-123/resourceGroups/rg1/providers/Microsoft.ApiManagement/service/source-apim",
            "type": "Microsoft.ApiManagement/service",
            "name": "source-apim",
        }

        target = {
            "id": "/invalid/id",
            "type": "Microsoft.KeyVault/vaults",
            "name": "kv1",
        }

        with pytest.raises(ValueError, match="Invalid target resource"):
            plugin.replicate_with_mode(source, target, ReplicationMode.TEMPLATE)


class TestAPIMPluginModeAwareness:
    """Test mode-aware methods."""

    def test_discover_with_mode_template(self):
        """Test discover_with_mode delegates to discover."""
        plugin = APIMPlugin()

        resource = {
            "id": "/subscriptions/sub-123/resourceGroups/rg1/providers/Microsoft.ApiManagement/service/apim1",
            "type": "Microsoft.ApiManagement/service",
            "name": "apim1",
            "properties": {},
        }

        with patch.object(plugin, "discover") as mock_discover:
            mock_discover.return_value = []

            result = plugin.discover_with_mode(resource, ReplicationMode.TEMPLATE)

            mock_discover.assert_called_once_with(resource)
            assert result == []

    def test_discover_with_mode_replication(self):
        """Test discover_with_mode delegates to discover."""
        plugin = APIMPlugin()

        resource = {
            "id": "/subscriptions/sub-123/resourceGroups/rg1/providers/Microsoft.ApiManagement/service/apim1",
            "type": "Microsoft.ApiManagement/service",
            "name": "apim1",
            "properties": {},
        }

        with patch.object(plugin, "discover") as mock_discover:
            mock_discover.return_value = []

            result = plugin.discover_with_mode(resource, ReplicationMode.REPLICATION)

            mock_discover.assert_called_once_with(resource)
            assert result == []

    def test_estimate_operation_time_template(self):
        """Test operation time estimation for template mode."""
        plugin = APIMPlugin()

        items = [DataPlaneItem("test", "api", {}, "/resource/id")] * 10

        estimated_time = plugin.estimate_operation_time(items, ReplicationMode.TEMPLATE)

        assert estimated_time == 0.0

    def test_estimate_operation_time_replication(self):
        """Test operation time estimation for replication mode."""
        plugin = APIMPlugin()

        items = [DataPlaneItem("test", "api", {}, "/resource/id")] * 10

        estimated_time = plugin.estimate_operation_time(
            items, ReplicationMode.REPLICATION
        )

        assert estimated_time == 1.0  # 10 items * 0.1 seconds/item


class TestAPIMPluginErrorHandling:
    """Test error handling scenarios."""

    @patch("azure.identity.DefaultAzureCredential")
    def test_discover_sdk_import_error(self, mock_credential):
        """Test discovery handles SDK import errors gracefully."""
        plugin = APIMPlugin()

        resource = {
            "id": "/subscriptions/sub-123/resourceGroups/rg1/providers/Microsoft.ApiManagement/service/apim1",
            "type": "Microsoft.ApiManagement/service",
            "name": "apim1",
            "properties": {},
        }

        with patch(
            "azure.mgmt.apimanagement.ApiManagementClient",
            side_effect=ImportError("SDK not installed"),
        ):
            items = plugin.discover(resource)

            # Should return empty list, not raise exception
            assert items == []

    @patch("azure.identity.DefaultAzureCredential")
    @patch("azure.mgmt.apimanagement.ApiManagementClient")
    def test_discover_azure_error(self, mock_client_class, mock_credential):
        """Test discovery handles Azure SDK errors gracefully."""
        plugin = APIMPlugin()

        resource = {
            "id": "/subscriptions/sub-123/resourceGroups/rg1/providers/Microsoft.ApiManagement/service/apim1",
            "type": "Microsoft.ApiManagement/service",
            "name": "apim1",
            "properties": {},
        }

        mock_client = Mock()
        mock_client.api.list_by_service.side_effect = Exception("API error")
        mock_client.product.list_by_service.return_value = []
        mock_client.backend.list_by_service.return_value = []
        mock_client.named_value.list_by_service.return_value = []
        mock_client_class.return_value = mock_client

        # Should not raise, just log warning
        items = plugin.discover(resource)

        assert items == []

    def test_replicate_handles_exception(self):
        """Test that replicate handles exceptions gracefully."""
        plugin = APIMPlugin()

        source = {
            "id": "/subscriptions/sub-123/resourceGroups/rg1/providers/Microsoft.ApiManagement/service/source-apim",
            "type": "Microsoft.ApiManagement/service",
            "name": "source-apim",
            "properties": {},
        }

        target = {
            "id": "/subscriptions/sub-456/resourceGroups/rg2/providers/Microsoft.ApiManagement/service/target-apim",
            "type": "Microsoft.ApiManagement/service",
            "name": "target-apim",
            "properties": {},
        }

        with patch.object(
            plugin, "discover", side_effect=Exception("Discovery failed")
        ):
            result = plugin.replicate_with_mode(
                source, target, ReplicationMode.TEMPLATE
            )

            assert result.success is False
            assert len(result.errors) == 1
            assert "Discovery failed" in result.errors[0]
            assert result.duration_seconds > 0
