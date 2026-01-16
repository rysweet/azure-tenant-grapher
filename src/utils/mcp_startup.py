"""
MCP Server Startup Utilities

Ensures MCP server is running and accessible, similar to Neo4j startup.
"""

import asyncio
import asyncio.subprocess as async_subprocess
import logging
import os
import subprocess
import time
from typing import Optional, Union

import aiohttp

logger = logging.getLogger(__name__)


class MCPServerManager:
    """Manages MCP server lifecycle."""

    def __init__(self, debug: bool = False):
        self.debug = debug
        self.mcp_port = int(os.environ.get("MCP_PORT", "8080"))
        self.mcp_endpoint = os.environ.get(
            "MCP_ENDPOINT", f"http://localhost:{self.mcp_port}"
        )
        self.process: Optional[
            Union[subprocess.Popen[bytes], async_subprocess.Process]
        ] = None

    def is_mcp_running(self) -> bool:
        """Check if MCP server is running by checking health endpoint."""
        try:
            import requests

            response = requests.get(f"{self.mcp_endpoint}/health", timeout=2)
            return response.status_code == 200
        except (ImportError, Exception):
            # If requests is not available or connection fails
            return False

    async def is_mcp_running_async(self) -> bool:
        """Async check if MCP server is running."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.mcp_endpoint}/health",
                    timeout=aiohttp.ClientTimeout(total=2),
                ) as response:
                    return response.status == 200
        except Exception:
            return False

    def start_mcp_server(self) -> bool:
        """Start the MCP server as a background process."""
        if self.is_mcp_running():
            logger.info("MCP server is already running")
            return True

        logger.info(str(f"Starting MCP server on port {self.mcp_port}..."))

        try:
            # Start MCP service in background
            env = os.environ.copy()
            self.process = subprocess.Popen(
                ["python", "-m", "src.mcp_service"],
                env=env,
                stdout=subprocess.PIPE if not self.debug else None,
                stderr=subprocess.PIPE if not self.debug else None,
                stdin=subprocess.DEVNULL,
            )

            # Wait for server to be ready
            max_attempts = 30  # 30 seconds max
            for attempt in range(max_attempts):
                time.sleep(1)
                if self.is_mcp_running():
                    logger.info(
                        f"✅ MCP server started successfully on port {self.mcp_port}"
                    )
                    return True

                # Check if process has died
                if self.process.poll() is not None:
                    _, stderr = self.process.communicate()
                    error_msg = (
                        f"MCP server process died. Exit code: {self.process.returncode}"
                    )
                    if stderr:
                        error_msg += f"\nError: {stderr.decode()}"
                    logger.error(error_msg)
                    return False

                if self.debug:
                    logger.debug(
                        f"Waiting for MCP server... (attempt {attempt + 1}/{max_attempts})"
                    )

            logger.error("MCP server failed to start within timeout")
            self.stop_mcp_server()
            return False

        except Exception as e:
            logger.error(str(f"Failed to start MCP server: {e}"))
            return False

    async def start_mcp_server_async(self) -> bool:
        """Async version of start_mcp_server."""
        if await self.is_mcp_running_async():
            logger.info("MCP server is already running")
            return True

        logger.info(str(f"Starting MCP server on port {self.mcp_port}..."))

        try:
            # Start MCP service in background
            env = os.environ.copy()
            self.process = await asyncio.create_subprocess_exec(
                "python",
                "-m",
                "src.mcp_service",
                env=env,
                stdout=asyncio.subprocess.PIPE if not self.debug else None,
                stderr=asyncio.subprocess.PIPE if not self.debug else None,
                stdin=asyncio.subprocess.DEVNULL,
            )

            # Wait for server to be ready
            max_attempts = 30  # 30 seconds max
            for attempt in range(max_attempts):
                await asyncio.sleep(1)
                if await self.is_mcp_running_async():
                    logger.info(
                        f"✅ MCP server started successfully on port {self.mcp_port}"
                    )
                    return True

                # Check if process has died
                if self.process and self.process.returncode is not None:
                    _, stderr = await self.process.communicate()
                    error_msg = (
                        f"MCP server process died. Exit code: {self.process.returncode}"
                    )
                    if stderr:
                        error_msg += f"\nError: {stderr.decode()}"
                    logger.error(error_msg)
                    return False

                if self.debug:
                    logger.debug(
                        f"Waiting for MCP server... (attempt {attempt + 1}/{max_attempts})"
                    )

            logger.error("MCP server failed to start within timeout")
            await self.stop_mcp_server_async()
            return False

        except Exception as e:
            logger.error(str(f"Failed to start MCP server: {e}"))
            return False

    def stop_mcp_server(self):
        """Stop the MCP server if it was started by this manager."""
        if self.process:
            logger.info("Stopping MCP server...")
            self.process.terminate()
            try:
                # For subprocess.Popen, wait() doesn't take timeout as positional
                # Use a loop with poll() instead
                if isinstance(self.process, subprocess.Popen):
                    for _ in range(50):  # 5 seconds with 0.1s intervals
                        if self.process.poll() is not None:
                            break
                        import time

                        time.sleep(0.1)
                    else:
                        raise subprocess.TimeoutExpired(self.process.args, 5)
                else:
                    # For async Process, we can't await in a sync function
                    # Just skip the wait since terminate() was already called
                    pass
            except subprocess.TimeoutExpired:
                logger.warning("MCP server did not stop gracefully, killing it")
                self.process.kill()
                if isinstance(self.process, subprocess.Popen):
                    self.process.wait()
                # For async Process, can't wait in sync context
            self.process = None
            logger.info("MCP server stopped")

    async def stop_mcp_server_async(self):
        """Async version of stop_mcp_server."""
        if self.process:
            logger.info("Stopping MCP server...")
            self.process.terminate()
            try:
                # Wait for process to terminate with timeout
                if isinstance(self.process, async_subprocess.Process):
                    await asyncio.wait_for(self.process.wait(), timeout=5)
                else:
                    # For sync Popen, use executor
                    loop = asyncio.get_event_loop()
                    await asyncio.wait_for(
                        loop.run_in_executor(None, self.process.wait), timeout=5
                    )
            except asyncio.TimeoutError:
                logger.warning("MCP server did not stop gracefully, killing it")
                self.process.kill()
                await self.process.wait()  # type: ignore[misc]
            self.process = None
            logger.info("MCP server stopped")


# Global manager instance
_manager: Optional[MCPServerManager] = None


def ensure_mcp_running(debug: bool = False) -> None:
    """
    Idempotently ensure an MCP server is running and reachable.
    Safe to call multiple times or concurrently.
    Raises RuntimeError if the server cannot be started.
    """
    global _manager
    if _manager is None:
        _manager = MCPServerManager(debug=debug)

    if not _manager.start_mcp_server():
        raise RuntimeError(
            "Failed to start MCP server. Please check the logs and ensure all dependencies are installed."
        )


async def ensure_mcp_running_async(debug: bool = False) -> None:
    """
    Async version of ensure_mcp_running.
    Idempotently ensure an MCP server is running and reachable.
    """
    global _manager
    if _manager is None:
        _manager = MCPServerManager(debug=debug)

    if not await _manager.start_mcp_server_async():
        raise RuntimeError(
            "Failed to start MCP server. Please check the logs and ensure all dependencies are installed."
        )


def stop_mcp_if_managed():
    """Stop the MCP server if it was started by this manager."""
    global _manager
    if _manager is not None:
        _manager.stop_mcp_server()


async def stop_mcp_if_managed_async():
    """Async version of stop_mcp_if_managed."""
    global _manager
    if _manager:
        await _manager.stop_mcp_server_async()
