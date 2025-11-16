"""
Comprehensive test suite for ScaleValidationService

Tests validation checks, auto-fix functionality, issue detection,
and error handling with proper mocking.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.services.scale_validation_service import ScaleValidationService
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
def validation_service(mock_session_manager):
    """Create a ScaleValidationService instance with mocked dependencies."""
    return ScaleValidationService(
        session_manager=mock_session_manager, batch_size=10
    )


# =========================================================================
# Test: Service Initialization
# =========================================================================


def test_service_initialization(mock_session_manager):
    """Test ScaleValidationService initializes correctly."""
    service = ScaleValidationService(
        session_manager=mock_session_manager, batch_size=1000
    )

    assert service.session_manager == mock_session_manager
    assert service.batch_size == 1000


def test_service_initialization_defaults(mock_session_manager):
    """Test ScaleValidationService uses correct defaults."""
    service = ScaleValidationService(session_manager=mock_session_manager)

    assert service.batch_size == 1000


# =========================================================================
# Test: Validate Graph - All Checks Pass
# =========================================================================


@pytest.mark.asyncio
async def test_validate_graph_all_checks_pass(validation_service, mock_session):
    """Test validation when all checks pass."""
    with patch.object(validation_service, "validate_tenant_exists", return_value=True):
        # Mock all validation checks to return no issues
        with patch.object(
            validation_service, "_check_original_contamination", return_value=[]
        ), patch.object(
            validation_service, "_check_scan_source_links", return_value=[]
        ), patch.object(
            validation_service, "_check_synthetic_markers", return_value=[]
        ), patch.object(
            validation_service, "_check_graph_structure", return_value=[]
        ):

            result = await validation_service.validate_graph(
                tenant_id="tenant-123", check_type="all"
            )

            assert result["success"] is True
            assert len(result["checks_run"]) == 4
            assert len(result["checks_passed"]) == 4
            assert len(result["checks_failed"]) == 0
            assert result["issue_count"] == 0
            assert result["auto_fix_applied"] is False


# =========================================================================
# Test: Validate Graph - Individual Check Types
# =========================================================================


@pytest.mark.asyncio
async def test_validate_graph_original_contamination_only(validation_service):
    """Test validation for Original contamination check only."""
    with patch.object(validation_service, "validate_tenant_exists", return_value=True):
        with patch.object(
            validation_service, "_check_original_contamination", return_value=[]
        ):

            result = await validation_service.validate_graph(
                tenant_id="tenant-123", check_type="original"
            )

            assert result["success"] is True
            assert len(result["checks_run"]) == 1
            assert "original_contamination" in result["checks_run"]


@pytest.mark.asyncio
async def test_validate_graph_scan_links_only(validation_service):
    """Test validation for SCAN_SOURCE_NODE links check only."""
    with patch.object(validation_service, "validate_tenant_exists", return_value=True):
        with patch.object(
            validation_service, "_check_scan_source_links", return_value=[]
        ):

            result = await validation_service.validate_graph(
                tenant_id="tenant-123", check_type="scan_links"
            )

            assert result["success"] is True
            assert len(result["checks_run"]) == 1
            assert "scan_source_links" in result["checks_run"]


@pytest.mark.asyncio
async def test_validate_graph_markers_only(validation_service):
    """Test validation for synthetic markers check only."""
    with patch.object(validation_service, "validate_tenant_exists", return_value=True):
        with patch.object(
            validation_service, "_check_synthetic_markers", return_value=[]
        ):

            result = await validation_service.validate_graph(
                tenant_id="tenant-123", check_type="markers"
            )

            assert result["success"] is True
            assert len(result["checks_run"]) == 1
            assert "synthetic_markers" in result["checks_run"]


@pytest.mark.asyncio
async def test_validate_graph_structure_only(validation_service):
    """Test validation for graph structure check only."""
    with patch.object(validation_service, "validate_tenant_exists", return_value=True):
        with patch.object(
            validation_service, "_check_graph_structure", return_value=[]
        ):

            result = await validation_service.validate_graph(
                tenant_id="tenant-123", check_type="structure"
            )

            assert result["success"] is True
            assert len(result["checks_run"]) == 1
            assert "graph_structure" in result["checks_run"]


# =========================================================================
# Test: Validate Graph - Issues Detected
# =========================================================================


@pytest.mark.asyncio
async def test_validate_graph_with_issues(validation_service):
    """Test validation when issues are detected."""
    mock_issues = [
        {
            "type": "original_contamination",
            "severity": "critical",
            "resource_id": "vm-123",
            "message": "Synthetic resource in Original layer",
        },
        {
            "type": "invalid_scan_link",
            "severity": "high",
            "resource_id": "vm-456",
            "message": "Invalid SCAN_SOURCE_NODE link",
        },
    ]

    with patch.object(validation_service, "validate_tenant_exists", return_value=True):
        with patch.object(
            validation_service, "_check_original_contamination", return_value=mock_issues[:1]
        ), patch.object(
            validation_service, "_check_scan_source_links", return_value=mock_issues[1:]
        ), patch.object(
            validation_service, "_check_synthetic_markers", return_value=[]
        ), patch.object(
            validation_service, "_check_graph_structure", return_value=[]
        ):

            result = await validation_service.validate_graph(
                tenant_id="tenant-123", check_type="all"
            )

            assert result["success"] is False
            assert len(result["issues"]) == 2
            assert len(result["checks_failed"]) == 2
            assert result["issue_count"] == 2


# =========================================================================
# Test: Validate Graph - Auto-Fix
# =========================================================================


@pytest.mark.asyncio
async def test_validate_graph_with_auto_fix(validation_service):
    """Test validation with auto-fix enabled."""
    mock_issues = [
        {
            "type": "invalid_scan_link",
            "severity": "high",
            "resource_id": "vm-123",
            "message": "Invalid link",
        }
    ]

    with patch.object(validation_service, "validate_tenant_exists", return_value=True):
        with patch.object(
            validation_service, "_check_original_contamination", return_value=[]
        ), patch.object(
            validation_service, "_check_scan_source_links", return_value=mock_issues
        ), patch.object(
            validation_service, "_check_synthetic_markers", return_value=[]
        ), patch.object(
            validation_service, "_check_graph_structure", return_value=[]
        ), patch.object(
            validation_service, "_apply_auto_fixes", return_value=1
        ):

            result = await validation_service.validate_graph(
                tenant_id="tenant-123", check_type="all", auto_fix=True
            )

            assert result["auto_fix_applied"] is True
            assert result["fixes_applied"] == 1


# =========================================================================
# Test: Validate Graph - Error Cases
# =========================================================================


@pytest.mark.asyncio
async def test_validate_graph_tenant_not_found(validation_service):
    """Test validation fails when tenant doesn't exist."""
    with patch.object(validation_service, "validate_tenant_exists", return_value=False):
        with pytest.raises(ValueError, match="not found"):
            await validation_service.validate_graph(
                tenant_id="nonexistent", check_type="all"
            )


