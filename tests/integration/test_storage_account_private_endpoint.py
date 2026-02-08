"""Integration test for Storage Account with multiple Private Endpoints.

This test verifies that a Storage Account with 2 Private Endpoints (blob and file)
is correctly discovered, stored in Neo4j with proper relationships, and emitted
as valid Terraform configuration.

This is a secondary integration test for Issue #887 - ensuring Private Endpoint
handler works for resources with multiple Private Endpoints.

Test coverage:
- Storage Account with 2 Private Endpoints discovered
- Each Private Endpoint has correct groupIds (blob, file)
- Neo4j relationships preserved (2 HAS_PRIVATE_ENDPOINT relationships)
- Terraform emission generates valid configuration for both Private Endpoints
- Generated Terraform has correct references
"""

import json
from typing import Any, Dict, List
from unittest.mock import Mock

import pytest

from src.iac.emitters.terraform.context import EmitterContext
from src.iac.emitters.terraform.handlers import ensure_handlers_registered


class TestStorageAccountWithMultiplePrivateEndpoints:
    """Integration tests for Storage Account with multiple Private Endpoints."""

    @pytest.fixture
    def mock_graph_service(self) -> Mock:
        """Provide a mock Neo4j graph service with Storage Account and 2 PEs."""
        graph = Mock()

        # Mock Storage Account node
        mock_storage_node = Mock()
        mock_storage_node.get.side_effect = lambda key, default=None: {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/teststorage",
            "name": "teststorage",
            "type": "Microsoft.Storage/storageAccounts",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "primaryEndpoints": {
                        "blob": "https://teststorage.blob.core.windows.net/",
                        "file": "https://teststorage.file.core.windows.net/",
                    },
                    "networkAcls": {"defaultAction": "Deny"},
                }
            ),
        }.get(key, default)

        # Mock Private Endpoint 1 (blob)
        mock_pe1_node = Mock()
        mock_pe1_node.get.side_effect = lambda key, default=None: {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/privateEndpoints/storage-blob-pe",
            "name": "storage-blob-pe",
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
                            "name": "blob-connection",
                            "properties": {
                                "privateLinkServiceId": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/teststorage",
                                "groupIds": ["blob"],
                            },
                        }
                    ],
                }
            ),
        }.get(key, default)

        # Mock Private Endpoint 2 (file)
        mock_pe2_node = Mock()
        mock_pe2_node.get.side_effect = lambda key, default=None: {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/privateEndpoints/storage-file-pe",
            "name": "storage-file-pe",
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
                            "name": "file-connection",
                            "properties": {
                                "privateLinkServiceId": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/teststorage",
                                "groupIds": ["file"],
                            },
                        }
                    ],
                }
            ),
        }.get(key, default)

        # Mock graph query to return Storage Account with both Private Endpoints
        def mock_cypher_query(query: str, **kwargs: Any) -> List[Dict[str, Any]]:
            if (
                "MATCH (storage:Resource {type: 'Microsoft.Storage/storageAccounts'})"
                in query
            ):
                # Return Storage Account with 2 Private Endpoints
                return [
                    {
                        "storage": mock_storage_node,
                        "pe1": mock_pe1_node,
                        "pe2": mock_pe2_node,
                    }
                ]
            return []

        graph.cypher_query = mock_cypher_query
        return graph

    @pytest.mark.asyncio
    async def test_storage_account_with_two_private_endpoints_discovery(
        self,
        mock_graph_service: Mock,
    ) -> None:
        """Test Storage Account with 2 Private Endpoints discovered correctly.

        Verifies:
        1. Both Private Endpoints are discovered
        2. Each has correct groupIds (blob, file)
        3. Both reference the same Storage Account
        """
        # Query Neo4j for Storage Account and related Private Endpoints
        result = mock_graph_service.cypher_query(
            """
            MATCH (storage:Resource {type: 'Microsoft.Storage/storageAccounts'})
            OPTIONAL MATCH (storage)-[:HAS_PRIVATE_ENDPOINT]->(pe1:Resource)
            OPTIONAL MATCH (storage)-[:HAS_PRIVATE_ENDPOINT]->(pe2:Resource)
            WHERE pe1.id <> pe2.id
            RETURN storage, pe1, pe2
            """
        )

        # Verify query returns Storage Account with 2 Private Endpoints
        assert len(result) > 0
        data = result[0]
        assert data["storage"] is not None
        assert data["pe1"] is not None
        assert data["pe2"] is not None

        # Verify Private Endpoint 1 (blob)
        pe1_properties = json.loads(data["pe1"].get("properties"))
        assert pe1_properties["privateLinkServiceConnections"][0]["properties"][
            "groupIds"
        ] == ["blob"]

        # Verify Private Endpoint 2 (file)
        pe2_properties = json.loads(data["pe2"].get("properties"))
        assert pe2_properties["privateLinkServiceConnections"][0]["properties"][
            "groupIds"
        ] == ["file"]

        # This test will fail until discovery and Neo4j storage are implemented
        assert False, "Storage Account multi-PE discovery not yet implemented"

    @pytest.mark.asyncio
    async def test_storage_account_private_endpoints_terraform_emission(
        self,
        mock_graph_service: Mock,
    ) -> None:
        """Test that both Private Endpoints emit correctly to Terraform.

        Verifies:
        1. Both Private Endpoints generate azurerm_private_endpoint resources
        2. Each has correct subresource_names (blob, file)
        3. Both reference Storage Account correctly
        4. Names are unique (storage_blob_pe, storage_file_pe)
        """
        ensure_handlers_registered()

        context = EmitterContext(
            target_subscription_id="test-sub",
            graph=mock_graph_service,
        )

        # Add Storage Account and subnet to context
        context.add_resource("azurerm_storage_account", "teststorage")
        context.add_resource("azurerm_subnet", "test_vnet_storage_subnet")

        # Import Private Endpoint handler (will fail until implemented)
        from src.iac.emitters.terraform.handlers.network.private_endpoint import (
            PrivateEndpointHandler,
        )

        handler = PrivateEndpointHandler()

        # Emit Private Endpoint 1 (blob)
        pe1_resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/privateEndpoints/storage-blob-pe",
            "name": "storage-blob-pe",
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
                            "name": "blob-connection",
                            "properties": {
                                "privateLinkServiceId": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/teststorage",
                                "groupIds": ["blob"],
                            },
                        }
                    ],
                }
            ),
        }

        result1 = handler.emit(pe1_resource, context)
        assert result1 is not None
        tf_type1, safe_name1, config1 = result1

        assert tf_type1 == "azurerm_private_endpoint"
        assert safe_name1 == "storage_blob_pe"
        assert config1["private_service_connection"]["subresource_names"] == ["blob"]
        assert (
            "${azurerm_storage_account.teststorage.id}"
            in config1["private_service_connection"]["private_connection_resource_id"]
        )

        # Emit Private Endpoint 2 (file)
        pe2_resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/privateEndpoints/storage-file-pe",
            "name": "storage-file-pe",
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
                            "name": "file-connection",
                            "properties": {
                                "privateLinkServiceId": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/teststorage",
                                "groupIds": ["file"],
                            },
                        }
                    ],
                }
            ),
        }

        result2 = handler.emit(pe2_resource, context)
        assert result2 is not None
        tf_type2, safe_name2, config2 = result2

        assert tf_type2 == "azurerm_private_endpoint"
        assert safe_name2 == "storage_file_pe"
        assert config2["private_service_connection"]["subresource_names"] == ["file"]
        assert (
            "${azurerm_storage_account.teststorage.id}"
            in config2["private_service_connection"]["private_connection_resource_id"]
        )

        # Verify names are unique
        assert safe_name1 != safe_name2

    @pytest.mark.asyncio
    async def test_neo4j_storage_account_has_two_private_endpoint_relationships(
        self,
        mock_graph_service: Mock,
    ) -> None:
        """Test Neo4j has 2 HAS_PRIVATE_ENDPOINT relationships for Storage Account.

        Verifies:
        1. Storage Account node exists
        2. Two Private Endpoint nodes exist
        3. Two HAS_PRIVATE_ENDPOINT relationships exist
        4. Relationships point to correct Private Endpoints
        """
        # Query for Storage Account and count Private Endpoint relationships
        result = mock_graph_service.cypher_query(
            """
            MATCH (storage:Resource {type: 'Microsoft.Storage/storageAccounts', name: 'teststorage'})
            MATCH (storage)-[:HAS_PRIVATE_ENDPOINT]->(pe:Resource)
            RETURN storage, collect(pe) as private_endpoints
            """
        )

        # This query will fail until Neo4j storage is implemented
        # Expected: 1 Storage Account with 2 Private Endpoints
        assert len(result) > 0
        data = result[0]
        assert data["storage"] is not None
        assert len(data["private_endpoints"]) == 2

        # Verify Private Endpoints are different
        pe_ids = [pe.get("id") for pe in data["private_endpoints"]]
        assert len(set(pe_ids)) == 2  # Unique IDs

        assert False, "Neo4j storage for multiple PEs not yet implemented"

    @pytest.mark.asyncio
    async def test_terraform_references_are_consistent(
        self,
        mock_graph_service: Mock,
    ) -> None:
        """Test that Terraform references between Storage and PEs are consistent.

        Verifies:
        1. Both Private Endpoints reference same Storage Account resource
        2. Storage Account resource exists in Terraform config
        3. No orphaned references
        """
        ensure_handlers_registered()

        context = EmitterContext(
            target_subscription_id="test-sub",
            graph=mock_graph_service,
        )

        # Add Storage Account to context
        context.add_resource("azurerm_storage_account", "teststorage")
        context.add_resource("azurerm_subnet", "test_vnet_storage_subnet")

        # Emit both Private Endpoints
        from src.iac.emitters.terraform.handlers.network.private_endpoint import (
            PrivateEndpointHandler,
        )

        handler = PrivateEndpointHandler()

        pe1_resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/privateEndpoints/storage-blob-pe",
            "name": "storage-blob-pe",
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
                            "name": "blob-connection",
                            "properties": {
                                "privateLinkServiceId": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/teststorage",
                                "groupIds": ["blob"],
                            },
                        }
                    ],
                }
            ),
        }

        pe2_resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/privateEndpoints/storage-file-pe",
            "name": "storage-file-pe",
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
                            "name": "file-connection",
                            "properties": {
                                "privateLinkServiceId": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/teststorage",
                                "groupIds": ["file"],
                            },
                        }
                    ],
                }
            ),
        }

        result1 = handler.emit(pe1_resource, context)
        result2 = handler.emit(pe2_resource, context)

        # Extract private_connection_resource_id from both
        _, _, config1 = result1
        _, _, config2 = result2

        ref1 = config1["private_service_connection"]["private_connection_resource_id"]
        ref2 = config2["private_service_connection"]["private_connection_resource_id"]

        # Both should reference the same Storage Account
        assert ref1 == ref2
        assert "${azurerm_storage_account.teststorage.id}" in ref1

        # Verify Storage Account resource exists in context
        assert context.resource_exists("azurerm_storage_account", "teststorage")

    @pytest.mark.asyncio
    async def test_private_endpoint_groupids_are_different(
        self,
        mock_graph_service: Mock,
    ) -> None:
        """Test that each Private Endpoint has different groupIds.

        Verifies:
        1. PE1 has groupIds = ["blob"]
        2. PE2 has groupIds = ["file"]
        3. No duplicate groupIds across Private Endpoints
        """
        # Query Neo4j
        result = mock_graph_service.cypher_query(
            """
            MATCH (storage:Resource {type: 'Microsoft.Storage/storageAccounts'})
            MATCH (storage)-[:HAS_PRIVATE_ENDPOINT]->(pe:Resource)
            RETURN pe
            """
        )

        # This will fail until implementation exists
        # Expected: 2 Private Endpoints with different groupIds
        assert False, "Private Endpoint groupIds differentiation not yet implemented"


