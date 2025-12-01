"""
Comprehensive test suite for ScaleCleanupService

Tests cleanup operations, preview functionality, batch processing,
and session management with proper mocking.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.services.scale_cleanup_service import ScaleCleanupService
from src.utils.session_manager import Neo4jSessionManager

# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def mock_session_manager():
    """Create a mock Neo4j session manager."""
    manager = MagicMock(spec=Neo4jSessionManager)

    # Create a mock session that can be used as context manager
    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=None)

    # Mock session() method to return the mock session
    manager.session = MagicMock(return_value=mock_session)

    return manager


@pytest.fixture
def mock_session(mock_session_manager):
    """Get the mock session from the manager."""
    return mock_session_manager.session().__enter__()


@pytest.fixture
def cleanup_service(mock_session_manager):
    """Create a ScaleCleanupService instance with mocked dependencies."""
    return ScaleCleanupService(session_manager=mock_session_manager, batch_size=10)


# =========================================================================
# Test: Service Initialization
# =========================================================================


def test_service_initialization(mock_session_manager):
    """Test ScaleCleanupService initializes correctly."""
    service = ScaleCleanupService(session_manager=mock_session_manager, batch_size=1000)

    assert service.session_manager == mock_session_manager
    assert service.batch_size == 1000


def test_service_initialization_defaults(mock_session_manager):
    """Test ScaleCleanupService uses correct defaults."""
    service = ScaleCleanupService(session_manager=mock_session_manager)

    assert service.batch_size == 1000


# =========================================================================
# Test: Preview Cleanup
# =========================================================================


@pytest.mark.asyncio
async def test_preview_cleanup_by_session(cleanup_service, mock_session):
    """Test preview cleanup for specific session."""
    # Mock tenant validation
    with patch.object(cleanup_service, "validate_tenant_exists", return_value=True):
        # Mock query results
        mock_session.run.side_effect = [
            # Resource count query
            MagicMock(single=MagicMock(return_value={"resource_count": 100})),
            # Relationship count query
            MagicMock(
                __iter__=MagicMock(
                    return_value=iter(
                        [
                            {"outgoing_count": 50, "incoming_count": None},
                            {"outgoing_count": None, "incoming_count": 30},
                        ]
                    )
                )
            ),
            # Sessions affected query
            MagicMock(
                __iter__=MagicMock(
                    return_value=iter([{"session_id": "scale-20250110-abc123"}])
                )
            ),
            # Resource types query
            MagicMock(
                __iter__=MagicMock(
                    return_value=iter(
                        [
                            {
                                "resource_type": "Microsoft.Compute/virtualMachines",
                                "count": 60,
                            },
                            {
                                "resource_type": "Microsoft.Network/virtualNetworks",
                                "count": 40,
                            },
                        ]
                    )
                )
            ),
        ]

        result = await cleanup_service.preview_cleanup(
            tenant_id="tenant-123", session_id="scale-20250110-abc123"
        )

        assert result["preview_only"] is True
        assert result["tenant_id"] == "tenant-123"
        assert result["session_id"] == "scale-20250110-abc123"
        assert result["resources_to_delete"] == 100
        assert result["relationships_to_delete"] == 80  # 50 + 30
        assert len(result["sessions_affected"]) == 1
        assert len(result["resource_types"]) == 2


@pytest.mark.asyncio
async def test_preview_cleanup_all(cleanup_service, mock_session):
    """Test preview cleanup for all synthetic data."""
    with patch.object(cleanup_service, "validate_tenant_exists", return_value=True):
        mock_session.run.side_effect = [
            MagicMock(single=MagicMock(return_value={"resource_count": 500})),
            MagicMock(
                __iter__=MagicMock(
                    return_value=iter([{"outgoing_count": 200, "incoming_count": None}])
                )
            ),
            MagicMock(
                __iter__=MagicMock(
                    return_value=iter(
                        [
                            {"session_id": "session-1"},
                            {"session_id": "session-2"},
                        ]
                    )
                )
            ),
            MagicMock(
                __iter__=MagicMock(
                    return_value=iter(
                        [
                            {
                                "resource_type": "Microsoft.Compute/virtualMachines",
                                "count": 500,
                            }
                        ]
                    )
                )
            ),
        ]

        result = await cleanup_service.preview_cleanup(
            tenant_id="tenant-123", clean_all=True
        )

        assert result["clean_all"] is True
        assert result["resources_to_delete"] == 500
        assert len(result["sessions_affected"]) == 2


@pytest.mark.asyncio
async def test_preview_cleanup_before_date(cleanup_service, mock_session):
    """Test preview cleanup for data before specific date."""
    before_date = datetime.now() - timedelta(days=7)

    with patch.object(cleanup_service, "validate_tenant_exists", return_value=True):
        mock_session.run.side_effect = [
            MagicMock(single=MagicMock(return_value={"resource_count": 150})),
            MagicMock(
                __iter__=MagicMock(
                    return_value=iter([{"outgoing_count": 75, "incoming_count": None}])
                )
            ),
            MagicMock(
                __iter__=MagicMock(return_value=iter([{"session_id": "old-session"}]))
            ),
            MagicMock(
                __iter__=MagicMock(
                    return_value=iter([{"resource_type": "Type1", "count": 150}])
                )
            ),
        ]

        result = await cleanup_service.preview_cleanup(
            tenant_id="tenant-123", before_date=before_date
        )

        assert result["before_date"] == before_date.isoformat()
        assert result["resources_to_delete"] == 150


@pytest.mark.asyncio
async def test_preview_cleanup_tenant_not_found(cleanup_service):
    """Test preview fails when tenant doesn't exist."""
    with patch.object(cleanup_service, "validate_tenant_exists", return_value=False):
        with pytest.raises(ValueError, match="not found"):
            await cleanup_service.preview_cleanup(
                tenant_id="nonexistent", clean_all=True
            )


