"""Tests for Bastion Host Terraform handler.

This module tests the BastionHostHandler which converts Azure Bastion Hosts
to Terraform azurerm_bastion_host resources.

Test coverage:
- Handler registration and discovery
- Basic Bastion Host conversion
- IP configuration handling
- Public IP reference validation
- Subnet reference resolution
- SKU configuration
- Error cases (missing IP config, missing public IP)
"""

import json

from src.iac.emitters.terraform.context import EmitterContext
from src.iac.emitters.terraform.handlers import (
    HandlerRegistry,
    ensure_handlers_registered,
)
from src.iac.emitters.terraform.handlers.network.bastion import BastionHostHandler


class TestBastionHandlerRegistration:
    """Test handler registration and discovery."""

    def test_bastion_handler_registered(self):
        """Verify BastionHostHandler is registered."""
        ensure_handlers_registered()
        handler = HandlerRegistry.get_handler("Microsoft.Network/bastionHosts")
        assert handler is not None
        assert isinstance(handler, BastionHostHandler)

    def test_bastion_handler_handled_types(self):
        """Verify handler declares correct Azure types."""
        assert "Microsoft.Network/bastionHosts" in BastionHostHandler.HANDLED_TYPES

    def test_bastion_handler_terraform_types(self):
        """Verify handler declares correct Terraform types."""
        assert "azurerm_bastion_host" in BastionHostHandler.TERRAFORM_TYPES


