"""
Comprehensive test suite for ScaleUpService

Tests all scale-up strategies, relationship duplication, validation,
and rollback functionality with proper mocking.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.services.scale_up_service import ScaleUpResult, ScaleUpService
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
def scale_up_service(mock_session_manager):
    """Create a ScaleUpService instance with mocked dependencies."""
    return ScaleUpService(
        session_manager=mock_session_manager, batch_size=10, validation_enabled=False
    )


@pytest.fixture
def mock_base_resources():
    """Sample base resources for testing."""
    return [
        {
            "id": "vm-abc123",
            "type": "Microsoft.Compute/virtualMachines",
            "props": {
                "id": "vm-abc123",
                "name": "test-vm-1",
                "type": "Microsoft.Compute/virtualMachines",
                "tenant_id": "tenant-123",
                "location": "eastus",
            },
        },
        {
            "id": "vnet-def456",
            "type": "Microsoft.Network/virtualNetworks",
            "props": {
                "id": "vnet-def456",
                "name": "test-vnet-1",
                "type": "Microsoft.Network/virtualNetworks",
                "tenant_id": "tenant-123",
                "location": "eastus",
            },
        },
    ]


@pytest.fixture
def mock_relationship_patterns():
    """Sample relationship patterns for testing."""
    return [
        {
            "source_id": "vm-abc123",
            "target_id": "vnet-def456",
            "rel_type": "CONNECTED_TO",
            "rel_props": {"connection_type": "network"},
        }
    ]


# =========================================================================
# Test: Service Initialization
# =========================================================================


def test_service_initialization(mock_session_manager):
    """Test ScaleUpService initializes correctly."""
    service = ScaleUpService(
        session_manager=mock_session_manager, batch_size=500, validation_enabled=True
    )

    assert service.session_manager == mock_session_manager
    assert service.batch_size == 500
    assert service.validation_enabled is True


def test_service_initialization_defaults(mock_session_manager):
    """Test ScaleUpService uses correct defaults."""
    service = ScaleUpService(session_manager=mock_session_manager)

    assert service.batch_size == 500
    assert service.validation_enabled is True


# =========================================================================
# Test: Template-Based Scale-Up
# =========================================================================


@pytest.mark.asyncio
async def test_scale_up_template_success(
    scale_up_service, mock_session, mock_base_resources
):
    """Test successful template-based scale-up."""
    # Mock tenant validation and component methods
    with patch.object(
        scale_up_service.setup, "validate_tenant_exists", return_value=True
    ), patch.object(
        scale_up_service.setup, "get_base_resources", return_value=mock_base_resources
    ), patch.object(
        scale_up_service.projection, "replicate_resources", return_value=10
    ), patch.object(
        scale_up_service.projection, "clone_relationships", return_value=5
    ):

        result = await scale_up_service.scale_up_template(
            tenant_id="tenant-123", scale_factor=2.0
        )

        assert result.success is True
        assert result.tenant_id == "tenant-123"
        assert result.strategy == "template"
        assert result.resources_created == 10
        assert result.relationships_created == 5
        assert result.error_message is None


@pytest.mark.asyncio
async def test_scale_up_template_tenant_not_found(scale_up_service):
    """Test template scale-up fails when tenant doesn't exist."""
    with patch.object(scale_up_service.setup, "validate_tenant_exists", return_value=False):

        result = await scale_up_service.scale_up_template(
            tenant_id="nonexistent", scale_factor=2.0
        )

        assert result.success is False
        assert "not found" in result.error_message.lower()


@pytest.mark.asyncio
async def test_scale_up_template_invalid_scale_factor(scale_up_service):
    """Test template scale-up fails with invalid scale factor."""
    with patch.object(scale_up_service.setup, "validate_tenant_exists", return_value=True):

        # Test zero scale factor
        result = await scale_up_service.scale_up_template(
            tenant_id="tenant-123", scale_factor=0.0
        )
        assert result.success is False
        assert "positive" in result.error_message.lower()

        # Test negative scale factor
        result = await scale_up_service.scale_up_template(
            tenant_id="tenant-123", scale_factor=-1.0
        )
        assert result.success is False
        assert "positive" in result.error_message.lower()


@pytest.mark.asyncio
async def test_scale_up_template_no_base_resources(scale_up_service):
    """Test template scale-up fails when no base resources exist."""
    with patch.object(
        scale_up_service.setup, "validate_tenant_exists", return_value=True
    ), patch.object(scale_up_service.setup, "get_base_resources", return_value=[]):

        result = await scale_up_service.scale_up_template(
            tenant_id="tenant-123", scale_factor=2.0
        )

        assert result.success is False
        assert "no base resources" in result.error_message.lower()


