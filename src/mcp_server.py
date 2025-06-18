import asyncio
import logging
import sys
from typing import List, Optional

from src.container_manager import Neo4jContainerManager

logger = logging.getLogger(__name__)


async def ensure_neo4j_running() -> None:
    """Ensure Neo4j container is running, start if needed."""
    container_manager = Neo4jContainerManager()
    if not container_manager.is_neo4j_container_running():
        logger.info("Starting Neo4j container...")
        if not container_manager.setup_neo4j():
            logger.error("Failed to start Neo4j container.")
            raise RuntimeError("Failed to start Neo4j container.")
        logger.info("Neo4j container started.")
    else:
        logger.info("Neo4j container already running.")


async def launch_mcp_server(
    uvx_path: str = "uvx",
    mcp_module: str = "mcp-neo4j-cypher",
    extra_args: Optional[List[str]] = None,
    attach_stdio: bool = True,
) -> asyncio.subprocess.Process:
    """
    Launch the MCP server process (uvx mcp-neo4j-cypher).
    Returns the process object.
    """
    cmd = [uvx_path, mcp_module]
    if extra_args:
        cmd.extend(extra_args)
    logger.info(f"Launching MCP server: {' '.join(cmd)}")
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=sys.stdin if attach_stdio else asyncio.subprocess.PIPE,
        stdout=sys.stdout if attach_stdio else asyncio.subprocess.PIPE,
        stderr=sys.stderr if attach_stdio else asyncio.subprocess.PIPE,
    )
    return process


async def run_mcp_server_foreground() -> int:
    """
    Ensure Neo4j is running, then launch MCP server in foreground (attached).
    Returns the MCP server process exit code.
    """
    await ensure_neo4j_running()
    process = await launch_mcp_server()
    logger.info("MCP server started. Press Ctrl+C to stop.")
    try:
        return await process.wait()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, terminating MCP server...")
        process.terminate()
        await process.wait()
        return 0
