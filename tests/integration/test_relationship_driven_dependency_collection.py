"""
Integration tests for relationship-driven cross-RG dependency collection.

Tests verify end-to-end functionality of the dependency collection system
including relationship rule extraction, dependency identification, and
resource fetching.

Following TDD methodology - these tests will FAIL until implementation is complete.
"""

import pytest
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock, patch

from src.azure_tenant_grapher import AzureTenantGrapher
from src.models.filter_config import FilterConfig
from src.services.relationship_dependency_collector import RelationshipDependencyCollector
from src.services.azure_discovery_service import AzureDiscoveryService
from src.relationship_rules.network_rule import NetworkRule
from src.relationship_rules.identity_rule import IdentityRule


class TestHubSpokeTopologyDependencies:
    """
    Integration test for hub-spoke network topology.

    Scenario:
    - Hub RG (rg-hub-network): Contains shared network infrastructure
      - VNet: hub-vnet
      - Subnet: hub-subnet1
      - NSG: hub-nsg1
    - Spoke RG (rg-spoke-prod): Contains production workloads
      - VM: spoke-vm1 (references hub NIC)
    - Spoke RG filter should automatically include hub network dependencies
    """

    @pytest.mark.asyncio
    async def test_filtered_scan_with_cross_rg_dependencies(self):
        """
        Test that filtered scan by spoke RG automatically includes hub network dependencies.

        This is the primary integration test validating the entire feature.
        """
        # Setup: Mock Azure resources in hub-spoke topology
        hub_nic = {
            "id": "/subscriptions/sub1/resourceGroups/rg-hub-network/providers/Microsoft.Network/networkInterfaces/hub-nic1",
            "name": "hub-nic1",
            "type": "Microsoft.Network/networkInterfaces",
            "resource_group": "rg-hub-network",
            "location": "eastus",
            "properties": {
                "ipConfigurations": [
                    {
                        "name": "ipconfig1",
                        "properties": {
                            "subnet": {
                                "id": "/subscriptions/sub1/resourceGroups/rg-hub-network/providers/Microsoft.Network/virtualNetworks/hub-vnet/subnets/hub-subnet1"
                            },
                        },
                    }
                ],
                "networkSecurityGroup": {
                    "id": "/subscriptions/sub1/resourceGroups/rg-hub-network/providers/Microsoft.Network/networkSecurityGroups/hub-nsg1"
                },
            },
        }

        hub_subnet = {
            "id": "/subscriptions/sub1/resourceGroups/rg-hub-network/providers/Microsoft.Network/virtualNetworks/hub-vnet/subnets/hub-subnet1",
            "name": "hub-subnet1",
            "type": "Microsoft.Network/virtualNetworks/subnets",
            "resource_group": "rg-hub-network",
            "properties": {
                "addressPrefix": "10.0.0.0/24",
            },
        }

        hub_nsg = {
            "id": "/subscriptions/sub1/resourceGroups/rg-hub-network/providers/Microsoft.Network/networkSecurityGroups/hub-nsg1",
            "name": "hub-nsg1",
            "type": "Microsoft.Network/networkSecurityGroups",
            "resource_group": "rg-hub-network",
            "location": "eastus",
        }

        spoke_vm = {
            "id": "/subscriptions/sub1/resourceGroups/rg-spoke-prod/providers/Microsoft.Compute/virtualMachines/spoke-vm1",
            "name": "spoke-vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "resource_group": "rg-spoke-prod",
            "location": "eastus",
            "properties": {
                "networkProfile": {
                    "networkInterfaces": [
                        {"id": hub_nic["id"]}
                    ]
                },
            },
        }

        # Mock discovery service
        mock_discovery = Mock(spec=AzureDiscoveryService)
        mock_discovery.discover_subscriptions = AsyncMock(
            return_value=[
                {
                    "subscription_id": "sub1",
                    "display_name": "Production",
                }
            ]
        )
        mock_discovery.discover_resources_across_subscriptions = AsyncMock(
            return_value=[spoke_vm]  # Only spoke resources in initial scan
        )

        async def mock_fetch_by_id(resource_id):
            """Mock fetching individual resources by ID."""
            if "hub-nic1" in resource_id:
                return hub_nic
            elif "hub-subnet1" in resource_id:
                return hub_subnet
            elif "hub-nsg1" in resource_id:
                return hub_nsg
            return None

        mock_discovery.fetch_resource_by_id = AsyncMock(side_effect=mock_fetch_by_id)

        # Mock db_ops
        mock_db_ops = Mock()
        mock_db_ops.check_resource_exists = Mock(return_value=False)  # Nothing exists yet
        mock_db_ops.create_resource_node = Mock(return_value=True)

        # Mock relationship rules
        network_rule = NetworkRule()
        identity_rule = IdentityRule()

        # Create dependency collector
        dependency_collector = RelationshipDependencyCollector(
            discovery_service=mock_discovery,
            db_ops=mock_db_ops,
            relationship_rules=[network_rule, identity_rule],
        )

        # Create tenant grapher with dependency collector
        tenant_grapher = AzureTenantGrapher(
            discovery_service=mock_discovery,
            db_ops=mock_db_ops,
            dependency_collector=dependency_collector,
        )

        # Act: Build graph with spoke RG filter
        filter_config = FilterConfig(
            resource_group_names=["rg-spoke-prod"],
            enable_relationship_dependency_collection=True,
        )

        await tenant_grapher.build_graph(filter_config=filter_config)

        # Assert: Verify hub dependencies were collected
        # Check that fetch_resource_by_id was called for hub resources
        fetch_calls = [call[0][0] for call in mock_discovery.fetch_resource_by_id.call_args_list]

        assert any("hub-nic1" in call for call in fetch_calls), (
            "Should fetch hub NIC as cross-RG dependency"
        )
        assert any("hub-subnet1" in call for call in fetch_calls), (
            "Should fetch hub subnet as transitive dependency"
        )
        assert any("hub-nsg1" in call for call in fetch_calls), (
            "Should fetch hub NSG as transitive dependency"
        )

        # Verify nodes were created for all resources (spoke + hub dependencies)
        create_calls = mock_db_ops.create_resource_node.call_args_list
        created_resource_ids = [call[0][0]["id"] for call in create_calls]

        assert spoke_vm["id"] in created_resource_ids, "Should create spoke VM node"
        assert hub_nic["id"] in created_resource_ids, "Should create hub NIC node"
        assert hub_subnet["id"] in created_resource_ids, "Should create hub subnet node"
        assert hub_nsg["id"] in created_resource_ids, "Should create hub NSG node"