class TestPrivateEndpointEdgeCases:
    """Test edge cases for Private Endpoint handling."""

    @pytest.mark.asyncio
    async def test_private_endpoint_with_multiple_groupids(self) -> None:
        """Test Private Endpoint with multiple groupIds (e.g., blob + file + table).

        Some Private Endpoints can have multiple subresources in a single connection.
        Verify this is handled correctly.
        """
        ensure_handlers_registered()

        context = EmitterContext()
        context.add_resource("azurerm_storage_account", "multistorage")
        context.add_resource("azurerm_subnet", "test_vnet_multi_subnet")

        from src.iac.emitters.terraform.handlers.network.private_endpoint import (
            PrivateEndpointHandler,
        )

        handler = PrivateEndpointHandler()

        pe_resource = {
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

        result = handler.emit(pe_resource, context)
        assert result is not None
        _, _, config = result

        # Verify all three groupIds are present
        assert config["private_service_connection"]["subresource_names"] == [
            "blob",
            "file",
            "table",
        ]

    @pytest.mark.asyncio
    async def test_private_endpoint_without_parent_resource(self) -> None:
        """Test Private Endpoint when parent resource doesn't exist in graph.

        This can happen if:
        1. Parent resource was deleted but PE still exists
        2. Parent resource is in different subscription (not discovered)
        3. Discovery race condition
        """
        # Verify handler gracefully handles missing parent
        # Should emit PE but track missing reference
        assert False, "Missing parent resource handling not yet implemented"
