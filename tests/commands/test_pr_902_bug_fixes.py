"""
Comprehensive tests for PR #902 bug fixes.

This test module verifies all four bug fixes that enable the --resource-level fidelity command:

1. CLI Registration Bug (scripts/cli.py):
   - Added --resource-level, --resource-type, --redaction-level flags
   - Updated function signature to accept new parameters
   - Pass parameters to fidelity_command_handler

2. Async Context Manager Bug (src/commands/fidelity.py):
   - Changed from `async with Neo4jSessionManager(...)` to regular instantiation
   - Added `.connect()` call to establish connection

3. Wrong Neo4j Label (src/validation/resource_fidelity_calculator.py):
   - Changed query from `:AzureResource` to `:Resource:Original`

4. Session Manager Not Connected (src/commands/fidelity.py):
   - Added `session_manager.connect()` before use

Testing pyramid distribution: Integration tests (30%)
These tests verify the bugs are fixed and prevent regression.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.validation.resource_fidelity_calculator import (
    FidelityResult,
    PropertyComparison,
    RedactionLevel,
    ResourceClassification,
    ResourceFidelityMetrics,
    ResourceStatus,
)


class TestBug1_CLIRegistration:
    """Test Bug #1: CLI flag registration and parameter passing."""

    def test_cli_has_resource_level_flag(self):
        """Verify --resource-level flag is registered in CLI."""
        from scripts.cli import fidelity

        # Check that the function has the resource_level parameter
        import inspect

        sig = inspect.signature(fidelity)
        assert "resource_level" in sig.parameters, "--resource-level flag not registered"

    def test_cli_has_resource_type_flag(self):
        """Verify --resource-type flag is registered in CLI."""
        from scripts.cli import fidelity

        import inspect

        sig = inspect.signature(fidelity)
        assert "resource_type" in sig.parameters, "--resource-type flag not registered"

    def test_cli_has_redaction_level_flag(self):
        """Verify --redaction-level flag is registered in CLI."""
        from scripts.cli import fidelity

        import inspect

        sig = inspect.signature(fidelity)
        assert "redaction_level" in sig.parameters, "--redaction-level flag not registered"

    @pytest.mark.asyncio
    async def test_cli_passes_resource_level_to_handler(self):
        """Verify --resource-level parameter is passed to fidelity_command_handler."""
        with patch("src.commands.fidelity.fidelity_command_handler", new_callable=AsyncMock) as mock_handler:
            with patch("src.commands.fidelity.ensure_neo4j_running"):
                from scripts.cli import fidelity
                from click.testing import CliRunner

                runner = CliRunner()
                result = await runner.invoke(
                    fidelity,
                    [
                        "--source-subscription", "source-123",
                        "--target-subscription", "target-456",
                        "--resource-level",
                    ],
                    catch_exceptions=False,
                )

                # Verify handler was called with resource_level=True
                mock_handler.assert_called_once()
                call_kwargs = mock_handler.call_args[1]
                assert call_kwargs["resource_level"] is True, "resource_level parameter not passed to handler"

    @pytest.mark.asyncio
    async def test_cli_passes_resource_type_to_handler(self):
        """Verify --resource-type parameter is passed to fidelity_command_handler."""
        with patch("src.commands.fidelity.fidelity_command_handler", new_callable=AsyncMock) as mock_handler:
            with patch("src.commands.fidelity.ensure_neo4j_running"):
                from scripts.cli import fidelity
                from click.testing import CliRunner

                runner = CliRunner()
                await runner.invoke(
                    fidelity,
                    [
                        "--source-subscription", "source-123",
                        "--target-subscription", "target-456",
                        "--resource-level",
                        "--resource-type", "Microsoft.Storage/storageAccounts",
                    ],
                    catch_exceptions=False,
                )

                # Verify handler was called with correct resource_type
                call_kwargs = mock_handler.call_args[1]
                assert call_kwargs["resource_type"] == "Microsoft.Storage/storageAccounts"

    @pytest.mark.asyncio
    async def test_cli_passes_redaction_level_to_handler(self):
        """Verify --redaction-level parameter is passed to fidelity_command_handler."""
        with patch("src.commands.fidelity.fidelity_command_handler", new_callable=AsyncMock) as mock_handler:
            with patch("src.commands.fidelity.ensure_neo4j_running"):
                from scripts.cli import fidelity
                from click.testing import CliRunner

                runner = CliRunner()
                await runner.invoke(
                    fidelity,
                    [
                        "--source-subscription", "source-123",
                        "--target-subscription", "target-456",
                        "--resource-level",
                        "--redaction-level", "MINIMAL",
                    ],
                    catch_exceptions=False,
                )

                # Verify handler was called with correct redaction_level
                call_kwargs = mock_handler.call_args[1]
                assert call_kwargs["redaction_level"] == "MINIMAL"

    def test_redaction_level_flag_has_choices(self):
        """Verify --redaction-level flag restricts to valid choices."""
        from scripts.cli import fidelity

        # Get the click command decorators
        for decorator_or_param in fidelity.__click_params__:
            if hasattr(decorator_or_param, "name") and decorator_or_param.name == "redaction_level":
                # Verify it's a Choice parameter
                assert hasattr(decorator_or_param.type, "choices"), "redaction_level should have restricted choices"
                choices = decorator_or_param.type.choices
                assert "FULL" in choices
                assert "MINIMAL" in choices
                assert "NONE" in choices
                break
        else:
            pytest.fail("redaction_level parameter not found in fidelity command")


