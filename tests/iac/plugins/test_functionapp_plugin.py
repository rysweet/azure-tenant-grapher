"""
Unit tests for Function App data plane plugin.

Tests cover:
- Function App resource validation
- Discovery functionality with mocked Azure SDK
- Terraform code generation
- Replication functionality
- Edge cases and error handling
"""

from unittest.mock import Mock, patch

import pytest

from src.iac.plugins.base_plugin import DataPlaneItem
from src.iac.plugins.functionapp_plugin import FunctionAppPlugin


class TestFunctionAppPlugin:
    """Test cases for FunctionAppPlugin instantiation and basic properties."""

    def test_plugin_instantiation(self):
        """Test that FunctionAppPlugin can be instantiated."""
        plugin = FunctionAppPlugin()
        assert plugin is not None
        assert plugin.plugin_name == "FunctionAppPlugin"

    def test_supported_resource_type(self):
        """Test that plugin supports correct resource type."""
        plugin = FunctionAppPlugin()
        assert plugin.supported_resource_type == "Microsoft.Web/sites"

    def test_supports_terraform_format(self):
        """Test that plugin supports Terraform output format."""
        plugin = FunctionAppPlugin()
        assert plugin.supports_output_format("terraform") is True
        assert plugin.supports_output_format("TERRAFORM") is True

    def test_does_not_support_other_formats(self):
        """Test that plugin doesn't support other formats yet."""
        plugin = FunctionAppPlugin()
        assert plugin.supports_output_format("bicep") is False
        assert plugin.supports_output_format("arm") is False


class TestFunctionAppValidation:
    """Test resource validation for Function App plugin."""

    def test_validate_valid_functionapp_resource(self):
        """Test validation succeeds for valid Function App resource."""
        plugin = FunctionAppPlugin()
        resource = {
            "id": "/subscriptions/123/resourceGroups/rg/providers/Microsoft.Web/sites/my-func",
            "type": "Microsoft.Web/sites",
            "name": "my-func",
            "kind": "functionapp,linux",
        }

        assert plugin.validate_resource(resource) is True

    def test_validate_valid_functionapp_windows(self):
        """Test validation succeeds for Windows Function App."""
        plugin = FunctionAppPlugin()
        resource = {
            "id": "/subscriptions/123/resourceGroups/rg/providers/Microsoft.Web/sites/win-func",
            "type": "Microsoft.Web/sites",
            "name": "win-func",
            "kind": "functionapp",
        }

        assert plugin.validate_resource(resource) is True

    def test_validate_valid_functionapp_container(self):
        """Test validation succeeds for Function App with container."""
        plugin = FunctionAppPlugin()
        resource = {
            "id": "/subscriptions/123/resourceGroups/rg/providers/Microsoft.Web/sites/container-func",
            "type": "Microsoft.Web/sites",
            "name": "container-func",
            "kind": "functionapp,linux,container",
        }

        assert plugin.validate_resource(resource) is True

    def test_validate_wrong_resource_type(self):
        """Test validation fails for wrong resource type."""
        plugin = FunctionAppPlugin()
        resource = {
            "id": "/subscriptions/123",
            "type": "Microsoft.Storage/storageAccounts",
            "name": "storage",
            "kind": "StorageV2",
        }

        assert plugin.validate_resource(resource) is False

    def test_validate_webapp_not_functionapp(self):
        """Test validation fails for regular web app (not function app)."""
        plugin = FunctionAppPlugin()
        resource = {
            "id": "/subscriptions/123/resourceGroups/rg/providers/Microsoft.Web/sites/webapp",
            "type": "Microsoft.Web/sites",
            "name": "webapp",
            "kind": "app",  # Regular web app, not function app
        }

        assert plugin.validate_resource(resource) is False

    def test_validate_missing_kind(self):
        """Test validation fails for missing kind field."""
        plugin = FunctionAppPlugin()
        resource = {
            "id": "/subscriptions/123/resourceGroups/rg/providers/Microsoft.Web/sites/func",
            "type": "Microsoft.Web/sites",
            "name": "func",
            # Missing 'kind'
        }

        assert plugin.validate_resource(resource) is False

    def test_validate_missing_id(self):
        """Test validation fails for missing resource ID."""
        plugin = FunctionAppPlugin()
        resource = {
            "type": "Microsoft.Web/sites",
            "name": "my-func",
            "kind": "functionapp",
            # Missing 'id'
        }

        assert plugin.validate_resource(resource) is False

    def test_validate_none_resource(self):
        """Test validation fails for None resource."""
        plugin = FunctionAppPlugin()
        assert plugin.validate_resource(None) is False

    def test_validate_empty_resource(self):
        """Test validation fails for empty resource."""
        plugin = FunctionAppPlugin()
        assert plugin.validate_resource({}) is False


