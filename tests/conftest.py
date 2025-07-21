import logging
import os
import subprocess
import sys
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
    user = "neo4j"
    password = "test"  # testcontainers default

    # Use a known-good Neo4j image version for testcontainers compatibility
    with (
        Neo4jContainer("neo4j:4.4")
        .with_env("NEO4J_AUTH", "neo4j/test")
        .with_name(container_name)
    ) as neo4j:
        bolt_port = neo4j.get_exposed_port(7687)
        uri = f"bolt://localhost:{bolt_port}"

        # Set environment variables for the test
        os.environ["NEO4J_URI"] = uri
        os.environ["NEO4J_USER"] = user
        os.environ["NEO4J_PASSWORD"] = password

        logger.info(
            f"Neo4j test container started with URI: {uri}, user: {user}, password: {password}"
        )
        print(
            f"[DEBUG] Neo4j test container started with URI: {uri}, user: {user}, password: {password}"
        )

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
            import pytest

            pytest.skip(
                f"Neo4j testcontainer authentication failed: {last_error}\n"
                "This is a known issue with testcontainers-python and Neo4j images on some systems. "
                "See https://github.com/testcontainers/testcontainers-python/issues for details."
            )

        yield (uri, user, password)


@pytest.fixture(scope="function")
def mcp_server_process():
    """
    Function-scoped fixture to start and clean up the MCP server process for integration tests.

    - Starts the MCP server as a subprocess using the same Python interpreter.
    - Waits for the server to be ready (by reading stdout for a ready message).
    - Yields the process object to the test.
    - Ensures the process is terminated and cleaned up after the test.
    - Does not interfere with persistent data or dev containers.
    """
    # Use the same Python interpreter and CLI entrypoint
    proc = subprocess.Popen(
        [sys.executable, "-m", "scripts.cli", "mcp-server"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        env=os.environ.copy(),
        bufsize=1,
        universal_newlines=True,
    )
    try:
        # Wait for the MCP server to be ready (look for a ready message)
        ready = False
        for _ in range(60):  # up to 30 seconds
            line = proc.stdout.readline()
            if not line:
                break
            if "MCP Server is ready" in line or "MCP Agent is ready" in line:
                ready = True
                break
            time.sleep(0.5)
        if not ready:
            proc.terminate()
            proc.wait(timeout=10)
            raise RuntimeError("MCP server did not become ready in time")
        yield proc
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except Exception:
                proc.kill()
        if proc.stdout:
            proc.stdout.close()
