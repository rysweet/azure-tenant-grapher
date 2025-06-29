"""
Tests for AsyncNeo4jSession wrapper.

This test suite covers the behaviour we expect from an async context manager
that wraps the Neo4j Python driver's async session objects.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

# Will raise ImportError until implemented
from src.db.async_neo4j_session import AsyncNeo4jSession  # type: ignore


@pytest.mark.asyncio
async def test_async_neo4j_session_run_delegates_to_underlying_session() -> None:
    """Ensure that `run` on our wrapper proxies to the underlying async session."""
    # Build a fake driver and session
    fake_session = AsyncMock()
    fake_session.run = AsyncMock(return_value="ok")

    fake_driver = MagicMock()
    fake_driver.session = AsyncMock(return_value=fake_session)

    # Construct wrapper
    async_session_wrapper = AsyncNeo4jSession(fake_driver)

    async with async_session_wrapper as session:
        result = await session.run("MATCH (n) RETURN n")

    fake_driver.session.assert_awaited_once()
    fake_session.run.assert_awaited_once_with("MATCH (n) RETURN n")
    assert result == "ok"