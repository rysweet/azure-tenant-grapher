"""
Tests for MCP Server Startup Utilities
"""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.utils.mcp_startup import (
    MCPServerManager,
    ensure_mcp_running,
    ensure_mcp_running_async,
    stop_mcp_if_managed,
    stop_mcp_if_managed_async,
)


class TestMCPServerManager:
    """Test MCP Server Manager functionality."""
    
    @pytest.fixture
    def manager(self):
        """Create an MCP server manager instance."""
        with patch.dict(os.environ, {"MCP_PORT": "8080", "MCP_ENDPOINT": "http://localhost:8080"}):
            return MCPServerManager(debug=False)
    
    def test_initialization(self):
        """Test manager initialization."""
        with patch.dict(os.environ, {"MCP_PORT": "8080"}):
            manager = MCPServerManager(debug=True)
            assert manager.debug is True
            assert manager.mcp_port == 8080
            assert manager.mcp_endpoint == "http://localhost:8080"
            assert manager.process is None
    
    def test_is_mcp_running_true(self, manager):
        """Test checking if MCP is running when it is."""
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            assert manager.is_mcp_running() is True
            mock_get.assert_called_once_with("http://localhost:8080/health", timeout=2)
    
    def test_is_mcp_running_false(self, manager):
        """Test checking if MCP is running when it's not."""
        with patch("requests.get", side_effect=Exception("Connection refused")):
            assert manager.is_mcp_running() is False
    
    @pytest.mark.asyncio
    async def test_is_mcp_running_async_true(self, manager):
        """Test async checking if MCP is running when it is."""
        # Mock response
        mock_response = MagicMock()
        mock_response.status = 200
        
        # Mock the get context manager
        mock_get_cm = AsyncMock()
        mock_get_cm.__aenter__.return_value = mock_response
        mock_get_cm.__aexit__.return_value = None
        
        # Mock session
        mock_session = MagicMock()
        mock_session.get.return_value = mock_get_cm
        
        # Mock the ClientSession context manager
        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__.return_value = mock_session
        mock_session_cm.__aexit__.return_value = None
        
        with patch("src.utils.mcp_startup.aiohttp.ClientSession", return_value=mock_session_cm):
            assert await manager.is_mcp_running_async() is True
    
    @pytest.mark.asyncio
    async def test_is_mcp_running_async_false(self, manager):
        """Test async checking if MCP is running when it's not."""
        with patch("src.utils.mcp_startup.aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session.get.side_effect = Exception("Connection refused")
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            assert await manager.is_mcp_running_async() is False
    
    def test_start_mcp_server_already_running(self, manager):
        """Test starting MCP when it's already running."""
        with patch.object(manager, "is_mcp_running", return_value=True):
            assert manager.start_mcp_server() is True
            assert manager.process is None  # Should not start a new process
    
    def test_start_mcp_server_success(self, manager):
        """Test successfully starting MCP server."""
        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Process is running
        
        with patch.object(manager, "is_mcp_running", side_effect=[False, False, True]):
            with patch("subprocess.Popen", return_value=mock_process):
                with patch("time.sleep"):
                    assert manager.start_mcp_server() is True
                    assert manager.process == mock_process
    
    def test_start_mcp_server_process_dies(self, manager):
        """Test MCP server process dying during startup."""
        mock_process = MagicMock()
        mock_process.poll.return_value = 1  # Process died
        mock_process.returncode = 1
        mock_process.communicate.return_value = (b"", b"Error starting server")
        
        with patch.object(manager, "is_mcp_running", return_value=False):
            with patch("subprocess.Popen", return_value=mock_process):
                with patch("time.sleep"):
                    assert manager.start_mcp_server() is False
                    mock_process.communicate.assert_called_once()
    
    def test_start_mcp_server_timeout(self, manager):
        """Test MCP server startup timeout."""
        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Process is running
        
        with patch.object(manager, "is_mcp_running", return_value=False):
            with patch.object(manager, "stop_mcp_server"):
                with patch("subprocess.Popen", return_value=mock_process):
                    with patch("time.sleep"):
                        assert manager.start_mcp_server() is False
                        manager.stop_mcp_server.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_mcp_server_async_success(self, manager):
        """Test async successfully starting MCP server."""
        mock_process = AsyncMock()
        mock_process.returncode = None  # Process is running
        
        with patch.object(manager, "is_mcp_running_async", side_effect=[False, False, True]):
            with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                with patch("asyncio.sleep"):
                    assert await manager.start_mcp_server_async() is True
                    assert manager.process == mock_process
    
    def test_stop_mcp_server(self, manager):
        """Test stopping MCP server."""
        mock_process = MagicMock()
        manager.process = mock_process
        
        manager.stop_mcp_server()
        
        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once_with(timeout=5)
        assert manager.process is None
    
    def test_stop_mcp_server_force_kill(self, manager):
        """Test force killing MCP server when it doesn't stop gracefully."""
        mock_process = MagicMock()
        mock_process.wait.side_effect = [subprocess.TimeoutExpired("cmd", 5), None]
        manager.process = mock_process
        
        manager.stop_mcp_server()
        
        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()
        assert manager.process is None
    
    @pytest.mark.asyncio
    async def test_stop_mcp_server_async(self, manager):
        """Test async stopping MCP server."""
        mock_process = AsyncMock()
        manager.process = mock_process
        
        await manager.stop_mcp_server_async()
        
        mock_process.terminate.assert_called_once()
        assert manager.process is None


class TestGlobalFunctions:
    """Test global MCP startup functions."""
    
    def test_ensure_mcp_running_success(self):
        """Test ensure_mcp_running when server starts successfully."""
        with patch("src.utils.mcp_startup.MCPServerManager") as MockManager:
            mock_manager = MockManager.return_value
            mock_manager.start_mcp_server.return_value = True
            
            ensure_mcp_running(debug=True)
            
            MockManager.assert_called_once_with(debug=True)
            mock_manager.start_mcp_server.assert_called_once()
    
    def test_ensure_mcp_running_failure(self):
        """Test ensure_mcp_running when server fails to start."""
        with patch("src.utils.mcp_startup._manager", None):
            with patch("src.utils.mcp_startup.MCPServerManager") as MockManager:
                mock_manager = MockManager.return_value
                mock_manager.start_mcp_server.return_value = False
                
                with pytest.raises(RuntimeError, match="Failed to start MCP server"):
                    ensure_mcp_running()
    
    @pytest.mark.asyncio
    async def test_ensure_mcp_running_async_success(self):
        """Test async ensure_mcp_running when server starts successfully."""
        with patch("src.utils.mcp_startup._manager", None):
            with patch("src.utils.mcp_startup.MCPServerManager") as MockManager:
                mock_manager = MagicMock()
                mock_manager.start_mcp_server_async = AsyncMock(return_value=True)
                MockManager.return_value = mock_manager
                
                await ensure_mcp_running_async(debug=True)
                
                MockManager.assert_called_once_with(debug=True)
                mock_manager.start_mcp_server_async.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_ensure_mcp_running_async_failure(self):
        """Test async ensure_mcp_running when server fails to start."""
        with patch("src.utils.mcp_startup._manager", None):
            with patch("src.utils.mcp_startup.MCPServerManager") as MockManager:
                mock_manager = MagicMock()
                mock_manager.start_mcp_server_async = AsyncMock(return_value=False)
                MockManager.return_value = mock_manager
                
                with pytest.raises(RuntimeError, match="Failed to start MCP server"):
                    await ensure_mcp_running_async()
    
    def test_stop_mcp_if_managed(self):
        """Test stopping MCP if it was managed."""
        mock_manager = MagicMock()
        
        with patch("src.utils.mcp_startup._manager", mock_manager):
            stop_mcp_if_managed()
            mock_manager.stop_mcp_server.assert_called_once()
    
    def test_stop_mcp_if_managed_no_manager(self):
        """Test stopping MCP when no manager exists."""
        with patch("src.utils.mcp_startup._manager", None):
            stop_mcp_if_managed()  # Should not raise
    
    @pytest.mark.asyncio
    async def test_stop_mcp_if_managed_async(self):
        """Test async stopping MCP if it was managed."""
        mock_manager = MagicMock()
        mock_manager.stop_mcp_server_async = AsyncMock()
        
        with patch("src.utils.mcp_startup._manager", mock_manager):
            await stop_mcp_if_managed_async()
            mock_manager.stop_mcp_server_async.assert_called_once()


# Add missing import for subprocess
import subprocess