class TestBastionHostConversion:
    """Test Bastion Host conversion to Terraform."""

    def test_basic_bastion_host(self):
        """Test converting a basic Bastion Host with required fields."""
        handler = BastionHostHandler()
        context = EmitterContext()

        # Add public IP to context as available resource
        context.add_resource("azurerm_public_ip", "bastion_pip")

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/bastionHosts/test-bastion",
            "name": "test-bastion",
            "type": "Microsoft.Network/bastionHosts",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "ipConfigurations": [
                        {
                            "name": "IpConf",
                            "properties": {
                                "subnet": {
                                    "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/AzureBastionSubnet"
                                },
                                "publicIPAddress": {
                                    "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/publicIPAddresses/bastion-pip"
                                },
                            },
                        }
                    ],
                }
            ),
        }

        result = handler.emit(resource, context)
        assert result is not None
        terraform_type, safe_name, config = result

        assert terraform_type == "azurerm_bastion_host"
        assert safe_name == "test_bastion"
        assert config["name"] == "test-bastion"
        assert config["location"] == "eastus"
        assert config["resource_group_name"] == "test-rg"
        assert "ip_configuration" in config

        # Verify IP configuration
        ip_config = config["ip_configuration"]
        assert ip_config["name"] == "IpConf"
        assert (
            "${azurerm_subnet.test_vnet_AzureBastionSubnet.id}"
            in ip_config["subnet_id"]
        )
        assert (
            ip_config["public_ip_address_id"] == "${azurerm_public_ip.bastion_pip.id}"
        )

    def test_bastion_host_with_sku(self):
        """Test Bastion Host with SKU configuration."""
        handler = BastionHostHandler()
        context = EmitterContext()
        context.add_resource("azurerm_public_ip", "bastion_pip")

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/bastionHosts/premium-bastion",
            "name": "premium-bastion",
            "type": "Microsoft.Network/bastionHosts",
            "location": "westus2",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "sku": {
                        "name": "Standard",
                    },
                    "ipConfigurations": [
                        {
                            "name": "IpConf",
                            "properties": {
                                "subnet": {
                                    "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/AzureBastionSubnet"
                                },
                                "publicIPAddress": {
                                    "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/publicIPAddresses/bastion-pip"
                                },
                            },
                        }
                    ],
                }
            ),
        }

        result = handler.emit(resource, context)
        assert result is not None
        _, _, config = result

        assert config["sku"] == "Standard"

    def test_bastion_host_missing_ip_configurations(self):
        """Test that Bastion Host without IP configurations is skipped."""
        handler = BastionHostHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/bastionHosts/no-ip-bastion",
            "name": "no-ip-bastion",
            "type": "Microsoft.Network/bastionHosts",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps({}),  # No ipConfigurations
        }

        result = handler.emit(resource, context)
        assert result is None

    def test_bastion_host_empty_ip_configurations(self):
        """Test that Bastion Host with empty IP configurations array is skipped."""
        handler = BastionHostHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/bastionHosts/empty-ip-bastion",
            "name": "empty-ip-bastion",
            "type": "Microsoft.Network/bastionHosts",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps({"ipConfigurations": []}),
        }

        result = handler.emit(resource, context)
        assert result is None

    def test_bastion_host_missing_public_ip(self):
        """Test that Bastion Host without public IP is skipped."""
        handler = BastionHostHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/bastionHosts/no-public-ip-bastion",
            "name": "no-public-ip-bastion",
            "type": "Microsoft.Network/bastionHosts",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "ipConfigurations": [
                        {
                            "name": "IpConf",
                            "properties": {
                                "subnet": {
                                    "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/AzureBastionSubnet"
                                },
                                # Missing publicIPAddress
                            },
                        }
                    ],
                }
            ),
        }

        result = handler.emit(resource, context)
        assert result is None

    def test_bastion_host_missing_subnet(self):
        """Test Bastion Host with missing subnet reference (should emit with unknown subnet)."""
        handler = BastionHostHandler()
        context = EmitterContext()
        context.add_resource("azurerm_public_ip", "bastion_pip")

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/bastionHosts/no-subnet-bastion",
            "name": "no-subnet-bastion",
            "type": "Microsoft.Network/bastionHosts",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "ipConfigurations": [
                        {
                            "name": "IpConf",
                            "properties": {
                                # Missing subnet
                                "publicIPAddress": {
                                    "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/publicIPAddresses/bastion-pip"
                                },
                            },
                        }
                    ],
                }
            ),
        }

        result = handler.emit(resource, context)
        assert result is not None
        _, _, config = result

        # Should have unknown subnet reference
        assert "unknown_subnet" in config["ip_configuration"]["subnet_id"]

    def test_bastion_host_missing_reference_tracking(self):
        """Test that missing public IP reference is tracked in context."""
        handler = BastionHostHandler()
        context = EmitterContext()

        # Don't add public IP to context - simulate missing reference

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/bastionHosts/test-bastion",
            "name": "test-bastion",
            "type": "Microsoft.Network/bastionHosts",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "ipConfigurations": [
                        {
                            "name": "IpConf",
                            "properties": {
                                "subnet": {
                                    "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/AzureBastionSubnet"
                                },
                                "publicIPAddress": {
                                    "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/publicIPAddresses/missing-pip"
                                },
                            },
                        }
                    ],
                }
            ),
        }

        result = handler.emit(resource, context)
        assert result is not None

        # Verify missing reference was tracked
        missing_refs = context.missing_references
        assert len(missing_refs) > 0
        # Find the missing public_ip reference
        public_ip_refs = [
            ref for ref in missing_refs if ref.get("resource_type") == "public_ip"
        ]
        assert len(public_ip_refs) > 0


class TestBastionHostNameSanitization:
    """Test name sanitization for Bastion Hosts."""

    def test_bastion_host_name_with_hyphens(self):
        """Test that Bastion Host names with hyphens are sanitized."""
        handler = BastionHostHandler()
        context = EmitterContext()
        context.add_resource("azurerm_public_ip", "bastion_pip")

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/bastionHosts/test-bastion-host",
            "name": "test-bastion-host",
            "type": "Microsoft.Network/bastionHosts",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "ipConfigurations": [
                        {
                            "name": "IpConf",
                            "properties": {
                                "subnet": {
                                    "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/AzureBastionSubnet"
                                },
                                "publicIPAddress": {
                                    "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/publicIPAddresses/bastion-pip"
                                },
                            },
                        }
                    ],
                }
            ),
        }

        result = handler.emit(resource, context)
        assert result is not None
        _, safe_name, config = result

        # Hyphens should be converted to underscores in safe_name
        assert safe_name == "test_bastion_host"
        # Original name preserved in config
        assert config["name"] == "test-bastion-host"