@pytest.mark.asyncio
async def test_scale_up_template_with_resource_types(
    scale_up_service, mock_session, mock_base_resources
):
    """Test template scale-up with specific resource types."""
    with patch.object(
        scale_up_service.setup, "validate_tenant_exists", return_value=True
    ), patch.object(
        scale_up_service.setup, "get_base_resources", return_value=mock_base_resources
    ), patch.object(
        scale_up_service.projection, "replicate_resources", return_value=5
    ), patch.object(
        scale_up_service.projection, "clone_relationships", return_value=2
    ):

        result = await scale_up_service.scale_up_template(
            tenant_id="tenant-123",
            scale_factor=2.0,
            resource_types=["Microsoft.Compute/virtualMachines"],
        )

        assert result.success is True
        assert result.metadata["resource_types"] == [
            "Microsoft.Compute/virtualMachines"
        ]


@pytest.mark.asyncio
async def test_scale_up_template_with_progress_callback(
    scale_up_service, mock_session, mock_base_resources
):
    """Test template scale-up calls progress callback."""
    progress_calls = []

    def progress_callback(message, current, total):
        progress_calls.append((message, current, total))

    with patch.object(
        scale_up_service.setup, "validate_tenant_exists", return_value=True
    ), patch.object(
        scale_up_service.setup, "get_base_resources", return_value=mock_base_resources
    ), patch.object(
        scale_up_service.projection, "replicate_resources", return_value=10
    ), patch.object(
        scale_up_service.projection, "clone_relationships", return_value=5
    ):

        result = await scale_up_service.scale_up_template(
            tenant_id="tenant-123",
            scale_factor=2.0,
            progress_callback=progress_callback,
        )

        assert result.success is True
        assert len(progress_calls) > 0
        assert any("complete" in msg.lower() for msg, _, _ in progress_calls)


@pytest.mark.asyncio
async def test_scale_up_template_scale_factor_too_small(
    scale_up_service, mock_base_resources
):
    """Test template scale-up fails when scale factor is too small."""
    with patch.object(
        scale_up_service, "validate_tenant_exists", return_value=True
    ), patch.object(
        scale_up_service, "_get_base_resources", return_value=mock_base_resources
    ):

        # Scale factor < 1.0 means we'd create negative resources
        result = await scale_up_service.scale_up_template(
            tenant_id="tenant-123", scale_factor=0.5
        )

        assert result.success is False
        assert "must be > 1.0" in result.error_message.lower()


# =========================================================================
# Test: Scenario-Based Scale-Up
# =========================================================================


@pytest.mark.asyncio
async def test_scale_up_scenario_hub_spoke(scale_up_service):
    """Test scenario-based scale-up with hub-spoke topology."""
    with patch.object(
        scale_up_service, "validate_tenant_exists", return_value=True
    ), patch.object(
        scale_up_service, "_generate_hub_spoke", return_value=(50, 25)
    ):

        result = await scale_up_service.scale_up_scenario(
            tenant_id="tenant-123",
            scenario="hub-spoke",
            params={"spoke_count": 5, "resources_per_spoke": 10},
        )

        assert result.success is True
        assert result.strategy == "scenario"
        assert result.resources_created == 50
        assert result.relationships_created == 25
        assert result.metadata["scenario"] == "hub-spoke"


@pytest.mark.asyncio
async def test_scale_up_scenario_multi_region(scale_up_service):
    """Test scenario-based scale-up with multi-region topology."""
    with patch.object(
        scale_up_service, "validate_tenant_exists", return_value=True
    ), patch.object(
        scale_up_service, "_generate_multi_region", return_value=(60, 0)
    ):

        result = await scale_up_service.scale_up_scenario(
            tenant_id="tenant-123",
            scenario="multi-region",
            params={"region_count": 3, "resources_per_region": 20},
        )

        assert result.success is True
        assert result.resources_created == 60
        assert result.metadata["scenario"] == "multi-region"


