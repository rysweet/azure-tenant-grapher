"""Tests for graph traverser functionality.

Tests the GraphTraverser class and TenantGraph data structure.
"""

from unittest.mock import MagicMock

import pytest

from src.iac.traverser import GraphTraverser, TenantGraph


class TestTenantGraph:
    """Test cases for TenantGraph data structure."""

    def test_tenant_graph_initialization(self) -> None:
        """Test that TenantGraph initializes with empty data."""
        graph = TenantGraph()
        assert graph.resources == []
        assert graph.relationships == []


class TestGraphTraverser:
    """Test cases for GraphTraverser class."""

    def test_traverser_initialization(self) -> None:
        """Test that GraphTraverser initializes with Neo4j driver."""
        mock_driver = MagicMock()
        traverser = GraphTraverser(mock_driver)
        assert traverser.driver == mock_driver

    @pytest.mark.asyncio
    async def test_traverse_returns_tenant_graph_instance(self) -> None:
        """Test that traverse returns TenantGraph instance."""
        # Mock Neo4j driver and session
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        # Mock session.run to return empty result
        mock_result = MagicMock()
        mock_result.__iter__.return_value = iter([])  # Empty result
        mock_session.run.return_value = mock_result

        # Create traverser instance
        traverser = GraphTraverser(mock_driver)

        # Test traverse method
        result = await traverser.traverse()
        assert isinstance(result, TenantGraph)
        assert result.resources == []
        assert result.relationships == []

    @pytest.mark.asyncio
    async def test_traverse_with_filter(self) -> None:
        """Test traverse with custom filter."""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        # Mock session.run to return empty result
        mock_result = MagicMock()
        mock_result.__iter__.return_value = iter([])
        mock_session.run.return_value = mock_result

        traverser = GraphTraverser(mock_driver)

        custom_filter = "MATCH (r:Resource) WHERE r.type = 'test' RETURN r"
        result = await traverser.traverse(custom_filter)

        # Verify custom query was used
        mock_session.run.assert_called_once_with(custom_filter)
        assert isinstance(result, TenantGraph)


