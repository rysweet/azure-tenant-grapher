"""
Unit tests for AppServicePlugin.

Tests cover:
- Resource validation
- Discovery of app settings, connection strings, deployment slots
- Mode-aware discovery and replication
- IaC code generation
- Permission requirements
- Error handling
"""

from unittest.mock import Mock, patch

import pytest

from src.iac.plugins.appservice_plugin import AppServicePlugin
from src.iac.plugins.base_plugin import (
    DataPlaneItem,
    ReplicationMode,
    ReplicationResult,
)


class TestAppServicePlugin:
    """Test suite for AppServicePlugin."""

    @pytest.fixture
    def plugin(self):
        """Create plugin instance for testing."""
        return AppServicePlugin()

    @pytest.fixture
    def sample_resource(self):
        """Sample App Service resource for testing."""
        return {
            "id": "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Web/sites/my-app",
            "type": "Microsoft.Web/sites",
            "name": "my-app",
            "properties": {
                "state": "Running",
                "enabled": True,
                "defaultHostName": "my-app.azurewebsites.net",
            },
        }

    def test_supported_resource_type(self, plugin):
        """Test that plugin returns correct resource type."""
        assert plugin.supported_resource_type == "Microsoft.Web/sites"

    def test_plugin_name(self, plugin):
        """Test that plugin has correct name."""
        assert plugin.plugin_name == "AppServicePlugin"

    def test_validate_resource_valid(self, plugin, sample_resource):
        """Test resource validation with valid resource."""
        assert plugin.validate_resource(sample_resource) is True

    def test_validate_resource_wrong_type(self, plugin):
        """Test resource validation with wrong resource type."""
        resource = {
            "id": "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Storage/storageAccounts/mystorage",
            "type": "Microsoft.Storage/storageAccounts",
            "name": "mystorage",
        }
        assert plugin.validate_resource(resource) is False

    def test_validate_resource_missing_id(self, plugin):
        """Test resource validation with missing ID."""
        resource = {"type": "Microsoft.Web/sites", "name": "my-app"}
        assert plugin.validate_resource(resource) is False

    def test_validate_resource_none(self, plugin):
        """Test resource validation with None."""
        assert plugin.validate_resource(None) is False

    def test_sanitize_name(self, plugin):
        """Test name sanitization for Terraform."""
        assert plugin._sanitize_name("my-app-name") == "my_app_name"
        assert plugin._sanitize_name("app.name") == "app_name"
        assert plugin._sanitize_name("app/slot") == "app_slot"
        assert plugin._sanitize_name("APP:KEY") == "app_key"
        assert plugin._sanitize_name("123-app") == "app_123_app"

    def test_is_sensitive_key(self, plugin):
        """Test sensitive key detection."""
        # Sensitive keys
        assert plugin._is_sensitive_key("DB_PASSWORD") is True
        assert plugin._is_sensitive_key("API_SECRET") is True
        assert plugin._is_sensitive_key("ConnectionString") is True
        assert plugin._is_sensitive_key("api_key") is True
        assert plugin._is_sensitive_key("JWT_TOKEN") is True
        assert plugin._is_sensitive_key("client_secret") is True

        # Non-sensitive keys
        assert plugin._is_sensitive_key("DB_HOST") is False
        assert plugin._is_sensitive_key("APP_NAME") is False
        assert plugin._is_sensitive_key("LOG_LEVEL") is False

    @patch("azure.mgmt.web.WebSiteManagementClient")
    @patch("azure.identity.DefaultAzureCredential")
    def test_discover_app_settings(
        self, mock_credential, mock_web_client, plugin, sample_resource
    ):
        """Test discovery of app settings."""
        # Mock credential
        mock_cred_instance = Mock()
        mock_credential.return_value = mock_cred_instance

        # Mock web client
        mock_client_instance = Mock()
        mock_web_client.return_value = mock_client_instance

        # Mock app settings response
        mock_settings = Mock()
        mock_settings.properties = {
            "DB_HOST": "localhost",
            "DB_PASSWORD": "secret123",
            "APP_NAME": "myapp",
        }
        mock_client_instance.web_apps.list_application_settings.return_value = (
            mock_settings
        )

        # Mock empty connection strings and slots
        mock_conn_strings = Mock()
        mock_conn_strings.properties = {}
        mock_client_instance.web_apps.list_connection_strings.return_value = (
            mock_conn_strings
        )
        mock_client_instance.web_apps.list_slots.return_value = []

        # Execute discovery
        items = plugin.discover(sample_resource)

        # Verify results
        assert len(items) == 3
        assert all(isinstance(item, DataPlaneItem) for item in items)

        # Check app settings
        app_settings = [item for item in items if item.item_type == "app_setting"]
        assert len(app_settings) == 3

        # Find specific settings
        db_password = next(item for item in app_settings if item.name == "DB_PASSWORD")
        assert db_password.properties["is_sensitive"] is True
        assert db_password.properties["value"] == "secret123"

        db_host = next(item for item in app_settings if item.name == "DB_HOST")
        assert db_host.properties["is_sensitive"] is False
        assert db_host.properties["value"] == "localhost"

    @patch("azure.mgmt.web.WebSiteManagementClient")
    @patch("azure.identity.DefaultAzureCredential")
    def test_discover_connection_strings(
        self, mock_credential, mock_web_client, plugin, sample_resource
    ):
        """Test discovery of connection strings."""
        # Mock credential
        mock_cred_instance = Mock()
        mock_credential.return_value = mock_cred_instance

        # Mock web client
        mock_client_instance = Mock()
        mock_web_client.return_value = mock_client_instance

        # Mock empty app settings
        mock_settings = Mock()
        mock_settings.properties = {}
        mock_client_instance.web_apps.list_application_settings.return_value = (
            mock_settings
        )

        # Mock connection strings response
        mock_conn_info = Mock()
        mock_conn_info.value = "Server=tcp:myserver.database.windows.net;Database=mydb"
        mock_conn_info.type = "SQLAzure"

        mock_conn_strings = Mock()
        mock_conn_strings.properties = {"DefaultConnection": mock_conn_info}
        mock_client_instance.web_apps.list_connection_strings.return_value = (
            mock_conn_strings
        )

        # Mock empty slots
        mock_client_instance.web_apps.list_slots.return_value = []

        # Execute discovery
        items = plugin.discover(sample_resource)

        # Verify results
        assert len(items) == 1
        conn_string = items[0]
        assert conn_string.item_type == "connection_string"
        assert conn_string.name == "DefaultConnection"
        assert conn_string.properties["is_sensitive"] is True
        assert conn_string.properties["type"] == "SQLAzure"
        assert "Server=tcp:" in conn_string.properties["value"]

    @patch("azure.mgmt.web.WebSiteManagementClient")
    @patch("azure.identity.DefaultAzureCredential")
    def test_discover_deployment_slots(
        self, mock_credential, mock_web_client, plugin, sample_resource
    ):
        """Test discovery of deployment slots."""
        # Mock credential
        mock_cred_instance = Mock()
        mock_credential.return_value = mock_cred_instance

        # Mock web client
        mock_client_instance = Mock()
        mock_web_client.return_value = mock_client_instance

        # Mock empty app settings and connection strings
        mock_settings = Mock()
        mock_settings.properties = {}
        mock_client_instance.web_apps.list_application_settings.return_value = (
            mock_settings
        )

        mock_conn_strings = Mock()
        mock_conn_strings.properties = {}
        mock_client_instance.web_apps.list_connection_strings.return_value = (
            mock_conn_strings
        )

        # Mock deployment slot
        mock_slot = Mock()
        mock_slot.name = "my-app/staging"
        mock_slot.state = "Running"
        mock_slot.enabled = True
        mock_slot.default_host_name = "my-app-staging.azurewebsites.net"
        mock_slot.id = "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Web/sites/my-app/slots/staging"

        mock_client_instance.web_apps.list_slots.return_value = [mock_slot]

        # Mock slot settings
        mock_slot_settings = Mock()
        mock_slot_settings.properties = {"SLOT_SETTING": "value1"}
        mock_client_instance.web_apps.list_application_settings_slot.return_value = (
            mock_slot_settings
        )

        mock_slot_conns = Mock()
        mock_slot_conns.properties = {}
        mock_client_instance.web_apps.list_connection_strings_slot.return_value = (
            mock_slot_conns
        )

        # Execute discovery
        items = plugin.discover(sample_resource)

        # Verify results
        assert len(items) >= 2  # Slot + slot setting

        # Check deployment slot
        slots = [item for item in items if item.item_type == "deployment_slot"]
        assert len(slots) == 1
        assert slots[0].name == "staging"
        assert slots[0].properties["state"] == "Running"

        # Check slot app setting
        slot_settings = [item for item in items if item.item_type == "slot_app_setting"]
        assert len(slot_settings) == 1
        assert slot_settings[0].name == "staging/SLOT_SETTING"
        assert slot_settings[0].properties["slot_name"] == "staging"

    def test_discover_invalid_resource(self, plugin):
        """Test discovery with invalid resource."""
        invalid_resource = {
            "id": "invalid-id",
            "type": "Microsoft.Storage/storageAccounts",
            "name": "storage",
        }

        with pytest.raises(ValueError, match="Invalid resource"):
            plugin.discover(invalid_resource)

    def test_generate_replication_code_empty(self, plugin):
        """Test code generation with no items."""
        code = plugin.generate_replication_code([])
        assert "No App Service data plane items to replicate" in code

    def test_generate_replication_code_app_settings(self, plugin):
        """Test code generation for app settings."""
        items = [
            DataPlaneItem(
                name="DB_HOST",
                item_type="app_setting",
                properties={"value": "localhost", "is_sensitive": False},
                source_resource_id="/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Web/sites/my-app",
                metadata={},
            ),
            DataPlaneItem(
                name="DB_PASSWORD",
                item_type="app_setting",
                properties={"value": "secret123", "is_sensitive": True},
                source_resource_id="/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Web/sites/my-app",
                metadata={},
            ),
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Verify code contains expected elements
        assert "App Settings" in code
        assert "DB_HOST" in code
        assert "DB_PASSWORD" in code
        assert "var.app_setting_db_password" in code
        assert "localhost" in code  # Non-sensitive value included
        assert "secret123" not in code  # Sensitive value not included
        assert 'variable "app_setting_db_password"' in code
        assert "sensitive   = true" in code

    def test_generate_replication_code_connection_strings(self, plugin):
        """Test code generation for connection strings."""
        items = [
            DataPlaneItem(
                name="DefaultConnection",
                item_type="connection_string",
                properties={
                    "value": "Server=myserver;Database=mydb",
                    "type": "SQLAzure",
                    "is_sensitive": True,
                },
                source_resource_id="/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Web/sites/my-app",
                metadata={},
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Verify code contains expected elements
        assert "Connection Strings" in code
        assert "DefaultConnection" in code
        assert "SQLAzure" in code
        assert "var.connection_string_defaultconnection" in code
        assert 'variable "connection_string_defaultconnection"' in code
        assert "Server=myserver" not in code  # Value not included

    def test_generate_replication_code_deployment_slots(self, plugin):
        """Test code generation for deployment slots."""
        items = [
            DataPlaneItem(
                name="staging",
                item_type="deployment_slot",
                properties={
                    "state": "Running",
                    "enabled": True,
                    "default_host_name": "my-app-staging.azurewebsites.net",
                },
                source_resource_id="/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Web/sites/my-app",
                metadata={},
            ),
            DataPlaneItem(
                name="staging/SLOT_SETTING",
                item_type="slot_app_setting",
                properties={
                    "value": "slot-value",
                    "is_sensitive": False,
                    "slot_name": "staging",
                },
                source_resource_id="/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Web/sites/my-app",
                metadata={},
            ),
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Verify code contains expected elements
        assert "Deployment Slots" in code
        assert "azurerm_app_service_slot" in code
        assert "staging" in code
        assert "SLOT_SETTING" in code
        assert "app_settings = {" in code
        assert "slot-value" in code

    def test_generate_replication_code_unsupported_format(self, plugin):
        """Test code generation with unsupported format."""
        items = [
            DataPlaneItem(
                name="test",
                item_type="app_setting",
                properties={"value": "test"},
                source_resource_id="/test",
                metadata={},
            )
        ]

        with pytest.raises(ValueError, match="not supported"):
            plugin.generate_replication_code(items, "bicep")

    def test_get_required_permissions_template_mode(self, plugin):
        """Test permission requirements for template mode."""
        perms = plugin.get_required_permissions(ReplicationMode.TEMPLATE)

        assert len(perms) == 1
        assert "Microsoft.Web/sites/read" in perms[0].actions
        assert "Microsoft.Web/sites/config/read" in perms[0].actions
        assert "Microsoft.Web/sites/config/write" not in perms[0].actions

    def test_get_required_permissions_replication_mode(self, plugin):
        """Test permission requirements for replication mode."""
        perms = plugin.get_required_permissions(ReplicationMode.REPLICATION)

        assert len(perms) == 1
        assert "Microsoft.Web/sites/read" in perms[0].actions
        assert "Microsoft.Web/sites/config/read" in perms[0].actions
        assert "Microsoft.Web/sites/config/write" in perms[0].actions
        assert "Microsoft.Web/sites/slots/config/write" in perms[0].actions

    @patch("azure.mgmt.web.WebSiteManagementClient")
    @patch("azure.identity.DefaultAzureCredential")
    def test_discover_with_mode_template(
        self, mock_credential, mock_web_client, plugin, sample_resource
    ):
        """Test mode-aware discovery in template mode."""
        # Mock credential
        mock_cred_instance = Mock()
        mock_credential.return_value = mock_cred_instance

        # Mock web client
        mock_client_instance = Mock()
        mock_web_client.return_value = mock_client_instance

        # Mock app settings response
        mock_settings = Mock()
        mock_settings.properties = {"DB_PASSWORD": "secret123", "DB_HOST": "localhost"}
        mock_client_instance.web_apps.list_application_settings.return_value = (
            mock_settings
        )

        # Mock empty connection strings and slots
        mock_conn_strings = Mock()
        mock_conn_strings.properties = {}
        mock_client_instance.web_apps.list_connection_strings.return_value = (
            mock_conn_strings
        )
        mock_client_instance.web_apps.list_slots.return_value = []

        # Execute discovery in template mode
        items = plugin.discover_with_mode(sample_resource, ReplicationMode.TEMPLATE)

        # Verify sensitive values are masked
        db_password = next(item for item in items if item.name == "DB_PASSWORD")
        assert db_password.properties["value"] == "PLACEHOLDER-SET-MANUALLY"

        # Non-sensitive values should be preserved
        db_host = next(item for item in items if item.name == "DB_HOST")
        assert db_host.properties["value"] == "localhost"

    @patch("azure.mgmt.web.WebSiteManagementClient")
    @patch("azure.identity.DefaultAzureCredential")
    def test_discover_with_mode_replication(
        self, mock_credential, mock_web_client, plugin, sample_resource
    ):
        """Test mode-aware discovery in replication mode."""
        # Mock credential
        mock_cred_instance = Mock()
        mock_credential.return_value = mock_cred_instance

        # Mock web client
        mock_client_instance = Mock()
        mock_web_client.return_value = mock_client_instance

        # Mock app settings response
        mock_settings = Mock()
        mock_settings.properties = {"DB_PASSWORD": "secret123"}
        mock_client_instance.web_apps.list_application_settings.return_value = (
            mock_settings
        )

        # Mock empty connection strings and slots
        mock_conn_strings = Mock()
        mock_conn_strings.properties = {}
        mock_client_instance.web_apps.list_connection_strings.return_value = (
            mock_conn_strings
        )
        mock_client_instance.web_apps.list_slots.return_value = []

        # Execute discovery in replication mode
        items = plugin.discover_with_mode(sample_resource, ReplicationMode.REPLICATION)

        # Verify actual values are preserved
        db_password = items[0]
        assert db_password.properties["value"] == "secret123"

    @patch("azure.mgmt.web.WebSiteManagementClient")
    @patch("azure.identity.DefaultAzureCredential")
    def test_replicate_with_mode_template(
        self, mock_credential, mock_web_client, plugin, sample_resource
    ):
        """Test mode-aware replication in template mode."""
        # Mock credential
        mock_cred_instance = Mock()
        mock_credential.return_value = mock_cred_instance

        # Mock web client
        mock_client_instance = Mock()
        mock_web_client.return_value = mock_client_instance

        # Mock discovery
        mock_settings = Mock()
        mock_settings.properties = {"SETTING1": "value1"}
        mock_client_instance.web_apps.list_application_settings.return_value = (
            mock_settings
        )

        mock_conn_strings = Mock()
        mock_conn_strings.properties = {}
        mock_client_instance.web_apps.list_connection_strings.return_value = (
            mock_conn_strings
        )
        mock_client_instance.web_apps.list_slots.return_value = []

        # Mock update methods
        mock_client_instance.web_apps.update_application_settings.return_value = None
        mock_client_instance.web_apps.update_connection_strings.return_value = None

        # Create target resource
        target_resource = sample_resource.copy()
        target_resource["name"] = "target-app"
        target_resource["id"] = target_resource["id"].replace("my-app", "target-app")

        # Execute replication in template mode
        result = plugin.replicate_with_mode(
            sample_resource, target_resource, ReplicationMode.TEMPLATE
        )

        # Verify result
        assert isinstance(result, ReplicationResult)
        assert result.success is True
        assert result.items_discovered > 0
        assert result.items_replicated > 0
        assert "placeholder" in " ".join(result.warnings).lower()

        # Verify placeholder values were used
        call_args = mock_client_instance.web_apps.update_application_settings.call_args
        settings_dict = call_args[1]["app_settings"].properties
        assert settings_dict["SETTING1"] == "PLACEHOLDER-SET-MANUALLY"

    @patch("azure.mgmt.web.WebSiteManagementClient")
    @patch("azure.identity.DefaultAzureCredential")
    def test_replicate_with_mode_full(
        self, mock_credential, mock_web_client, plugin, sample_resource
    ):
        """Test mode-aware replication in full replication mode."""
        # Mock credential
        mock_cred_instance = Mock()
        mock_credential.return_value = mock_cred_instance

        # Mock web client
        mock_client_instance = Mock()
        mock_web_client.return_value = mock_client_instance

        # Mock discovery
        mock_settings = Mock()
        mock_settings.properties = {"SETTING1": "value1"}
        mock_client_instance.web_apps.list_application_settings.return_value = (
            mock_settings
        )

        mock_conn_strings = Mock()
        mock_conn_strings.properties = {}
        mock_client_instance.web_apps.list_connection_strings.return_value = (
            mock_conn_strings
        )
        mock_client_instance.web_apps.list_slots.return_value = []

        # Mock update methods
        mock_client_instance.web_apps.update_application_settings.return_value = None
        mock_client_instance.web_apps.update_connection_strings.return_value = None

        # Create target resource
        target_resource = sample_resource.copy()
        target_resource["name"] = "target-app"
        target_resource["id"] = target_resource["id"].replace("my-app", "target-app")

        # Execute replication in full mode
        result = plugin.replicate_with_mode(
            sample_resource, target_resource, ReplicationMode.REPLICATION
        )

        # Verify result
        assert isinstance(result, ReplicationResult)
        assert result.success is True
        assert result.items_discovered > 0
        assert result.items_replicated > 0

        # Verify actual values were used
        call_args = mock_client_instance.web_apps.update_application_settings.call_args
        settings_dict = call_args[1]["app_settings"].properties
        assert settings_dict["SETTING1"] == "value1"

    def test_replicate_invalid_source(self, plugin, sample_resource):
        """Test replication with invalid source resource."""
        invalid_resource = {
            "id": "invalid",
            "type": "Microsoft.Storage/storageAccounts",
            "name": "storage",
        }

        with pytest.raises(ValueError, match="Invalid source resource"):
            plugin.replicate_with_mode(
                invalid_resource, sample_resource, ReplicationMode.TEMPLATE
            )

    def test_replicate_invalid_target(self, plugin, sample_resource):
        """Test replication with invalid target resource."""
        invalid_resource = {
            "id": "invalid",
            "type": "Microsoft.Storage/storageAccounts",
            "name": "storage",
        }

        with pytest.raises(ValueError, match="Invalid target resource"):
            plugin.replicate_with_mode(
                sample_resource, invalid_resource, ReplicationMode.TEMPLATE
            )

    def test_supports_mode(self, plugin):
        """Test that plugin supports both modes."""
        assert plugin.supports_mode(ReplicationMode.TEMPLATE) is True
        assert plugin.supports_mode(ReplicationMode.REPLICATION) is True

    def test_estimate_operation_time_template(self, plugin):
        """Test operation time estimation for template mode."""
        items = [Mock() for _ in range(10)]
        time_estimate = plugin.estimate_operation_time(items, ReplicationMode.TEMPLATE)
        assert time_estimate == 0.0

    def test_estimate_operation_time_replication(self, plugin):
        """Test operation time estimation for replication mode."""
        items = [Mock() for _ in range(10)]
        time_estimate = plugin.estimate_operation_time(
            items, ReplicationMode.REPLICATION
        )
        assert time_estimate > 0.0
        assert time_estimate == 10 * 0.1  # Default 100ms per item

    def test_progress_reporter_integration(self, sample_resource):
        """Test integration with progress reporter."""
        # Create mock progress reporter
        mock_reporter = Mock()
        mock_reporter.report_discovery = Mock()
        mock_reporter.report_replication_progress = Mock()
        mock_reporter.report_completion = Mock()

        # Create plugin with progress reporter
        plugin = AppServicePlugin(progress_reporter=mock_reporter)

        # This test just verifies the plugin accepts the reporter
        # Actual progress reporting is tested in integration tests
        assert plugin.progress_reporter == mock_reporter

    def test_credential_provider_integration(self, sample_resource):
        """Test integration with credential provider."""
        # Create mock credential provider
        mock_cred_provider = Mock()
        mock_cred_provider.get_credential = Mock(return_value=Mock())

        # Create plugin with credential provider
        plugin = AppServicePlugin(credential_provider=mock_cred_provider)

        # Verify plugin accepts the provider
        assert plugin.credential_provider == mock_cred_provider

    def test_supports_output_format(self, plugin):
        """Test output format support."""
        assert plugin.supports_output_format("terraform") is True
        assert plugin.supports_output_format("Terraform") is True
        assert plugin.supports_output_format("TERRAFORM") is True
        assert plugin.supports_output_format("bicep") is False
        assert plugin.supports_output_format("arm") is False
