"""
AsyncNeo4jSession - thin wrapper around the Neo4j driver's async session.

Implements an async context manager and delegates ``run`` to the underlying
session, handling both coroutine and immediate-return variants exposed by the
driver.
"""

from __future__ import annotations

import asyncio
from typing import Any


class AsyncNeo4jSession:
    """Async context manager that wraps Neo4j's async driver session.

    Example
    -------
    ```python
    async with AsyncNeo4jSession(driver) as session:
        await session.run("MATCH (n) RETURN n")
    ```
    """

    def __init__(self, driver: Any) -> None:
        self._driver = driver
        self._session: Any | None = None

    async def __aenter__(self) -> Any:
        # neo4j async driver exposes an async `session` factory.  It can return
        # either a coroutine or an awaitable that yields a session object.
        session_obj = self._driver.session()
        # Handle both coroutine and already-resolved session.
        self._session = (
            await session_obj if asyncio.iscoroutine(session_obj) else session_obj
        )
        return self._session

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[override]
        if self._session and hasattr(self._session, "close"):
            close_coro = self._session.close()
            if asyncio.iscoroutine(close_coro):
                await close_coro

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        """Delegate `run` to the underlying Neo4j session."""
        if not self._session:
            raise RuntimeError(
                "Session has not been initialised; use within an async context manager."
            )
        result = self._session.run(*args, **kwargs)
        return await result if asyncio.iscoroutine(result) else result
