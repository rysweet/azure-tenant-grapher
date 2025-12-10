"""
Comprehensive test suite for ScaleStatsService

Tests statistics generation, tenant comparison, session history,
and export functionality with proper mocking.
"""

from unittest.mock import MagicMock, mock_open, patch

import pytest

from src.services.scale_stats_service import ScaleStatsService
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
def stats_service(mock_session_manager):
    """Create a ScaleStatsService instance with mocked dependencies."""
    return ScaleStatsService(session_manager=mock_session_manager)


# =========================================================================
# Test: Service Initialization
# =========================================================================


def test_service_initialization(mock_session_manager):
    """Test ScaleStatsService initializes correctly."""
    service = ScaleStatsService(session_manager=mock_session_manager)

    assert service.session_manager == mock_session_manager


# =========================================================================
# Test: Get Tenant Stats - Basic
# =========================================================================


@pytest.mark.asyncio
async def test_get_tenant_stats_basic(stats_service, mock_session):
    """Test getting basic tenant statistics."""
    with patch.object(stats_service, "validate_tenant_exists", return_value=True):
        # Mock query results
        mock_session.run.side_effect = [
            # Resource counts query
            MagicMock(
                __iter__=MagicMock(
                    return_value=iter(
                        [
                            {"category": "original", "count": 100},
                            {"category": "synthetic", "count": 50},
                        ]
                    )
                )
            ),
            # Type breakdown query
            MagicMock(
                __iter__=MagicMock(
                    return_value=iter(
                        [
                            {
                                "resource_type": "Microsoft.Compute/virtualMachines",
                                "category": "original",
                                "count": 60,
                            },
                            {
                                "resource_type": "Microsoft.Compute/virtualMachines",
                                "category": "synthetic",
                                "count": 30,
                            },
                            {
                                "resource_type": "Microsoft.Network/virtualNetworks",
                                "category": "original",
                                "count": 40,
                            },
                            {
                                "resource_type": "Microsoft.Network/virtualNetworks",
                                "category": "synthetic",
                                "count": 20,
                            },
                        ]
                    )
                )
            ),
            # Session summary query
            MagicMock(
                __iter__=MagicMock(
                    return_value=iter(
                        [
                            {
                                "session_id": "scale-123",
                                "resource_count": 50,
                                "strategy": "template",
                                "timestamp": "2025-01-10T12:00:00",
                            }
                        ]
                    )
                )
            ),
            # Relationship counts query
            MagicMock(
                __iter__=MagicMock(
                    return_value=iter(
                        [
                            {"category": "original", "count": 200},
                            {"category": "synthetic", "count": 100},
                        ]
                    )
                )
            ),
        ]

        stats = await stats_service.get_tenant_stats("tenant-123")

        assert stats["tenant_id"] == "tenant-123"
        assert stats["total_resources"] == 150  # 100 + 50
        assert stats["original_resources"] == 100
        assert stats["synthetic_resources"] == 50
        assert stats["synthetic_percentage"] == pytest.approx(33.33, rel=0.1)
        assert stats["relationship_count"] == 300  # 200 + 100
        assert stats["session_count"] == 1


@pytest.mark.asyncio
async def test_get_tenant_stats_detailed(stats_service, mock_session):
    """Test getting detailed tenant statistics."""
    with patch.object(stats_service, "validate_tenant_exists", return_value=True):
        mock_session.run.side_effect = [
            MagicMock(
                __iter__=MagicMock(
                    return_value=iter([{"category": "original", "count": 100}])
                )
            ),
            MagicMock(
                __iter__=MagicMock(
                    return_value=iter(
                        [
                            {
                                "resource_type": "Type1",
                                "category": "original",
                                "count": 100,
                            }
                        ]
                    )
                )
            ),
            MagicMock(
                __iter__=MagicMock(
                    return_value=iter(
                        [
                            {
                                "session_id": "session-1",
                                "resource_count": 50,
                                "strategy": "template",
                                "timestamp": "2025-01-10T12:00:00",
                            },
                            {
                                "session_id": "session-2",
                                "resource_count": 30,
                                "strategy": "random",
                                "timestamp": "2025-01-09T12:00:00",
                            },
                        ]
                    )
                )
            ),
            MagicMock(
                __iter__=MagicMock(
                    return_value=iter([{"category": "original", "count": 200}])
                )
            ),
        ]

        stats = await stats_service.get_tenant_stats("tenant-123", detailed=True)

        assert "sessions" in stats
        assert len(stats["sessions"]) == 2
        assert stats["sessions"][0]["session_id"] == "session-1"
        assert stats["sessions"][1]["session_id"] == "session-2"


