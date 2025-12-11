"""Tests for database management CLI commands (Issue #482).

Test Coverage:
- Help text for all commands
- Successful backup/restore/wipe operations
- Error handling (missing container, file not found, etc.)
- Confirmation prompts
- Backward compatibility

Target: 80% coverage
"""

from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from src.commands.database import (
    backup,
    backup_db,
    container,
    restore,
    restore_db,
    wipe,
)


class TestBackupCommand:
    """Test suite for backup CLI command."""

    @pytest.fixture
    def runner(self):
        """Click CLI test runner."""
        return CliRunner()

    def test_backup_help(self, runner):
        """Test backup help text displays correctly."""
        result = runner.invoke(backup, ["--help"])

        assert result.exit_code == 0
        assert "Backup the Neo4j database" in result.output
        assert "--path" in result.output

    @patch("src.container_manager.Neo4jContainerManager")
    def test_backup_success(self, mock_container_manager_class, runner):
        """Test successful database backup."""
        # Mock container manager
        container_manager = Mock()
        container_manager.is_neo4j_container_running.return_value = True
        container_manager.backup_neo4j_database.return_value = True
        mock_container_manager_class.return_value = container_manager

        # Run command
        result = runner.invoke(backup, ["--path", "/tmp/test_backup.dump"])

        assert result.exit_code == 0
        assert "backed up successfully" in result.output
        container_manager.backup_neo4j_database.assert_called_once_with(
            "/tmp/test_backup.dump"
        )

    @patch("src.container_manager.Neo4jContainerManager")
    def test_backup_container_not_running(self, mock_container_manager_class, runner):
        """Test backup when container is not running."""
        # Mock container manager
        container_manager = Mock()
        container_manager.is_neo4j_container_running.return_value = False
        mock_container_manager_class.return_value = container_manager

        # Run command
        result = runner.invoke(backup, ["--path", "/tmp/test_backup.dump"])

        assert result.exit_code == 1
        assert "not running" in result.output

    @patch("src.container_manager.Neo4jContainerManager")
    def test_backup_failure(self, mock_container_manager_class, runner):
        """Test backup failure handling."""
        # Mock container manager
        container_manager = Mock()
        container_manager.is_neo4j_container_running.return_value = True
        container_manager.backup_neo4j_database.return_value = False
        mock_container_manager_class.return_value = container_manager

        # Run command
        result = runner.invoke(backup, ["--path", "/tmp/test_backup.dump"])

        assert result.exit_code == 1
        assert "failed" in result.output


class TestBackupDbCommand:
    """Test suite for backup-db CLI command (positional argument version)."""

    @pytest.fixture
    def runner(self):
        """Click CLI test runner."""
        return CliRunner()

    def test_backup_db_help(self, runner):
        """Test backup-db help text displays correctly."""
        result = runner.invoke(backup_db, ["--help"])

        assert result.exit_code == 0
        assert "Backup the Neo4j database" in result.output
        assert "BACKUP_PATH" in result.output

    @patch("src.container_manager.Neo4jContainerManager")
    def test_backup_db_success(self, mock_container_manager_class, runner):
        """Test successful database backup with positional argument."""
        # Mock container manager
        container_manager = Mock()
        container_manager.backup_neo4j_database.return_value = True
        mock_container_manager_class.return_value = container_manager

        # Run command
        result = runner.invoke(backup_db, ["/tmp/test_backup.dump"])

        assert result.exit_code == 0
        assert "backup completed" in result.output
        container_manager.backup_neo4j_database.assert_called_once_with(
            "/tmp/test_backup.dump"
        )

    @patch("src.container_manager.Neo4jContainerManager")
    def test_backup_db_failure(self, mock_container_manager_class, runner):
        """Test backup-db failure handling."""
        # Mock container manager
        container_manager = Mock()
        container_manager.backup_neo4j_database.return_value = False
        mock_container_manager_class.return_value = container_manager

        # Run command
        result = runner.invoke(backup_db, ["/tmp/test_backup.dump"])

        assert result.exit_code == 1
        assert "failed" in result.output


