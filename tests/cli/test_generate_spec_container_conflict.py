import os
import pathlib
import subprocess
import time
import uuid

import pytest
from testcontainers.neo4j import Neo4jContainer


@pytest.mark.skipif(
    not os.environ.get("RUN_DOCKER_CONFLICT_TESTS"),
    reason="Set RUN_DOCKER_CONFLICT_TESTS=1 to run this test (it manipulates Docker containers).",
)
def test_generate_spec_container_name_conflict(tmp_path: pathlib.Path):
    """
    Simulate a scenario where a Neo4j container with the default name is already running,
    but with a different password than the one provided to the CLI.

    Container name conflicts are not a valid success scenario and should be treated as a misconfiguration.
    The CLI must detect the container name conflict and fail with a clear authentication or container conflict error.
    This test ensures that authentication failures, password mismatches, or container name conflicts are handled
    explicitly and reported to the user, and that no output file is produced.

    Expected behavior:
    - If a container with the default name is running but the password is wrong,
      the CLI should fail and print an authentication error or password mismatch message.
    - If a container name conflict occurs, the CLI should fail and report the conflict as a misconfiguration.
    """

    import docker
    from testcontainers.neo4j import Neo4jContainer

    default_container_name = "azure-tenant-grapher-neo4j"
    correct_password = "pw" + uuid.uuid4().hex[:8]  # pragma: allowlist secret
    wrong_password = "pw" + uuid.uuid4().hex[:8]  # pragma: allowlist secret

    # Remove any existing container with the default name to avoid test setup conflicts
    client = docker.from_env()
    try:
        existing = client.containers.list(
            all=True, filters={"name": default_container_name}
        )
        for c in existing:
            c.remove(force=True)
    except Exception as e:
        print(
            f"Warning: could not remove existing container {default_container_name}: {e}"
        )

    # Start a Neo4j container with the default name and a known password
    try:
        neo4j_container = (
            Neo4jContainer("neo4j:5.19")
            .with_env("NEO4J_AUTH", f"neo4j/{correct_password}")
            .with_name(default_container_name)
        )
        with neo4j_container:
            time.sleep(5)  # Ensure container is up

            # Now run the CLI with a *different* password, which should cause an auth failure
            cli_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "../../scripts/cli.py")
            )
            output_path = tmp_path / "spec.json"
            env = {
                **os.environ,
                "NEO4J_PASSWORD": wrong_password,  # Intentionally wrong
                "NEO4J_CONTAINER_NAME": default_container_name,
                "NEO4J_PORT": "7687",
                "NEO4J_URI": "",
                "NEO4J_DATA_VOLUME": "azure-tenant-grapher-neo4j-data",
            }
            print("[TEST ENV DUMP][BEFORE CLI INVOCATION]")
            for k in [
                "NEO4J_CONTAINER_NAME",
                "NEO4J_DATA_VOLUME",
                "NEO4J_PASSWORD",
                "NEO4J_PORT",
                "NEO4J_URI",
            ]:
                print(f"[TEST ENV] {k}={env.get(k)}")
            print(f"[TEST DEBUG] correct_password={correct_password}")
            print(f"[TEST DEBUG] wrong_password={wrong_password}")
            containers_before = client.containers.list(
                all=True, filters={"name": default_container_name}
            )
            print(
                f"[TEST DEBUG] Containers before CLI: {[c.name + ':' + c.status for c in containers_before]}"
            )
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "python",
                    cli_path,
                    "generate-spec",
                    "--output",
                    str(output_path),
                ],
                capture_output=True,
                text=True,
                env=env,
            )
            containers_after = client.containers.list(
                all=True, filters={"name": default_container_name}
            )
            print(
                f"[TEST DEBUG] Containers after CLI: {[c.name + ':' + c.status for c in containers_after]}"
            )
            print(f"[TEST DEBUG] CLI stdout:\n{result.stdout}")
            print(f"[TEST DEBUG] CLI stderr:\n{result.stderr}")

            # Container name conflicts are a misconfiguration and must not result in CLI success.
            # The CLI should fail with a clear authentication or container conflict error,
            # and must not produce an output file.
            assert result.returncode != 0, (
                f"CLI should fail if the password does not match the running container or if there is a container name conflict\n"
                f"correct_password={correct_password}\nwrong_password={wrong_password}\nstderr:\n{result.stderr}"
            )
            assert (
                "auth" in result.stderr.lower()
                or "password" in result.stderr.lower()
                or "mismatch" in result.stderr.lower()
                or "authentication" in result.stderr.lower()
                or "conflict" in result.stderr.lower()
                or "already in use" in result.stderr.lower()
            ), (
                "CLI stderr should indicate authentication failure, password mismatch, or container name conflict. "
                f"STDERR: {result.stderr}\n"
                f"correct_password={correct_password}\nwrong_password={wrong_password}"
            )
            # The output file should not be created
            assert not output_path.exists() or output_path.stat().st_size == 0, (
                "Spec output file should not be created on authentication or container conflict failure\n"
                f"Output file exists: {output_path.exists()}, size: {output_path.stat().st_size if output_path.exists() else 'N/A'}"
            )
    finally:
        # Always clean up the test container and volume
        import docker

        client = docker.from_env()
        print("[TEST ENV DUMP][CLEANUP]")
        for k in [
            "NEO4J_CONTAINER_NAME",
            "NEO4J_DATA_VOLUME",
            "NEO4J_PASSWORD",
            "NEO4J_PORT",
            "NEO4J_URI",
        ]:
            print(f"[TEST ENV] {k}={os.environ.get(k)}")
        try:
            containers = client.containers.list(
                all=True, filters={"name": default_container_name}
            )
            for c in containers:
                print(
                    f"[TEST CLEANUP] Removing container: {c.name} (status: {c.status})"
                )
                c.remove(force=True)
        except Exception as e:
            print(
                f"Warning: could not remove container {default_container_name} in cleanup: {e}"
            )
        try:
            volumes = client.volumes.list(
                filters={"name": "azure-tenant-grapher-neo4j-data"}
            )
            for v in volumes:
                print(f"[TEST CLEANUP] Removing volume: {v.name}")
                v.remove(force=True)
        except Exception as e:
            print(f"Warning: could not remove volume in cleanup: {e}")
        # Also call the container manager's cleanup for extra reliability
        try:
            from src.container_manager import Neo4jContainerManager

            Neo4jContainerManager().cleanup()
        except Exception as e:
            print(f"[TEST DEBUG] Error during container manager cleanup: {e}")


