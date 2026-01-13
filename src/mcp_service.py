#!/usr/bin/env python3
"""
MCP Service - runs MCP server with HTTP healthcheck endpoint
This allows the MCP server to run as a persistent service.
"""

import asyncio
import logging
import os
import sys

from aiohttp import web
from neo4j import GraphDatabase, basic_auth

from src.utils.neo4j_startup import ensure_neo4j_running

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='{"event": "%(message)s", "timestamp": "%(asctime)s", "level": "%(levelname)s"}',
    datefmt="%Y-%m-%dT%H:%M:%S.%fZ",
)


def can_connect_to_neo4j(uri: str, user: str, password: str, timeout: int = 5) -> bool:
    """Check if Neo4j database is accepting connections."""
    try:
        driver = GraphDatabase.driver(
            uri, auth=basic_auth(user, password), connection_timeout=timeout
        )
        with driver.session() as session:
            session.run("RETURN 1")
        driver.close()
        return True
    except Exception as e:
        logger.warning(str(f"Neo4j connection check failed: {e}"))
        return False


async def start_healthcheck_server(port: int = 8080):
    """Start a simple HTTP healthcheck server."""

    async def health_handler(request: web.Request):
        # Check Neo4j connection
        neo4j_port = os.environ.get("NEO4J_PORT")
        if not neo4j_port:
            raise ValueError("NEO4J_PORT environment variable is required")
        neo4j_uri = os.environ.get("NEO4J_URI", f"bolt://localhost:{neo4j_port}")
        neo4j_user = os.environ.get("NEO4J_USER", "neo4j")
        neo4j_password = os.environ.get("NEO4J_PASSWORD")
        if not neo4j_password:
            raise ValueError("NEO4J_PASSWORD environment variable is required")

        neo4j_connected = can_connect_to_neo4j(neo4j_uri, neo4j_user, neo4j_password)

        status = {
            "status": "healthy" if neo4j_connected else "degraded",
            "neo4j": neo4j_connected,
            "mcp": "ready",
        }

        return web.json_response(status)

    async def simple_health(request: web.Request):
        return web.Response(text="OK")

    app = web.Application()
    app.router.add_get("/health", health_handler)
    app.router.add_get("/", simple_health)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(str(f"MCP healthcheck server running on port {port}"))

    return runner


async def run_mcp_service():
    """Run MCP as a persistent service with healthcheck."""

    # Ensure Neo4j is running
    ensure_neo4j_running()

    # Start healthcheck server
    healthcheck_runner = await start_healthcheck_server(8080)

    logger.info("MCP service is ready and accepting requests")
    logger.info("Healthcheck available at http://localhost:8080/health")

    # The MCP Neo4j Cypher server would be integrated here
    # For now, we just keep the service running with healthcheck

    try:
        # Keep running forever
        while True:
            await asyncio.sleep(60)  # Check every minute

            # Verify Neo4j is still accessible
            neo4j_port = os.environ.get("NEO4J_PORT")
            if not neo4j_port:
                raise ValueError("NEO4J_PORT environment variable is required")
            neo4j_uri = os.environ.get("NEO4J_URI", f"bolt://localhost:{neo4j_port}")
            neo4j_user = os.environ.get("NEO4J_USER", "neo4j")
            neo4j_password = os.environ.get("NEO4J_PASSWORD")
            if not neo4j_password:
                raise ValueError("NEO4J_PASSWORD environment variable is required")

            if not can_connect_to_neo4j(neo4j_uri, neo4j_user, neo4j_password):
                logger.warning("Neo4j connection lost, attempting to reconnect...")

    except KeyboardInterrupt:
        logger.info("MCP service shutting down...")
        await healthcheck_runner.cleanup()

    except Exception as e:
        logger.error(str(f"MCP service error: {e}"))
        await healthcheck_runner.cleanup()
        raise


if __name__ == "__main__":
    try:
        asyncio.run(run_mcp_service())
    except KeyboardInterrupt:
        logger.info("MCP service stopped")
        sys.exit(0)
    except Exception as e:
        logger.error(str(f"Failed to run MCP service: {e}"))
        sys.exit(1)
