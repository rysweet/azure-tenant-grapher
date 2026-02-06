"""Unit tests for replication plan converter service.

Tests verify conversion from architecture-based replication plans
(pattern-based resource selection) to TenantGraph structures for IaC generation.

Key Test Areas:
- Resource flattening from nested structure
- Relationship querying with Neo4j
- Pattern and instance filtering
- Edge case handling (empty plans, no relationships)

Philosophy:
- Each test focuses on one function/behavior
- Mock Neo4j to avoid external dependencies
- Test both happy path and edge cases
"""

import pytest
from typing import Any, Dict, List, Set, Tuple
from unittest.mock import AsyncMock, MagicMock, Mock

from src.services.replication_plan_converter import (
    _flatten_resources,
    _filter_instances,
    _filter_patterns,
    _query_relationships,
    replication_plan_to_tenant_graph,
    DEFAULT_RELATIONSHIP_TYPES,
)
from src.iac.traverser import TenantGraph


class TestFlattenResources:
    """Tests for _flatten_resources() helper function."""

    def test_flatten_simple_structure(self):
        """Test flattening a simple replication plan structure."""
        # Arrange
        selected_instances = [
            (
                "Web Application",
                [
                    # Instance 1
                    [
                        {"id": "/subscriptions/.../sites/webapp1", "name": "webapp1"},
                        {
                            "id": "/subscriptions/.../serverFarms/plan1",
                            "name": "plan1",
                        },
                    ],
                    # Instance 2
                    [
                        {"id": "/subscriptions/.../sites/webapp2", "name": "webapp2"},
                    ],
                ],
            ),
        ]

        # Act
        flat_resources, resource_ids = _flatten_resources(selected_instances)

        # Assert
        assert len(flat_resources) == 3
        assert len(resource_ids) == 3
        assert "/subscriptions/.../sites/webapp1" in resource_ids
        assert "/subscriptions/.../serverFarms/plan1" in resource_ids
        assert "/subscriptions/.../sites/webapp2" in resource_ids

    def test_flatten_multiple_patterns(self):
        """Test flattening replication plan with multiple patterns."""
        # Arrange
        selected_instances = [
            (
                "Web Application",
                [
                    [
                        {"id": "/subscriptions/.../sites/webapp1", "name": "webapp1"},
                    ]
                ],
            ),
            (
                "VM Workload",
                [
                    [
                        {
                            "id": "/subscriptions/.../virtualMachines/vm1",
                            "name": "vm1",
                        },
                        {
                            "id": "/subscriptions/.../networkInterfaces/nic1",
                            "name": "nic1",
                        },
                    ]
                ],
            ),
        ]

        # Act
        flat_resources, resource_ids = _flatten_resources(selected_instances)

        # Assert
        assert len(flat_resources) == 3
        assert len(resource_ids) == 3

    def test_flatten_with_pattern_filter(self):
        """Test flattening with pattern filter applied."""
        # Arrange
        selected_instances = [
            (
                "Web Application",
                [
                    [
                        {"id": "/subscriptions/.../sites/webapp1", "name": "webapp1"},
                    ]
                ],
            ),
            (
                "VM Workload",
                [
                    [
                        {
                            "id": "/subscriptions/.../virtualMachines/vm1",
                            "name": "vm1",
                        },
                    ]
                ],
            ),
        ]

        # Act - filter to only "Web Application"
        flat_resources, resource_ids = _flatten_resources(
            selected_instances, pattern_filter=["Web Application"]
        )

        # Assert
        assert len(flat_resources) == 1
        assert "/subscriptions/.../sites/webapp1" in resource_ids
        assert "/subscriptions/.../virtualMachines/vm1" not in resource_ids

    def test_flatten_empty_plan(self):
        """Test flattening an empty replication plan."""
        # Arrange
        selected_instances = []

        # Act
        flat_resources, resource_ids = _flatten_resources(selected_instances)

        # Assert
        assert len(flat_resources) == 0
        assert len(resource_ids) == 0


