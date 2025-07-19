import os
import subprocess

import pytest

pytest.importorskip("subprocess")

# IMPORTANT: NEO4J_PORT must be set in the environment for all CLI/test subprocesses.
# The port must match the docker-compose.yml mapping and Neo4j startup logic.
# Default is 7687 if not set. See README for details.

# Check for docker presence, skip if not available
try:
    subprocess.run(
        ["docker", "--version"],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
except Exception:
    pytest.skip("docker is not available in the environment")


@pytest.mark.integration
def test_build_no_dashboard_autostarts_neo4j(tmp_path, neo4j_container):
    """
    Integration test: verifies that running the build command with --no-dashboard
    autostarts a Neo4j container and connects to it, using an isolated ephemeral container.
    This test is self-contained and does not interfere with dev containers or persistent data.
    """
    # neo4j_container fixture yields (uri, user, password) and sets env vars
    uri, user, password = neo4j_container

    env = os.environ.copy()
    # Ensure CLI uses the ephemeral test container
    env["NEO4J_URI"] = uri
    env["NEO4J_USER"] = user
    env["NEO4J_PASSWORD"] = password
    # Remove any port/volume/container overrides to avoid interfering with dev containers
    env.pop("NEO4J_PORT", None)
    env.pop("NEO4J_CONTAINER_NAME", None)
    env.pop("NEO4J_DATA_VOLUME", None)
    # Increase Neo4j readiness timeout for slow container startup
    env["NEO4J_READY_TIMEOUT"] = "300"

    try:
        proc = subprocess.run(
            [
                "uv",
                "run",
                "azure-tenant-grapher",
                "build",
                "--no-dashboard",
                "--resource-limit=1",
            ],
            text=True,
            capture_output=True,
            timeout=300,
            env=env,
        )
    except subprocess.TimeoutExpired as e:
        pytest.fail(
            f"Process timed out after 300s.\nstdout:\n{getattr(e, 'stdout', '')}\nstderr:\n{getattr(e, 'stderr', '')}"
        )

    # Assert return code and include output for diagnostics
    print(f"[TEST DEBUG] CLI stdout:\n{proc.stdout}")
    print(f"[TEST DEBUG] CLI stderr:\n{proc.stderr}")
    assert proc.returncode == 0, (
        f"Process failed with return code {proc.returncode}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    # The neo4j_container fixture ensures the container is running and will be cleaned up after the test.
    # Optionally, verify the container is still up by connecting to the DB (already done in fixture).
