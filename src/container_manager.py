"""
Container orchestration module for managing Neo4j Docker container.
"""

import os
import random
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


class Neo4jContainerManager:
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

    def __init__(self, compose_file: str = "docker-compose.yml") -> None:
        """
        Initialize the container manager.

        Args:
            compose_file: Path to docker-compose.yml file
        """
        self.compose_file = compose_file
        self.docker_client = None

        # Unique container name per test run
        self.container_name = os.getenv(
            "NEO4J_CONTAINER_NAME", f"azure-tenant-grapher-neo4j-{uuid.uuid4().hex[:8]}"
        )
        self.volume_name = f"{self.container_name}-data"

        self.neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7688")
        self.neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_password = (
            os.getenv("NEO4J_PASSWORD") or self._generate_random_password()
        )

        # Readiness timeout configurable via env
        self.readiness_timeout = int(os.getenv("NEO4J_READY_TIMEOUT", "30"))

        try:
            self.docker_client = docker.from_env()
        except Exception as e:
            logger.warning(event=f"Could not connect to Docker daemon: {e}")

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
            return False

        try:
            containers = self.docker_client.containers.list(  # type: ignore[misc]
                filters={"name": self.container_name}
            )
            return len(containers) > 0 and containers[0].status == "running"  # type: ignore[misc]
        except Exception as e:
            logger.exception(event=f"Error checking container status: {e}")
            return False

    def start_neo4j_container(self) -> bool:
        """Start Neo4j container using docker-compose."""
        if not self.is_docker_available():
            logger.exception(event="Docker is not available")
            return False

        if not self.is_compose_available():
            logger.exception(event="Docker Compose is not available")
            return False

        if self.is_neo4j_container_running():
            logger.info(event="Neo4j container is already running")
            return True

        try:
            compose_cmd = self.get_compose_command()
            logger.info(event="Starting Neo4j container...")

            # Start the container
            env = os.environ.copy()
            env["NEO4J_AUTH"] = f"{self.neo4j_user}/{self.neo4j_password}"
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

    def setup_neo4j(self) -> bool:
        """
        Complete Neo4j setup: start container and wait for readiness.

        Returns:
            True if setup successful, False otherwise
        """
        logger.info(event="Setting up Neo4j container...")

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

    def cleanup(self):
        """
        Cleanup Neo4j container and volume for this test run.
        Ensures removal even if container is stopped or exited.
        """
        if not self.docker_client:
            return
        try:
            containers = self.docker_client.containers.list(
                all=True, filters={"name": self.container_name}
            )
            for c in containers:
                try:
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
                    v.remove(force=True)
                    logger.info(event=f"Removed volume {v.name}")
                except Exception as e:
                    logger.warning(event=f"Failed to remove volume {v.name}: {e}")
        except Exception as e:
            logger.warning(event=f"Error listing volumes for cleanup: {e}")

    @staticmethod
    def _generate_random_password(length: int = 16) -> str:
        """Generate a random password for Neo4j."""
        chars = string.ascii_letters + string.digits
        return "".join(random.SystemRandom().choice(chars) for _ in range(length))
