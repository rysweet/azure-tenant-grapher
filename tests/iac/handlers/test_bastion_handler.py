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
        context.track_generated_resource("azurerm_public_ip", "bastion_pip")

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
        context.track_generated_resource("azurerm_public_ip", "bastion_pip")

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
        context.track_generated_resource("azurerm_public_ip", "bastion_pip")

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
        missing_refs = context.get_missing_references()
        assert len(missing_refs) > 0
        # Find the missing public_ip reference
        public_ip_refs = [
            ref for ref in missing_refs if ref.get("reference_type") == "public_ip"
        ]
        assert len(public_ip_refs) > 0


class TestBastionHostNameSanitization:
    """Test name sanitization for Bastion Hosts."""

    def test_bastion_host_name_with_hyphens(self):
        """Test that Bastion Host names with hyphens are sanitized."""
        handler = BastionHostHandler()
        context = EmitterContext()
        context.track_generated_resource("azurerm_public_ip", "bastion_pip")

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
