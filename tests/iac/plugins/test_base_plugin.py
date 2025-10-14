"""
Unit tests for base data plane plugin infrastructure.

Tests cover:
- DataPlanePlugin abstract base class
- DataPlaneItem and ReplicationResult dataclasses
- Plugin validation and interface contracts
"""

import pytest

from src.iac.plugins.base_plugin import (
    DataPlaneItem,
    DataPlanePlugin,
    ReplicationResult,
)


class ConcretePlugin(DataPlanePlugin):
    """Concrete implementation for testing base plugin functionality."""

    @property
    def supported_resource_type(self) -> str:
        return "Microsoft.Test/resources"

    def discover(self, resource: dict) -> list:
        if not self.validate_resource(resource):
            raise ValueError("Invalid resource")
        return [
            DataPlaneItem(
                name="test-item",
                item_type="test",
                properties={"key": "value"},
                source_resource_id=resource["id"],
            )
        ]

    def generate_replication_code(
        self, items: list, output_format: str = "terraform"
    ) -> str:
        if not self.supports_output_format(output_format):
            raise ValueError(f"Unsupported format: {output_format}")
        return f"# Generated code for {len(items)} items"

    def replicate(
        self, source_resource: dict, target_resource: dict
    ) -> ReplicationResult:
        return ReplicationResult(
            success=True,
            items_discovered=1,
            items_replicated=1,
            errors=[],
            warnings=[],
        )


class TestDataPlaneItem:
    """Test cases for DataPlaneItem dataclass."""

    def test_create_data_plane_item(self):
        """Test creating a DataPlaneItem with all fields."""
        item = DataPlaneItem(
            name="my-secret",
            item_type="secret",
            properties={"enabled": True, "content_type": "text/plain"},
            source_resource_id="/subscriptions/123/resourceGroups/rg/providers/Microsoft.KeyVault/vaults/kv",
            metadata={"created": "2024-01-01"},
        )

        assert item.name == "my-secret"
        assert item.item_type == "secret"
        assert item.properties["enabled"] is True
        assert item.source_resource_id.endswith("/vaults/kv")
        assert item.metadata["created"] == "2024-01-01"

    def test_create_data_plane_item_without_metadata(self):
        """Test creating a DataPlaneItem without optional metadata."""
        item = DataPlaneItem(
            name="my-key",
            item_type="key",
            properties={},
            source_resource_id="/subscriptions/123",
        )

        assert item.name == "my-key"
        assert item.metadata is None


class TestReplicationResult:
    """Test cases for ReplicationResult dataclass."""

    def test_successful_replication_result(self):
        """Test creating a successful ReplicationResult."""
        result = ReplicationResult(
            success=True,
            items_discovered=10,
            items_replicated=10,
            errors=[],
            warnings=[],
        )

        assert result.success is True
        assert result.items_discovered == 10
        assert result.items_replicated == 10
        assert len(result.errors) == 0
        assert len(result.warnings) == 0

    def test_failed_replication_result_with_errors(self):
        """Test creating a failed ReplicationResult with errors."""
        result = ReplicationResult(
            success=False,
            items_discovered=10,
            items_replicated=5,
            errors=["Permission denied", "Network timeout"],
            warnings=["Slow connection"],
        )

        assert result.success is False
        assert result.items_discovered == 10
        assert result.items_replicated == 5
        assert len(result.errors) == 2
        assert "Permission denied" in result.errors
        assert len(result.warnings) == 1


