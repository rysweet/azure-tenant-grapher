"""
Unit tests for RelationshipDependencyCollector service.

Tests verify that the collector correctly identifies missing dependencies
from relationship rules and fetches only the missing resources.

Following TDD methodology - these tests will FAIL until implementation is complete.
"""

import pytest
from typing import Any, Dict, List, Set
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from src.services.relationship_dependency_collector import RelationshipDependencyCollector
from src.models.filter_config import FilterConfig


class TestRelationshipDependencyCollectorInit:
    """Tests for RelationshipDependencyCollector initialization."""

    def test_collector_initialization(self):
        """Test that collector initializes with required dependencies."""
        mock_discovery_service = Mock()
        mock_db_ops = Mock()
        mock_relationship_rules = []

        collector = RelationshipDependencyCollector(
            discovery_service=mock_discovery_service,
            db_ops=mock_db_ops,
            relationship_rules=mock_relationship_rules,
        )

        assert collector.discovery_service == mock_discovery_service
        assert collector.db_ops == mock_db_ops
        assert collector.relationship_rules == mock_relationship_rules


class TestCollectMissingDependencies:
    """Tests for collecting missing dependencies from filtered resources."""

    @pytest.mark.asyncio
    async def test_collect_missing_dependencies_fetches_missing_only(self):
        """Test that collector only fetches dependencies that don't exist in graph."""
        # Setup: VM references NIC in different RG
        filtered_resources = [
            {
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
                    }
                },
            }
        ]

        # Mock relationship rule that extracts NIC ID
        mock_rule = Mock()
        mock_rule.applies.return_value = True
        mock_rule.extract_target_ids.return_value = {
            "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic1"
        }

        # Mock discovery service
        mock_discovery = Mock()
        mock_discovery.fetch_resource_by_id = AsyncMock(
            return_value={
                "id": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic1",
                "name": "nic1",
                "type": "Microsoft.Network/networkInterfaces",
                "resource_group": "rg-network",
            }
        )

        # Mock db_ops that reports NIC doesn't exist
        mock_db_ops = Mock()
        mock_db_ops.check_resource_exists = Mock(return_value=False)

        collector = RelationshipDependencyCollector(
            discovery_service=mock_discovery,
            db_ops=mock_db_ops,
            relationship_rules=[mock_rule],
        )

        filter_config = FilterConfig(resource_group_names=["rg-compute"])

        # Act
        missing_resources = await collector.collect_missing_dependencies(
            filtered_resources=filtered_resources,
            filter_config=filter_config,
        )

        # Assert
        assert len(missing_resources) == 1, "Should fetch the missing NIC"
        assert missing_resources[0]["name"] == "nic1"
        assert missing_resources[0]["resource_group"] == "rg-network"

        # Verify fetch was called for the missing resource
        mock_discovery.fetch_resource_by_id.assert_called_once_with(
            "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic1"
        )

    @pytest.mark.asyncio
    async def test_collect_missing_dependencies_skips_existing(self):
        """Test that collector skips dependencies that already exist in graph."""
        # Setup: VM references NIC
        filtered_resources = [
            {
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
                    }
                },
            }
        ]

        # Mock relationship rule
        mock_rule = Mock()
        mock_rule.applies.return_value = True
        mock_rule.extract_target_ids.return_value = {
            "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic1"
        }

        # Mock discovery service (should NOT be called if resource exists)
        mock_discovery = Mock()
        mock_discovery.fetch_resource_by_id = AsyncMock()

        # Mock db_ops that reports NIC ALREADY exists
        mock_db_ops = Mock()
        mock_db_ops.check_resource_exists = Mock(return_value=True)

        collector = RelationshipDependencyCollector(
            discovery_service=mock_discovery,
            db_ops=mock_db_ops,
            relationship_rules=[mock_rule],
        )

        filter_config = FilterConfig(resource_group_names=["rg-compute"])

        # Act
        missing_resources = await collector.collect_missing_dependencies(
            filtered_resources=filtered_resources,
            filter_config=filter_config,
        )

        # Assert
        assert len(missing_resources) == 0, "Should skip existing resource"

        # Verify fetch was NOT called since resource exists
        mock_discovery.fetch_resource_by_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_collect_missing_dependencies_handles_fetch_failures(self):
        """Test that collector gracefully handles failures when fetching resources."""
        # Setup: VM references NIC that fails to fetch
        filtered_resources = [
            {
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
                    }
                },
            }
        ]

        # Mock relationship rule
        mock_rule = Mock()
        mock_rule.applies.return_value = True
        mock_rule.extract_target_ids.return_value = {
            "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic1"
        }

        # Mock discovery service that raises exception
        mock_discovery = Mock()
        mock_discovery.fetch_resource_by_id = AsyncMock(
            side_effect=Exception("Resource not found or insufficient permissions")
        )

        # Mock db_ops
        mock_db_ops = Mock()
        mock_db_ops.check_resource_exists = Mock(return_value=False)

        collector = RelationshipDependencyCollector(
            discovery_service=mock_discovery,
            db_ops=mock_db_ops,
            relationship_rules=[mock_rule],
        )

        filter_config = FilterConfig(resource_group_names=["rg-compute"])

        # Act - should NOT raise exception
        missing_resources = await collector.collect_missing_dependencies(
            filtered_resources=filtered_resources,
            filter_config=filter_config,
        )

        # Assert
        assert len(missing_resources) == 0, "Should return empty list on fetch failure"
        # Should log warning but not crash

    @pytest.mark.asyncio
    async def test_collect_missing_dependencies_empty_targets(self):
        """Test that collector handles resources with no external dependencies."""
        # Setup: Resource with no external dependencies
        filtered_resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg-storage/providers/Microsoft.Storage/storageAccounts/storage1",
                "name": "storage1",
                "type": "Microsoft.Storage/storageAccounts",
                "resource_group": "rg-storage",
            }
        ]

        # Mock relationship rule that returns empty set
        mock_rule = Mock()
        mock_rule.applies.return_value = True
        mock_rule.extract_target_ids.return_value = set()

        # Mock discovery service (should NOT be called)
        mock_discovery = Mock()
        mock_discovery.fetch_resource_by_id = AsyncMock()

        mock_db_ops = Mock()

        collector = RelationshipDependencyCollector(
            discovery_service=mock_discovery,
            db_ops=mock_db_ops,
            relationship_rules=[mock_rule],
        )

        filter_config = FilterConfig(resource_group_names=["rg-storage"])

        # Act
        missing_resources = await collector.collect_missing_dependencies(
            filtered_resources=filtered_resources,
            filter_config=filter_config,
        )

        # Assert
        assert len(missing_resources) == 0, "Should return empty list for resources with no dependencies"
        mock_discovery.fetch_resource_by_id.assert_not_called()


