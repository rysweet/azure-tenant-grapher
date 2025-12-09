"""
Progress Streaming for ATG Remote Service.

Philosophy:
- Simple API for sending progress updates
- Async context manager for lifecycle
- Automatic connection management

Provides high-level API for streaming progress to WebSocket clients.
"""

import logging
from typing import Any, Dict, Optional

from fastapi import WebSocket

from .manager import WebSocketManager
from .protocol import CompletionMessage, ErrorMessage, ProgressMessage

logger = logging.getLogger(__name__)


class ProgressStream:
    """
    High-level API for streaming progress to WebSocket clients.

    Usage:
        async with ProgressStream(job_id, manager, websocket) as stream:
            await stream.send_progress(50.0, "Halfway done")
            await stream.send_completion({"resources": 1523})
    """

    def __init__(
        self,
        job_id: str,
        manager: WebSocketManager,
        websocket: Optional[WebSocket] = None,
    ):
        """
        Initialize progress stream.

        Args:
            job_id: Job identifier
            manager: WebSocket manager
            websocket: WebSocket connection (optional, for context manager)
        """
        self.job_id = job_id
        self.manager = manager
        self.websocket = websocket

    async def __aenter__(self) -> "ProgressStream":
        """Enter context: register WebSocket connection."""
        if self.websocket:
            await self.manager.register(self.job_id, self.websocket)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        """Exit context: unregister WebSocket connection."""
        if self.websocket:
            await self.manager.unregister(self.job_id)

    async def send_progress(self, percent: float, message: str) -> None:
        """
        Send progress update.

        Args:
            percent: Progress percentage (0-100)
            message: Human-readable progress message
        """
        msg = ProgressMessage(job_id=self.job_id, progress=percent, message=message)
        await self.manager.send_message(self.job_id, msg)

    async def send_error(
        self,
        error_code: str,
        error_message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Send error notification.

        Args:
            error_code: Error code
            error_message: Error message
            details: Additional error details
        """
        msg = ErrorMessage(
            job_id=self.job_id,
            error_code=error_code,
            error_message=error_message,
            details=details,
        )
        await self.manager.send_message(self.job_id, msg)

    async def send_completion(self, result: Optional[Dict[str, Any]] = None) -> None:
        """
        Send completion notification.

        Args:
            result: Job result summary
        """
        msg = CompletionMessage(job_id=self.job_id, status="completed", result=result)
        await self.manager.send_message(self.job_id, msg)


__all__ = ["ProgressStream"]
