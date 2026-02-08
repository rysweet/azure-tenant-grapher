"""Tests for Private Endpoint Terraform handler.

This module tests the PrivateEndpointHandler which converts Azure Private Endpoints
to Terraform azurerm_private_endpoint resources.

Test coverage:
- Handler registration and discovery
- Basic Private Endpoint conversion
- Private service connection handling
- Subnet reference resolution
- Multiple private DNS zone group handling
- Error cases (missing required fields)
"""

import json

from src.iac.emitters.terraform.context import EmitterContext
from src.iac.emitters.terraform.handlers import (
    HandlerRegistry,
    ensure_handlers_registered,
)
from src.iac.emitters.terraform.handlers.network.private_endpoint import (
    PrivateEndpointHandler,
)


class TestPrivateEndpointHandlerRegistration:
    """Test handler registration and discovery."""

    def test_private_endpoint_handler_registered(self):
        """Verify PrivateEndpointHandler is registered."""
        ensure_handlers_registered()
        handler = HandlerRegistry.get_handler("Microsoft.Network/privateEndpoints")
        assert handler is not None
        assert isinstance(handler, PrivateEndpointHandler)

    def test_private_endpoint_handler_handled_types(self):
        """Verify handler declares correct Azure types."""
        assert (
            "Microsoft.Network/privateEndpoints" in PrivateEndpointHandler.HANDLED_TYPES
        )

    def test_private_endpoint_handler_terraform_types(self):
        """Verify handler declares correct Terraform types."""
        assert "azurerm_private_endpoint" in PrivateEndpointHandler.TERRAFORM_TYPES