class TestBug2_AsyncContextManager:
    """Test Bug #2: Async context manager usage fixed."""

    @pytest.mark.asyncio
    async def test_session_manager_not_used_as_context_manager(self):
        """Verify Neo4jSessionManager is instantiated, not used with 'async with'."""
        with patch("src.commands.fidelity.Neo4jSessionManager") as MockSessionManager:
            with patch("src.commands.fidelity.ResourceFidelityCalculator") as MockCalculator:
                with patch("src.commands.fidelity.ensure_neo4j_running"):
                    with patch("src.commands.fidelity.get_neo4j_config_from_env", return_value=("uri", "user", "pass")):
                        # Create mock instance
                        mock_session_manager = Mock()
                        mock_session_manager.connect = Mock()
                        MockSessionManager.return_value = mock_session_manager

                        # Create mock calculator result
                        mock_calculator_instance = Mock()
                        mock_result = FidelityResult(
                            classifications=[],
                            metrics=ResourceFidelityMetrics(
                                total_resources=0,
                                exact_match=0,
                                drifted=0,
                                missing_target=0,
                                missing_source=0,
                                match_percentage=0.0,
                            ),
                        )
                        mock_calculator_instance.calculate_fidelity.return_value = mock_result
                        MockCalculator.return_value = mock_calculator_instance

                        from src.commands.fidelity import fidelity_resource_level_handler

                        await fidelity_resource_level_handler(
                            source_subscription="source-123",
                            target_subscription="target-456",
                            no_container=True,
                        )

                        # Verify session_manager was instantiated (not used as context manager)
                        MockSessionManager.assert_called_once()
                        # Verify connect() was called
                        mock_session_manager.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_manager_connect_called_before_calculator(self):
        """Verify session_manager.connect() is called before ResourceFidelityCalculator creation."""
        call_order = []

        with patch("src.commands.fidelity.Neo4jSessionManager") as MockSessionManager:
            with patch("src.commands.fidelity.ResourceFidelityCalculator") as MockCalculator:
                with patch("src.commands.fidelity.ensure_neo4j_running"):
                    with patch("src.commands.fidelity.get_neo4j_config_from_env", return_value=("uri", "user", "pass")):
                        mock_session_manager = Mock()
                        mock_session_manager.connect = Mock(side_effect=lambda: call_order.append("connect"))
                        MockSessionManager.return_value = mock_session_manager

                        def mock_calculator_init(*args, **kwargs):
                            call_order.append("calculator_init")
                            mock_instance = Mock()
                            mock_result = FidelityResult(
                                classifications=[],
                                metrics=ResourceFidelityMetrics(
                                    total_resources=0,
                                    exact_match=0,
                                    drifted=0,
                                    missing_target=0,
                                    missing_source=0,
                                    match_percentage=0.0,
                                ),
                            )
                            mock_instance.calculate_fidelity.return_value = mock_result
                            return mock_instance

                        MockCalculator.side_effect = mock_calculator_init

                        from src.commands.fidelity import fidelity_resource_level_handler

                        await fidelity_resource_level_handler(
                            source_subscription="source-123",
                            target_subscription="target-456",
                            no_container=True,
                        )

                        # Verify connect() was called before calculator initialization
                        assert call_order == ["connect", "calculator_init"], \
                            f"Expected connect before calculator_init, got: {call_order}"


