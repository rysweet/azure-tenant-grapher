"""
Health Check Router for ATG Remote API.

Philosophy:
- Simple health checks (no auth required)
- Reports Neo4j status
- Fast response times

Endpoints:
    GET /api/v1/health - Basic health check
"""

from typing import Dict

from fastapi import APIRouter, Depends

from ...db.connection_manager import ConnectionManager
from ..config import ATGServerConfig
from ..dependencies import get_config, get_connection_manager

router = APIRouter()


@router.get("/health")
async def health_check(
    connection_manager: ConnectionManager = Depends(get_connection_manager),
    config: ATGServerConfig = Depends(get_config),
) -> Dict[str, str]:
    """
    Health check endpoint (no authentication required).

    Returns service health status and Neo4j connection status.

    Returns:
        Dictionary with status, version, and neo4j_status
    """
    # Check Neo4j connection
    try:
        is_healthy = await connection_manager.health_check()
        neo4j_status = "connected" if is_healthy else "disconnected"
    except Exception:
        neo4j_status = "disconnected"

    return {
        "status": "healthy",
        "version": "1.0.0",
        "neo4j_status": neo4j_status,
        "environment": config.environment,
    }


__all__ = ["router"]
