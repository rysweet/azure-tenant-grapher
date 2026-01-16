"""
WebSocket Router for ATG Remote Service.

Philosophy:
- WebSocket progress streaming
- API key authentication via query params
- Automatic cleanup on disconnect

Endpoints:
    WS /ws/progress/{job_id} - Stream progress for a job
"""

import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from ...auth.middleware import get_api_key_store
from ..websocket.manager import WebSocketManager
from ..websocket.progress import ProgressStream

logger = logging.getLogger(__name__)

router = APIRouter()

# Global WebSocket manager (initialized on app startup)
_ws_manager: WebSocketManager = None  # type: ignore[misc]


def get_ws_manager() -> WebSocketManager:
    """Get global WebSocket manager."""
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = WebSocketManager()
    return _ws_manager


@router.websocket("/ws/progress/{job_id}")
async def stream_job_progress(
    websocket: WebSocket,
    job_id: str,
    api_key: str = Query(..., description="API key for authentication"),
):
    """
    Stream job progress via WebSocket.

    Requires API key in query parameter (WebSocket doesn't support headers well).

    Connection lifecycle:
    1. Validate API key
    2. Accept WebSocket connection
    3. Register with manager
    4. Wait for disconnection
    5. Unregister from manager

    Args:
        websocket: WebSocket connection
        job_id: Job identifier
        api_key: API key from query parameter

    Raises:
        WebSocketDisconnect: When client disconnects
    """
    # Validate API key
    try:
        api_key_store = get_api_key_store()
        validation = api_key_store.validate(api_key)

        if not validation["valid"]:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Invalid API key"
            )
            return
    except Exception as e:
        logger.error(str(f"API key validation failed: {e}"))
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="Authentication failed"
        )
        return

    # Accept WebSocket connection
    await websocket.accept()
    logger.info(str(f"WebSocket connected for job {job_id}"))

    # Get WebSocket manager
    manager = get_ws_manager()

    # Use ProgressStream context manager
    try:
        async with ProgressStream(job_id, manager, websocket):
            # Keep connection alive until client disconnects
            while True:
                try:
                    # Wait for messages (we don't expect any from client, but this keeps connection alive)
                    data = await websocket.receive_text()
                    # Ignore client messages (we only send, not receive)
                    logger.debug(
                        f"Received unexpected message from client for job {job_id}: {data}"
                    )
                except WebSocketDisconnect:
                    logger.info(str(f"WebSocket disconnected for job {job_id}"))
                    break
    except Exception as e:
        logger.exception(f"Error in WebSocket connection for job {job_id}: {e}")
    finally:
        logger.info(str(f"WebSocket cleanup complete for job {job_id}"))


__all__ = ["get_ws_manager", "router"]
