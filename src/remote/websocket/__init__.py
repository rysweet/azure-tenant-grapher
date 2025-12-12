"""
WebSocket compatibility layer.

Re-exports from src.remote.server.websocket for test compatibility.
"""

from src.remote.server.websocket.manager import WebSocketManager
from src.remote.server.websocket.progress import ProgressStream
from src.remote.server.websocket.protocol import (
    BaseMessage,
    CompletionMessage,
    ErrorMessage,
    ProgressMessage,
    ProtocolError,
)

__all__ = [
    "BaseMessage",
    "CompletionMessage",
    "ErrorMessage",
    "ProgressMessage",
    "ProgressStream",
    "ProtocolError",
    "WebSocketManager",
]
