import os
import random
import string
import subprocess
import uuid

import pytest


@pytest.fixture(scope="session", autouse=True)
def neo4j_test_env():
    """
    Session-scoped fixture to set up unique Neo4j container and password for tests.

    - Sets NEO4J_CONTAINER_NAME and NEO4J_PASSWORD to random values for each test session.
    - Ensures cleanup of all test artifacts (container, volume) even on failure.
    - Documents password policy: never hardcode secrets, always use env vars.
    """
    container_name = f"azure-tenant-grapher-neo4j-{uuid.uuid4().hex[:8]}"
    volume_name = f"{container_name}-data"
    password = "".join(
        random.SystemRandom().choice(string.ascii_letters + string.digits)
        for _ in range(16)
    )

    os.environ["NEO4J_CONTAINER_NAME"] = container_name
    os.environ["NEO4J_PASSWORD"] = password

    # Cleanup before
    subprocess.run(
        ["docker", "rm", "-f", container_name],
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["docker", "volume", "rm", "-f", volume_name],
        capture_output=True,
        text=True,
    )
    yield
    # Cleanup after
    subprocess.run(
        ["docker", "rm", "-f", container_name],
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["docker", "volume", "rm", "-f", volume_name],
        capture_output=True,
        text=True,
    )
