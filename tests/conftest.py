import os
from typing import Any, Dict, List
from unittest.mock import Mock

import pytest

# from testcontainers.neo4j import Neo4jContainer  # Commented out - complex setup


# ============================================================================
# Resource Processor Test Fixtures
# ============================================================================


@pytest.fixture
def mock_neo4j_session():
    """Provide a mock Neo4j session."""
    mock_session = Mock()
    mock_session.queries_run = []  # Track queries for assertions
    mock_session.run = Mock(return_value=Mock(single=Mock(return_value={})))
    return mock_session


@pytest.fixture
def mock_llm_generator():
    """Provide a mock LLM generator."""

    class MockLLMGenerator:
        def __init__(self):
            self.descriptions_generated = []

        async def generate_resource_description(self, resource: Dict[str, Any]) -> str:
            desc = f"Mock description for {resource.get('name', 'Unknown')}"
            self.descriptions_generated.append(desc)
            return desc

        async def generate_resource_group_description(
            self, rg_name: str, subscription_id: str, resources: List[Dict[str, Any]]
        ) -> str:
            return f"Mock RG description for {rg_name}"

        async def generate_tag_description(
            self, key: str, value: str, resources: List[Dict[str, Any]]
        ) -> str:
            return f"Mock tag description for {key}:{value}"

    return MockLLMGenerator()


@pytest.fixture
def sample_resource() -> Dict[str, Any]:
    """Provide a sample resource for testing."""
    return {
        "id": "/subscriptions/test-sub-123/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm",
        "name": "test-vm",
        "type": "Microsoft.Compute/virtualMachines",
        "location": "eastus",
        "resource_group": "test-rg",
        "subscription_id": "test-sub-123",
        "tags": {"Environment": "Test"},
        "kind": None,
        "sku": None,
    }


@pytest.fixture
def sample_resources(sample_resource: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Provide a list of sample resources for testing."""
    resource1 = sample_resource.copy()
    resource2 = sample_resource.copy()
    resource2["id"] = "/subscriptions/test-sub-123/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm-2"
    resource2["name"] = "test-vm-2"
    return [resource1, resource2]


# ============================================================================
# Neo4j Container Fixtures
# ============================================================================


@pytest.fixture(scope="function")
def neo4j_container():
    """Provides mock Neo4j connection details for testing."""
    uri = "bolt://localhost:7687"
    user = "neo4j"
    password = "test_password"

    os.environ["NEO4J_URI"] = uri
    os.environ["NEO4J_USER"] = user
    os.environ["NEO4J_PASSWORD"] = password

    yield uri, user, password


@pytest.fixture(scope="session")
def shared_neo4j_container():
    """Provides mock Neo4j connection details for testing."""
    uri = "bolt://localhost:7687"
    user = "neo4j"
    password = "test_password"

    os.environ["NEO4J_URI"] = uri
    os.environ["NEO4J_USER"] = user
    os.environ["NEO4J_PASSWORD"] = password

    yield uri, user, password


@pytest.fixture
def mock_terraform_installed():
    """Mock terraform being installed for tests that don't need actual terraform."""
    with pytest.mock.patch(
        "src.utils.cli_installer.is_tool_installed", return_value=True
    ):
        yield


@pytest.fixture
def temp_deployments_dir(tmp_path):
    """Create a temporary deployments directory for testing."""
    deployments_dir = tmp_path / ".deployments"
    deployments_dir.mkdir()
    (deployments_dir / "registry.json").write_text("{}")
    return deployments_dir


@pytest.fixture
def mock_neo4j_connection():
    """Mock Neo4j connection for tests that don't need actual database."""
    from unittest.mock import MagicMock

    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__.return_value = mock_session
    mock_driver.session.return_value.__exit__.return_value = None

    with pytest.mock.patch("neo4j.GraphDatabase.driver", return_value=mock_driver):
        yield mock_driver, mock_session
