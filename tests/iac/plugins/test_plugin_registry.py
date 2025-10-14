"""
Unit tests for plugin registry and discovery system.

Tests cover:
- Plugin registration and retrieval
- Plugin discovery for resource types
- Registry initialization and reset
"""

import pytest

from src.iac.plugins import PluginRegistry
from src.iac.plugins.base_plugin import (
    DataPlanePlugin,
    ReplicationResult,
)


class TestPlugin(DataPlanePlugin):
    """Test plugin for registry testing."""

    @property
    def supported_resource_type(self) -> str:
        return "Microsoft.Test/resources"

    def discover(self, resource: dict) -> list:
        return []

    def generate_replication_code(
        self, items: list, output_format: str = "terraform"
    ) -> str:
        return "# Test code"

    def replicate(
        self, source_resource: dict, target_resource: dict
    ) -> ReplicationResult:
        return ReplicationResult(
            success=True, items_discovered=0, items_replicated=0, errors=[], warnings=[]
        )


class AnotherTestPlugin(DataPlanePlugin):
    """Another test plugin for testing multiple registrations."""

    @property
    def supported_resource_type(self) -> str:
        return "Microsoft.Other/resources"

    def discover(self, resource: dict) -> list:
        return []

    def generate_replication_code(
        self, items: list, output_format: str = "terraform"
    ) -> str:
        return "# Other code"

    def replicate(
        self, source_resource: dict, target_resource: dict
    ) -> ReplicationResult:
        return ReplicationResult(
            success=True, items_discovered=0, items_replicated=0, errors=[], warnings=[]
        )


class TestPluginRegistry:
    """Test cases for PluginRegistry."""

    def setup_method(self):
        """Reset registry before each test."""
        PluginRegistry.reset()

    def teardown_method(self):
        """Clean up registry after each test."""
        PluginRegistry.reset()

    def test_register_plugin(self):
        """Test registering a plugin."""
        plugin = TestPlugin()
        PluginRegistry.register_plugin(plugin)

        registered = PluginRegistry.get_plugin("Microsoft.Test/resources")
        assert registered is not None
        assert registered.supported_resource_type == "Microsoft.Test/resources"

    def test_register_multiple_plugins(self):
        """Test registering multiple plugins."""
        plugin1 = TestPlugin()
        plugin2 = AnotherTestPlugin()

        PluginRegistry.register_plugin(plugin1)
        PluginRegistry.register_plugin(plugin2)

        assert PluginRegistry.get_plugin("Microsoft.Test/resources") is not None
        assert PluginRegistry.get_plugin("Microsoft.Other/resources") is not None

    def test_get_plugin_for_registered_type(self):
        """Test retrieving plugin by resource type."""
        plugin = TestPlugin()
        PluginRegistry.register_plugin(plugin)

        retrieved = PluginRegistry.get_plugin("Microsoft.Test/resources")
        assert retrieved is plugin

    def test_get_plugin_for_unregistered_type_returns_none(self):
        """Test retrieving plugin for unregistered type returns None."""
        plugin = PluginRegistry.get_plugin("Microsoft.Unregistered/resources")
        assert plugin is None

    def test_get_plugin_for_resource(self):
        """Test retrieving plugin by resource dictionary."""
        plugin = TestPlugin()
        PluginRegistry.register_plugin(plugin)

        resource = {
            "id": "/subscriptions/123",
            "type": "Microsoft.Test/resources",
            "name": "test",
        }

        retrieved = PluginRegistry.get_plugin_for_resource(resource)
        assert retrieved is not None
        assert retrieved.supported_resource_type == "Microsoft.Test/resources"

    def test_get_plugin_for_resource_missing_type(self):
        """Test get_plugin_for_resource with missing type field."""
        resource = {
            "id": "/subscriptions/123",
            "name": "test",
            # Missing 'type'
        }

        retrieved = PluginRegistry.get_plugin_for_resource(resource)
        assert retrieved is None

    def test_get_plugin_for_resource_empty_type(self):
        """Test get_plugin_for_resource with empty type field."""
        resource = {
            "id": "/subscriptions/123",
            "type": "",
            "name": "test",
        }

        retrieved = PluginRegistry.get_plugin_for_resource(resource)
        assert retrieved is None

    def test_has_plugin_returns_true_for_registered(self):
        """Test has_plugin returns True for registered type."""
        plugin = TestPlugin()
        PluginRegistry.register_plugin(plugin)

        assert PluginRegistry.has_plugin("Microsoft.Test/resources") is True

    def test_has_plugin_returns_false_for_unregistered(self):
        """Test has_plugin returns False for unregistered type."""
        assert PluginRegistry.has_plugin("Microsoft.Unregistered/resources") is False

    def test_list_supported_types(self):
        """Test listing all supported resource types."""
        # Manually register test plugins without triggering auto-discovery
        plugin1 = TestPlugin()
        plugin2 = AnotherTestPlugin()

        PluginRegistry.register_plugin(plugin1)
        PluginRegistry.register_plugin(plugin2)
        PluginRegistry._initialized = (
            True  # Mark as initialized to prevent auto-discovery
        )

        types = PluginRegistry.list_supported_types()

        assert "Microsoft.Test/resources" in types
        assert "Microsoft.Other/resources" in types
        assert len(types) == 2

    def test_list_supported_types_empty_registry(self):
        """Test listing types from empty registry."""
        types = PluginRegistry.list_supported_types()
        assert isinstance(types, list)
        # May be empty or have auto-discovered plugins

    def test_reset_clears_registry(self):
        """Test reset clears all registered plugins."""
        plugin = TestPlugin()
        PluginRegistry.register_plugin(plugin)

        assert PluginRegistry.has_plugin("Microsoft.Test/resources") is True

        PluginRegistry.reset()

        # Registry should be cleared and not initialized
        assert not PluginRegistry._initialized
        # After reset, discovery may re-populate
        types = PluginRegistry.list_supported_types()
        # Test plugin should not be present (only auto-discovered ones)
        if "Microsoft.Test/resources" in types:
            # This would mean the test plugin is auto-discovered
            pytest.fail("Test plugin should not be auto-discovered")

    def test_overwrite_existing_plugin_logs_warning(self, caplog):
        """Test overwriting existing plugin logs warning."""
        plugin1 = TestPlugin()
        plugin2 = TestPlugin()

        PluginRegistry.register_plugin(plugin1)
        PluginRegistry.register_plugin(plugin2)  # Overwrite

        # Should have logged a warning
        assert "Overwriting existing plugin" in caplog.text


