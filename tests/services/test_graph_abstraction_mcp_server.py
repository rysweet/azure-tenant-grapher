"""Tests for Graph Abstraction MCP Server (Issue #508).

Test Coverage:
- list_tenant_abstractions tool
- get_abstraction_metadata tool
- get_abstraction_quality tool
- compare_abstractions tool
- Empty tenant handling
- Error cases
- Response format validation

Target: 85% coverage
"""

from unittest.mock import Mock

import pytest

from src.services.graph_abstraction_mcp_server import GraphAbstractionMCPServer


class TestGraphAbstractionMCPServer:
    """Test suite for GraphAbstractionMCPServer."""

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

    @pytest.mark.asyncio
    async def test_list_tenant_abstractions_success(self, mock_session_manager):
        """Test listing abstractions for tenant."""
        session_manager, session = mock_session_manager

        # Mock Neo4j query result
        result = Mock()
        result.single.return_value = {
            "tenant_id": "test-tenant",
            "sample_count": 100,
            "source_count": 1000,
            "sample_types": [
                "Microsoft.Compute/virtualMachines",
                "Microsoft.Storage/storageAccounts",
            ],
        }
        session.run.return_value = result

        # Create server and call tool
        server = GraphAbstractionMCPServer(session_manager)
        response = await server._list_tenant_abstractions({"tenant_id": "test-tenant"})

        assert len(response) == 1
        assert "test-tenant" in response[0].text
        assert "100 nodes" in response[0].text
        assert "10.00%" in response[0].text  # 100/1000

    @pytest.mark.asyncio
    async def test_list_tenant_abstractions_not_found(self, mock_session_manager):
        """Test listing abstractions for non-existent tenant."""
        session_manager, session = mock_session_manager

        # Mock empty result
        result = Mock()
        result.single.return_value = None
        session.run.return_value = result

        server = GraphAbstractionMCPServer(session_manager)
        response = await server._list_tenant_abstractions({"tenant_id": "nonexistent"})

        assert "No abstractions found" in response[0].text

    @pytest.mark.asyncio
    async def test_get_abstraction_metadata_success(self, mock_session_manager):
        """Test getting abstraction metadata."""
        session_manager, session = mock_session_manager

        # Mock query result
        result = Mock()
        result.data.return_value = [
            {"type": "Microsoft.Compute/virtualMachines", "count": 50},
            {"type": "Microsoft.Storage/storageAccounts", "count": 30},
            {"type": "Microsoft.Network/virtualNetworks", "count": 20},
        ]
        session.run.return_value = result

        server = GraphAbstractionMCPServer(session_manager)
        response = await server._get_abstraction_metadata({"tenant_id": "test-tenant"})

        assert len(response) == 1
        assert "Microsoft.Compute/virtualMachines: 50" in response[0].text
        assert "Microsoft.Storage/storageAccounts: 30" in response[0].text
        assert "Total types: 3" in response[0].text
        assert "Total samples: 100" in response[0].text

    @pytest.mark.asyncio
    async def test_get_abstraction_metadata_not_found(self, mock_session_manager):
        """Test getting metadata for non-existent tenant."""
        session_manager, session = mock_session_manager

        # Mock empty result
        result = Mock()
        result.data.return_value = []
        session.run.return_value = result

        server = GraphAbstractionMCPServer(session_manager)
        response = await server._get_abstraction_metadata({"tenant_id": "nonexistent"})

        assert "No abstraction found" in response[0].text

    @pytest.mark.asyncio
    async def test_get_abstraction_quality_calculates_cv(self, mock_session_manager):
        """Test quality metrics calculation including coefficient of variation."""
        session_manager, session = mock_session_manager

        # Mock quality data with varying ratios
        result = Mock()
        result.data.return_value = [
            {"type": "VM", "sample_count": 10, "source_count": 100, "ratio": 0.10},
            {"type": "Storage", "sample_count": 5, "source_count": 50, "ratio": 0.10},
            {
                "type": "Network",
                "sample_count": 15,
                "source_count": 120,
                "ratio": 0.125,
            },
        ]
        session.run.return_value = result

        server = GraphAbstractionMCPServer(session_manager)
        response = await server._get_abstraction_quality({"tenant_id": "test-tenant"})

        assert "Coefficient of variation" in response[0].text
        assert "Average sampling ratio" in response[0].text
        assert "VM: 10/100 (10.0%)" in response[0].text

    @pytest.mark.asyncio
    async def test_get_abstraction_quality_single_type(self, mock_session_manager):
        """Test quality metrics with single type (no std deviation)."""
        session_manager, session = mock_session_manager

        # Mock single type
        result = Mock()
        result.data.return_value = [
            {"type": "VM", "sample_count": 10, "source_count": 100, "ratio": 0.10},
        ]
        session.run.return_value = result

        server = GraphAbstractionMCPServer(session_manager)
        response = await server._get_abstraction_quality({"tenant_id": "test-tenant"})

        # Should handle single type gracefully (stdev = 0)
        assert "Coefficient of variation: 0.000" in response[0].text

    @pytest.mark.asyncio
    async def test_get_abstraction_quality_not_found(self, mock_session_manager):
        """Test quality metrics for non-existent tenant."""
        session_manager, session = mock_session_manager

        # Mock empty result
        result = Mock()
        result.data.return_value = []
        session.run.return_value = result

        server = GraphAbstractionMCPServer(session_manager)
        response = await server._get_abstraction_quality({"tenant_id": "nonexistent"})

        assert "No abstraction found" in response[0].text

    @pytest.mark.asyncio
    async def test_compare_abstractions(self, mock_session_manager):
        """Test comparing two abstractions."""
        session_manager, session = mock_session_manager

        # Mock both tenants
        result = Mock()
        result.data.return_value = [
            {"type": "VM", "sample_count": 10, "source_count": 100, "ratio": 0.10},
        ]
        session.run.return_value = result

        server = GraphAbstractionMCPServer(session_manager)
        response = await server._compare_abstractions(
            {"tenant_id_1": "tenant1", "tenant_id_2": "tenant2"}
        )

        assert "Comparison of abstractions" in response[0].text
        assert "tenant1" in response[0].text
        assert "tenant2" in response[0].text
        assert "=== Tenant 1:" in response[0].text
        assert "=== Tenant 2:" in response[0].text

    def test_server_initialization(self, mock_session_manager):
        """Test MCP server initializes correctly."""
        session_manager, _ = mock_session_manager

        server = GraphAbstractionMCPServer(session_manager)

        assert server.session_manager == session_manager
        assert server.server is not None
        assert server.server.name == "graph-abstraction-server"

    @pytest.mark.asyncio
    async def test_quality_metrics_multiple_types(self, mock_session_manager):
        """Test quality metrics with many resource types."""
        session_manager, session = mock_session_manager

        # Mock 15 resource types (should show top 10)
        result = Mock()
        result.data.return_value = [
            {
                "type": f"Microsoft.Type{i}",
                "sample_count": 10 + i,
                "source_count": 100 + i * 10,
                "ratio": (10 + i) / (100 + i * 10),
            }
            for i in range(15)
        ]
        session.run.return_value = result

        server = GraphAbstractionMCPServer(session_manager)
        response = await server._get_abstraction_quality({"tenant_id": "test-tenant"})

        # Should only show top 10 types
        lines = response[0].text.split("\n")
        type_lines = [line for line in lines if "Microsoft.Type" in line]
        assert len(type_lines) <= 10
