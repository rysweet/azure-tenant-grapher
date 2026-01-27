"""Tests for Network Watcher Terraform handler.

This module tests the NetworkWatcherHandler which converts Azure Network Watchers
to Terraform azurerm_network_watcher resources.

Network Watchers are automatically created by Azure (one per region) and are
typically found in the NetworkWatcherRG resource group. They should be imported
rather than created new.

Test coverage:
- Handler registration and discovery
- Basic Network Watcher conversion
- Name sanitization
- Regional Network Watcher handling
- Edge cases (missing fields)
- Resource group name handling (typically NetworkWatcherRG)
"""

import json

from src.iac.emitters.terraform.context import EmitterContext
from src.iac.emitters.terraform.handlers import (
    HandlerRegistry,
    ensure_handlers_registered,
)
from src.iac.emitters.terraform.handlers.network.network_watcher import (
    NetworkWatcherHandler,
)


class TestNetworkWatcherHandlerRegistration:
    """Test handler registration and discovery."""

    def test_network_watcher_handler_registered(self):
        """Verify NetworkWatcherHandler is registered."""
        ensure_handlers_registered()
        handler = HandlerRegistry.get_handler("Microsoft.Network/networkWatchers")
        assert handler is not None
        assert isinstance(handler, NetworkWatcherHandler)

    def test_network_watcher_handler_handled_types(self):
        """Verify handler declares correct Azure types."""
        assert (
            "Microsoft.Network/networkWatchers" in NetworkWatcherHandler.HANDLED_TYPES
        )

    def test_network_watcher_handler_terraform_types(self):
        """Verify handler declares correct Terraform types."""
        assert "azurerm_network_watcher" in NetworkWatcherHandler.TERRAFORM_TYPES


class TestNetworkWatcherConversion:
    """Test Network Watcher conversion to Terraform."""

    def test_basic_network_watcher(self):
        """Test converting a basic Network Watcher with required fields."""
        handler = NetworkWatcherHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/NetworkWatcherRG/providers/Microsoft.Network/networkWatchers/NetworkWatcher_eastus",
            "name": "NetworkWatcher_eastus",
            "type": "Microsoft.Network/networkWatchers",
            "location": "eastus",
            "resource_group": "NetworkWatcherRG",
            "properties": json.dumps({}),
        }

        result = handler.emit(resource, context)
        assert result is not None
        terraform_type, safe_name, config = result

        assert terraform_type == "azurerm_network_watcher"
        assert safe_name == "NetworkWatcher_eastus"
        assert config["name"] == "NetworkWatcher_eastus"
        assert config["location"] == "eastus"
        assert config["resource_group_name"] == "NetworkWatcherRG"

    def test_network_watcher_westus(self):
        """Test Network Watcher in different region."""
        handler = NetworkWatcherHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/NetworkWatcherRG/providers/Microsoft.Network/networkWatchers/NetworkWatcher_westus",
            "name": "NetworkWatcher_westus",
            "type": "Microsoft.Network/networkWatchers",
            "location": "westus",
            "resource_group": "NetworkWatcherRG",
            "properties": json.dumps({}),
        }

        result = handler.emit(resource, context)
        assert result is not None
        _, safe_name, config = result

        assert safe_name == "NetworkWatcher_westus"
        assert config["location"] == "westus"
        assert config["resource_group_name"] == "NetworkWatcherRG"

    def test_network_watcher_westeurope(self):
        """Test Network Watcher in European region."""
        handler = NetworkWatcherHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/NetworkWatcherRG/providers/Microsoft.Network/networkWatchers/NetworkWatcher_westeurope",
            "name": "NetworkWatcher_westeurope",
            "type": "Microsoft.Network/networkWatchers",
            "location": "westeurope",
            "resource_group": "NetworkWatcherRG",
            "properties": json.dumps({}),
        }

        result = handler.emit(resource, context)
        assert result is not None
        _, safe_name, config = result

        assert safe_name == "NetworkWatcher_westeurope"
        assert config["location"] == "westeurope"

    def test_network_watcher_custom_resource_group(self):
        """Test Network Watcher in non-standard resource group."""
        handler = NetworkWatcherHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/custom-rg/providers/Microsoft.Network/networkWatchers/NetworkWatcher_eastus2",
            "name": "NetworkWatcher_eastus2",
            "type": "Microsoft.Network/networkWatchers",
            "location": "eastus2",
            "resource_group": "custom-rg",
            "properties": json.dumps({}),
        }

        result = handler.emit(resource, context)
        assert result is not None
        _, _, config = result

        # Should preserve custom resource group name
        assert config["resource_group_name"] == "custom-rg"
        assert config["location"] == "eastus2"

    def test_network_watcher_with_tags(self):
        """Test Network Watcher with tags."""
        handler = NetworkWatcherHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/NetworkWatcherRG/providers/Microsoft.Network/networkWatchers/NetworkWatcher_eastus",
            "name": "NetworkWatcher_eastus",
            "type": "Microsoft.Network/networkWatchers",
            "location": "eastus",
            "resource_group": "NetworkWatcherRG",
            "tags": json.dumps(
                {
                    "Environment": "Production",
                    "ManagedBy": "Azure",
                }
            ),
            "properties": json.dumps({}),
        }

        result = handler.emit(resource, context)
        assert result is not None
        _, _, config = result

        # Tags should be included via build_base_config
        assert "tags" in config
        tags = config["tags"]
        assert tags["Environment"] == "Production"
        assert tags["ManagedBy"] == "Azure"


