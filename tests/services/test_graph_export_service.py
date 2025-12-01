"""Tests for Graph Export Service (Issue #508).

Test Coverage:
- GraphML export validation
- JSON export (D3.js format)
- DOT export (Graphviz format)
- Invalid format handling
- Empty tenant handling
- No-relationships export
- Neo4j session integration

Target: 90% coverage
"""

import json
from unittest.mock import Mock

import networkx as nx
import pytest

from src.services.graph_export_service import GraphExportService


class TestGraphExportService:
    """Test suite for GraphExportService."""

    @pytest.fixture
    def mock_session_manager(self):
        """Mock Neo4j session manager."""
        session_manager = Mock()
        session = Mock()
        # Properly mock context manager
        context_manager = Mock()
        context_manager.__enter__ = Mock(return_value=session)
        context_manager.__exit__ = Mock(return_value=None)
        session_manager.session.return_value = context_manager
        return session_manager, session

    def test_export_to_graphml(self, mock_session_manager, tmp_path):
        """Test GraphML export creates valid format."""
        session_manager, session = mock_session_manager

        # Mock Neo4j node query
        node_result = Mock()
        node_result.__iter__ = lambda self: iter(
            [
                {
                    "id": "vm1",
                    "name": "vm1",
                    "type": "Microsoft.Compute/virtualMachines",
                    "location": "eastus",
                    "tenant_id": "test-tenant",
                }
            ]
        )

        # Mock Neo4j edge query
        edge_result = Mock()
        edge_result.__iter__ = lambda self: iter([])

        session.run.side_effect = [node_result, edge_result]

        # Export
        service = GraphExportService(session_manager)
        output_path = tmp_path / "test.graphml"
        result = service.export_abstraction(
            tenant_id="test-tenant", output_path=output_path, format="graphml"
        )

        assert result["success"] is True
        assert result["node_count"] == 1
        assert result["edge_count"] == 0
        assert output_path.exists()

        # Verify GraphML is valid by loading it
        graph = nx.read_graphml(str(output_path))
        assert graph.number_of_nodes() == 1

    def test_export_to_json(self, mock_session_manager, tmp_path):
        """Test JSON export creates D3.js-compatible format."""
        session_manager, session = mock_session_manager

        # Mock Neo4j queries
        node_result = Mock()
        node_result.__iter__ = lambda self: iter(
            [
                {
                    "id": "vm1",
                    "name": "vm1",
                    "type": "Microsoft.Compute/virtualMachines",
                    "location": "eastus",
                    "tenant_id": "test-tenant",
                }
            ]
        )

        edge_result = Mock()
        edge_result.__iter__ = lambda self: iter(
            [{"source_id": "rg1", "target_id": "vm1", "rel_type": "CONTAINS"}]
        )

        session.run.side_effect = [node_result, edge_result]

        # Export
        service = GraphExportService(session_manager)
        output_path = tmp_path / "test.json"
        result = service.export_abstraction(
            tenant_id="test-tenant", output_path=output_path, format="json"
        )

        assert result["success"] is True
        assert output_path.exists()

        # Verify JSON structure
        data = json.loads(output_path.read_text())
        assert "nodes" in data
        assert "links" in data
        assert "metadata" in data
        # Note: 2 nodes because NetworkX auto-creates missing source node "rg1"
        assert len(data["nodes"]) == 2
        # Find the vm1 node
        vm_node = next(n for n in data["nodes"] if n["id"] == "vm1")
        assert vm_node["type"] == "Microsoft.Compute/virtualMachines"

    def test_export_to_dot(self, mock_session_manager, tmp_path):
        """Test DOT export creates valid Graphviz format."""
        session_manager, session = mock_session_manager

        # Mock Neo4j queries
        node_result = Mock()
        node_result.__iter__ = lambda self: iter(
            [
                {
                    "id": "vm1",
                    "name": "vm1",
                    "type": "Microsoft.Compute/virtualMachines",
                    "location": "eastus",
                    "tenant_id": "test-tenant",
                }
            ]
        )

        edge_result = Mock()
        edge_result.__iter__ = lambda self: iter([])

        session.run.side_effect = [node_result, edge_result]

        # Export
        service = GraphExportService(session_manager)
        output_path = tmp_path / "test.dot"
        result = service.export_abstraction(
            tenant_id="test-tenant", output_path=output_path, format="dot"
        )

        assert result["success"] is True
        assert output_path.exists()

        # Verify DOT file was created
        content = output_path.read_text()
        assert "digraph" in content or "strict digraph" in content

    def test_export_no_relationships(self, mock_session_manager, tmp_path):
        """Test export with no-relationships flag."""
        session_manager, session = mock_session_manager

        # Mock only node query (no edge query)
        node_result = Mock()
        node_result.__iter__ = lambda self: iter(
            [
                {
                    "id": "vm1",
                    "name": "vm1",
                    "type": "Microsoft.Compute/virtualMachines",
                    "location": "eastus",
                    "tenant_id": "test-tenant",
                }
            ]
        )

        session.run.return_value = node_result

        # Export without relationships
        service = GraphExportService(session_manager)
        output_path = tmp_path / "test.graphml"
        result = service.export_abstraction(
            tenant_id="test-tenant",
            output_path=output_path,
            format="graphml",
            include_relationships=False,
        )

        assert result["edge_count"] == 0
        # Verify session.run was only called once (for nodes)
        assert session.run.call_count == 1

    def test_export_invalid_format(self, mock_session_manager, tmp_path):
        """Test export with invalid format raises ValueError."""
        session_manager, _ = mock_session_manager

        service = GraphExportService(session_manager)

        with pytest.raises(ValueError, match="Unsupported format"):
            service.export_abstraction(
                tenant_id="test-tenant",
                output_path=tmp_path / "test.csv",
                format="csv",
            )

    def test_export_tenant_not_found(self, mock_session_manager, tmp_path):
        """Test export with non-existent tenant raises ValueError."""
        session_manager, session = mock_session_manager

        # Mock empty result
        node_result = Mock()
        node_result.__iter__ = lambda self: iter([])
        session.run.return_value = node_result

        service = GraphExportService(session_manager)

        with pytest.raises(ValueError, match="No abstraction found"):
            service.export_abstraction(
                tenant_id="nonexistent",
                output_path=tmp_path / "test.graphml",
                format="graphml",
            )

    def test_export_creates_parent_directories(self, mock_session_manager, tmp_path):
        """Test export creates parent directories if they don't exist."""
        session_manager, session = mock_session_manager

        # Mock Neo4j node query
        node_result = Mock()
        node_result.__iter__ = lambda self: iter(
            [
                {
                    "id": "vm1",
                    "name": "vm1",
                    "type": "Microsoft.Compute/virtualMachines",
                    "location": "eastus",
                    "tenant_id": "test-tenant",
                }
            ]
        )

        edge_result = Mock()
        edge_result.__iter__ = lambda self: iter([])

        session.run.side_effect = [node_result, edge_result]

        # Export to nested directory
        service = GraphExportService(session_manager)
        output_path = tmp_path / "nested" / "dir" / "test.graphml"
        result = service.export_abstraction(
            tenant_id="test-tenant", output_path=output_path, format="graphml"
        )

        assert result["success"] is True
        assert output_path.exists()
        assert output_path.parent.exists()

    def test_json_export_with_edges(self, mock_session_manager, tmp_path):
        """Test JSON export includes edges in D3.js format."""
        session_manager, session = mock_session_manager

        # Mock queries with multiple nodes and edges
        node_result = Mock()
        node_result.__iter__ = lambda self: iter(
            [
                {
                    "id": "rg1",
                    "name": "rg1",
                    "type": "Microsoft.Resources/resourceGroups",
                    "location": "eastus",
                    "tenant_id": "test-tenant",
                },
                {
                    "id": "vm1",
                    "name": "vm1",
                    "type": "Microsoft.Compute/virtualMachines",
                    "location": "eastus",
                    "tenant_id": "test-tenant",
                },
            ]
        )

        edge_result = Mock()
        edge_result.__iter__ = lambda self: iter(
            [
                {"source_id": "rg1", "target_id": "vm1", "rel_type": "CONTAINS"},
            ]
        )

        session.run.side_effect = [node_result, edge_result]

        # Export
        service = GraphExportService(session_manager)
        output_path = tmp_path / "test.json"
        service.export_abstraction(
            tenant_id="test-tenant", output_path=output_path, format="json"
        )

        # Verify JSON structure
        data = json.loads(output_path.read_text())
        assert len(data["nodes"]) == 2
        assert len(data["links"]) == 1
        assert data["links"][0]["source"] == "rg1"
        assert data["links"][0]["target"] == "vm1"
        assert data["links"][0]["relationship"] == "CONTAINS"
        assert data["metadata"]["node_count"] == 2
        assert data["metadata"]["edge_count"] == 1
