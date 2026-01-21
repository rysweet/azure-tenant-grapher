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
        mock_record.__contains__.side_effect = lambda key: key in [
            "r",
            "original_id",
            "rels",
        ]
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
        mock_record.__contains__.side_effect = lambda key: key in [
            "r",
            "original_id",
            "rels",
        ]
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
        mock_record.__contains__.side_effect = lambda key: key in [
            "r",
            "original_id",
            "rels",
        ]
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


class TestTopologicalSort:
    """Test cases for topological sort functionality (Issue #297)."""

    def test_topological_sort_simple_linear_dependency(self) -> None:
        """Test topological sort with simple linear dependency chain."""
        # Create test graph: A -> B -> C
        resources = [
            {"id": "C", "name": "resource-c", "type": "Type-C"},
            {"id": "A", "name": "resource-a", "type": "Type-A"},
            {"id": "B", "name": "resource-b", "type": "Type-B"},
        ]
        relationships = [
            {"source": "B", "target": "A", "type": "DEPENDS_ON"},  # B depends on A
            {"source": "C", "target": "B", "type": "DEPENDS_ON"},  # C depends on B
        ]
        graph = TenantGraph(resources=resources, relationships=relationships)

        traverser = GraphTraverser(driver=None, transformation_rules=[])  # type: ignore[arg-type]
        sorted_resources = traverser.topological_sort(graph)

        # Verify order: A should come before B, B before C
        ids = [r["id"] for r in sorted_resources]
        assert ids.index("A") < ids.index("B")
        assert ids.index("B") < ids.index("C")
        assert len(sorted_resources) == 3

    def test_topological_sort_multiple_roots(self) -> None:
        """Test topological sort with multiple root nodes."""
        # Create test graph: A and B are roots, C depends on both
        resources = [
            {"id": "C", "name": "resource-c", "type": "Type-C"},
            {"id": "A", "name": "resource-a", "type": "Type-A"},
            {"id": "B", "name": "resource-b", "type": "Type-B"},
        ]
        relationships = [
            {"source": "C", "target": "A", "type": "DEPENDS_ON"},  # C depends on A
            {"source": "C", "target": "B", "type": "DEPENDS_ON"},  # C depends on B
        ]
        graph = TenantGraph(resources=resources, relationships=relationships)

        traverser = GraphTraverser(driver=None, transformation_rules=[])  # type: ignore[arg-type]
        sorted_resources = traverser.topological_sort(graph)

        # Verify order: A and B before C
        ids = [r["id"] for r in sorted_resources]
        assert ids.index("A") < ids.index("C")
        assert ids.index("B") < ids.index("C")
        assert len(sorted_resources) == 3

    def test_topological_sort_no_dependencies(self) -> None:
        """Test topological sort with no dependencies."""
        resources = [
            {"id": "A", "name": "resource-a", "type": "Type-A"},
            {"id": "B", "name": "resource-b", "type": "Type-B"},
            {"id": "C", "name": "resource-c", "type": "Type-C"},
        ]
        relationships = []
        graph = TenantGraph(resources=resources, relationships=relationships)

        traverser = GraphTraverser(driver=None, transformation_rules=[])  # type: ignore[arg-type]
        sorted_resources = traverser.topological_sort(graph)

        # All resources should be returned (order doesn't matter)
        assert len(sorted_resources) == 3
        ids = {r["id"] for r in sorted_resources}
        assert ids == {"A", "B", "C"}

    def test_topological_sort_circular_dependency_detected(self) -> None:
        """Test that circular dependencies are detected and reported."""
        # Create circular dependency: A -> B -> C -> A
        resources = [
            {"id": "A", "name": "resource-a", "type": "Type-A"},
            {"id": "B", "name": "resource-b", "type": "Type-B"},
            {"id": "C", "name": "resource-c", "type": "Type-C"},
        ]
        relationships = [
            {"source": "B", "target": "A", "type": "DEPENDS_ON"},  # B depends on A
            {"source": "C", "target": "B", "type": "DEPENDS_ON"},  # C depends on B
            {
                "source": "A",
                "target": "C",
                "type": "DEPENDS_ON",
            },  # A depends on C (cycle!)
        ]
        graph = TenantGraph(resources=resources, relationships=relationships)

        traverser = GraphTraverser(driver=None, transformation_rules=[])  # type: ignore[arg-type]

        with pytest.raises(ValueError) as exc_info:
            traverser.topological_sort(graph)

        # Verify error message mentions circular dependency
        assert "Circular dependency detected" in str(exc_info.value)
        assert "3 resources" in str(exc_info.value)

    def test_topological_sort_filters_relationship_types(self) -> None:
        """Test that topological sort filters by relationship type."""
        # Create graph with mixed relationship types
        resources = [
            {"id": "A", "name": "resource-a", "type": "Type-A"},
            {"id": "B", "name": "resource-b", "type": "Type-B"},
            {"id": "C", "name": "resource-c", "type": "Type-C"},
        ]
        relationships = [
            {
                "source": "B",
                "target": "A",
                "type": "DEPENDS_ON",
            },  # Should be considered
            {
                "source": "C",
                "target": "B",
                "type": "USES_IDENTITY",
            },  # Should be ignored
        ]
        graph = TenantGraph(resources=resources, relationships=relationships)

        traverser = GraphTraverser(driver=None, transformation_rules=[])  # type: ignore[arg-type]
        sorted_resources = traverser.topological_sort(
            graph, relationship_types=["DEPENDS_ON"]
        )

        # Only DEPENDS_ON relationship should be considered
        # A should come before B, but C order is independent
        ids = [r["id"] for r in sorted_resources]
        assert ids.index("A") < ids.index("B")
        assert len(sorted_resources) == 3

    def test_topological_sort_respects_max_depth(self) -> None:
        """Test that max_depth parameter limits traversal depth."""
        # Create deep chain: A -> B -> C -> D
        resources = [
            {"id": "A", "name": "resource-a", "type": "Type-A"},
            {"id": "B", "name": "resource-b", "type": "Type-B"},
            {"id": "C", "name": "resource-c", "type": "Type-C"},
            {"id": "D", "name": "resource-d", "type": "Type-D"},
        ]
        relationships = [
            {"source": "B", "target": "A", "type": "DEPENDS_ON"},
            {"source": "C", "target": "B", "type": "DEPENDS_ON"},
            {"source": "D", "target": "C", "type": "DEPENDS_ON"},
        ]
        graph = TenantGraph(resources=resources, relationships=relationships)

        traverser = GraphTraverser(driver=None, transformation_rules=[])  # type: ignore[arg-type]
        sorted_resources = traverser.topological_sort(graph, max_depth=2)

        # With max_depth=2, we should get A (depth 0), B (depth 1), C (depth 2)
        # D (depth 3) should be excluded
        assert len(sorted_resources) == 3
        ids = {r["id"] for r in sorted_resources}
        assert ids == {"A", "B", "C"}

    def test_topological_sort_complex_dag(self) -> None:
        """Test topological sort with complex DAG structure."""
        # Complex graph:
        #     A   B
        #     |\ /|
        #     | X |
        #     |/ \|
        #     C   D
        #      \ /
        #       E
        resources = [
            {"id": "E", "name": "resource-e", "type": "Type-E"},
            {"id": "C", "name": "resource-c", "type": "Type-C"},
            {"id": "A", "name": "resource-a", "type": "Type-A"},
            {"id": "D", "name": "resource-d", "type": "Type-D"},
            {"id": "B", "name": "resource-b", "type": "Type-B"},
        ]
        relationships = [
            {"source": "C", "target": "A", "type": "DEPENDS_ON"},
            {"source": "C", "target": "B", "type": "DEPENDS_ON"},
            {"source": "D", "target": "A", "type": "DEPENDS_ON"},
            {"source": "D", "target": "B", "type": "DEPENDS_ON"},
            {"source": "E", "target": "C", "type": "DEPENDS_ON"},
            {"source": "E", "target": "D", "type": "DEPENDS_ON"},
        ]
        graph = TenantGraph(resources=resources, relationships=relationships)

        traverser = GraphTraverser(driver=None, transformation_rules=[])  # type: ignore[arg-type]
        sorted_resources = traverser.topological_sort(graph)

        ids = [r["id"] for r in sorted_resources]

        # Verify topological order constraints
        assert ids.index("A") < ids.index("C")
        assert ids.index("A") < ids.index("D")
        assert ids.index("B") < ids.index("C")
        assert ids.index("B") < ids.index("D")
        assert ids.index("C") < ids.index("E")
        assert ids.index("D") < ids.index("E")
        assert len(sorted_resources) == 5

    def test_topological_sort_contains_relationship(self) -> None:
        """Test topological sort with CONTAINS relationships."""
        # VNET contains Subnet, Subnet contains NIC
        resources = [
            {
                "id": "NIC-1",
                "name": "nic-1",
                "type": "Microsoft.Network/networkInterfaces",
            },
            {
                "id": "VNET-1",
                "name": "vnet-1",
                "type": "Microsoft.Network/virtualNetworks",
            },
            {"id": "SUBNET-1", "name": "subnet-1", "type": "Microsoft.Network/subnets"},
        ]
        relationships = [
            {"source": "SUBNET-1", "target": "VNET-1", "type": "CONTAINS"},
            {"source": "NIC-1", "target": "SUBNET-1", "type": "CONTAINS"},
        ]
        graph = TenantGraph(resources=resources, relationships=relationships)

        traverser = GraphTraverser(driver=None, transformation_rules=[])  # type: ignore[arg-type]
        sorted_resources = traverser.topological_sort(
            graph, relationship_types=["CONTAINS"]
        )

        ids = [r["id"] for r in sorted_resources]

        # VNET before SUBNET, SUBNET before NIC
        assert ids.index("VNET-1") < ids.index("SUBNET-1")
        assert ids.index("SUBNET-1") < ids.index("NIC-1")


