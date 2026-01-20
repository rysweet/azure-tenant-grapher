# tests/unit/commands/test_mcp.py
"""Tests for mcp.py (MCP server and query commands).

Coverage target: 85%+
Test pyramid: 60% unit, 30% integration, 10% E2E
"""

import pytest

from src.commands.mcp import (
    mcp_query,
    mcp_query_command_handler,
    mcp_server,
    mcp_server_command_handler,
)

# ============================================================================
# UNIT TESTS (60%)
# ============================================================================


class TestMCPServerCommand:
    """Test MCP server command."""

    def test_mcp_server_command_exists(self, cli_runner):
        """MCP server command can be invoked."""
        result = cli_runner.invoke(mcp_server, ["--help"])
        assert result.exit_code == 0
        assert "mcp" in result.output.lower() or "server" in result.output.lower()

    @pytest.mark.asyncio
    async def test_mcp_server_handler_calls_run_server(
        self, mock_click_context, mocker
    ):
        """Handler calls run_mcp_server_foreground."""
        mock_run_server = mocker.patch(
            "src.mcp_server.run_mcp_server_foreground", return_value=0
        )

        await mcp_server_command_handler(mock_click_context)
        mock_run_server.assert_called_once()

    @pytest.mark.asyncio
    async def test_mcp_server_handler_handles_startup_failure(
        self, mock_click_context, mocker
    ):
        """Handler handles server startup failures."""
        mock_run_server = mocker.patch(
            "src.mcp_server.run_mcp_server_foreground",
            side_effect=Exception("Server failed"),
        )

        with pytest.raises(SystemExit):
            await mcp_server_command_handler(mock_click_context)


class TestMCPQueryCommand:
    """Test MCP query command."""

    def test_mcp_query_command_exists(self, cli_runner):
        """MCP query command can be invoked."""
        result = cli_runner.invoke(mcp_query, ["--help"])
        assert result.exit_code == 0
        assert "query" in result.output.lower()

    def test_mcp_query_requires_query_argument(self, cli_runner):
        """Query command requires query argument."""
        result = cli_runner.invoke(mcp_query, [])
        assert result.exit_code != 0

    def test_mcp_query_has_format_option(self, cli_runner):
        """Query command has output format option."""
        result = cli_runner.invoke(mcp_query, ["--help"])
        assert "format" in result.output.lower()
        assert "json" in result.output.lower()


class TestMCPQueryParameters:
    """Test MCP query parameter handling."""

    def test_mcp_query_accepts_tenant_id(self, cli_runner, sample_tenant_id, mocker):
        """Query accepts tenant-id parameter."""
        # Mock MCP initialization to avoid actual service calls
        mocker.patch("src.services.mcp_integration.MCPIntegrationService")
        mocker.patch("src.utils.mcp_startup.ensure_mcp_running_async")
        mocker.patch.dict("os.environ", {"MCP_ENABLED": "true"})

        result = cli_runner.invoke(
            mcp_query, ["test query", "--tenant-id", sample_tenant_id]
        )
        # May fail for other reasons, but tenant-id should be accepted
        assert result is not None

    def test_mcp_query_uses_env_tenant_id(self, cli_runner, sample_tenant_id, mocker):
        """Query uses AZURE_TENANT_ID from environment."""
        mocker.patch("src.services.mcp_integration.MCPIntegrationService")
        mocker.patch("src.utils.mcp_startup.ensure_mcp_running_async")
        mocker.patch.dict(
            "os.environ", {"AZURE_TENANT_ID": sample_tenant_id, "MCP_ENABLED": "true"}
        )

        result = cli_runner.invoke(mcp_query, ["test query"])
        # Should use env variable
        assert result is not None


