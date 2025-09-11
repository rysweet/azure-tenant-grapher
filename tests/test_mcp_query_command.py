"""
Tests for MCP Query Command with startup logic
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import click
import pytest
from click.testing import CliRunner

from src.cli_commands import mcp_query_command


class TestMCPQueryCommand:
    """Test MCP query command with startup logic."""

    @pytest.fixture
    def runner(self):
        """Create a Click test runner."""
        return CliRunner()

    @pytest.fixture
    def mock_env(self):
        """Set up mock environment variables."""
        with patch.dict(
            os.environ,
            {
                "AZURE_TENANT_ID": "test-tenant-123",
                "MCP_ENABLED": "true",
                "MCP_ENDPOINT": "http://localhost:8080",
                "MCP_PORT": "8080",
            },
        ):
            yield

    @pytest.mark.asyncio
    async def test_mcp_query_starts_server(self, mock_env):
        """Test that mcp-query starts the MCP server if not running."""
        with patch("src.utils.mcp_startup.ensure_mcp_running_async") as mock_ensure:
            with patch(
                "src.services.mcp_integration.MCPIntegrationService"
            ) as MockService:
                mock_service = MockService.return_value
                mock_service.initialize = AsyncMock(return_value=True)
                mock_service.natural_language_command = AsyncMock(
                    return_value=(True, {"result": "test"})
                )
                mock_service.close = AsyncMock()

                with patch("src.cli_commands.create_config_from_env") as mock_config:
                    mock_config.return_value = MagicMock(
                        mcp=MagicMock(enabled=True, endpoint="http://localhost:8080"),
                        logging=MagicMock(),
                    )

                    with patch("src.cli_commands.setup_logging"):
                        ctx = click.Context(click.Command("test"))
                        ctx.obj = {"log_level": "INFO"}

                        await mcp_query_command(
                            ctx=ctx,
                            query="test query",
                            tenant_id="test-tenant",
                            use_fallback=False,
                            output_format="json",
                            debug=False,
                        )

                        # Verify MCP server startup was attempted
                        mock_ensure.assert_called_once_with(debug=False)

                        # Verify MCP service was initialized
                        mock_service.initialize.assert_called_once()

                        # Verify query was executed
                        mock_service.natural_language_command.assert_called_once_with(
                            "test query"
                        )

    @pytest.mark.asyncio
    async def test_mcp_query_fails_when_disabled(self, mock_env):
        """Test that mcp-query fails when MCP is disabled."""
        with patch("src.cli_commands.create_config_from_env") as mock_config:
            mock_config.return_value = MagicMock(
                mcp=MagicMock(enabled=False), logging=MagicMock()
            )

            with patch("src.cli_commands.setup_logging"):
                with patch("sys.exit") as mock_exit:
                    ctx = click.Context(click.Command("test"))
                    ctx.obj = {"log_level": "INFO"}

                    await mcp_query_command(
                        ctx=ctx,
                        query="test query",
                        tenant_id="test-tenant",
                        use_fallback=False,
                        output_format="json",
                        debug=False,
                    )

                    # Verify the command exited with error
                    mock_exit.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_mcp_query_handles_startup_failure(self, mock_env):
        """Test that mcp-query handles MCP server startup failure."""
        with patch("src.utils.mcp_startup.ensure_mcp_running_async") as mock_ensure:
            mock_ensure.side_effect = RuntimeError("Failed to start MCP server")

            with patch("src.cli_commands.create_config_from_env") as mock_config:
                mock_config.return_value = MagicMock(
                    mcp=MagicMock(enabled=True, endpoint="http://localhost:8080"),
                    logging=MagicMock(),
                )

                with patch("src.cli_commands.setup_logging"):
                    with patch("sys.exit") as mock_exit:
                        ctx = click.Context(click.Command("test"))
                        ctx.obj = {"log_level": "INFO"}

                        await mcp_query_command(
                            ctx=ctx,
                            query="test query",
                            tenant_id="test-tenant",
                            use_fallback=False,
                            output_format="json",
                            debug=False,
                        )

                        # Verify the command exited with error
                        mock_exit.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_mcp_query_handles_connection_failure_after_startup(self, mock_env):
        """Test that mcp-query handles connection failure after server startup."""
        with patch("src.utils.mcp_startup.ensure_mcp_running_async"):
            with patch(
                "src.services.mcp_integration.MCPIntegrationService"
            ) as MockService:
                mock_service = MockService.return_value
                mock_service.initialize = AsyncMock(
                    return_value=False
                )  # Connection fails
                mock_service.close = AsyncMock()

                with patch("src.cli_commands.create_config_from_env") as mock_config:
                    mock_config.return_value = MagicMock(
                        mcp=MagicMock(enabled=True, endpoint="http://localhost:8080"),
                        logging=MagicMock(),
                    )

                    with patch("src.cli_commands.setup_logging"):
                        with patch("sys.exit") as mock_exit:
                            ctx = click.Context(click.Command("test"))
                            ctx.obj = {"log_level": "INFO"}

                            await mcp_query_command(
                                ctx=ctx,
                                query="test query",
                                tenant_id="test-tenant",
                                use_fallback=False,
                                output_format="json",
                                debug=False,
                            )

                            # Verify the command exited with error
                            mock_exit.assert_called_once_with(1)