@pytest.mark.asyncio
async def test_validate_graph_invalid_check_type(validation_service):
    """Test validation fails with invalid check type."""
    with patch.object(validation_service, "validate_tenant_exists", return_value=True):
        with pytest.raises(ValueError, match="Invalid check_type"):
            await validation_service.validate_graph(
                tenant_id="tenant-123", check_type="invalid"
            )


@pytest.mark.asyncio
async def test_validate_graph_with_progress_callback(validation_service):
    """Test validation with progress callback."""
    progress_updates = []

    def progress_callback(message, current, total):
        progress_updates.append({"message": message, "current": current, "total": total})

    with patch.object(validation_service, "validate_tenant_exists", return_value=True):
        with patch.object(
            validation_service, "_check_original_contamination", return_value=[]
        ), patch.object(
            validation_service, "_check_scan_source_links", return_value=[]
        ), patch.object(
            validation_service, "_check_synthetic_markers", return_value=[]
        ), patch.object(
            validation_service, "_check_graph_structure", return_value=[]
        ):

            result = await validation_service.validate_graph(
                tenant_id="tenant-123",
                check_type="all",
                progress_callback=progress_callback,
            )

            assert result["success"] is True
            assert len(progress_updates) >= 4  # At least one per check


# =========================================================================
# Test: Fix Validation Issues
# =========================================================================


