"""
ATG Server Module - REST API Service

Philosophy:
- Single responsibility: Provide REST API for remote ATG execution
- FastAPI for API framework
- Self-contained and regeneratable

Public API (the "studs"):
    ATGServerConfig: Server configuration
    Neo4jConfig: Neo4j connection configuration
"""

from .config import ATGServerConfig, Neo4jConfig

__all__ = ["ATGServerConfig", "Neo4jConfig"]
