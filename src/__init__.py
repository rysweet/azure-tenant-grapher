"""
Azure Tenant Grapher

A comprehensive toolkit for discovering Azure resources and building a
Neo4j graph database of those resources and their relationships.

Test-suites for synchronous helper functions sometimes obtain the default
event-loop directly via ``asyncio.get_event_loop()``.  When a previous test
has executed ``asyncio.run`` the global loop is *closed*.  Re-using that
closed loop with ``run_until_complete`` then raises
``RuntimeError: Event loop is closed``.

To provide a stable, backward-compatible environment we eagerly replace any
closed default loop with a fresh one **once** at import-time.  This avoids
changing individual test helpers while remaining a no-op in production.
"""

from __future__ import annotations

import asyncio

try:
    _loop = asyncio.get_event_loop()
    if _loop.is_closed():  # pragma: no cover
        asyncio.set_event_loop(asyncio.new_event_loop())
except RuntimeError:
    # No current event-loop; create one so later `get_event_loop()` succeeds.
    asyncio.set_event_loop(asyncio.new_event_loop())
# ---------------------------------------------------------------------------
# Ensure future calls to asyncio.get_event_loop() always return an *open* loop.
# This guards against test utilities that reuse the default loop after it
# has been closed by a previous asyncio.run invocation.
# ---------------------------------------------------------------------------
_original_get_event_loop = asyncio.get_event_loop  # type: ignore[attr-defined]


def _safe_get_event_loop() -> asyncio.AbstractEventLoop:  # pragma: no cover
    try:
        loop = _original_get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


asyncio.get_event_loop = _safe_get_event_loop  # type: ignore[assignment]

# (empty file)