@pytest.mark.asyncio
async def test_get_tenant_stats_no_synthetic_data(stats_service, mock_session):
    """Test stats when no synthetic data exists."""
    with patch.object(stats_service, "validate_tenant_exists", return_value=True):
        mock_session.run.side_effect = [
            MagicMock(
                __iter__=MagicMock(
                    return_value=iter([{"category": "original", "count": 100}])
                )
            ),
            MagicMock(
                __iter__=MagicMock(
                    return_value=iter(
                        [
                            {
                                "resource_type": "Type1",
                                "category": "original",
                                "count": 100,
                            }
                        ]
                    )
                )
            ),
            MagicMock(__iter__=MagicMock(return_value=iter([]))),  # No sessions
            MagicMock(
                __iter__=MagicMock(
                    return_value=iter([{"category": "original", "count": 200}])
                )
            ),
        ]

        stats = await stats_service.get_tenant_stats("tenant-123")

        assert stats["total_resources"] == 100
        assert stats["synthetic_resources"] == 0
        assert stats["synthetic_percentage"] == 0.0
        assert stats["session_count"] == 0


@pytest.mark.asyncio
async def test_get_tenant_stats_tenant_not_found(stats_service):
    """Test stats fails when tenant doesn't exist."""
    with patch.object(stats_service, "validate_tenant_exists", return_value=False):
        with pytest.raises(ValueError, match="not found"):
            await stats_service.get_tenant_stats("nonexistent")


# =========================================================================
# Test: Compare Tenants
# =========================================================================


@pytest.mark.asyncio
async def test_compare_tenants_success(stats_service):
    """Test comparing multiple tenants."""
    mock_stats_1 = {
        "total_resources": 100,
        "original_resources": 60,
        "synthetic_resources": 40,
        "synthetic_percentage": 40.0,
        "relationship_count": 200,
        "session_count": 2,
    }

    mock_stats_2 = {
        "total_resources": 150,
        "original_resources": 100,
        "synthetic_resources": 50,
        "synthetic_percentage": 33.33,
        "relationship_count": 300,
        "session_count": 3,
    }

    with patch.object(stats_service, "validate_tenant_exists", return_value=True):
        with patch.object(
            stats_service,
            "get_tenant_stats",
            side_effect=[mock_stats_1, mock_stats_2],
        ):
            result = await stats_service.compare_tenants(
                ["tenant-1", "tenant-2"], detailed=False
            )

            assert result["tenant_count"] == 2
            assert result["summary"]["total_resources"] == 250  # 100 + 150
            assert result["summary"]["total_synthetic_resources"] == 90  # 40 + 50
            assert result["summary"]["total_sessions"] == 5  # 2 + 3
            assert "comparison_metrics" in result
            assert result["comparison_metrics"]["synthetic_percentage"]["min"] == 33.33
            assert result["comparison_metrics"]["synthetic_percentage"]["max"] == 40.0


@pytest.mark.asyncio
async def test_compare_tenants_detailed(stats_service):
    """Test comparing tenants with detailed stats."""
    mock_stats_1 = {
        "tenant_id": "tenant-1",
        "total_resources": 100,
        "original_resources": 60,
        "synthetic_resources": 40,
        "synthetic_percentage": 40.0,
        "relationship_count": 200,
        "session_count": 2,
    }

    with patch.object(stats_service, "validate_tenant_exists", return_value=True):
        with patch.object(stats_service, "get_tenant_stats", return_value=mock_stats_1):
            result = await stats_service.compare_tenants(["tenant-1"], detailed=True)

            assert isinstance(result["tenants"], dict)
            assert "tenant-1" in result["tenants"]


