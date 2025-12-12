"""
WebSocket Connection Manager for ATG Remote Service.

Philosophy:
- Simple connection tracking
- Efficient message broadcasting
- Automatic cleanup of closed connections

Manages WebSocket connections for progress streaming.
"""

import logging
from typing import Dict

from fastapi import WebSocket

from .protocol import Message

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    Manages WebSocket connections for job progress streaming.

    Philosophy:
    - Track connections by job_id
    - Handle closed connections gracefully
    - Fast message delivery
    """

    def __init__(self):
        """Initialize manager with empty connection registry."""
        self._connections: Dict[str, WebSocket] = {}

    async def register(self, job_id: str, websocket: WebSocket) -> None:
        """
        Register a new WebSocket connection.

        Args:
            job_id: Job identifier
            websocket: WebSocket connection
        """
        self._connections[job_id] = websocket
        logger.info(f"Registered WebSocket connection for job {job_id}")

    async def unregister(self, job_id: str) -> None:
        """
        Unregister a WebSocket connection.

        Args:
            job_id: Job identifier
        """
        if job_id in self._connections:
            del self._connections[job_id]
            logger.info(f"Unregistered WebSocket connection for job {job_id}")

    async def send_message(self, job_id: str, message: Message) -> None:
        """
        Send message to a specific job's WebSocket connection.

        Automatically unregisters closed connections.

        Args:
            job_id: Job identifier
            message: Message to send
        """
        websocket = self._connections.get(job_id)
        if websocket is None:
            logger.debug(f"No WebSocket connection for job {job_id}")
            return

        try:
            json_str = message.to_json()
            await websocket.send_text(json_str)
        except Exception as e:
            logger.warning(
                f"Failed to send message to job {job_id}: {e}. "
                f"Unregistering connection."
            )
            await self.unregister(job_id)

    async def broadcast(self, message: Message) -> None:
        """
        Broadcast message to all connected WebSockets.

        Args:
            message: Message to broadcast
        """
        json_str = message.to_json()

        # Send to all connections
        for job_id, websocket in list(self._connections.items()):
            try:
                await websocket.send_text(json_str)
            except Exception as e:
                logger.warning(
                    f"Failed to broadcast to job {job_id}: {e}. "
                    f"Unregistering connection."
                )
                await self.unregister(job_id)

    def connection_count(self) -> int:
        """
        Get number of active connections.

        Returns:
            Number of active WebSocket connections
        """
        return len(self._connections)

    @property
    def connections(self) -> Dict[str, WebSocket]:
        """Get connections dict (for testing)."""
        return self._connections


__all__ = ["WebSocketManager"]