class TestRestoreCommand:
    """Test suite for restore CLI command."""

    @pytest.fixture
    def runner(self):
        """Click CLI test runner."""
        return CliRunner()

    def test_restore_help(self, runner):
        """Test restore help text displays correctly."""
        result = runner.invoke(restore, ["--help"])

        assert result.exit_code == 0
        assert "Restore the Neo4j database" in result.output
        assert "--path" in result.output

    @patch("src.container_manager.Neo4jContainerManager")
    @patch("src.commands.database.os.path.exists")
    def test_restore_success(self, mock_exists, mock_container_manager_class, runner):
        """Test successful database restore."""
        # Mock file exists
        mock_exists.return_value = True

        # Mock container manager
        container_manager = Mock()
        container_manager.is_neo4j_container_running.return_value = True
        container_manager.restore_neo4j_database.return_value = True
        mock_container_manager_class.return_value = container_manager

        # Run command with confirmation
        result = runner.invoke(
            restore, ["--path", "/tmp/test_backup.dump"], input="y\n"
        )

        assert result.exit_code == 0
        assert "restored successfully" in result.output
        container_manager.restore_neo4j_database.assert_called_once_with(
            "/tmp/test_backup.dump"
        )

    @patch("src.commands.database.os.path.exists")
    def test_restore_file_not_found(self, mock_exists, runner):
        """Test restore when backup file doesn't exist."""
        mock_exists.return_value = False

        # Run command
        result = runner.invoke(restore, ["--path", "/tmp/missing.dump"])

        assert result.exit_code == 1
        assert "not found" in result.output

    @patch("src.container_manager.Neo4jContainerManager")
    @patch("src.commands.database.os.path.exists")
    def test_restore_cancelled(self, mock_exists, mock_container_manager_class, runner):
        """Test restore cancellation."""
        mock_exists.return_value = True

        # Run command with 'n' for confirmation
        result = runner.invoke(
            restore, ["--path", "/tmp/test_backup.dump"], input="n\n"
        )

        assert result.exit_code == 0
        assert "cancelled" in result.output

    @patch("src.container_manager.Neo4jContainerManager")
    @patch("src.commands.database.os.path.exists")
    def test_restore_container_not_running(
        self, mock_exists, mock_container_manager_class, runner
    ):
        """Test restore when container is not running."""
        mock_exists.return_value = True

        # Mock container manager
        container_manager = Mock()
        container_manager.is_neo4j_container_running.return_value = False
        mock_container_manager_class.return_value = container_manager

        # Run command with confirmation
        result = runner.invoke(
            restore, ["--path", "/tmp/test_backup.dump"], input="y\n"
        )

        assert result.exit_code == 1
        assert "not running" in result.output

    @patch("src.container_manager.Neo4jContainerManager")
    @patch("src.commands.database.os.path.exists")
    def test_restore_failure(self, mock_exists, mock_container_manager_class, runner):
        """Test restore failure handling."""
        mock_exists.return_value = True

        # Mock container manager
        container_manager = Mock()
        container_manager.is_neo4j_container_running.return_value = True
        container_manager.restore_neo4j_database.return_value = False
        mock_container_manager_class.return_value = container_manager

        # Run command with confirmation
        result = runner.invoke(
            restore, ["--path", "/tmp/test_backup.dump"], input="y\n"
        )

        assert result.exit_code == 1
        assert "failed" in result.output


class TestRestoreDbAlias:
    """Test suite for restore-db alias."""

    @pytest.fixture
    def runner(self):
        """Click CLI test runner."""
        return CliRunner()

    def test_restore_db_is_alias(self):
        """Test that restore_db is the same as restore."""
        assert restore_db == restore