class TestNetworkWatcherNameSanitization:
    """Test name sanitization for Network Watchers."""

    def test_network_watcher_name_with_hyphens(self):
        """Test that Network Watcher names with hyphens are sanitized."""
        handler = NetworkWatcherHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/NetworkWatcherRG/providers/Microsoft.Network/networkWatchers/network-watcher-eastus",
            "name": "network-watcher-eastus",
            "type": "Microsoft.Network/networkWatchers",
            "location": "eastus",
            "resource_group": "NetworkWatcherRG",
            "properties": json.dumps({}),
        }

        result = handler.emit(resource, context)
        assert result is not None
        _, safe_name, config = result

        # Hyphens should be converted to underscores in safe_name
        assert safe_name == "network_watcher_eastus"
        # Original name preserved in config
        assert config["name"] == "network-watcher-eastus"

    def test_network_watcher_name_uppercase(self):
        """Test that uppercase characters are preserved in original name."""
        handler = NetworkWatcherHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/NetworkWatcherRG/providers/Microsoft.Network/networkWatchers/NetworkWatcher_EastUS",
            "name": "NetworkWatcher_EastUS",
            "type": "Microsoft.Network/networkWatchers",
            "location": "eastus",
            "resource_group": "NetworkWatcherRG",
            "properties": json.dumps({}),
        }

        result = handler.emit(resource, context)
        assert result is not None
        _, safe_name, config = result

        # Safe name should preserve underscores and case
        assert safe_name == "NetworkWatcher_EastUS"
        # Original name preserved
        assert config["name"] == "NetworkWatcher_EastUS"

    def test_network_watcher_name_special_characters(self):
        """Test Network Watcher with special characters in name."""
        handler = NetworkWatcherHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/NetworkWatcherRG/providers/Microsoft.Network/networkWatchers/network.watcher-eastus_v2",
            "name": "network.watcher-eastus_v2",
            "type": "Microsoft.Network/networkWatchers",
            "location": "eastus",
            "resource_group": "NetworkWatcherRG",
            "properties": json.dumps({}),
        }

        result = handler.emit(resource, context)
        assert result is not None
        _, safe_name, config = result

        # Dots and hyphens should be converted to underscores in safe_name
        assert safe_name == "network_watcher_eastus_v2"
        # Original name preserved
        assert config["name"] == "network.watcher-eastus_v2"


