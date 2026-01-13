"""
WebSocket Support for ATG Remote Service.

Philosophy:
- Real-time progress streaming
- Simple protocol for events
- Fast message serialization

Public API:
    WebSocketManager: Connection management
    ProgressStream: Progress event streaming
    protocol: Message protocol definitions
"""

from .manager import WebSocketManager
from .protocol import (
    CompletionMessage,
    ErrorMessage,
    Message,
    ProgressMessage,
    ProtocolError,
)

__all__ = [
    "CompletionMessage",
    "ErrorMessage",
    "Message",
    "ProgressMessage",
    "ProtocolError",
    "WebSocketManager",
]