class TestRelationshipCreation:
    """Tests for creating relationships after collecting dependencies."""

    @pytest.mark.asyncio
    async def test_filtered_scan_creates_relationships_successfully(self):
        """Test that relationships are created correctly after dependency collection."""
        # Setup resources
        webapp = {
            "id": "/subscriptions/sub1/resourceGroups/rg-apps/providers/Microsoft.Web/sites/webapp1",
            "name": "webapp1",
            "type": "Microsoft.Web/sites",
            "resource_group": "rg-apps",
            "identity": {
                "type": "UserAssigned",
                "userAssignedIdentities": {
                    "/subscriptions/sub1/resourceGroups/rg-identity/providers/Microsoft.ManagedIdentity/userAssignedIdentities/webapp-identity": {}
                },
            },
        }

        identity = {
            "id": "/subscriptions/sub1/resourceGroups/rg-identity/providers/Microsoft.ManagedIdentity/userAssignedIdentities/webapp-identity",
            "name": "webapp-identity",
            "type": "Microsoft.ManagedIdentity/userAssignedIdentities",
            "resource_group": "rg-identity",
            "properties": {
                "clientId": "12345678-1234-1234-1234-123456789012",
                "principalId": "87654321-4321-4321-4321-210987654321",
            },
        }

        # Mock discovery service
        mock_discovery = Mock(spec=AzureDiscoveryService)
        mock_discovery.discover_subscriptions = AsyncMock(return_value=[{"subscription_id": "sub1"}])
        mock_discovery.discover_resources_across_subscriptions = AsyncMock(return_value=[webapp])
        mock_discovery.fetch_resource_by_id = AsyncMock(return_value=identity)

        # Mock db_ops that tracks relationship creation
        mock_db_ops = Mock()
        mock_db_ops.check_resource_exists = Mock(return_value=False)
        mock_db_ops.create_resource_node = Mock(return_value=True)
        mock_db_ops.create_relationship = Mock(return_value=True)

        # Create dependency collector
        identity_rule = IdentityRule()
        dependency_collector = RelationshipDependencyCollector(
            discovery_service=mock_discovery,
            db_ops=mock_db_ops,
            relationship_rules=[identity_rule],
        )

        # Create tenant grapher
        tenant_grapher = AzureTenantGrapher(
            discovery_service=mock_discovery,
            db_ops=mock_db_ops,
            dependency_collector=dependency_collector,
        )

        # Act
        filter_config = FilterConfig(
            resource_group_names=["rg-apps"],
            enable_relationship_dependency_collection=True,
        )
        await tenant_grapher.build_graph(filter_config=filter_config)

        # Assert: Verify USES_IDENTITY relationship was created
        relationship_calls = mock_db_ops.create_relationship.call_args_list
        uses_identity_rels = [
            call for call in relationship_calls
            if len(call[0]) >= 2 and call[0][1] == "USES_IDENTITY"
        ]

        assert len(uses_identity_rels) > 0, "Should create USES_IDENTITY relationship"

        # Verify relationship connects webapp to identity
        rel = uses_identity_rels[0]
        assert webapp["id"] in str(rel), "Relationship should involve webapp"
        assert identity["id"] in str(rel), "Relationship should involve identity"


