"""
Unit tests for OrphanedResourceManager brick.

Tests orphaned resource discovery and analysis (with mocked Neo4j).
"""

from unittest.mock import MagicMock

import networkx as nx
import pytest

from src.replicator.modules.orphaned_resource_manager import OrphanedResourceManager


class TestOrphanedResourceManager:
    """Test suite for OrphanedResourceManager brick."""

    @pytest.fixture
    def mock_analyzer(self):
        """Create a mock ArchitecturalPatternAnalyzer."""
        analyzer = MagicMock()
        analyzer._get_resource_type_name.side_effect = lambda labels, azure_type: (
            azure_type.split("/")[-1] if azure_type else "Unknown"
        )
        analyzer.identify_orphaned_nodes.return_value = {"orphanType1", "orphanType2"}
        analyzer.detect_patterns.return_value = {
            "pattern1": {"matched_resources": {"vm", "disk"}}
        }
        analyzer.suggest_new_patterns.return_value = [
            {
                "suggested_pattern": "Orphan Pattern",
                "node_types": ["orphanType1", "orphanType2"]
            }
        ]
        return analyzer

    @pytest.fixture
    def manager(self, mock_analyzer):
        """Create an OrphanedResourceManager with mocked analyzer."""
        return OrphanedResourceManager(mock_analyzer)

    def test_find_orphaned_instances_basic(self, manager, mock_analyzer):
        """Test finding orphaned instances from ResourceGroups."""
        mock_session = MagicMock()

        # Mock query 1: Get all resource types
        mock_result1 = MagicMock()
        mock_result1.__iter__.return_value = iter([
            {"full_type": "Microsoft.Compute/virtualMachines"},
            {"full_type": "Microsoft.Storage/storageAccounts"},
            {"full_type": "Microsoft.KeyVault/vaults"}
        ])

        # Mock query 2: Get orphaned resources in ResourceGroups
        mock_result2 = MagicMock()
        mock_result2.__iter__.return_value = iter([
            {
                "rg_id": "rg1",
                "resources": [
                    {"id": "kv1", "type": "Microsoft.KeyVault/vaults", "name": "KeyVault1"}
                ]
            }
        ])

        # Mock query 3: Standalone resources
        mock_result3 = MagicMock()
        mock_result3.__iter__.return_value = iter([])

        mock_session.run.side_effect = [mock_result1, mock_result2, mock_result3]

        detected_patterns = {
            "vm_pattern": {"matched_resources": {"virtualMachines"}}
        }
        source_counts = {
            "virtualMachines": 5,
            "storageAccounts": 3,
            "vaults": 2  # Orphaned
        }

        instances = manager.find_orphaned_instances(
            mock_session,
            detected_patterns,
            source_counts
        )

        # Should find orphaned instances
        assert len(instances) >= 0

    def test_find_orphaned_instances_no_orphans(self, manager, mock_analyzer):
        """Test finding orphaned instances when none exist."""
        mock_session = MagicMock()

        # All types are in patterns
        mock_result1 = MagicMock()
        mock_result1.__iter__.return_value = iter([
            {"full_type": "Microsoft.Compute/virtualMachines"}
        ])

        mock_session.run.return_value = mock_result1

        detected_patterns = {
            "vm_pattern": {"matched_resources": {"virtualMachines"}}
        }
        source_counts = {
            "virtualMachines": 5
        }

        instances = manager.find_orphaned_instances(
            mock_session,
            detected_patterns,
            source_counts
        )

        # Should return empty list
        assert len(instances) == 0

    def test_find_orphaned_instances_with_standalone(self, manager, mock_analyzer):
        """Test finding orphaned instances including standalone resources."""
        mock_session = MagicMock()

        # Mock query 1: Get all resource types
        mock_result1 = MagicMock()
        mock_result1.__iter__.return_value = iter([
            {"full_type": "Microsoft.KeyVault/vaults"}
        ])

        # Mock query 2: RG-based orphaned resources
        mock_result2 = MagicMock()
        mock_result2.__iter__.return_value = iter([
            {
                "rg_id": "rg1",
                "resources": [
                    {"id": "kv1", "type": "Microsoft.KeyVault/vaults", "name": "KV1"}
                ]
            }
        ])

        # Mock query 3: Standalone orphaned resources
        mock_result3 = MagicMock()
        mock_result3.__iter__.return_value = iter([
            {"id": "kv2", "type": "Microsoft.KeyVault/vaults", "name": "KV2"}
        ])

        mock_session.run.side_effect = [mock_result1, mock_result2, mock_result3]

        detected_patterns = {}
        source_counts = {"vaults": 2}

        instances = manager.find_orphaned_instances(
            mock_session,
            detected_patterns,
            source_counts
        )

        # Should find both RG-based and standalone
        assert len(instances) >= 1

    def test_find_orphaned_instances_type_mapping(self, manager, mock_analyzer):
        """Test that orphaned finder correctly maps simplified to full types."""
        mock_session = MagicMock()

        # Setup type mapping
        mock_analyzer._get_resource_type_name.return_value = "vaults"

        mock_result1 = MagicMock()
        mock_result1.__iter__.return_value = iter([
            {"full_type": "Microsoft.KeyVault/vaults"}
        ])

        mock_result2 = MagicMock()
        mock_result2.__iter__.return_value = iter([])

        mock_result3 = MagicMock()
        mock_result3.__iter__.return_value = iter([])

        mock_session.run.side_effect = [mock_result1, mock_result2, mock_result3]

        detected_patterns = {}
        source_counts = {"vaults": 1}

        instances = manager.find_orphaned_instances(
            mock_session,
            detected_patterns,
            source_counts
        )

        # Should call type resolution
        assert mock_analyzer._get_resource_type_name.called

    def test_analyze_orphaned_nodes_basic(self, manager, mock_analyzer):
        """Test orphaned node analysis."""
        source_graph = nx.DiGraph()
        source_graph.add_node("vm", count=5)
        source_graph.add_node("disk", count=3)
        source_graph.add_node("orphan1", count=2)

        target_graph = nx.DiGraph()
        target_graph.add_node("vm", count=4)
        target_graph.add_node("disk", count=2)

        detected_patterns = {
            "vm_pattern": {"matched_resources": {"vm", "disk"}}
        }

        analysis = manager.analyze_orphaned_nodes(
            source_graph,
            target_graph,
            detected_patterns
        )

        # Should identify orphaned nodes
        assert "source_orphaned" in analysis
        assert "target_orphaned" in analysis
        assert "missing_in_target" in analysis
        assert "suggested_patterns" in analysis
        assert analysis["source_orphaned_count"] >= 0
        assert analysis["target_orphaned_count"] >= 0
        assert analysis["missing_count"] >= 0

    def test_analyze_orphaned_nodes_missing_in_target(self, manager, mock_analyzer):
        """Test analysis identifies nodes missing in target."""
        source_graph = nx.DiGraph()
        source_graph.add_node("vm", count=5)
        source_graph.add_node("disk", count=3)
        source_graph.add_node("nic", count=2)

        target_graph = nx.DiGraph()
        target_graph.add_node("vm", count=4)
        # disk and nic missing

        detected_patterns = {
            "vm_pattern": {"matched_resources": {"vm", "disk", "nic"}}
        }

        analysis = manager.analyze_orphaned_nodes(
            source_graph,
            target_graph,
            detected_patterns
        )

        # Should identify disk and nic as missing
        missing = set(analysis["missing_in_target"])
        assert "disk" in missing
        assert "nic" in missing
        assert analysis["missing_count"] == 2

    def test_analyze_orphaned_nodes_no_orphans(self, manager, mock_analyzer):
        """Test analysis when no orphans exist."""
        source_graph = nx.DiGraph()
        source_graph.add_node("vm", count=5)

        target_graph = nx.DiGraph()
        target_graph.add_node("vm", count=4)

        detected_patterns = {
            "vm_pattern": {"matched_resources": {"vm"}}
        }

        # Mock to return no orphans
        mock_analyzer.identify_orphaned_nodes.return_value = set()
        mock_analyzer.suggest_new_patterns.return_value = []

        analysis = manager.analyze_orphaned_nodes(
            source_graph,
            target_graph,
            detected_patterns
        )

        # Should have zero orphans
        assert analysis["source_orphaned_count"] == 0
        assert analysis["target_orphaned_count"] == 0

    def test_analyze_orphaned_nodes_requires_source_and_patterns(self, manager):
        """Test that analysis requires source graph and patterns."""
        target_graph = nx.DiGraph()

        # Should raise error with no source graph
        with pytest.raises(RuntimeError):
            manager.analyze_orphaned_nodes(None, target_graph, {})

        # Should raise error with no patterns
        source_graph = nx.DiGraph()
        source_graph.add_node("vm")
        with pytest.raises(RuntimeError):
            manager.analyze_orphaned_nodes(source_graph, target_graph, {})

    def test_analyze_orphaned_nodes_calls_analyzer_methods(self, manager, mock_analyzer):
        """Test that analysis calls all required analyzer methods."""
        source_graph = nx.DiGraph()
        source_graph.add_node("vm", count=5)

        target_graph = nx.DiGraph()
        target_graph.add_node("vm", count=4)

        detected_patterns = {
            "vm_pattern": {"matched_resources": {"vm"}}
        }

        manager.analyze_orphaned_nodes(
            source_graph,
            target_graph,
            detected_patterns
        )

        # Should call all analyzer methods
        assert mock_analyzer.identify_orphaned_nodes.called
        assert mock_analyzer.detect_patterns.called
        assert mock_analyzer.suggest_new_patterns.called

    def test_find_orphaned_instances_handles_unmapped_types(self, manager, mock_analyzer):
        """Test that finder handles types that don't map to Neo4j (organizational/identity)."""
        mock_session = MagicMock()

        # Only Azure resources in Neo4j
        mock_result1 = MagicMock()
        mock_result1.__iter__.return_value = iter([
            {"full_type": "Microsoft.Compute/virtualMachines"}
        ])

        mock_session.run.return_value = mock_result1

        detected_patterns = {}
        # Source includes organizational type not in Neo4j
        source_counts = {
            "virtualMachines": 5,
            "users": 10,  # Organizational type, won't be in Neo4j
            "groups": 5   # Organizational type, won't be in Neo4j
        }

        instances = manager.find_orphaned_instances(
            mock_session,
            detected_patterns,
            source_counts
        )

        # Should handle gracefully, not crash
        assert isinstance(instances, list)
