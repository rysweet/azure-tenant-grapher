"""
Integration tests for AppServicePlugin.

These tests require real Azure resources and credentials.
They are marked with @pytest.mark.integration and skipped by default.

To run: pytest tests/iac/plugins/test_appservice_plugin_integration.py -m integration
"""

import os

import pytest

from src.iac.plugins.appservice_plugin import AppServicePlugin
from src.iac.plugins.base_plugin import ReplicationMode
from src.iac.plugins.credential_manager import CredentialConfig, CredentialManager


@pytest.mark.integration
@pytest.mark.azure
class TestAppServicePluginIntegration:
    """Integration tests for AppServicePlugin with real Azure resources."""

    @pytest.fixture(scope="class")
    def credentials(self):
        """Get Azure credentials for testing."""
        # Check if running in CI or local dev
        if all(
            os.getenv(var)
            for var in ["AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "AZURE_TENANT_ID"]
        ):
            config = CredentialConfig(
                client_id=os.getenv("AZURE_CLIENT_ID"),
                client_secret=os.getenv("AZURE_CLIENT_SECRET"),
                tenant_id=os.getenv("AZURE_TENANT_ID"),
            )
            return CredentialManager(config)
        else:
            # Use default credential chain
            return CredentialManager()

    @pytest.fixture(scope="class")
    def plugin(self, credentials):
        """Create plugin with credentials."""
        return AppServicePlugin(credential_provider=credentials)

    @pytest.fixture(scope="class")
    def test_app_service(self):
        """
        Provide test App Service resource.

        Note: This requires a real App Service to exist in your test subscription.
        Set the AZURE_TEST_APP_SERVICE_ID environment variable to use a specific resource.
        """
        app_service_id = os.getenv("AZURE_TEST_APP_SERVICE_ID")

        if not app_service_id:
            pytest.skip(
                "AZURE_TEST_APP_SERVICE_ID not set - skipping integration tests"
            )

        # Parse resource ID to build resource dict
        parts = app_service_id.split("/")
        if len(parts) < 9:
            pytest.skip(f"Invalid AZURE_TEST_APP_SERVICE_ID format: {app_service_id}")

        return {
            "id": app_service_id,
            "type": "Microsoft.Web/sites",
            "name": parts[8],
            "properties": {},
        }

    @pytest.mark.skipif(
        not os.getenv("AZURE_TEST_APP_SERVICE_ID"),
        reason="AZURE_TEST_APP_SERVICE_ID not set",
    )
    def test_discover_real_app_service(self, plugin, test_app_service):
        """Test discovery against real Azure App Service."""
        # Execute discovery
        items = plugin.discover(test_app_service)

        # Verify we got some items
        assert len(items) > 0, "Expected to discover at least some configuration items"

        # Verify item structure
        for item in items:
            assert item.name, "Item should have a name"
            assert item.item_type in [
                "app_setting",
                "connection_string",
                "deployment_slot",
                "slot_app_setting",
                "slot_connection_string",
            ], f"Unexpected item type: {item.item_type}"
            assert item.source_resource_id == test_app_service["id"]

        # Log what we found
        print(f"\nDiscovered {len(items)} items:")
        for item_type in ["app_setting", "connection_string", "deployment_slot"]:
            count = len([i for i in items if i.item_type == item_type])
            if count > 0:
                print(f"  {item_type}: {count}")

    @pytest.mark.skipif(
        not os.getenv("AZURE_TEST_APP_SERVICE_ID"),
        reason="AZURE_TEST_APP_SERVICE_ID not set",
    )
    def test_discover_with_template_mode(self, plugin, test_app_service):
        """Test mode-aware discovery in template mode."""
        # Execute discovery in template mode
        items = plugin.discover_with_mode(test_app_service, ReplicationMode.TEMPLATE)

        # Verify sensitive values are masked
        sensitive_items = [
            item for item in items if item.properties.get("is_sensitive")
        ]

        for item in sensitive_items:
            assert item.properties["value"] == "PLACEHOLDER-SET-MANUALLY", (
                f"Sensitive item {item.name} should have placeholder value in template mode"
            )

    @pytest.mark.skipif(
        not os.getenv("AZURE_TEST_APP_SERVICE_ID"),
        reason="AZURE_TEST_APP_SERVICE_ID not set",
    )
    def test_generate_terraform_code(self, plugin, test_app_service):
        """Test Terraform code generation with real data."""
        # Discover items
        items = plugin.discover(test_app_service)

        # Generate code
        code = plugin.generate_replication_code(items, "terraform")

        # Verify code structure
        assert "App Service Data Plane Items" in code
        assert len(code) > 100, "Generated code should be substantial"

        # Verify security note
        assert "SECURITY NOTE" in code or "Security note" in code.lower()

        # If there are app settings, verify they're in the code
        app_settings = [i for i in items if i.item_type == "app_setting"]
        if app_settings:
            assert "App Settings" in code or "app_settings" in code

        # If there are connection strings, verify they're in the code
        conn_strings = [i for i in items if i.item_type == "connection_string"]
        if conn_strings:
            assert "Connection String" in code or "connection_string" in code

        print(f"\nGenerated {len(code.splitlines())} lines of Terraform code")

    @pytest.mark.skipif(
        not os.getenv("AZURE_TEST_APP_SERVICE_ID")
        or not os.getenv("AZURE_TEST_TARGET_APP_SERVICE_ID"),
        reason="Both AZURE_TEST_APP_SERVICE_ID and AZURE_TEST_TARGET_APP_SERVICE_ID must be set",
    )
    def test_replicate_template_mode(self, plugin, test_app_service):
        """
        Test template mode replication to a target App Service.

        WARNING: This test modifies the target App Service configuration.
        Use a dedicated test App Service for this.
        """
        target_id = os.getenv("AZURE_TEST_TARGET_APP_SERVICE_ID")
        parts = target_id.split("/")

        target_resource = {
            "id": target_id,
            "type": "Microsoft.Web/sites",
            "name": parts[8],
            "properties": {},
        }

        # Execute replication in template mode
        result = plugin.replicate_with_mode(
            test_app_service, target_resource, ReplicationMode.TEMPLATE
        )

        # Verify result
        assert result.success, f"Replication failed: {result.errors}"
        assert result.items_discovered > 0
        assert result.items_replicated >= 0
        assert result.duration_seconds > 0

        # Verify warnings about placeholders
        assert any("placeholder" in w.lower() for w in result.warnings)

        print("\nTemplate mode replication:")
        print(f"  Discovered: {result.items_discovered}")
        print(f"  Replicated: {result.items_replicated}")
        print(f"  Skipped: {result.items_skipped}")
        print(f"  Duration: {result.duration_seconds:.2f}s")