class TestCheckExistingNodes:
    """Tests for checking which dependency nodes already exist in Neo4j."""

    def test_check_existing_nodes_queries_neo4j_correctly(self):
        """Test that check_existing_nodes() queries Neo4j efficiently."""
        target_ids = {
            "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic1",
            "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic2",
            "/subscriptions/sub1/resourceGroups/rg-storage/providers/Microsoft.Storage/storageAccounts/storage1",
        }

        # Mock db_ops with session manager
        mock_session = Mock()
        mock_session.run.return_value.data.return_value = [
            {"id": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic1"},
            # nic2 and storage1 are missing
        ]

        mock_context_manager = MagicMock()
        mock_context_manager.__enter__.return_value = mock_session
        mock_context_manager.__exit__.return_value = False

        mock_session_manager = Mock()
        mock_session_manager.session.return_value = mock_context_manager

        mock_db_ops = Mock(spec=['session_manager'])
        mock_db_ops.session_manager = mock_session_manager

        collector = RelationshipDependencyCollector(
            discovery_service=Mock(),
            db_ops=mock_db_ops,
            relationship_rules=[],
        )

        # Act
        existing_ids = collector.check_existing_nodes(target_ids)

        # Assert
        assert len(existing_ids) == 1, "Should find 1 existing resource"
        assert "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic1" in existing_ids

        # Verify query was executed with all IDs
        mock_session.run.assert_called_once()
        call_args = mock_session.run.call_args
        assert "UNWIND" in call_args[0][0], "Should use UNWIND for batch query"
        assert call_args[1]["target_ids"] == list(target_ids), "Should pass all target IDs"


class TestFetchResourcesByIds:
    """Tests for fetching missing resources in parallel."""

    @pytest.mark.asyncio
    async def test_fetch_resources_by_ids_parallel_execution(self):
        """Test that fetch_resources_by_ids() fetches multiple resources in parallel."""
        missing_ids = {
            "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic1",
            "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic2",
            "/subscriptions/sub1/resourceGroups/rg-storage/providers/Microsoft.Storage/storageAccounts/storage1",
        }

        # Mock discovery service
        async def mock_fetch(resource_id):
            # Simulate different resources
            if "nic1" in resource_id:
                return {"id": resource_id, "name": "nic1", "type": "Microsoft.Network/networkInterfaces"}
            elif "nic2" in resource_id:
                return {"id": resource_id, "name": "nic2", "type": "Microsoft.Network/networkInterfaces"}
            elif "storage1" in resource_id:
                return {"id": resource_id, "name": "storage1", "type": "Microsoft.Storage/storageAccounts"}
            return None

        mock_discovery = Mock()
        mock_discovery.fetch_resource_by_id = AsyncMock(side_effect=mock_fetch)

        collector = RelationshipDependencyCollector(
            discovery_service=mock_discovery,
            db_ops=Mock(),
            relationship_rules=[],
        )

        # Act
        resources = await collector.fetch_resources_by_ids(missing_ids)

        # Assert
        assert len(resources) == 3, "Should fetch all 3 resources"
        assert any(r["name"] == "nic1" for r in resources)
        assert any(r["name"] == "nic2" for r in resources)
        assert any(r["name"] == "storage1" for r in resources)

        # Verify all fetch calls were made
        assert mock_discovery.fetch_resource_by_id.call_count == 3


class TestIntegrationScenarios:
    """Integration-style tests for complex dependency scenarios."""

    @pytest.mark.asyncio
    async def test_hub_spoke_topology_dependencies(self):
        """
        Test collecting dependencies in hub-spoke network topology.

        Scenario:
        - Filter by spoke RG (rg-spoke-prod)
        - VM in spoke references NIC in hub RG (rg-hub-network)
        - NIC in hub references subnet in hub VNet
        - Should collect both NIC and subnet as dependencies
        """
        # Spoke VM referencing hub NIC
        filtered_resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg-spoke-prod/providers/Microsoft.Compute/virtualMachines/spoke-vm1",
                "name": "spoke-vm1",
                "type": "Microsoft.Compute/virtualMachines",
                "resource_group": "rg-spoke-prod",
                "properties": {
                    "networkProfile": {
                        "networkInterfaces": [
                            {
                                "id": "/subscriptions/sub1/resourceGroups/rg-hub-network/providers/Microsoft.Network/networkInterfaces/hub-nic1"
                            }
                        ]
                    }
                },
            }
        ]

        # Mock relationship rule for network dependencies
        mock_rule = Mock()
        mock_rule.applies.return_value = True

        def extract_targets(resource):
            if resource["type"] == "Microsoft.Compute/virtualMachines":
                # VM -> NIC
                return {
                    "/subscriptions/sub1/resourceGroups/rg-hub-network/providers/Microsoft.Network/networkInterfaces/hub-nic1"
                }
            elif resource["type"] == "Microsoft.Network/networkInterfaces":
                # NIC -> Subnet
                return {
                    "/subscriptions/sub1/resourceGroups/rg-hub-network/providers/Microsoft.Network/virtualNetworks/hub-vnet/subnets/hub-subnet1"
                }
            return set()

        mock_rule.extract_target_ids.side_effect = extract_targets

        # Mock discovery service
        async def mock_fetch(resource_id):
            if "hub-nic1" in resource_id:
                return {
                    "id": resource_id,
                    "name": "hub-nic1",
                    "type": "Microsoft.Network/networkInterfaces",
                    "resource_group": "rg-hub-network",
                    "properties": {
                        "ipConfigurations": [
                            {
                                "subnet": {
                                    "id": "/subscriptions/sub1/resourceGroups/rg-hub-network/providers/Microsoft.Network/virtualNetworks/hub-vnet/subnets/hub-subnet1"
                                }
                            }
                        ]
                    },
                }
            elif "hub-subnet1" in resource_id:
                return {
                    "id": resource_id,
                    "name": "hub-subnet1",
                    "type": "Microsoft.Network/virtualNetworks/subnets",
                    "resource_group": "rg-hub-network",
                }
            return None

        mock_discovery = Mock()
        mock_discovery.fetch_resource_by_id = AsyncMock(side_effect=mock_fetch)

        # Mock db_ops - nothing exists initially
        mock_db_ops = Mock()
        mock_db_ops.check_resource_exists = Mock(return_value=False)

        collector = RelationshipDependencyCollector(
            discovery_service=mock_discovery,
            db_ops=mock_db_ops,
            relationship_rules=[mock_rule],
        )

        filter_config = FilterConfig(resource_group_names=["rg-spoke-prod"])

        # Act - First pass collects NIC
        missing_resources = await collector.collect_missing_dependencies(
            filtered_resources=filtered_resources,
            filter_config=filter_config,
        )

        # Assert - Should collect hub NIC as dependency
        assert len(missing_resources) >= 1, "Should collect at least hub NIC"
        assert any(r["name"] == "hub-nic1" for r in missing_resources)

        # Second pass: Include collected NIC in resources and collect its dependencies
        all_resources = filtered_resources + missing_resources
        missing_resources_pass2 = await collector.collect_missing_dependencies(
            filtered_resources=all_resources,
            filter_config=filter_config,
        )

        # Assert - Should collect hub subnet as transitive dependency
        # (This demonstrates multi-pass dependency collection)
        assert any(r["name"] == "hub-subnet1" for r in missing_resources_pass2), (
            "Should collect hub subnet as transitive dependency"
        )