class TestFunctionAppDiscovery:
    """Test discovery functionality for Function App plugin."""

    def test_discover_invalid_resource_raises_error(self):
        """Test discover raises ValueError for invalid resource."""
        plugin = FunctionAppPlugin()
        resource = {
            "type": "Microsoft.Storage/storageAccounts",
            "name": "storage",
        }

        with pytest.raises(ValueError, match="Invalid resource"):
            plugin.discover(resource)

    def test_discover_with_invalid_resource_id(self):
        """Test discover handles invalid resource ID format."""
        plugin = FunctionAppPlugin()
        resource = {
            "id": "/invalid/id",
            "type": "Microsoft.Web/sites",
            "name": "my-func",
            "kind": "functionapp",
        }

        items = plugin.discover(resource)
        assert items == []

    @patch("azure.mgmt.web.WebSiteManagementClient")
    @patch("azure.identity.DefaultAzureCredential")
    def test_discover_app_settings(self, mock_credential, mock_web_client_class):
        """Test discover returns application settings."""
        plugin = FunctionAppPlugin()

        # Setup mock
        mock_client = Mock()
        mock_web_client_class.return_value = mock_client

        # Mock application settings
        mock_settings = Mock()
        mock_settings.properties = {
            "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=abc123;",
            "FUNCTIONS_WORKER_RUNTIME": "python",
            "FUNCTIONS_EXTENSION_VERSION": "~4",
            "CUSTOM_SETTING": "value",
        }
        mock_client.web_apps.list_application_settings.return_value = mock_settings

        # Mock other methods to return empty
        from azure.core.exceptions import HttpResponseError

        mock_client.web_apps.list_functions.return_value = []
        mock_client.web_apps.get_configuration.side_effect = HttpResponseError(
            "Not found"
        )
        mock_client.web_apps.list_connection_strings.return_value = Mock(properties={})

        resource = {
            "id": "/subscriptions/sub-123/resourceGroups/rg-1/providers/Microsoft.Web/sites/func-app",
            "type": "Microsoft.Web/sites",
            "name": "func-app",
            "kind": "functionapp,linux",
        }

        items = plugin.discover(resource)

        # Should have 4 app settings
        app_setting_items = [item for item in items if "setting" in item.item_type]
        assert len(app_setting_items) == 4

        # Check specific settings
        setting_names = [item.name for item in app_setting_items]
        assert "AzureWebJobsStorage" in setting_names
        assert "FUNCTIONS_WORKER_RUNTIME" in setting_names
        assert "CUSTOM_SETTING" in setting_names

        # Check that sensitive settings are redacted (AzureWebJobsStorage contains "Key")
        storage_setting = next(
            item for item in app_setting_items if item.name == "AzureWebJobsStorage"
        )
        # The value contains "AccountKey" so it should be redacted
        assert storage_setting.properties["value"] == "***REDACTED***"
        assert storage_setting.properties["is_sensitive"] is True

    @patch("azure.mgmt.web.WebSiteManagementClient")
    @patch("azure.identity.DefaultAzureCredential")
    def test_discover_functions(self, mock_credential, mock_web_client_class):
        """Test discover returns function definitions."""
        plugin = FunctionAppPlugin()

        # Setup mock
        mock_client = Mock()
        mock_web_client_class.return_value = mock_client

        # Mock functions
        mock_function1 = Mock()
        mock_function1.name = "sites/func-app/HttpTrigger1"
        mock_function1.id = "/subscriptions/.../functions/HttpTrigger1"
        mock_function1.href = "https://..."
        mock_function1.properties = Mock()
        mock_function1.properties.config = {
            "bindings": [{"type": "httpTrigger", "direction": "in", "name": "req"}]
        }

        mock_function2 = Mock()
        mock_function2.name = "sites/func-app/TimerTrigger1"
        mock_function2.id = "/subscriptions/.../functions/TimerTrigger1"
        mock_function2.properties = Mock()
        mock_function2.properties.config = {
            "bindings": [
                {"type": "timerTrigger", "direction": "in", "schedule": "0 */5 * * * *"}
            ]
        }

        mock_client.web_apps.list_functions.return_value = [
            mock_function1,
            mock_function2,
        ]

        # Mock other methods
        mock_client.web_apps.list_application_settings.return_value = Mock(
            properties={}
        )
        mock_client.web_apps.get_configuration.side_effect = Exception("Not found")
        mock_client.web_apps.list_connection_strings.return_value = Mock(properties={})

        resource = {
            "id": "/subscriptions/sub-123/resourceGroups/rg-1/providers/Microsoft.Web/sites/func-app",
            "type": "Microsoft.Web/sites",
            "name": "func-app",
            "kind": "functionapp",
        }

        items = plugin.discover(resource)

        # Should have 2 functions
        function_items = [item for item in items if item.item_type == "function"]
        assert len(function_items) == 2

        # Check function details
        http_func = next(item for item in function_items if "HttpTrigger1" in item.name)
        assert http_func.properties["trigger_type"] == "httpTrigger"
        assert len(http_func.properties["bindings"]) == 1

        timer_func = next(
            item for item in function_items if "TimerTrigger1" in item.name
        )
        assert timer_func.properties["trigger_type"] == "timerTrigger"

    @patch("azure.mgmt.web.WebSiteManagementClient")
    @patch("azure.identity.DefaultAzureCredential")
    def test_discover_site_configuration(self, mock_credential, mock_web_client_class):
        """Test discover returns site configuration."""
        plugin = FunctionAppPlugin()

        # Setup mock
        mock_client = Mock()
        mock_web_client_class.return_value = mock_client

        # Mock site config
        mock_config = Mock()
        mock_config.always_on = True
        mock_config.app_command_line = ""
        mock_config.linux_fx_version = "PYTHON|3.9"
        mock_config.windows_fx_version = None
        mock_config.http20_enabled = True
        mock_config.min_tls_version = "1.2"
        mock_config.ftps_state = "FtpsOnly"

        mock_client.web_apps.get_configuration.return_value = mock_config
        mock_client.web_apps.list_application_settings.return_value = Mock(
            properties={}
        )
        mock_client.web_apps.list_functions.return_value = []
        mock_client.web_apps.list_connection_strings.return_value = Mock(properties={})

        resource = {
            "id": "/subscriptions/sub-123/resourceGroups/rg-1/providers/Microsoft.Web/sites/func-app",
            "type": "Microsoft.Web/sites",
            "name": "func-app",
            "kind": "functionapp,linux",
        }

        items = plugin.discover(resource)

        # Should have site config
        config_items = [item for item in items if item.item_type == "site_config"]
        assert len(config_items) == 1

        config = config_items[0]
        assert config.properties["always_on"] is True
        assert config.properties["linux_fx_version"] == "PYTHON|3.9"
        assert config.properties["min_tls_version"] == "1.2"

    @patch("azure.mgmt.web.WebSiteManagementClient")
    @patch("azure.identity.DefaultAzureCredential")
    def test_discover_connection_strings(self, mock_credential, mock_web_client_class):
        """Test discover returns connection strings."""
        plugin = FunctionAppPlugin()

        # Setup mock
        mock_client = Mock()
        mock_web_client_class.return_value = mock_client

        # Mock connection strings
        mock_conn_string1 = Mock()
        mock_conn_string1.type = "SQLAzure"

        mock_conn_string2 = Mock()
        mock_conn_string2.type = "Custom"

        mock_conn_strings = Mock()
        mock_conn_strings.properties = {
            "DatabaseConnection": mock_conn_string1,
            "CustomConnection": mock_conn_string2,
        }

        mock_client.web_apps.list_connection_strings.return_value = mock_conn_strings
        mock_client.web_apps.list_application_settings.return_value = Mock(
            properties={}
        )
        mock_client.web_apps.list_functions.return_value = []
        from azure.core.exceptions import HttpResponseError

        mock_client.web_apps.get_configuration.side_effect = HttpResponseError(
            "Not found"
        )

        resource = {
            "id": "/subscriptions/sub-123/resourceGroups/rg-1/providers/Microsoft.Web/sites/func-app",
            "type": "Microsoft.Web/sites",
            "name": "func-app",
            "kind": "functionapp",
        }

        items = plugin.discover(resource)

        # Should have connection strings
        conn_items = [item for item in items if item.item_type == "connection_string"]
        assert len(conn_items) == 2

        # Check that values are redacted
        for item in conn_items:
            assert item.properties["value"] == "***REDACTED***"

        # Check types
        db_conn = next(item for item in conn_items if item.name == "DatabaseConnection")
        assert db_conn.properties["type"] == "SQLAzure"

    @patch("azure.mgmt.web.WebSiteManagementClient")
    @patch("azure.identity.DefaultAzureCredential")
    def test_discover_handles_api_errors_gracefully(
        self, mock_credential, mock_web_client_class
    ):
        """Test discover handles API errors without crashing."""
        plugin = FunctionAppPlugin()

        # Setup mock that throws errors
        mock_client = Mock()
        mock_web_client_class.return_value = mock_client

        # All API calls fail
        from azure.core.exceptions import HttpResponseError

        mock_client.web_apps.list_application_settings.side_effect = HttpResponseError(
            "Forbidden"
        )
        mock_client.web_apps.list_functions.side_effect = HttpResponseError("Forbidden")
        mock_client.web_apps.get_configuration.side_effect = HttpResponseError(
            "Forbidden"
        )
        mock_client.web_apps.list_connection_strings.side_effect = HttpResponseError(
            "Forbidden"
        )

        resource = {
            "id": "/subscriptions/sub-123/resourceGroups/rg-1/providers/Microsoft.Web/sites/func-app",
            "type": "Microsoft.Web/sites",
            "name": "func-app",
            "kind": "functionapp",
        }

        # Should not crash, just return empty list
        items = plugin.discover(resource)
        assert items == []

    def test_discover_missing_azure_sdk(self):
        """Test discover handles missing Azure SDK gracefully."""
        plugin = FunctionAppPlugin()

        # Mock import error by patching the import statement
        with patch.dict("sys.modules", {"azure.mgmt.web": None}):
            resource = {
                "id": "/subscriptions/sub-123/resourceGroups/rg-1/providers/Microsoft.Web/sites/func-app",
                "type": "Microsoft.Web/sites",
                "name": "func-app",
                "kind": "functionapp",
            }

            items = plugin.discover(resource)
            # Should return empty list, not crash
            assert items == []