class TestPhase26Integration:
    """Tests for Phase 26 integration in build_graph workflow."""

    @pytest.mark.asyncio
    async def test_phase_26_integration_in_build_graph(self):
        """
        Test that Phase 26 (relationship-driven dependency collection)
        is properly integrated into build_graph() workflow.

        Workflow:
        1. Phase 1-10: Discover and filter resources
        2. Phase 26: Collect cross-RG dependencies via relationships (NEW)
        3. Phase 11-25: Process all resources (including dependencies)
        """
        # Setup: Single VM referencing cross-RG NIC
        vm = {
            "id": "/subscriptions/sub1/resourceGroups/rg-compute/providers/Microsoft.Compute/virtualMachines/vm1",
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "resource_group": "rg-compute",
            "properties": {
                "networkProfile": {
                    "networkInterfaces": [
                        {
                            "id": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic1"
                        }
                    ]
                },
            },
        }

        nic = {
            "id": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic1",
            "name": "nic1",
            "type": "Microsoft.Network/networkInterfaces",
            "resource_group": "rg-network",
        }

        # Mock discovery service
        mock_discovery = Mock(spec=AzureDiscoveryService)
        mock_discovery.discover_subscriptions = AsyncMock(return_value=[{"subscription_id": "sub1"}])
        mock_discovery.discover_resources_across_subscriptions = AsyncMock(return_value=[vm])
        mock_discovery.fetch_resource_by_id = AsyncMock(return_value=nic)

        # Mock db_ops
        mock_db_ops = Mock()
        mock_db_ops.check_resource_exists = Mock(return_value=False)

        # Track processing order
        processing_order = []

        def track_resource_processing(resource):
            processing_order.append(resource["name"])
            return True

        mock_db_ops.create_resource_node = Mock(side_effect=track_resource_processing)

        # Create dependency collector
        network_rule = NetworkRule()
        dependency_collector = RelationshipDependencyCollector(
            discovery_service=mock_discovery,
            db_ops=mock_db_ops,
            relationship_rules=[network_rule],
        )

        # Create tenant grapher
        tenant_grapher = AzureTenantGrapher(
            discovery_service=mock_discovery,
            db_ops=mock_db_ops,
            dependency_collector=dependency_collector,
        )

        # Act: Build graph
        filter_config = FilterConfig(
            resource_group_names=["rg-compute"],
            enable_relationship_dependency_collection=True,
        )
        await tenant_grapher.build_graph(filter_config=filter_config)

        # Assert: Both resources should be processed
        assert "vm1" in processing_order, "Should process filtered VM"
        assert "nic1" in processing_order, "Should process cross-RG dependency NIC"

        # Phase 26 should run BEFORE resource processing
        # (Dependencies must be collected before relationships are created)