@pytest.mark.asyncio
async def test_compare_tenants_empty_list(stats_service):
    """Test comparison fails with empty tenant list."""
    with pytest.raises(ValueError, match="cannot be empty"):
        await stats_service.compare_tenants([])


@pytest.mark.asyncio
async def test_compare_tenants_too_many(stats_service):
    """Test comparison fails with too many tenants."""
    tenant_ids = [f"tenant-{i}" for i in range(101)]

    with pytest.raises(ValueError, match="Cannot compare more than 100"):
        await stats_service.compare_tenants(tenant_ids)


@pytest.mark.asyncio
async def test_compare_tenants_nonexistent_tenant(stats_service):
    """Test comparison fails if any tenant doesn't exist."""
    with patch.object(stats_service, "validate_tenant_exists", return_value=False):
        with pytest.raises(ValueError, match="not found"):
            await stats_service.compare_tenants(["nonexistent"])


# =========================================================================
# Test: Get Session History
# =========================================================================


@pytest.mark.asyncio
async def test_get_session_history_success(stats_service, mock_session):
    """Test getting session history."""
    with patch.object(stats_service, "validate_tenant_exists", return_value=True):
        mock_session.run.return_value = MagicMock(
            __iter__=MagicMock(
                return_value=iter(
                    [
                        {
                            "session_id": "scale-123",
                            "strategy": "template",
                            "timestamp": "2025-01-10T12:00:00",
                            "resource_count": 100,
                            "relationship_count": 50,
                            "resource_types": ["Type1", "Type2"],
                        },
                        {
                            "session_id": "scale-456",
                            "strategy": "random",
                            "timestamp": "2025-01-09T12:00:00",
                            "resource_count": 50,
                            "relationship_count": 25,
                            "resource_types": ["Type3"],
                        },
                    ]
                )
            )
        )

        history = await stats_service.get_session_history("tenant-123")

        assert len(history) == 2
        assert history[0]["session_id"] == "scale-123"
        assert history[0]["strategy"] == "template"
        assert history[0]["resource_count"] == 100
        assert history[1]["session_id"] == "scale-456"


@pytest.mark.asyncio
async def test_get_session_history_empty(stats_service, mock_session):
    """Test session history when no sessions exist."""
    with patch.object(stats_service, "validate_tenant_exists", return_value=True):
        mock_session.run.return_value = MagicMock(
            __iter__=MagicMock(return_value=iter([]))
        )

        history = await stats_service.get_session_history("tenant-123")

        assert len(history) == 0


@pytest.mark.asyncio
async def test_get_session_history_tenant_not_found(stats_service):
    """Test session history fails when tenant doesn't exist."""
    with patch.object(stats_service, "validate_tenant_exists", return_value=False):
        with pytest.raises(ValueError, match="not found"):
            await stats_service.get_session_history("nonexistent")


# =========================================================================
# Test: Export Stats - JSON
# =========================================================================


@pytest.mark.asyncio
async def test_export_stats_json_format(stats_service):
    """Test exporting stats in JSON format."""
    mock_stats = {
        "tenant_id": "tenant-123",
        "timestamp": "2025-01-10T12:00:00",
        "total_resources": 100,
        "synthetic_percentage": 40.0,
    }

    with patch.object(stats_service, "get_tenant_stats", return_value=mock_stats):
        output = await stats_service.export_stats(tenant_id="tenant-123", format="json")

        assert "tenant-123" in output
        assert "100" in output
        assert "40.0" in output


@pytest.mark.asyncio
async def test_export_stats_json_to_file(stats_service):
    """Test exporting JSON stats to file."""
    mock_stats = {"tenant_id": "tenant-123", "total_resources": 100}

    with patch.object(stats_service, "get_tenant_stats", return_value=mock_stats):
        with patch("builtins.open", mock_open()) as mock_file:
            output = await stats_service.export_stats(
                tenant_id="tenant-123",
                format="json",
                output_path="/tmp/stats.json",
            )

            mock_file.assert_called_once_with("/tmp/stats.json", "w")
            assert "tenant-123" in output


