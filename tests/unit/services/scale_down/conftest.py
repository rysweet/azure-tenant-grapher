# tests/unit/services/scale_down/conftest.py
"""Shared test fixtures for scale_down services testing.

This module provides common mocks and fixtures used across all scale_down service tests,
following the project's testing philosophy (ruthless simplicity, no stubs).
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import networkx as nx
import pytest


@pytest.fixture
def mock_neo4j_session_manager():
    """Provide mocked Neo4j session manager for database operations."""
    mock_manager = MagicMock()
    mock_session = MagicMock()

    # Mock session context manager
    mock_manager.session.return_value.__enter__.return_value = mock_session
    mock_manager.session.return_value.__exit__.return_value = None

    return mock_manager


@pytest.fixture
def sample_networkx_graph():
    """Provide sample NetworkX directed graph for testing."""
    G = nx.DiGraph()

    # Add nodes with properties
    G.add_node("node1", type="Microsoft.Compute/virtualMachines", name="vm1")
    G.add_node("node2", type="Microsoft.Network/virtualNetworks", name="vnet1")
    G.add_node("node3", type="Microsoft.Storage/storageAccounts", name="storage1")
    G.add_node("node4", type="Microsoft.Compute/virtualMachines", name="vm2")
    G.add_node("node5", type="Microsoft.Network/networkInterfaces", name="nic1")

    # Add edges (relationships)
    G.add_edge("node1", "node5")  # VM -> NIC
    G.add_edge("node5", "node2")  # NIC -> VNet
    G.add_edge("node4", "node5")  # VM2 -> NIC
    G.add_edge("node3", "node1")  # Storage -> VM1

    return G


@pytest.fixture
def sample_node_properties():
    """Provide sample node properties dictionary."""
    return {
        "node1": {
            "id": "node1",
            "type": "Microsoft.Compute/virtualMachines",
            "name": "vm1",
            "location": "eastus",
            "tags": {"environment": "production"},
        },
        "node2": {
            "id": "node2",
            "type": "Microsoft.Network/virtualNetworks",
            "name": "vnet1",
            "location": "eastus",
            "tags": {"environment": "production"},
        },
        "node3": {
            "id": "node3",
            "type": "Microsoft.Storage/storageAccounts",
            "name": "storage1",
            "location": "eastus",
            "tags": {"environment": "staging"},
        },
        "node4": {
            "id": "node4",
            "type": "Microsoft.Compute/virtualMachines",
            "name": "vm2",
            "location": "westus",
            "tags": {"environment": "development"},
        },
        "node5": {
            "id": "node5",
            "type": "Microsoft.Network/networkInterfaces",
            "name": "nic1",
            "location": "eastus",
            "tags": {"environment": "production"},
        },
    }


@pytest.fixture
def temp_output_dir():
    """Provide temporary directory for file outputs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_progress_callback():
    """Provide mock progress callback for testing progress reporting."""
    return MagicMock()


@pytest.fixture
def test_tenant_id():
    """Provide test tenant ID."""
    return "00000000-0000-0000-0000-000000000000"


@pytest.fixture
def mock_neo4j_result():
    """Provide mock Neo4j query result."""
    mock_result = MagicMock()
    mock_record = MagicMock()
    mock_record.__getitem__ = lambda self, key: 42 if key == "deleted_count" else None
    mock_result.single.return_value = mock_record
    return mock_result