@pytest.mark.asyncio
async def test_scale_up_scenario_dev_test_prod(scale_up_service):
    """Test scenario-based scale-up with dev/test/prod topology."""
    with patch.object(
        scale_up_service, "validate_tenant_exists", return_value=True
    ), patch.object(
        scale_up_service, "_generate_dev_test_prod", return_value=(45, 0)
    ):

        result = await scale_up_service.scale_up_scenario(
            tenant_id="tenant-123",
            scenario="dev-test-prod",
            params={"resources_per_env": 15},
        )

        assert result.success is True
        assert result.resources_created == 45
        assert result.metadata["scenario"] == "dev-test-prod"


@pytest.mark.asyncio
async def test_scale_up_scenario_unknown_scenario(scale_up_service):
    """Test scenario scale-up fails with unknown scenario."""
    with patch.object(scale_up_service.setup, "validate_tenant_exists", return_value=True):

        result = await scale_up_service.scale_up_scenario(
            tenant_id="tenant-123", scenario="unknown-scenario", params={}
        )

        assert result.success is False
        assert "unknown scenario" in result.error_message.lower()


@pytest.mark.asyncio
async def test_scale_up_scenario_tenant_not_found(scale_up_service):
    """Test scenario scale-up fails when tenant doesn't exist."""
    with patch.object(scale_up_service.setup, "validate_tenant_exists", return_value=False):

        result = await scale_up_service.scale_up_scenario(
            tenant_id="nonexistent", scenario="hub-spoke", params={}
        )

        assert result.success is False
        assert "not found" in result.error_message.lower()


# =========================================================================
# Test: Random Scale-Up
# =========================================================================


@pytest.mark.asyncio
async def test_scale_up_random_success(scale_up_service):
    """Test successful random scale-up."""
    config = {
        "resource_type_distribution": {
            "Microsoft.Compute/virtualMachines": 0.5,
            "Microsoft.Network/virtualNetworks": 0.5,
        },
        "relationship_density": 0.3,
        "seed": 42,
    }

    with patch.object(
        scale_up_service, "validate_tenant_exists", return_value=True
    ), patch.object(
        scale_up_service, "_generate_random_resources", return_value=100
    ), patch.object(
        scale_up_service, "_generate_random_relationships", return_value=30
    ):

        result = await scale_up_service.scale_up_random(
            tenant_id="tenant-123", target_count=100, config=config
        )

        assert result.success is True
        assert result.strategy == "random"
        assert result.resources_created == 100
        assert result.relationships_created == 30


@pytest.mark.asyncio
async def test_scale_up_random_invalid_target_count(scale_up_service):
    """Test random scale-up fails with invalid target count."""
    config = {"resource_type_distribution": {"Microsoft.Compute/virtualMachines": 1.0}}

    with patch.object(scale_up_service.setup, "validate_tenant_exists", return_value=True):

        result = await scale_up_service.scale_up_random(
            tenant_id="tenant-123", target_count=0, config=config
        )

        assert result.success is False
        assert "positive" in result.error_message.lower()


@pytest.mark.asyncio
async def test_scale_up_random_missing_distribution(scale_up_service):
    """Test random scale-up fails without resource type distribution."""
    with patch.object(scale_up_service.setup, "validate_tenant_exists", return_value=True):

        result = await scale_up_service.scale_up_random(
            tenant_id="tenant-123", target_count=100, config={}
        )

        assert result.success is False
        assert "resource_type_distribution" in result.error_message.lower()


@pytest.mark.asyncio
async def test_scale_up_random_tenant_not_found(scale_up_service):
    """Test random scale-up fails when tenant doesn't exist."""
    config = {"resource_type_distribution": {"Microsoft.Compute/virtualMachines": 1.0}}

    with patch.object(scale_up_service.setup, "validate_tenant_exists", return_value=False):

        result = await scale_up_service.scale_up_random(
            tenant_id="nonexistent", target_count=100, config=config
        )

        assert result.success is False
        assert "not found" in result.error_message.lower()


# =========================================================================
# Test: Rollback Operation
# =========================================================================


@pytest.mark.asyncio
async def test_rollback_operation_success(scale_up_service, mock_session):
    """Test successful rollback of scale operation."""
    # Mock the query result
    mock_result = MagicMock()
    mock_record = MagicMock()
    mock_record.__getitem__ = MagicMock(return_value=50)
    mock_result.single = MagicMock(return_value=mock_record)
    mock_session.run = MagicMock(return_value=mock_result)

    deleted_count = await scale_up_service.rollback_operation(
        "scale-20250110T123045-a1b2c3d4"
    )

    assert deleted_count == 50
    assert mock_session.run.called