class TestFunctionAppCodeGeneration:
    """Test Terraform code generation for Function App plugin."""

    def test_generate_replication_code_empty_items(self):
        """Test code generation with no items."""
        plugin = FunctionAppPlugin()
        items = []

        code = plugin.generate_replication_code(items, "terraform")

        assert "No Function App data plane items" in code

    def test_generate_replication_code_unsupported_format(self):
        """Test code generation raises error for unsupported format."""
        plugin = FunctionAppPlugin()
        items = [
            DataPlaneItem(
                name="test",
                item_type="app_setting",
                properties={},
                source_resource_id="/subscriptions/123",
            )
        ]

        with pytest.raises(ValueError, match="not supported"):
            plugin.generate_replication_code(items, "bicep")

    def test_generate_replication_code_app_settings(self):
        """Test code generation includes app settings."""
        plugin = FunctionAppPlugin()
        items = [
            DataPlaneItem(
                name="FUNCTIONS_WORKER_RUNTIME",
                item_type="function_app_setting",
                properties={"value": "python", "is_sensitive": False},
                source_resource_id="/subscriptions/123",
            ),
            DataPlaneItem(
                name="CUSTOM_SETTING",
                item_type="app_setting",
                properties={"value": "custom_value", "is_sensitive": False},
                source_resource_id="/subscriptions/123",
            ),
        ]

        code = plugin.generate_replication_code(items, "terraform")

        assert "Application Settings" in code
        assert "FUNCTIONS_WORKER_RUNTIME" in code
        assert "CUSTOM_SETTING" in code
        assert "python" in code
        assert "custom_value" in code

    def test_generate_replication_code_sensitive_settings(self):
        """Test code generation creates variables for sensitive settings."""
        plugin = FunctionAppPlugin()
        items = [
            DataPlaneItem(
                name="AzureWebJobsStorage",
                item_type="function_app_setting",
                properties={"value": "***REDACTED***", "is_sensitive": True},
                source_resource_id="/subscriptions/123",
            ),
            DataPlaneItem(
                name="DATABASE_PASSWORD",
                item_type="app_setting",
                properties={"value": "***REDACTED***", "is_sensitive": True},
                source_resource_id="/subscriptions/123",
            ),
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Should create variables
        assert "variable" in code
        assert "function_app_setting_azurewebjobsstorage" in code
        assert "function_app_setting_database_password" in code
        assert "sensitive   = true" in code

    def test_generate_replication_code_functions(self):
        """Test code generation includes function deployment guidance."""
        plugin = FunctionAppPlugin()
        items = [
            DataPlaneItem(
                name="HttpTrigger1",
                item_type="function",
                properties={
                    "trigger_type": "httpTrigger",
                    "bindings": [{"type": "httpTrigger"}],
                    "config": {},
                },
                source_resource_id="/subscriptions/123",
            ),
            DataPlaneItem(
                name="TimerTrigger1",
                item_type="function",
                properties={
                    "trigger_type": "timerTrigger",
                    "bindings": [{"type": "timerTrigger"}],
                    "config": {},
                },
                source_resource_id="/subscriptions/123",
            ),
        ]

        code = plugin.generate_replication_code(items, "terraform")

        assert "Discovered Functions" in code
        assert "HttpTrigger1" in code
        assert "TimerTrigger1" in code
        assert "httpTrigger" in code
        assert "timerTrigger" in code
        assert "func azure functionapp publish" in code

    def test_generate_replication_code_site_config(self):
        """Test code generation includes site configuration."""
        plugin = FunctionAppPlugin()
        items = [
            DataPlaneItem(
                name="site_config",
                item_type="site_config",
                properties={
                    "always_on": True,
                    "http20_enabled": True,
                    "min_tls_version": "1.2",
                    "ftps_state": "FtpsOnly",
                },
                source_resource_id="/subscriptions/123",
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        assert "Site Configuration" in code
        assert "always_on = true" in code
        assert "http20_enabled = true" in code
        assert 'min_tls_version = "1.2"' in code
        assert 'ftps_state = "FtpsOnly"' in code

    def test_generate_replication_code_connection_strings(self):
        """Test code generation includes connection strings as variables."""
        plugin = FunctionAppPlugin()
        items = [
            DataPlaneItem(
                name="DatabaseConnection",
                item_type="connection_string",
                properties={"type": "SQLAzure", "value": "***REDACTED***"},
                source_resource_id="/subscriptions/123",
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        assert "Connection Strings" in code
        assert "DatabaseConnection" in code
        assert "variable" in code
        assert "function_app_connection_databaseconnection" in code
        assert "sensitive   = true" in code

    def test_generate_replication_code_deployment_methods(self):
        """Test code generation includes deployment method guidance."""
        plugin = FunctionAppPlugin()
        items = [
            DataPlaneItem(
                name="test",
                item_type="app_setting",
                properties={"value": "test"},
                source_resource_id="/subscriptions/123",
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Check for various deployment methods
        assert "Zip Deploy" in code or "zip" in code.lower()
        assert "GitHub Actions" in code
        assert "Azure DevOps" in code
        assert "az functionapp deployment" in code

    def test_sanitize_name(self):
        """Test name sanitization for Terraform identifiers."""
        plugin = FunctionAppPlugin()

        assert plugin._sanitize_name("simple") == "simple"
        assert plugin._sanitize_name("with-dashes") == "with_dashes"
        assert plugin._sanitize_name("with.dots") == "with_dots"
        assert plugin._sanitize_name("with spaces") == "with_spaces"
        assert plugin._sanitize_name("with:colons") == "with_colons"
        assert plugin._sanitize_name("123numeric") == "func_123numeric"
        assert plugin._sanitize_name("UPPERCASE") == "uppercase"


class TestFunctionAppReplication:
    """Test replication functionality for Function App plugin."""

    def test_replicate_invalid_source_raises_error(self):
        """Test replicate raises ValueError for invalid source."""
        plugin = FunctionAppPlugin()

        source = {"type": "Microsoft.Storage/storageAccounts", "name": "storage"}
        target = {
            "id": "/subscriptions/123/resourceGroups/rg/providers/Microsoft.Web/sites/target",
            "type": "Microsoft.Web/sites",
            "name": "target",
            "kind": "functionapp",
        }

        with pytest.raises(ValueError, match="Invalid source resource"):
            plugin.replicate(source, target)

    def test_replicate_invalid_target_raises_error(self):
        """Test replicate raises ValueError for invalid target."""
        plugin = FunctionAppPlugin()

        source = {
            "id": "/subscriptions/123/resourceGroups/rg/providers/Microsoft.Web/sites/source",
            "type": "Microsoft.Web/sites",
            "name": "source",
            "kind": "functionapp",
        }
        target = {"type": "Microsoft.Storage/storageAccounts", "name": "storage"}

        with pytest.raises(ValueError, match="Invalid target resource"):
            plugin.replicate(source, target)

    @patch.object(FunctionAppPlugin, "discover")
    def test_replicate_discovery_failure(self, mock_discover):
        """Test replicate handles discovery failure."""
        plugin = FunctionAppPlugin()

        mock_discover.side_effect = Exception("Discovery failed")

        source = {
            "id": "/subscriptions/123/resourceGroups/rg/providers/Microsoft.Web/sites/source",
            "type": "Microsoft.Web/sites",
            "name": "source",
            "kind": "functionapp",
        }
        target = {
            "id": "/subscriptions/456/resourceGroups/rg2/providers/Microsoft.Web/sites/target",
            "type": "Microsoft.Web/sites",
            "name": "target",
            "kind": "functionapp",
        }

        result = plugin.replicate(source, target)

        assert result.success is False
        assert result.items_discovered == 0
        assert result.items_replicated == 0
        assert len(result.errors) > 0
        assert "Discovery failed" in result.errors[0]

    @patch.object(FunctionAppPlugin, "discover")
    def test_replicate_no_items_to_replicate(self, mock_discover):
        """Test replicate handles empty discovery results."""
        plugin = FunctionAppPlugin()

        mock_discover.return_value = []

        source = {
            "id": "/subscriptions/123/resourceGroups/rg/providers/Microsoft.Web/sites/source",
            "type": "Microsoft.Web/sites",
            "name": "source",
            "kind": "functionapp",
        }
        target = {
            "id": "/subscriptions/456/resourceGroups/rg2/providers/Microsoft.Web/sites/target",
            "type": "Microsoft.Web/sites",
            "name": "target",
            "kind": "functionapp",
        }

        result = plugin.replicate(source, target)

        assert result.success is True
        assert result.items_discovered == 0
        assert result.items_replicated == 0
        assert len(result.warnings) > 0

    @patch.object(FunctionAppPlugin, "discover")
    @patch("azure.mgmt.web.WebSiteManagementClient")
    @patch("azure.identity.DefaultAzureCredential")
    def test_replicate_app_settings_success(
        self, mock_credential, mock_web_client_class, mock_discover
    ):
        """Test replicate successfully replicates app settings."""
        plugin = FunctionAppPlugin()

        # Mock discovery
        mock_discover.return_value = [
            DataPlaneItem(
                name="FUNCTIONS_WORKER_RUNTIME",
                item_type="function_app_setting",
                properties={"value": "python", "is_sensitive": False},
                source_resource_id="/subscriptions/123/resourceGroups/rg/providers/Microsoft.Web/sites/source",
            ),
            DataPlaneItem(
                name="CUSTOM_SETTING",
                item_type="app_setting",
                properties={"value": "custom", "is_sensitive": False},
                source_resource_id="/subscriptions/123/resourceGroups/rg/providers/Microsoft.Web/sites/source",
            ),
        ]

        # Mock Azure SDK
        mock_client = Mock()
        mock_web_client_class.return_value = mock_client

        source = {
            "id": "/subscriptions/sub-123/resourceGroups/rg-1/providers/Microsoft.Web/sites/source-func",
            "type": "Microsoft.Web/sites",
            "name": "source-func",
            "kind": "functionapp",
        }
        target = {
            "id": "/subscriptions/sub-456/resourceGroups/rg-2/providers/Microsoft.Web/sites/target-func",
            "type": "Microsoft.Web/sites",
            "name": "target-func",
            "kind": "functionapp",
        }

        result = plugin.replicate(source, target)

        assert result.success is True
        assert result.items_discovered == 2
        assert result.items_replicated == 2
        assert mock_client.web_apps.update_application_settings.called

    @patch.object(FunctionAppPlugin, "discover")
    @patch("azure.mgmt.web.WebSiteManagementClient")
    @patch("azure.identity.DefaultAzureCredential")
    def test_replicate_skips_sensitive_settings(
        self, mock_credential, mock_web_client_class, mock_discover
    ):
        """Test replicate skips redacted sensitive settings."""
        plugin = FunctionAppPlugin()

        # Mock discovery with sensitive setting
        mock_discover.return_value = [
            DataPlaneItem(
                name="AzureWebJobsStorage",
                item_type="function_app_setting",
                properties={"value": "***REDACTED***", "is_sensitive": True},
                source_resource_id="/subscriptions/123/resourceGroups/rg/providers/Microsoft.Web/sites/source",
            )
        ]

        # Mock Azure SDK
        mock_client = Mock()
        mock_web_client_class.return_value = mock_client

        source = {
            "id": "/subscriptions/sub-123/resourceGroups/rg-1/providers/Microsoft.Web/sites/source-func",
            "type": "Microsoft.Web/sites",
            "name": "source-func",
            "kind": "functionapp",
        }
        target = {
            "id": "/subscriptions/sub-456/resourceGroups/rg-2/providers/Microsoft.Web/sites/target-func",
            "type": "Microsoft.Web/sites",
            "name": "target-func",
            "kind": "functionapp",
        }

        result = plugin.replicate(source, target)

        # Should warn about sensitive setting
        assert len(result.warnings) > 0
        assert any("sensitive" in w.lower() for w in result.warnings)

    @patch.object(FunctionAppPlugin, "discover")
    @patch("azure.mgmt.web.WebSiteManagementClient")
    @patch("azure.identity.DefaultAzureCredential")
    def test_replicate_handles_connection_strings(
        self, mock_credential, mock_web_client_class, mock_discover
    ):
        """Test replicate adds warning for connection strings."""
        plugin = FunctionAppPlugin()

        # Mock discovery with connection strings
        mock_discover.return_value = [
            DataPlaneItem(
                name="DatabaseConnection",
                item_type="connection_string",
                properties={"type": "SQLAzure", "value": "***REDACTED***"},
                source_resource_id="/subscriptions/123/resourceGroups/rg/providers/Microsoft.Web/sites/source",
            )
        ]

        # Mock Azure SDK
        mock_client = Mock()
        mock_web_client_class.return_value = mock_client

        source = {
            "id": "/subscriptions/sub-123/resourceGroups/rg-1/providers/Microsoft.Web/sites/source-func",
            "type": "Microsoft.Web/sites",
            "name": "source-func",
            "kind": "functionapp",
        }
        target = {
            "id": "/subscriptions/sub-456/resourceGroups/rg-2/providers/Microsoft.Web/sites/target-func",
            "type": "Microsoft.Web/sites",
            "name": "target-func",
            "kind": "functionapp",
        }

        result = plugin.replicate(source, target)

        # Should warn about connection strings
        assert len(result.warnings) > 0
        assert any("connection string" in w.lower() for w in result.warnings)

    @patch.object(FunctionAppPlugin, "discover")
    @patch("azure.mgmt.web.WebSiteManagementClient")
    @patch("azure.identity.DefaultAzureCredential")
    def test_replicate_handles_functions_warning(
        self, mock_credential, mock_web_client_class, mock_discover
    ):
        """Test replicate adds warning for functions."""
        plugin = FunctionAppPlugin()

        # Mock discovery with functions
        mock_discover.return_value = [
            DataPlaneItem(
                name="HttpTrigger1",
                item_type="function",
                properties={
                    "trigger_type": "httpTrigger",
                    "bindings": [],
                    "config": {},
                },
                source_resource_id="/subscriptions/123/resourceGroups/rg/providers/Microsoft.Web/sites/source",
            )
        ]

        # Mock Azure SDK
        mock_client = Mock()
        mock_web_client_class.return_value = mock_client

        source = {
            "id": "/subscriptions/sub-123/resourceGroups/rg-1/providers/Microsoft.Web/sites/source-func",
            "type": "Microsoft.Web/sites",
            "name": "source-func",
            "kind": "functionapp",
        }
        target = {
            "id": "/subscriptions/sub-456/resourceGroups/rg-2/providers/Microsoft.Web/sites/target-func",
            "type": "Microsoft.Web/sites",
            "name": "target-func",
            "kind": "functionapp",
        }

        result = plugin.replicate(source, target)

        # Should warn about functions
        assert len(result.warnings) > 0
        assert any("function" in w.lower() for w in result.warnings)

    @patch.object(FunctionAppPlugin, "discover")
    @patch("azure.mgmt.web.WebSiteManagementClient")
    @patch("azure.identity.DefaultAzureCredential")
    def test_replicate_handles_api_errors(
        self, mock_credential, mock_web_client_class, mock_discover
    ):
        """Test replicate handles API errors gracefully."""
        plugin = FunctionAppPlugin()

        # Mock discovery
        mock_discover.return_value = [
            DataPlaneItem(
                name="SETTING",
                item_type="app_setting",
                properties={"value": "value", "is_sensitive": False},
                source_resource_id="/subscriptions/123/resourceGroups/rg/providers/Microsoft.Web/sites/source",
            )
        ]

        # Mock Azure SDK to throw error
        mock_client = Mock()
        mock_web_client_class.return_value = mock_client

        from azure.core.exceptions import HttpResponseError

        mock_client.web_apps.update_application_settings.side_effect = (
            HttpResponseError("Forbidden")
        )

        source = {
            "id": "/subscriptions/sub-123/resourceGroups/rg-1/providers/Microsoft.Web/sites/source-func",
            "type": "Microsoft.Web/sites",
            "name": "source-func",
            "kind": "functionapp",
        }
        target = {
            "id": "/subscriptions/sub-456/resourceGroups/rg-2/providers/Microsoft.Web/sites/target-func",
            "type": "Microsoft.Web/sites",
            "name": "target-func",
            "kind": "functionapp",
        }

        result = plugin.replicate(source, target)

        assert len(result.errors) > 0
        assert result.items_replicated == 0

    def test_replicate_invalid_resource_id_format(self):
        """Test replicate handles invalid resource ID format."""
        plugin = FunctionAppPlugin()

        source = {
            "id": "/invalid/id",
            "type": "Microsoft.Web/sites",
            "name": "source",
            "kind": "functionapp",
        }
        target = {
            "id": "/invalid/id2",
            "type": "Microsoft.Web/sites",
            "name": "target",
            "kind": "functionapp",
        }

        # Mock discover to return items so we don't exit early
        mock_items = [
            DataPlaneItem(
                name="test",
                item_type="app_setting",
                properties={"value": "test"},
                source_resource_id="/subscriptions/123/resourceGroups/rg/providers/Microsoft.Web/sites/source",
            )
        ]

        with patch.object(plugin, "discover", return_value=mock_items):
            result = plugin.replicate(source, target)

            assert result.success is False
            assert "Invalid resource ID" in result.errors[0]

    @patch.object(FunctionAppPlugin, "discover")
    def test_replicate_missing_azure_sdk(self, mock_discover):
        """Test replicate handles missing Azure SDK."""
        plugin = FunctionAppPlugin()

        # Mock discovery
        mock_discover.return_value = [
            DataPlaneItem(
                name="test",
                item_type="app_setting",
                properties={"value": "test"},
                source_resource_id="/subscriptions/123/resourceGroups/rg/providers/Microsoft.Web/sites/source",
            )
        ]

        source = {
            "id": "/subscriptions/sub-123/resourceGroups/rg-1/providers/Microsoft.Web/sites/source-func",
            "type": "Microsoft.Web/sites",
            "name": "source-func",
            "kind": "functionapp",
        }
        target = {
            "id": "/subscriptions/sub-456/resourceGroups/rg-2/providers/Microsoft.Web/sites/target-func",
            "type": "Microsoft.Web/sites",
            "name": "target-func",
            "kind": "functionapp",
        }

        # Mock missing SDK
        with patch.dict("sys.modules", {"azure.mgmt.web": None}):
            result = plugin.replicate(source, target)

            assert result.success is False
            assert result.items_replicated == 0
            assert any("SDK not installed" in e for e in result.errors)