@pytest.mark.asyncio
async def test_preview_cleanup_no_criteria(cleanup_service):
    """Test preview fails when no cleanup criteria provided."""
    with patch.object(cleanup_service, "validate_tenant_exists", return_value=True):
        with pytest.raises(ValueError, match="Must specify"):
            await cleanup_service.preview_cleanup(tenant_id="tenant-123")


# =========================================================================
# Test: Cleanup Synthetic Data
# =========================================================================


@pytest.mark.asyncio
async def test_cleanup_by_session_success(cleanup_service, mock_session):
    """Test successful cleanup by session ID."""
    with patch.object(cleanup_service, "validate_tenant_exists", return_value=True):
        # Mock session list query
        mock_session.run.side_effect = [
            # Session list query
            MagicMock(
                __iter__=MagicMock(return_value=iter([{"session_id": "session-1"}]))
            ),
            # First delete batch
            MagicMock(
                single=MagicMock(
                    return_value={
                        "deleted_count": 10,
                        "outgoing_rels": 5,
                        "incoming_rels": 3,
                    }
                )
            ),
            # Second delete batch (empty, signals end)
            MagicMock(single=MagicMock(return_value={"deleted_count": 0})),
        ]

        result = await cleanup_service.cleanup_synthetic_data(
            tenant_id="tenant-123", session_id="session-1"
        )

        assert result["success"] is True
        assert result["resources_deleted"] == 10
        assert result["relationships_deleted"] == 8  # 5 + 3
        assert result["session_id"] == "session-1"
        assert "session-1" in result["sessions_cleaned"]


