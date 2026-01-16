import asyncio
import logging
import sys
from typing import List, Optional

from neo4j import GraphDatabase, basic_auth

from src.utils.neo4j_startup import ensure_neo4j_running
from src.utils.secure_credentials import get_neo4j_credentials

logger = logging.getLogger(__name__)


# Additional connection verification utilities


def can_connect_to_neo4j(uri: str, user: str, password: str, timeout: int = 5) -> bool:
    """Check if Neo4j database is accepting connections."""
    try:
        driver = GraphDatabase.driver(
            uri, auth=basic_auth(user, password), connection_timeout=timeout
        )
        with driver.session() as session:
            session.run("RETURN 1")  # type: ignore[arg-type]
        driver.close()
        return True
    except Exception as e:
        logger.warning(str(f"Neo4j connection check failed: {e}"))
        return False


async def verify_neo4j_connection(max_attempts: int = 5, delay: float = 2.0) -> None:
    """Verify Neo4j is accepting connections, with retries."""
    # Get credentials securely (Key Vault or env fallback)
    try:
        credentials = get_neo4j_credentials()
    except RuntimeError as e:
        raise RuntimeError(f"Failed to retrieve Neo4j credentials: {e}") from e

    # Try to connect up to max_attempts times
    for attempt in range(max_attempts):
        if can_connect_to_neo4j(
            credentials.uri, credentials.username, credentials.password
        ):
            logger.info(
                f"Neo4j database is available and accepting connections at {credentials.uri}."
            )
            return
        else:
            logger.info(
                f"Waiting for Neo4j database to become available at {credentials.uri} (attempt {attempt + 1}/{max_attempts})..."
            )
            if attempt < max_attempts - 1:  # Don't sleep on the last attempt
                await asyncio.sleep(delay)

    logger.error(
        f"Neo4j container is running but database is not accepting connections at {credentials.uri}."
    )
    raise RuntimeError(
        f"Neo4j database is not available at {credentials.uri}. Please check the container logs and configuration."
    )


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
    ensure_neo4j_running()
    process = await launch_mcp_server()
    logger.info("MCP server started. Press Ctrl+C to stop.")
    try:
        return await process.wait()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, terminating MCP server...")
        process.terminate()
        await process.wait()
        return 0


async def start_healthcheck_server(port: int = 8080):
    from aiohttp import web

    async def handle(request: web.Request):
        return web.Response(text="OK")

    app = web.Application()
    app.router.add_get("/", handle)
    app.router.add_get("/health", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(str(f"Healthcheck server running on port {port}"))
    # Keep running forever
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Start the MCP server (Neo4j Cypher).")
    parser.add_argument(
        "--foreground",
        action="store_true",
        help="Run MCP server in foreground (default)",
    )
    args = parser.parse_args()

    async def main():
        # Start both the MCP server and the healthcheck server concurrently
        await asyncio.gather(
            run_mcp_server_foreground(),
            start_healthcheck_server(8080),
        )

    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(str(f"Failed to start MCP server: {e}"))
        sys.exit(1)