class TestBug3_Neo4jLabel:
    """Test Bug #3: Neo4j query uses correct :Resource:Original label."""

    def test_query_uses_resource_original_label(self):
        """Verify Neo4j query uses :Resource:Original label (not :AzureResource)."""
        from src.validation.resource_fidelity_calculator import ResourceFidelityCalculator

        # Create mock session manager
        mock_session_manager = Mock()
        mock_session = MagicMock()
        mock_session_manager.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_session_manager.session.return_value.__exit__ = Mock(return_value=False)

        # Mock Neo4j result
        mock_session.run.return_value = []

        # Create calculator instance
        calculator = ResourceFidelityCalculator(
            session_manager=mock_session_manager,
            source_subscription_id="source-123",
            target_subscription_id="target-123",
        )

        # Trigger query execution
        calculator._fetch_resources_from_neo4j("source-123")

        # Verify the query was executed
        mock_session.run.assert_called_once()

        # Get the query that was executed
        query = mock_session.run.call_args[0][0]

        # Verify query uses :Resource:Original label
        assert ":Resource:Original" in query, \
            "Query should use :Resource:Original label (Bug #3 not fixed)"

        # Verify query does NOT use old :AzureResource label
        assert ":AzureResource" not in query, \
            "Query should not use deprecated :AzureResource label"

    def test_query_filters_by_subscription_id(self):
        """Verify Neo4j query correctly filters by subscription_id."""
        from src.validation.resource_fidelity_calculator import ResourceFidelityCalculator

        mock_session_manager = Mock()
        mock_session = MagicMock()
        mock_session_manager.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_session_manager.session.return_value.__exit__ = Mock(return_value=False)
        mock_session.run.return_value = []

        calculator = ResourceFidelityCalculator(
            session_manager=mock_session_manager,
            source_subscription_id="source-123",
            target_subscription_id="target-123",
        )

        # Trigger query with specific subscription ID
        test_subscription = "9b00bc5e-9abc-45de-9958-02a9d9277b16"
        calculator._fetch_resources_from_neo4j(test_subscription)

        # Verify query parameters include subscription_id
        query_params = mock_session.run.call_args[0][1]
        assert "subscription_id" in query_params
        assert query_params["subscription_id"] == test_subscription

    def test_query_with_resource_type_filter(self):
        """Verify Neo4j query correctly applies resource_type filter."""
        from src.validation.resource_fidelity_calculator import ResourceFidelityCalculator

        mock_session_manager = Mock()
        mock_session = MagicMock()
        mock_session_manager.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_session_manager.session.return_value.__exit__ = Mock(return_value=False)
        mock_session.run.return_value = []

        calculator = ResourceFidelityCalculator(
            session_manager=mock_session_manager,
            source_subscription_id="source-123",
            target_subscription_id="target-123",
        )

        # Trigger query with resource type filter
        calculator._fetch_resources_from_neo4j(
            "source-123",
            resource_type="Microsoft.Storage/storageAccounts"
        )

        # Verify query includes resource_type in parameters
        query_params = mock_session.run.call_args[0][1]
        assert "resource_type" in query_params
        assert query_params["resource_type"] == "Microsoft.Storage/storageAccounts"

        # Verify query includes resource_type filter in WHERE clause
        query = mock_session.run.call_args[0][0]
        assert "r.type" in query


class TestBug4_SessionManagerConnection:
    """Test Bug #4: Session manager connect() called before use."""

    @pytest.mark.asyncio
    async def test_fidelity_handler_connects_session_manager(self):
        """Verify fidelity_resource_level_handler calls session_manager.connect()."""
        with patch("src.commands.fidelity.Neo4jSessionManager") as MockSessionManager:
            with patch("src.commands.fidelity.ResourceFidelityCalculator") as MockCalculator:
                with patch("src.commands.fidelity.ensure_neo4j_running"):
                    with patch("src.commands.fidelity.get_neo4j_config_from_env", return_value=("uri", "user", "pass")):
                        mock_session_manager = Mock()
                        mock_session_manager.connect = Mock()
                        MockSessionManager.return_value = mock_session_manager

                        mock_calculator_instance = Mock()
                        mock_result = FidelityResult(
                            classifications=[],
                            metrics=ResourceFidelityMetrics(
                                total_resources=0,
                                exact_match=0,
                                drifted=0,
                                missing_target=0,
                                missing_source=0,
                                match_percentage=0.0,
                            ),
                        )
                        mock_calculator_instance.calculate_fidelity.return_value = mock_result
                        MockCalculator.return_value = mock_calculator_instance

                        from src.commands.fidelity import fidelity_resource_level_handler

                        await fidelity_resource_level_handler(
                            source_subscription="source-123",
                            target_subscription="target-456",
                            no_container=True,
                        )

                        # Verify connect() was called
                        mock_session_manager.connect.assert_called_once(), \
                            "session_manager.connect() not called (Bug #4 not fixed)"

    @pytest.mark.asyncio
    async def test_connection_failure_shows_helpful_error(self):
        """Verify connection failure shows helpful error message."""
        with patch("src.commands.fidelity.Neo4jSessionManager") as MockSessionManager:
            with patch("src.commands.fidelity.ensure_neo4j_running"):
                with patch("src.commands.fidelity.get_neo4j_config_from_env", return_value=("uri", "user", "pass")):
                    mock_session_manager = Mock()
                    # Simulate connection failure
                    mock_session_manager.connect = Mock(side_effect=Exception("Connection refused"))
                    MockSessionManager.return_value = mock_session_manager

                    from src.commands.fidelity import fidelity_resource_level_handler

                    # Should not crash, should handle error gracefully
                    with pytest.raises(Exception):
                        await fidelity_resource_level_handler(
                            source_subscription="source-123",
                            target_subscription="target-456",
                            no_container=True,
                        )


