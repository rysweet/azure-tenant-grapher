import sys
from unittest.mock import AsyncMock, patch

import pytest

import src.mcp_server


@pytest.mark.asyncio
async def test_run_mcp_server_foreground_starts_neo4j_and_mcp(monkeypatch):
    # Mock Neo4jContainerManager
    with patch("src.mcp_server.Neo4jContainerManager") as MockManager:
        mock_mgr = MockManager.return_value
        mock_mgr.is_neo4j_container_running.return_value = False
        mock_mgr.setup_neo4j.return_value = True

        # Mock subprocess
        mock_proc = AsyncMock()
        mock_proc.wait = AsyncMock(return_value=0)
        with patch(
            "src.mcp_server.asyncio.create_subprocess_exec", return_value=mock_proc
        ) as mock_subproc:
            exit_code = await src.mcp_server.run_mcp_server_foreground()
            assert exit_code == 0
            mock_mgr.setup_neo4j.assert_called_once()
            mock_subproc.assert_called_with(
                "uvx",
                "mcp-neo4j-cypher",
                stdin=sys.stdin,
                stdout=sys.stdout,
                stderr=sys.stderr,
            )
            mock_proc.wait.assert_awaited()
