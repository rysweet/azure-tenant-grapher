"""Tests for layer management CLI commands (Issue #482 - Phase 3).

Test Coverage:
- Help text for all layer commands
- Command invocation with various options
- Backward compatibility with cli.py
- Error handling and validation
- Handler delegation

Target: 80% coverage
"""

from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from src.commands.layer_cmd import (
    layer,
    layer_active,
    layer_archive,
    layer_copy,
    layer_create,
    layer_delete,
    layer_diff,
    layer_list,
    layer_refresh_stats,
    layer_restore,
    layer_show,
    layer_validate,
)


class TestLayerGroup:
    """Test suite for layer command group."""

    @pytest.fixture
    def runner(self):
        """Click CLI test runner."""
        return CliRunner()

    def test_layer_group_help(self, runner):
        """Test layer group help text displays correctly."""
        result = runner.invoke(layer, ["--help"])

        assert result.exit_code == 0
        assert "Layer management commands" in result.output
        assert "list" in result.output
        assert "show" in result.output
        assert "create" in result.output


class TestLayerListCommand:
    """Test suite for layer list CLI command."""

    @pytest.fixture
    def runner(self):
        """Click CLI test runner."""
        return CliRunner()

    def test_layer_list_help(self, runner):
        """Test layer list help text displays correctly."""
        result = runner.invoke(layer_list, ["--help"])

        assert result.exit_code == 0
        assert "List all layers" in result.output
        assert "--tenant-id" in result.output
        assert "--format" in result.output

    @patch("src.commands.layer_cmd.layer_list_command_handler")
    def test_layer_list_basic(self, mock_handler, runner):
        """Test basic layer list invocation."""
        mock_handler.return_value = AsyncMock()

        runner.invoke(
            layer_list, [], obj={"debug": False}, catch_exceptions=False
        )

        # Command should complete
        assert mock_handler.called
        call_args = mock_handler.call_args[1]
        assert call_args["tenant_id"] is None
        assert call_args["include_inactive"] is True
        assert call_args["format_type"] == "table"
        assert call_args["debug"] is False

    @patch("src.commands.layer_cmd.layer_list_command_handler")
    def test_layer_list_with_filters(self, mock_handler, runner):
        """Test layer list with filtering options."""
        mock_handler.return_value = AsyncMock()

        runner.invoke(
            layer_list,
            [
                "--tenant-id",
                "test-tenant",
                "--type",
                "baseline",
                "--sort-by",
                "name",
                "--ascending",
                "--format",
                "json",
            ],
            obj={"debug": True},
            catch_exceptions=False,
        )

        assert mock_handler.called
        call_args = mock_handler.call_args[1]
        assert call_args["tenant_id"] == "test-tenant"
        assert call_args["layer_type"] == "baseline"
        assert call_args["sort_by"] == "name"
        assert call_args["ascending"] is True
        assert call_args["format_type"] == "json"


class TestLayerShowCommand:
    """Test suite for layer show CLI command."""

    @pytest.fixture
    def runner(self):
        """Click CLI test runner."""
        return CliRunner()

    def test_layer_show_help(self, runner):
        """Test layer show help text displays correctly."""
        result = runner.invoke(layer_show, ["--help"])

        assert result.exit_code == 0
        assert "Show detailed information" in result.output
        assert "--format" in result.output
        assert "--show-stats" in result.output

    @patch("src.commands.layer_cmd.layer_show_command_handler")
    def test_layer_show_basic(self, mock_handler, runner):
        """Test basic layer show invocation."""
        mock_handler.return_value = AsyncMock()

        runner.invoke(
            layer_show, ["test-layer"], obj={"debug": False}, catch_exceptions=False
        )

        assert mock_handler.called
        call_args = mock_handler.call_args[1]
        assert call_args["layer_id"] == "test-layer"
        assert call_args["format_type"] == "text"
        assert call_args["show_stats"] is False