class TestTopologicalSortPerformance:
    """Performance tests for topological sort (Issue #297)."""

    def test_topological_sort_large_graph_performance(self) -> None:
        """Test topological sort with 10,000+ resources."""
        # Generate large graph with 10,000 resources
        num_resources = 10000
        resources = [
            {"id": f"resource-{i}", "name": f"name-{i}", "type": f"Type-{i % 10}"}
            for i in range(num_resources)
        ]

        # Create dependencies: each resource depends on the next 3
        relationships = []
        for i in range(num_resources - 3):
            for j in range(1, 4):
                relationships.append(
                    {
                        "source": f"resource-{i}",
                        "target": f"resource-{i + j}",
                        "type": "DEPENDS_ON",
                    }
                )

        graph = TenantGraph(resources=resources, relationships=relationships)

        traverser = GraphTraverser(driver=None, transformation_rules=[])  # type: ignore[arg-type]

        # Measure performance
        import time

        start_time = time.time()
        sorted_resources = traverser.topological_sort(graph)
        elapsed_time = time.time() - start_time

        # Verify correctness
        assert len(sorted_resources) == num_resources

        # Performance assertion: should complete in < 5 seconds
        assert elapsed_time < 5.0, (
            f"Topological sort took {elapsed_time:.2f}s (expected < 5s)"
        )

        # Verify order is correct (spot check)
        ids = [r["id"] for r in sorted_resources]
        for i in range(0, num_resources - 3):
            for j in range(1, 4):
                # resource-i should come AFTER resource-(i+j) in sorted order
                assert ids.index(f"resource-{i + j}") < ids.index(f"resource-{i}")