@pytest.mark.asyncio
async def test_cleanup_all_synthetic_data(cleanup_service, mock_session):
    """Test cleanup all synthetic data for tenant."""
    with patch.object(cleanup_service, "validate_tenant_exists", return_value=True):
        mock_session.run.side_effect = [
            # Session list
            MagicMock(
                __iter__=MagicMock(
                    return_value=iter([{"session_id": "s1"}, {"session_id": "s2"}])
                )
            ),
            # First batch
            MagicMock(
                single=MagicMock(
                    return_value={
                        "deleted_count": 10,
                        "outgoing_rels": 5,
                        "incoming_rels": 5,
                    }
                )
            ),
            # Second batch
            MagicMock(
                single=MagicMock(
                    return_value={
                        "deleted_count": 10,
                        "outgoing_rels": 5,
                        "incoming_rels": 5,
                    }
                )
            ),
            # Third batch (partial)
            MagicMock(
                single=MagicMock(
                    return_value={
                        "deleted_count": 5,
                        "outgoing_rels": 2,
                        "incoming_rels": 2,
                    }
                )
            ),
        ]

        result = await cleanup_service.cleanup_synthetic_data(
            tenant_id="tenant-123", clean_all=True
        )

        assert result["success"] is True
        assert result["resources_deleted"] == 25
        assert result["relationships_deleted"] == 24
        assert result["clean_all"] is True


@pytest.mark.asyncio
async def test_cleanup_before_date(cleanup_service, mock_session):
    """Test cleanup data before specific date."""
    before_date = datetime.now() - timedelta(days=30)

    with patch.object(cleanup_service, "validate_tenant_exists", return_value=True):
        mock_session.run.side_effect = [
            MagicMock(
                __iter__=MagicMock(return_value=iter([{"session_id": "old-session"}]))
            ),
            MagicMock(
                single=MagicMock(
                    return_value={
                        "deleted_count": 50,
                        "outgoing_rels": 25,
                        "incoming_rels": 25,
                    }
                )
            ),
            MagicMock(single=MagicMock(return_value={"deleted_count": 0})),
        ]

        result = await cleanup_service.cleanup_synthetic_data(
            tenant_id="tenant-123", before_date=before_date
        )

        assert result["success"] is True
        assert result["resources_deleted"] == 50
        assert result["before_date"] == before_date.isoformat()


@pytest.mark.asyncio
async def test_cleanup_with_progress_callback(cleanup_service, mock_session):
    """Test cleanup with progress callback."""
    progress_updates = []

    def progress_callback(message, current, total):
        progress_updates.append(
            {"message": message, "current": current, "total": total}
        )

    with patch.object(cleanup_service, "validate_tenant_exists", return_value=True):
        mock_session.run.side_effect = [
            MagicMock(__iter__=MagicMock(return_value=iter([{"session_id": "s1"}]))),
            MagicMock(
                single=MagicMock(
                    return_value={
                        "deleted_count": 10,
                        "outgoing_rels": 5,
                        "incoming_rels": 5,
                    }
                )
            ),
            MagicMock(single=MagicMock(return_value={"deleted_count": 0})),
        ]

        result = await cleanup_service.cleanup_synthetic_data(
            tenant_id="tenant-123",
            session_id="s1",
            progress_callback=progress_callback,
        )

        assert result["success"] is True
        assert len(progress_updates) >= 2  # At least start and end messages


@pytest.mark.asyncio
async def test_cleanup_tenant_not_found(cleanup_service):
    """Test cleanup fails when tenant doesn't exist."""
    with patch.object(cleanup_service, "validate_tenant_exists", return_value=False):
        with pytest.raises(ValueError, match="not found"):
            await cleanup_service.cleanup_synthetic_data(
                tenant_id="nonexistent", clean_all=True
            )


@pytest.mark.asyncio
async def test_cleanup_no_criteria(cleanup_service):
    """Test cleanup fails when no criteria provided."""
    with patch.object(cleanup_service, "validate_tenant_exists", return_value=True):
        with pytest.raises(ValueError, match="Must specify"):
            await cleanup_service.cleanup_synthetic_data(tenant_id="tenant-123")


@pytest.mark.asyncio
async def test_cleanup_error_handling(cleanup_service, mock_session):
    """Test cleanup handles errors gracefully."""
    with patch.object(cleanup_service, "validate_tenant_exists", return_value=True):
        # Simulate database error
        mock_session.run.side_effect = [
            MagicMock(__iter__=MagicMock(return_value=iter([{"session_id": "s1"}]))),
            Exception("Database connection failed"),
        ]

        result = await cleanup_service.cleanup_synthetic_data(
            tenant_id="tenant-123", session_id="s1"
        )

        assert result["success"] is False
        assert "error_message" in result
        assert "Database connection failed" in result["error_message"]