class TestLayerActiveCommand:
    """Test suite for layer active CLI command."""

    @pytest.fixture
    def runner(self):
        """Click CLI test runner."""
        return CliRunner()

    def test_layer_active_help(self, runner):
        """Test layer active help text displays correctly."""
        result = runner.invoke(layer_active, ["--help"])

        assert result.exit_code == 0
        assert "Show or set the active layer" in result.output

    @patch("src.commands.layer_cmd.layer_active_command_handler")
    def test_layer_active_show(self, mock_handler, runner):
        """Test showing current active layer."""
        mock_handler.return_value = AsyncMock()

        runner.invoke(
            layer_active, [], obj={"debug": False}, catch_exceptions=False
        )

        assert mock_handler.called
        call_args = mock_handler.call_args[1]
        assert call_args["layer_id"] is None

    @patch("src.commands.layer_cmd.layer_active_command_handler")
    def test_layer_active_set(self, mock_handler, runner):
        """Test setting active layer."""
        mock_handler.return_value = AsyncMock()

        runner.invoke(
            layer_active,
            ["test-layer"],
            obj={"debug": False},
            catch_exceptions=False,
        )

        assert mock_handler.called
        call_args = mock_handler.call_args[1]
        assert call_args["layer_id"] == "test-layer"


class TestLayerCreateCommand:
    """Test suite for layer create CLI command."""

    @pytest.fixture
    def runner(self):
        """Click CLI test runner."""
        return CliRunner()

    def test_layer_create_help(self, runner):
        """Test layer create help text displays correctly."""
        result = runner.invoke(layer_create, ["--help"])

        assert result.exit_code == 0
        assert "Create a new empty layer" in result.output
        assert "--name" in result.output
        assert "--type" in result.output

    @patch("src.commands.layer_cmd.layer_create_command_handler")
    def test_layer_create_basic(self, mock_handler, runner):
        """Test basic layer create invocation."""
        mock_handler.return_value = AsyncMock()

        runner.invoke(
            layer_create,
            ["new-layer", "--yes"],
            obj={"debug": False},
            catch_exceptions=False,
        )

        assert mock_handler.called
        call_args = mock_handler.call_args[1]
        assert call_args["layer_id"] == "new-layer"
        assert call_args["layer_type"] == "experimental"
        assert call_args["yes"] is True

    @patch("src.commands.layer_cmd.layer_create_command_handler")
    def test_layer_create_with_options(self, mock_handler, runner):
        """Test layer create with various options."""
        mock_handler.return_value = AsyncMock()

        runner.invoke(
            layer_create,
            [
                "new-layer",
                "--name",
                "Test Layer",
                "--description",
                "Test description",
                "--type",
                "baseline",
                "--parent-layer",
                "parent-layer",
                "--tag",
                "test",
                "--tag",
                "prod",
                "--make-active",
                "--yes",
            ],
            obj={"debug": False},
            catch_exceptions=False,
        )

        assert mock_handler.called
        call_args = mock_handler.call_args[1]
        assert call_args["name"] == "Test Layer"
        assert call_args["description"] == "Test description"
        assert call_args["layer_type"] == "baseline"
        assert call_args["parent_layer"] == "parent-layer"
        assert call_args["tags"] == ["test", "prod"]
        assert call_args["make_active"] is True


class TestLayerCopyCommand:
    """Test suite for layer copy CLI command."""

    @pytest.fixture
    def runner(self):
        """Click CLI test runner."""
        return CliRunner()

    def test_layer_copy_help(self, runner):
        """Test layer copy help text displays correctly."""
        result = runner.invoke(layer_copy, ["--help"])

        assert result.exit_code == 0
        assert "Copy an entire layer" in result.output

    @patch("src.commands.layer_cmd.layer_copy_command_handler")
    def test_layer_copy_basic(self, mock_handler, runner):
        """Test basic layer copy invocation."""
        mock_handler.return_value = AsyncMock()

        runner.invoke(
            layer_copy,
            ["source-layer", "target-layer", "--yes"],
            obj={"debug": False},
            catch_exceptions=False,
        )

        assert mock_handler.called
        call_args = mock_handler.call_args[1]
        assert call_args["source"] == "source-layer"
        assert call_args["target"] == "target-layer"
        assert call_args["copy_metadata"] is True