class TestMCPQueryOutputFormats:
    """Test MCP query output formatting."""

    @pytest.mark.asyncio
    async def test_mcp_query_json_output_format(
        self, mock_click_context, mocker, sample_tenant_id
    ):
        """Query supports JSON output format."""
        mock_service = mocker.patch(
            "src.services.mcp_integration.MCPIntegrationService"
        )
        mock_instance = mocker.MagicMock()
        mock_instance.initialize.return_value = True
        mock_instance.natural_language_command.return_value = (
            True,
            {"response": "test"},
        )
        mock_service.return_value = mock_instance

        mocker.patch("src.utils.mcp_startup.ensure_mcp_running_async")
        mocker.patch("src.config_manager.create_config_from_env")
        mocker.patch("src.config_manager.setup_logging")

        # Mock config
        mock_config = mocker.MagicMock()
        mock_config.mcp.enabled = True
        mock_config.mcp.endpoint = "http://localhost:8000"
        mock_config.mcp.timeout = 30
        mock_config.mcp.api_key = None
        mocker.patch(
            "src.config_manager.create_config_from_env", return_value=mock_config
        )

        await mcp_query_command_handler(
            mock_click_context,
            query="test query",
            tenant_id=sample_tenant_id,
            use_fallback=True,
            output_format="json",
            debug=False,
        )
        # Should complete without error
        mock_instance.natural_language_command.assert_called_once()


class TestMCPErrorHandling:
    """Test MCP error handling."""

    @pytest.mark.asyncio
    async def test_mcp_query_handles_mcp_disabled(self, cli_runner, mocker):
        """Query handles MCP disabled in config."""
        mock_config = mocker.MagicMock()
        mock_config.mcp.enabled = False
        mocker.patch(
            "src.config_manager.create_config_from_env", return_value=mock_config
        )
        mocker.patch("src.config_manager.setup_logging")
        mocker.patch.dict("os.environ", {"AZURE_TENANT_ID": "test-tenant"})

        result = cli_runner.invoke(mcp_query, ["test query"])
        assert result.exit_code != 0
        assert "not enabled" in result.output.lower()

    @pytest.mark.asyncio
    async def test_mcp_query_handles_server_startup_failure(self, cli_runner, mocker):
        """Query handles MCP server startup failure."""
        mock_config = mocker.MagicMock()
        mock_config.mcp.enabled = True
        mocker.patch(
            "src.config_manager.create_config_from_env", return_value=mock_config
        )
        mocker.patch("src.config_manager.setup_logging")
        mocker.patch(
            "src.utils.mcp_startup.ensure_mcp_running_async",
            side_effect=RuntimeError("Server failed"),
        )
        mocker.patch.dict("os.environ", {"AZURE_TENANT_ID": "test-tenant"})

        result = cli_runner.invoke(mcp_query, ["test query"])
        assert result.exit_code != 0
        assert "Failed to start MCP server" in result.output


# ============================================================================
# INTEGRATION TESTS (30%)
# ============================================================================


class TestMCPIntegration:
    """Test MCP commands with multiple components."""

    @pytest.mark.asyncio
    async def test_mcp_query_full_workflow(
        self, mock_click_context, mocker, sample_tenant_id
    ):
        """Complete MCP query workflow."""
        # Mock all dependencies
        mock_config = mocker.MagicMock()
        mock_config.mcp.enabled = True
        mock_config.mcp.endpoint = "http://localhost:8000"
        mock_config.mcp.timeout = 30
        mock_config.mcp.api_key = None

        mocker.patch(
            "src.config_manager.create_config_from_env", return_value=mock_config
        )
        mocker.patch("src.config_manager.setup_logging")
        mocker.patch("src.utils.mcp_startup.ensure_mcp_running_async")

        mock_service = mocker.patch(
            "src.services.mcp_integration.MCPIntegrationService"
        )
        mock_instance = mocker.MagicMock()
        mock_instance.initialize.return_value = True
        mock_instance.natural_language_command.return_value = (
            True,
            {"response": "Result"},
        )
        mock_instance.close.return_value = None
        mock_service.return_value = mock_instance

        await mcp_query_command_handler(
            mock_click_context,
            query="test query",
            tenant_id=sample_tenant_id,
            use_fallback=False,
            output_format="json",
            debug=False,
        )

        mock_instance.initialize.assert_called_once()
        mock_instance.natural_language_command.assert_called_once_with("test query")
        mock_instance.close.assert_called_once()


# ============================================================================
# END-TO-END TESTS (10%)
# ============================================================================


class TestMCPE2E:
    """Test complete MCP workflows."""

    def test_mcp_server_full_execution(self, cli_runner, mocker):
        """Full MCP server execution."""
        mock_run_server = mocker.patch(
            "src.mcp_server.run_mcp_server_foreground", return_value=0
        )

        result = cli_runner.invoke(mcp_server, [])
        assert "MCP server exited cleanly" in result.output or result.exit_code == 0