class TestDataPlanePlugin:
    """Test cases for DataPlanePlugin base class."""

    def test_cannot_instantiate_abstract_class(self):
        """Test that DataPlanePlugin cannot be instantiated directly."""
        with pytest.raises(TypeError):
            DataPlanePlugin()

    def test_concrete_plugin_instantiation(self):
        """Test that concrete plugin can be instantiated."""
        plugin = ConcretePlugin()
        assert plugin is not None
        assert plugin.plugin_name == "ConcretePlugin"
        assert plugin.supported_resource_type == "Microsoft.Test/resources"

    def test_plugin_name_property(self):
        """Test that plugin_name is derived from class name."""
        plugin = ConcretePlugin()
        assert plugin.plugin_name == "ConcretePlugin"

    def test_validate_resource_success(self):
        """Test successful resource validation."""
        plugin = ConcretePlugin()
        resource = {
            "id": "/subscriptions/123/resourceGroups/rg/providers/Microsoft.Test/resources/test",
            "type": "Microsoft.Test/resources",
            "name": "test-resource",
        }

        assert plugin.validate_resource(resource) is True

    def test_validate_resource_wrong_type(self):
        """Test validation fails for wrong resource type."""
        plugin = ConcretePlugin()
        resource = {
            "id": "/subscriptions/123",
            "type": "Microsoft.Other/resources",  # Wrong type
            "name": "test",
        }

        assert plugin.validate_resource(resource) is False

    def test_validate_resource_missing_id(self):
        """Test validation fails for missing resource ID."""
        plugin = ConcretePlugin()
        resource = {
            "type": "Microsoft.Test/resources",
            "name": "test",
            # Missing 'id'
        }

        assert plugin.validate_resource(resource) is False

    def test_validate_resource_none(self):
        """Test validation fails for None resource."""
        plugin = ConcretePlugin()
        assert plugin.validate_resource(None) is False

    def test_validate_resource_empty_dict(self):
        """Test validation fails for empty resource dict."""
        plugin = ConcretePlugin()
        assert plugin.validate_resource({}) is False

    def test_supports_output_format_terraform(self):
        """Test that default implementation supports Terraform."""
        plugin = ConcretePlugin()
        assert plugin.supports_output_format("terraform") is True
        assert plugin.supports_output_format("TERRAFORM") is True

    def test_supports_output_format_unsupported(self):
        """Test that default implementation doesn't support other formats."""
        plugin = ConcretePlugin()
        assert plugin.supports_output_format("bicep") is False
        assert plugin.supports_output_format("arm") is False

    def test_discover_with_valid_resource(self):
        """Test discover method with valid resource."""
        plugin = ConcretePlugin()
        resource = {
            "id": "/subscriptions/123",
            "type": "Microsoft.Test/resources",
            "name": "test",
        }

        items = plugin.discover(resource)

        assert len(items) == 1
        assert items[0].name == "test-item"
        assert items[0].item_type == "test"
        assert items[0].source_resource_id == resource["id"]

    def test_discover_with_invalid_resource_raises_error(self):
        """Test discover raises ValueError for invalid resource."""
        plugin = ConcretePlugin()
        invalid_resource = {"type": "Microsoft.Other/resources"}  # Wrong type, no ID

        with pytest.raises(ValueError, match="Invalid resource"):
            plugin.discover(invalid_resource)

    def test_generate_replication_code_terraform(self):
        """Test code generation for Terraform format."""
        plugin = ConcretePlugin()
        items = [
            DataPlaneItem(
                name="item1",
                item_type="test",
                properties={},
                source_resource_id="/sub/123",
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        assert "# Generated code for 1 items" in code

    def test_generate_replication_code_unsupported_format(self):
        """Test code generation raises error for unsupported format."""
        plugin = ConcretePlugin()
        items = [
            DataPlaneItem(
                name="item1",
                item_type="test",
                properties={},
                source_resource_id="/sub/123",
            )
        ]

        with pytest.raises(ValueError, match="Unsupported format: bicep"):
            plugin.generate_replication_code(items, "bicep")

    def test_replicate_returns_result(self):
        """Test replicate method returns ReplicationResult."""
        plugin = ConcretePlugin()
        source = {
            "id": "/subscriptions/123/source",
            "type": "Microsoft.Test/resources",
            "name": "source",
        }
        target = {
            "id": "/subscriptions/123/target",
            "type": "Microsoft.Test/resources",
            "name": "target",
        }

        result = plugin.replicate(source, target)

        assert isinstance(result, ReplicationResult)
        assert result.success is True
        assert result.items_discovered == 1
        assert result.items_replicated == 1


class TestDataPlanePluginEdgeCases:
    """Test edge cases and boundary conditions for base plugin."""

    def test_plugin_with_empty_properties(self):
        """Test DataPlaneItem with empty properties dict."""
        item = DataPlaneItem(
            name="empty",
            item_type="test",
            properties={},
            source_resource_id="/sub/123",
        )

        assert item.properties == {}

    def test_plugin_with_complex_properties(self):
        """Test DataPlaneItem with nested properties."""
        item = DataPlaneItem(
            name="complex",
            item_type="test",
            properties={
                "nested": {"key": "value"},
                "list": [1, 2, 3],
                "enabled": True,
            },
            source_resource_id="/sub/123",
        )

        assert item.properties["nested"]["key"] == "value"
        assert len(item.properties["list"]) == 3
        assert item.properties["enabled"] is True

    def test_replication_result_with_many_errors(self):
        """Test ReplicationResult with multiple errors and warnings."""
        result = ReplicationResult(
            success=False,
            items_discovered=100,
            items_replicated=75,
            errors=[f"Error {i}" for i in range(25)],
            warnings=[f"Warning {i}" for i in range(10)],
        )

        assert len(result.errors) == 25
        assert len(result.warnings) == 10
        assert result.items_discovered == 100
        assert result.items_replicated == 75

    def test_validate_resource_with_extra_fields(self):
        """Test validation succeeds with extra resource fields."""
        plugin = ConcretePlugin()
        resource = {
            "id": "/subscriptions/123",
            "type": "Microsoft.Test/resources",
            "name": "test",
            "location": "eastus",
            "tags": {"env": "prod"},
            "properties": {"custom": "data"},
        }

        assert plugin.validate_resource(resource) is True