class TestMultiPassDependencyCollection:
    """Tests for multi-pass dependency collection (transitive dependencies)."""

    @pytest.mark.asyncio
    async def test_multi_pass_collects_transitive_dependencies(self):
        """
        Test that multi-pass collection handles transitive dependencies.

        Scenario:
        - VM -> NIC (pass 1)
        - NIC -> Subnet (pass 2)
        - Subnet -> NSG (pass 3)
        """
        # Setup resources with chain of dependencies
        vm = {
            "id": "/subscriptions/sub1/resourceGroups/rg-compute/providers/Microsoft.Compute/virtualMachines/vm1",
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "resource_group": "rg-compute",
            "properties": {
                "networkProfile": {
                    "networkInterfaces": [
                        {"id": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic1"}
                    ]
                },
            },
        }

        nic = {
            "id": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic1",
            "name": "nic1",
            "type": "Microsoft.Network/networkInterfaces",
            "resource_group": "rg-network",
            "properties": {
                "ipConfigurations": [
                    {
                        "properties": {
                            "subnet": {
                                "id": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1"
                            }
                        }
                    }
                ]
            },
        }

        subnet = {
            "id": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1",
            "name": "subnet1",
            "type": "Microsoft.Network/virtualNetworks/subnets",
            "resource_group": "rg-network",
            "properties": {
                "networkSecurityGroup": {
                    "id": "/subscriptions/sub1/resourceGroups/rg-security/providers/Microsoft.Network/networkSecurityGroups/nsg1"
                }
            },
        }

        nsg = {
            "id": "/subscriptions/sub1/resourceGroups/rg-security/providers/Microsoft.Network/networkSecurityGroups/nsg1",
            "name": "nsg1",
            "type": "Microsoft.Network/networkSecurityGroups",
            "resource_group": "rg-security",
        }

        # Mock discovery service
        async def mock_fetch(resource_id):
            if "nic1" in resource_id:
                return nic
            elif "subnet1" in resource_id:
                return subnet
            elif "nsg1" in resource_id:
                return nsg
            return None

        mock_discovery = Mock(spec=AzureDiscoveryService)
        mock_discovery.discover_subscriptions = AsyncMock(return_value=[{"subscription_id": "sub1"}])
        mock_discovery.discover_resources_across_subscriptions = AsyncMock(return_value=[vm])
        mock_discovery.fetch_resource_by_id = AsyncMock(side_effect=mock_fetch)

        # Mock db_ops
        mock_db_ops = Mock()
        mock_db_ops.check_resource_exists = Mock(return_value=False)

        collected_resources = []

        def track_resources(resource):
            collected_resources.append(resource["name"])
            return True

        mock_db_ops.create_resource_node = Mock(side_effect=track_resources)

        # Create dependency collector with multi-pass enabled
        network_rule = NetworkRule()
        dependency_collector = RelationshipDependencyCollector(
            discovery_service=mock_discovery,
            db_ops=mock_db_ops,
            relationship_rules=[network_rule],
            max_passes=3,  # Enable multi-pass collection
        )

        # Create tenant grapher
        tenant_grapher = AzureTenantGrapher(
            discovery_service=mock_discovery,
            db_ops=mock_db_ops,
            dependency_collector=dependency_collector,
        )

        # Act
        filter_config = FilterConfig(
            resource_group_names=["rg-compute"],
            enable_relationship_dependency_collection=True,
        )
        await tenant_grapher.build_graph(filter_config=filter_config)

        # Assert: All transitive dependencies should be collected
        assert "vm1" in collected_resources, "Should collect filtered VM"
        assert "nic1" in collected_resources, "Should collect NIC (pass 1)"
        assert "subnet1" in collected_resources, "Should collect subnet (pass 2)"
        assert "nsg1" in collected_resources, "Should collect NSG (pass 3)"


class TestDisabledDependencyCollection:
    """Tests for when relationship-driven dependency collection is disabled."""

    @pytest.mark.asyncio
    async def test_dependency_collection_disabled_by_default(self):
        """Test that dependency collection is opt-in (disabled by default)."""
        # Setup: VM with cross-RG NIC reference
        vm = {
            "id": "/subscriptions/sub1/resourceGroups/rg-compute/providers/Microsoft.Compute/virtualMachines/vm1",
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "resource_group": "rg-compute",
            "properties": {
                "networkProfile": {
                    "networkInterfaces": [
                        {"id": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic1"}
                    ]
                },
            },
        }

        # Mock discovery service
        mock_discovery = Mock(spec=AzureDiscoveryService)
        mock_discovery.discover_subscriptions = AsyncMock(return_value=[{"subscription_id": "sub1"}])
        mock_discovery.discover_resources_across_subscriptions = AsyncMock(return_value=[vm])
        mock_discovery.fetch_resource_by_id = AsyncMock()

        # Mock db_ops
        mock_db_ops = Mock()
        mock_db_ops.check_resource_exists = Mock(return_value=False)
        mock_db_ops.create_resource_node = Mock(return_value=True)

        # Create tenant grapher WITHOUT dependency collector
        tenant_grapher = AzureTenantGrapher(
            discovery_service=mock_discovery,
            db_ops=mock_db_ops,
            dependency_collector=None,  # No collector
        )

        # Act: Build graph without enabling dependency collection
        filter_config = FilterConfig(
            resource_group_names=["rg-compute"],
            enable_relationship_dependency_collection=False,  # Explicitly disabled
        )
        await tenant_grapher.build_graph(filter_config=filter_config)

        # Assert: fetch_resource_by_id should NOT be called
        mock_discovery.fetch_resource_by_id.assert_not_called()