class TestPluginDiscovery:
    """Test plugin auto-discovery functionality."""

    def setup_method(self):
        """Reset registry before each test."""
        PluginRegistry.reset()

    def teardown_method(self):
        """Clean up registry after each test."""
        PluginRegistry.reset()

    def test_discover_plugins_initializes_registry(self):
        """Test discover_plugins initializes the registry."""
        assert not PluginRegistry._initialized

        PluginRegistry.discover_plugins()

        assert PluginRegistry._initialized

    def test_discover_plugins_registers_keyvault_plugin(self):
        """Test that KeyVaultPlugin is auto-discovered."""
        PluginRegistry.discover_plugins()

        # KeyVaultPlugin should be registered
        plugin = PluginRegistry.get_plugin("Microsoft.KeyVault/vaults")
        assert plugin is not None
        assert plugin.plugin_name == "KeyVaultPlugin"

    def test_discover_plugins_idempotent(self):
        """Test discover_plugins can be called multiple times safely."""
        PluginRegistry.discover_plugins()
        count1 = len(PluginRegistry.list_supported_types())

        PluginRegistry.discover_plugins()
        count2 = len(PluginRegistry.list_supported_types())

        # Should have same number of plugins (idempotent)
        assert count1 == count2

    def test_get_plugin_auto_discovers(self):
        """Test that get_plugin triggers auto-discovery."""
        assert not PluginRegistry._initialized

        # Getting a plugin should trigger discovery
        plugin = PluginRegistry.get_plugin("Microsoft.KeyVault/vaults")

        assert PluginRegistry._initialized
        assert plugin is not None

    def test_has_plugin_auto_discovers(self):
        """Test that has_plugin triggers auto-discovery."""
        assert not PluginRegistry._initialized

        # Checking for plugin should trigger discovery
        has_kv = PluginRegistry.has_plugin("Microsoft.KeyVault/vaults")

        assert PluginRegistry._initialized
        assert has_kv is True

    def test_list_supported_types_auto_discovers(self):
        """Test that list_supported_types triggers auto-discovery."""
        assert not PluginRegistry._initialized

        # Listing types should trigger discovery
        types = PluginRegistry.list_supported_types()

        assert PluginRegistry._initialized
        assert "Microsoft.KeyVault/vaults" in types


class TestPluginRegistryEdgeCases:
    """Test edge cases for plugin registry."""

    def setup_method(self):
        """Reset registry before each test."""
        PluginRegistry.reset()

    def teardown_method(self):
        """Clean up registry after each test."""
        PluginRegistry.reset()

    def test_register_plugin_without_resource_type_raises_error(self):
        """Test registering plugin with no resource type raises error."""

        class BadPlugin(DataPlanePlugin):
            @property
            def supported_resource_type(self) -> str:
                return ""  # Empty resource type

            def discover(self, resource: dict) -> list:
                return []

            def generate_replication_code(
                self, items: list, output_format: str = "terraform"
            ) -> str:
                return ""

            def replicate(
                self, source_resource: dict, target_resource: dict
            ) -> ReplicationResult:
                return ReplicationResult(
                    success=False,
                    items_discovered=0,
                    items_replicated=0,
                    errors=[],
                    warnings=[],
                )

        plugin = BadPlugin()

        with pytest.raises(ValueError, match="no supported_resource_type"):
            PluginRegistry.register_plugin(plugin)

    def test_get_plugin_for_resource_with_none_resource(self):
        """Test get_plugin_for_resource with None resource."""
        result = PluginRegistry.get_plugin_for_resource(None)
        assert result is None

    def test_get_plugin_for_resource_with_empty_dict(self):
        """Test get_plugin_for_resource with empty resource dict."""
        result = PluginRegistry.get_plugin_for_resource({})
        assert result is None

    def test_register_same_plugin_instance_twice(self):
        """Test registering same plugin instance twice."""
        plugin = TestPlugin()

        PluginRegistry.register_plugin(plugin)
        PluginRegistry.register_plugin(plugin)

        # Should not cause errors, just overwrite
        retrieved = PluginRegistry.get_plugin("Microsoft.Test/resources")
        assert retrieved is plugin

    def test_registry_state_persists_across_calls(self):
        """Test that registry state persists across multiple calls."""
        plugin = TestPlugin()
        PluginRegistry.register_plugin(plugin)

        # Multiple gets should return same plugin
        p1 = PluginRegistry.get_plugin("Microsoft.Test/resources")
        p2 = PluginRegistry.get_plugin("Microsoft.Test/resources")

        assert p1 is p2
        assert p1 is plugin
