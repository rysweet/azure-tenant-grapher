#!/usr/bin/env python3
"""
Test suite for scale operations CLI commands (Issue #427).

Tests all CLI commands for scale-up, scale-down, and utility operations.
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import click.testing
import pytest

# Add the parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.cli import cli


class TestScaleUpCommands:
    """Test scale-up command group and subcommands."""

    def test_scale_up_group_exists(self):
        """Verify scale-up command group is registered."""
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["scale-up", "--help"])

        assert result.exit_code == 0
        assert "Scale up operations" in result.output
        assert "template" in result.output
        assert "scenario" in result.output

    def test_scale_up_template_command_exists(self):
        """Verify scale-up template subcommand exists with correct parameters."""
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["scale-up", "template", "--help"])

        assert result.exit_code == 0
        assert "--template-file" in result.output
        assert "--scale-factor" in result.output
        assert "--batch-size" in result.output
        assert "--dry-run" in result.output
        assert "--no-validate" in result.output
        assert "--config" in result.output
        assert "--output-format" in result.output

    def test_scale_up_template_requires_template_file(self):
        """Verify template command requires --template-file parameter."""
        runner = click.testing.CliRunner()
        result = runner.invoke(
            cli, ["scale-up", "template", "--tenant-id", "test-tenant"]
        )

        assert result.exit_code != 0
        assert "template-file" in result.output.lower() or "missing" in result.output.lower()

    def test_scale_up_scenario_command_exists(self):
        """Verify scale-up scenario subcommand exists with correct parameters."""
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["scale-up", "scenario", "--help"])

        assert result.exit_code == 0
        assert "--scenario" in result.output
        assert "--scale-factor" in result.output
        assert "--regions" in result.output
        assert "--spoke-count" in result.output
        assert "--dry-run" in result.output

    def test_scale_up_scenario_requires_scenario_parameter(self):
        """Verify scenario command requires --scenario parameter."""
        runner = click.testing.CliRunner()
        result = runner.invoke(
            cli, ["scale-up", "scenario", "--tenant-id", "test-tenant"]
        )

        assert result.exit_code != 0
        assert "scenario" in result.output.lower() or "missing" in result.output.lower()

    def test_scale_up_scenario_validates_scenario_choices(self):
        """Verify scenario command validates scenario type."""
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["scale-up", "scenario", "--help"])

        assert "hub-spoke" in result.output
        assert "multi-region" in result.output
        assert "dev-test-prod" in result.output

    @patch("src.config_manager.create_neo4j_config_from_env")
    @patch("src.services.scale_up_service.ScaleUpService")
    @patch.dict("os.environ", {"AZURE_TENANT_ID": "test-tenant-id"})
    def test_scale_up_template_dry_run_mode(
        self, mock_service_class, mock_neo4j_config
    ):
        """Test scale-up template with dry-run flag."""
        # Mock Neo4j driver
        mock_driver = MagicMock()
        mock_driver.close = AsyncMock()
        mock_neo4j_config.return_value.get_driver.return_value = mock_driver

        # Mock service
        mock_service = MagicMock()
        mock_service.scale_up_from_template = AsyncMock(
            return_value={"nodes_created": 100, "relationships_created": 200}
        )
        mock_service_class.return_value = mock_service

        runner = click.testing.CliRunner()

        # Create a temporary template file
        with runner.isolated_filesystem():
            template_path = "test_template.yaml"
            with open(template_path, "w") as f:
                f.write("# Test template\n")

            result = runner.invoke(
                cli,
                [
                    "scale-up",
                    "template",
                    "--template-file",
                    template_path,
                    "--scale-factor",
                    "2.0",
                    "--dry-run",
                ],
            )

            # Should not error (dry run should work)
            assert "DRY RUN" in result.output or result.exit_code == 0


class TestScaleDownCommands:
    """Test scale-down command group and subcommands."""

    def test_scale_down_group_exists(self):
        """Verify scale-down command group is registered."""
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["scale-down", "--help"])

        assert result.exit_code == 0
        assert "Scale down operations" in result.output
        assert "algorithm" in result.output
        assert "pattern" in result.output

    def test_scale_down_algorithm_command_exists(self):
        """Verify scale-down algorithm subcommand exists with correct parameters."""
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["scale-down", "algorithm", "--help"])

        assert result.exit_code == 0
        assert "--algorithm" in result.output
        assert "--target-size" in result.output
        assert "--target-count" in result.output
        assert "--burn-in" in result.output
        assert "--burning-prob" in result.output
        assert "--walk-length" in result.output
        assert "--alpha" in result.output
        assert "--output-mode" in result.output
        assert "--dry-run" in result.output

    def test_scale_down_algorithm_validates_algorithm_choices(self):
        """Verify algorithm command validates algorithm type."""
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["scale-down", "algorithm", "--help"])

        assert "forest-fire" in result.output
        assert "mhrw" in result.output
        assert "random-walk" in result.output
        assert "random-node" in result.output

    def test_scale_down_pattern_command_exists(self):
        """Verify scale-down pattern subcommand exists with correct parameters."""
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["scale-down", "pattern", "--help"])

        assert result.exit_code == 0
        assert "--pattern" in result.output
        assert "--resource-types" in result.output
        assert "--target-size" in result.output
        assert "--output-mode" in result.output
        assert "--dry-run" in result.output

    def test_scale_down_pattern_validates_pattern_choices(self):
        """Verify pattern command validates pattern type."""
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["scale-down", "pattern", "--help"])

        assert "security" in result.output
        assert "network" in result.output
        assert "compute" in result.output
        assert "storage" in result.output
        assert "resource-type" in result.output

    def test_scale_down_algorithm_requires_algorithm_parameter(self):
        """Verify algorithm command requires --algorithm parameter."""
        runner = click.testing.CliRunner()
        result = runner.invoke(
            cli, ["scale-down", "algorithm", "--tenant-id", "test-tenant"]
        )

        assert result.exit_code != 0
        assert "algorithm" in result.output.lower() or "missing" in result.output.lower()

    def test_scale_down_pattern_requires_pattern_parameter(self):
        """Verify pattern command requires --pattern parameter."""
        runner = click.testing.CliRunner()
        result = runner.invoke(
            cli, ["scale-down", "pattern", "--tenant-id", "test-tenant"]
        )

        assert result.exit_code != 0
        assert "pattern" in result.output.lower() or "missing" in result.output.lower()


class TestScaleUtilityCommands:
    """Test scale utility commands (clean, validate, stats)."""

    def test_scale_clean_command_exists(self):
        """Verify scale-clean command exists with correct parameters."""
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["scale-clean", "--help"])

        assert result.exit_code == 0
        assert "Clean up all synthetic data" in result.output
        assert "--force" in result.output
        assert "--dry-run" in result.output
        assert "--output-format" in result.output

    def test_scale_validate_command_exists(self):
        """Verify scale-validate command exists with correct parameters."""
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["scale-validate", "--help"])

        assert result.exit_code == 0
        assert "Validate graph integrity" in result.output
        assert "--fix" in result.output
        assert "--output-format" in result.output

    def test_scale_stats_command_exists(self):
        """Verify scale-stats command exists with correct parameters."""
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["scale-stats", "--help"])

        assert result.exit_code == 0
        assert "Show graph statistics" in result.output
        assert "--detailed" in result.output
        assert "--output-format" in result.output

    def test_scale_clean_has_confirmation_safety(self):
        """Verify scale-clean command mentions confirmation."""
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["scale-clean", "--help"])

        # Check that help text mentions force flag for skipping confirmation
        assert "--force" in result.output

    @patch("src.config_manager.create_neo4j_config_from_env")
    @patch.dict("os.environ", {"AZURE_TENANT_ID": "test-tenant-id"})
    def test_scale_stats_command_execution(self, mock_neo4j_config):
        """Test scale-stats command execution."""
        # Mock Neo4j driver and session
        mock_result = MagicMock()
        mock_result.single.return_value = {"count": 100}

        mock_session = MagicMock()
        mock_session.run.return_value = mock_result
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=None)

        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session
        mock_driver.close = AsyncMock()

        mock_neo4j_config.return_value.get_driver.return_value = mock_driver

        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["scale-stats"])

        # Should execute without error
        assert result.exit_code == 0 or "statistics" in result.output.lower()


class TestScaleCommandOutputFormats:
    """Test output format support across scale commands."""

    def test_scale_up_template_supports_output_formats(self):
        """Verify scale-up template supports multiple output formats."""
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["scale-up", "template", "--help"])

        assert "--output-format" in result.output
        assert "table" in result.output or "json" in result.output or "markdown" in result.output

    def test_scale_down_algorithm_supports_output_formats(self):
        """Verify scale-down algorithm supports YAML and JSON export."""
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["scale-down", "algorithm", "--help"])

        assert "--output-format" in result.output
        assert "yaml" in result.output or "json" in result.output

    def test_scale_stats_supports_output_formats(self):
        """Verify scale-stats supports multiple output formats."""
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["scale-stats", "--help"])

        assert "--output-format" in result.output
        # Should support table, json, markdown
        output_lower = result.output.lower()
        assert any(fmt in output_lower for fmt in ["table", "json", "markdown"])


class TestScaleDryRunMode:
    """Test dry-run mode across scale commands."""

    def test_scale_up_template_has_dry_run(self):
        """Verify scale-up template supports dry-run."""
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["scale-up", "template", "--help"])

        assert "--dry-run" in result.output
        assert "preview" in result.output.lower() or "without executing" in result.output.lower()

    def test_scale_up_scenario_has_dry_run(self):
        """Verify scale-up scenario supports dry-run."""
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["scale-up", "scenario", "--help"])

        assert "--dry-run" in result.output

    def test_scale_down_algorithm_has_dry_run(self):
        """Verify scale-down algorithm supports dry-run."""
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["scale-down", "algorithm", "--help"])

        assert "--dry-run" in result.output

    def test_scale_down_pattern_has_dry_run(self):
        """Verify scale-down pattern supports dry-run."""
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["scale-down", "pattern", "--help"])

        assert "--dry-run" in result.output

    def test_scale_clean_has_dry_run(self):
        """Verify scale-clean supports dry-run."""
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["scale-clean", "--help"])

        assert "--dry-run" in result.output


class TestScaleConfigurationSupport:
    """Test configuration file support."""

    def test_scale_up_template_supports_config_file(self):
        """Verify scale-up template accepts config file."""
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["scale-up", "template", "--help"])

        assert "--config" in result.output

    def test_scale_up_scenario_supports_config_file(self):
        """Verify scale-up scenario accepts config file."""
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["scale-up", "scenario", "--help"])

        assert "--config" in result.output

    def test_scale_down_algorithm_supports_config_file(self):
        """Verify scale-down algorithm accepts config file."""
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["scale-down", "algorithm", "--help"])

        assert "--config" in result.output


class TestScaleValidationOptions:
    """Test validation-related options."""

    def test_scale_up_template_has_validation_option(self):
        """Verify scale-up template has --no-validate option."""
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["scale-up", "template", "--help"])

        assert "--no-validate" in result.output

    def test_scale_up_scenario_has_validation_option(self):
        """Verify scale-up scenario has --no-validate option."""
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["scale-up", "scenario", "--help"])

        assert "--no-validate" in result.output

    def test_scale_validate_has_fix_option(self):
        """Verify scale-validate has --fix option for auto-fixing."""
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["scale-validate", "--help"])

        assert "--fix" in result.output
        assert "auto" in result.output.lower() or "fix" in result.output.lower()


class TestScaleCommandHelpText:
    """Test help text quality and completeness."""

    def test_all_scale_commands_have_examples(self):
        """Verify all scale commands have usage examples in help text."""
        runner = click.testing.CliRunner()

        commands_to_test = [
            ["scale-up", "template"],
            ["scale-up", "scenario"],
            ["scale-down", "algorithm"],
            ["scale-down", "pattern"],
            ["scale-clean"],
            ["scale-validate"],
            ["scale-stats"],
        ]

        for cmd in commands_to_test:
            result = runner.invoke(cli, cmd + ["--help"])
            assert result.exit_code == 0
            # Should have either "Example" or "Usage" in help text
            help_lower = result.output.lower()
            assert "example" in help_lower or "usage" in help_lower, f"Command {' '.join(cmd)} missing examples"

    def test_scale_commands_have_clear_descriptions(self):
        """Verify scale commands have clear descriptions."""
        runner = click.testing.CliRunner()

        # Check main groups
        result = runner.invoke(cli, ["scale-up", "--help"])
        assert result.exit_code == 0
        assert len(result.output) > 100  # Non-trivial help text

        result = runner.invoke(cli, ["scale-down", "--help"])
        assert result.exit_code == 0
        assert len(result.output) > 100


class TestScaleCommandErrorHandling:
    """Test error handling and validation."""

    def test_scale_up_template_validates_file_existence(self):
        """Verify template command validates file exists."""
        runner = click.testing.CliRunner()
        result = runner.invoke(
            cli,
            [
                "scale-up",
                "template",
                "--template-file",
                "/nonexistent/file.yaml",
                "--tenant-id",
                "test",
            ],
        )

        # Should fail due to nonexistent file
        assert result.exit_code != 0

    def test_scale_commands_respect_no_container_flag(self):
        """Verify all scale commands have --no-container option."""
        runner = click.testing.CliRunner()

        commands = [
            ["scale-up", "template"],
            ["scale-up", "scenario"],
            ["scale-down", "algorithm"],
            ["scale-down", "pattern"],
            ["scale-clean"],
            ["scale-validate"],
            ["scale-stats"],
        ]

        for cmd in commands:
            result = runner.invoke(cli, cmd + ["--help"])
            assert "--no-container" in result.output, f"Command {' '.join(cmd)} missing --no-container"


class TestScaleCommandParameters:
    """Test specific parameter validations."""

    def test_scale_factor_defaults_correctly(self):
        """Verify scale-factor has correct defaults."""
        runner = click.testing.CliRunner()

        # Template should default to 2.0
        result = runner.invoke(cli, ["scale-up", "template", "--help"])
        assert "2.0" in result.output or "default: 2" in result.output.lower()

        # Scenario should default to 1.0
        result = runner.invoke(cli, ["scale-up", "scenario", "--help"])
        assert "1.0" in result.output or "default: 1" in result.output.lower()

    def test_target_size_defaults_correctly(self):
        """Verify target-size has correct default (0.1)."""
        runner = click.testing.CliRunner()

        result = runner.invoke(cli, ["scale-down", "algorithm", "--help"])
        assert "0.1" in result.output

    def test_batch_size_has_default(self):
        """Verify batch-size has a default value."""
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["scale-up", "template", "--help"])

        assert "--batch-size" in result.output
        assert "500" in result.output  # Default batch size

    def test_spoke_count_has_default(self):
        """Verify spoke-count has a default value."""
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["scale-up", "scenario", "--help"])

        assert "--spoke-count" in result.output
        assert "3" in result.output  # Default spoke count


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
