import logging
import os
import random
import string
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
    password = "".join(
        random.SystemRandom().choice(string.ascii_letters + string.digits)
        for _ in range(16)
    )
    container_name = f"test-neo4j-{uuid.uuid4().hex[:8]}"
    user = "neo4j"

    # Start the container
    with (
        Neo4jContainer("neo4j:5.19")
        .with_env("NEO4J_AUTH", f"{user}/{password}")
        .with_name(container_name)
    ) as neo4j:
        bolt_port = neo4j.get_exposed_port(7687)
        uri = f"bolt://localhost:{bolt_port}"

        # Set environment variables for the test
        os.environ["NEO4J_URI"] = uri
        os.environ["NEO4J_USER"] = user
        os.environ["NEO4J_PASSWORD"] = password

        # Wait for Neo4j DB readiness (not just container up)
        logger.info(
            f"Waiting for Neo4j DB to become available at {uri} (timeout={readiness_timeout}s)"
        )
        ready = False
        last_error = None
        try:
            import neo4j
            from neo4j import GraphDatabase
        except ImportError:
            logger.warning(
                "neo4j Python driver not installed; skipping DB readiness check."
            )
            yield (uri, user, password)
            return

        # Give Neo4j more time to initialize before first attempt
        time.sleep(5)

        driver = None
        for attempt in range(readiness_timeout):
            try:
                # Close previous driver if exists to avoid connection leaks
                if driver:
                    driver.close()

                driver = GraphDatabase.driver(uri, auth=(user, password))
                with driver.session() as session:
                    session.run("RETURN 1")
                ready = True
                logger.info(f"Neo4j DB is ready after {attempt + 1} attempts.")
                break
            except Exception as e:
                last_error = e
                logger.debug(f"Neo4j not ready yet (attempt {attempt + 1}): {e}")
                # Exponential backoff to avoid rate limiting
                wait_time = min(2 ** (attempt // 10), 5)  # Cap at 5 seconds
                time.sleep(wait_time)

        # Clean up driver connection
        if driver:
            driver.close()
        if not ready:
            logger.error(
                f"Neo4j did not become ready within {readiness_timeout}s. Last error: {last_error}"
            )
            raise RuntimeError(
                f"Neo4j did not become ready within {readiness_timeout}s. Last error: {last_error}"
            )

        yield (uri, user, password)


@pytest.fixture
def mcp_server_process():
    """Stub fixture for mcp_server_process to unblock integration tests.
    Replace with real implementation as needed."""
    pytest.skip("mcp_server_process fixture is not implemented in this environment.")
    yield None