class TestGraphTraverserWithMockData:
    """Test cases with mocked Neo4j data."""

    @pytest.mark.asyncio
    async def test_traverse_fallback_query_used(self) -> None:
        """Test that fallback query is used when :Resource label is absent and uses correct syntax."""
        from src.iac.traverser import GraphTraverser

        # Mock driver and session
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        # First call returns empty iterator, second returns a resource
        mock_record = MagicMock()
        mock_resource_node = {
            "id": "fallback-1",
            "original_id": "/subscriptions/test/resourceGroups/test/providers/Test/fallback-1",
            "name": "fallback-vm",
            "type": "FallbackType",
        }
        mock_record.__getitem__.side_effect = lambda key: {
            "r": mock_resource_node,
            "original_id": "/subscriptions/test/resourceGroups/test/providers/Test/fallback-1",
            "rels": [{"type": "CONNECTED_TO", "target": "other-1"}],
        }[key]
        mock_record.__contains__.side_effect = lambda key: key in ["r", "original_id", "rels"]
        mock_record.get = lambda key, default=None: {
            "r": mock_resource_node,
            "original_id": "/subscriptions/test/resourceGroups/test/providers/Test/fallback-1",
            "rels": [{"type": "CONNECTED_TO", "target": "other-1"}],
        }.get(key, default)

        # First result: empty, Second result: contains mock_record
        mock_result_empty = MagicMock()
        mock_result_empty.__iter__.return_value = iter([])
        mock_result_fallback = MagicMock()
        mock_result_fallback.__iter__.return_value = iter([mock_record])
        mock_session.run.side_effect = [mock_result_empty, mock_result_fallback]

        traverser = GraphTraverser(mock_driver)
        graph = await traverser.traverse()
        assert len(graph.resources) == 1
        assert graph.resources[0]["id"] == "fallback-1"
        assert graph.resources[0]["name"] == "fallback-vm"
        assert len(graph.relationships) == 1
        assert graph.relationships[0]["source"] == "fallback-1"
        assert graph.relationships[0]["target"] == "other-1"
        assert graph.relationships[0]["type"] == "CONNECTED_TO"
        assert mock_session.run.call_count == 2

        # Check that the fallback query uses correct syntax
        # The second call to run should be the fallback query
        fallback_query = mock_session.run.call_args_list[1][0][0]
        assert "IS NOT NULL" in fallback_query
        assert "exists(" not in fallback_query

    @pytest.mark.asyncio
    async def test_traverse_fallback_query_valid_syntax(self) -> None:
        """Test that fallback query uses 'IS NOT NULL' and not deprecated 'exists('."""
        from src.iac.traverser import GraphTraverser

        # Mock driver and session
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        # First call returns empty iterator, second returns a resource
        mock_record = MagicMock()
        mock_resource_node = {
            "id": "fallback-2",
            "original_id": "/subscriptions/test/resourceGroups/test/providers/Test/fallback-2",
            "name": "fallback-vm2",
            "type": "FallbackType2",
        }
        mock_record.__getitem__.side_effect = lambda key: {
            "r": mock_resource_node,
            "original_id": "/subscriptions/test/resourceGroups/test/providers/Test/fallback-2",
            "rels": [{"type": "CONNECTED_TO", "target": "other-2"}],
        }[key]
        mock_record.__contains__.side_effect = lambda key: key in ["r", "original_id", "rels"]
        mock_record.get = lambda key, default=None: {
            "r": mock_resource_node,
            "original_id": "/subscriptions/test/resourceGroups/test/providers/Test/fallback-2",
            "rels": [{"type": "CONNECTED_TO", "target": "other-2"}],
        }.get(key, default)

        mock_result_empty = MagicMock()
        mock_result_empty.__iter__.return_value = iter([])
        mock_result_fallback = MagicMock()
        mock_result_fallback.__iter__.return_value = iter([mock_record])
        mock_session.run.side_effect = [mock_result_empty, mock_result_fallback]

        traverser = GraphTraverser(mock_driver)
        graph = await traverser.traverse()

        # Assert fallback query syntax
        assert mock_session.run.call_count == 2
        fallback_query = mock_session.run.call_args_list[1][0][0]
        assert "IS NOT NULL" in fallback_query
        assert "exists(" not in fallback_query

        # Assert traversal returns the resource
        assert len(graph.resources) == 1
        assert graph.resources[0]["id"] == "fallback-2"
        assert graph.resources[0]["name"] == "fallback-vm2"
        assert len(graph.relationships) == 1
        assert graph.relationships[0]["source"] == "fallback-2"
        assert graph.relationships[0]["target"] == "other-2"
        assert graph.relationships[0]["type"] == "CONNECTED_TO"

    @pytest.mark.asyncio
    async def test_traverser_processes_mock_data(self) -> None:
        """Test that GraphTraverser processes mock Neo4j data correctly."""
        # Create mock driver and session
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        # Create mock record with resource and relationships
        mock_record = MagicMock()
        mock_resource_node = {
            "id": "vm-1",
            "original_id": "/subscriptions/test/resourceGroups/test/providers/Microsoft.Compute/virtualMachines/test-vm",
            "name": "test-vm",
            "type": "Microsoft.Compute/virtualMachines",
        }
        mock_record.__getitem__.side_effect = lambda key: {
            "r": mock_resource_node,
            "original_id": "/subscriptions/test/resourceGroups/test/providers/Microsoft.Compute/virtualMachines/test-vm",
            "rels": [{"type": "DEPENDS_ON", "target": "storage-1"}],
        }[key]
        mock_record.__contains__.side_effect = lambda key: key in ["r", "original_id", "rels"]
        mock_record.get = lambda key, default=None: {
            "r": mock_resource_node,
            "original_id": "/subscriptions/test/resourceGroups/test/providers/Microsoft.Compute/virtualMachines/test-vm",
            "rels": [{"type": "DEPENDS_ON", "target": "storage-1"}],
        }.get(key, default)

        # Mock result to return our mock record
        mock_result = MagicMock()
        mock_result.__iter__.return_value = iter([mock_record])
        mock_session.run.return_value = mock_result

        traverser = GraphTraverser(mock_driver)
        result = await traverser.traverse()

        # Verify data was processed
        assert len(result.resources) == 1
        assert result.resources[0]["id"] == "vm-1"
        assert result.resources[0]["name"] == "test-vm"

        assert len(result.relationships) == 1
        assert result.relationships[0]["source"] == "vm-1"
        assert result.relationships[0]["target"] == "storage-1"
        assert result.relationships[0]["type"] == "DEPENDS_ON"
