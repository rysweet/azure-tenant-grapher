import logging
import os
import time
import uuid

import pytest
from testcontainers.neo4j import Neo4jContainer


@pytest.fixture(scope="function")
def neo4j_container():
    """
    Function-scoped fixture to provide an ephemeral, isolated Neo4j container for each test.

    - Uses testcontainers to spin up a unique Neo4j container per test.
    - Allocates a random password and unique container name.
    - Yields (uri, user, password) for test code.
    - Sets NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD env vars for the test.
    - Ensures cleanup after test.
    - Waits for actual Neo4j DB readiness, not just container status.
    - Timeout is configurable via NEO4J_READINESS_TIMEOUT_SECONDS env var (default 60).
    """
    logger = logging.getLogger("conftest.neo4j_container")
    logging.basicConfig(level=logging.INFO)
    readiness_timeout = int(os.environ.get("NEO4J_READINESS_TIMEOUT_SECONDS", 60))
    container_name = f"test-neo4j-{uuid.uuid4().hex[:8]}"
    import secrets

    user = "neo4j"
    # Generate a random, secure password for each test run
    password = secrets.token_urlsafe(12)

    # Use a known-good Neo4j image version for testcontainers compatibility
    with (
        Neo4jContainer("neo4j:4.4")
        .with_env("NEO4J_AUTH", f"neo4j/{password}")
        .with_name(container_name)
    ) as neo4j:
        bolt_port = neo4j.get_exposed_port(7687)
        uri = f"bolt://localhost:{bolt_port}"
        # Log the credentials for debugging
        print(
            f"[DEBUG] Neo4j test container started: name={container_name}, uri={uri}, user={user}, password={password}"
        )

        # Set environment variables for the test and all subprocesses
        os.environ["NEO4J_URI"] = uri
        os.environ["NEO4J_USER"] = user
        os.environ["NEO4J_PASSWORD"] = password

        # Wait for Neo4j readiness
        logger.info(f"Waiting for Neo4j readiness at {uri}...")
        start_time = time.time()
        while time.time() - start_time < readiness_timeout:
            # Attempt to establish connection via Python driver
            try:
                from neo4j import GraphDatabase

                driver = GraphDatabase.driver(uri, auth=(user, password))
                with driver.session() as session:
                    result = session.run("RETURN 1")
                    if result.single()[0] == 1:
                        logger.info(f"Neo4j is ready at {uri}")
                        driver.close()
                        yield uri, user, password
                        return
                driver.close()
            except Exception as e:
                logger.debug(f"Waiting for Neo4j readiness: {e}")
                time.sleep(1)

        # If we got here, it timed out
        raise TimeoutError(
            f"Neo4j container did not become ready within {readiness_timeout} seconds"
        )


@pytest.fixture(scope="session")
def shared_neo4j_container():
    """
    Session-scoped fixture for tests that can share a Neo4j container.
    
    - Uses testcontainers to spin up a single Neo4j container for the session.
    - Yields (uri, user, password) for test code.
    - Sets NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD env vars.
    - Ensures cleanup after session.
    """
    logger = logging.getLogger("conftest.shared_neo4j_container")
    logging.basicConfig(level=logging.INFO)
    readiness_timeout = int(os.environ.get("NEO4J_READINESS_TIMEOUT_SECONDS", 60))
    container_name = f"test-neo4j-shared-{uuid.uuid4().hex[:8]}"
    import secrets

    user = "neo4j"
    password = secrets.token_urlsafe(12)

    # Use a known-good Neo4j image version for testcontainers compatibility
    with (
        Neo4jContainer("neo4j:4.4")
        .with_env("NEO4J_AUTH", f"neo4j/{password}")
        .with_name(container_name)
    ) as neo4j:
        bolt_port = neo4j.get_exposed_port(7687)
        uri = f"bolt://localhost:{bolt_port}"
        
        print(
            f"[DEBUG] Shared Neo4j test container started: name={container_name}, uri={uri}, user={user}, password={password}"
        )

        # Set environment variables for the test and all subprocesses
        os.environ["NEO4J_URI"] = uri
        os.environ["NEO4J_USER"] = user
        os.environ["NEO4J_PASSWORD"] = password

        # Wait for Neo4j readiness
        logger.info(f"Waiting for Neo4j readiness at {uri}...")
        start_time = time.time()
        while time.time() - start_time < readiness_timeout:
            # Attempt to establish connection via Python driver
            try:
                from neo4j import GraphDatabase

                driver = GraphDatabase.driver(uri, auth=(user, password))
                with driver.session() as session:
                    result = session.run("RETURN 1")
                    if result.single()[0] == 1:
                        logger.info(f"Neo4j is ready at {uri}")
                        driver.close()
                        yield uri, user, password
                        return
                driver.close()
            except Exception as e:
                logger.debug(f"Waiting for Neo4j readiness: {e}")
                time.sleep(1)

        # If we got here, it timed out
        raise TimeoutError(
            f"Neo4j container did not become ready within {readiness_timeout} seconds"
        )


# Add common fixtures for mocking tools
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