class TestBastionVNetLimitEnforcement:
    """Test VNet limit enforcement (Issue #327 - 1 Bastion per VNet)."""

    def test_first_bastion_per_vnet_is_emitted(self):
        """Test that first Bastion in a VNet is successfully emitted."""
        handler = BastionHostHandler()
        context = EmitterContext()
        context.add_resource("azurerm_public_ip", "bastion1_pip")

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/bastionHosts/bastion1",
            "name": "bastion1",
            "type": "Microsoft.Network/bastionHosts",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "ipConfigurations": [
                        {
                            "name": "IpConf",
                            "properties": {
                                "subnet": {
                                    "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/AzureBastionSubnet"
                                },
                                "publicIPAddress": {
                                    "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/publicIPAddresses/bastion1-pip"
                                },
                            },
                        }
                    ],
                }
            ),
        }

        result = handler.emit(resource, context)
        assert result is not None
        terraform_type, safe_name, config = result

        assert terraform_type == "azurerm_bastion_host"
        assert safe_name == "bastion1"
        # Verify VNet is tracked
        assert len(context.vnets_with_bastions) == 1
        assert "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/vnet1" in context.vnets_with_bastions

    def test_second_bastion_on_same_vnet_is_skipped(self):
        """Test that second Bastion on same VNet is skipped with warning."""
        handler = BastionHostHandler()
        context = EmitterContext()
        context.add_resource("azurerm_public_ip", "bastion1_pip")
        context.add_resource("azurerm_public_ip", "bastion2_pip")

        # First Bastion
        resource1 = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/bastionHosts/bastion1",
            "name": "bastion1",
            "type": "Microsoft.Network/bastionHosts",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "ipConfigurations": [
                        {
                            "name": "IpConf",
                            "properties": {
                                "subnet": {
                                    "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/AzureBastionSubnet"
                                },
                                "publicIPAddress": {
                                    "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/publicIPAddresses/bastion1-pip"
                                },
                            },
                        }
                    ],
                }
            ),
        }

        # Second Bastion on same VNet
        resource2 = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/bastionHosts/bastion2",
            "name": "bastion2",
            "type": "Microsoft.Network/bastionHosts",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "ipConfigurations": [
                        {
                            "name": "IpConf",
                            "properties": {
                                "subnet": {
                                    "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/AzureBastionSubnet"  # Same VNet
                                },
                                "publicIPAddress": {
                                    "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/publicIPAddresses/bastion2-pip"
                                },
                            },
                        }
                    ],
                }
            ),
        }

        # First Bastion should succeed
        result1 = handler.emit(resource1, context)
        assert result1 is not None

        # Second Bastion should be skipped
        result2 = handler.emit(resource2, context)
        assert result2 is None

        # Context should still track only one VNet
        assert len(context.vnets_with_bastions) == 1

    def test_multiple_bastions_on_different_vnets_all_emitted(self):
        """Test that Bastions on different VNets are all emitted."""
        handler = BastionHostHandler()
        context = EmitterContext()
        context.add_resource("azurerm_public_ip", "bastion1_pip")
        context.add_resource("azurerm_public_ip", "bastion2_pip")
        context.add_resource("azurerm_public_ip", "bastion3_pip")

        # Bastion on VNet1
        resource1 = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/bastionHosts/bastion1",
            "name": "bastion1",
            "type": "Microsoft.Network/bastionHosts",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "ipConfigurations": [
                        {
                            "name": "IpConf",
                            "properties": {
                                "subnet": {
                                    "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/AzureBastionSubnet"
                                },
                                "publicIPAddress": {
                                    "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/publicIPAddresses/bastion1-pip"
                                },
                            },
                        }
                    ],
                }
            ),
        }

        # Bastion on VNet2
        resource2 = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg2/providers/Microsoft.Network/bastionHosts/bastion2",
            "name": "bastion2",
            "type": "Microsoft.Network/bastionHosts",
            "location": "westus",
            "resource_group": "test-rg2",
            "properties": json.dumps(
                {
                    "ipConfigurations": [
                        {
                            "name": "IpConf",
                            "properties": {
                                "subnet": {
                                    "id": "/subscriptions/test-sub/resourceGroups/test-rg2/providers/Microsoft.Network/virtualNetworks/vnet2/subnets/AzureBastionSubnet"
                                },
                                "publicIPAddress": {
                                    "id": "/subscriptions/test-sub/resourceGroups/test-rg2/providers/Microsoft.Network/publicIPAddresses/bastion2-pip"
                                },
                            },
                        }
                    ],
                }
            ),
        }

        # Bastion on VNet3
        resource3 = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg3/providers/Microsoft.Network/bastionHosts/bastion3",
            "name": "bastion3",
            "type": "Microsoft.Network/bastionHosts",
            "location": "centralus",
            "resource_group": "test-rg3",
            "properties": json.dumps(
                {
                    "ipConfigurations": [
                        {
                            "name": "IpConf",
                            "properties": {
                                "subnet": {
                                    "id": "/subscriptions/test-sub/resourceGroups/test-rg3/providers/Microsoft.Network/virtualNetworks/vnet3/subnets/AzureBastionSubnet"
                                },
                                "publicIPAddress": {
                                    "id": "/subscriptions/test-sub/resourceGroups/test-rg3/providers/Microsoft.Network/publicIPAddresses/bastion3-pip"
                                },
                            },
                        }
                    ],
                }
            ),
        }

        # All three Bastions should be emitted
        result1 = handler.emit(resource1, context)
        result2 = handler.emit(resource2, context)
        result3 = handler.emit(resource3, context)

        assert result1 is not None
        assert result2 is not None
        assert result3 is not None

        # Context should track three VNets
        assert len(context.vnets_with_bastions) == 3

    def test_bastion_without_subnet_not_tracked(self):
        """Test that Bastion without valid subnet doesn't affect VNet tracking."""
        handler = BastionHostHandler()
        context = EmitterContext()
        context.add_resource("azurerm_public_ip", "bastion_pip")

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/bastionHosts/no-subnet-bastion",
            "name": "no-subnet-bastion",
            "type": "Microsoft.Network/bastionHosts",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "ipConfigurations": [
                        {
                            "name": "IpConf",
                            "properties": {
                                # No subnet - will get unknown_subnet
                                "publicIPAddress": {
                                    "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/publicIPAddresses/bastion-pip"
                                },
                            },
                        }
                    ],
                }
            ),
        }

        result = handler.emit(resource, context)
        # Should emit (with unknown subnet) but not track VNet since subnet ID is invalid
        assert result is not None
        assert len(context.vnets_with_bastions) == 0

    def test_vnet_id_extraction_from_subnet(self):
        """Test the VNet ID extraction helper method."""
        handler = BastionHostHandler()

        # Valid subnet ID
        subnet_id = "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/AzureBastionSubnet"
        vnet_id = handler._extract_vnet_id_from_subnet(subnet_id)
        assert vnet_id == "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/vnet1"

        # Empty subnet ID
        vnet_id = handler._extract_vnet_id_from_subnet("")
        assert vnet_id is None

        # Invalid subnet ID (missing virtualNetworks)
        invalid_subnet_id = "/subscriptions/test-sub/resourceGroups/test-rg/subnets/subnet1"
        vnet_id = handler._extract_vnet_id_from_subnet(invalid_subnet_id)
        assert vnet_id is None
