"""
Unit tests for App Service data plane plugin.

Tests cover:
- App Service resource validation
- Discovery functionality with mocked Azure SDK
- Terraform code generation
- Replication functionality
- Error handling and edge cases
"""

from unittest.mock import MagicMock, patch

import pytest

from src.iac.plugins.appservice_plugin import AppServicePlugin
from src.iac.plugins.base_plugin import DataPlaneItem


class TestAppServicePlugin:
    """Test cases for AppServicePlugin."""

    def test_plugin_instantiation(self):
        """Test that AppServicePlugin can be instantiated."""
        plugin = AppServicePlugin()
        assert plugin is not None
        assert plugin.plugin_name == "AppServicePlugin"

    def test_supported_resource_type(self):
        """Test that plugin supports correct resource type."""
        plugin = AppServicePlugin()
        assert plugin.supported_resource_type == "Microsoft.Web/sites"

    def test_supports_terraform_format(self):
        """Test that plugin supports Terraform output format."""
        plugin = AppServicePlugin()
        assert plugin.supports_output_format("terraform") is True
        assert plugin.supports_output_format("TERRAFORM") is True

    def test_does_not_support_other_formats(self):
        """Test that plugin doesn't support other formats yet."""
        plugin = AppServicePlugin()
        assert plugin.supports_output_format("bicep") is False
        assert plugin.supports_output_format("arm") is False


class TestAppServiceValidation:
    """Test resource validation for App Service plugin."""

    def test_validate_valid_appservice_resource(self):
        """Test validation succeeds for valid App Service resource."""
        plugin = AppServicePlugin()
        resource = {
            "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/my-rg/providers/Microsoft.Web/sites/my-app",
            "type": "Microsoft.Web/sites",
            "name": "my-app",
            "properties": {},
        }

        assert plugin.validate_resource(resource) is True

    def test_validate_wrong_resource_type(self):
        """Test validation fails for wrong resource type."""
        plugin = AppServicePlugin()
        resource = {
            "id": "/subscriptions/123/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/mystorage",
            "type": "Microsoft.Storage/storageAccounts",  # Wrong type
            "name": "mystorage",
        }

        assert plugin.validate_resource(resource) is False

    def test_validate_missing_id(self):
        """Test validation fails for missing resource ID."""
        plugin = AppServicePlugin()
        resource = {
            "type": "Microsoft.Web/sites",
            "name": "my-app",
            # Missing 'id'
        }

        assert plugin.validate_resource(resource) is False

    def test_validate_none_resource(self):
        """Test validation fails for None resource."""
        plugin = AppServicePlugin()
        assert plugin.validate_resource(None) is False

    def test_validate_empty_resource(self):
        """Test validation fails for empty resource."""
        plugin = AppServicePlugin()
        assert plugin.validate_resource({}) is False


