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
    
    # Verify Neo4j is accepting connections
    await verify_neo4j_connection()


# Additional connection verification utilities
import os
from neo4j import GraphDatabase, basic_auth


def can_connect_to_neo4j(uri: str, user: str, password: str, timeout: int = 5) -> bool:
    """Check if Neo4j database is accepting connections."""
    try:
        driver = GraphDatabase.driver(uri, auth=basic_auth(user, password), connection_timeout=timeout)
        with driver.session() as session:
            session.run("RETURN 1")
        driver.close()
        return True
    except Exception as e:
        logger.warning(f"Neo4j connection check failed: {e}")
        return False


async def verify_neo4j_connection(max_attempts: int = 5, delay: float = 2.0) -> None:
    """Verify Neo4j is accepting connections, with retries."""
    # Read connection info from environment
    neo4j_uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.environ.get("NEO4J_USER", "neo4j")
    neo4j_password = os.environ.get("NEO4J_PASSWORD", "neo4j")
    
    # Try to connect up to max_attempts times
    for attempt in range(max_attempts):
        if can_connect_to_neo4j(neo4j_uri, neo4j_user, neo4j_password):
            logger.info(f"Neo4j database is available and accepting connections at {neo4j_uri}.")
            return
        else:
            logger.info(f"Waiting for Neo4j database to become available at {neo4j_uri} (attempt {attempt+1}/{max_attempts})...")
            if attempt < max_attempts - 1:  # Don't sleep on the last attempt
                await asyncio.sleep(delay)
    
    logger.error(f"Neo4j container is running but database is not accepting connections at {neo4j_uri}.")
    raise RuntimeError(f"Neo4j database is not available at {neo4j_uri}. Please check the container logs and configuration.")


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