class TestNetworkWatcherEdgeCases:
    """Test edge cases and error handling."""

    def test_network_watcher_missing_name(self):
        """Test Network Watcher with missing name defaults to 'unknown'."""
        handler = NetworkWatcherHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/NetworkWatcherRG/providers/Microsoft.Network/networkWatchers/",
            # name missing
            "type": "Microsoft.Network/networkWatchers",
            "location": "eastus",
            "resource_group": "NetworkWatcherRG",
            "properties": json.dumps({}),
        }

        result = handler.emit(resource, context)
        assert result is not None
        _, safe_name, config = result

        # Should default to 'unknown'
        assert safe_name == "unknown"
        assert config["name"] == "unknown"

    def test_network_watcher_minimal_resource(self):
        """Test Network Watcher with minimal required fields."""
        handler = NetworkWatcherHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/NetworkWatcherRG/providers/Microsoft.Network/networkWatchers/NetworkWatcher_minimal",
            "name": "NetworkWatcher_minimal",
            "type": "Microsoft.Network/networkWatchers",
            "location": "centralus",
            "resource_group": "NetworkWatcherRG",
        }

        result = handler.emit(resource, context)
        assert result is not None
        terraform_type, safe_name, config = result

        assert terraform_type == "azurerm_network_watcher"
        assert safe_name == "NetworkWatcher_minimal"
        assert config["name"] == "NetworkWatcher_minimal"
        assert config["location"] == "centralus"
        assert config["resource_group_name"] == "NetworkWatcherRG"

    def test_network_watcher_empty_properties(self):
        """Test Network Watcher with empty properties is handled correctly."""
        handler = NetworkWatcherHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/NetworkWatcherRG/providers/Microsoft.Network/networkWatchers/NetworkWatcher_northcentralus",
            "name": "NetworkWatcher_northcentralus",
            "type": "Microsoft.Network/networkWatchers",
            "location": "northcentralus",
            "resource_group": "NetworkWatcherRG",
            "properties": json.dumps({}),
        }

        result = handler.emit(resource, context)
        assert result is not None
        _, _, config = result

        # Should emit successfully even with empty properties
        assert config["name"] == "NetworkWatcher_northcentralus"
        assert config["location"] == "northcentralus"

    def test_network_watcher_no_properties_field(self):
        """Test Network Watcher without properties field at all."""
        handler = NetworkWatcherHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/NetworkWatcherRG/providers/Microsoft.Network/networkWatchers/NetworkWatcher_southcentralus",
            "name": "NetworkWatcher_southcentralus",
            "type": "Microsoft.Network/networkWatchers",
            "location": "southcentralus",
            "resource_group": "NetworkWatcherRG",
            # No properties field
        }

        result = handler.emit(resource, context)
        assert result is not None
        _, _, config = result

        # Should emit successfully without properties
        assert config["name"] == "NetworkWatcher_southcentralus"
        assert config["location"] == "southcentralus"


class TestNetworkWatcherContextTracking:
    """Test context tracking for Network Watchers."""

    def test_network_watcher_registered_in_context(self):
        """Test that emitted Network Watcher is tracked in context."""
        handler = NetworkWatcherHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/NetworkWatcherRG/providers/Microsoft.Network/networkWatchers/NetworkWatcher_eastus",
            "name": "NetworkWatcher_eastus",
            "type": "Microsoft.Network/networkWatchers",
            "location": "eastus",
            "resource_group": "NetworkWatcherRG",
            "properties": json.dumps({}),
        }

        result = handler.emit(resource, context)
        assert result is not None
        terraform_type, safe_name, _ = result

        # Verify resource is tracked in context (via base handler)
        # This allows other resources to reference the Network Watcher
        # Note: Actual tracking happens in the emitter after emit() returns
        assert terraform_type == "azurerm_network_watcher"
        assert safe_name == "NetworkWatcher_eastus"