class TestPrivateEndpointConversion:
    """Test Private Endpoint conversion to Terraform."""

    def test_basic_private_endpoint(self):
        """Test converting a basic Private Endpoint with required fields."""
        handler = PrivateEndpointHandler()
        context = EmitterContext()

        # Add subnet to context as available resource
        context.add_resource("azurerm_subnet", "storage_subnet")

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/privateEndpoints/test-pe",
            "name": "test-pe",
            "type": "Microsoft.Network/privateEndpoints",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "subnet": {
                        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/storage-subnet"
                    },
                    "privateLinkServiceConnections": [
                        {
                            "name": "storage-connection",
                            "properties": {
                                "privateLinkServiceId": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/teststorage",
                                "groupIds": ["blob"],
                            },
                        }
                    ],
                }
            ),
        }

        result = handler.emit(resource, context)
        assert result is not None
        terraform_type, safe_name, config = result

        assert terraform_type == "azurerm_private_endpoint"
        assert safe_name == "test_pe"
        assert config["name"] == "test-pe"
        assert config["location"] == "eastus"
        assert config["resource_group_name"] == "test-rg"
        assert "subnet_id" in config
        assert "private_service_connection" in config

    def test_private_endpoint_with_private_service_connection(self):
        """Test Private Endpoint with private service connection details."""
        handler = PrivateEndpointHandler()
        context = EmitterContext()
        context.add_resource("azurerm_subnet", "keyvault_subnet")

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/privateEndpoints/kv-pe",
            "name": "kv-pe",
            "type": "Microsoft.Network/privateEndpoints",
            "location": "westus2",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "subnet": {
                        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/keyvault-subnet"
                    },
                    "privateLinkServiceConnections": [
                        {
                            "name": "keyvault-connection",
                            "properties": {
                                "privateLinkServiceId": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/test-kv",
                                "groupIds": ["vault"],
                                "requestMessage": "Please approve this connection",
                            },
                        }
                    ],
                }
            ),
        }

        result = handler.emit(resource, context)
        assert result is not None
        _, _, config = result

        # Verify private service connection
        psc = config["private_service_connection"]
        assert psc["name"] == "keyvault-connection"
        assert (
            "Microsoft.KeyVault/vaults/test-kv" in psc["private_connection_resource_id"]
        )
        assert psc["subresource_names"] == ["vault"]
        assert "request_message" in psc
        assert psc["is_manual_connection"] is False

    def test_private_endpoint_with_multiple_group_ids(self):
        """Test Private Endpoint with multiple group IDs (subresource_names)."""
        handler = PrivateEndpointHandler()
        context = EmitterContext()
        context.add_resource("azurerm_subnet", "multi_subnet")

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/privateEndpoints/multi-pe",
            "name": "multi-pe",
            "type": "Microsoft.Network/privateEndpoints",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "subnet": {
                        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/multi-subnet"
                    },
                    "privateLinkServiceConnections": [
                        {
                            "name": "multi-connection",
                            "properties": {
                                "privateLinkServiceId": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/multistorage",
                                "groupIds": ["blob", "file", "table"],
                            },
                        }
                    ],
                }
            ),
        }

        result = handler.emit(resource, context)
        assert result is not None
        _, _, config = result

        psc = config["private_service_connection"]
        assert psc["subresource_names"] == ["blob", "file", "table"]

    def test_private_endpoint_subnet_reference_resolution(self):
        """Test subnet reference resolution works correctly."""
        handler = PrivateEndpointHandler()
        context = EmitterContext()
        context.add_resource("azurerm_subnet", "test_vnet_pe_subnet")

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/privateEndpoints/subnet-test-pe",
            "name": "subnet-test-pe",
            "type": "Microsoft.Network/privateEndpoints",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "subnet": {
                        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/pe-subnet"
                    },
                    "privateLinkServiceConnections": [
                        {
                            "name": "test-connection",
                            "properties": {
                                "privateLinkServiceId": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/teststorage",
                                "groupIds": ["blob"],
                            },
                        }
                    ],
                }
            ),
        }

        result = handler.emit(resource, context)
        assert result is not None
        _, _, config = result

        # Verify subnet_id uses Terraform reference
        assert "${azurerm_subnet.test_vnet_pe_subnet.id}" in config["subnet_id"]

    def test_private_endpoint_missing_subnet(self):
        """Test that Private Endpoint without subnet is skipped."""
        handler = PrivateEndpointHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/privateEndpoints/no-subnet-pe",
            "name": "no-subnet-pe",
            "type": "Microsoft.Network/privateEndpoints",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    # Missing subnet
                    "privateLinkServiceConnections": [
                        {
                            "name": "test-connection",
                            "properties": {
                                "privateLinkServiceId": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/teststorage",
                                "groupIds": ["blob"],
                            },
                        }
                    ],
                }
            ),
        }

        result = handler.emit(resource, context)
        assert result is None

    def test_private_endpoint_missing_private_link_service_connections(self):
        """Test that Private Endpoint without privateLinkServiceConnections is skipped."""
        handler = PrivateEndpointHandler()
        context = EmitterContext()
        context.add_resource("azurerm_subnet", "test_subnet")

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/privateEndpoints/no-psc-pe",
            "name": "no-psc-pe",
            "type": "Microsoft.Network/privateEndpoints",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "subnet": {
                        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/test-subnet"
                    },
                    # Missing privateLinkServiceConnections
                }
            ),
        }

        result = handler.emit(resource, context)
        assert result is None

    def test_private_endpoint_empty_private_link_service_connections(self):
        """Test that Private Endpoint with empty privateLinkServiceConnections is skipped."""
        handler = PrivateEndpointHandler()
        context = EmitterContext()
        context.add_resource("azurerm_subnet", "test_subnet")

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/privateEndpoints/empty-psc-pe",
            "name": "empty-psc-pe",
            "type": "Microsoft.Network/privateEndpoints",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "subnet": {
                        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/test-subnet"
                    },
                    "privateLinkServiceConnections": [],
                }
            ),
        }

        result = handler.emit(resource, context)
        assert result is None

    def test_private_endpoint_missing_private_link_service_id(self):
        """Test that Private Endpoint without privateLinkServiceId is skipped."""
        handler = PrivateEndpointHandler()
        context = EmitterContext()
        context.add_resource("azurerm_subnet", "test_subnet")

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/privateEndpoints/no-plsid-pe",
            "name": "no-plsid-pe",
            "type": "Microsoft.Network/privateEndpoints",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "subnet": {
                        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/test-subnet"
                    },
                    "privateLinkServiceConnections": [
                        {
                            "name": "incomplete-connection",
                            "properties": {
                                # Missing privateLinkServiceId
                                "groupIds": ["blob"],
                            },
                        }
                    ],
                }
            ),
        }

        result = handler.emit(resource, context)
        assert result is None

    def test_private_endpoint_missing_group_ids(self):
        """Test that Private Endpoint without groupIds is skipped."""
        handler = PrivateEndpointHandler()
        context = EmitterContext()
        context.add_resource("azurerm_subnet", "test_subnet")

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/privateEndpoints/no-groupids-pe",
            "name": "no-groupids-pe",
            "type": "Microsoft.Network/privateEndpoints",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "subnet": {
                        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/test-subnet"
                    },
                    "privateLinkServiceConnections": [
                        {
                            "name": "incomplete-connection",
                            "properties": {
                                "privateLinkServiceId": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/teststorage",
                                # Missing groupIds
                            },
                        }
                    ],
                }
            ),
        }

        result = handler.emit(resource, context)
        assert result is None

    def test_private_endpoint_with_private_dns_zone_group(self):
        """Test Private Endpoint with private DNS zone group configuration."""
        handler = PrivateEndpointHandler()
        context = EmitterContext()
        context.add_resource("azurerm_subnet", "dns_subnet")

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/privateEndpoints/dns-pe",
            "name": "dns-pe",
            "type": "Microsoft.Network/privateEndpoints",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "subnet": {
                        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/dns-subnet"
                    },
                    "privateLinkServiceConnections": [
                        {
                            "name": "dns-connection",
                            "properties": {
                                "privateLinkServiceId": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/test-kv",
                                "groupIds": ["vault"],
                            },
                        }
                    ],
                    "privateDnsZoneGroups": [
                        {
                            "name": "default",
                            "properties": {
                                "privateDnsZoneConfigs": [
                                    {
                                        "name": "privatelink-vaultcore-azure-net",
                                        "properties": {
                                            "privateDnsZoneId": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/privateDnsZones/privatelink.vaultcore.azure.net"
                                        },
                                    }
                                ]
                            },
                        }
                    ],
                }
            ),
        }

        result = handler.emit(resource, context)
        assert result is not None
        _, _, config = result

        # Verify private_dns_zone_group is present
        assert "private_dns_zone_group" in config
        dns_zone_group = config["private_dns_zone_group"]
        assert dns_zone_group["name"] == "default"
        assert "private_dns_zone_ids" in dns_zone_group
        assert len(dns_zone_group["private_dns_zone_ids"]) == 1