class TestAppServiceDiscovery:
    """Test discovery functionality for App Service plugin."""

    def test_discover_with_invalid_resource_raises_error(self):
        """Test discover raises ValueError for invalid resource."""
        plugin = AppServicePlugin()
        invalid_resource = {
            "type": "Microsoft.Storage/storageAccounts",  # Wrong type
            "name": "storage",
        }

        with pytest.raises(ValueError, match="Invalid resource"):
            plugin.discover(invalid_resource)

    def test_discover_with_invalid_resource_id_format(self):
        """Test discover handles invalid resource ID format."""
        plugin = AppServicePlugin()
        resource = {
            "id": "/invalid/format",
            "type": "Microsoft.Web/sites",
            "name": "my-app",
        }

        # Should return empty list, not crash
        items = plugin.discover(resource)
        assert isinstance(items, list)
        assert len(items) == 0

    @patch("azure.mgmt.web.WebSiteManagementClient")
    @patch("azure.identity.DefaultAzureCredential")
    def test_discover_app_settings(self, mock_credential, mock_web_client_class):
        """Test discovering application settings."""
        plugin = AppServicePlugin()
        resource = {
            "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/my-rg/providers/Microsoft.Web/sites/my-app",
            "type": "Microsoft.Web/sites",
            "name": "my-app",
        }

        # Mock the web client
        mock_web_client = MagicMock()
        mock_web_client_class.return_value = mock_web_client

        # Mock app settings response
        mock_settings_response = MagicMock()
        mock_settings_response.properties = {
            "DB_HOST": "localhost",
            "DB_PORT": "5432",
            "API_KEY": "secret123",  # pragma: allowlist secret
        }
        mock_web_client.web_apps.list_application_settings.return_value = (
            mock_settings_response
        )

        # Mock connection strings response (empty)
        mock_conn_strings = MagicMock()
        mock_conn_strings.properties = {}
        mock_web_client.web_apps.list_connection_strings.return_value = (
            mock_conn_strings
        )

        # Mock site config
        mock_config = MagicMock()
        mock_config.always_on = True
        mock_web_client.web_apps.get_configuration.return_value = mock_config

        # Mock slots (empty)
        mock_web_client.web_apps.list_slots.return_value = []

        items = plugin.discover(resource)

        # Should have 3 app settings + 1 config
        assert len(items) == 4
        app_setting_items = [item for item in items if item.item_type == "app_setting"]
        assert len(app_setting_items) == 3

        # Check sensitive detection
        api_key_item = next((item for item in items if item.name == "API_KEY"), None)
        assert api_key_item is not None
        assert api_key_item.metadata.get("sensitive") is True

    @patch("azure.mgmt.web.WebSiteManagementClient")
    @patch("azure.identity.DefaultAzureCredential")
    def test_discover_connection_strings(self, mock_credential, mock_web_client_class):
        """Test discovering connection strings."""
        plugin = AppServicePlugin()
        resource = {
            "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/my-rg/providers/Microsoft.Web/sites/my-app",
            "type": "Microsoft.Web/sites",
            "name": "my-app",
        }

        # Mock the web client
        mock_web_client = MagicMock()
        mock_web_client_class.return_value = mock_web_client

        # Mock app settings (empty)
        mock_settings_response = MagicMock()
        mock_settings_response.properties = {}
        mock_web_client.web_apps.list_application_settings.return_value = (
            mock_settings_response
        )

        # Mock connection strings response
        mock_conn_string = MagicMock()
        mock_conn_string.value = "Server=myserver;Database=mydb"
        mock_conn_string.type = "SQLAzure"

        mock_conn_strings = MagicMock()
        mock_conn_strings.properties = {"DefaultConnection": mock_conn_string}
        mock_web_client.web_apps.list_connection_strings.return_value = (
            mock_conn_strings
        )

        # Mock site config
        mock_config = MagicMock()
        mock_web_client.web_apps.get_configuration.return_value = mock_config

        # Mock slots
        mock_web_client.web_apps.list_slots.return_value = []

        items = plugin.discover(resource)

        # Should have 1 connection string + 1 config
        conn_string_items = [
            item for item in items if item.item_type == "connection_string"
        ]
        assert len(conn_string_items) == 1
        assert conn_string_items[0].name == "DefaultConnection"
        assert conn_string_items[0].properties["type"] == "SQLAzure"
        assert conn_string_items[0].metadata["sensitive"] is True

    @patch("azure.mgmt.web.WebSiteManagementClient")
    @patch("azure.identity.DefaultAzureCredential")
    def test_discover_deployment_slots(self, mock_credential, mock_web_client_class):
        """Test discovering deployment slots."""
        plugin = AppServicePlugin()
        resource = {
            "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/my-rg/providers/Microsoft.Web/sites/my-app",
            "type": "Microsoft.Web/sites",
            "name": "my-app",
        }

        # Mock the web client
        mock_web_client = MagicMock()
        mock_web_client_class.return_value = mock_web_client

        # Mock app settings (empty)
        mock_settings_response = MagicMock()
        mock_settings_response.properties = {}
        mock_web_client.web_apps.list_application_settings.return_value = (
            mock_settings_response
        )

        # Mock connection strings (empty)
        mock_conn_strings = MagicMock()
        mock_conn_strings.properties = {}
        mock_web_client.web_apps.list_connection_strings.return_value = (
            mock_conn_strings
        )

        # Mock site config
        mock_config = MagicMock()
        mock_web_client.web_apps.get_configuration.return_value = mock_config

        # Mock deployment slots
        mock_slot1 = MagicMock()
        mock_slot1.name = "my-app/staging"
        mock_slot1.location = "eastus"
        mock_slot1.state = "Running"
        mock_slot1.enabled = True

        mock_slot2 = MagicMock()
        mock_slot2.name = "my-app"  # Production slot - should be skipped
        mock_slot2.location = "eastus"

        mock_web_client.web_apps.list_slots.return_value = [mock_slot1, mock_slot2]

        items = plugin.discover(resource)

        # Should have 1 deployment slot (excluding production) + 1 config
        slot_items = [item for item in items if item.item_type == "deployment_slot"]
        assert len(slot_items) == 1
        assert slot_items[0].name == "staging"
        assert slot_items[0].properties["location"] == "eastus"

    @patch("azure.mgmt.web.WebSiteManagementClient")
    @patch("azure.identity.DefaultAzureCredential")
    def test_discover_skips_system_settings(
        self, mock_credential, mock_web_client_class
    ):
        """Test that system-managed settings are skipped."""
        plugin = AppServicePlugin()
        resource = {
            "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/my-rg/providers/Microsoft.Web/sites/my-app",
            "type": "Microsoft.Web/sites",
            "name": "my-app",
        }

        # Mock the web client
        mock_web_client = MagicMock()
        mock_web_client_class.return_value = mock_web_client

        # Mock app settings with system settings
        mock_settings_response = MagicMock()
        mock_settings_response.properties = {
            "WEBSITE_NODE_DEFAULT_VERSION": "14.0.0",  # System setting - should skip
            "APPSETTING_SOMETHING": "value",  # System setting - should skip
            "MY_CUSTOM_SETTING": "value",  # User setting - should include
        }
        mock_web_client.web_apps.list_application_settings.return_value = (
            mock_settings_response
        )

        # Mock empty connection strings
        mock_conn_strings = MagicMock()
        mock_conn_strings.properties = {}
        mock_web_client.web_apps.list_connection_strings.return_value = (
            mock_conn_strings
        )

        # Mock site config
        mock_config = MagicMock()
        mock_web_client.web_apps.get_configuration.return_value = mock_config

        # Mock slots
        mock_web_client.web_apps.list_slots.return_value = []

        items = plugin.discover(resource)

        # Should only have 1 app setting (system settings skipped) + 1 config
        app_setting_items = [item for item in items if item.item_type == "app_setting"]
        assert len(app_setting_items) == 1
        assert app_setting_items[0].name == "MY_CUSTOM_SETTING"

    @patch("azure.mgmt.web.WebSiteManagementClient")
    @patch("azure.identity.DefaultAzureCredential")
    def test_discover_handles_permission_error(
        self, mock_credential, mock_web_client_class
    ):
        """Test discover handles permission errors gracefully."""
        plugin = AppServicePlugin()
        resource = {
            "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/my-rg/providers/Microsoft.Web/sites/my-app",
            "type": "Microsoft.Web/sites",
            "name": "my-app",
        }

        # Mock the web client
        mock_web_client = MagicMock()
        mock_web_client_class.return_value = mock_web_client

        # Mock permission error
        from azure.core.exceptions import HttpResponseError

        mock_web_client.web_apps.list_application_settings.side_effect = (
            HttpResponseError(message="Forbidden")
        )

        # Should not crash, just return empty list
        items = plugin.discover(resource)
        assert isinstance(items, list)


