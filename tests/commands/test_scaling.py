"""Tests for scaling operations CLI commands (Issue #427, Issue #482 - Phase 2).

Test Coverage:
- Help text for all commands
- Command groups (scale-up, scale-down)
- Individual commands (scale-clean, scale-validate, scale-stats)
- Successful operations with mocked handlers
- Error handling and validation
- Backward compatibility

Target: 80% coverage
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from click.testing import CliRunner

from src.commands.scaling import (
    scale_clean,
    scale_down,
    scale_down_algorithm,
    scale_down_pattern,
    scale_stats,
    scale_up,
    scale_up_scenario,
    scale_up_template,
    scale_validate,
)


class TestScaleUpCommands:
    """Test suite for scale-up CLI commands."""

    @pytest.fixture
    def runner(self):
        """Click CLI test runner."""
        return CliRunner()

    def test_scale_up_group_help(self, runner):
        """Test scale-up group help text displays correctly."""
        result = runner.invoke(scale_up, ["--help"])

        assert result.exit_code == 0
        assert "Scale up operations" in result.output
        assert "add synthetic nodes" in result.output

    def test_scale_up_template_help(self, runner):
        """Test scale-up template help text displays correctly."""
        result = runner.invoke(scale_up, ["template", "--help"])

        assert result.exit_code == 0
        assert "template-based generation" in result.output
        assert "--template-file" in result.output
        assert "--scale-factor" in result.output

    @patch("src.commands.scaling.ensure_neo4j_running")
    @patch("src.cli_commands_scale.scale_up_template_command_handler", new_callable=AsyncMock)
    def test_scale_up_template_success(
        self, mock_handler, mock_neo4j, runner, tmp_path
    ):
        """Test successful scale-up template operation."""
        # Create temporary template file
        template_file = tmp_path / "test_template.yaml"
        template_file.write_text("test: data")

        # Mock Neo4j startup
        mock_neo4j.return_value = None

        # Run command
        result = runner.invoke(
            scale_up,
            [
                "template",
                "--template-file",
                str(template_file),
                "--scale-factor",
                "2.0",
            ],
            obj={"debug": False},
        )

        assert result.exit_code == 0
        mock_neo4j.assert_called_once()
        mock_handler.assert_called_once()

    def test_scale_up_scenario_help(self, runner):
        """Test scale-up scenario help text displays correctly."""
        result = runner.invoke(scale_up, ["scenario", "--help"])

        assert result.exit_code == 0
        assert "scenario-based generation" in result.output
        assert "--scenario" in result.output
        assert "hub-spoke" in result.output
        assert "multi-region" in result.output

    @patch("src.commands.scaling.ensure_neo4j_running")
    @patch("src.cli_commands_scale.scale_up_scenario_command_handler", new_callable=AsyncMock)
    def test_scale_up_scenario_success(self, mock_handler, mock_neo4j, runner):
        """Test successful scale-up scenario operation."""
        # Mock Neo4j startup
        mock_neo4j.return_value = None

        # Run command
        result = runner.invoke(
            scale_up,
            ["scenario", "--scenario", "hub-spoke", "--spoke-count", "5"],
            obj={"debug": False},
        )

        assert result.exit_code == 0
        mock_neo4j.assert_called_once()
        mock_handler.assert_called_once()


class TestScaleDownCommands:
    """Test suite for scale-down CLI commands."""

    @pytest.fixture
    def runner(self):
        """Click CLI test runner."""
        return CliRunner()

    def test_scale_down_group_help(self, runner):
        """Test scale-down group help text displays correctly."""
        result = runner.invoke(scale_down, ["--help"])

        assert result.exit_code == 0
        assert "Scale down operations" in result.output
        assert "sample/reduce the graph" in result.output

    def test_scale_down_algorithm_help(self, runner):
        """Test scale-down algorithm help text displays correctly."""
        result = runner.invoke(scale_down, ["algorithm", "--help"])

        assert result.exit_code == 0
        assert "sampling algorithms" in result.output
        assert "--algorithm" in result.output
        assert "forest-fire" in result.output
        assert "mhrw" in result.output

    @patch("src.commands.scaling.ensure_neo4j_running")
    @patch(
        "src.cli_commands_scale.scale_down_algorithm_command_handler", new_callable=AsyncMock
    )
    def test_scale_down_algorithm_success(self, mock_handler, mock_neo4j, runner):
        """Test successful scale-down algorithm operation."""
        # Mock Neo4j startup
        mock_neo4j.return_value = None

        # Run command
        result = runner.invoke(
            scale_down,
            ["algorithm", "--algorithm", "forest-fire", "--target-size", "0.1"],
            obj={"debug": False},
        )

        assert result.exit_code == 0
        mock_neo4j.assert_called_once()
        mock_handler.assert_called_once()

    def test_scale_down_pattern_help(self, runner):
        """Test scale-down pattern help text displays correctly."""
        result = runner.invoke(scale_down, ["pattern", "--help"])

        assert result.exit_code == 0
        assert "pattern-based filtering" in result.output
        assert "--pattern" in result.output
        assert "security" in result.output
        assert "network" in result.output

    @patch("src.commands.scaling.ensure_neo4j_running")
    @patch("src.cli_commands_scale.scale_down_pattern_command_handler", new_callable=AsyncMock)
    def test_scale_down_pattern_success(self, mock_handler, mock_neo4j, runner):
        """Test successful scale-down pattern operation."""
        # Mock Neo4j startup
        mock_neo4j.return_value = None

        # Run command
        result = runner.invoke(
            scale_down,
            ["pattern", "--pattern", "security", "--target-size", "1.0"],
            obj={"debug": False},
        )

        assert result.exit_code == 0
        mock_neo4j.assert_called_once()
        mock_handler.assert_called_once()


class TestScaleCleanCommand:
    """Test suite for scale-clean CLI command."""

    @pytest.fixture
    def runner(self):
        """Click CLI test runner."""
        return CliRunner()

    def test_scale_clean_help(self, runner):
        """Test scale-clean help text displays correctly."""
        result = runner.invoke(scale_clean, ["--help"])

        assert result.exit_code == 0
        assert "Clean up all synthetic data" in result.output
        assert "--force" in result.output
        assert "--dry-run" in result.output

    @patch("src.commands.scaling.ensure_neo4j_running")
    @patch("src.cli_commands_scale.scale_clean_command_handler", new_callable=AsyncMock)
    def test_scale_clean_success(self, mock_handler, mock_neo4j, runner):
        """Test successful scale-clean operation."""
        # Mock Neo4j startup
        mock_neo4j.return_value = None

        # Run command with force flag to skip confirmation
        result = runner.invoke(scale_clean, ["--force"], obj={"debug": False})

        assert result.exit_code == 0
        mock_neo4j.assert_called_once()
        mock_handler.assert_called_once()

    @patch("src.commands.scaling.ensure_neo4j_running")
    @patch("src.cli_commands_scale.scale_clean_command_handler", new_callable=AsyncMock)
    def test_scale_clean_dry_run(self, mock_handler, mock_neo4j, runner):
        """Test scale-clean dry-run operation."""
        # Mock Neo4j startup
        mock_neo4j.return_value = None

        # Run command with dry-run flag
        result = runner.invoke(scale_clean, ["--dry-run"], obj={"debug": False})

        assert result.exit_code == 0
        mock_neo4j.assert_called_once()
        mock_handler.assert_called_once()


class TestScaleValidateCommand:
    """Test suite for scale-validate CLI command."""

    @pytest.fixture
    def runner(self):
        """Click CLI test runner."""
        return CliRunner()

    def test_scale_validate_help(self, runner):
        """Test scale-validate help text displays correctly."""
        result = runner.invoke(scale_validate, ["--help"])

        assert result.exit_code == 0
        assert "Validate graph integrity" in result.output
        assert "--fix" in result.output
        assert "validation checks" in result.output

    @patch("src.commands.scaling.ensure_neo4j_running")
    @patch("src.cli_commands_scale.scale_validate_command_handler", new_callable=AsyncMock)
    def test_scale_validate_success(self, mock_handler, mock_neo4j, runner):
        """Test successful scale-validate operation."""
        # Mock Neo4j startup
        mock_neo4j.return_value = None

        # Run command
        result = runner.invoke(scale_validate, [], obj={"debug": False})

        assert result.exit_code == 0
        mock_neo4j.assert_called_once()
        mock_handler.assert_called_once()

    @patch("src.commands.scaling.ensure_neo4j_running")
    @patch("src.cli_commands_scale.scale_validate_command_handler", new_callable=AsyncMock)
    def test_scale_validate_with_fix(self, mock_handler, mock_neo4j, runner):
        """Test scale-validate with auto-fix flag."""
        # Mock Neo4j startup
        mock_neo4j.return_value = None

        # Run command with fix flag
        result = runner.invoke(scale_validate, ["--fix"], obj={"debug": False})

        assert result.exit_code == 0
        mock_neo4j.assert_called_once()
        mock_handler.assert_called_once()


class TestScaleStatsCommand:
    """Test suite for scale-stats CLI command."""

    @pytest.fixture
    def runner(self):
        """Click CLI test runner."""
        return CliRunner()

    def test_scale_stats_help(self, runner):
        """Test scale-stats help text displays correctly."""
        result = runner.invoke(scale_stats, ["--help"])

        assert result.exit_code == 0
        assert "Show graph statistics" in result.output
        assert "--detailed" in result.output
        assert "metrics" in result.output

    @patch("src.commands.scaling.ensure_neo4j_running")
    @patch("src.cli_commands_scale.scale_stats_command_handler", new_callable=AsyncMock)
    def test_scale_stats_success(self, mock_handler, mock_neo4j, runner):
        """Test successful scale-stats operation."""
        # Mock Neo4j startup
        mock_neo4j.return_value = None

        # Run command
        result = runner.invoke(scale_stats, [], obj={"debug": False})

        assert result.exit_code == 0
        mock_neo4j.assert_called_once()
        mock_handler.assert_called_once()

    @patch("src.commands.scaling.ensure_neo4j_running")
    @patch("src.cli_commands_scale.scale_stats_command_handler", new_callable=AsyncMock)
    def test_scale_stats_detailed(self, mock_handler, mock_neo4j, runner):
        """Test scale-stats with detailed flag."""
        # Mock Neo4j startup
        mock_neo4j.return_value = None

        # Run command with detailed flag
        result = runner.invoke(scale_stats, ["--detailed"], obj={"debug": False})

        assert result.exit_code == 0
        mock_neo4j.assert_called_once()
        mock_handler.assert_called_once()


class TestBackwardCompatibility:
    """Test backward compatibility after modularization."""

    @pytest.fixture
    def runner(self):
        """Click CLI test runner."""
        return CliRunner()

    def test_all_commands_importable(self):
        """Test that all scaling commands are importable."""
        from src.commands.scaling import (
            scale_clean,
            scale_clean_command,
            scale_down,
            scale_down_algorithm,
            scale_down_group,
            scale_down_pattern,
            scale_stats,
            scale_stats_command,
            scale_up,
            scale_up_group,
            scale_up_scenario,
            scale_up_template,
            scale_validate,
            scale_validate_command,
        )

        # Verify all imports succeeded
        assert scale_up is not None
        assert scale_up_group is not None
        assert scale_up_template is not None
        assert scale_up_scenario is not None
        assert scale_down is not None
        assert scale_down_group is not None
        assert scale_down_algorithm is not None
        assert scale_down_pattern is not None
        assert scale_clean is not None
        assert scale_clean_command is not None
        assert scale_validate is not None
        assert scale_validate_command is not None
        assert scale_stats is not None
        assert scale_stats_command is not None

    def test_command_aliases_exist(self):
        """Test that backward compatibility aliases exist."""
        from src.commands.scaling import (
            scale_clean_command,
            scale_down_group,
            scale_stats_command,
            scale_up_group,
            scale_validate_command,
        )

        # These should be the same objects
        assert scale_up_group is scale_up
        assert scale_down_group is scale_down
        assert scale_clean_command is scale_clean
        assert scale_validate_command is scale_validate
        assert scale_stats_command is scale_stats
