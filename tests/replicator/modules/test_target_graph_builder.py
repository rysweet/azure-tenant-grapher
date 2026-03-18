"""
Unit tests for TargetGraphBuilder brick.

Tests graph construction from instances (with mocked Neo4j).
"""

from unittest.mock import MagicMock, patch

import networkx as nx
import pytest

from src.replicator.modules.target_graph_builder import TargetGraphBuilder


class TestTargetGraphBuilder:
    """Test suite for TargetGraphBuilder brick."""

    @pytest.fixture
    def mock_analyzer(self):
        """Create a mock ArchitecturalPatternAnalyzer."""
        analyzer = MagicMock()
        analyzer.aggregate_relationships.return_value = [
            {
                "source_type": "sites",
                "target_type": "serverFarms",
                "rel_type": "USES",
                "frequency": 5
            }
        ]
        return analyzer

    @pytest.fixture
    def builder(self, mock_analyzer):
        """Create a TargetGraphBuilder with mocked dependencies."""
        return TargetGraphBuilder(
            analyzer=mock_analyzer,
            neo4j_uri="bolt://localhost:7687",
            neo4j_user="neo4j",
            neo4j_password="password",  # pragma: allowlist secret
        )

    def test_build_from_instances_empty(self, builder):
        """Test building graph from empty instance list."""
        selected_instances = []

        graph = builder.build_from_instances(selected_instances)

        # Should return empty graph
        assert graph.number_of_nodes() == 0
        assert graph.number_of_edges() == 0

    @patch('src.replicator.modules.target_graph_builder.GraphDatabase')
    def test_build_from_instances_basic(self, mock_graph_db, builder, mock_analyzer):
        """Test building graph from basic instances."""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = MagicMock()

        # Mock Neo4j query result
        mock_result.__iter__.return_value = iter([
            {
                "source_labels": ["Resource", "Original"],
                "source_type": "Microsoft.Web/sites",
                "rel_type": "USES",
                "target_labels": ["Resource", "Original"],
                "target_type": "Microsoft.Web/serverFarms"
            }
        ])

        mock_session.run.return_value = mock_result
        mock_session.__enter__.return_value = mock_session
        mock_session.__exit__.return_value = None
        mock_driver.session.return_value = mock_session
        mock_graph_db.driver.return_value = mock_driver

        selected_instances = [
            ("web_app", [
                {"id": "site1", "type": "sites"},
                {"id": "farm1", "type": "serverFarms"}
            ])
        ]

        graph = builder.build_from_instances(selected_instances)

        # Should have nodes for both resource types
        assert graph.number_of_nodes() >= 2
        assert "sites" in graph.nodes()
        assert "serverFarms" in graph.nodes()

        # Should close driver
        mock_driver.close.assert_called_once()

    @patch('src.replicator.modules.target_graph_builder.GraphDatabase')
    def test_build_from_instances_multiple_patterns(self, mock_graph_db, builder, mock_analyzer):
        """Test building graph from multiple pattern instances."""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = MagicMock()

        mock_result.__iter__.return_value = iter([])
        mock_session.run.return_value = mock_result
        mock_session.__enter__.return_value = mock_session
        mock_session.__exit__.return_value = None
        mock_driver.session.return_value = mock_session
        mock_graph_db.driver.return_value = mock_driver

        selected_instances = [
            ("web_app", [{"id": "site1", "type": "sites"}]),
            ("database", [{"id": "db1", "type": "sqlServers"}]),
            ("storage", [{"id": "sa1", "type": "storageAccounts"}])
        ]

        graph = builder.build_from_instances(selected_instances)

        # Should have nodes for all resource types
        assert "sites" in graph.nodes()
        assert "sqlServers" in graph.nodes()
        assert "storageAccounts" in graph.nodes()

    @patch('src.replicator.modules.target_graph_builder.GraphDatabase')
    def test_build_from_instances_with_edges(self, mock_graph_db, builder, mock_analyzer):
        """Test building graph with edges from relationships."""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = MagicMock()

        # Mock relationships
        mock_result.__iter__.return_value = iter([
            {
                "source_labels": ["Resource"],
                "source_type": "Microsoft.Compute/virtualMachines",
                "rel_type": "USES",
                "target_labels": ["Resource"],
                "target_type": "Microsoft.Compute/disks"
            }
        ])

        mock_session.run.return_value = mock_result
        mock_session.__enter__.return_value = mock_session
        mock_session.__exit__.return_value = None
        mock_driver.session.return_value = mock_session
        mock_graph_db.driver.return_value = mock_driver

        # Mock aggregated relationships
        mock_analyzer.aggregate_relationships.return_value = [
            {
                "source_type": "virtualMachines",
                "target_type": "disks",
                "rel_type": "USES",
                "frequency": 3
            }
        ]

        selected_instances = [
            ("vm_infra", [
                {"id": "vm1", "type": "virtualMachines"},
                {"id": "disk1", "type": "disks"}
            ])
        ]

        graph = builder.build_from_instances(selected_instances)

        # Should have edge between VM and disk
        assert graph.has_edge("virtualMachines", "disks")

    @patch('src.replicator.modules.target_graph_builder.GraphDatabase')
    def test_build_from_instances_node_counts(self, mock_graph_db, builder):
        """Test that node counts are tracked correctly."""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = MagicMock()

        mock_result.__iter__.return_value = iter([])
        mock_session.run.return_value = mock_result
        mock_session.__enter__.return_value = mock_session
        mock_session.__exit__.return_value = None
        mock_driver.session.return_value = mock_session
        mock_graph_db.driver.return_value = mock_driver

        selected_instances = [
            ("pattern1", [
                {"id": "vm1", "type": "virtualMachines"},
                {"id": "vm2", "type": "virtualMachines"}
            ]),
            ("pattern2", [
                {"id": "vm3", "type": "virtualMachines"}
            ])
        ]

        graph = builder.build_from_instances(selected_instances)

        # Should track count of each resource type
        assert "virtualMachines" in graph.nodes()
        node_data = graph.nodes["virtualMachines"]
        assert "count" in node_data
        assert node_data["count"] == 3  # 3 VM instances total

    @patch('src.replicator.modules.target_graph_builder.GraphDatabase')
    def test_build_from_instances_orphaned_resources(self, mock_graph_db, builder):
        """Test that orphaned resources (no relationships) still appear as nodes."""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = MagicMock()

        # No relationships returned
        mock_result.__iter__.return_value = iter([])
        mock_session.run.return_value = mock_result
        mock_session.__enter__.return_value = mock_session
        mock_session.__exit__.return_value = None
        mock_driver.session.return_value = mock_session
        mock_graph_db.driver.return_value = mock_driver

        selected_instances = [
            ("orphan_pattern", [
                {"id": "orphan1", "type": "keyVaults"}
            ])
        ]

        graph = builder.build_from_instances(selected_instances)

        # Orphaned resource should still be a node
        assert "keyVaults" in graph.nodes()
        assert graph.nodes["keyVaults"]["count"] == 1

    @patch('src.replicator.modules.target_graph_builder.GraphDatabase')
    def test_build_from_instances_calls_aggregate(self, mock_graph_db, builder, mock_analyzer):
        """Test that builder calls analyzer's aggregate_relationships."""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = MagicMock()

        mock_result.__iter__.return_value = iter([
            {
                "source_labels": ["Resource"],
                "source_type": "Microsoft.Compute/virtualMachines",
                "rel_type": "USES",
                "target_labels": ["Resource"],
                "target_type": "Microsoft.Compute/disks"
            }
        ])

        mock_session.run.return_value = mock_result
        mock_session.__enter__.return_value = mock_session
        mock_session.__exit__.return_value = None
        mock_driver.session.return_value = mock_session
        mock_graph_db.driver.return_value = mock_driver

        selected_instances = [
            ("vm_infra", [{"id": "vm1", "type": "virtualMachines"}])
        ]

        builder.build_from_instances(selected_instances)

        # Should call aggregate_relationships with query results
        assert mock_analyzer.aggregate_relationships.called

    @patch('src.replicator.modules.target_graph_builder.GraphDatabase')
    def test_build_from_instances_multigraph(self, mock_graph_db, builder, mock_analyzer):
        """Test that builder returns MultiDiGraph (allows multiple edges)."""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = MagicMock()

        mock_result.__iter__.return_value = iter([])
        mock_session.run.return_value = mock_result
        mock_session.__enter__.return_value = mock_session
        mock_session.__exit__.return_value = None
        mock_driver.session.return_value = mock_session
        mock_graph_db.driver.return_value = mock_driver

        # Mock multiple relationships between same nodes
        mock_analyzer.aggregate_relationships.return_value = [
            {
                "source_type": "virtualMachines",
                "target_type": "disks",
                "rel_type": "USES",
                "frequency": 3
            },
            {
                "source_type": "virtualMachines",
                "target_type": "disks",
                "rel_type": "ATTACHES",
                "frequency": 2
            }
        ]

        selected_instances = [
            ("vm_infra", [
                {"id": "vm1", "type": "virtualMachines"},
                {"id": "disk1", "type": "disks"}
            ])
        ]

        graph = builder.build_from_instances(selected_instances)

        # Should be a MultiDiGraph
        assert isinstance(graph, nx.MultiDiGraph)

    @patch('src.replicator.modules.target_graph_builder.GraphDatabase')
    def test_build_from_instances_edge_attributes(self, mock_graph_db, builder, mock_analyzer):
        """Test that edges have correct attributes (relationship, frequency)."""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = MagicMock()

        mock_result.__iter__.return_value = iter([
            {
                "source_labels": ["Resource"],
                "source_type": "Microsoft.Compute/virtualMachines",
                "rel_type": "USES",
                "target_labels": ["Resource"],
                "target_type": "Microsoft.Compute/disks"
            }
        ])

        mock_session.run.return_value = mock_result
        mock_session.__enter__.return_value = mock_session
        mock_session.__exit__.return_value = None
        mock_driver.session.return_value = mock_session
        mock_graph_db.driver.return_value = mock_driver

        mock_analyzer.aggregate_relationships.return_value = [
            {
                "source_type": "virtualMachines",
                "target_type": "disks",
                "rel_type": "USES",
                "frequency": 5
            }
        ]

        selected_instances = [
            ("vm_infra", [
                {"id": "vm1", "type": "virtualMachines"},
                {"id": "disk1", "type": "disks"}
            ])
        ]

        graph = builder.build_from_instances(selected_instances)

        # Check edge attributes
        edges = list(graph.edges(data=True))
        assert len(edges) > 0
        for source, target, data in edges:
            assert "relationship" in data
            assert "frequency" in data

    @patch('src.replicator.modules.target_graph_builder.GraphDatabase')
    def test_build_from_instances_deterministic(self, mock_graph_db, builder):
        """Test that building graph is deterministic (same input = same output)."""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = MagicMock()

        mock_result.__iter__.return_value = iter([])
        mock_session.run.return_value = mock_result
        mock_session.__enter__.return_value = mock_session
        mock_session.__exit__.return_value = None
        mock_driver.session.return_value = mock_session
        mock_graph_db.driver.return_value = mock_driver

        selected_instances = [
            ("pattern1", [{"id": "vm1", "type": "virtualMachines"}])
        ]

        # Build twice
        graph1 = builder.build_from_instances(selected_instances)
        graph2 = builder.build_from_instances(selected_instances)

        # Should be identical
        assert set(graph1.nodes()) == set(graph2.nodes())
        assert graph1.number_of_edges() == graph2.number_of_edges()