class TestAppServiceCodeGeneration:
    """Test IaC code generation for App Service plugin."""

    def test_generate_code_for_empty_items(self):
        """Test code generation with no items."""
        plugin = AppServicePlugin()
        code = plugin.generate_replication_code([], "terraform")

        assert "No App Service data plane items" in code

    def test_generate_code_for_app_settings(self):
        """Test code generation for app settings."""
        plugin = AppServicePlugin()
        items = [
            DataPlaneItem(
                name="DB_HOST",
                item_type="app_setting",
                properties={"value": "localhost"},
                source_resource_id="/subscriptions/123/sites/app",
                metadata={"sensitive": False},
            ),
            DataPlaneItem(
                name="DB_PORT",
                item_type="app_setting",
                properties={"value": "5432"},
                source_resource_id="/subscriptions/123/sites/app",
                metadata={"sensitive": False},
            ),
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Check for app settings
        assert "Application Settings" in code
        assert "DB_HOST" in code
        assert "localhost" in code
        assert "DB_PORT" in code
        assert "5432" in code

    def test_generate_code_for_sensitive_app_settings(self):
        """Test code generation masks sensitive app settings."""
        plugin = AppServicePlugin()
        items = [
            DataPlaneItem(
                name="API_KEY",
                item_type="app_setting",
                properties={"value": "secret123"},
                source_resource_id="/subscriptions/123/sites/app",
                metadata={"sensitive": True},
            ),
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Should use variable, not include actual value
        assert "var.app_setting_api_key" in code
        assert "secret123" not in code

        # Should have variable declaration
        assert 'variable "app_setting_api_key"' in code
        assert "sensitive   = true" in code

    def test_generate_code_for_connection_strings(self):
        """Test code generation for connection strings."""
        plugin = AppServicePlugin()
        items = [
            DataPlaneItem(
                name="DefaultConnection",
                item_type="connection_string",
                properties={
                    "value": "Server=myserver;Database=mydb",
                    "type": "SQLAzure",
                },
                source_resource_id="/subscriptions/123/sites/app",
                metadata={"sensitive": True},
            ),
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Check for connection string
        assert "Connection Strings" in code
        assert "DefaultConnection" in code
        assert "SQLAzure" in code
        assert "var.connection_string_defaultconnection" in code

        # Should not include actual connection string value
        assert "Server=myserver" not in code

        # Should have variable declaration
        assert 'variable "connection_string_defaultconnection"' in code

    def test_generate_code_for_site_configuration(self):
        """Test code generation for site configuration."""
        plugin = AppServicePlugin()
        items = [
            DataPlaneItem(
                name="site_config",
                item_type="configuration",
                properties={
                    "always_on": True,
                    "http20_enabled": True,
                    "min_tls_version": "1.2",
                    "ftps_state": "FtpsOnly",
                },
                source_resource_id="/subscriptions/123/sites/app",
                metadata={},
            ),
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Check for site config
        assert "Site Configuration" in code
        assert "always_on = true" in code
        assert "http2_enabled = true" in code
        assert 'minimum_tls_version = "1.2"' in code
        assert 'ftps_state = "FtpsOnly"' in code

    def test_generate_code_for_deployment_slots(self):
        """Test code generation for deployment slots."""
        plugin = AppServicePlugin()
        items = [
            DataPlaneItem(
                name="staging",
                item_type="deployment_slot",
                properties={"location": "eastus", "state": "Running"},
                source_resource_id="/subscriptions/123/sites/app",
                metadata={},
            ),
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Check for deployment slot
        assert "Deployment Slots" in code
        assert "azurerm_linux_web_app_slot" in code
        assert "staging" in code

    def test_generate_code_includes_deployment_guide(self):
        """Test code generation includes deployment guidance."""
        plugin = AppServicePlugin()
        items = [
            DataPlaneItem(
                name="TEST_SETTING",
                item_type="app_setting",
                properties={"value": "test"},
                source_resource_id="/subscriptions/123/sites/app",
                metadata={"sensitive": False},
            ),
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Check for deployment guide
        assert "Application Deployment Guide" in code
        assert "ZIP deployment" in code
        assert "Git deployment" in code
        assert "GitHub Actions" in code

    def test_generate_code_with_multiple_item_types(self):
        """Test code generation with mixed item types."""
        plugin = AppServicePlugin()
        items = [
            DataPlaneItem(
                name="APP_SETTING",
                item_type="app_setting",
                properties={"value": "value1"},
                source_resource_id="/subscriptions/123/sites/app",
                metadata={"sensitive": False},
            ),
            DataPlaneItem(
                name="ConnString",
                item_type="connection_string",
                properties={"value": "conn", "type": "Custom"},
                source_resource_id="/subscriptions/123/sites/app",
                metadata={"sensitive": True},
            ),
            DataPlaneItem(
                name="site_config",
                item_type="configuration",
                properties={"always_on": True},
                source_resource_id="/subscriptions/123/sites/app",
                metadata={},
            ),
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Should have all sections
        assert "Application Settings" in code
        assert "Connection Strings" in code
        assert "Site Configuration" in code

    def test_generate_code_unsupported_format_raises_error(self):
        """Test code generation raises error for unsupported format."""
        plugin = AppServicePlugin()
        items = []

        with pytest.raises(ValueError, match="not supported"):
            plugin.generate_replication_code(items, "bicep")


class TestAppServiceReplication:
    """Test replication functionality for App Service plugin."""

    def test_replicate_with_invalid_source_raises_error(self):
        """Test replicate raises ValueError for invalid source."""
        plugin = AppServicePlugin()
        invalid_source = {
            "type": "Microsoft.Storage/storageAccounts",
            "name": "storage",
        }
        valid_target = {
            "id": "/subscriptions/123/resourceGroups/rg/providers/Microsoft.Web/sites/target",
            "type": "Microsoft.Web/sites",
            "name": "target",
        }

        with pytest.raises(ValueError, match="Invalid source resource"):
            plugin.replicate(invalid_source, valid_target)

    def test_replicate_with_invalid_target_raises_error(self):
        """Test replicate raises ValueError for invalid target."""
        plugin = AppServicePlugin()
        valid_source = {
            "id": "/subscriptions/123/resourceGroups/rg/providers/Microsoft.Web/sites/source",
            "type": "Microsoft.Web/sites",
            "name": "source",
        }
        invalid_target = {
            "type": "Microsoft.Storage/storageAccounts",
            "name": "storage",
        }

        with pytest.raises(ValueError, match="Invalid target resource"):
            plugin.replicate(valid_source, invalid_target)

    @patch.object(AppServicePlugin, "discover")
    def test_replicate_with_discovery_error(self, mock_discover):
        """Test replicate handles discovery errors."""
        plugin = AppServicePlugin()
        source = {
            "id": "/subscriptions/123/resourceGroups/rg/providers/Microsoft.Web/sites/source",
            "type": "Microsoft.Web/sites",
            "name": "source",
        }
        target = {
            "id": "/subscriptions/123/resourceGroups/rg/providers/Microsoft.Web/sites/target",
            "type": "Microsoft.Web/sites",
            "name": "target",
        }

        mock_discover.side_effect = Exception("Discovery failed")

        result = plugin.replicate(source, target)

        assert result.success is False
        assert result.items_discovered == 0
        assert result.items_replicated == 0
        assert len(result.errors) > 0
        assert "Discovery failed" in result.errors[0]

    @patch.object(AppServicePlugin, "discover")
    def test_replicate_with_no_items(self, mock_discover):
        """Test replicate with no items to replicate."""
        plugin = AppServicePlugin()
        source = {
            "id": "/subscriptions/123/resourceGroups/rg/providers/Microsoft.Web/sites/source",
            "type": "Microsoft.Web/sites",
            "name": "source",
        }
        target = {
            "id": "/subscriptions/123/resourceGroups/rg/providers/Microsoft.Web/sites/target",
            "type": "Microsoft.Web/sites",
            "name": "target",
        }

        mock_discover.return_value = []

        result = plugin.replicate(source, target)

        assert result.success is True
        assert result.items_discovered == 0
        assert result.items_replicated == 0
        assert len(result.warnings) > 0

    @patch("azure.mgmt.web.WebSiteManagementClient")
    @patch("azure.identity.DefaultAzureCredential")
    @patch.object(AppServicePlugin, "discover")
    def test_replicate_app_settings_success(
        self, mock_discover, mock_credential, mock_web_client_class
    ):
        """Test successful replication of app settings."""
        plugin = AppServicePlugin()
        source = {
            "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg/providers/Microsoft.Web/sites/source",
            "type": "Microsoft.Web/sites",
            "name": "source",
        }
        target = {
            "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg/providers/Microsoft.Web/sites/target",
            "type": "Microsoft.Web/sites",
            "name": "target",
        }

        # Mock discovered items
        mock_discover.return_value = [
            DataPlaneItem(
                name="SETTING1",
                item_type="app_setting",
                properties={"value": "value1"},
                source_resource_id=source["id"],
                metadata={"sensitive": False},
            ),
        ]

        # Mock web client
        mock_web_client = MagicMock()
        mock_web_client_class.return_value = mock_web_client

        result = plugin.replicate(source, target)

        assert result.success is True
        assert result.items_discovered == 1
        assert result.items_replicated == 1
        assert len(result.errors) == 0

        # Verify update was called
        mock_web_client.web_apps.update_application_settings.assert_called_once()

    @patch("azure.mgmt.web.WebSiteManagementClient")
    @patch("azure.identity.DefaultAzureCredential")
    @patch.object(AppServicePlugin, "discover")
    def test_replicate_connection_strings_success(
        self, mock_discover, mock_credential, mock_web_client_class
    ):
        """Test successful replication of connection strings."""
        plugin = AppServicePlugin()
        source = {
            "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg/providers/Microsoft.Web/sites/source",
            "type": "Microsoft.Web/sites",
            "name": "source",
        }
        target = {
            "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg/providers/Microsoft.Web/sites/target",
            "type": "Microsoft.Web/sites",
            "name": "target",
        }

        # Mock discovered items
        mock_discover.return_value = [
            DataPlaneItem(
                name="DefaultConnection",
                item_type="connection_string",
                properties={"value": "Server=myserver", "type": "SQLAzure"},
                source_resource_id=source["id"],
                metadata={"sensitive": True},
            ),
        ]

        # Mock web client
        mock_web_client = MagicMock()
        mock_web_client_class.return_value = mock_web_client

        result = plugin.replicate(source, target)

        assert result.success is True
        assert result.items_discovered == 1
        assert result.items_replicated == 1
        assert len(result.warnings) > 0  # Security warning

        # Verify update was called
        mock_web_client.web_apps.update_connection_strings.assert_called_once()

    @patch("azure.mgmt.web.WebSiteManagementClient")
    @patch("azure.identity.DefaultAzureCredential")
    @patch.object(AppServicePlugin, "discover")
    def test_replicate_handles_permission_error(
        self, mock_discover, mock_credential, mock_web_client_class
    ):
        """Test replicate handles permission errors gracefully."""
        plugin = AppServicePlugin()
        source = {
            "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg/providers/Microsoft.Web/sites/source",
            "type": "Microsoft.Web/sites",
            "name": "source",
        }
        target = {
            "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg/providers/Microsoft.Web/sites/target",
            "type": "Microsoft.Web/sites",
            "name": "target",
        }

        # Mock discovered items
        mock_discover.return_value = [
            DataPlaneItem(
                name="SETTING1",
                item_type="app_setting",
                properties={"value": "value1"},
                source_resource_id=source["id"],
                metadata={"sensitive": False},
            ),
        ]

        # Mock web client with permission error
        mock_web_client = MagicMock()
        mock_web_client_class.return_value = mock_web_client

        from azure.core.exceptions import HttpResponseError

        mock_error = HttpResponseError(message="Forbidden")
        mock_error.status_code = 403
        mock_web_client.web_apps.update_application_settings.side_effect = mock_error

        result = plugin.replicate(source, target)

        assert result.success is False
        assert result.items_replicated == 0
        assert len(result.errors) > 0
        assert "Permission denied" in result.errors[0]

    @patch("azure.mgmt.web.WebSiteManagementClient")
    @patch("azure.identity.DefaultAzureCredential")
    @patch.object(AppServicePlugin, "discover")
    def test_replicate_with_invalid_resource_id_format(
        self, mock_discover, mock_credential, mock_web_client_class
    ):
        """Test replicate handles invalid resource ID format."""
        plugin = AppServicePlugin()
        source = {
            "id": "/invalid/format",
            "type": "Microsoft.Web/sites",
            "name": "source",
        }
        target = {
            "id": "/also/invalid",
            "type": "Microsoft.Web/sites",
            "name": "target",
        }

        # Mock discovered items
        mock_discover.return_value = [
            DataPlaneItem(
                name="SETTING1",
                item_type="app_setting",
                properties={"value": "value1"},
                source_resource_id=source["id"],
                metadata={"sensitive": False},
            ),
        ]

        result = plugin.replicate(source, target)

        assert result.success is False
        assert "Invalid resource ID format" in result.errors[0]


class TestAppServiceHelperMethods:
    """Test helper methods for App Service plugin."""

    def test_sanitize_name_basic(self):
        """Test name sanitization for basic names."""
        plugin = AppServicePlugin()
        assert plugin._sanitize_name("simple") == "simple"
        assert plugin._sanitize_name("UPPERCASE") == "uppercase"

    def test_sanitize_name_with_special_chars(self):
        """Test name sanitization handles special characters."""
        plugin = AppServicePlugin()
        assert plugin._sanitize_name("my-setting") == "my_setting"
        assert plugin._sanitize_name("my.setting") == "my_setting"
        assert plugin._sanitize_name("my:setting") == "my_setting"
        assert plugin._sanitize_name("my/setting") == "my_setting"

    def test_sanitize_name_starts_with_number(self):
        """Test name sanitization adds prefix for numeric start."""
        plugin = AppServicePlugin()
        result = plugin._sanitize_name("123test")
        assert result.startswith("app_")
        assert "123test" in result

    def test_is_sensitive_key(self):
        """Test sensitive key detection."""
        plugin = AppServicePlugin()

        # Sensitive keys
        assert plugin._is_sensitive_key("API_KEY") is True
        assert plugin._is_sensitive_key("db_password") is True
        assert plugin._is_sensitive_key("SECRET_TOKEN") is True
        assert (
            plugin._is_sensitive_key("connectionstring") is True
        )  # No underscore version
        assert plugin._is_sensitive_key("MyApiKey") is True

        # Non-sensitive keys
        assert plugin._is_sensitive_key("DB_HOST") is False
        assert plugin._is_sensitive_key("PORT") is False
        assert plugin._is_sensitive_key("APP_NAME") is False

    def test_escape_terraform_string(self):
        """Test Terraform string escaping."""
        plugin = AppServicePlugin()

        assert plugin._escape_terraform_string("simple") == "simple"
        assert plugin._escape_terraform_string('has "quotes"') == 'has \\"quotes\\"'
        assert plugin._escape_terraform_string("has\\backslash") == "has\\\\backslash"
        assert plugin._escape_terraform_string("line\nbreak") == "line\\nbreak"
        assert plugin._escape_terraform_string("tab\there") == "tab\\there"
