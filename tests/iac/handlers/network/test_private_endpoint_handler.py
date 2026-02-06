"""Tests for Private Endpoint Terraform handler.

This module tests the PrivateEndpointHandler which converts Azure Private Endpoints
to Terraform azurerm_private_endpoint resources.

Test coverage:
- Handler registration and discovery
- Basic Private Endpoint conversion
- Subnet reference resolution (VNet-scoped)
- Private service connection handling
- Multiple connections support
- Error cases (missing connections, invalid subnet)
- Name sanitization
- Missing reference tracking
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
        context.add_resource("azurerm_subnet", "test_vnet_default")

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/privateEndpoints/test-pe",
            "name": "test-pe",
            "type": "Microsoft.Network/privateEndpoints",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "subnet": {
                        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/default"
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
        terraform_type, safe_name, config = result

        assert terraform_type == "azurerm_private_endpoint"
        assert safe_name == "test_pe"
        assert config["name"] == "test-pe"
        assert config["location"] == "eastus"
        assert config["resource_group_name"] == "test-rg"
        assert "subnet_id" in config
        assert "private_service_connection" in config

        # Verify subnet reference
        assert config["subnet_id"] == "${azurerm_subnet.test_vnet_default.id}"

        # Verify private service connection
        connections = config["private_service_connection"]
        assert len(connections) == 1
        assert connections[0]["name"] == "test-connection"
        assert connections[0]["is_manual_connection"] is False
        assert (
            connections[0]["private_connection_resource_id"]
            == "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/teststorage"
        )
        assert connections[0]["subresource_names"] == ["blob"]

    def test_private_endpoint_with_subnet_reference(self):
        """Test Private Endpoint with VNet-scoped subnet reference resolution."""
        handler = PrivateEndpointHandler()
        context = EmitterContext()

        # Add subnet to context with VNet-scoped name
        context.add_resource("azurerm_subnet", "prod_vnet_private_endpoints")

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/prod-rg/providers/Microsoft.Network/privateEndpoints/storage-pe",
            "name": "storage-pe",
            "type": "Microsoft.Network/privateEndpoints",
            "location": "westus2",
            "resource_group": "prod-rg",
            "properties": json.dumps(
                {
                    "subnet": {
                        "id": "/subscriptions/test-sub/resourceGroups/prod-rg/providers/Microsoft.Network/virtualNetworks/prod-vnet/subnets/private-endpoints"
                    },
                    "privateLinkServiceConnections": [
                        {
                            "name": "storage-connection",
                            "properties": {
                                "privateLinkServiceId": "/subscriptions/test-sub/resourceGroups/prod-rg/providers/Microsoft.Storage/storageAccounts/prodstg",
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

        # Verify VNet-scoped subnet reference
        assert config["subnet_id"] == "${azurerm_subnet.prod_vnet_private_endpoints.id}"

    def test_private_endpoint_multiple_connections(self):
        """Test Private Endpoint with multiple private service connections."""
        handler = PrivateEndpointHandler()
        context = EmitterContext()
        context.add_resource("azurerm_subnet", "test_vnet_default")

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/privateEndpoints/multi-pe",
            "name": "multi-pe",
            "type": "Microsoft.Network/privateEndpoints",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "subnet": {
                        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/default"
                    },
                    "privateLinkServiceConnections": [
                        {
                            "name": "blob-connection",
                            "properties": {
                                "privateLinkServiceId": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/teststorage",
                                "groupIds": ["blob"],
                            },
                        },
                        {
                            "name": "file-connection",
                            "properties": {
                                "privateLinkServiceId": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/teststorage",
                                "groupIds": ["file"],
                            },
                        },
                    ],
                }
            ),
        }

        result = handler.emit(resource, context)
        assert result is not None
        _, _, config = result

        # Verify multiple connections
        connections = config["private_service_connection"]
        assert len(connections) == 2
        assert connections[0]["name"] == "blob-connection"
        assert connections[0]["subresource_names"] == ["blob"]
        assert connections[1]["name"] == "file-connection"
        assert connections[1]["subresource_names"] == ["file"]

    def test_private_endpoint_missing_connections(self):
        """Test that Private Endpoint without connections is skipped."""
        handler = PrivateEndpointHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/privateEndpoints/no-conn-pe",
            "name": "no-conn-pe",
            "type": "Microsoft.Network/privateEndpoints",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "subnet": {
                        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/default"
                    },
                    "privateLinkServiceConnections": [],  # Empty connections
                }
            ),
        }

        result = handler.emit(resource, context)
        assert result is None

    def test_private_endpoint_no_connections_field(self):
        """Test that Private Endpoint without connections field is skipped."""
        handler = PrivateEndpointHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/privateEndpoints/no-field-pe",
            "name": "no-field-pe",
            "type": "Microsoft.Network/privateEndpoints",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "subnet": {
                        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/default"
                    }
                    # Missing privateLinkServiceConnections field
                }
            ),
        }

        result = handler.emit(resource, context)
        assert result is None

    def test_private_endpoint_missing_subnet(self):
        """Test Private Endpoint with missing subnet reference (unknown subnet)."""
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
                    # No subnet field
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

        # Should have unknown subnet reference
        assert "unknown_subnet" in config["subnet_id"]

    def test_private_endpoint_invalid_subnet_id(self):
        """Test Private Endpoint with invalid/malformed subnet ID."""
        handler = PrivateEndpointHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/privateEndpoints/invalid-subnet-pe",
            "name": "invalid-subnet-pe",
            "type": "Microsoft.Network/privateEndpoints",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "subnet": {
                        "id": "/invalid/subnet/id"  # Malformed ID
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

        # Should fall back to unknown subnet
        assert "unknown_subnet" in config["subnet_id"]

    def test_private_endpoint_missing_subnet_reference_tracking(self):
        """Test that missing subnet reference is tracked in context."""
        handler = PrivateEndpointHandler()
        context = EmitterContext()

        # Don't add subnet to context - simulate missing reference

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/privateEndpoints/test-pe",
            "name": "test-pe",
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
        assert result is not None

        # Verify missing reference was tracked
        missing_refs = context.missing_references
        assert len(missing_refs) > 0
        # Find the missing subnet reference
        subnet_refs = [
            ref for ref in missing_refs if ref.get("resource_type") == "subnet"
        ]
        assert len(subnet_refs) > 0
        # Verify structure: resource_name is the PE, missing_resource_name is the subnet
        assert subnet_refs[0]["resource_name"] == "test-pe"
        assert subnet_refs[0]["missing_resource_name"] == "missing-subnet"
        assert "missing-subnet" in subnet_refs[0]["missing_resource_id"]


class TestPrivateEndpointNameSanitization:
    """Test name sanitization for Private Endpoints."""

    def test_private_endpoint_name_with_hyphens(self):
        """Test that Private Endpoint names with hyphens are sanitized."""
        handler = PrivateEndpointHandler()
        context = EmitterContext()
        context.add_resource("azurerm_subnet", "test_vnet_default")

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/privateEndpoints/test-private-endpoint",
            "name": "test-private-endpoint",
            "type": "Microsoft.Network/privateEndpoints",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "subnet": {
                        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/default"
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
        assert safe_name == "test_private_endpoint"
        # Original name preserved in config
        assert config["name"] == "test-private-endpoint"


class TestPrivateEndpointConnectionDetails:
    """Test private service connection detail handling."""

    def test_connection_without_group_ids(self):
        """Test connection without subresource group IDs."""
        handler = PrivateEndpointHandler()
        context = EmitterContext()
        context.add_resource("azurerm_subnet", "test_vnet_default")

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/privateEndpoints/no-groups-pe",
            "name": "no-groups-pe",
            "type": "Microsoft.Network/privateEndpoints",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "subnet": {
                        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/default"
                    },
                    "privateLinkServiceConnections": [
                        {
                            "name": "no-groups-connection",
                            "properties": {
                                "privateLinkServiceId": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/testkv"
                                # No groupIds field
                            },
                        }
                    ],
                }
            ),
        }

        result = handler.emit(resource, context)
        assert result is not None
        _, _, config = result

        # Connection should still be created without subresource_names
        connections = config["private_service_connection"]
        assert len(connections) == 1
        assert connections[0]["name"] == "no-groups-connection"
        assert (
            connections[0]["private_connection_resource_id"]
            == "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/testkv"
        )
        assert "subresource_names" not in connections[0]

    def test_connection_without_target_resource_id(self):
        """Test connection without target resource ID."""
        handler = PrivateEndpointHandler()
        context = EmitterContext()
        context.add_resource("azurerm_subnet", "test_vnet_default")

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/privateEndpoints/no-target-pe",
            "name": "no-target-pe",
            "type": "Microsoft.Network/privateEndpoints",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "subnet": {
                        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/default"
                    },
                    "privateLinkServiceConnections": [
                        {
                            "name": "no-target-connection",
                            "properties": {
                                # No privateLinkServiceId field
                                "groupIds": ["blob"]
                            },
                        }
                    ],
                }
            ),
        }

        result = handler.emit(resource, context)
        assert result is not None
        _, _, config = result

        # Connection should be created without private_connection_resource_id
        connections = config["private_service_connection"]
        assert len(connections) == 1
        assert connections[0]["name"] == "no-target-connection"
        assert "private_connection_resource_id" not in connections[0]
        assert connections[0]["subresource_names"] == ["blob"]

    def test_connection_with_default_name(self):
        """Test connection without explicit name uses default."""
        handler = PrivateEndpointHandler()
        context = EmitterContext()
        context.add_resource("azurerm_subnet", "test_vnet_default")

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/privateEndpoints/default-name-pe",
            "name": "default-name-pe",
            "type": "Microsoft.Network/privateEndpoints",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "subnet": {
                        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/default"
                    },
                    "privateLinkServiceConnections": [
                        {
                            # No name field
                            "properties": {
                                "privateLinkServiceId": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/teststorage",
                                "groupIds": ["blob"],
                            }
                        }
                    ],
                }
            ),
        }

        result = handler.emit(resource, context)
        assert result is not None
        _, _, config = result

        # Should use default name based on PE name
        connections = config["private_service_connection"]
        assert len(connections) == 1
        assert connections[0]["name"] == "default-name-pe-connection"