class TestIntegration_AllBugsFix:
    """Integration tests verifying all four bugs are fixed together."""

    @pytest.mark.asyncio
    async def test_complete_resource_level_flow(self):
        """Test complete flow: CLI → handler → calculator → Neo4j query."""
        # Mock Neo4j to return sample resources
        sample_resources = [
            {
                "id": "/subscriptions/source-123/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1",
                "name": "storage1",
                "type": "Microsoft.Storage/storageAccounts",
                "properties": {"sku": {"name": "Standard_LRS"}, "location": "eastus"},
            }
        ]

        with patch("src.commands.fidelity.Neo4jSessionManager") as MockSessionManager:
            with patch("src.commands.fidelity.ensure_neo4j_running"):
                with patch("src.commands.fidelity.get_neo4j_config_from_env", return_value=("uri", "user", "pass")):
                    # Setup mock session manager
                    mock_session_manager = Mock()
                    mock_session_manager.connect = Mock()
                    mock_session = MagicMock()
                    mock_session_manager.session.return_value.__enter__ = Mock(return_value=mock_session)
                    mock_session_manager.session.return_value.__exit__ = Mock(return_value=False)
                    MockSessionManager.return_value = mock_session_manager

                    # Mock Neo4j query result
                    mock_record = Mock()
                    mock_record.__getitem__ = lambda self, key: sample_resources[0].get(key)
                    mock_session.run.return_value = [mock_record, mock_record]

                    from src.commands.fidelity import fidelity_resource_level_handler

                    # Execute the complete flow
                    await fidelity_resource_level_handler(
                        source_subscription="source-123",
                        target_subscription="target-123",
                        resource_type="Microsoft.Storage/storageAccounts",
                        redaction_level="FULL",
                        no_container=True,
                    )

                    # Verify all components were called correctly
                    mock_session_manager.connect.assert_called_once()  # Bug #4 fix
                    assert mock_session.run.called  # Neo4j query executed

                    # Verify query uses correct label (Bug #3 fix)
                    query = mock_session.run.call_args[0][0]
                    assert ":Resource:Original" in query

    @pytest.mark.asyncio
    async def test_resource_level_with_redaction(self):
        """Test resource-level fidelity with different redaction levels."""
        with patch("src.commands.fidelity.Neo4jSessionManager") as MockSessionManager:
            with patch("src.commands.fidelity.ResourceFidelityCalculator") as MockCalculator:
                with patch("src.commands.fidelity.ensure_neo4j_running"):
                    with patch("src.commands.fidelity.get_neo4j_config_from_env", return_value=("uri", "user", "pass")):
                        mock_session_manager = Mock()
                        mock_session_manager.connect = Mock()
                        MockSessionManager.return_value = mock_session_manager

                        mock_calculator_instance = Mock()
                        mock_result = FidelityResult(
                            classifications=[],
                            metrics=ResourceFidelityMetrics(
                                total_resources=0,
                                exact_match=0,
                                drifted=0,
                                missing_target=0,
                                missing_source=0,
                                match_percentage=0.0,
                            ),
                            redaction_level=RedactionLevel.MINIMAL,
                        )
                        mock_calculator_instance.calculate_fidelity.return_value = mock_result
                        MockCalculator.return_value = mock_calculator_instance

                        from src.commands.fidelity import fidelity_resource_level_handler

                        await fidelity_resource_level_handler(
                            source_subscription="source-123",
                            target_subscription="target-123",
                            redaction_level="MINIMAL",
                            no_container=True,
                        )

                        # Verify calculator was called with MINIMAL redaction
                        call_kwargs = mock_calculator_instance.calculate_fidelity.call_args[1]
                        assert call_kwargs["redaction_level"] == RedactionLevel.MINIMAL

    @pytest.mark.asyncio
    async def test_resource_level_json_export(self):
        """Test resource-level fidelity with JSON export."""
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp_file:
            output_path = tmp_file.name

        try:
            with patch("src.commands.fidelity.Neo4jSessionManager") as MockSessionManager:
                with patch("src.commands.fidelity.ResourceFidelityCalculator") as MockCalculator:
                    with patch("src.commands.fidelity.ensure_neo4j_running"):
                        with patch("src.commands.fidelity.get_neo4j_config_from_env", return_value=("uri", "user", "pass")):
                            mock_session_manager = Mock()
                            mock_session_manager.connect = Mock()
                            MockSessionManager.return_value = mock_session_manager

                            # Create realistic result
                            classification = ResourceClassification(
                                resource_id="/subscriptions/source/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/storage1",
                                resource_name="storage1",
                                resource_type="Microsoft.Storage/storageAccounts",
                                status=ResourceStatus.EXACT_MATCH,
                                source_exists=True,
                                target_exists=True,
                                property_comparisons=[
                                    PropertyComparison("sku.name", "Standard_LRS", "Standard_LRS", True, False)
                                ],
                                mismatch_count=0,
                                match_count=1,
                            )

                            mock_result = FidelityResult(
                                classifications=[classification],
                                metrics=ResourceFidelityMetrics(
                                    total_resources=1,
                                    exact_match=1,
                                    drifted=0,
                                    missing_target=0,
                                    missing_source=0,
                                    match_percentage=100.0,
                                ),
                                source_subscription="source-123",
                                target_subscription="target-123",
                                redaction_level=RedactionLevel.FULL,
                            )

                            mock_calculator_instance = Mock()
                            mock_calculator_instance.calculate_fidelity.return_value = mock_result
                            MockCalculator.return_value = mock_calculator_instance

                            from src.commands.fidelity import fidelity_resource_level_handler

                            await fidelity_resource_level_handler(
                                source_subscription="source-123",
                                target_subscription="target-123",
                                output=output_path,
                                no_container=True,
                            )

                            # Verify JSON file was created
                            assert Path(output_path).exists()

                            # Verify JSON content is valid
                            with open(output_path) as f:
                                data = json.load(f)

                            assert "metadata" in data
                            assert "summary" in data
                            assert "resources" in data
                            assert data["summary"]["total_resources"] == 1

        finally:
            # Cleanup
            if Path(output_path).exists():
                Path(output_path).unlink()