@pytest.mark.asyncio
async def test_fix_validation_issues_success(validation_service, mock_session):
    """Test successful fixing of validation issues."""
    issues = [
        {
            "type": "missing_marker",
            "resource_id": "vm-123",
            "missing_markers": ["scale_operation_id"],
        },
        {
            "type": "invalid_scan_link",
            "resource_id": "vm-456",
        },
    ]

    with patch.object(validation_service, "validate_tenant_exists", return_value=True):
        with patch.object(validation_service, "_fix_missing_marker"), patch.object(
            validation_service, "_fix_invalid_scan_link"
        ):

            result = await validation_service.fix_validation_issues(
                tenant_id="tenant-123", issues=issues
            )

            assert result["success"] is True
            assert result["issues_provided"] == 2
            assert result["fixes_attempted"] == 2
            assert result["fixes_succeeded"] == 2
            assert result["fixes_failed"] == 0


@pytest.mark.asyncio
async def test_fix_validation_issues_partial_success(validation_service, mock_session):
    """Test fixing issues with some failures."""
    issues = [
        {"type": "missing_marker", "resource_id": "vm-123", "missing_markers": ["scale_operation_id"]},
        {"type": "unknown_type", "resource_id": "vm-456"},  # Will fail
    ]

    with patch.object(validation_service, "validate_tenant_exists", return_value=True):
        with patch.object(validation_service, "_fix_missing_marker"):

            result = await validation_service.fix_validation_issues(
                tenant_id="tenant-123", issues=issues
            )

            assert result["success"] is False  # Not all succeeded
            assert result["fixes_attempted"] == 2
            assert result["fixes_succeeded"] == 1
            assert result["fixes_failed"] == 1


@pytest.mark.asyncio
async def test_fix_validation_issues_empty_list(validation_service):
    """Test fixing fails with empty issues list."""
    with patch.object(validation_service, "validate_tenant_exists", return_value=True):
        with pytest.raises(ValueError, match="cannot be empty"):
            await validation_service.fix_validation_issues(
                tenant_id="tenant-123", issues=[]
            )


@pytest.mark.asyncio
async def test_fix_validation_issues_with_progress(validation_service):
    """Test fixing issues with progress callback."""
    progress_updates = []

    def progress_callback(message, current, total):
        progress_updates.append({"message": message, "current": current, "total": total})

    issues = [{"type": "missing_marker", "resource_id": "vm-123", "missing_markers": ["scale_operation_id"]}]

    with patch.object(validation_service, "validate_tenant_exists", return_value=True):
        with patch.object(validation_service, "_fix_missing_marker"):

            result = await validation_service.fix_validation_issues(
                tenant_id="tenant-123", issues=issues, progress_callback=progress_callback
            )

            assert result["success"] is True
            assert len(progress_updates) >= 2  # Start and end


# =========================================================================
# Test: Check Methods
# =========================================================================


@pytest.mark.asyncio
async def test_check_original_contamination_found(validation_service, mock_session):
    """Test detecting Original contamination."""
    mock_session.run.return_value = MagicMock(
        __iter__=MagicMock(
            return_value=iter(
                [
                    {
                        "resource_id": "vm-123",
                        "resource_type": "Microsoft.Compute/virtualMachines",
                        "operation_id": "scale-123",
                    }
                ]
            )
        )
    )

    issues = await validation_service._check_original_contamination("tenant-123")

    assert len(issues) == 1
    assert issues[0]["type"] == "original_contamination"
    assert issues[0]["severity"] == "critical"


@pytest.mark.asyncio
async def test_check_original_contamination_clean(validation_service, mock_session):
    """Test Original contamination check when clean."""
    mock_session.run.return_value = MagicMock(__iter__=MagicMock(return_value=iter([])))

    issues = await validation_service._check_original_contamination("tenant-123")

    assert len(issues) == 0


@pytest.mark.asyncio
async def test_check_scan_source_links_found(validation_service, mock_session):
    """Test detecting invalid SCAN_SOURCE_NODE links."""
    mock_session.run.return_value = MagicMock(
        __iter__=MagicMock(
            return_value=iter(
                [
                    {
                        "resource_id": "vm-123",
                        "resource_type": "Microsoft.Compute/virtualMachines",
                        "operation_id": "scale-123",
                        "original_id": "vm-original-123",
                    }
                ]
            )
        )
    )

    issues = await validation_service._check_scan_source_links("tenant-123")

    assert len(issues) == 1
    assert issues[0]["type"] == "invalid_scan_link"
    assert issues[0]["severity"] == "high"


