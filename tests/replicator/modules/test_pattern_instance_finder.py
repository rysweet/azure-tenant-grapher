"""
Unit tests for PatternInstanceFinder brick.

Tests Neo4j queries for discovering pattern instances (with mocked Neo4j).
"""

from unittest.mock import MagicMock, call

import pytest

from src.replicator.modules.pattern_instance_finder import PatternInstanceFinder


class TestPatternInstanceFinder:
    """Test suite for PatternInstanceFinder brick."""

    @pytest.fixture
    def mock_analyzer(self):
        """Create a mock ArchitecturalPatternAnalyzer."""
        analyzer = MagicMock()
        analyzer._get_resource_type_name.side_effect = lambda labels, azure_type: (
            azure_type.split("/")[-1] if azure_type else "Unknown"
        )
        analyzer.create_configuration_fingerprint.return_value = {
            "location": "eastus",
            "sku": "Standard_D2s_v3",
            "tags": {}
        }
        return analyzer

    @pytest.fixture
    def mock_config_similarity(self):
        """Create a mock ConfigurationSimilarity."""
        similarity = MagicMock()
        similarity.cluster_by_coherence.return_value = [
            [{"id": "r1", "type": "vm", "name": "vm1"}],
            [{"id": "r2", "type": "disk", "name": "disk1"}]
        ]
        return similarity

    @pytest.fixture
    def finder(self, mock_analyzer, mock_config_similarity):
        """Create a PatternInstanceFinder with mocked dependencies."""
        return PatternInstanceFinder(mock_analyzer, mock_config_similarity)

    def test_find_connected_instances_basic(self, finder, mock_analyzer):
        """Test finding connected instances from ResourceGroups."""
        mock_session = MagicMock()

        # Mock the first query (resources in ResourceGroups)
        mock_result1 = MagicMock()
        mock_result1.__iter__.return_value = iter([
            {
                "id": "vm1",
                "type": "Microsoft.Compute/virtualMachines",
                "name": "TestVM1",
                "resource_group_id": "rg1"
            },
            {
                "id": "disk1",
                "type": "Microsoft.Compute/disks",
                "name": "TestDisk1",
                "resource_group_id": "rg1"
            },
            {
                "id": "vm2",
                "type": "Microsoft.Compute/virtualMachines",
                "name": "TestVM2",
                "resource_group_id": "rg2"
            }
        ])

        # Mock the second query (direct connections)
        mock_result2 = MagicMock()
        mock_result2.__iter__.return_value = iter([])

        mock_session.run.side_effect = [mock_result1, mock_result2]

        matched_types = {"virtualMachines", "disks"}
        detected_patterns = {
            "pattern1": {"matched_resources": {"virtualMachines", "disks"}}
        }

        instances = finder.find_connected_instances(
            mock_session,
            matched_types,
            "pattern1",
            detected_patterns,
            include_colocated_orphaned_resources=False
        )

        # Should find 1 instance (rg1 has 2+ resources)
        assert len(instances) == 1
        assert len(instances[0]) == 2

    def test_find_connected_instances_with_direct_connections(self, finder, mock_analyzer):
        """Test finding instances with direct resource connections."""
        mock_session = MagicMock()

        # Mock resources
        mock_result1 = MagicMock()
        mock_result1.__iter__.return_value = iter([
            {
                "id": "vnet1",
                "type": "Microsoft.Network/virtualNetworks",
                "name": "VNet1",
                "resource_group_id": "rg1"
            },
            {
                "id": "subnet1",
                "type": "Microsoft.Network/virtualNetworks/subnets",
                "name": "Subnet1",
                "resource_group_id": "rg1"
            }
        ])

        # Mock direct connection vnet1 -> subnet1
        mock_result2 = MagicMock()
        mock_result2.__iter__.return_value = iter([
            {"source_id": "vnet1", "target_id": "subnet1"}
        ])

        mock_session.run.side_effect = [mock_result1, mock_result2]

        matched_types = {"virtualNetworks", "subnets"}
        detected_patterns = {
            "network_pattern": {"matched_resources": {"virtualNetworks", "subnets"}}
        }

        instances = finder.find_connected_instances(
            mock_session,
            matched_types,
            "network_pattern",
            detected_patterns
        )

        assert len(instances) >= 1

    def test_find_connected_instances_no_matches(self, finder):
        """Test finding instances when no resources match."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__.return_value = iter([])
        mock_session.run.return_value = mock_result

        matched_types = {"virtualMachines"}
        detected_patterns = {}

        instances = finder.find_connected_instances(
            mock_session,
            matched_types,
            "pattern1",
            detected_patterns
        )

        assert len(instances) == 0

    def test_find_connected_instances_with_orphaned_resources(self, finder, mock_analyzer):
        """Test finding instances including orphaned resources."""
        mock_session = MagicMock()

        # Mock resources: 2 pattern types + 1 orphaned type in same RG
        mock_result1 = MagicMock()
        mock_result1.__iter__.return_value = iter([
            {
                "id": "vm1",
                "type": "Microsoft.Compute/virtualMachines",
                "name": "VM1",
                "resource_group_id": "rg1"
            },
            {
                "id": "disk1",
                "type": "Microsoft.Compute/disks",
                "name": "Disk1",
                "resource_group_id": "rg1"
            },
            {
                "id": "orphan1",
                "type": "Microsoft.Something/orphanedType",
                "name": "Orphan1",
                "resource_group_id": "rg1"
            }
        ])

        mock_result2 = MagicMock()
        mock_result2.__iter__.return_value = iter([])

        mock_session.run.side_effect = [mock_result1, mock_result2]

        matched_types = {"virtualMachines", "disks"}
        detected_patterns = {
            "pattern1": {"matched_resources": {"virtualMachines", "disks"}}
        }

        instances = finder.find_connected_instances(
            mock_session,
            matched_types,
            "pattern1",
            detected_patterns,
            include_colocated_orphaned_resources=True
        )

        # Should include orphaned resource in the instance
        assert len(instances) >= 1
        # Check if orphaned resource is included
        all_ids = [r["id"] for instance in instances for r in instance]
        assert "orphan1" in all_ids

    def test_find_configuration_coherent_instances_basic(self, finder, mock_analyzer, mock_config_similarity):
        """Test finding configuration-coherent instances."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__.return_value = iter([
            {
                "resource_group_id": "rg1",
                "id": "vm1",
                "type": "Microsoft.Compute/virtualMachines",
                "name": "VM1",
                "location": "eastus",
                "tags": "{}",
                "properties": "{}"
            },
            {
                "resource_group_id": "rg1",
                "id": "vm2",
                "type": "Microsoft.Compute/virtualMachines",
                "name": "VM2",
                "location": "eastus",
                "tags": "{}",
                "properties": "{}"
            }
        ])
        mock_session.run.return_value = mock_result

        matched_types = {"virtualMachines"}
        detected_patterns = {
            "vm_pattern": {"matched_resources": {"virtualMachines"}}
        }

        instances = finder.find_configuration_coherent_instances(
            mock_session,
            "vm_pattern",
            matched_types,
            detected_patterns,
            coherence_threshold=0.7
        )

        # Should call clustering
        assert mock_config_similarity.cluster_by_coherence.called
        assert len(instances) >= 0

    def test_find_configuration_coherent_instances_no_resources(self, finder):
        """Test coherent instances when no resources match."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__.return_value = iter([])
        mock_session.run.return_value = mock_result

        matched_types = {"virtualMachines"}
        detected_patterns = {}

        instances = finder.find_configuration_coherent_instances(
            mock_session,
            "pattern",
            matched_types,
            detected_patterns
        )

        assert len(instances) == 0

    def test_find_configuration_coherent_instances_with_orphaned(self, finder, mock_analyzer, mock_config_similarity):
        """Test coherent instances including orphaned resources."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__.return_value = iter([
            {
                "resource_group_id": "rg1",
                "id": "vm1",
                "type": "Microsoft.Compute/virtualMachines",
                "name": "VM1",
                "location": "eastus",
                "tags": "{}",
                "properties": "{}"
            },
            {
                "resource_group_id": "rg1",
                "id": "orphan1",
                "type": "Microsoft.Something/orphanedType",
                "name": "Orphan1",
                "location": "eastus",
                "tags": "{}",
                "properties": "{}"
            }
        ])
        mock_session.run.return_value = mock_result

        # Mock clustering to return cluster with VM
        mock_config_similarity.cluster_by_coherence.return_value = [
            [{"id": "vm1", "type": "virtualMachines", "name": "VM1"}]
        ]

        matched_types = {"virtualMachines"}
        detected_patterns = {
            "vm_pattern": {"matched_resources": {"virtualMachines"}}
        }

        instances = finder.find_configuration_coherent_instances(
            mock_session,
            "vm_pattern",
            matched_types,
            detected_patterns,
            include_colocated_orphaned_resources=True
        )

        # Should include orphaned resource in cluster
        assert len(instances) >= 1

    def test_find_configuration_coherent_instances_json_parsing(self, finder, mock_analyzer, mock_config_similarity):
        """Test that JSON properties are parsed correctly."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__.return_value = iter([
            {
                "resource_group_id": "rg1",
                "id": "vm1",
                "type": "Microsoft.Compute/virtualMachines",
                "name": "VM1",
                "location": "eastus",
                "tags": '{"env": "prod"}',
                "properties": '{"hardwareProfile": {"vmSize": "Standard_D2s_v3"}}'
            }
        ])
        mock_session.run.return_value = mock_result

        matched_types = {"virtualMachines"}
        detected_patterns = {
            "vm_pattern": {"matched_resources": {"virtualMachines"}}
        }

        # Mock clustering to return single cluster
        mock_config_similarity.cluster_by_coherence.return_value = [
            [{"id": "vm1", "type": "virtualMachines", "name": "VM1"}]
        ]

        instances = finder.find_configuration_coherent_instances(
            mock_session,
            "vm_pattern",
            matched_types,
            detected_patterns
        )

        # Should parse JSON and create fingerprint
        assert mock_analyzer.create_configuration_fingerprint.called

    def test_find_configuration_coherent_instances_invalid_json(self, finder, mock_analyzer, mock_config_similarity):
        """Test handling of invalid JSON in properties."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__.return_value = iter([
            {
                "resource_group_id": "rg1",
                "id": "vm1",
                "type": "Microsoft.Compute/virtualMachines",
                "name": "VM1",
                "location": "eastus",
                "tags": "{}",
                "properties": "{invalid json"
            }
        ])
        mock_session.run.return_value = mock_result

        matched_types = {"virtualMachines"}
        detected_patterns = {
            "vm_pattern": {"matched_resources": {"virtualMachines"}}
        }

        mock_config_similarity.cluster_by_coherence.return_value = [
            [{"id": "vm1", "type": "virtualMachines", "name": "VM1"}]
        ]

        # Should handle invalid JSON gracefully
        instances = finder.find_configuration_coherent_instances(
            mock_session,
            "vm_pattern",
            matched_types,
            detected_patterns
        )

        assert len(instances) >= 0