class TestFilterInstances:
    """Tests for _filter_instances() helper function."""

    def test_filter_instances_single_index(self):
        """Test filtering instances by single index."""
        # Arrange
        instances = [
            [{"id": "res1"}],  # Index 0
            [{"id": "res2"}],  # Index 1
            [{"id": "res3"}],  # Index 2
        ]

        # Act
        filtered = _filter_instances(instances, "1")

        # Assert
        assert len(filtered) == 1
        assert filtered[0][0]["id"] == "res2"

    def test_filter_instances_multiple_indices(self):
        """Test filtering instances by multiple comma-separated indices."""
        # Arrange
        instances = [
            [{"id": "res1"}],  # Index 0
            [{"id": "res2"}],  # Index 1
            [{"id": "res3"}],  # Index 2
            [{"id": "res4"}],  # Index 3
        ]

        # Act
        filtered = _filter_instances(instances, "0,2,3")

        # Assert
        assert len(filtered) == 3
        assert filtered[0][0]["id"] == "res1"
        assert filtered[1][0]["id"] == "res3"
        assert filtered[2][0]["id"] == "res4"

    def test_filter_instances_range(self):
        """Test filtering instances by range specification."""
        # Arrange
        instances = [
            [{"id": "res1"}],  # Index 0
            [{"id": "res2"}],  # Index 1
            [{"id": "res3"}],  # Index 2
            [{"id": "res4"}],  # Index 3
        ]

        # Act
        filtered = _filter_instances(instances, "1-3")

        # Assert
        assert len(filtered) == 3
        assert filtered[0][0]["id"] == "res2"
        assert filtered[1][0]["id"] == "res3"
        assert filtered[2][0]["id"] == "res4"

    def test_filter_instances_no_filter(self):
        """Test that None filter returns all instances."""
        # Arrange
        instances = [
            [{"id": "res1"}],
            [{"id": "res2"}],
            [{"id": "res3"}],
        ]

        # Act
        filtered = _filter_instances(instances, None)

        # Assert
        assert len(filtered) == 3
        assert filtered == instances


class TestFilterPatterns:
    """Tests for _filter_patterns() helper function."""

    def test_filter_patterns_single_pattern(self):
        """Test filtering to single pattern."""
        # Arrange
        selected_instances = [
            ("Web Application", [[{"id": "webapp1"}]]),
            ("VM Workload", [[{"id": "vm1"}]]),
        ]

        # Act
        filtered = _filter_patterns(
            selected_instances, pattern_filter=["Web Application"], instance_filter=None
        )

        # Assert
        assert len(filtered) == 1
        assert filtered[0][0] == "Web Application"

    def test_filter_patterns_with_instance_filter(self):
        """Test filtering patterns with instance filter applied."""
        # Arrange
        selected_instances = [
            (
                "Web Application",
                [
                    [{"id": "webapp1"}],  # Index 0
                    [{"id": "webapp2"}],  # Index 1
                    [{"id": "webapp3"}],  # Index 2
                ],
            ),
        ]

        # Act
        filtered = _filter_patterns(
            selected_instances, pattern_filter=None, instance_filter="0,2"
        )

        # Assert
        assert len(filtered) == 1
        assert len(filtered[0][1]) == 2  # Only 2 instances (0 and 2)

    def test_filter_patterns_no_filters(self):
        """Test that no filters returns all patterns and instances."""
        # Arrange
        selected_instances = [
            ("Web Application", [[{"id": "webapp1"}]]),
            ("VM Workload", [[{"id": "vm1"}]]),
        ]

        # Act
        filtered = _filter_patterns(
            selected_instances, pattern_filter=None, instance_filter=None
        )

        # Assert
        assert len(filtered) == 2
        assert filtered == selected_instances


class TestQueryRelationships:
    """Tests for _query_relationships() helper function with mocked Neo4j."""

    @pytest.mark.asyncio
    async def test_query_relationships_success(self):
        """Test successful relationship query with mock Neo4j session."""
        # Arrange
        mock_session = AsyncMock()
        mock_result = AsyncMock()

        # Mock Neo4j query results
        mock_records = [
            {
                "source": "/subscriptions/.../virtualMachines/vm1",
                "target": "/subscriptions/.../networkInterfaces/nic1",
                "type": "CONTAINS",
            },
            {
                "source": "/subscriptions/.../sites/webapp1",
                "target": "/subscriptions/.../serverFarms/plan1",
                "type": "DEPENDS_ON",
            },
        ]

        # Setup async iteration
        async def mock_async_iter(self):
            for record in mock_records:
                yield record

        mock_result.__aiter__ = lambda self: mock_async_iter(self)
        mock_session.run.return_value = mock_result

        resource_ids = {
            "/subscriptions/.../virtualMachines/vm1",
            "/subscriptions/.../networkInterfaces/nic1",
            "/subscriptions/.../sites/webapp1",
            "/subscriptions/.../serverFarms/plan1",
        }

        # Act
        relationships = await _query_relationships(
            mock_session, resource_ids, DEFAULT_RELATIONSHIP_TYPES
        )

        # Assert
        assert len(relationships) == 2
        assert relationships[0]["source"] == "/subscriptions/.../virtualMachines/vm1"
        assert relationships[0]["type"] == "CONTAINS"
        assert relationships[1]["type"] == "DEPENDS_ON"

        # Verify Neo4j query was called with correct parameters
        mock_session.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_relationships_empty_resource_ids(self):
        """Test relationship query with empty resource IDs."""
        # Arrange
        mock_session = AsyncMock()

        # Act
        relationships = await _query_relationships(
            mock_session, set(), DEFAULT_RELATIONSHIP_TYPES
        )

        # Assert
        assert len(relationships) == 0
        mock_session.run.assert_not_called()

    @pytest.mark.asyncio
    async def test_query_relationships_no_results(self):
        """Test relationship query when Neo4j returns no relationships."""
        # Arrange
        mock_session = AsyncMock()
        mock_result = AsyncMock()

        # Setup empty async iteration
        async def mock_empty_iter(self):
            return
            yield  # Make it a generator

        mock_result.__aiter__ = lambda self: mock_empty_iter(self)
        mock_session.run.return_value = mock_result

        resource_ids = {"/subscriptions/.../virtualMachines/vm1"}

        # Act
        relationships = await _query_relationships(
            mock_session, resource_ids, DEFAULT_RELATIONSHIP_TYPES
        )

        # Assert
        assert len(relationships) == 0

    @pytest.mark.asyncio
    async def test_query_relationships_error_handling(self):
        """Test relationship query error handling."""
        # Arrange
        mock_session = AsyncMock()
        mock_session.run.side_effect = Exception("Neo4j connection failed")

        resource_ids = {"/subscriptions/.../virtualMachines/vm1"}

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            await _query_relationships(
                mock_session, resource_ids, DEFAULT_RELATIONSHIP_TYPES
            )

        assert "Neo4j connection failed" in str(exc_info.value)


