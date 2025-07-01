import subprocess

import pytest


@pytest.fixture(scope="session", autouse=True)
def clean_neo4j_container():
    """Ensure no old/exited Neo4j containers or volumes are present before tests."""
    subprocess.run(
        ["docker", "rm", "-f", "azure-tenant-grapher-neo4j"],
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["docker", "volume", "rm", "-f", "azure-tenant-grapher-neo4j-data"],
        capture_output=True,
        text=True,
    )
    yield