class TestLayerDeleteCommand:
    """Test suite for layer delete CLI command."""

    @pytest.fixture
    def runner(self):
        """Click CLI test runner."""
        return CliRunner()

    def test_layer_delete_help(self, runner):
        """Test layer delete help text displays correctly."""
        result = runner.invoke(layer_delete, ["--help"])

        assert result.exit_code == 0
        assert "Delete a layer" in result.output
        assert "--force" in result.output

    @patch("src.commands.layer_cmd.layer_delete_command_handler")
    def test_layer_delete_basic(self, mock_handler, runner):
        """Test basic layer delete invocation."""
        mock_handler.return_value = AsyncMock()

        runner.invoke(
            layer_delete,
            ["test-layer", "--yes"],
            obj={"debug": False},
            catch_exceptions=False,
        )

        assert mock_handler.called
        call_args = mock_handler.call_args[1]
        assert call_args["layer_id"] == "test-layer"
        assert call_args["force"] is False
        assert call_args["yes"] is True

    @patch("src.commands.layer_cmd.layer_delete_command_handler")
    def test_layer_delete_with_archive(self, mock_handler, runner):
        """Test layer delete with archiving."""
        mock_handler.return_value = AsyncMock()

        runner.invoke(
            layer_delete,
            ["test-layer", "--archive", "/tmp/backup.json", "--force", "--yes"],
            obj={"debug": False},
            catch_exceptions=False,
        )

        assert mock_handler.called
        call_args = mock_handler.call_args[1]
        assert call_args["archive"] == "/tmp/backup.json"
        assert call_args["force"] is True


class TestLayerDiffCommand:
    """Test suite for layer diff CLI command."""

    @pytest.fixture
    def runner(self):
        """Click CLI test runner."""
        return CliRunner()

    def test_layer_diff_help(self, runner):
        """Test layer diff help text displays correctly."""
        result = runner.invoke(layer_diff, ["--help"])

        assert result.exit_code == 0
        assert "Compare two layers" in result.output
        assert "--detailed" in result.output

    @patch("src.commands.layer_cmd.layer_diff_command_handler")
    def test_layer_diff_basic(self, mock_handler, runner):
        """Test basic layer diff invocation."""
        mock_handler.return_value = AsyncMock()

        runner.invoke(
            layer_diff,
            ["layer-a", "layer-b"],
            obj={"debug": False},
            catch_exceptions=False,
        )

        assert mock_handler.called
        call_args = mock_handler.call_args[1]
        assert call_args["layer_a"] == "layer-a"
        assert call_args["layer_b"] == "layer-b"
        assert call_args["detailed"] is False
        assert call_args["properties"] is False


class TestLayerValidateCommand:
    """Test suite for layer validate CLI command."""

    @pytest.fixture
    def runner(self):
        """Click CLI test runner."""
        return CliRunner()

    def test_layer_validate_help(self, runner):
        """Test layer validate help text displays correctly."""
        result = runner.invoke(layer_validate, ["--help"])

        assert result.exit_code == 0
        assert "Validate layer integrity" in result.output
        assert "--fix" in result.output

    @patch("src.commands.layer_cmd.layer_validate_command_handler")
    def test_layer_validate_basic(self, mock_handler, runner):
        """Test basic layer validate invocation."""
        mock_handler.return_value = AsyncMock()

        runner.invoke(
            layer_validate,
            ["test-layer"],
            obj={"debug": False},
            catch_exceptions=False,
        )

        assert mock_handler.called
        call_args = mock_handler.call_args[1]
        assert call_args["layer_id"] == "test-layer"
        assert call_args["fix"] is False


