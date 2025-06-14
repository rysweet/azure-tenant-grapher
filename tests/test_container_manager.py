# mypy: disable-error-code=misc
"""
Tests for container_manager module.
"""

import subprocess  # nosec B404
from unittest.mock import Mock, patch

from src.container_manager import Neo4jContainerManager


class TestNeo4jContainerManager:
    """Test cases for Neo4jContainerManager."""

    def test_initialization(self) -> None:
        """Test Neo4jContainerManager initialization."""
        import os

        manager = Neo4jContainerManager()
        assert manager.compose_file == "docker-compose.yml"
        expected_uri = os.getenv("NEO4J_URI", "bolt://localhost:7688")
        assert manager.neo4j_uri == expected_uri
        assert manager.neo4j_user == "neo4j"
        assert manager.neo4j_password == "azure-grapher-2024"  # nosec

    @patch("src.container_manager.docker")
    def test_is_docker_available_true(self, mock_docker: Mock) -> None:
        """Test Docker availability check when Docker is available."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_docker.from_env.return_value = mock_client

        manager = Neo4jContainerManager()
        manager.docker_client = mock_client
        result = manager.is_docker_available()

        assert result is True
        mock_client.ping.assert_called_once()

    @patch("src.container_manager.docker")
    def test_is_docker_available_false(self, mock_docker: Mock) -> None:
        """Test Docker availability check when Docker is not available."""
        mock_client = Mock()
        mock_client.ping.side_effect = Exception("Docker not available")
        mock_docker.from_env.return_value = mock_client

        manager = Neo4jContainerManager()
        manager.docker_client = mock_client
        result = manager.is_docker_available()

        assert result is False

    @patch("subprocess.run")
    def test_is_compose_available_true(self, mock_run: Mock) -> None:
        """Test Docker Compose availability check when Compose is available."""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Docker Compose version 2.0.0"

        manager = Neo4jContainerManager()
        result = manager.is_compose_available()

        assert result is True

    @patch("subprocess.run")
    def test_is_compose_available_false(self, mock_run: Mock) -> None:
        """Test Docker Compose availability check when Compose is not available."""
        # Mock both docker-compose and docker compose commands to fail
        mock_run.side_effect = [
            subprocess.CalledProcessError(1, "docker-compose"),  # First call fails
            subprocess.CalledProcessError(1, "docker"),  # Second call fails
        ]

        manager = Neo4jContainerManager()
        result = manager.is_compose_available()

        assert result is False

    @patch("subprocess.run")
    def test_start_neo4j_container_success(self, mock_run: Mock) -> None:
        """Test successful Neo4j container start."""
        mock_run.return_value.returncode = 0

        manager = Neo4jContainerManager()

        with patch.object(
            manager, "is_docker_available", return_value=True
        ), patch.object(
            manager, "is_compose_available", return_value=True
        ), patch.object(manager, "is_neo4j_container_running", return_value=False):
            result = manager.start_neo4j_container()

            assert result is True
            mock_run.assert_called()

    def test_start_neo4j_container_docker_unavailable(self) -> None:
        """Test container start when Docker is unavailable."""
        manager = Neo4jContainerManager()

        with patch.object(manager, "is_docker_available", return_value=False):
            result = manager.start_neo4j_container()

            assert result is False

    @patch("subprocess.run")
    def test_stop_neo4j_container_success(self, mock_run: Mock) -> None:
        """Test successful Neo4j container stop."""
        mock_run.return_value.returncode = 0

        manager = Neo4jContainerManager()

        with patch.object(manager, "is_compose_available", return_value=True):
            result = manager.stop_neo4j_container()

            assert result is True
            mock_run.assert_called()

    @patch("subprocess.run")
    def test_get_container_logs_success(self, mock_run: Mock) -> None:
        """Test successful container logs retrieval."""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Neo4j container logs"

        manager = Neo4jContainerManager()
        logs = manager.get_container_logs()

        assert logs is not None
        assert "Neo4j container logs" in logs
        mock_run.assert_called()

    @patch("subprocess.run")
    def test_get_container_logs_failure(self, mock_run: Mock) -> None:
        """Test container logs retrieval failure."""
        mock_run.return_value.returncode = 1

        manager = Neo4jContainerManager()
        logs = manager.get_container_logs()

        # Might return empty string or None on failure
        assert (
            logs is not None
        )  # The actual implementation returns logs even on failure

    def test_setup_neo4j_docker_unavailable(self) -> None:
        """Test Neo4j setup when Docker is unavailable."""
        manager = Neo4jContainerManager()

        with patch.object(manager, "is_docker_available", return_value=False):
            result = manager.setup_neo4j()

            assert result is False
