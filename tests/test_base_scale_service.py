"""Tests for Base Scale Service.

This test suite validates the base functionality for scale operations
including tenant validation, resource counting, and session ID generation.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, Mock

from src.services.base_scale_service import BaseScaleService
from src.utils.session_manager import Neo4jSessionManager


class TestBaseScaleService:
    """Test suite for BaseScaleService."""

    @pytest.fixture
    def mock_session_manager(self):
        """Provide a mock Neo4j session manager."""
        manager = MagicMock(spec=Neo4jSessionManager)
        session = MagicMock()
        manager.session.return_value.__enter__ = Mock(return_value=session)
        manager.session.return_value.__exit__ = Mock(return_value=False)
        return manager

    @pytest.fixture
    def base_service(self, mock_session_manager):
        """Provide a base scale service instance."""
        return BaseScaleService(mock_session_manager)

    @pytest.mark.asyncio
    async def test_validate_tenant_exists_success(
        self, base_service, mock_session_manager
    ):
        """Test successful tenant validation."""
        # Mock session.run to return tenant exists
        session = mock_session_manager.session.return_value.__enter__.return_value
        result_mock = MagicMock()
        record_mock = {"exists": True}
        result_mock.single.return_value = record_mock
        session.run.return_value = result_mock

        tenant_id = "00000000-0000-0000-0000-000000000000"
        exists = await base_service.validate_tenant_exists(tenant_id)

        assert exists is True
        session.run.assert_called_once()
        # Verify the query was called with correct parameters
        call_args, call_kwargs = session.run.call_args
        assert "MATCH (t:Tenant" in call_args[0]
        # Parameters are passed as keyword arguments in the second parameter (a dict)
        assert call_args[1]["tenant_id"] == tenant_id

    @pytest.mark.asyncio
    async def test_validate_tenant_exists_not_found(
        self, base_service, mock_session_manager
    ):
        """Test tenant validation when tenant not found."""
        session = mock_session_manager.session.return_value.__enter__.return_value
        result_mock = MagicMock()
        record_mock = {"exists": False}
        result_mock.single.return_value = record_mock
        session.run.return_value = result_mock

        tenant_id = "11111111-1111-1111-1111-111111111111"
        exists = await base_service.validate_tenant_exists(tenant_id)

        assert exists is False

    @pytest.mark.asyncio
    async def test_count_resources_all(self, base_service, mock_session_manager):
        """Test counting all resources in a tenant."""
        session = mock_session_manager.session.return_value.__enter__.return_value
        result_mock = MagicMock()
        record_mock = {"count": 150}
        result_mock.single.return_value = record_mock
        session.run.return_value = result_mock

        tenant_id = "00000000-0000-0000-0000-000000000000"
        count = await base_service.count_resources(tenant_id, synthetic_only=False)

        assert count == 150
        session.run.assert_called_once()
        call_args = session.run.call_args
        assert "MATCH (r:Resource)" in call_args[0][0]
        assert "NOT r:Original" in call_args[0][0]
        # Should NOT filter by synthetic=true when synthetic_only=False
        assert "r.synthetic = true" not in call_args[0][0]

    @pytest.mark.asyncio
    async def test_count_resources_synthetic_only(
        self, base_service, mock_session_manager
    ):
        """Test counting only synthetic resources."""
        session = mock_session_manager.session.return_value.__enter__.return_value
        result_mock = MagicMock()
        record_mock = {"count": 50}
        result_mock.single.return_value = record_mock
        session.run.return_value = result_mock

        tenant_id = "00000000-0000-0000-0000-000000000000"
        count = await base_service.count_resources(tenant_id, synthetic_only=True)

        assert count == 50
        session.run.assert_called_once()
        call_args = session.run.call_args
        assert "MATCH (r:Resource)" in call_args[0][0]
        assert "NOT r:Original" in call_args[0][0]
        assert "r.synthetic = true" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_generate_session_id(self, base_service):
        """Test session ID generation."""
        session_id = await base_service.generate_session_id()

        # Validate format: scale-{timestamp}-{uuid}
        # Example: scale-20251110T180745-8893990d
        assert session_id.startswith("scale-")
        parts = session_id.split("-")
        # Format is "scale-20251110T180745-8893990d" which splits into ["scale", "20251110T180745", "8893990d"]
        assert len(parts) == 3  # scale, timestamp, uuid
        assert parts[0] == "scale"
        # Timestamp should be in format YYYYMMDDTHHmmss (15 chars)
        assert len(parts[1]) == 15
        assert "T" in parts[1]
        # UUID part should be 8 characters
        assert len(parts[2]) == 8

    @pytest.mark.asyncio
    async def test_generate_session_id_uniqueness(self, base_service):
        """Test that session IDs are unique."""
        session_ids = set()
        for _ in range(100):
            session_id = await base_service.generate_session_id()
            session_ids.add(session_id)

        # All 100 IDs should be unique
        assert len(session_ids) == 100

    @pytest.mark.asyncio
    async def test_get_tenant_info_success(self, base_service, mock_session_manager):
        """Test retrieving tenant information."""
        session = mock_session_manager.session.return_value.__enter__.return_value
        result_mock = MagicMock()

        # Mock Neo4j node
        tenant_node = MagicMock()
        tenant_node.items.return_value = [
            ("id", "00000000-0000-0000-0000-000000000000"),
            ("display_name", "Test Tenant"),
            ("domain", "test.com"),
        ]

        record_mock = {"t": tenant_node}
        result_mock.single.return_value = record_mock
        session.run.return_value = result_mock

        tenant_id = "00000000-0000-0000-0000-000000000000"
        tenant_info = await base_service.get_tenant_info(tenant_id)

        assert tenant_info is not None
        assert tenant_info["id"] == tenant_id
        assert tenant_info["display_name"] == "Test Tenant"
        assert tenant_info["domain"] == "test.com"

    @pytest.mark.asyncio
    async def test_get_tenant_info_not_found(
        self, base_service, mock_session_manager
    ):
        """Test retrieving tenant info when tenant doesn't exist."""
        session = mock_session_manager.session.return_value.__enter__.return_value
        result_mock = MagicMock()
        result_mock.single.return_value = None
        session.run.return_value = result_mock

        tenant_id = "11111111-1111-1111-1111-111111111111"
        tenant_info = await base_service.get_tenant_info(tenant_id)

        assert tenant_info is None

    @pytest.mark.asyncio
    async def test_count_relationships_all(self, base_service, mock_session_manager):
        """Test counting all relationships in a tenant."""
        session = mock_session_manager.session.return_value.__enter__.return_value
        result_mock = MagicMock()
        record_mock = {"count": 300}
        result_mock.single.return_value = record_mock
        session.run.return_value = result_mock

        tenant_id = "00000000-0000-0000-0000-000000000000"
        count = await base_service.count_relationships(tenant_id, synthetic_only=False)

        assert count == 300
        session.run.assert_called_once()
        call_args = session.run.call_args
        assert "MATCH (r1:Resource)-[rel]->(r2:Resource)" in call_args[0][0]
        assert "NOT r1:Original AND NOT r2:Original" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_count_relationships_synthetic_only(
        self, base_service, mock_session_manager
    ):
        """Test counting only synthetic relationships."""
        session = mock_session_manager.session.return_value.__enter__.return_value
        result_mock = MagicMock()
        record_mock = {"count": 100}
        result_mock.single.return_value = record_mock
        session.run.return_value = result_mock

        tenant_id = "00000000-0000-0000-0000-000000000000"
        count = await base_service.count_relationships(tenant_id, synthetic_only=True)

        assert count == 100
        session.run.assert_called_once()
        call_args = session.run.call_args
        assert "r1.synthetic = true OR r2.synthetic = true" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_queries_exclude_original_layer(
        self, base_service, mock_session_manager
    ):
        """Test that all queries exclude the Original layer."""
        session = mock_session_manager.session.return_value.__enter__.return_value
        result_mock = MagicMock()
        record_mock = {"count": 0}
        result_mock.single.return_value = record_mock
        session.run.return_value = result_mock

        tenant_id = "00000000-0000-0000-0000-000000000000"

        # Test count_resources
        await base_service.count_resources(tenant_id)
        call_args = session.run.call_args[0][0]
        assert "NOT r:Original" in call_args

        # Test count_relationships
        await base_service.count_relationships(tenant_id)
        call_args = session.run.call_args[0][0]
        assert "NOT r1:Original AND NOT r2:Original" in call_args