class TestLayerRefreshStatsCommand:
    """Test suite for layer refresh-stats CLI command."""

    @pytest.fixture
    def runner(self):
        """Click CLI test runner."""
        return CliRunner()

    def test_layer_refresh_stats_help(self, runner):
        """Test layer refresh-stats help text displays correctly."""
        result = runner.invoke(layer_refresh_stats, ["--help"])

        assert result.exit_code == 0
        assert "Refresh layer metadata" in result.output

    @patch("src.commands.layer_cmd.layer_refresh_stats_command_handler")
    def test_layer_refresh_stats_basic(self, mock_handler, runner):
        """Test basic layer refresh-stats invocation."""
        mock_handler.return_value = AsyncMock()

        runner.invoke(
            layer_refresh_stats,
            ["test-layer"],
            obj={"debug": False},
            catch_exceptions=False,
        )

        assert mock_handler.called
        call_args = mock_handler.call_args[1]
        assert call_args["layer_id"] == "test-layer"


class TestLayerArchiveCommand:
    """Test suite for layer archive CLI command."""

    @pytest.fixture
    def runner(self):
        """Click CLI test runner."""
        return CliRunner()

    def test_layer_archive_help(self, runner):
        """Test layer archive help text displays correctly."""
        result = runner.invoke(layer_archive, ["--help"])

        assert result.exit_code == 0
        assert "Export layer to JSON" in result.output
        assert "--include-original" in result.output

    @patch("src.commands.layer_cmd.layer_archive_command_handler")
    def test_layer_archive_basic(self, mock_handler, runner):
        """Test basic layer archive invocation."""
        mock_handler.return_value = AsyncMock()

        runner.invoke(
            layer_archive,
            ["test-layer", "/tmp/archive.json", "--yes"],
            obj={"debug": False},
            catch_exceptions=False,
        )

        assert mock_handler.called
        call_args = mock_handler.call_args[1]
        assert call_args["layer_id"] == "test-layer"
        assert call_args["output_path"] == "/tmp/archive.json"
        assert call_args["include_original"] is False


class TestLayerRestoreCommand:
    """Test suite for layer restore CLI command."""

    @pytest.fixture
    def runner(self):
        """Click CLI test runner."""
        return CliRunner()

    def test_layer_restore_help(self, runner):
        """Test layer restore help text displays correctly."""
        result = runner.invoke(layer_restore, ["--help"])

        assert result.exit_code == 0
        assert "Restore layer from JSON" in result.output
        assert "--layer-id" in result.output

    @patch("src.commands.layer_cmd.layer_restore_command_handler")
    def test_layer_restore_basic(self, mock_handler, runner, tmp_path):
        """Test basic layer restore invocation."""
        mock_handler.return_value = AsyncMock()

        # Create a temporary archive file
        archive_file = tmp_path / "archive.json"
        archive_file.write_text("{}")

        runner.invoke(
            layer_restore,
            [str(archive_file), "--yes"],
            obj={"debug": False},
            catch_exceptions=False,
        )

        assert mock_handler.called
        call_args = mock_handler.call_args[1]
        assert call_args["archive_path"] == str(archive_file)
        assert call_args["layer_id"] is None
        assert call_args["make_active"] is False


class TestBackwardCompatibility:
    """Test suite for backward compatibility with cli.py."""

    @pytest.fixture
    def runner(self):
        """Click CLI test runner."""
        return CliRunner()

    @patch("src.commands.layer_cmd.layer_list_command_handler")
    def test_layer_group_works_as_subcommand(self, mock_handler, runner):
        """Test layer command group works when registered to main CLI."""
        mock_handler.return_value = AsyncMock()

        # Import and register layer group to test CLI
        from click import Group

        test_cli = Group()
        test_cli.add_command(layer)

        runner.invoke(
            test_cli,
            ["layer", "list"],
            obj={"debug": False},
            catch_exceptions=False,
        )

        assert mock_handler.called

    def test_all_commands_exported(self):
        """Test all commands are properly exported."""
        from src.commands import layer_cmd

        expected_exports = [
            "layer",
            "layer_list",
            "layer_show",
            "layer_active",
            "layer_create",
            "layer_copy",
            "layer_delete",
            "layer_diff",
            "layer_validate",
            "layer_refresh_stats",
            "layer_archive",
            "layer_restore",
        ]

        for export in expected_exports:
            assert hasattr(layer_cmd, export), f"Missing export: {export}"
            assert export in layer_cmd.__all__, f"Export not in __all__: {export}"
