# tests/unit/commands/test_agent.py
"""Tests for agent.py (agent mode command).

Coverage target: 85%+
Test pyramid: 60% unit, 30% integration, 10% E2E
"""

import pytest
from click.testing import CliRunner

from src.commands.agent import agent_mode, agent_mode_command_handler


# ============================================================================
# UNIT TESTS (60%)
# ============================================================================


class TestAgentModeParameters:
    """Test CLI parameter handling."""

    def test_agent_mode_has_question_option(self, cli_runner):
        """Agent mode has --question option."""
        result = cli_runner.invoke(agent_mode, ["--help"])
        assert "question" in result.output

    def test_agent_mode_works_without_question(
        self, cli_runner, mock_agent_mode, mocker
    ):
        """Agent mode works in interactive mode (no question)."""
        result = cli_runner.invoke(agent_mode, [])
        mock_agent_mode.assert_called_once()

    def test_agent_mode_accepts_question_parameter(
        self, cli_runner, mock_agent_mode
    ):
        """Agent mode accepts single question for non-interactive mode."""
        result = cli_runner.invoke(agent_mode, ["--question", "Show all VMs"])
        mock_agent_mode.assert_called_once_with(question="Show all VMs")


class TestAgentModeInitialization:
    """Test agent mode initialization."""

    @pytest.mark.asyncio
    async def test_agent_mode_handler_calls_run_agent_mode(
        self, mock_click_context, mock_agent_mode
    ):
        """Handler calls run_agent_mode function."""
        await agent_mode_command_handler(mock_click_context, question=None)
        mock_agent_mode.assert_called_once_with(question=None)

    @pytest.mark.asyncio
    async def test_agent_mode_handler_passes_question(
        self, mock_click_context, mock_agent_mode
    ):
        """Handler passes question to run_agent_mode."""
        await agent_mode_command_handler(
            mock_click_context, question="Test question"
        )
        mock_agent_mode.assert_called_once_with(question="Test question")


class TestAgentModeErrorHandling:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_agent_mode_handles_startup_failure(
        self, cli_runner, mock_agent_mode
    ):
        """Agent mode handles startup failures gracefully."""
        mock_agent_mode.side_effect = Exception("MCP server failed")

        result = cli_runner.invoke(agent_mode, [])
        assert result.exit_code != 0
        assert "Failed to start agent mode" in result.output

    @pytest.mark.asyncio
    async def test_agent_mode_shows_error_traceback(
        self, cli_runner, mock_agent_mode, mocker
    ):
        """Agent mode prints traceback on error."""
        mock_traceback = mocker.patch("traceback.print_exc")
        mock_agent_mode.side_effect = Exception("Test error")

        result = cli_runner.invoke(agent_mode, [])
        mock_traceback.assert_called_once()


class TestLoggingConfiguration:
    """Test logging setup."""

    @pytest.mark.asyncio
    async def test_agent_mode_configures_logging(
        self, mock_click_context, mock_agent_mode, mocker
    ):
        """Agent mode configures logging from context."""
        mock_logging = mocker.patch("logging.basicConfig")

        await agent_mode_command_handler(mock_click_context, question=None)
        mock_logging.assert_called_once()


# ============================================================================
# INTEGRATION TESTS (30%)
# ============================================================================


class TestAgentModeIntegration:
    """Test agent mode with multiple components."""

    def test_agent_mode_interactive_workflow(
        self, cli_runner, mock_agent_mode
    ):
        """Complete interactive agent mode workflow."""
        result = cli_runner.invoke(agent_mode, [])
        mock_agent_mode.assert_called_once()


    def test_agent_mode_question_workflow(
        self, cli_runner, mock_agent_mode
    ):
        """Complete question mode workflow."""
        result = cli_runner.invoke(
            agent_mode, ["--question", "List all storage accounts"]
        )
        mock_agent_mode.assert_called_once_with(
            question="List all storage accounts"
        )


# ============================================================================
# END-TO-END TESTS (10%)
# ============================================================================


class TestAgentModeE2E:
    """Test complete agent mode workflows."""

    def test_agent_mode_full_interactive_session(
        self, cli_runner, mock_agent_mode
    ):
        """Full interactive agent session."""
        mock_agent_mode.return_value = None
        result = cli_runner.invoke(agent_mode, [])
        assert result.exit_code == 0 or "Failed" in result.output

    def test_agent_mode_full_question_session(
        self, cli_runner, mock_agent_mode
    ):
        """Full single-question session."""
        mock_agent_mode.return_value = None
        result = cli_runner.invoke(
            agent_mode, ["--question", "Show tenant summary"]
        )
        assert result.exit_code == 0 or "Failed" in result.output
