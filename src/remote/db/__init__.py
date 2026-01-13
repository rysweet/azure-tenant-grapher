"""
Neo4j Connection Management for ATG Remote Service.

Philosophy:
- Singleton connection manager per environment
- Lazy driver initialization
- Trust Neo4j driver's built-in pooling
- Self-contained and regeneratable

Public API (the "studs"):
    ConnectionManager: Singleton connection manager
    Neo4jConnectionConfig: Connection configuration
    HealthChecker: Health check utilities
    PoolMetrics: Connection pool metrics
"""

from .connection_manager import ConnectionManager, Neo4jConnectionConfig
from .health import HealthChecker, HealthStatus
from .metrics import PoolMetrics, PoolMonitor
from .transaction import chunked_transaction, with_retry

__all__ = [
    "ConnectionManager",
    "HealthChecker",
    "HealthStatus",
    "Neo4jConnectionConfig",
    "PoolMetrics",
    "PoolMonitor",
    "chunked_transaction",
    "with_retry",
]
