"""
Neo4j Session Manager

This module provides a context manager for Neo4j database operations,
centralizing session management and connection handling with proper
error handling and resource cleanup.
"""

import logging
import time
from contextlib import contextmanager
from typing import Any, Callable, Generator, Optional

from neo4j import Driver, GraphDatabase, Session
from neo4j.exceptions import Neo4jError, ServiceUnavailable, SessionExpired

from ..config_manager import Neo4jConfig
from ..exceptions import Neo4jConnectionError, wrap_neo4j_exception

logger = logging.getLogger(__name__)


def retry_neo4j_operation(
    max_retries: int = 3, initial_delay: float = 1.0, backoff: float = 2.0
) -> Any:
    """
    Decorator to retry a Neo4j operation on connection errors.
    Note: This decorator is for functions that take a session as first parameter.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (
                    ServiceUnavailable,
                    SessionExpired,
                    OSError,
                    TimeoutError,
                    BufferError,
                    Neo4jError,
                ) as e:
                    last_exception = e
                    logger.warning(
                        f"Neo4j connection error ({type(e).__name__}): {e}. "
                        f"Retrying {attempt + 1}/{max_retries} after {delay}s..."
                    )
                    time.sleep(delay)
                    delay *= backoff
                except Exception as e:
                    # Catch any other Neo4j-related errors that might be protocol errors
                    error_msg = str(e)
                    if any(
                        marker in error_msg
                        for marker in [
                            "Expected structure, found marker",
                            "PackStream",
                            "protocol",
                        ]
                    ):
                        last_exception = e
                        logger.warning(
                            f"Neo4j protocol error ({type(e).__name__}): {e}. "
                            f"Retrying {attempt + 1}/{max_retries} after {delay}s..."
                        )
                        time.sleep(delay)
                        delay *= backoff
                    else:
                        # Re-raise non-retryable exceptions immediately
                        raise

            # If we get here, all retries failed
            raise ServiceUnavailable(
                f"Max retries ({max_retries}) exceeded for Neo4j operation"
            ) from last_exception

        return wrapper

    return decorator


class Neo4jSessionManager:
    """
    Manages Neo4j database connections and sessions with automatic cleanup
    and enhanced error handling.
    """

    def __init__(self, config: Neo4jConfig) -> None:
        """
        Initialize the session manager.

        Args:
            config: Neo4j configuration containing connection details
        """
        self.config = config
        self._driver: Optional[Driver] = None
        self._is_connected = False

    @property
    def is_connected(self) -> bool:
        """Check if database is connected."""
        return self._is_connected and self._driver is not None

    def connect(self) -> None:
        """
        Establish connection to Neo4j database.

        Raises:
            Neo4jConnectionError: If connection fails
        """
        try:
            if not self.config.uri:
                raise Neo4jConnectionError("Neo4j URI is not configured")
            
            logger.debug(f"Connecting to Neo4j at {self.config.uri}")

            self._driver = GraphDatabase.driver(
                self.config.uri,
                auth=(self.config.user, self.config.password),
            )

            # Test the connection
            with self._driver.session() as session:
                session.run("RETURN 1")

            self._is_connected = True
            logger.info(f"✅ Connected to Neo4j at {self.config.uri}")

        except Exception as e:
            self._is_connected = False
            if self._driver:
                self._driver.close()
                self._driver = None

            raise Neo4jConnectionError(
                "Failed to connect to Neo4j database",
                uri=self.config.uri,
                context={"config_uri": self.config.uri},
                cause=e,
            ) from e

    def ensure_connection(self) -> None:
        """
        Ensure an active connection to Neo4j if not already connected.

        This is a convenience wrapper used by legacy adapter methods that
        expect an idempotent connection helper. It will attempt to connect
        only when the manager is not yet connected.
        """
        if not self.is_connected:
            self.connect()

    def disconnect(self) -> None:
        """Close Neo4j database connection."""
        if self._driver:
            try:
                self._driver.close()
                logger.info("🔌 Neo4j connection closed")
            except Exception as e:
                logger.warning(f"Error closing Neo4j connection: {e}")
            finally:
                self._driver = None
                self._is_connected = False

    def get_session(self, **kwargs: Any) -> Session:
        """
        Get a Neo4j session.

        Args:
            **kwargs: Additional session configuration

        Returns:
            Session: Neo4j session instance

        Raises:
            Neo4jConnectionError: If not connected to database
        """
        if not self.is_connected or not self._driver:
            raise Neo4jConnectionError(
                "Not connected to Neo4j database",
                context={"is_connected": self._is_connected},
            )

        try:
            return self._driver.session(**kwargs)
        except Exception as e:
            raise wrap_neo4j_exception(e, context={"operation": "get_session"}) from e

    @contextmanager
    def session(self, **kwargs: Any) -> Generator[Session, None, None]:
        """
        Context manager for Neo4j sessions with automatic cleanup.

        Args:
            **kwargs: Additional session configuration

        Yields:
            Session: Neo4j session instance

        Example:
            ```python
            with session_manager.session() as session:
                result = session.run("MATCH (n) RETURN n LIMIT 1")
                # Session is automatically closed when exiting the context
            ```
        """
        session = None
        try:
            session = self.get_session(**kwargs)
            yield session
        except Exception as e:
            logger.exception(f"Error in Neo4j session: {e}")
            raise wrap_neo4j_exception(
                e, context={"operation": "session_context"}
            ) from e
        finally:
            if session:
                try:
                    session.close()
                except Exception as e:
                    logger.warning(f"Error closing Neo4j session: {e}")

    def test_connection(self) -> bool:
        """
        Test the database connection.

        Returns:
            bool: True if connection is working, False otherwise
        """
        if not self.is_connected:
            return False

        try:
            with self.session() as session:
                result = session.run("RETURN 1 as test")
                record = result.single()
                return record is not None and record["test"] == 1
        except Exception as e:
            logger.exception(f"Connection test failed: {e}")
            return False

    def execute_query(
        self,
        query: str,
        parameters: Optional[dict[str, Any]] = None,
        **session_kwargs: Any,
    ) -> Any:
        """
        Execute a single query with automatic session management.

        Args:
            query: Cypher query to execute
            parameters: Optional query parameters
            **session_kwargs: Additional session configuration

        Returns:
            Query result

        Raises:
            Neo4jQueryError: If query execution fails
        """
        try:
            with self.session(**session_kwargs) as session:
                return session.run(query, parameters or {})  # type: ignore[misc]
        except Exception as e:
            from ..exceptions import Neo4jQueryError

            raise Neo4jQueryError(
                f"Query execution failed: {e}",
                query=query,
                parameters=parameters,
                cause=e,
            ) from e

    def execute_write_transaction(
        self, transaction_function: Any, *args: Any, **kwargs: Any
    ) -> Any:
        """
        Execute a write transaction with automatic session management.

        Args:
            transaction_function: Function to execute in transaction
            *args: Arguments for transaction function
            **kwargs: Keyword arguments for transaction function

        Returns:
            Transaction result
        """
        try:
            with self.session() as session:
                return session.execute_write(transaction_function, *args, **kwargs)
        except Exception as e:
            raise wrap_neo4j_exception(
                e,
                context={
                    "operation": "write_transaction",
                    "function": transaction_function.__name__
                    if hasattr(transaction_function, "__name__")
                    else str(transaction_function),
                },
            ) from e

    def execute_read_transaction(
        self, transaction_function: Any, *args: Any, **kwargs: Any
    ) -> Any:
        """
        Execute a read transaction with automatic session management.

        Args:
            transaction_function: Function to execute in transaction
            *args: Arguments for transaction function
            **kwargs: Keyword arguments for transaction function

        Returns:
            Transaction result
        """
        try:
            with self.session() as session:
                return session.execute_read(transaction_function, *args, **kwargs)
        except Exception as e:
            raise wrap_neo4j_exception(
                e,
                context={
                    "operation": "read_transaction",
                    "function": transaction_function.__name__
                    if hasattr(transaction_function, "__name__")
                    else str(transaction_function),
                },
            ) from e

    def __enter__(self) -> "Neo4jSessionManager":
        """Context manager entry."""
        if not self.is_connected:
            self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit with cleanup."""
        self.disconnect()


def create_session_manager(config: Neo4jConfig) -> Neo4jSessionManager:
    """
    Factory function to create a Neo4j session manager.

    Args:
        config: Neo4j configuration

    Returns:
        Neo4jSessionManager: Configured session manager instance
    """
    return Neo4jSessionManager(config)


@contextmanager
def neo4j_session(
    config: Neo4jConfig, **session_kwargs: Any
) -> Generator[Session, None, None]:
    """
    Convenience context manager for one-off Neo4j operations.

    Args:
        config: Neo4j configuration
        **session_kwargs: Additional session configuration

    Yields:
        Session: Neo4j session instance

    Example:
        ```python
        with neo4j_session(config) as session:
            result = session.run("MATCH (n) RETURN n LIMIT 1")
        ```
    """
    manager = None
    try:
        manager = create_session_manager(config)
        manager.connect()
        with manager.session(**session_kwargs) as session:
            yield session
    finally:
        if manager:
            manager.disconnect()
