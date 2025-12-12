"""
Neo4j Connection Manager for ATG Remote Service.

Philosophy:
- Single responsibility: Manage Neo4j connections
- Standard library + neo4j driver only
- Self-contained and regeneratable
- Trust the Neo4j driver's built-in pooling

Singleton Pattern:
    One ConnectionManager instance per application
    One driver per environment (dev, integration, etc.)

Connection Lifecycle:
    1. Configure environment with connection settings
    2. Create driver lazily on first session request
    3. Verify connectivity on driver creation
    4. Reuse driver for all subsequent sessions
    5. Close driver when environment is no longer needed
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, Optional

try:
    from neo4j import AsyncGraphDatabase
except ImportError:
    # Allow import even if neo4j not installed (for testing)
    AsyncGraphDatabase = None

from ..common.exceptions import ConnectionError

logger = logging.getLogger(__name__)


@dataclass
class Neo4jConnectionConfig:
    """
    Configuration for a Neo4j connection.

    Philosophy: Simple dataclass with validation, no complex logic.

    Attributes:
        uri: Neo4j connection URI (e.g., bolt://localhost:7687)
        user: Neo4j username
        password: Neo4j password
        max_pool_size: Maximum connection pool size (default: 50)
        connection_timeout: Connection timeout in seconds (default: 30.0)
        max_transaction_retry_time: Max transaction retry time in seconds (default: 30.0)
    """

    uri: str
    user: str
    password: str
    max_pool_size: int = 50
    connection_timeout: float = 30.0
    max_transaction_retry_time: float = 30.0

    def __post_init__(self):
        """Validate configuration on initialization."""
        if not self.uri:
            raise ValueError("Neo4j URI is required")
        if not self.user:
            raise ValueError("Neo4j user is required")
        if not self.password:
            raise ValueError("Neo4j password is required")
        if self.max_pool_size < 1:
            raise ValueError("Max pool size must be at least 1")
        if self.connection_timeout < 1:
            raise ValueError("Connection timeout must be at least 1 second")


class ConnectionManager:
    """
    Singleton connection manager for Neo4j.

    Manages one driver per environment (dev, integration, etc).
    Uses Neo4j driver's built-in connection pooling.

    Example:
        manager = ConnectionManager()
        await manager.configure("dev", config)

        async with await manager.get_session("dev") as session:
            result = await session.run("MATCH (n) RETURN count(n)")

    Thread Safety:
        Uses asyncio.Lock for thread-safe singleton and driver management.
    """

    _instance: Optional["ConnectionManager"] = None
    _lock = asyncio.Lock()

    def __new__(cls):
        """Implement singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize connection manager (only once)."""
        if self._initialized:
            return

        self._drivers: Dict[str, any] = {}
        self._configs: Dict[str, Neo4jConnectionConfig] = {}
        self._initialized = True
        logger.info("ConnectionManager initialized")

    async def configure(self, environment: str, config: Neo4jConnectionConfig):
        """
        Configure connection for an environment.

        Args:
            environment: Environment name (dev, integration, etc)
            config: Connection configuration

        Raises:
            ConnectionError: If driver creation fails
        """
        async with self._lock:
            if environment in self._drivers:
                logger.warning(
                    f"Environment {environment} already configured, closing existing driver"
                )
                await self._drivers[environment].close()
                del self._drivers[environment]

            self._configs[environment] = config
            logger.info(f"Configured environment: {environment} -> {config.uri}")

    async def _get_or_create_driver(self, environment: str):
        """
        Get or create driver for environment (lazy initialization).

        Args:
            environment: Environment name

        Returns:
            Neo4j AsyncDriver instance

        Raises:
            ValueError: If environment not configured
            ConnectionError: If driver creation or connectivity check fails
        """
        if environment not in self._drivers:
            if environment not in self._configs:
                raise ValueError(f"Environment '{environment}' not configured")

            if AsyncGraphDatabase is None:
                raise ImportError(
                    "neo4j package not installed. Install with: pip install neo4j"
                )

            config = self._configs[environment]

            try:
                driver = AsyncGraphDatabase.driver(
                    config.uri,
                    auth=(config.user, config.password),
                    max_connection_pool_size=config.max_pool_size,
                    connection_timeout=config.connection_timeout,
                    max_transaction_retry_time=config.max_transaction_retry_time,
                )

                # Verify connectivity before returning
                await driver.verify_connectivity()
                self._drivers[environment] = driver
                logger.info(f"Created driver for {environment}")

            except Exception as e:
                logger.error(f"Failed to create driver for {environment}: {e}")
                raise ConnectionError(
                    f"Failed to connect to Neo4j at {config.uri}: {e}"
                ) from e

        return self._drivers[environment]

    async def get_session(self, environment: str):
        """
        Get Neo4j session for environment.

        Args:
            environment: Environment name

        Returns:
            AsyncSession context manager

        Raises:
            ValueError: If environment not configured
            ConnectionError: If connection fails
        """
        driver = await self._get_or_create_driver(environment)
        return driver.session()

    async def close(self, environment: str):
        """
        Close connections for specific environment.

        Args:
            environment: Environment name
        """
        async with self._lock:
            if environment in self._drivers:
                await self._drivers[environment].close()
                del self._drivers[environment]
                logger.info(f"Closed driver for {environment}")

    async def close_all(self):
        """Close all connections."""
        async with self._lock:
            for env, driver in list(self._drivers.items()):
                await driver.close()
                logger.info(f"Closed driver for {env}")
            self._drivers.clear()

    async def health_check(self, environment: str) -> bool:
        """
        Check if connection to environment is healthy.

        Args:
            environment: Environment name

        Returns:
            True if healthy, False otherwise
        """
        try:
            driver = await self._get_or_create_driver(environment)
            await driver.verify_connectivity()
            return True
        except Exception as e:
            logger.error(f"Health check failed for {environment}: {e}")
            return False


__all__ = ["ConnectionManager", "Neo4jConnectionConfig"]