@pytest.mark.asyncio
async def test_rollback_operation_no_resources(scale_up_service, mock_session):
    """Test rollback when no resources exist for operation."""
    mock_result = MagicMock()
    mock_record = MagicMock()
    mock_record.__getitem__ = MagicMock(return_value=0)
    mock_result.single = MagicMock(return_value=mock_record)
    mock_session.run = MagicMock(return_value=mock_result)

    deleted_count = await scale_up_service.rollback_operation(
        "nonexistent-operation"
    )

    assert deleted_count == 0


# =========================================================================
# Test: Private Helper Methods
# =========================================================================


@pytest.mark.asyncio
async def test_get_base_resources(scale_up_service, mock_session, mock_base_resources):
    """Test retrieval of base resources."""
    mock_result = MagicMock()
    mock_result.__iter__ = MagicMock(
        return_value=iter(
            [
                {
                    "id": r["id"],
                    "type": r["type"],
                    "props": r["props"],
                }
                for r in mock_base_resources
            ]
        )
    )
    mock_session.run = MagicMock(return_value=mock_result)

    resources = await scale_up_service._get_base_resources("tenant-123")

    assert len(resources) == 2
    assert resources[0]["id"] == "vm-abc123"
    assert resources[1]["id"] == "vnet-def456"


@pytest.mark.asyncio
async def test_get_base_resources_with_filter(scale_up_service, mock_session):
    """Test retrieval of base resources with type filter."""
    mock_result = MagicMock()
    mock_result.__iter__ = MagicMock(return_value=iter([]))
    mock_session.run = MagicMock(return_value=mock_result)

    await scale_up_service._get_base_resources(
        "tenant-123", resource_types=["Microsoft.Compute/virtualMachines"]
    )

    # Verify the query included the type filter
    call_args = mock_session.run.call_args
    assert "IN" in call_args[0][0]


@pytest.mark.asyncio
async def test_replicate_resources(
    scale_up_service, mock_session, mock_base_resources
):
    """Test resource replication."""
    with patch.object(scale_up_service.projection, "_insert_resource_batch", return_value=None):
        created_count = await scale_up_service._replicate_resources(
            tenant_id="tenant-123",
            operation_id="scale-123",
            base_resources=mock_base_resources,
            target_count=5,
        )

        assert created_count == 5


@pytest.mark.asyncio
async def test_insert_resource_batch(scale_up_service, mock_session):
    """Test batch insertion of resources."""
    resources = [
        {
            "id": "synthetic-vm-abc123",
            "type": "Microsoft.Compute/virtualMachines",
            "props": {"id": "synthetic-vm-abc123", "synthetic": True},
        }
    ]

    mock_session.run = MagicMock()

    await scale_up_service._insert_resource_batch(resources)

    assert mock_session.run.called


@pytest.mark.asyncio
async def test_build_resource_mapping(scale_up_service, mock_session):
    """Test building resource ID mapping."""
    mock_result = MagicMock()
    mock_result.__iter__ = MagicMock(
        return_value=iter(
            [
                {"id": "synthetic-vm-1", "source_id": "vm-abc123"},
                {"id": "synthetic-vm-2", "source_id": "vm-abc123"},
                {"id": "synthetic-vnet-1", "source_id": "vnet-def456"},
            ]
        )
    )
    mock_session.run = MagicMock(return_value=mock_result)

    mapping = await scale_up_service._build_resource_mapping(
        "scale-123", [{"id": "vm-abc123"}, {"id": "vnet-def456"}]
    )

    assert "vm-abc123" in mapping
    assert len(mapping["vm-abc123"]) == 2
    assert "vnet-def456" in mapping
    assert len(mapping["vnet-def456"]) == 1


@pytest.mark.asyncio
async def test_get_relationship_patterns(
    scale_up_service, mock_session, mock_base_resources, mock_relationship_patterns
):
    """Test extraction of relationship patterns."""
    mock_result = MagicMock()
    mock_result.__iter__ = MagicMock(
        return_value=iter(
            [
                {
                    "source_id": p["source_id"],
                    "target_id": p["target_id"],
                    "rel_type": p["rel_type"],
                    "rel_props": p["rel_props"],
                }
                for p in mock_relationship_patterns
            ]
        )
    )
    mock_session.run = MagicMock(return_value=mock_result)

    patterns = await scale_up_service._get_relationship_patterns(mock_base_resources)

    assert len(patterns) == 1
    assert patterns[0]["source_id"] == "vm-abc123"
    assert patterns[0]["target_id"] == "vnet-def456"
    assert patterns[0]["rel_type"] == "CONNECTED_TO"


