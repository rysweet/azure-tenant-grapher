import logging
import os

import docker

logger = logging.getLogger(__name__)
...


class Neo4jContainerManager:
    """Manages Neo4j Docker container lifecycle."""

    def __init__(
        self,
        compose_file: str = "docker-compose.yml",
        container_name: str = "azure-tenant-grapher-neo4j",
    ) -> None:
        """
        Initialize the container manager.

        Args:
            compose_file: Path to docker-compose.yml file
            container_name: Name of the Neo4j Docker container to manage
        """
        self.compose_file = compose_file
        self.container_name = container_name
        self.docker_client = None
        self.neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7688")
        self.neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_password = os.getenv("NEO4J_PASSWORD", "azure-grapher-2024")

        try:
            self.docker_client = docker.from_env()
        except Exception as e:
            logger.warning(f"Could not connect to Docker daemon: {e}")

    ...

    def is_neo4j_container_running(self) -> bool:
        """Check if Neo4j container is running."""
        if not self.docker_client:
            return False

        try:
            containers = self.docker_client.containers.list(
                filters={"name": self.container_name}
            )
            return len(containers) > 0 and containers[0].status == "running"
        except Exception as e:
            logger.exception(f"Error checking container status: {e}")
            return False

    ...

    def backup_neo4j_database(self, backup_path: str) -> bool:
        # Find the container
        try:
            if not self.docker_client:
                logger.error("Docker client is not available")
                return False

            containers = self.docker_client.containers.list(
                filters={"name": self.container_name}
            )
            if not containers:
                logger.error("Neo4j container not found")
                return False

            container = containers[0]
        except Exception as e:
            logger.error(f"Could not find Neo4j container: {e}")
            return False

        # Run neo4j-admin dump inside the container
        try:
            backup_dir_in_container = "/data/backup"
            backup_file_in_container = "/data/backup/neo4j.dump"

            # Create backup directory in container
            exit_code, output = container.exec_run(
                f"mkdir -p {backup_dir_in_container}"
            )
            if exit_code != 0:
                logger.error(f"Failed to create backup directory: {output.decode()}")
                return False

            logger.info("Stopping Neo4j database for backup...")
            exit_code, output = container.exec_run("neo4j stop", user="neo4j")
            if exit_code != 0:
                logger.warning(
                    f"Failed to stop Neo4j service (this might be okay): {output.decode()}"
                )

            # Give it a moment to stop
            import time

            time.sleep(2)

            # Run the dump command
            exit_code, output = container.exec_run(
                f"neo4j-admin database dump neo4j --to-path={backup_dir_in_container} --overwrite-destination=true",
                user="neo4j",
            )

            # Restart Neo4j database
            logger.info("Restarting Neo4j database...")
            restart_exit_code, restart_output = container.exec_run(
                "neo4j start", user="neo4j"
            )
            if restart_exit_code != 0:
                logger.warning(
                    f"Failed to restart Neo4j service: {restart_output.decode()}"
                )

            if exit_code != 0:
                logger.error(f"neo4j-admin dump failed: {output.decode()}")
                print(f"neo4j-admin dump failed: {output.decode()}")
                return False

            # Copy the backup file from the container to the host
            bits, _ = container.get_archive(backup_file_in_container)
            import io
            import tarfile

            file_bytes = b"".join(bits)
            with tarfile.open(fileobj=io.BytesIO(file_bytes)) as tar:
                member = tar.getmember("neo4j.dump")
                src_file = tar.extractfile(member)
                if src_file is None:
                    logger.error("Failed to extract neo4j.dump from container archive")
                    print("Failed to extract neo4j.dump from container archive")
                    return False
                with src_file, open(backup_path, "wb") as dst:
                    dst.write(src_file.read())
            logger.info(f"Backup completed and saved to {backup_path}")
            print(f"Backup completed and saved to {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            print(f"Backup failed: {e}")
            return False

    def restore_neo4j_database(self, backup_path: str) -> bool:
        # Find the container
        try:
            if not self.docker_client:
                logger.error("Docker client is not available")
                return False

            containers = self.docker_client.containers.list(
                filters={"name": self.container_name}
            )
            if not containers:
                logger.error("Neo4j container not found")
                return False

            container = containers[0]
        except Exception as e:
            logger.error(f"Could not find Neo4j container: {e}")
            print(f"Could not find Neo4j container: {e}")
            return False

        # Copy the backup file into the container
        try:
            backup_dir_in_container = "/data/backup"
            # (removed unused backup_file_in_container)

            import io
            import shutil
            import tarfile
            import tempfile

            temp_path = None
            tar_source = backup_path
            cleanup_temp = False
            try:
                # Detect if the backup file is a tar archive
                is_tar = False
                try:
                    with tarfile.open(backup_path, "r") as tar:
                        members = tar.getnames()
                        if "neo4j.dump" in members:
                            is_tar = True
                except tarfile.ReadError:
                    is_tar = False

                if is_tar:
                    # Extract neo4j.dump from the tar archive to a temp file
                    temp_dir = tempfile.gettempdir()
                    temp_path = os.path.join(temp_dir, "neo4j.dump")
                    with tarfile.open(backup_path, "r") as tar:
                        tar.extract("neo4j.dump", path=temp_dir)
                    tar_source = temp_path
                    cleanup_temp = True
                elif os.path.basename(backup_path) != "neo4j.dump":
                    temp_dir = tempfile.gettempdir()
                    temp_path = os.path.join(temp_dir, "neo4j.dump")
                    shutil.copy2(backup_path, temp_path)
                    tar_source = temp_path
                    cleanup_temp = True

                # Create backup directory in container
                exit_code, output = container.exec_run(
                    f"mkdir -p {backup_dir_in_container}"
                )
                if exit_code != 0:
                    logger.error(
                        f"Failed to create backup directory: {output.decode()}"
                    )
                    print(f"Failed to create backup directory: {output.decode()}")
                    return False

                tarstream = io.BytesIO()
                with tarfile.open(fileobj=tarstream, mode="w") as tar:
                    tar.add(tar_source, arcname="neo4j.dump")
                tarstream.seek(0)
                container.put_archive(backup_dir_in_container, tarstream.read())
            finally:
                if cleanup_temp and temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)
        except Exception as e:
            logger.error(f"Failed to copy backup file into container: {e}")
            print(f"Failed to copy backup file into container: {e}")
            return False

        # Run neo4j-admin load inside the container
        try:
            logger.info("Stopping Neo4j database for restore...")
            exit_code, output = container.exec_run("neo4j stop", user="neo4j")
            if exit_code != 0:
                logger.warning(
                    f"Failed to stop Neo4j service (this might be okay): {output.decode()}"
                )
                print(
                    f"Failed to stop Neo4j service (this might be okay): {output.decode()}"
                )

            import time

            time.sleep(2)

            # Run the load command
            exit_code, output = container.exec_run(
                f"neo4j-admin database load neo4j --from-path={backup_dir_in_container} --overwrite-destination=true",
                user="neo4j",
            )

            # Restart Neo4j database
            logger.info("Restarting Neo4j database...")
            restart_exit_code, restart_output = container.exec_run(
                "neo4j start", user="neo4j"
            )
            if restart_exit_code != 0:
                logger.warning(
                    f"Failed to restart Neo4j service: {restart_output.decode()}"
                )
                print(f"Failed to restart Neo4j service: {restart_output.decode()}")

            if exit_code != 0:
                logger.error(f"neo4j-admin load failed: {output.decode()}")
                print(f"neo4j-admin load failed: {output.decode()}")
                return False

            logger.info("Restore completed successfully.")
            print("Restore completed successfully.")
            return True
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            print(f"Restore failed: {e}")
            return False
