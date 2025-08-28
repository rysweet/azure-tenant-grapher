import asyncio
from typing import Any

import pytest

from src.resource_processor import ResourceProcessor


class DummySession:
    """A context manager that does nothing (for mocking session_manager.session())."""

    def __enter__(self) -> "DummySession":
        return self

    def __exit__(self, exc_type: type, exc_val: BaseException, exc_tb: Any) -> None:
        pass

    def run(self, *args: Any, **kwargs: Any) -> Any:
        # Always return an object that supports .single() and __iter__()
        class DummyResult:
            def single(self) -> dict[str, Any]:
                return {"count": 0}  # For resource_exists, etc.

            def __iter__(self) -> Any:
                return iter([])

        return DummyResult()


class DummySessionManager:
    """Minimal mock to avoid DB calls for ResourceProcessor."""

    def session(self):
        return DummySession()


@pytest.mark.asyncio
async def test_resource_processor_process_resources_hangs_on_loop_exit():
    """Regression: prove processor loop does not exit with resources; expect TimeoutError."""
    session_manager = DummySessionManager()
    processor = ResourceProcessor(session_manager)

    resources = [
        {
            "id": "r1",
            "name": "A",
            "type": "Test",
            "location": "westus",
            "resource_group": "rg",
            "subscription_id": "sub",
        },
        {
            "id": "r2",
            "name": "B",
            "type": "Test",
            "location": "eastus",
            "resource_group": "rg",
            "subscription_id": "sub",
        },
    ]

    # The regression condition is now fixed: process_resources should NOT hang, and must return.
    # This should complete within the timeout if the processor exits correctly.
    await asyncio.wait_for(
        processor.process_resources(resources, max_workers=2),
        timeout=1.0,
    )