class TestPrivateEndpointNameSanitization:
    """Test name sanitization for Private Endpoints."""

    def test_private_endpoint_name_with_hyphens(self):
        """Test that Private Endpoint names with hyphens are sanitized."""
        handler = PrivateEndpointHandler()
        context = EmitterContext()
        context.add_resource("azurerm_subnet", "test_subnet")

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/privateEndpoints/test-pe-endpoint",
            "name": "test-pe-endpoint",
            "type": "Microsoft.Network/privateEndpoints",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "subnet": {
                        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/test-subnet"
                    },
                    "privateLinkServiceConnections": [
                        {
                            "name": "test-connection",
                            "properties": {
                                "privateLinkServiceId": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/teststorage",
                                "groupIds": ["blob"],
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
        assert safe_name == "test_pe_endpoint"
        # Original name preserved in config
        assert config["name"] == "test-pe-endpoint"


class TestPrivateEndpointMissingReferenceTracking:
    """Test missing reference tracking for Private Endpoints."""

    def test_private_endpoint_missing_subnet_tracked(self):
        """Test that missing subnet reference is tracked in context."""
        handler = PrivateEndpointHandler()
        context = EmitterContext()

        # Don't add subnet to context - simulate missing reference

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/privateEndpoints/missing-subnet-pe",
            "name": "missing-subnet-pe",
            "type": "Microsoft.Network/privateEndpoints",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "subnet": {
                        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/missing-subnet"
                    },
                    "privateLinkServiceConnections": [
                        {
                            "name": "test-connection",
                            "properties": {
                                "privateLinkServiceId": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/teststorage",
                                "groupIds": ["blob"],
                            },
                        }
                    ],
                }
            ),
        }

        result = handler.emit(resource, context)
        # Should emit but track missing reference
        assert result is not None

        # Verify missing reference was tracked
        missing_refs = context.missing_references
        assert len(missing_refs) > 0
        # Find the missing subnet reference
        subnet_refs = [
            ref for ref in missing_refs if ref.get("resource_type") == "subnet"
        ]
        assert len(subnet_refs) > 0