class TestReplicationPlanToTenantGraph:
    """Tests for main replication_plan_to_tenant_graph() function."""

    @pytest.mark.asyncio
    async def test_conversion_success(self):
        """Test successful conversion from replication plan to TenantGraph."""
        # Arrange
        replication_plan = (
            [
                (
                    "Web Application",
                    [
                        [
                            {
                                "id": "/subscriptions/.../sites/webapp1",
                                "name": "webapp1",
                            },
                            {
                                "id": "/subscriptions/.../serverFarms/plan1",
                                "name": "plan1",
                            },
                        ]
                    ],
                )
            ],
            [0.8, 0.6],  # spectral_history
            {"selection_mode": "proportional"},  # metadata
        )

        mock_session = AsyncMock()
        mock_result = AsyncMock()

        # Mock relationship
        mock_records = [
            {
                "source": "/subscriptions/.../sites/webapp1",
                "target": "/subscriptions/.../serverFarms/plan1",
                "type": "DEPENDS_ON",
            }
        ]

        async def mock_async_iter(self):
            for record in mock_records:
                yield record

        mock_result.__aiter__ = lambda self: mock_async_iter(self)
        mock_session.run.return_value = mock_result

        # Act
        tenant_graph = await replication_plan_to_tenant_graph(
            replication_plan, mock_session
        )

        # Assert
        assert isinstance(tenant_graph, TenantGraph)
        assert len(tenant_graph.resources) == 2
        assert len(tenant_graph.relationships) == 1
        assert tenant_graph.relationships[0]["type"] == "DEPENDS_ON"

    @pytest.mark.asyncio
    async def test_conversion_with_pattern_filter(self):
        """Test conversion with pattern filter applied."""
        # Arrange
        replication_plan = (
            [
                ("Web Application", [[{"id": "/subscriptions/.../sites/webapp1"}]]),
                ("VM Workload", [[{"id": "/subscriptions/.../virtualMachines/vm1"}]]),
            ],
            [],
            None,
        )

        mock_session = AsyncMock()
        mock_result = AsyncMock()

        async def mock_empty_iter(self):
            return
            yield

        mock_result.__aiter__ = lambda self: mock_empty_iter(self)
        mock_session.run.return_value = mock_result

        # Act
        tenant_graph = await replication_plan_to_tenant_graph(
            replication_plan, mock_session, pattern_filter=["Web Application"]
        )

        # Assert
        assert len(tenant_graph.resources) == 1
        assert tenant_graph.resources[0]["id"] == "/subscriptions/.../sites/webapp1"

    @pytest.mark.asyncio
    async def test_conversion_with_instance_filter(self):
        """Test conversion with instance filter applied."""
        # Arrange
        replication_plan = (
            [
                (
                    "Web Application",
                    [
                        [{"id": "/subscriptions/.../sites/webapp1"}],  # Index 0
                        [{"id": "/subscriptions/.../sites/webapp2"}],  # Index 1
                        [{"id": "/subscriptions/.../sites/webapp3"}],  # Index 2
                    ],
                )
            ],
            [],
            None,
        )

        mock_session = AsyncMock()
        mock_result = AsyncMock()

        async def mock_empty_iter(self):
            return
            yield

        mock_result.__aiter__ = lambda self: mock_empty_iter(self)
        mock_session.run.return_value = mock_result

        # Act
        tenant_graph = await replication_plan_to_tenant_graph(
            replication_plan, mock_session, instance_filter="0,2"
        )

        # Assert
        assert len(tenant_graph.resources) == 2
        assert tenant_graph.resources[0]["id"] == "/subscriptions/.../sites/webapp1"
        assert tenant_graph.resources[1]["id"] == "/subscriptions/.../sites/webapp3"

    @pytest.mark.asyncio
    async def test_conversion_empty_plan(self):
        """Test conversion with empty replication plan."""
        # Arrange
        replication_plan = ([], [], None)

        mock_session = AsyncMock()

        # Act
        tenant_graph = await replication_plan_to_tenant_graph(
            replication_plan, mock_session
        )

        # Assert
        assert isinstance(tenant_graph, TenantGraph)
        assert len(tenant_graph.resources) == 0
        assert len(tenant_graph.relationships) == 0

    @pytest.mark.asyncio
    async def test_conversion_no_relationships(self):
        """Test conversion when no relationships exist between resources."""
        # Arrange
        replication_plan = (
            [("Web Application", [[{"id": "/subscriptions/.../sites/webapp1"}]])],
            [],
            None,
        )

        mock_session = AsyncMock()
        mock_result = AsyncMock()

        async def mock_empty_iter(self):
            return
            yield

        mock_result.__aiter__ = lambda self: mock_empty_iter(self)
        mock_session.run.return_value = mock_result

        # Act
        tenant_graph = await replication_plan_to_tenant_graph(
            replication_plan, mock_session
        )

        # Assert
        assert len(tenant_graph.resources) == 1
        assert len(tenant_graph.relationships) == 0

    @pytest.mark.asyncio
    async def test_conversion_custom_relationship_types(self):
        """Test conversion with custom relationship types specified."""
        # Arrange
        replication_plan = (
            [("Web Application", [[{"id": "/subscriptions/.../sites/webapp1"}]])],
            [],
            None,
        )

        mock_session = AsyncMock()
        mock_result = AsyncMock()

        async def mock_empty_iter(self):
            return
            yield

        mock_result.__aiter__ = lambda self: mock_empty_iter(self)
        mock_session.run.return_value = mock_result

        custom_rel_types = ["CONTAINS", "DEPENDS_ON"]

        # Act
        tenant_graph = await replication_plan_to_tenant_graph(
            replication_plan,
            mock_session,
            include_relationship_types=custom_rel_types,
        )

        # Assert
        # Verify Neo4j query was called with custom relationship types
        mock_session.run.assert_called_once()
        call_args = mock_session.run.call_args
        assert call_args[1]["rel_types"] == custom_rel_types

    @pytest.mark.asyncio
    async def test_conversion_filter_excludes_all(self):
        """Test conversion when filters exclude all patterns."""
        # Arrange
        replication_plan = (
            [("Web Application", [[{"id": "/subscriptions/.../sites/webapp1"}]])],
            [],
            None,
        )

        mock_session = AsyncMock()

        # Act
        tenant_graph = await replication_plan_to_tenant_graph(
            replication_plan, mock_session, pattern_filter=["Nonexistent Pattern"]
        )

        # Assert
        assert len(tenant_graph.resources) == 0
        assert len(tenant_graph.relationships) == 0


