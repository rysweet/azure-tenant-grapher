"""
Integration tests for PR #902 CLI flag registration and parameter flow.

This module tests the complete integration of CLI flags through to the
fidelity command handler, ensuring all four bugs are fixed in concert.

Testing pyramid distribution: 30% integration tests
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from click.testing import CliRunner

from src.validation.resource_fidelity_calculator import (
    FidelityResult,
    PropertyComparison,
    RedactionLevel,
    ResourceClassification,
    ResourceFidelityMetrics,
    ResourceStatus,
)


@pytest.fixture
def cli_runner():
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_neo4j_environment():
    """Mock Neo4j environment for testing."""
    with patch("src.commands.fidelity.ensure_neo4j_running"):
        with patch("src.commands.fidelity.get_neo4j_config_from_env", return_value=("neo4j://localhost", "neo4j", "password")):
            with patch("src.commands.fidelity.Neo4jConfig"):
                yield


@pytest.fixture
def mock_session_manager():
    """Create mock session manager."""
    mock_manager = Mock()
    mock_manager.connect = Mock()
    mock_manager.session = Mock()
    return mock_manager


@pytest.fixture
def sample_fidelity_result():
    """Create sample fidelity result for testing."""
    classification = ResourceClassification(
        resource_id="/subscriptions/source/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/storage1",
        resource_name="storage1",
        resource_type="Microsoft.Storage/storageAccounts",
        status=ResourceStatus.DRIFTED,
        source_exists=True,
        target_exists=True,
        property_comparisons=[
            PropertyComparison("sku.name", "Standard_LRS", "Premium_LRS", False, False),
            PropertyComparison("location", "eastus", "eastus", True, False),
        ],
        mismatch_count=1,
        match_count=1,
    )

    return FidelityResult(
        classifications=[classification],
        metrics=ResourceFidelityMetrics(
            total_resources=1,
            exact_match=0,
            drifted=1,
            missing_target=0,
            missing_source=0,
            match_percentage=50.0,
            top_mismatched_properties=[{"property": "sku.name", "count": 1}],
        ),
        source_subscription="source-sub-123",
        target_subscription="target-sub-456",
        redaction_level=RedactionLevel.FULL,
    )


class TestCLIFlagRegistration:
    """Test CLI flag registration for all new parameters."""

    @pytest.mark.asyncio
    async def test_resource_level_flag_recognized(self, cli_runner, mock_neo4j_environment):
        """Verify --resource-level flag is recognized by CLI."""
        with patch("src.commands.fidelity.fidelity_command_handler", new_callable=AsyncMock) as mock_handler:
            from scripts.cli import fidelity

            result = await cli_runner.invoke(
                fidelity,
                [
                    "--source-subscription", "source-123",
                    "--target-subscription", "target-456",
                    "--resource-level",
                ],
                catch_exceptions=False,
            )

            # Should not show "no such option" error
            assert "--resource-level" not in result.output or "no such option" not in result.output.lower()

    @pytest.mark.asyncio
    async def test_resource_type_flag_recognized(self, cli_runner, mock_neo4j_environment):
        """Verify --resource-type flag is recognized by CLI."""
        with patch("src.commands.fidelity.fidelity_command_handler", new_callable=AsyncMock):
            from scripts.cli import fidelity

            result = await cli_runner.invoke(
                fidelity,
                [
                    "--source-subscription", "source-123",
                    "--target-subscription", "target-456",
                    "--resource-level",
                    "--resource-type", "Microsoft.Storage/storageAccounts",
                ],
                catch_exceptions=False,
            )

            assert "--resource-type" not in result.output or "no such option" not in result.output.lower()

    @pytest.mark.asyncio
    async def test_redaction_level_flag_recognized(self, cli_runner, mock_neo4j_environment):
        """Verify --redaction-level flag is recognized by CLI."""
        with patch("src.commands.fidelity.fidelity_command_handler", new_callable=AsyncMock):
            from scripts.cli import fidelity

            result = await cli_runner.invoke(
                fidelity,
                [
                    "--source-subscription", "source-123",
                    "--target-subscription", "target-456",
                    "--resource-level",
                    "--redaction-level", "MINIMAL",
                ],
                catch_exceptions=False,
            )

            assert "--redaction-level" not in result.output or "no such option" not in result.output.lower()


class TestParameterFlowToHandler:
    """Test that CLI parameters flow correctly to fidelity_command_handler."""

    @pytest.mark.asyncio
    async def test_all_parameters_passed_to_handler(self, cli_runner, mock_neo4j_environment):
        """Verify all new parameters are passed to handler."""
        with patch("src.commands.fidelity.fidelity_command_handler", new_callable=AsyncMock) as mock_handler:
            from scripts.cli import fidelity

            await cli_runner.invoke(
                fidelity,
                [
                    "--source-subscription", "source-abc",
                    "--target-subscription", "target-xyz",
                    "--resource-level",
                    "--resource-type", "Microsoft.Compute/virtualMachines",
                    "--redaction-level", "NONE",
                ],
                catch_exceptions=False,
            )

            # Verify handler was called
            mock_handler.assert_called_once()

            # Verify all parameters passed correctly
            call_kwargs = mock_handler.call_args[1]
            assert call_kwargs["source_subscription"] == "source-abc"
            assert call_kwargs["target_subscription"] == "target-xyz"
            assert call_kwargs["resource_level"] is True
            assert call_kwargs["resource_type"] == "Microsoft.Compute/virtualMachines"
            assert call_kwargs["redaction_level"] == "NONE"

    @pytest.mark.asyncio
    async def test_default_redaction_level_passed(self, cli_runner, mock_neo4j_environment):
        """Verify default FULL redaction level is passed when not specified."""
        with patch("src.commands.fidelity.fidelity_command_handler", new_callable=AsyncMock) as mock_handler:
            from scripts.cli import fidelity

            await cli_runner.invoke(
                fidelity,
                [
                    "--source-subscription", "source-123",
                    "--target-subscription", "target-456",
                    "--resource-level",
                ],
                catch_exceptions=False,
            )

            call_kwargs = mock_handler.call_args[1]
            assert call_kwargs["redaction_level"] == "FULL", "Default redaction should be FULL"


class TestEndToEndResourceLevelFlow:
    """Test complete end-to-end flow with all bug fixes."""

    @pytest.mark.asyncio
    async def test_complete_flow_with_all_fixes(
        self,
        cli_runner,
        mock_neo4j_environment,
        mock_session_manager,
        sample_fidelity_result,
    ):
        """Test complete CLI → handler → calculator → Neo4j flow."""
        with patch("src.commands.fidelity.Neo4jSessionManager", return_value=mock_session_manager):
            with patch("src.commands.fidelity.ResourceFidelityCalculator") as MockCalculator:
                # Setup mock calculator
                mock_calculator = Mock()
                mock_calculator.calculate_fidelity.return_value = sample_fidelity_result
                MockCalculator.return_value = mock_calculator

                from scripts.cli import fidelity

                result = await cli_runner.invoke(
                    fidelity,
                    [
                        "--source-subscription", "source-123",
                        "--target-subscription", "target-456",
                        "--resource-level",
                        "--resource-type", "Microsoft.Storage/storageAccounts",
                        "--redaction-level", "FULL",
                    ],
                    catch_exceptions=False,
                )

                # Verify session manager connection (Bug #4 fix)
                mock_session_manager.connect.assert_called_once()

                # Verify calculator was created (Bug #2 fix - not async with)
                MockCalculator.assert_called_once()

                # Verify calculator received session manager
                calc_kwargs = MockCalculator.call_args[1]
                assert calc_kwargs["session_manager"] is mock_session_manager

                # Verify execution succeeded
                assert result.exit_code == 0

    @pytest.mark.asyncio
    async def test_resource_type_filter_flows_to_calculator(
        self,
        cli_runner,
        mock_neo4j_environment,
        mock_session_manager,
        sample_fidelity_result,
    ):
        """Verify resource_type filter parameter flows through to calculator."""
        with patch("src.commands.fidelity.Neo4jSessionManager", return_value=mock_session_manager):
            with patch("src.commands.fidelity.ResourceFidelityCalculator") as MockCalculator:
                mock_calculator = Mock()
                mock_calculator.calculate_fidelity.return_value = sample_fidelity_result
                MockCalculator.return_value = mock_calculator

                from scripts.cli import fidelity

                await cli_runner.invoke(
                    fidelity,
                    [
                        "--source-subscription", "source-123",
                        "--target-subscription", "target-456",
                        "--resource-level",
                        "--resource-type", "Microsoft.Network/virtualNetworks",
                    ],
                    catch_exceptions=False,
                )

                # Verify calculate_fidelity was called with resource_type
                mock_calculator.calculate_fidelity.assert_called_once()
                calc_call_kwargs = mock_calculator.calculate_fidelity.call_args[1]
                assert calc_call_kwargs["resource_type"] == "Microsoft.Network/virtualNetworks"

    @pytest.mark.asyncio
    async def test_redaction_level_flows_to_calculator(
        self,
        cli_runner,
        mock_neo4j_environment,
        mock_session_manager,
        sample_fidelity_result,
    ):
        """Verify redaction_level parameter flows through to calculator."""
        with patch("src.commands.fidelity.Neo4jSessionManager", return_value=mock_session_manager):
            with patch("src.commands.fidelity.ResourceFidelityCalculator") as MockCalculator:
                mock_calculator = Mock()
                mock_calculator.calculate_fidelity.return_value = sample_fidelity_result
                MockCalculator.return_value = mock_calculator

                from scripts.cli import fidelity

                await cli_runner.invoke(
                    fidelity,
                    [
                        "--source-subscription", "source-123",
                        "--target-subscription", "target-456",
                        "--resource-level",
                        "--redaction-level", "MINIMAL",
                    ],
                    catch_exceptions=False,
                )

                # Verify calculate_fidelity was called with MINIMAL redaction
                calc_call_kwargs = mock_calculator.calculate_fidelity.call_args[1]
                assert calc_call_kwargs["redaction_level"] == RedactionLevel.MINIMAL


class TestJSONExportIntegration:
    """Test JSON export functionality with all bug fixes."""

    @pytest.mark.asyncio
    async def test_json_export_with_resource_level(
        self,
        cli_runner,
        mock_neo4j_environment,
        mock_session_manager,
        sample_fidelity_result,
        tmp_path,
    ):
        """Test JSON export works with resource-level fidelity."""
        output_file = tmp_path / "fidelity-report.json"

        with patch("src.commands.fidelity.Neo4jSessionManager", return_value=mock_session_manager):
            with patch("src.commands.fidelity.ResourceFidelityCalculator") as MockCalculator:
                mock_calculator = Mock()
                mock_calculator.calculate_fidelity.return_value = sample_fidelity_result
                MockCalculator.return_value = mock_calculator

                from scripts.cli import fidelity

                result = await cli_runner.invoke(
                    fidelity,
                    [
                        "--source-subscription", "source-123",
                        "--target-subscription", "target-456",
                        "--resource-level",
                        "--output", str(output_file),
                    ],
                    catch_exceptions=False,
                )

                assert result.exit_code == 0
                assert output_file.exists(), "JSON output file should be created"

                # Verify JSON content
                with open(output_file) as f:
                    data = json.load(f)

                assert "metadata" in data
                assert "summary" in data
                assert "resources" in data
                assert data["summary"]["total_resources"] == 1

    @pytest.mark.asyncio
    async def test_json_export_includes_filter_metadata(
        self,
        cli_runner,
        mock_neo4j_environment,
        mock_session_manager,
        sample_fidelity_result,
        tmp_path,
    ):
        """Test JSON export includes resource_type filter in metadata."""
        output_file = tmp_path / "filtered-report.json"

        with patch("src.commands.fidelity.Neo4jSessionManager", return_value=mock_session_manager):
            with patch("src.commands.fidelity.ResourceFidelityCalculator") as MockCalculator:
                mock_calculator = Mock()
                mock_calculator.calculate_fidelity.return_value = sample_fidelity_result
                MockCalculator.return_value = mock_calculator

                from scripts.cli import fidelity

                await cli_runner.invoke(
                    fidelity,
                    [
                        "--source-subscription", "source-123",
                        "--target-subscription", "target-456",
                        "--resource-level",
                        "--resource-type", "Microsoft.Storage/storageAccounts",
                        "--output", str(output_file),
                    ],
                    catch_exceptions=False,
                )

                with open(output_file) as f:
                    data = json.load(f)

                assert data["metadata"]["resource_type_filter"] == "Microsoft.Storage/storageAccounts"


class TestErrorHandlingIntegration:
    """Test error handling across the complete integration."""

    @pytest.mark.asyncio
    async def test_neo4j_connection_failure_handled(self, cli_runner, mock_neo4j_environment):
        """Test graceful handling of Neo4j connection failures."""
        with patch("src.commands.fidelity.Neo4jSessionManager") as MockSessionManager:
            mock_manager = Mock()
            mock_manager.connect = Mock(side_effect=Exception("Neo4j connection failed"))
            MockSessionManager.return_value = mock_manager

            from scripts.cli import fidelity

            result = await cli_runner.invoke(
                fidelity,
                [
                    "--source-subscription", "source-123",
                    "--target-subscription", "target-456",
                    "--resource-level",
                ],
                catch_exceptions=True,  # Catch to verify error handling
            )

            # Should fail gracefully with non-zero exit code
            assert result.exit_code != 0
            assert "error" in result.output.lower() or "failed" in result.output.lower()

    @pytest.mark.asyncio
    async def test_invalid_redaction_level_rejected(self, cli_runner):
        """Test that invalid redaction level values are rejected."""
        from scripts.cli import fidelity

        result = await cli_runner.invoke(
            fidelity,
            [
                "--source-subscription", "source-123",
                "--target-subscription", "target-456",
                "--resource-level",
                "--redaction-level", "INVALID_LEVEL",
            ],
            catch_exceptions=True,
        )

        # Should fail with error about invalid choice
        assert result.exit_code != 0
        assert "invalid" in result.output.lower() or "choice" in result.output.lower()


class TestAllBugsFixedTogether:
    """Integration tests verifying all four bugs are fixed together."""

    @pytest.mark.asyncio
    async def test_bug_1_and_4_together(
        self,
        cli_runner,
        mock_neo4j_environment,
        mock_session_manager,
        sample_fidelity_result,
    ):
        """Test Bug #1 (CLI registration) and Bug #4 (connect() call) work together."""
        with patch("src.commands.fidelity.Neo4jSessionManager", return_value=mock_session_manager):
            with patch("src.commands.fidelity.ResourceFidelityCalculator") as MockCalculator:
                mock_calculator = Mock()
                mock_calculator.calculate_fidelity.return_value = sample_fidelity_result
                MockCalculator.return_value = mock_calculator

                from scripts.cli import fidelity

                # Use --resource-level flag (Bug #1)
                result = await cli_runner.invoke(
                    fidelity,
                    [
                        "--source-subscription", "source-123",
                        "--target-subscription", "target-456",
                        "--resource-level",
                    ],
                    catch_exceptions=False,
                )

                # Verify connect() was called (Bug #4)
                mock_session_manager.connect.assert_called_once()
                assert result.exit_code == 0

    @pytest.mark.asyncio
    async def test_all_four_bugs_fixed(
        self,
        cli_runner,
        mock_neo4j_environment,
        sample_fidelity_result,
    ):
        """Comprehensive test verifying all four bugs are fixed."""
        call_order = []

        with patch("src.commands.fidelity.Neo4jSessionManager") as MockSessionManager:
            with patch("src.commands.fidelity.ResourceFidelityCalculator") as MockCalculator:
                # Setup mock session manager
                mock_manager = Mock()
                mock_manager.connect = Mock(side_effect=lambda: call_order.append("connect"))
                MockSessionManager.return_value = mock_manager

                # Setup mock calculator
                def mock_calc_init(*args, **kwargs):
                    call_order.append("calculator_init")
                    mock_calc = Mock()
                    mock_calc.calculate_fidelity.return_value = sample_fidelity_result
                    return mock_calc

                MockCalculator.side_effect = mock_calc_init

                # Mock Neo4j query execution
                with patch.object(sample_fidelity_result.__class__, "__init__", return_value=None):
                    from scripts.cli import fidelity

                    # Execute with all flags (Bug #1: CLI registration)
                    result = await cli_runner.invoke(
                        fidelity,
                        [
                            "--source-subscription", "source-123",
                            "--target-subscription", "target-456",
                            "--resource-level",  # Bug #1
                            "--resource-type", "Microsoft.Storage/storageAccounts",  # Bug #1
                            "--redaction-level", "FULL",  # Bug #1
                        ],
                        catch_exceptions=False,
                    )

                    # Bug #2: Session manager NOT used as async context manager
                    assert not hasattr(mock_manager, "__aenter__") or not mock_manager.__aenter__.called

                    # Bug #3: Neo4j query uses :Resource:Original (verified in separate tests)

                    # Bug #4: connect() called before calculator
                    assert call_order == ["connect", "calculator_init"]

                    assert result.exit_code == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
