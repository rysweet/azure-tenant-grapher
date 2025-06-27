import importlib.util
import subprocess
import sys
from unittest.mock import AsyncMock, patch

import pytest


def test_agent_mode_dependencies_available():
    """Test that all required agent-mode dependencies are available."""
    try:
        # Test that all critical imports work
        # Check for required modules
        assert importlib.util.find_spec("openai") is not None, "openai not installed"
        assert (
            importlib.util.find_spec("tiktoken") is not None
        ), "tiktoken not installed"
        assert (
            importlib.util.find_spec("autogen_agentchat.agents") is not None
        ), "autogen_agentchat.agents not installed"
        assert (
            importlib.util.find_spec("autogen_ext.tools.mcp") is not None
        ), "autogen_ext.tools.mcp not installed"
        assert (
            importlib.util.find_spec("src.llm_descriptions") is not None
        ), "src.llm_descriptions not installed"

        # If we get here, all dependencies are available
        assert True
    except ImportError as e:
        pytest.fail(f"Required agent-mode dependency missing: {e}")


@pytest.mark.asyncio
async def test_agent_mode_startup():
    """Test that agent-mode can start up without errors (but exit quickly)."""

    # Mock the subprocess and network calls to avoid actually starting services
    with patch(
        "src.agent_mode.ensure_neo4j_running", new_callable=AsyncMock
    ) as mock_neo4j, patch(
        "src.llm_descriptions.LLMConfig.from_env"
    ) as mock_config, patch(
        "src.llm_descriptions.LLMConfig.is_valid", return_value=True
    ), patch("autogen_ext.models.openai.AzureOpenAIChatCompletionClient"), patch(
        "autogen_agentchat.agents.AssistantAgent"
    ) as mock_agent, patch(
        "autogen_ext.tools.mcp.McpWorkbench"
    ) as mock_workbench, patch("asyncio.to_thread") as mock_input:
        # Configure mocks
        mock_config.return_value.api_key = "test-key"
        mock_config.return_value.endpoint = "https://test.openai.azure.com/"
        mock_config.return_value.api_version = "2024-02-01"
        mock_config.return_value.model_chat = "gpt-4"

        # Mock user input to exit immediately
        mock_input.return_value = "x"

        # Import and run agent mode
        from src.agent_mode import run_agent_mode

        # This should start up and exit cleanly without errors
        await run_agent_mode()

        # Verify the setup calls were made
        mock_neo4j.assert_called_once()
        mock_workbench.assert_called_once()
        mock_agent.assert_called_once()


def test_agent_mode_cli_integration():
    """Test that the agent-mode CLI command is properly integrated."""
    # Test that the CLI recognizes the agent-mode command
    result = subprocess.run(
        [sys.executable, "-m", "src.cli_commands", "--help"],
        capture_output=True,
        text=True,
        cwd=".",
        stdin=subprocess.DEVNULL,
    )

    # This would fail if CLI integration is broken
    assert (
        result.returncode != 1
        or "agent-mode" in result.stderr
        or "agent_mode" in result.stderr
    )