# =========================================================================
# Test: Get Cleanable Sessions
# =========================================================================


@pytest.mark.asyncio
async def test_get_cleanable_sessions_success(cleanup_service, mock_session):
    """Test getting list of cleanable sessions."""
    with patch.object(cleanup_service, "validate_tenant_exists", return_value=True):
        mock_session.run.return_value = MagicMock(
            __iter__=MagicMock(
                return_value=iter(
                    [
                        {
                            "session_id": "session-1",
                            "resource_count": 100,
                            "resource_types": ["Type1", "Type2"],
                            "generation_strategy": "template",
                            "generation_timestamp": "2025-01-10T12:00:00",
                        },
                        {
                            "session_id": "session-2",
                            "resource_count": 50,
                            "resource_types": ["Type3"],
                            "generation_strategy": "random",
                            "generation_timestamp": "2025-01-09T12:00:00",
                        },
                    ]
                )
            )
        )

        sessions = await cleanup_service.get_cleanable_sessions("tenant-123")

        assert len(sessions) == 2
        assert sessions[0]["session_id"] == "session-1"
        assert sessions[0]["resource_count"] == 100
        assert sessions[0]["generation_strategy"] == "template"
        assert sessions[1]["session_id"] == "session-2"


@pytest.mark.asyncio
async def test_get_cleanable_sessions_empty(cleanup_service, mock_session):
    """Test getting sessions when none exist."""
    with patch.object(cleanup_service, "validate_tenant_exists", return_value=True):
        mock_session.run.return_value = MagicMock(
            __iter__=MagicMock(return_value=iter([]))
        )

        sessions = await cleanup_service.get_cleanable_sessions("tenant-123")

        assert len(sessions) == 0


@pytest.mark.asyncio
async def test_get_cleanable_sessions_tenant_not_found(cleanup_service):
    """Test get sessions fails when tenant doesn't exist."""
    with patch.object(cleanup_service, "validate_tenant_exists", return_value=False):
        with pytest.raises(ValueError, match="not found"):
            await cleanup_service.get_cleanable_sessions("nonexistent")


# =========================================================================
# Test: Edge Cases
# =========================================================================


@pytest.mark.asyncio
async def test_cleanup_no_resources_to_delete(cleanup_service, mock_session):
    """Test cleanup when no resources match criteria."""
    with patch.object(cleanup_service, "validate_tenant_exists", return_value=True):
        mock_session.run.side_effect = [
            MagicMock(__iter__=MagicMock(return_value=iter([]))),  # No sessions
            MagicMock(single=MagicMock(return_value={"deleted_count": 0})),
        ]

        result = await cleanup_service.cleanup_synthetic_data(
            tenant_id="tenant-123", session_id="nonexistent-session"
        )

        assert result["success"] is True
        assert result["resources_deleted"] == 0
        assert result["relationships_deleted"] == 0


@pytest.mark.asyncio
async def test_preview_cleanup_with_null_relationships(cleanup_service, mock_session):
    """Test preview handles null relationship counts gracefully."""
    with patch.object(cleanup_service, "validate_tenant_exists", return_value=True):
        mock_session.run.side_effect = [
            MagicMock(single=MagicMock(return_value={"resource_count": 10})),
            MagicMock(__iter__=MagicMock(return_value=iter([]))),  # No relationships
            MagicMock(__iter__=MagicMock(return_value=iter([{"session_id": "s1"}]))),
            MagicMock(
                __iter__=MagicMock(
                    return_value=iter([{"resource_type": "Type1", "count": 10}])
                )
            ),
        ]

        result = await cleanup_service.preview_cleanup(
            tenant_id="tenant-123", session_id="s1"
        )

        assert result["resources_to_delete"] == 10
        assert result["relationships_to_delete"] == 0
