"""
Container orchestration module for managing Neo4j Docker container.
"""

import os
import random
import shutil
import string
import subprocess  # nosec B404
import time
import uuid
from typing import Optional

import docker
import structlog
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable

from src.logging_config import configure_logging

configure_logging()
logger = structlog.get_logger(__name__)


# Only remove neo4j-data if running in CI or test context
def should_remove_neo4j_data():
    # Remove only if running in CI or test context, not in normal dev
    return (
        os.environ.get("RUN_DOCKER_CONFLICT_TESTS") == "1"
        or os.environ.get("CI") == "1"
        or os.environ.get("PYTEST_CURRENT_TEST") is not None
    )


class Neo4jContainerManager:
    """
    Manages Neo4j Docker container lifecycle.

    # _print_env_block removed (unused debug utility)

    Password Policy:
    - The Neo4j password for tests must be provided via the NEO4J_PASSWORD environment variable.
    - If not set, a random password is generated for each test run.
    - Never hardcode secrets or passwords in test code or fixtures.
    - The container name is randomized per test run to avoid conflicts in parallel CI.

    Container Naming Policy:
    - The Neo4j container name is set via the NEO4J_CONTAINER_NAME environment variable.
    - If not set, a unique name is generated per test run (e.g., azure-tenant-grapher-neo4j-<random>).

    Data Directory Policy:
    - The host data directory (neo4j-data) is only removed in CI or test context (RUN_DOCKER_CONFLICT_TESTS, CI, or PYTEST_CURRENT_TEST).
    - In normal development, the data directory is preserved to avoid data loss.
    """

    """
    Manages Neo4j Docker container lifecycle.

    Password Policy:
    - The Neo4j password for tests must be provided via the NEO4J_PASSWORD environment variable.
    - If not set, a random password is generated for each test run.
    - Never hardcode secrets or passwords in test code or fixtures.
    - The container name is randomized per test run to avoid conflicts in parallel CI.

    Container Naming Policy:
    - The Neo4j container name is set via the NEO4J_CONTAINER_NAME environment variable.
    - If not set, a unique name is generated per test run (e.g., azure-tenant-grapher-neo4j-<random>).
    """

    def __init__(
        self, compose_file: str = "docker-compose.yml", debug: bool = False
    ) -> None:
        """
        Initialize the container manager.

        Args:
            compose_file: Path to docker-compose.yml file
            debug: Enable debug output
        """
        self.debug = debug
        # Only show debug env output if debug is enabled
        if self.debug:
            # Redact sensitive environment variables
            def should_redact(key: str) -> bool:
                """Check if environment variable should be redacted."""
                sensitive_patterns = {
                    'PASSWORD', 'SECRET', 'KEY', 'TOKEN', 'AUTH'
                }
                return any(pattern in key.upper() for pattern in sensitive_patterns)

            safe_env = {
                k: '***REDACTED***' if should_redact(k) else v
                for k, v in os.environ.items()
            }
            print(f"[DEBUG][Neo4jEnv] os.environ at init: {safe_env}")
            print(
                f"[DEBUG][Neo4jEnv] NEO4J_PORT={os.environ.get('NEO4J_PORT')}, NEO4J_URI={os.environ.get('NEO4J_URI')}"
            )
        self.compose_file = compose_file
        self.docker_client = None

        # Set container name based on environment
        self.container_name = self._determine_container_name()
        # Use a unique data volume for tests to avoid interfering with dev data
        self.volume_name = os.getenv(
            "NEO4J_DATA_VOLUME", "azure-tenant-grapher-neo4j-data"
        )
        # Log the container name, volume, and password for debug
        # self._print_env_block("INIT")  # Removed per instructions
        if should_remove_neo4j_data():
            self.data_dir = None  # Use Docker named volume, not host directory
            # Remove the named volume if it exists (test/CI only)
            try:
                if self.docker_client:
                    volumes = self.docker_client.volumes.list(
                        filters={"name": self.volume_name}
                    )
                    for v in volumes:
                        v.remove(force=True)
                        logger.info(event=f"Removed test volume {v.name}")
            except Exception as e:
                logger.warning(
                    event=f"Failed to remove test volume {self.volume_name}: {e}"
                )
        else:
            self.data_dir = os.path.join(os.getcwd(), "neo4j-data")
            # Ensure the directory exists, but do not remove or chmod it
            if not os.path.isdir(self.data_dir):
                try:
                    os.makedirs(self.data_dir, exist_ok=True)
                except Exception as e:
                    logger.warning(
                        event=f"Could not create dev data directory {self.data_dir}: {e}"
                    )

        # Always use NEO4J_PORT if set, fallback to 7687 (default Bolt port)
        uri_env = os.environ.get("NEO4J_URI")
        if uri_env:
            self.neo4j_uri = uri_env
        else:
            port = os.environ.get("NEO4J_PORT")
            if not port:
                raise ValueError(
                    "NEO4J_PORT environment variable is required when NEO4J_URI is not set"
                )
            self.neo4j_uri = f"bolt://localhost:{port}"
        if self.debug:
            print(
                f"[DEBUG][Neo4jConfig] uri={self.neo4j_uri}, NEO4J_PORT={os.environ.get('NEO4J_PORT')}, NEO4J_URI={uri_env}"
            )
        self.neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_password = (
            os.getenv("NEO4J_PASSWORD") or self.generate_random_password()
        )

        # Readiness timeout configurable via env
        self.readiness_timeout = int(os.getenv("NEO4J_READY_TIMEOUT", "30"))

        try:
            self.docker_client = docker.from_env()
        except Exception as e:
            logger.warning(event=f"Could not connect to Docker daemon: {e}")

    def _determine_container_name(self) -> str:
        """Determine container name based on environment.

        Returns:
            str: Container name - unique for test/CI environments, fixed for dev
        """
        # In test/CI environments, use a unique name to avoid conflicts
        if (
            os.environ.get("PYTEST_CURRENT_TEST") is not None
            or os.environ.get("CI") == "1"
            or os.environ.get("RUN_DOCKER_CONFLICT_TESTS") == "1"
        ):
            return os.getenv(
                "NEO4J_CONTAINER_NAME",
                f"azure-tenant-grapher-neo4j-{uuid.uuid4().hex[:8]}",
            )
        else:
            # In dev mode, use the fixed name from docker-compose.yml
            return os.getenv("NEO4J_CONTAINER_NAME", "azure-tenant-grapher-neo4j")

    def is_docker_available(self) -> bool:
        """Check if Docker is available and running."""
        try:
            if self.docker_client:
                self.docker_client.ping()  # type: ignore[misc]
                return True
        except Exception as e:
            logger.exception(event=f"Docker is not available: {e}")
            logger.exception(
                event="Please ensure Docker Desktop is installed and running."
            )
            logger.exception(
                event="You can download Docker Desktop from: https://www.docker.com/products/docker-desktop"
            )
        return False

    def is_compose_available(self) -> bool:
        """Check if docker-compose is available."""
        try:
            result = subprocess.run(  # nosec B603
                ["docker-compose", "--version"],
                capture_output=True,
                text=True,
                check=True,
            )
            logger.info(event=f"Docker Compose available: {result.stdout.strip()}")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            try:
                # Try docker compose (newer syntax)
                result = subprocess.run(  # nosec B603
                    ["docker", "compose", "version"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                logger.info(event=f"Docker Compose available: {result.stdout.strip()}")
                return True
            except (subprocess.CalledProcessError, FileNotFoundError):
                logger.exception(event="Docker Compose is not available")
                return False

    def get_compose_command(self) -> list[str]:
        """Get the appropriate docker compose command."""
        try:
            subprocess.run(  # nosec B603
                ["docker-compose", "--version"], capture_output=True, check=True
            )
            return ["docker-compose"]
        except (subprocess.CalledProcessError, FileNotFoundError):
            return ["docker", "compose"]

    def is_neo4j_container_running(self) -> bool:
        """Check if Neo4j container is running."""
        if not self.docker_client:
            logger.debug(
                event="Docker client not available when checking container status"
            )
            return False

        try:
            logger.debug(
                event=f"Checking for containers with name: {self.container_name}"
            )
            containers = self.docker_client.containers.list(  # type: ignore[misc]
                filters={"name": self.container_name}
            )
            logger.debug(
                event=f"Found {len(containers)} containers with name '{self.container_name}': {[c.status for c in containers]}"
            )
            if len(containers) > 0:
                logger.debug(event=f"First container status: {containers[0].status}")
            return len(containers) > 0 and containers[0].status == "running"  # type: ignore[misc]
        except Exception as e:
            logger.exception(event=f"Error checking container status: {e}")
            return False

    def start_neo4j_container(self) -> bool:
        """Start Neo4j container using docker-compose, robustly handling name conflicts and unhealthy containers."""
        # self._print_env_block("START_CONTAINER")  # Removed per instructions
        logger.info(
            event=f"Attempting to start Neo4j container with name: {self.container_name}"
        )
        if not self.is_docker_available():
            logger.exception(event="Docker is not available")
            return False

        if not self.is_compose_available():
            logger.exception(event="Docker Compose is not available")
            return False

        # Robustly handle container name conflicts and unhealthy containers
        if self.docker_client:
            try:
                containers = self.docker_client.containers.list(
                    all=True, filters={"name": self.container_name}
                )
                logger.info(
                    event=f"Found {len(containers)} containers with name '{self.container_name}'"
                )
                for c in containers:
                    # Log container status and health (if available)
                    health_status = None
                    try:
                        health_status = (
                            c.attrs.get("State", {}).get("Health", {}).get("Status")
                        )
                    except Exception as e:
                        logger.warning(
                            event=f"Could not retrieve health status for container {c.name}: {e}"
                        )
                    logger.info(
                        event=f"Container {c.name} status: {c.status}, health: {health_status}"
                    )

                    if c.status == "running":
                        # Accept running container regardless of health status; rely on Bolt readiness check
                        logger.info(
                            event=f"Container {c.name} is running (health: {health_status}), will reuse."
                        )
                        return True
                    else:
                        logger.info(
                            event=f"Removing container {c.name} (status: {c.status}) to avoid name conflict."
                        )
                        try:
                            c.remove(force=True)
                            logger.info(event=f"Removed container {c.name}")
                        except Exception as e:
                            logger.warning(
                                event=f"Failed to remove container {c.name}: {e}"
                            )
            except Exception as e:
                logger.warning(
                    event=f"Error listing/removing containers for name conflict: {e}"
                )

        try:
            # Remove stale host data directory before starting container, but only in test/CI
            host_data_dir = os.path.join(os.getcwd(), "neo4j-data")
            if should_remove_neo4j_data() and os.path.isdir(host_data_dir):
                logger.info(
                    event=f"Removing stale host data directory {host_data_dir} (test/CI only)"
                )
                shutil.rmtree(host_data_dir, ignore_errors=True)
            # Always set NEO4J_DATA_VOLUME in the environment for compose
            env = os.environ.copy()
            env["NEO4J_DATA_VOLUME"] = self.volume_name
            env["NEO4J_AUTH"] = f"{self.neo4j_user}/{self.neo4j_password}"
            env["NEO4J_PASSWORD"] = self.neo4j_password
            compose_cmd = self.get_compose_command()
            logger.info(event="Starting Neo4j container...")

            # Start the container
            if self.debug:
                print(
                    f"[CONTAINER MANAGER DEBUG][compose env] NEO4J_AUTH=***REDACTED***"
                )
                print(
                    f"[CONTAINER MANAGER DEBUG][compose env] NEO4J_PASSWORD=***REDACTED***"
                )
                print(
                    f"[CONTAINER MANAGER DEBUG][compose env] NEO4J_CONTAINER_NAME={self.container_name}"
                )
                print(
                    f"[CONTAINER MANAGER DEBUG][compose env] NEO4J_DATA_VOLUME={self.volume_name}"
                )
            # Compose service name is always "neo4j", but container name is unique
            result = subprocess.run(  # nosec B603
                [*compose_cmd, "-f", self.compose_file, "up", "-d", "neo4j"],
                capture_output=True,
                text=True,
                check=True,
                env=env,
            )

            logger.info(event="Neo4j container started successfully")
            logger.debug(event=f"Docker compose output: {result.stdout}")

            return True

        except subprocess.CalledProcessError as e:
            logger.exception(event=f"Failed to start Neo4j container: {e}")
            logger.exception(event=f"Error output: {e.stderr}")
            return False

    def wait_for_neo4j_ready(self, timeout: Optional[int] = None) -> bool:
        """
        Wait for Neo4j to be ready to accept connections.

        Args:
            timeout: Maximum time to wait in seconds (overrides env/instance default)

        Returns:
            True if Neo4j is ready, False if timeout
        """
        if timeout is None:
            timeout = self.readiness_timeout
        logger.info(event="Waiting for Neo4j to be ready...")
        start_time = time.time()
        last_print = start_time

        while time.time() - start_time < timeout:
            try:
                if self.debug:
                    print(
                        f"[DEBUG][Neo4jConnection] Connecting to {self.neo4j_uri} as {self.neo4j_user}"
                    )
                driver = GraphDatabase.driver(
                    self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password)
                )

                with driver.session() as session:
                    result = session.run("RETURN 1 as test")
                    record = result.single()
                    if record and record["test"] == 1:
                        driver.close()
                        logger.info(event="Neo4j is ready!")
                        return True

            except ServiceUnavailable:
                logger.debug(event="Neo4j not ready yet, waiting...")
                now = time.time()
                if now - last_print > 5:
                    logger.info(
                        event="Still waiting for Neo4j...",
                        wait_state="wait_for_neo4j_ready",
                    )
                    last_print = now
                time.sleep(2)
            except Exception as e:
                logger.debug(event=f"Connection attempt failed: {e}")
                logger.warning(
                    event="Error while waiting for Neo4j",
                    error=str(e),
                    wait_state="wait_for_neo4j_ready",
                )
                time.sleep(2)

        logger.error(event=f"Neo4j did not become ready within {timeout} seconds")
        logger.error(
            event="Neo4j did not become ready within timeout",
            timeout=timeout,
            wait_state="wait_for_neo4j_ready",
        )
        return False

    def stop_neo4j_container(self) -> bool:
        """Stop Neo4j container."""
        # self._print_env_block("STOP_CONTAINER")  # Removed per instructions
        if not self.is_compose_available():
            logger.exception(event="Docker Compose is not available")
            return False

        try:
            compose_cmd = self.get_compose_command()
            logger.info(event="Stopping Neo4j container...")

            subprocess.run(  # nosec B603
                [*compose_cmd, "-f", self.compose_file, "stop", "neo4j"],
                capture_output=True,
                text=True,
                check=True,
            )

            logger.info(event="Neo4j container stopped successfully")
            return True

        except subprocess.CalledProcessError as e:
            logger.exception(f"Failed to stop Neo4j container: {e}")
            return False

    def get_container_logs(self, lines: int = 50) -> Optional[str]:
        """Get recent logs from Neo4j container."""
        if not self.is_compose_available():
            return None

        try:
            compose_cmd = self.get_compose_command()
            result = subprocess.run(  # nosec B603
                [
                    *compose_cmd,
                    "-f",
                    self.compose_file,
                    "logs",
                    "--tail",
                    str(lines),
                    "neo4j",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.exception(event=f"Failed to get container logs: {e}")
            return None

    def is_neo4j_reachable(self, timeout: int = 5) -> bool:
        """
        Check if Neo4j is already reachable at the configured URI.

        Args:
            timeout: Maximum time to wait for connection attempt

        Returns:
            True if Neo4j is reachable and accepts queries, False otherwise
        """
        try:
            driver = GraphDatabase.driver(
                self.neo4j_uri,
                auth=(self.neo4j_user, self.neo4j_password),
                connection_timeout=timeout,
            )

            with driver.session() as session:
                result = session.run("RETURN 1 as test")
                record = result.single()
                if record and record["test"] == 1:
                    driver.close()
                    logger.info(event="Neo4j is already reachable", uri=self.neo4j_uri)
                    return True

            driver.close()
            return False
        except Exception as e:
            logger.debug(
                event="Neo4j not reachable yet", uri=self.neo4j_uri, error=str(e)
            )
            return False

    def setup_neo4j(self, debug: bool = False) -> bool:
        """
        Complete Neo4j setup: ensure Neo4j is reachable.

        If Neo4j is already reachable at the configured URI, returns immediately.
        Otherwise, attempts to start a container and wait for readiness.

        This allows the manager to work in environments where Neo4j is provided
        externally (e.g., CI service containers) or needs to be started locally.

        Returns:
            True if Neo4j is reachable, False otherwise
        """
        logger.info(event="Setting up Neo4j...")

        # Check if Neo4j is already reachable
        if self.is_neo4j_reachable():
            logger.info(
                event="Neo4j is already running and reachable, skipping container startup",
                uri=self.neo4j_uri,
            )
            return True

        logger.info(
            event="Neo4j not reachable, attempting to start container",
            uri=self.neo4j_uri,
        )

        # Start the container
        if not self.start_neo4j_container():
            return False

        # Wait for it to be ready
        if not self.wait_for_neo4j_ready():
            logger.exception(
                event="Neo4j setup failed - container did not become ready"
            )
            logs = self.get_container_logs()
            if logs:
                logger.exception(event=f"Container logs:\n{logs}")
            return False

        logger.info(event="Neo4j setup completed successfully!")
        return True

    def backup_neo4j_database(self, backup_path: str) -> bool:
        """
        Backup the Neo4j database using neo4j-admin dump inside the container.
        This requires stopping the database temporarily.

        Args:
            backup_path: Local path to save the backup file.

        Returns:
            True if backup succeeded, False otherwise.
        """
        logger.info(event=f"Starting Neo4j backup to {backup_path}")
        if not self.is_neo4j_container_running():
            logger.error(event="Neo4j container is not running. Cannot perform backup.")
            return False

        # Find the container
        try:
            if not self.docker_client:
                logger.error(event="Docker client is not available")
                return False

            containers = self.docker_client.containers.list(
                filters={"name": self.container_name}
            )
            if not containers:
                logger.error(event="Neo4j container not found")
                return False

            container = containers[0]
        except Exception as e:
            logger.error(event=f"Could not find Neo4j container: {e}")
            return False

        # Run neo4j-admin dump inside the container
        try:
            # --to-path expects a directory, it will create neo4j.dump inside that directory
            backup_dir_in_container = "/data/backup"
            backup_file_in_container = "/data/backup/neo4j.dump"

            # Create backup directory in container
            exit_code, output = container.exec_run(
                f"mkdir -p {backup_dir_in_container}"
            )
            if exit_code != 0:
                logger.error(
                    event=f"Failed to create backup directory: {output.decode()}"
                )
                return False

            logger.info(event="Stopping Neo4j database for backup...")
            # Stop the Neo4j database (not the container)
            exit_code, output = container.exec_run("neo4j stop", user="neo4j")
            if exit_code != 0:
                logger.warning(
                    event=f"Failed to stop Neo4j service (this might be okay): {output.decode()}"
                )

            # Give it a moment to stop
            time.sleep(2)

            # Run the dump command
            exit_code, output = container.exec_run(
                f"neo4j-admin database dump neo4j --to-path={backup_dir_in_container} --overwrite-destination=true",
                user="neo4j",
            )

            # Restart Neo4j database
            logger.info(event="Restarting Neo4j database...")
            restart_exit_code, restart_output = container.exec_run(
                "neo4j start", user="neo4j"
            )
            if restart_exit_code != 0:
                logger.warning(
                    event=f"Failed to restart Neo4j service: {restart_output.decode()}"
                )

            if exit_code != 0:
                logger.error(event=f"neo4j-admin dump failed: {output.decode()}")
                return False

            # Copy the backup file from the container to the host
            bits, _ = container.get_archive(backup_file_in_container)
            with open(backup_path, "wb") as f:
                for chunk in bits:
                    f.write(chunk)
            logger.info(event=f"Backup completed and saved to {backup_path}")
            return True
        except Exception as e:
            logger.error(event=f"Backup failed: {e}")
            return False

    def restore_neo4j_database(self, backup_path: str) -> bool:
        """
        Restore the Neo4j database from a backup file using neo4j-admin load.
        This requires stopping the database temporarily.

        Args:
            backup_path: Local path to the backup file to restore from.

        Returns:
            True if restore succeeded, False otherwise.
        """
        logger.info(event=f"Starting Neo4j restore from {backup_path}")

        # Check if backup file exists
        if not os.path.exists(backup_path):
            logger.error(event=f"Backup file not found: {backup_path}")
            return False

        if not self.is_neo4j_container_running():
            logger.error(
                event="Neo4j container is not running. Cannot perform restore."
            )
            return False

        # Find the container
        try:
            if not self.docker_client:
                logger.error(event="Docker client is not available")
                return False

            containers = self.docker_client.containers.list(
                filters={"name": self.container_name}
            )
            if not containers:
                logger.error(event="Neo4j container not found")
                return False

            container = containers[0]
        except Exception as e:
            logger.error(event=f"Could not find Neo4j container: {e}")
            return False

        # Copy backup file to container
        try:
            # Create restore directory in container
            exit_code, output = container.exec_run("mkdir -p /data/restore")
            if exit_code != 0:
                logger.error(
                    event=f"Failed to create restore directory: {output.decode()}"
                )
                return False

            # Copy the backup file to the container
            # We need to create a tar archive containing the backup file
            import io
            import tarfile

            tar_stream = io.BytesIO()
            with tarfile.open(fileobj=tar_stream, mode="w") as tar:
                tar.add(backup_path, arcname="neo4j.dump")
            tar_stream.seek(0)

            container.put_archive("/data/restore", tar_stream.read())

            logger.info(event="Stopping Neo4j database for restore...")
            # Stop the Neo4j database (not the container)
            exit_code, output = container.exec_run("neo4j stop", user="neo4j")
            if exit_code != 0:
                logger.warning(
                    event=f"Failed to stop Neo4j service (this might be okay): {output.decode()}"
                )

            # Give it a moment to stop
            time.sleep(2)

            # Run the load command
            logger.info(event="Loading database from backup...")
            exit_code, output = container.exec_run(
                "neo4j-admin database load neo4j --from-path=/data/restore --overwrite-destination=true",
                user="neo4j",
            )

            # Restart Neo4j database
            logger.info(event="Restarting Neo4j database...")
            restart_exit_code, restart_output = container.exec_run(
                "neo4j start", user="neo4j"
            )
            if restart_exit_code != 0:
                logger.warning(
                    event=f"Failed to restart Neo4j service: {restart_output.decode()}"
                )

            if exit_code != 0:
                logger.error(event=f"neo4j-admin load failed: {output.decode()}")
                return False

            logger.info(event=f"Restore completed successfully from {backup_path}")
            return True
        except Exception as e:
            logger.error(event=f"Restore failed: {e}")
            return False

    def cleanup(self):
        """
        Cleanup Neo4j container and volume for this test run.
        Ensures removal even if container is stopped or exited.
        """
        # self._print_env_block("CLEANUP")  # Removed per instructions
        if not self.docker_client:
            return
        try:
            containers = self.docker_client.containers.list(
                all=True, filters={"name": self.container_name}
            )
            for c in containers:
                try:
                    if self.debug:
                        print(
                            f"[CONTAINER MANAGER CLEANUP] Removing container: {c.name} (status: {c.status})"
                        )
                    c.remove(force=True)
                    logger.info(event=f"Removed container {c.name}")
                except Exception as e:
                    logger.warning(event=f"Failed to remove container {c.name}: {e}")
        except Exception as e:
            logger.warning(event=f"Error listing containers for cleanup: {e}")

        # Remove volume
        try:
            volumes = self.docker_client.volumes.list(
                filters={"name": self.volume_name}
            )
            for v in volumes:
                try:
                    if self.debug:
                        print(f"[CONTAINER MANAGER CLEANUP] Removing volume: {v.name}")
                    v.remove(force=True)
                    logger.info(event=f"Removed volume {v.name}")
                except Exception as e:
                    logger.warning(event=f"Failed to remove volume {v.name}: {e}")
            # Only remove host data dir in dev if not using named volume
            if self.data_dir and os.path.isdir(self.data_dir):
                try:
                    shutil.rmtree(self.data_dir, ignore_errors=True)
                    logger.info(event=f"Removed host data directory {self.data_dir}")
                except Exception as e:
                    logger.warning(
                        event=f"Failed to remove host data directory {self.data_dir}: {e}"
                    )
        except Exception as e:
            logger.warning(event=f"Error listing volumes for cleanup: {e}")

    @staticmethod
    def generate_random_password(length: int = 16) -> str:
        """Generate a random password for Neo4j."""
        chars = string.ascii_letters + string.digits
        return "".join(random.SystemRandom().choice(chars) for _ in range(length))
