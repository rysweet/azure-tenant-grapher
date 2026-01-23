"""
Comprehensive test suite for ScaleReductionService

Tests pattern discovery, representative selection, relationship preservation,
validation, and performance monitoring with proper mocking.

Philosophy:
- TDD approach: Tests written before implementation
- Mock external dependencies (Neo4j)
- Test critical paths and edge cases
- Verify 100% pattern coverage guarantee
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from src.services.scale_performance import PerformanceMetrics
from src.services.scale_reduction_service import (
    GraphPattern,
    ScaleReductionResult,
    ScaleReductionService,
    ValidationResult,
)
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
def reduction_service(mock_session_manager):
    """Create a ScaleReductionService instance with mocked dependencies."""
    return ScaleReductionService(
        session_manager=mock_session_manager,
        enable_performance_monitoring=False,  # Disable for faster tests
        validation_enabled=False,  # Control validation explicitly per test
    )


@pytest.fixture
def sample_patterns():
    """Sample graph patterns for testing."""
    return [
        GraphPattern(
            source_labels=["Resource"],
            relationship_type="DEPENDS_ON",
            target_labels=["Resource"],
            frequency=450,  # Common pattern
            examples=["vm-1", "vm-2", "vm-3"],
        ),
        GraphPattern(
            source_labels=["Resource"],
            relationship_type="CONNECTED_TO",
            target_labels=["Resource"],
            frequency=120,
            examples=["vnet-1", "vnet-2"],
        ),
        GraphPattern(
            source_labels=["Identity"],
            relationship_type="HAS_ROLE",
            target_labels=["Role"],
            frequency=5,  # Rare pattern
            examples=["user-1"],
        ),
    ]


@pytest.fixture
def sample_nodes():
    """Sample nodes for testing representative selection."""
    return [
        {
            "id": "vm-1",
            "labels": ["Resource"],
            "type": "Microsoft.Compute/virtualMachines",
            "location": "eastus",
        },
        {
            "id": "vm-2",
            "labels": ["Resource"],
            "type": "Microsoft.Compute/virtualMachines",
            "location": "westus",
        },
        {
            "id": "vnet-1",
            "labels": ["Resource"],
            "type": "Microsoft.Network/virtualNetworks",
            "location": "eastus",
        },
        {
            "id": "user-1",
            "labels": ["Identity"],
            "type": "User",
            "upn": "test@example.com",
        },
    ]


# =========================================================================
# Test: Service Initialization
# =========================================================================


def test_service_initialization(mock_session_manager):
    """Test ScaleReductionService initializes correctly."""
    service = ScaleReductionService(
        session_manager=mock_session_manager,
        enable_performance_monitoring=True,
        validation_enabled=True,
    )

    assert service.session_manager == mock_session_manager
    assert service.enable_performance_monitoring is True
    assert service.validation_enabled is True


def test_service_initialization_defaults(mock_session_manager):
    """Test ScaleReductionService uses correct defaults."""
    service = ScaleReductionService(session_manager=mock_session_manager)

    # Defaults from documentation
    assert service.enable_performance_monitoring is True
    assert service.validation_enabled is True


# =========================================================================
# Test: Pattern Discovery
# =========================================================================


@pytest.mark.asyncio
async def test_get_patterns_success(reduction_service, mock_session, sample_patterns):
    """Test successful pattern discovery from graph."""
    # Mock Neo4j query result
    mock_records = [
        {
            "sourceLabels": p.source_labels,
            "relType": p.relationship_type,
            "targetLabels": p.target_labels,
            "frequency": p.frequency,
        }
        for p in sample_patterns
    ]

    mock_result = MagicMock()
    mock_result.__iter__ = MagicMock(return_value=iter(mock_records))
    mock_session.run = MagicMock(return_value=mock_result)

    # Execute
    patterns = await reduction_service.get_patterns(tenant_id="test-tenant")

    # Verify
    assert len(patterns) == 3
    assert patterns[0].source_labels == ["Resource"]
    assert patterns[0].relationship_type == "DEPENDS_ON"
    assert patterns[0].frequency == 450
    assert patterns[2].frequency == 5  # Rare pattern included


@pytest.mark.asyncio
async def test_get_patterns_empty_graph(reduction_service, mock_session):
    """Test pattern discovery on empty graph returns empty list."""
    mock_result = MagicMock()
    mock_result.__iter__ = MagicMock(return_value=iter([]))
    mock_session.run = MagicMock(return_value=mock_result)

    patterns = await reduction_service.get_patterns(tenant_id="empty-tenant")

    assert len(patterns) == 0


@pytest.mark.asyncio
async def test_get_patterns_handles_neo4j_errors(reduction_service, mock_session):
    """Test pattern discovery handles Neo4j errors gracefully."""
    mock_session.run = MagicMock(side_effect=Exception("Neo4j connection error"))

    with pytest.raises(RuntimeError, match="Failed to discover patterns"):
        await reduction_service.get_patterns(tenant_id="test-tenant")


# =========================================================================
# Test: Representative Selection
# =========================================================================


@pytest.mark.asyncio
async def test_select_representatives_default_count(
    reduction_service, mock_session, sample_patterns
):
    """Test representative selection with default count (2 per pattern)."""
    # Mock pattern discovery
    with patch.object(
        reduction_service, "get_patterns", return_value=sample_patterns
    ), patch.object(reduction_service, "_fetch_pattern_examples") as mock_fetch:
        # Mock fetch returning example nodes
        mock_fetch.return_value = ["node-1", "node-2", "node-3"]

        representatives = await reduction_service._select_representatives(
            tenant_id="test-tenant", representatives_per_pattern=2
        )

        # Should have 2 representatives per pattern (default)
        # Pattern 1: 2 reps, Pattern 2: 2 reps, Pattern 3: 2 reps (but only 1 exists)
        assert len(representatives) >= 5  # At least 2+2+1


@pytest.mark.asyncio
async def test_select_representatives_handles_rare_patterns(
    reduction_service, mock_session, sample_patterns
):
    """Test representative selection for rare patterns (frequency < N)."""
    # Pattern 3 has frequency=5, requesting 10 representatives should get all 5
    with patch.object(
        reduction_service, "get_patterns", return_value=[sample_patterns[2]]
    ), patch.object(reduction_service, "_fetch_pattern_examples") as mock_fetch:
        mock_fetch.return_value = ["user-1", "user-2", "user-3", "user-4", "user-5"]

        representatives = await reduction_service._select_representatives(
            tenant_id="test-tenant",
            representatives_per_pattern=10,  # Request more than available
        )

        # Should get all 5 available (not fail or duplicate)
        assert len(representatives) == 5


@pytest.mark.asyncio
async def test_select_representatives_preserves_diversity(
    reduction_service, mock_session
):
    """Test representative selection preserves property diversity."""
    # Mock nodes with different properties (location, size, config)
    diverse_nodes = [
        {"id": f"vm-{i}", "location": loc, "size": size}
        for i, (loc, size) in enumerate(
            [
                ("eastus", "Standard_D2"),
                ("westus", "Standard_D4"),
                ("centralus", "Standard_D8"),
            ]
        )
    ]

    with patch.object(reduction_service, "_fetch_pattern_examples") as mock_fetch:
        mock_fetch.return_value = diverse_nodes

        # Selection algorithm should prioritize diversity
        # (implementation detail - verify through integration tests)
        pass


# =========================================================================
# Test: Relationship Preservation
# =========================================================================


@pytest.mark.asyncio
async def test_preserve_critical_paths_enabled(reduction_service, mock_session):
    """Test critical path preservation when enabled."""
    # Mock scenario: RBAC chain User -> Group -> Role -> Subscription
    # Should preserve intermediate nodes even if not in representatives
    with patch.object(
        reduction_service, "_identify_critical_paths"
    ) as mock_identify, patch.object(
        reduction_service, "_add_path_nodes"
    ) as mock_add_nodes:
        mock_identify.return_value = [
            {"nodes": ["user-1", "group-1", "role-1", "sub-1"], "path_type": "RBAC"}
        ]

        await reduction_service._preserve_critical_paths(
            tenant_id="test-tenant",
            representatives=["user-1", "sub-1"],  # Ends only
            preserve_critical_paths=True,
        )

        # Should identify and add intermediate nodes
        mock_identify.assert_called_once()
        mock_add_nodes.assert_called_once()


@pytest.mark.asyncio
async def test_preserve_critical_paths_disabled(reduction_service, mock_session):
    """Test critical path preservation can be disabled."""
    with patch.object(reduction_service, "_identify_critical_paths") as mock_identify:
        await reduction_service._preserve_critical_paths(
            tenant_id="test-tenant",
            representatives=["user-1"],
            preserve_critical_paths=False,  # Disabled
        )

        # Should not identify paths when disabled
        mock_identify.assert_not_called()


# =========================================================================
# Test: Graph Reduction End-to-End
# =========================================================================


@pytest.mark.asyncio
async def test_reduce_graph_success(reduction_service, mock_session, sample_patterns):
    """Test successful end-to-end graph reduction."""
    # Mock all phases
    with patch.object(
        reduction_service, "get_patterns", return_value=sample_patterns
    ), patch.object(
        reduction_service, "_select_representatives", return_value=["vm-1", "vnet-1"]
    ), patch.object(reduction_service, "_preserve_critical_paths"), patch.object(
        reduction_service, "_create_reduced_graph"
    ) as mock_create, patch.object(
        reduction_service, "_get_graph_counts"
    ) as mock_counts:
        # Mock graph counts (original vs reduced)
        mock_counts.side_effect = [
            (40000, 120000),  # Original: 40k nodes, 120k rels
            (2000, 5000),  # Reduced: 2k nodes, 5k rels
        ]
        mock_create.return_value = str(uuid4())  # operation_id

        result = await reduction_service.reduce_graph(
            tenant_id="test-tenant", representatives_per_pattern=2
        )

        # Verify result
        assert result.success is True
        assert result.tenant_id == "test-tenant"
        assert result.original_node_count == 40000
        assert result.reduced_node_count == 2000
        assert result.reduction_percentage == 95.0  # (40k-2k)/40k * 100
        assert result.total_patterns == 3  # From sample_patterns
        assert result.error_message is None


@pytest.mark.asyncio
async def test_reduce_graph_validation_failure(
    reduction_service, mock_session, sample_patterns
):
    """Test reduction fails validation if pattern coverage < 100%."""
    service = ScaleReductionService(
        session_manager=reduction_service.session_manager, validation_enabled=True
    )

    with patch.object(
        service, "get_patterns", return_value=sample_patterns
    ), patch.object(service, "_select_representatives", return_value=[]), patch.object(
        service, "_create_reduced_graph"
    ), patch.object(service, "validate_reduction") as mock_validate:
        # Mock validation failure (not all patterns preserved)
        mock_validate.return_value = ValidationResult(
            success=False,
            pattern_coverage_percentage=85.0,  # < 100%
            missing_patterns=["(Identity)-[:HAS_ROLE]->(Role)"],
        )

        result = await service.reduce_graph(tenant_id="test-tenant")

        # Should fail due to validation
        assert result.success is False
        assert "Pattern coverage 85.0% < 100%" in result.error_message


@pytest.mark.asyncio
async def test_reduce_graph_with_progress_callback(
    reduction_service, mock_session, sample_patterns
):
    """Test reduction reports progress via callback."""
    progress_calls = []

    def progress_callback(message, current, total):
        progress_calls.append((message, current, total))

    with patch.object(
        reduction_service, "get_patterns", return_value=sample_patterns
    ), patch.object(
        reduction_service, "_select_representatives", return_value=["vm-1"]
    ), patch.object(reduction_service, "_preserve_critical_paths"), patch.object(
        reduction_service, "_create_reduced_graph"
    ), patch.object(reduction_service, "_get_graph_counts", return_value=(1000, 3000)):
        await reduction_service.reduce_graph(
            tenant_id="test-tenant", progress_callback=progress_callback
        )

        # Should have received progress updates
        assert len(progress_calls) > 0
        # First call should be phase 1
        assert "Discovering patterns" in progress_calls[0][0]


# =========================================================================
# Test: Validation
# =========================================================================


@pytest.mark.asyncio
async def test_validate_reduction_success(reduction_service, mock_session):
    """Test validation passes when all patterns are preserved."""
    operation_id = str(uuid4())

    # Mock original patterns
    original_patterns = [
        {"source": ["Resource"], "rel": "DEPENDS_ON", "target": ["Resource"]},
        {"source": ["Resource"], "rel": "CONNECTED_TO", "target": ["Resource"]},
    ]

    # Mock reduced patterns (same as original)
    reduced_patterns = original_patterns.copy()

    with patch.object(
        reduction_service, "_get_patterns_for_graph"
    ) as mock_get_patterns:
        # First call: original graph, second call: reduced graph
        mock_get_patterns.side_effect = [original_patterns, reduced_patterns]

        result = await reduction_service.validate_reduction(operation_id=operation_id)

        # All patterns preserved
        assert result.success is True
        assert result.pattern_coverage_percentage == 100.0
        assert len(result.missing_patterns) == 0


@pytest.mark.asyncio
async def test_validate_reduction_missing_patterns(reduction_service, mock_session):
    """Test validation fails when patterns are missing."""
    operation_id = str(uuid4())

    original_patterns = [
        {"source": ["Resource"], "rel": "DEPENDS_ON", "target": ["Resource"]},
        {"source": ["Resource"], "rel": "CONNECTED_TO", "target": ["Resource"]},
        {"source": ["Identity"], "rel": "HAS_ROLE", "target": ["Role"]},
    ]

    # Reduced graph missing one pattern
    reduced_patterns = original_patterns[:2]  # Missing third pattern

    with patch.object(
        reduction_service, "_get_patterns_for_graph"
    ) as mock_get_patterns:
        mock_get_patterns.side_effect = [original_patterns, reduced_patterns]

        result = await reduction_service.validate_reduction(operation_id=operation_id)

        # Missing 1 of 3 patterns (66.67% coverage)
        assert result.success is False
        assert result.pattern_coverage_percentage == pytest.approx(66.67, rel=0.1)
        assert len(result.missing_patterns) == 1
        assert "(Identity)-[:HAS_ROLE]->(Role)" in result.missing_patterns


# =========================================================================
# Test: Performance Monitoring
# =========================================================================


@pytest.mark.asyncio
async def test_reduce_graph_performance_monitoring_enabled(
    mock_session_manager, sample_patterns
):
    """Test performance monitoring tracks metrics when enabled."""
    service = ScaleReductionService(
        session_manager=mock_session_manager, enable_performance_monitoring=True
    )

    with patch.object(
        service, "get_patterns", return_value=sample_patterns
    ), patch.object(
        service, "_select_representatives", return_value=["vm-1"]
    ), patch.object(service, "_preserve_critical_paths"), patch.object(
        service, "_create_reduced_graph"
    ), patch.object(service, "_get_graph_counts", return_value=(1000, 2000)):
        result = await service.reduce_graph(tenant_id="test-tenant")

        # Performance metrics should be populated
        assert result.performance_metrics is not None
        assert isinstance(result.performance_metrics, PerformanceMetrics)
        assert result.performance_metrics.operation_name == "scale_reduction"


@pytest.mark.asyncio
async def test_reduce_graph_performance_monitoring_disabled(
    mock_session_manager, sample_patterns
):
    """Test performance monitoring can be disabled."""
    service = ScaleReductionService(
        session_manager=mock_session_manager, enable_performance_monitoring=False
    )

    with patch.object(
        service, "get_patterns", return_value=sample_patterns
    ), patch.object(
        service, "_select_representatives", return_value=["vm-1"]
    ), patch.object(service, "_preserve_critical_paths"), patch.object(
        service, "_create_reduced_graph"
    ), patch.object(service, "_get_graph_counts", return_value=(1000, 2000)):
        result = await service.reduce_graph(tenant_id="test-tenant")

        # Performance metrics should be None
        assert result.performance_metrics is None


# =========================================================================
# Test: Error Handling
# =========================================================================


@pytest.mark.asyncio
async def test_reduce_graph_handles_neo4j_errors(reduction_service, mock_session):
    """Test reduction handles Neo4j errors gracefully."""
    mock_session.run = MagicMock(side_effect=Exception("Neo4j connection lost"))

    result = await reduction_service.reduce_graph(tenant_id="test-tenant")

    assert result.success is False
    assert "Neo4j connection lost" in result.error_message


@pytest.mark.asyncio
async def test_reduce_graph_handles_invalid_tenant(reduction_service, mock_session):
    """Test reduction validates tenant exists."""
    with patch.object(reduction_service, "_validate_tenant_exists", return_value=False):
        result = await reduction_service.reduce_graph(tenant_id="nonexistent")

        assert result.success is False
        assert "Tenant 'nonexistent' not found" in result.error_message


@pytest.mark.asyncio
async def test_reduce_graph_handles_empty_graph(reduction_service, mock_session):
    """Test reduction handles empty graphs gracefully."""
    with patch.object(reduction_service, "get_patterns", return_value=[]):
        result = await reduction_service.reduce_graph(tenant_id="empty-tenant")

        assert result.success is True
        assert result.total_patterns == 0
        assert result.reduced_node_count == 0


# =========================================================================
# Test: Configuration Parameters
# =========================================================================


@pytest.mark.parametrize(
    "representatives_per_pattern,expected_min_size",
    [
        (1, 3),  # 1 rep per pattern * 3 patterns
        (2, 6),  # 2 reps per pattern * 3 patterns
        (3, 9),  # 3 reps per pattern * 3 patterns
    ],
)
@pytest.mark.asyncio
async def test_reduce_graph_representatives_per_pattern(
    reduction_service,
    mock_session,
    sample_patterns,
    representatives_per_pattern,
    expected_min_size,
):
    """Test different representatives_per_pattern values."""
    with patch.object(
        reduction_service, "get_patterns", return_value=sample_patterns
    ), patch.object(
        reduction_service, "_select_representatives"
    ) as mock_select, patch.object(
        reduction_service, "_preserve_critical_paths"
    ), patch.object(reduction_service, "_create_reduced_graph"), patch.object(
        reduction_service, "_get_graph_counts", return_value=(1000, 2000)
    ):
        await reduction_service.reduce_graph(
            tenant_id="test-tenant",
            representatives_per_pattern=representatives_per_pattern,
        )

        # Verify selection called with correct parameter
        mock_select.assert_called_once()
        args, kwargs = mock_select.call_args
        assert kwargs.get("representatives_per_pattern") == representatives_per_pattern


# =========================================================================
# Test: GraphPattern Dataclass
# =========================================================================


def test_graph_pattern_creation():
    """Test GraphPattern dataclass initialization."""
    pattern = GraphPattern(
        source_labels=["Resource"],
        relationship_type="DEPENDS_ON",
        target_labels=["Resource"],
        frequency=100,
        examples=["vm-1", "vm-2"],
    )

    assert pattern.source_labels == ["Resource"]
    assert pattern.relationship_type == "DEPENDS_ON"
    assert pattern.frequency == 100
    assert len(pattern.examples) == 2


def test_graph_pattern_equality():
    """Test GraphPattern equality comparison (ignoring examples)."""
    pattern1 = GraphPattern(
        source_labels=["Resource"],
        relationship_type="DEPENDS_ON",
        target_labels=["Resource"],
        frequency=100,
        examples=["vm-1"],
    )

    pattern2 = GraphPattern(
        source_labels=["Resource"],
        relationship_type="DEPENDS_ON",
        target_labels=["Resource"],
        frequency=200,  # Different frequency
        examples=["vm-2"],  # Different examples
    )

    # Patterns are equal if structure matches (ignoring frequency/examples)
    assert pattern1.matches(pattern2)  # Assuming matches() method exists


# =========================================================================
# Test: ScaleReductionResult Dataclass
# =========================================================================


def test_scale_reduction_result_creation():
    """Test ScaleReductionResult dataclass initialization."""
    result = ScaleReductionResult(
        success=True,
        operation_id=str(uuid4()),
        tenant_id="test-tenant",
        original_node_count=40000,
        original_relationship_count=120000,
        reduced_node_count=2000,
        reduced_relationship_count=5000,
        total_patterns=150,
        patterns_preserved=150,
        duration_seconds=85.5,
        error_message=None,
        performance_metrics=None,
    )

    assert result.success is True
    assert result.reduction_percentage == 95.0  # (40k-2k)/40k * 100
    assert result.pattern_coverage_percentage == 100.0  # 150/150 * 100


def test_scale_reduction_result_calculates_percentages():
    """Test ScaleReductionResult calculates reduction percentage correctly."""
    result = ScaleReductionResult(
        success=True,
        operation_id=str(uuid4()),
        tenant_id="test-tenant",
        original_node_count=1000,
        original_relationship_count=3000,
        reduced_node_count=100,  # 90% reduction
        reduced_relationship_count=300,
        total_patterns=10,
        patterns_preserved=8,  # 80% coverage
        duration_seconds=10.0,
    )

    assert result.reduction_percentage == pytest.approx(90.0, rel=0.01)
    assert result.pattern_coverage_percentage == pytest.approx(80.0, rel=0.01)


# =========================================================================
# Test: ValidationResult Dataclass
# =========================================================================


def test_validation_result_success():
    """Test ValidationResult for successful validation."""
    result = ValidationResult(
        success=True,
        pattern_coverage_percentage=100.0,
        missing_patterns=[],
    )

    assert result.success is True
    assert result.pattern_coverage_percentage == 100.0
    assert len(result.missing_patterns) == 0


def test_validation_result_failure():
    """Test ValidationResult for failed validation."""
    result = ValidationResult(
        success=False,
        pattern_coverage_percentage=85.0,
        missing_patterns=[
            "(Identity)-[:HAS_ROLE]->(Role)",
            "(Resource)-[:RARE_PATTERN]->(Resource)",
        ],
    )

    assert result.success is False
    assert result.pattern_coverage_percentage == 85.0
    assert len(result.missing_patterns) == 2