@pytest.mark.asyncio
async def test_insert_relationship_batch(scale_up_service, mock_session):
    """Test batch insertion of relationships."""
    relationships = [
        {
            "source_id": "synthetic-vm-1",
            "target_id": "synthetic-vnet-1",
            "rel_type": "CONNECTED_TO",
            "rel_props": {},
        }
    ]

    mock_session.run = MagicMock()

    await scale_up_service._insert_relationship_batch(relationships)

    assert mock_session.run.called


# =========================================================================
# Test: Scenario Generators
# =========================================================================


@pytest.mark.asyncio
async def test_generate_hub_spoke(scale_up_service, mock_session):
    """Test hub-spoke topology generation."""
    with patch.object(
        scale_up_service, "_insert_resource_batch", return_value=None
    ), patch.object(
        scale_up_service, "_insert_relationship_batch", return_value=None
    ):

        resources_created, relationships_created = (
            await scale_up_service._generate_hub_spoke(
                tenant_id="tenant-123",
                operation_id="scale-123",
                params={"spoke_count": 3, "resources_per_spoke": 5},
            )
        )

        # 1 hub + 3 spokes + (3 * 5) spoke resources = 19 resources
        assert resources_created == 19
        # 3 hub-spoke connections
        assert relationships_created == 3


@pytest.mark.asyncio
async def test_generate_multi_region(scale_up_service, mock_session):
    """Test multi-region topology generation."""
    with patch.object(scale_up_service.projection, "_insert_resource_batch", return_value=None):

        resources_created, relationships_created = (
            await scale_up_service._generate_multi_region(
                tenant_id="tenant-123",
                operation_id="scale-123",
                params={"region_count": 3, "resources_per_region": 10},
            )
        )

        # 3 regions * 10 resources = 30
        assert resources_created == 30
        assert relationships_created == 0


@pytest.mark.asyncio
async def test_generate_dev_test_prod(scale_up_service, mock_session):
    """Test dev/test/prod topology generation."""
    with patch.object(scale_up_service.projection, "_insert_resource_batch", return_value=None):

        resources_created, relationships_created = (
            await scale_up_service._generate_dev_test_prod(
                tenant_id="tenant-123",
                operation_id="scale-123",
                params={"resources_per_env": 10},
            )
        )

        # 3 environments * 10 resources = 30
        assert resources_created == 30
        assert relationships_created == 0


@pytest.mark.asyncio
async def test_generate_random_resources(scale_up_service, mock_session):
    """Test random resource generation."""
    distribution = {
        "Microsoft.Compute/virtualMachines": 0.6,
        "Microsoft.Network/virtualNetworks": 0.4,
    }

    with patch.object(scale_up_service.projection, "_insert_resource_batch", return_value=None):

        created_count = await scale_up_service._generate_random_resources(
            tenant_id="tenant-123",
            operation_id="scale-123",
            target_count=50,
            distribution=distribution,
        )

        assert created_count == 50


@pytest.mark.asyncio
async def test_generate_random_relationships(scale_up_service, mock_session):
    """Test random relationship generation."""
    # Mock resources
    mock_result = MagicMock()
    mock_result.__iter__ = MagicMock(
        return_value=iter(
            [{"id": f"resource-{i}", "type": "Microsoft.Compute/virtualMachines"}
             for i in range(10)]
        )
    )
    mock_session.run = MagicMock(return_value=mock_result)

    with patch.object(
        scale_up_service, "_insert_relationship_batch", return_value=None
    ):

        created_count = await scale_up_service._generate_random_relationships(
            tenant_id="tenant-123", operation_id="scale-123", density=0.2
        )

        # With 10 resources and 0.2 density, we expect some relationships
        assert created_count >= 0


# =========================================================================
# Test: Validation Integration
# =========================================================================


@pytest.mark.asyncio
async def test_validation_enabled(mock_session_manager):
    """Test that validation runs when enabled."""
    service = ScaleUpService(
        session_manager=mock_session_manager, validation_enabled=True
    )

    with patch.object(service, "validate_tenant_exists", return_value=True), patch.object(
        service, "_get_base_resources", return_value=[{"id": "r1", "type": "t1", "props": {}}]
    ), patch.object(service, "_replicate_resources", return_value=5), patch.object(
        service, "_clone_relationships", return_value=2
    ), patch.object(
        service, "_validate_operation", return_value=True
    ) as mock_validate:

        result = await service.scale_up_template(
            tenant_id="tenant-123", scale_factor=2.0
        )

        assert result.success is True
        assert mock_validate.called
        assert result.validation_passed is True


