import logging
import os
import time
import uuid

import pytest
# from testcontainers.neo4j import Neo4jContainer  # Commented out - complex setup


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
    with pytest.mock.patch("src.utils.cli_installer.is_tool_installed", return_value=True):
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