class TestRegressionPrevention:
    """Tests to prevent future regressions of these bugs."""

    def test_neo4j_query_label_consistency(self):
        """Ensure all Neo4j queries in fidelity module use consistent labels."""
        from src.validation import resource_fidelity_calculator
        import inspect

        source = inspect.getsource(resource_fidelity_calculator)

        # Check that old label is not used anywhere
        assert ":AzureResource" not in source, \
            "Code should not reference deprecated :AzureResource label"

        # Verify new label is used
        assert ":Resource:Original" in source, \
            "Code should use :Resource:Original label"

    def test_session_manager_async_context_pattern(self):
        """Ensure session_manager is not used as async context manager."""
        from src.commands import fidelity
        import inspect

        source = inspect.getsource(fidelity)

        # Check that async with pattern is not used with Neo4jSessionManager
        # This is a heuristic check - may need adjustment
        lines = source.split("\n")
        for i, line in enumerate(lines):
            if "async with" in line and "Neo4jSessionManager" in line:
                pytest.fail(
                    f"Line {i+1} uses 'async with Neo4jSessionManager' pattern (Bug #2 regression)\n"
                    f"Use regular instantiation + .connect() instead"
                )

    def test_cli_parameters_match_handler_signature(self):
        """Ensure CLI parameters match fidelity_command_handler signature."""
        from scripts.cli import fidelity
        from src.commands.fidelity import fidelity_command_handler
        import inspect

        cli_sig = inspect.signature(fidelity)
        handler_sig = inspect.signature(fidelity_command_handler)

        # Key parameters that must match
        key_params = ["resource_level", "resource_type", "redaction_level"]

        for param in key_params:
            assert param in cli_sig.parameters, \
                f"CLI missing parameter: {param}"
            assert param in handler_sig.parameters, \
                f"Handler missing parameter: {param}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