class TestResourceIdCollection:
    """Tests for resource ID collection accuracy."""

    def test_resource_ids_unique(self):
        """Test that resource IDs are deduplicated."""
        # Arrange - same resource appears in multiple patterns
        selected_instances = [
            ("Pattern1", [[{"id": "/subscriptions/.../resource1"}]]),
            ("Pattern2", [[{"id": "/subscriptions/.../resource1"}]]),  # Duplicate
        ]

        # Act
        flat_resources, resource_ids = _flatten_resources(selected_instances)

        # Assert
        assert len(resource_ids) == 1  # Deduplicated
        assert "/subscriptions/.../resource1" in resource_ids

    def test_resource_ids_collected_from_all_instances(self):
        """Test that resource IDs are collected from all instances and patterns."""
        # Arrange
        selected_instances = [
            (
                "Pattern1",
                [
                    [{"id": "/subscriptions/.../res1"}],
                    [{"id": "/subscriptions/.../res2"}],
                ],
            ),
            (
                "Pattern2",
                [
                    [{"id": "/subscriptions/.../res3"}],
                ],
            ),
        ]

        # Act
        flat_resources, resource_ids = _flatten_resources(selected_instances)

        # Assert
        assert len(resource_ids) == 3
        assert "/subscriptions/.../res1" in resource_ids
        assert "/subscriptions/.../res2" in resource_ids
        assert "/subscriptions/.../res3" in resource_ids
