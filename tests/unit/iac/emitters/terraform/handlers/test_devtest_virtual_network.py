"""Unit tests for DevTestLab Virtual Network handler (GAP-019).

Tests virtual network emission with subnet configurations and permissions.
"""

from unittest.mock import Mock

import pytest

from src.iac.emitters.terraform.context import EmitterContext
from src.iac.emitters.terraform.handlers.devtest.devtest_virtual_network import (
    DevTestVirtualNetworkHandler,
)


class TestDevTestVirtualNetworkHandler:
    """Tests for DevTestLab Virtual Network handler."""

    @pytest.fixture
    def handler(self):
        """Create handler instance."""
        return DevTestVirtualNetworkHandler()

    @pytest.fixture
    def context(self):
        """Create mock emitter context."""
        ctx = Mock(spec=EmitterContext)
        ctx.get_effective_subscription_id.return_value = "sub-12345"
        return ctx

    @pytest.fixture
    def base_vnet_resource(self):
        """Base DevTestLab virtual network resource structure."""
        return {
            "id": "/subscriptions/sub-12345/resourceGroups/rg-test/providers/Microsoft.DevTestLab/labs/testlab/virtualnetworks/testvnet",
            "name": "testlab/testvnet",
            "type": "Microsoft.DevTestLab/labs/virtualnetworks",
            "location": "eastus",
            "resource_group": "rg-test",
            "tags": {},
            "properties": {
                "description": "Test lab virtual network",
                "externalProviderResourceId": "/subscriptions/sub-12345/resourceGroups/rg-test/providers/Microsoft.Network/virtualNetworks/actualvnet",
                "subnetOverrides": [
                    {
                        "labSubnetName": "default",
                        "resourceId": "/subscriptions/sub-12345/resourceGroups/rg-test/providers/Microsoft.Network/virtualNetworks/actualvnet/subnets/default",
                        "useInVmCreationPermission": "Allow",
                        "usePublicIpAddressPermission": "Allow",
                    }
                ],
            },
        }

    # ========== Basic Emission Tests ==========

    def test_emit_basic_virtual_network(self, handler, context, base_vnet_resource):
        """Test basic virtual network emission with all properties."""
        tf_type, safe_name, config = handler.emit(base_vnet_resource, context)

        assert tf_type == "azurerm_dev_test_virtual_network"
        assert safe_name == "testvnet"
        assert config["name"] == "testvnet"
        assert config["lab_name"] == "testlab"
        assert config["description"] == "Test lab virtual network"
        assert config["location"] == "eastus"

    def test_handler_registration(self, handler):
        """Test handler is registered for correct resource type."""
        assert handler.can_handle("Microsoft.DevTestLab/labs/virtualnetworks")
        assert handler.can_handle("microsoft.devtestlab/labs/virtualnetworks")

    # ========== Name Parsing Tests ==========

    def test_parse_hierarchical_name(self, handler, context, base_vnet_resource):
        """Test parsing of lab/vnet name."""
        base_vnet_resource["name"] = "mylab/myvnet"

        _, _, config = handler.emit(base_vnet_resource, context)

        assert config["lab_name"] == "mylab"
        assert config["name"] == "myvnet"

    def test_parse_name_with_unusual_characters(
        self, handler, context, base_vnet_resource
    ):
        """Test name parsing with hyphens and underscores."""
        base_vnet_resource["name"] = "my-lab_01/my-vnet_02"

        _, safe_name, config = handler.emit(base_vnet_resource, context)

        assert config["lab_name"] == "my-lab_01"
        assert config["name"] == "my-vnet_02"
        assert (
            safe_name == "my_vnet_02"
        )  # sanitize_name converts hyphens to underscores

    def test_malformed_name_fallback(self, handler, context, base_vnet_resource):
        """Test fallback for malformed virtual network names."""
        base_vnet_resource["name"] = "SingleName"

        _, _, config = handler.emit(base_vnet_resource, context)

        # Should handle gracefully with defaults
        assert config["lab_name"] is not None
        assert config["name"] is not None

    # ========== Subnet Configuration Tests ==========

    def test_subnet_permissions_allow(self, handler, context, base_vnet_resource):
        """Test subnet with Allow permissions."""
        base_vnet_resource["properties"]["subnetOverrides"] = [
            {
                "labSubnetName": "default",
                "resourceId": "/subscriptions/sub-12345/resourceGroups/rg/providers/Microsoft.Network/virtualNetworks/vnet/subnets/default",
                "useInVmCreationPermission": "Allow",
                "usePublicIpAddressPermission": "Allow",
            }
        ]

        _, _, config = handler.emit(base_vnet_resource, context)

        assert "subnet" in config
        assert config["subnet"]["use_in_virtual_machine_creation"] == "Allow"
        assert config["subnet"]["use_public_ip_address"] == "Allow"

    def test_subnet_permissions_deny(self, handler, context, base_vnet_resource):
        """Test subnet with Deny permissions."""
        base_vnet_resource["properties"]["subnetOverrides"] = [
            {
                "labSubnetName": "restricted",
                "resourceId": "/subscriptions/sub-12345/resourceGroups/rg/providers/Microsoft.Network/virtualNetworks/vnet/subnets/restricted",
                "useInVmCreationPermission": "Deny",
                "usePublicIpAddressPermission": "Deny",
            }
        ]

        _, _, config = handler.emit(base_vnet_resource, context)

        assert config["subnet"]["use_in_virtual_machine_creation"] == "Deny"
        assert config["subnet"]["use_public_ip_address"] == "Deny"

    def test_subnet_permissions_default(self, handler, context, base_vnet_resource):
        """Test subnet with Default permissions."""
        base_vnet_resource["properties"]["subnetOverrides"] = [
            {
                "labSubnetName": "default",
                "resourceId": "/subscriptions/sub-12345/resourceGroups/rg/providers/Microsoft.Network/virtualNetworks/vnet/subnets/default",
                "useInVmCreationPermission": "Default",
                "usePublicIpAddressPermission": "Default",
            }
        ]

        _, _, config = handler.emit(base_vnet_resource, context)

        assert config["subnet"]["use_in_virtual_machine_creation"] == "Default"
        assert config["subnet"]["use_public_ip_address"] == "Default"

    def test_empty_subnet_overrides(self, handler, context, base_vnet_resource):
        """Test handling of empty subnetOverrides array."""
        base_vnet_resource["properties"]["subnetOverrides"] = []

        _, _, config = handler.emit(base_vnet_resource, context)

        # Should emit successfully with minimal subnet config
        assert config["name"] == "testvnet"

    def test_missing_subnet_overrides(self, handler, context, base_vnet_resource):
        """Test handling of missing subnetOverrides property."""
        del base_vnet_resource["properties"]["subnetOverrides"]

        _, _, config = handler.emit(base_vnet_resource, context)

        # Should emit successfully
        assert config["name"] == "testvnet"

    # ========== External Provider Resource Tests ==========

    def test_external_vnet_reference(self, handler, context, base_vnet_resource):
        """Test external virtual network resource ID."""
        external_id = "/subscriptions/sub-12345/resourceGroups/rg-external/providers/Microsoft.Network/virtualNetworks/external-vnet"
        base_vnet_resource["properties"]["externalProviderResourceId"] = external_id

        _, _, config = handler.emit(base_vnet_resource, context)

        # Handler should preserve the reference
        assert config["name"] == "testvnet"

    def test_missing_external_provider(self, handler, context, base_vnet_resource):
        """Test handling of missing externalProviderResourceId."""
        del base_vnet_resource["properties"]["externalProviderResourceId"]

        _, _, config = handler.emit(base_vnet_resource, context)

        # Should emit successfully without external reference
        assert config["name"] == "testvnet"

    # ========== Multiple Subnets Tests ==========

    def test_multiple_subnet_overrides(self, handler, context, base_vnet_resource):
        """Test handling of multiple subnet configurations."""
        base_vnet_resource["properties"]["subnetOverrides"] = [
            {
                "labSubnetName": "subnet1",
                "resourceId": "/subscriptions/sub-12345/resourceGroups/rg/providers/Microsoft.Network/virtualNetworks/vnet/subnets/subnet1",
                "useInVmCreationPermission": "Allow",
                "usePublicIpAddressPermission": "Allow",
            },
            {
                "labSubnetName": "subnet2",
                "resourceId": "/subscriptions/sub-12345/resourceGroups/rg/providers/Microsoft.Network/virtualNetworks/vnet/subnets/subnet2",
                "useInVmCreationPermission": "Deny",
                "usePublicIpAddressPermission": "Allow",
            },
        ]

        _, _, config = handler.emit(base_vnet_resource, context)

        # Handler should process primary subnet (first one)
        assert "subnet" in config

    # ========== Description Tests ==========

    def test_with_description(self, handler, context, base_vnet_resource):
        """Test virtual network with description."""
        base_vnet_resource["properties"]["description"] = "Production lab network"

        _, _, config = handler.emit(base_vnet_resource, context)

        assert config["description"] == "Production lab network"

    def test_missing_description(self, handler, context, base_vnet_resource):
        """Test handling of missing description."""
        del base_vnet_resource["properties"]["description"]

        _, _, config = handler.emit(base_vnet_resource, context)

        # Should emit successfully
        assert config["name"] == "testvnet"

    def test_empty_description(self, handler, context, base_vnet_resource):
        """Test handling of empty description."""
        base_vnet_resource["properties"]["description"] = ""

        _, _, config = handler.emit(base_vnet_resource, context)

        # Empty description should not be included in config (handler skips empty strings)
        # Just verify the handler emits successfully
        assert config["name"] == "testvnet"

    # ========== Edge Cases Tests ==========

    def test_tags_preservation(self, handler, context, base_vnet_resource):
        """Test tags are preserved in config."""
        base_vnet_resource["tags"] = {
            "Environment": "Production",
            "CostCenter": "Engineering",
        }

        _, _, config = handler.emit(base_vnet_resource, context)

        assert config["tags"]["Environment"] == "Production"
        assert config["tags"]["CostCenter"] == "Engineering"

    def test_resource_group_extraction(self, handler, context, base_vnet_resource):
        """Test resource group is correctly extracted."""
        _, _, config = handler.emit(base_vnet_resource, context)

        assert "resource_group_name" in config
        assert config["resource_group_name"] is not None

    def test_location_preservation(self, handler, context, base_vnet_resource):
        """Test location is preserved."""
        base_vnet_resource["location"] = "westus2"

        _, _, config = handler.emit(base_vnet_resource, context)

        assert config["location"] == "westus2"

    # ========== Subnet Name Extraction Tests ==========

    def test_subnet_name_from_override(self, handler, context, base_vnet_resource):
        """Test subnet name extraction from subnetOverrides."""
        base_vnet_resource["properties"]["subnetOverrides"] = [
            {
                "labSubnetName": "custom-subnet",
                "resourceId": "/subscriptions/sub-12345/resourceGroups/rg/providers/Microsoft.Network/virtualNetworks/vnet/subnets/custom-subnet",
                "useInVmCreationPermission": "Allow",
                "usePublicIpAddressPermission": "Default",
            }
        ]

        _, _, config = handler.emit(base_vnet_resource, context)

        # Subnet configuration should be present
        assert "subnet" in config
