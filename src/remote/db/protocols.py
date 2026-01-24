"""
Type protocols for Neo4j driver interfaces.

Philosophy:
- Define protocols for Neo4j types to avoid Any usage
- Allow type checking without concrete implementation dependencies
- Provide clear type contracts for database operations

These protocols match the neo4j-python-driver API but are defined as protocols
to avoid tight coupling and enable better type checking.
"""

from typing import Any, AsyncContextManager, Protocol, TypeVar

T = TypeVar("T")


class Neo4jResult(Protocol):
    """Protocol for Neo4j query result objects."""

    async def single(self) -> Any:
        """
        Get single result record.

        Returns:
            Single record from query
        """
        ...

    async def data(self) -> list[dict[str, Any]]:
        """
        Get all result records as dictionaries.

        Returns:
            List of record dictionaries
        """
        ...


class Neo4jTransaction(Protocol):
    """Protocol for Neo4j transaction objects."""

    async def run(self, query: str, **parameters: Any) -> Neo4jResult:
        """
        Execute Cypher query within transaction.

        Args:
            query: Cypher query string
            **parameters: Query parameters

        Returns:
            Query result object
        """
        ...

    async def commit(self) -> None:
        """Commit the transaction."""
        ...

    async def rollback(self) -> None:
        """Rollback the transaction."""
        ...


class Neo4jSession(Protocol):
    """Protocol for Neo4j session objects."""

    async def run(self, query: str, **parameters: Any) -> Neo4jResult:
        """
        Execute Cypher query in auto-commit transaction.

        Args:
            query: Cypher query string
            **parameters: Query parameters

        Returns:
            Query result object
        """
        ...

    def begin_transaction(self) -> AsyncContextManager[Neo4jTransaction]:
        """
        Begin a new transaction.

        Returns:
            Async context manager for transaction
        """
        ...

    async def close(self) -> None:
        """Close the session."""
        ...


class Neo4jDriver(Protocol):
    """Protocol for Neo4j driver objects."""

    def session(
        self,
        **kwargs: Any,
    ) -> AsyncContextManager[Neo4jSession]:
        """
        Create a new session.

        Args:
            **kwargs: Session configuration options

        Returns:
            Async context manager for session
        """
        ...

    async def close(self) -> None:
        """Close the driver and all connections."""
        ...

    async def verify_connectivity(self) -> dict[str, Any]:
        """
        Verify connectivity to Neo4j database.

        Returns:
            Dictionary with connection information
        """
        ...


__all__ = [
    "Neo4jDriver",
    "Neo4jResult",
    "Neo4jSession",
    "Neo4jTransaction",
]