class TestWipeCommand:
    """Test suite for wipe CLI command."""

    @pytest.fixture
    def runner(self):
        """Click CLI test runner."""
        return CliRunner()

    def test_wipe_help(self, runner):
        """Test wipe help text displays correctly."""
        result = runner.invoke(wipe, ["--help"])

        assert result.exit_code == 0
        assert "Wipe all data" in result.output
        assert "--force" in result.output

    @patch("neo4j.GraphDatabase")
    @patch("src.commands.database.get_neo4j_config_from_env")
    def test_wipe_success_with_force(
        self, mock_get_config, mock_graph_database, runner
    ):
        """Test successful database wipe with --force flag."""
        # Mock configuration
        mock_get_config.return_value = ("bolt://localhost:7687", "neo4j", "password")

        # Mock GraphDatabase
        mock_driver = Mock()
        mock_session = Mock()
        mock_result = Mock()
        mock_record = Mock()
        mock_record.__getitem__ = Mock(return_value=0)
        mock_result.single.return_value = mock_record
        mock_session.run.return_value = mock_result
        mock_driver.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = Mock(return_value=None)
        mock_graph_database.driver.return_value = mock_driver

        # Run command with force flag
        result = runner.invoke(wipe, ["--force"])

        assert result.exit_code == 0
        assert "wiped successfully" in result.output
        mock_session.run.assert_any_call("MATCH (n) DETACH DELETE n")

    @patch("neo4j.GraphDatabase")
    @patch("src.commands.database.get_neo4j_config_from_env")
    def test_wipe_success_with_confirmation(
        self, mock_get_config, mock_graph_database, runner
    ):
        """Test successful database wipe with confirmation prompt."""
        # Mock configuration
        mock_get_config.return_value = ("bolt://localhost:7687", "neo4j", "password")

        # Mock GraphDatabase
        mock_driver = Mock()
        mock_session = Mock()
        mock_result = Mock()
        mock_record = Mock()
        mock_record.__getitem__ = Mock(return_value=0)
        mock_result.single.return_value = mock_record
        mock_session.run.return_value = mock_result
        mock_driver.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = Mock(return_value=None)
        mock_graph_database.driver.return_value = mock_driver

        # Run command with confirmation
        result = runner.invoke(wipe, input="y\n")

        assert result.exit_code == 0
        assert "wiped successfully" in result.output

    def test_wipe_cancelled(self, runner):
        """Test wipe cancellation."""
        # Run command with 'n' for confirmation
        result = runner.invoke(wipe, input="n\n")

        assert result.exit_code == 0
        assert "cancelled" in result.output

    @patch("neo4j.GraphDatabase")
    @patch("src.commands.database.get_neo4j_config_from_env")
    def test_wipe_incomplete(self, mock_get_config, mock_graph_database, runner):
        """Test wipe incomplete scenario."""
        # Mock configuration
        mock_get_config.return_value = ("bolt://localhost:7687", "neo4j", "password")

        # Mock GraphDatabase - return non-zero count
        mock_driver = Mock()
        mock_session = Mock()
        mock_result = Mock()
        mock_record = Mock()
        mock_record.__getitem__ = Mock(return_value=5)
        mock_result.single.return_value = mock_record
        mock_session.run.return_value = mock_result
        mock_driver.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = Mock(return_value=None)
        mock_graph_database.driver.return_value = mock_driver

        # Run command with force flag
        result = runner.invoke(wipe, ["--force"])

        assert result.exit_code == 0
        assert "incomplete" in result.output

    @patch("src.commands.database.get_neo4j_config_from_env")
    def test_wipe_connection_error(self, mock_get_config, runner):
        """Test wipe with connection error."""
        # Mock configuration to raise exception
        mock_get_config.side_effect = Exception("Connection failed")

        # Run command with force flag
        result = runner.invoke(wipe, ["--force"])

        assert result.exit_code == 1
        assert "Failed" in result.output


class TestContainerCommand:
    """Test suite for container CLI command."""

    @pytest.fixture
    def runner(self):
        """Click CLI test runner."""
        return CliRunner()

    def test_container_help(self, runner):
        """Test container help text displays correctly."""
        result = runner.invoke(container, ["--help"])

        assert result.exit_code == 0
        assert "Manage Neo4j container" in result.output

    def test_container_info_message(self, runner):
        """Test container command displays info message."""
        result = runner.invoke(container)

        assert result.exit_code == 0
        assert "handled automatically" in result.output
        assert "build" in result.output


class TestBackwardCompatibility:
    """Test suite for backward compatibility exports."""

    def test_backup_command_export(self):
        """Test backup_command backward compatibility export."""
        from src.commands.database import backup_command

        assert backup_command == backup

    def test_backup_db_command_export(self):
        """Test backup_db_command backward compatibility export."""
        from src.commands.database import backup_db_command

        assert backup_db_command == backup_db

    def test_restore_command_export(self):
        """Test restore_command backward compatibility export."""
        from src.commands.database import restore_command

        assert restore_command == restore

    def test_restore_db_command_export(self):
        """Test restore_db_command backward compatibility export."""
        from src.commands.database import restore_db_command

        assert restore_db_command == restore_db

    def test_wipe_command_export(self):
        """Test wipe_command backward compatibility export."""
        from src.commands.database import wipe_command

        assert wipe_command == wipe

    def test_container_command_export(self):
        """Test container_command backward compatibility export."""
        from src.commands.database import container_command

        assert container_command == container

    def test_all_exports(self):
        """Test __all__ exports are complete."""
        from src.commands.database import __all__

        expected_exports = [
            "backup",
            "backup_command",
            "backup_db",
            "backup_db_command",
            "container",
            "container_command",
            "restore",
            "restore_command",
            "restore_db",
            "restore_db_command",
            "wipe",
            "wipe_command",
        ]

        for export in expected_exports:
            assert export in __all__, f"{export} not in __all__"