# =========================================================================
# Test: Export Stats - Markdown
# =========================================================================


@pytest.mark.asyncio
async def test_export_stats_markdown_format(stats_service):
    """Test exporting stats in Markdown format."""
    mock_stats = {
        "tenant_id": "tenant-123",
        "timestamp": "2025-01-10T12:00:00",
        "total_resources": 100,
        "original_resources": 60,
        "synthetic_resources": 40,
        "synthetic_percentage": 40.0,
        "relationship_count": 200,
        "original_relationships": 120,
        "synthetic_relationships": 80,
        "session_count": 2,
        "resource_type_breakdown": {
            "Microsoft.Compute/virtualMachines": {
                "original": 30,
                "synthetic": 20,
                "total": 50,
            }
        },
    }

    with patch.object(stats_service, "get_tenant_stats", return_value=mock_stats):
        output = await stats_service.export_stats(
            tenant_id="tenant-123", format="markdown"
        )

        assert "# Tenant Statistics" in output
        assert "tenant-123" in output
        assert "**Total Resources:** 100" in output
        assert "| Resource Type |" in output


@pytest.mark.asyncio
async def test_export_stats_markdown_with_sessions(stats_service):
    """Test Markdown export includes session details when detailed=True."""
    mock_stats = {
        "tenant_id": "tenant-123",
        "timestamp": "2025-01-10T12:00:00",
        "total_resources": 100,
        "original_resources": 60,
        "synthetic_resources": 40,
        "synthetic_percentage": 40.0,
        "relationship_count": 200,
        "original_relationships": 120,
        "synthetic_relationships": 80,
        "session_count": 2,
        "resource_type_breakdown": {},
        "sessions": [
            {
                "session_id": "scale-123",
                "strategy": "template",
                "resource_count": 40,
                "timestamp": "2025-01-10T12:00:00",
            }
        ],
    }

    with patch.object(stats_service, "get_tenant_stats", return_value=mock_stats):
        output = await stats_service.export_stats(
            tenant_id="tenant-123", format="markdown", detailed=True
        )

        assert "## Scale Operation Sessions" in output
        assert "scale-123" in output


# =========================================================================
# Test: Export Stats - Table
# =========================================================================


@pytest.mark.asyncio
async def test_export_stats_table_format(stats_service):
    """Test exporting stats in ASCII table format."""
    mock_stats = {
        "tenant_id": "tenant-123",
        "timestamp": "2025-01-10T12:00:00",
        "total_resources": 100,
        "original_resources": 60,
        "synthetic_resources": 40,
        "synthetic_percentage": 40.0,
        "relationship_count": 200,
        "original_relationships": 120,
        "synthetic_relationships": 80,
        "session_count": 2,
        "resource_type_breakdown": {
            "Microsoft.Compute/virtualMachines": {
                "original": 30,
                "synthetic": 20,
                "total": 50,
            }
        },
    }

    with patch.object(stats_service, "get_tenant_stats", return_value=mock_stats):
        output = await stats_service.export_stats(
            tenant_id="tenant-123", format="table"
        )

        assert "Tenant Statistics" in output
        assert "tenant-123" in output
        assert "Total Resources:" in output
        assert "=" * 80 in output
        assert "-" * 80 in output


# =========================================================================
# Test: Export Stats - Error Cases
# =========================================================================


@pytest.mark.asyncio
async def test_export_stats_invalid_format(stats_service):
    """Test export fails with invalid format."""
    with pytest.raises(ValueError, match="Invalid format"):
        await stats_service.export_stats(tenant_id="tenant-123", format="invalid")


@pytest.mark.asyncio
async def test_export_stats_tenant_not_found(stats_service):
    """Test export fails when tenant doesn't exist."""
    with patch.object(
        stats_service,
        "get_tenant_stats",
        side_effect=ValueError("not found"),
    ):
        with pytest.raises(ValueError, match="not found"):
            await stats_service.export_stats(tenant_id="nonexistent", format="json")


