"""
End-to-end CLI tests for resource-level fidelity validation command.

Tests the complete user workflow from command execution to output.

Testing pyramid distribution: 10% E2E tests (this file)
"""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

# These imports will fail initially - that's expected for TDD
try:
    from src.cli_commands_fidelity import fidelity
    from src.validation.resource_fidelity_calculator import (
        RedactionLevel,
        ResourceFidelityMetrics,
        ResourceStatus,
    )
except ImportError:
    # TDD: Modules don't exist yet
    pass


@pytest.fixture
def cli_runner():
    """Create Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_calculator():
    """Create mock ResourceFidelityCalculator with sample results."""
    from dataclasses import dataclass
    from typing import Any, List

    @dataclass
    class MockResult:
        classifications: List[Any]
        metrics: ResourceFidelityMetrics

    mock = Mock()

    # Mock result with sample data
    mock.calculate_fidelity.return_value = MockResult(
        classifications=[
            Mock(
                resource_id="/subscriptions/abc/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/storage1",
                resource_name="storage1",
                resource_type="Microsoft.Storage/storageAccounts",
                status=ResourceStatus.DRIFTED,
                source_exists=True,
                target_exists=True,
                property_comparisons=[
                    Mock(property_path="sku.name", source_value="Standard_LRS", target_value="Premium_LRS", match=False)
                ],
                mismatch_count=1,
                match_count=2,
            ),
            Mock(
                resource_id="/subscriptions/abc/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm1",
                resource_name="vm1",
                resource_type="Microsoft.Compute/virtualMachines",
                status=ResourceStatus.MISSING_TARGET,
                source_exists=True,
                target_exists=False,
                property_comparisons=[],
                mismatch_count=0,
                match_count=0,
            ),
        ],
        metrics=ResourceFidelityMetrics(
            total_resources=2,
            exact_match=0,
            drifted=1,
            missing_target=1,
            missing_source=0,
            match_percentage=0.0,
            top_mismatched_properties=[{"property": "sku.name", "count": 1}],
        ),
    )

    return mock


class TestFidelityCommandBasicExecution:
    """Test basic execution of fidelity --resource-level command."""

    def test_command_requires_resource_level_flag(self, cli_runner):
        """Test that --resource-level flag is required for resource validation."""
        result = cli_runner.invoke(fidelity)

        # Command should show help or error without --resource-level flag
        assert result.exit_code != 0 or "--resource-level" in result.output

    def test_command_with_resource_level_flag_executes(self, cli_runner, mock_calculator):
        """Test command executes with --resource-level flag."""
        with patch("src.cli_commands_fidelity.ResourceFidelityCalculator", return_value=mock_calculator):
            result = cli_runner.invoke(fidelity, ["--resource-level"])

            # Command should execute successfully
            assert result.exit_code == 0

    def test_command_displays_console_output(self, cli_runner, mock_calculator):
        """Test command displays formatted console output."""
        with patch("src.cli_commands_fidelity.ResourceFidelityCalculator", return_value=mock_calculator):
            result = cli_runner.invoke(fidelity, ["--resource-level"])

            # Should display header
            assert "Resource-Level Fidelity Validation Report" in result.output
            # Should display resource name
            assert "storage1" in result.output
            # Should display status
            assert "DRIFTED" in result.output or "MISMATCH" in result.output
            # Should display summary
            assert "Total Resources" in result.output


class TestFidelityCommandResourceTypeFiltering:
    """Test --resource-type filtering option."""

    def test_filter_by_storage_accounts(self, cli_runner, mock_calculator):
        """Test filtering validation to Storage Accounts only."""
        with patch("src.cli_commands_fidelity.ResourceFidelityCalculator", return_value=mock_calculator):
            result = cli_runner.invoke(
                fidelity,
                ["--resource-level", "--resource-type", "Microsoft.Storage/storageAccounts"],
            )

            assert result.exit_code == 0
            # Should show filter in output
            assert "Microsoft.Storage/storageAccounts" in result.output

    def test_filter_by_virtual_machines(self, cli_runner, mock_calculator):
        """Test filtering validation to Virtual Machines only."""
        with patch("src.cli_commands_fidelity.ResourceFidelityCalculator", return_value=mock_calculator):
            result = cli_runner.invoke(
                fidelity,
                ["--resource-level", "--resource-type", "Microsoft.Compute/virtualMachines"],
            )

            assert result.exit_code == 0
            assert "Microsoft.Compute/virtualMachines" in result.output

    def test_invalid_resource_type_shows_error(self, cli_runner):
        """Test invalid resource type shows helpful error."""
        result = cli_runner.invoke(
            fidelity,
            ["--resource-level", "--resource-type", "Invalid.Type"],
        )

        # Should show error for invalid type
        assert result.exit_code != 0 or "invalid" in result.output.lower()


class TestFidelityCommandJSONExport:
    """Test --output option for JSON export."""

    def test_export_to_json_file(self, cli_runner, mock_calculator, tmp_path):
        """Test exporting validation results to JSON file."""
        output_file = tmp_path / "fidelity-report.json"

        with patch("src.cli_commands_fidelity.ResourceFidelityCalculator", return_value=mock_calculator):
            result = cli_runner.invoke(
                fidelity,
                ["--resource-level", "--output", str(output_file)],
            )

            assert result.exit_code == 0
            # File should be created
            assert output_file.exists()
            # Should show success message
            assert "saved" in result.output.lower() or "exported" in result.output.lower()

    def test_json_export_creates_valid_json(self, cli_runner, mock_calculator, tmp_path):
        """Test JSON export creates valid parseable JSON."""
        output_file = tmp_path / "report.json"

        with patch("src.cli_commands_fidelity.ResourceFidelityCalculator", return_value=mock_calculator):
            result = cli_runner.invoke(
                fidelity,
                ["--resource-level", "--output", str(output_file)],
            )

            # Verify JSON is valid
            with open(output_file) as f:
                data = json.load(f)

            assert "metadata" in data
            assert "resources" in data
            assert "summary" in data

    def test_json_export_includes_all_expected_fields(self, cli_runner, mock_calculator, tmp_path):
        """Test JSON export includes all expected report fields."""
        output_file = tmp_path / "report.json"

        with patch("src.cli_commands_fidelity.ResourceFidelityCalculator", return_value=mock_calculator):
            cli_runner.invoke(
                fidelity,
                ["--resource-level", "--output", str(output_file)],
            )

            with open(output_file) as f:
                data = json.load(f)

            # Verify all required fields
            assert "validation_timestamp" in data["metadata"]
            assert "source_subscription" in data["metadata"]
            assert "target_subscription" in data["metadata"]
            assert "total_resources" in data["summary"]
            assert "exact_match" in data["summary"]
            assert "drifted" in data["summary"]
            assert "security_warnings" in data


# Historical tracking tests removed per Zero-BS principle
# Resource-level fidelity does not support historical tracking
# Use subscription-level fidelity with --track for time-series metrics


class TestFidelityCommandRedactionLevels:
    """Test --redaction-level option for security controls."""

    def test_default_redaction_is_full(self, cli_runner, mock_calculator):
        """Test default redaction level is FULL (most secure)."""
        with patch("src.cli_commands_fidelity.ResourceFidelityCalculator", return_value=mock_calculator):
            result = cli_runner.invoke(
                fidelity,
                ["--resource-level"],
            )

            # Verify FULL redaction was used
            call_args = mock_calculator.calculate_fidelity.call_args
            if call_args and len(call_args[1]) > 0:
                assert call_args[1].get("redaction_level") == RedactionLevel.FULL

    def test_minimal_redaction_level(self, cli_runner, mock_calculator):
        """Test --redaction-level MINIMAL option."""
        with patch("src.cli_commands_fidelity.ResourceFidelityCalculator", return_value=mock_calculator):
            result = cli_runner.invoke(
                fidelity,
                ["--resource-level", "--redaction-level", "MINIMAL"],
            )

            assert result.exit_code == 0
            # Should show warning about minimal redaction
            assert "MINIMAL" in result.output or "redaction" in result.output.lower()

    def test_none_redaction_level_requires_confirmation(self, cli_runner, mock_calculator):
        """Test --redaction-level NONE shows security warning."""
        with patch("src.cli_commands_fidelity.ResourceFidelityCalculator", return_value=mock_calculator):
            result = cli_runner.invoke(
                fidelity,
                ["--resource-level", "--redaction-level", "NONE"],
            )

            # Should show strong security warning
            assert "WARNING" in result.output or "security" in result.output.lower()

    def test_invalid_redaction_level_shows_error(self, cli_runner):
        """Test invalid redaction level shows error."""
        result = cli_runner.invoke(
            fidelity,
            ["--resource-level", "--redaction-level", "INVALID"],
        )

        assert result.exit_code != 0


class TestFidelityCommandSubscriptionOverrides:
    """Test --source-subscription and --target-subscription options."""

    def test_source_subscription_override(self, cli_runner, mock_calculator):
        """Test overriding source subscription ID."""
        with patch("src.cli_commands_fidelity.ResourceFidelityCalculator", return_value=mock_calculator) as MockCalc:
            result = cli_runner.invoke(
                fidelity,
                ["--resource-level", "--source-subscription", "custom-source-sub"],
            )

            assert result.exit_code == 0
            # Verify calculator was created with custom subscription
            MockCalc.assert_called_once()
            call_args = MockCalc.call_args
            assert call_args[1]["source_subscription_id"] == "custom-source-sub"

    def test_target_subscription_override(self, cli_runner, mock_calculator):
        """Test overriding target subscription ID."""
        with patch("src.cli_commands_fidelity.ResourceFidelityCalculator", return_value=mock_calculator) as MockCalc:
            result = cli_runner.invoke(
                fidelity,
                ["--resource-level", "--target-subscription", "custom-target-sub"],
            )

            assert result.exit_code == 0
            call_args = MockCalc.call_args
            assert call_args[1]["target_subscription_id"] == "custom-target-sub"

    def test_both_subscriptions_override(self, cli_runner, mock_calculator):
        """Test overriding both source and target subscriptions."""
        with patch("src.cli_commands_fidelity.ResourceFidelityCalculator", return_value=mock_calculator) as MockCalc:
            result = cli_runner.invoke(
                fidelity,
                [
                    "--resource-level",
                    "--source-subscription",
                    "custom-source",
                    "--target-subscription",
                    "custom-target",
                ],
            )

            assert result.exit_code == 0
            call_args = MockCalc.call_args
            assert call_args[1]["source_subscription_id"] == "custom-source"
            assert call_args[1]["target_subscription_id"] == "custom-target"


class TestFidelityCommandErrorHandling:
    """Test error handling and user-friendly error messages."""

    def test_neo4j_connection_error_shows_helpful_message(self, cli_runner):
        """Test Neo4j connection error shows helpful message."""
        with patch("src.cli_commands_fidelity.ResourceFidelityCalculator") as MockCalc:
            MockCalc.side_effect = Exception("Neo4j connection failed")

            result = cli_runner.invoke(
                fidelity,
                ["--resource-level"],
            )

            # Should show error message
            assert result.exit_code != 0
            assert "error" in result.output.lower() or "failed" in result.output.lower()

    def test_no_resources_found_shows_informative_message(self, cli_runner, mock_calculator):
        """Test message when no resources are found."""
        # Mock empty result
        mock_calculator.calculate_fidelity.return_value.metrics.total_resources = 0
        mock_calculator.calculate_fidelity.return_value.classifications = []

        with patch("src.cli_commands_fidelity.ResourceFidelityCalculator", return_value=mock_calculator):
            result = cli_runner.invoke(
                fidelity,
                ["--resource-level"],
            )

            # Should show informative message
            assert "no resources" in result.output.lower() or "0 resources" in result.output.lower()

    def test_invalid_output_path_shows_error(self, cli_runner, mock_calculator):
        """Test invalid output path shows error."""
        with patch("src.cli_commands_fidelity.ResourceFidelityCalculator", return_value=mock_calculator):
            result = cli_runner.invoke(
                fidelity,
                ["--resource-level", "--output", "/invalid/path/that/does/not/exist/report.json"],
            )

            # Should show error about invalid path
            assert result.exit_code != 0 or "error" in result.output.lower()


class TestFidelityCommandConsoleFormatting:
    """Test console output formatting and readability."""

    def test_console_output_includes_header(self, cli_runner, mock_calculator):
        """Test console output has clear header."""
        with patch("src.cli_commands_fidelity.ResourceFidelityCalculator", return_value=mock_calculator):
            result = cli_runner.invoke(
                fidelity,
                ["--resource-level"],
            )

            assert "Resource-Level Fidelity Validation Report" in result.output
            assert "=" in result.output  # Header decoration

    def test_console_output_shows_resource_details(self, cli_runner, mock_calculator):
        """Test console output shows detailed resource information."""
        with patch("src.cli_commands_fidelity.ResourceFidelityCalculator", return_value=mock_calculator):
            result = cli_runner.invoke(
                fidelity,
                ["--resource-level"],
            )

            # Should show resource type
            assert "Microsoft.Storage/storageAccounts" in result.output
            # Should show resource name
            assert "storage1" in result.output
            # Should show status
            assert "DRIFTED" in result.output or "MISMATCH" in result.output

    def test_console_output_shows_property_mismatches(self, cli_runner, mock_calculator):
        """Test console output shows property-level mismatches."""
        with patch("src.cli_commands_fidelity.ResourceFidelityCalculator", return_value=mock_calculator):
            result = cli_runner.invoke(
                fidelity,
                ["--resource-level"],
            )

            # Should show property path
            assert "sku.name" in result.output
            # Should show source and target values
            assert "Standard_LRS" in result.output
            assert "Premium_LRS" in result.output

    def test_console_output_shows_summary_statistics(self, cli_runner, mock_calculator):
        """Test console output includes summary statistics."""
        with patch("src.cli_commands_fidelity.ResourceFidelityCalculator", return_value=mock_calculator):
            result = cli_runner.invoke(
                fidelity,
                ["--resource-level"],
            )

            # Should show summary section
            assert "Summary" in result.output
            # Should show total resources
            assert "Total Resources" in result.output or "2" in result.output
            # Should show match percentage
            assert "%" in result.output

    def test_console_output_uses_color_for_status(self, cli_runner, mock_calculator):
        """Test console output uses symbols or colors for status indicators."""
        with patch("src.cli_commands_fidelity.ResourceFidelityCalculator", return_value=mock_calculator):
            result = cli_runner.invoke(
                fidelity,
                ["--resource-level"],
            )

            # Should use status symbols (✓, ✗, ⚠)
            has_symbols = "✓" in result.output or "✗" in result.output or "⚠" in result.output
            # Or should have clear status text
            has_status_text = "MATCH" in result.output or "MISMATCH" in result.output

            assert has_symbols or has_status_text


class TestFidelityCommandCombinedOptions:
    """Test combining multiple command options."""

    def test_filter_with_json_export(self, cli_runner, mock_calculator, tmp_path):
        """Test combining --resource-type filter with --output JSON export."""
        output_file = tmp_path / "filtered-report.json"

        with patch("src.cli_commands_fidelity.ResourceFidelityCalculator", return_value=mock_calculator):
            result = cli_runner.invoke(
                fidelity,
                [
                    "--resource-level",
                    "--resource-type",
                    "Microsoft.Storage/storageAccounts",
                    "--output",
                    str(output_file),
                ],
            )

            assert result.exit_code == 0
            assert output_file.exists()

            # Verify filter is in JSON metadata
            with open(output_file) as f:
                data = json.load(f)
            assert data["metadata"]["resource_type_filter"] == "Microsoft.Storage/storageAccounts"

    def test_filter_with_tracking_and_minimal_redaction(self, cli_runner, mock_calculator):
        """Test combining filter, tracking, and redaction level."""
        with patch("src.cli_commands_fidelity.ResourceFidelityCalculator", return_value=mock_calculator):
            result = cli_runner.invoke(
                fidelity,
                [
                    "--resource-level",
                    "--resource-type",
                    "Microsoft.Compute/virtualMachines",
                    "--track",
                    "--redaction-level",
                    "MINIMAL",
                ],
            )

            assert result.exit_code == 0

    def test_subscription_overrides_with_json_export(self, cli_runner, mock_calculator, tmp_path):
        """Test combining subscription overrides with JSON export."""
        output_file = tmp_path / "custom-subs-report.json"

        with patch("src.cli_commands_fidelity.ResourceFidelityCalculator", return_value=mock_calculator):
            result = cli_runner.invoke(
                fidelity,
                [
                    "--resource-level",
                    "--source-subscription",
                    "source-sub-123",
                    "--target-subscription",
                    "target-sub-456",
                    "--output",
                    str(output_file),
                ],
            )

            assert result.exit_code == 0

            with open(output_file) as f:
                data = json.load(f)
            assert data["metadata"]["source_subscription"] == "source-sub-123"
            assert data["metadata"]["target_subscription"] == "target-sub-456"
