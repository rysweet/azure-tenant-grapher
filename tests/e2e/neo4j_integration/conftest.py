"""Neo4j integration test configuration and fixtures."""

import pytest
import asyncio
import time
from typing import Generator, Dict, Any, List
from unittest.mock import Mock, patch, MagicMock
from neo4j import GraphDatabase, Session, Transaction
# from testcontainers.neo4j import Neo4jContainer  # Commented out - complex setup
import docker
import os


@pytest.fixture(scope="session")
def neo4j_container() -> Generator[Neo4jContainer, None, None]:
    """Provide a Neo4j test container for the entire test session."""
    container = Neo4jContainer(
        image="neo4j:5.15",
        initial_password="testpassword123"
    )
    container.start()

    # Wait for Neo4j to be ready
    max_retries = 30
    for i in range(max_retries):
        try:
            driver = GraphDatabase.driver(
                container.get_connection_url(),
                auth=("neo4j", "testpassword123")
            )
            with driver.session() as session:
                session.run("RETURN 1")
            driver.close()
            break
        except Exception:
            if i == max_retries - 1:
                container.stop()
                raise
            time.sleep(1)

    yield container
    container.stop()


@pytest.fixture
def neo4j_driver(neo4j_container):
    """Provide a Neo4j driver for tests."""
    driver = GraphDatabase.driver(
        neo4j_container.get_connection_url(),
        auth=("neo4j", "testpassword123"),
        max_connection_pool_size=50,
        connection_acquisition_timeout=30
    )
    yield driver
    driver.close()


@pytest.fixture
def neo4j_session(neo4j_driver):
    """Provide a Neo4j session for tests."""
    session = neo4j_driver.session()
    yield session
    # Clean up test data
    session.run("MATCH (n) WHERE n.test = true DETACH DELETE n")
    session.close()


@pytest.fixture
def sample_azure_data() -> Dict[str, Any]:
    """Provide sample Azure resource data for testing."""
    return {
        "subscriptions": [
            {
                "id": "/subscriptions/sub-123",
                "displayName": "Test Subscription",
                "state": "Enabled"
            }
        ],
        "resource_groups": [
            {
                "id": "/subscriptions/sub-123/resourceGroups/rg-test",
                "name": "rg-test",
                "location": "eastus"
            }
        ],
        "resources": [
            {
                "id": "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/vm-test",
                "name": "vm-test",
                "type": "Microsoft.Compute/virtualMachines",
                "location": "eastus"
            }
        ]
    }


@pytest.fixture
def large_dataset() -> List[Dict[str, Any]]:
    """Generate a large dataset for performance testing."""
    resources = []
    for i in range(10000):
        resources.append({
            "id": f"/subscriptions/sub-{i//100}/resourceGroups/rg-{i//10}/providers/Microsoft.Compute/virtualMachines/vm-{i}",
            "name": f"vm-{i}",
            "type": "Microsoft.Compute/virtualMachines",
            "location": "eastus" if i % 2 == 0 else "westus",
            "tags": {
                "environment": "prod" if i % 3 == 0 else "dev",
                "team": f"team-{i % 10}"
            }
        })
    return resources


@pytest.fixture
def mock_connection_pool():
    """Mock connection pool for testing connection management."""
    pool = MagicMock()
    pool.size = 10
    pool.in_use = 0
    pool.available = 10
    pool.acquire = MagicMock(return_value=MagicMock())
    pool.release = MagicMock()
    return pool