@pytest.mark.skipif(
    not os.environ.get("RUN_DOCKER_CONFLICT_TESTS"),
    reason="Set RUN_DOCKER_CONFLICT_TESTS=1 to run this test (it manipulates Docker containers).",
)
def test_generate_spec_container_stopped_container(tmp_path: pathlib.Path):
    """
    Simulate a scenario where a Neo4j container with the default name exists but is stopped/exited.

    The CLI should remove the stopped container, start a new one, and succeed.
    This test ensures that the CLI can recover from a stopped/exited container with the default name,
    and that it does not fail or get stuck due to a stale container.

    Expected behavior:
    - If a stopped container with the default name exists, the CLI should remove it,
      start a new container, and succeed in generating the spec.
    """
    import docker

    default_container_name = "azure-tenant-grapher-neo4j"
    neo4j_password = "test" + uuid.uuid4().hex[:8]  # pragma: allowlist secret

    # Remove any existing container with the default name to avoid test setup conflicts
    client = docker.from_env()
    try:
        existing = client.containers.list(
            all=True, filters={"name": default_container_name}
        )
        for c in existing:
            c.remove(force=True)
    except Exception as e:
        print(
            f"Warning: could not remove existing container {default_container_name}: {e}"
        )

    # Start a Neo4j container with a unique name (never the CLI's default)
    unique_container_name = f"testcontainers-neo4j-{uuid.uuid4().hex[:8]}"
    try:
        neo4j_container = (
            Neo4jContainer("neo4j:5.19")
            .with_env("NEO4J_AUTH", f"neo4j/{neo4j_password}")
            .with_name(unique_container_name)
        )
        with neo4j_container:
            time.sleep(5)  # Ensure container is up

            # Remove any container with the CLI's default name to ensure a clean state
            try:
                existing = client.containers.list(
                    all=True, filters={"name": default_container_name}
                )
                for c in existing:
                    c.remove(force=True)
            except Exception as e:
                print(
                    f"Warning: could not remove existing container {default_container_name}: {e}"
                )

            # Attempt to run the CLI command that would start another container with the same name
            cli_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "../../scripts/cli.py")
            )
            output_path = tmp_path / "spec_stopped.json"
            env = {
                **os.environ,
                "NEO4J_PASSWORD": neo4j_password,
                "NEO4J_CONTAINER_NAME": default_container_name,
                "NEO4J_PORT": "7687",  # force both to use 7687
                "NEO4J_DATA_VOLUME": "azure-tenant-grapher-neo4j-data",
            }
            env["NEO4J_URI"] = ""
            print("[TEST ENV DUMP][BEFORE CLI INVOCATION]")
            for k in [
                "NEO4J_CONTAINER_NAME",
                "NEO4J_DATA_VOLUME",
                "NEO4J_PASSWORD",
                "NEO4J_PORT",
                "NEO4J_URI",
            ]:
                print(f"[TEST ENV] {k}={env.get(k)}")
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "python",
                    cli_path,
                    "generate-spec",
                    "--output",
                    str(output_path),
                ],
                capture_output=True,
                text=True,
                env=env,
            )
            print(f"[TEST DEBUG] CLI stdout:\n{result.stdout}")
            print(f"[TEST DEBUG] CLI stderr:\n{result.stderr}")

            # The CLI should succeed and produce a spec file
            assert result.returncode == 0, (
                f"CLI should succeed even with stopped container. STDERR: {result.stderr}"
            )
            assert output_path.exists() and output_path.stat().st_size > 0, (
                "Spec output file should be created and non-empty"
            )
    finally:
        # Always clean up the test container and volume
        import docker

        client = docker.from_env()
        print("[TEST ENV DUMP][CLEANUP]")
        for k in [
            "NEO4J_CONTAINER_NAME",
            "NEO4J_DATA_VOLUME",
            "NEO4J_PASSWORD",
            "NEO4J_PORT",
            "NEO4J_URI",
        ]:
            print(f"[TEST ENV] {k}={os.environ.get(k)}")
        try:
            containers = client.containers.list(
                all=True, filters={"name": default_container_name}
            )
            for c in containers:
                print(
                    f"[TEST CLEANUP] Removing container: {c.name} (status: {c.status})"
                )
                c.remove(force=True)
        except Exception as e:
            print(
                f"Warning: could not remove container {default_container_name} in cleanup: {e}"
            )
        try:
            volumes = client.volumes.list(
                filters={"name": "azure-tenant-grapher-neo4j-data"}
            )
            for v in volumes:
                print(f"[TEST CLEANUP] Removing volume: {v.name}")
                v.remove(force=True)
        except Exception as e:
            print(f"Warning: could not remove volume in cleanup: {e}")
        # Also call the container manager's cleanup for extra reliability
        try:
            from src.container_manager import Neo4jContainerManager

            Neo4jContainerManager().cleanup()
        except Exception as e:
            print(f"[TEST DEBUG] Error during container manager cleanup: {e}")