@pytest.mark.asyncio
async def test_check_synthetic_markers_missing(validation_service, mock_session):
    """Test detecting missing synthetic markers."""
    mock_session.run.return_value = MagicMock(
        __iter__=MagicMock(
            return_value=iter(
                [
                    {
                        "resource_id": "vm-123",
                        "resource_type": "Microsoft.Compute/virtualMachines",
                        "missing_op": "missing_operation_id",
                        "missing_strategy": "missing_strategy",
                        "missing_timestamp": None,
                    }
                ]
            )
        )
    )

    issues = await validation_service._check_synthetic_markers("tenant-123")

    assert len(issues) == 1
    assert issues[0]["type"] == "missing_marker"
    assert issues[0]["severity"] == "medium"
    assert "scale_operation_id" in issues[0]["missing_markers"]
    assert "generation_strategy" in issues[0]["missing_markers"]


@pytest.mark.asyncio
async def test_check_graph_structure_orphans(validation_service, mock_session):
    """Test detecting orphaned nodes."""
    mock_session.run.return_value = MagicMock(
        __iter__=MagicMock(
            return_value=iter(
                [
                    {
                        "resource_id": "vm-123",
                        "resource_type": "Microsoft.Compute/virtualMachines",
                        "operation_id": "scale-123",
                    }
                ]
            )
        )
    )

    issues = await validation_service._check_graph_structure("tenant-123")

    assert len(issues) == 1
    assert issues[0]["type"] == "orphaned_node"
    assert issues[0]["severity"] == "low"


# =========================================================================
# Test: Fix Methods
# =========================================================================


@pytest.mark.asyncio
async def test_fix_missing_marker(validation_service, mock_session):
    """Test fixing missing marker."""
    issue = {
        "resource_id": "vm-123",
        "missing_markers": ["scale_operation_id", "generation_strategy"],
    }

    await validation_service._fix_missing_marker(issue)

    # Verify session.run was called
    mock_session.run.assert_called_once()


@pytest.mark.asyncio
async def test_fix_invalid_scan_link(validation_service, mock_session):
    """Test fixing invalid SCAN_SOURCE_NODE link."""
    issue = {"resource_id": "vm-123"}

    await validation_service._fix_invalid_scan_link(issue)

    # Verify session.run was called
    mock_session.run.assert_called_once()


@pytest.mark.asyncio
async def test_fix_original_contamination(validation_service, mock_session):
    """Test fixing Original contamination."""
    issue = {"resource_id": "vm-123"}

    await validation_service._fix_original_contamination(issue)

    # Verify session.run was called
    mock_session.run.assert_called_once()


# =========================================================================
# Test: Error Handling
# =========================================================================


@pytest.mark.asyncio
async def test_validate_graph_handles_exception(validation_service):
    """Test validation handles exceptions gracefully."""
    with patch.object(validation_service, "validate_tenant_exists", return_value=True):
        with patch.object(
            validation_service,
            "_check_original_contamination",
            side_effect=Exception("Database error"),
        ):

            result = await validation_service.validate_graph(
                tenant_id="tenant-123", check_type="all"
            )

            assert result["success"] is False
            assert "error_message" in result
            assert "Database error" in result["error_message"]


@pytest.mark.asyncio
async def test_fix_issues_handles_fix_exception(validation_service):
    """Test fix handles individual fix exceptions."""
    issues = [{"type": "missing_marker", "resource_id": "vm-123", "missing_markers": ["scale_operation_id"]}]

    with patch.object(validation_service, "validate_tenant_exists", return_value=True):
        with patch.object(
            validation_service,
            "_fix_missing_marker",
            side_effect=Exception("Fix failed"),
        ):

            result = await validation_service.fix_validation_issues(
                tenant_id="tenant-123", issues=issues
            )

            assert result["success"] is False
            assert result["fixes_failed"] == 1
            assert "Fix failed" in result["fix_details"][0]["message"]