@pytest.mark.asyncio
async def test_validation_disabled(mock_session_manager):
    """Test that validation is skipped when disabled."""
    service = ScaleUpService(
        session_manager=mock_session_manager, validation_enabled=False
    )

    with patch.object(service, "validate_tenant_exists", return_value=True), patch.object(
        service, "_get_base_resources", return_value=[{"id": "r1", "type": "t1", "props": {}}]
    ), patch.object(service, "_replicate_resources", return_value=5), patch.object(
        service, "_clone_relationships", return_value=2
    ), patch.object(
        service, "_validate_operation", return_value=True
    ) as mock_validate:

        result = await service.scale_up_template(
            tenant_id="tenant-123", scale_factor=2.0
        )

        assert result.success is True
        assert not mock_validate.called


# =========================================================================
# Test: Error Handling and Rollback
# =========================================================================


@pytest.mark.asyncio
async def test_template_scale_up_rollback_on_error(scale_up_service):
    """Test that rollback is attempted on template scale-up failure."""
    from neo4j.exceptions import Neo4jError

    with patch.object(
        scale_up_service, "validate_tenant_exists", return_value=True
    ), patch.object(
        scale_up_service,
        "_get_base_resources",
        side_effect=Neo4jError("Database error"),
    ), patch.object(
        scale_up_service, "rollback_operation", return_value=0
    ) as mock_rollback:

        result = await scale_up_service.scale_up_template(
            tenant_id="tenant-123", scale_factor=2.0
        )

        assert result.success is False
        assert mock_rollback.called


@pytest.mark.asyncio
async def test_scenario_scale_up_rollback_on_error(scale_up_service):
    """Test that rollback is attempted on scenario scale-up failure."""
    from neo4j.exceptions import Neo4jError

    with patch.object(
        scale_up_service, "validate_tenant_exists", return_value=True
    ), patch.object(
        scale_up_service,
        "_generate_hub_spoke",
        side_effect=Neo4jError("Generation error"),
    ), patch.object(
        scale_up_service, "rollback_operation", return_value=0
    ) as mock_rollback:

        result = await scale_up_service.scale_up_scenario(
            tenant_id="tenant-123", scenario="hub-spoke", params={}
        )

        assert result.success is False
        assert mock_rollback.called


@pytest.mark.asyncio
async def test_random_scale_up_rollback_on_error(scale_up_service):
    """Test that rollback is attempted on random scale-up failure."""
    from neo4j.exceptions import Neo4jError

    config = {"resource_type_distribution": {"Microsoft.Compute/virtualMachines": 1.0}}

    with patch.object(
        scale_up_service, "validate_tenant_exists", return_value=True
    ), patch.object(
        scale_up_service,
        "_generate_random_resources",
        side_effect=Neo4jError("Generation error"),
    ), patch.object(
        scale_up_service, "rollback_operation", return_value=0
    ) as mock_rollback:

        result = await scale_up_service.scale_up_random(
            tenant_id="tenant-123", target_count=100, config=config
        )

        assert result.success is False
        assert mock_rollback.called


# =========================================================================
# Test: ScaleUpResult Dataclass
# =========================================================================


def test_scale_up_result_creation():
    """Test ScaleUpResult dataclass creation."""
    result = ScaleUpResult(
        operation_id="scale-123",
        tenant_id="tenant-123",
        strategy="template",
        resources_created=50,
        relationships_created=25,
        duration_seconds=15.5,
        success=True,
        validation_passed=True,
        error_message=None,
        metadata={"key": "value"},
    )

    assert result.operation_id == "scale-123"
    assert result.tenant_id == "tenant-123"
    assert result.strategy == "template"
    assert result.resources_created == 50
    assert result.relationships_created == 25
    assert result.duration_seconds == 15.5
    assert result.success is True
    assert result.validation_passed is True
    assert result.error_message is None
    assert result.metadata == {"key": "value"}


def test_scale_up_result_failure():
    """Test ScaleUpResult for failed operation."""
    result = ScaleUpResult(
        operation_id="scale-123",
        tenant_id="tenant-123",
        strategy="template",
        resources_created=0,
        relationships_created=0,
        duration_seconds=1.0,
        success=False,
        validation_passed=False,
        error_message="Operation failed",
    )

    assert result.success is False
    assert result.validation_passed is False
    assert result.error_message == "Operation failed"