# =========================================================================
# Test: Format Methods
# =========================================================================


def test_format_markdown_basic(stats_service):
    """Test Markdown formatting."""
    stats = {
        "tenant_id": "tenant-123",
        "timestamp": "2025-01-10T12:00:00",
        "total_resources": 100,
        "original_resources": 60,
        "synthetic_resources": 40,
        "synthetic_percentage": 40.0,
        "relationship_count": 200,
        "original_relationships": 120,
        "synthetic_relationships": 80,
        "session_count": 2,
        "resource_type_breakdown": {},
    }

    output = stats_service._format_markdown(stats)

    assert "# Tenant Statistics" in output
    assert "tenant-123" in output
    assert "100" in output


def test_format_table_basic(stats_service):
    """Test ASCII table formatting."""
    stats = {
        "tenant_id": "tenant-123",
        "timestamp": "2025-01-10T12:00:00",
        "total_resources": 100,
        "original_resources": 60,
        "synthetic_resources": 40,
        "synthetic_percentage": 40.0,
        "relationship_count": 200,
        "original_relationships": 120,
        "synthetic_relationships": 80,
        "session_count": 2,
        "resource_type_breakdown": {},
    }

    output = stats_service._format_table(stats)

    assert "Tenant Statistics" in output
    assert "tenant-123" in output
    assert "=" * 80 in output


def test_format_table_with_long_resource_types(stats_service):
    """Test table formatting truncates long resource type names."""
    stats = {
        "tenant_id": "tenant-123",
        "timestamp": "2025-01-10T12:00:00",
        "total_resources": 100,
        "original_resources": 60,
        "synthetic_resources": 40,
        "synthetic_percentage": 40.0,
        "relationship_count": 200,
        "original_relationships": 120,
        "synthetic_relationships": 80,
        "session_count": 2,
        "resource_type_breakdown": {
            "A" * 100: {"original": 10, "synthetic": 5, "total": 15}  # Very long name
        },
    }

    output = stats_service._format_table(stats)

    # Should truncate long names
    assert "..." in output


# =========================================================================
# Test: Edge Cases
# =========================================================================


@pytest.mark.asyncio
async def test_get_tenant_stats_all_synthetic(stats_service, mock_session):
    """Test stats when all resources are synthetic."""
    with patch.object(stats_service, "validate_tenant_exists", return_value=True):
        mock_session.run.side_effect = [
            MagicMock(
                __iter__=MagicMock(
                    return_value=iter([{"category": "synthetic", "count": 100}])
                )
            ),
            MagicMock(
                __iter__=MagicMock(
                    return_value=iter(
                        [
                            {
                                "resource_type": "Type1",
                                "category": "synthetic",
                                "count": 100,
                            }
                        ]
                    )
                )
            ),
            MagicMock(
                __iter__=MagicMock(
                    return_value=iter(
                        [
                            {
                                "session_id": "s1",
                                "resource_count": 100,
                                "strategy": "template",
                                "timestamp": "2025-01-10T12:00:00",
                            }
                        ]
                    )
                )
            ),
            MagicMock(
                __iter__=MagicMock(
                    return_value=iter([{"category": "synthetic", "count": 200}])
                )
            ),
        ]

        stats = await stats_service.get_tenant_stats("tenant-123")

        assert stats["total_resources"] == 100
        assert stats["original_resources"] == 0
        assert stats["synthetic_resources"] == 100
        assert stats["synthetic_percentage"] == 100.0


@pytest.mark.asyncio
async def test_compare_tenants_single_tenant(stats_service):
    """Test comparing a single tenant."""
    mock_stats = {
        "total_resources": 100,
        "original_resources": 60,
        "synthetic_resources": 40,
        "synthetic_percentage": 40.0,
        "relationship_count": 200,
        "session_count": 2,
    }

    with patch.object(stats_service, "validate_tenant_exists", return_value=True):
        with patch.object(stats_service, "get_tenant_stats", return_value=mock_stats):
            result = await stats_service.compare_tenants(["tenant-1"])

            assert result["tenant_count"] == 1
            assert result["summary"]["total_resources"] == 100
