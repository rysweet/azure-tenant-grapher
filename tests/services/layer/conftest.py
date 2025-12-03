"""
Pytest fixtures for layer service tests (Issue #570)

Provides shared fixtures for unit, integration, and E2E tests of layer operations
with SCAN_SOURCE_NODE relationship preservation.

Philosophy:
- DRY: Shared fixtures reduce duplication
- Isolated: Each test gets fresh fixtures
- Fast: Fixtures are lightweight
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock
from datetime import datetime

from src.services.layer.models import LayerMetadata, LayerType
from src.services.layer.export import LayerExportOperations
from src.utils.session_manager import Neo4jSessionManager


# =============================================================================
# Mock Fixtures (for unit tests)
# =============================================================================


@pytest.fixture
def mock_session_manager():
    """
    Mock Neo4j session manager for fast unit tests.

    Returns:
        Tuple of (mock_manager, mock_session) for easy access to both
    """
    mock_manager = Mock(spec=Neo4jSessionManager)
    mock_session = MagicMock()

    # Mock the context manager behavior
    mock_manager.session.return_value.__enter__.return_value = mock_session
    mock_manager.session.return_value.__exit__.return_value = None

    return mock_manager, mock_session


@pytest.fixture
def mock_crud_operations():
    """Mock CRUD operations for layer metadata."""
    mock_crud = AsyncMock()

    # Default layer metadata
    source_layer = LayerMetadata(
        layer_id="test-layer",
        name="Test Layer",
        description="Test layer for unit tests",
        created_at=datetime.utcnow(),
        tenant_id="test-tenant",
        layer_type=LayerType.BASELINE,
        node_count=10,
        relationship_count=5,
    )

    mock_crud.get_layer.return_value = source_layer
    mock_crud.create_layer.return_value = None

    return mock_crud


@pytest.fixture
def mock_stats_operations():
    """Mock stats operations for layer statistics."""
    mock_stats = AsyncMock()
    mock_stats.refresh_layer_stats.return_value = None
    return mock_stats


# =============================================================================
# Sample Data Fixtures
# =============================================================================


@pytest.fixture
def sample_resource_nodes():
    """
    Sample Resource nodes for testing.

    Returns list of Resource node dictionaries with realistic Azure resource data.
    """
    return [
        {
            "id": "/subscriptions/test-sub-123/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "location": "eastus",
            "layer_id": "test-layer",
            "tags": {"Environment": "Production", "Owner": "TeamA"},
        },
        {
            "id": "/subscriptions/test-sub-123/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1",
            "name": "vnet1",
            "type": "Microsoft.Network/virtualNetworks",
            "location": "eastus",
            "layer_id": "test-layer",
            "tags": {"Environment": "Production"},
        },
        {
            "id": "/subscriptions/test-sub-123/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1",
            "name": "storage1",
            "type": "Microsoft.Storage/storageAccounts",
            "location": "eastus",
            "layer_id": "test-layer",
            "tags": {},
        },
    ]


@pytest.fixture
def sample_original_nodes():
    """
    Sample Original nodes (scan results) for testing.

    These represent the raw scan data before abstraction.
    """
    return [
        {
            "id": "/subscriptions/test-sub-123/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "location": "eastus",
            "tags": {"Environment": "Production", "Owner": "TeamA"},
        },
        {
            "id": "/subscriptions/test-sub-123/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1",
            "name": "vnet1",
            "type": "Microsoft.Network/virtualNetworks",
            "location": "eastus",
            "tags": {"Environment": "Production"},
        },
    ]


@pytest.fixture
def sample_scan_source_relationships():
    """
    Sample SCAN_SOURCE_NODE relationships for testing.

    Maps abstracted Resource IDs to Original Resource IDs.
    """
    return [
        {
            "source": "/subscriptions/test-sub-123/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "target": "/subscriptions/test-sub-123/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "type": "SCAN_SOURCE_NODE",
            "properties": {},
        },
        {
            "source": "/subscriptions/test-sub-123/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1",
            "target": "/subscriptions/test-sub-123/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1",
            "type": "SCAN_SOURCE_NODE",
            "properties": {},
        },
    ]


@pytest.fixture
def sample_layer_metadata():
    """Sample LayerMetadata for testing."""
    return LayerMetadata(
        layer_id="sample-layer",
        name="Sample Layer",
        description="Sample layer for testing",
        created_at=datetime.utcnow(),
        created_by="test_user",
        tenant_id="test-tenant",
        layer_type=LayerType.BASELINE,
        node_count=3,
        relationship_count=2,
        tags=["test", "sample"],
    )


# =============================================================================
# Service Instance Fixtures
# =============================================================================


@pytest.fixture
def layer_export_operations(mock_session_manager, mock_crud_operations, mock_stats_operations):
    """
    Create LayerExportOperations instance with mocked dependencies.

    Use this fixture for unit tests that need to test layer export operations
    without real database connections.
    """
    session_manager, _ = mock_session_manager
    return LayerExportOperations(
        session_manager=session_manager,
        crud_operations=mock_crud_operations,
        stats_operations=mock_stats_operations,
    )


# =============================================================================
# Helper Functions
# =============================================================================


def make_layer_metadata(layer_id: str, **kwargs) -> LayerMetadata:
    """
    Helper function to create LayerMetadata with defaults.

    Args:
        layer_id: Unique identifier for the layer
        **kwargs: Override default values

    Returns:
        LayerMetadata instance with sensible defaults
    """
    defaults = {
        "name": f"Layer {layer_id}",
        "description": f"Test layer {layer_id}",
        "created_at": datetime.utcnow(),
        "created_by": "test",
        "tenant_id": "test-tenant",
        "layer_type": LayerType.EXPERIMENTAL,
    }
    defaults.update(kwargs)
    return LayerMetadata(layer_id=layer_id, **defaults)


def make_resource_node(resource_id: str, layer_id: str, **kwargs) -> dict:
    """
    Helper function to create Resource node dictionaries.

    Args:
        resource_id: Azure resource ID
        layer_id: Layer this resource belongs to
        **kwargs: Additional properties

    Returns:
        Resource node dictionary
    """
    defaults = {
        "id": resource_id,
        "name": resource_id.split("/")[-1],
        "type": "Microsoft.Resources/genericResource",
        "location": "eastus",
        "layer_id": layer_id,
        "tags": {},
    }
    defaults.update(kwargs)
    return defaults


# =============================================================================
# Markers Configuration
# =============================================================================


def pytest_configure(config):
    """Register custom markers for layer tests."""
    config.addinivalue_line(
        "markers",
        "unit: mark test as unit test (fast, heavily mocked)",
    )
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test (requires Neo4j)",
    )
    config.addinivalue_line(
        "markers",
        "e2e: mark test as end-to-end test (full workflow, slower)",
    )
    config.addinivalue_line(
        "markers",
        "scan_source_node: mark test as related to SCAN_SOURCE_NODE preservation (Issue #570)",
    )
