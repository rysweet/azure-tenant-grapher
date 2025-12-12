"""
WebSocket protocol re-exports for test compatibility.

This module re-exports protocol classes from the server implementation
to maintain backward compatibility with existing tests.
"""

from src.remote.server.websocket.protocol import (
    BaseMessage,
    CompletionMessage,
    ErrorMessage,
    LogMessage,
    Message,
    ProgressMessage,
    ProtocolError,
    from_json,
)

# Add from_json as a class method for backward compatibility
Message.from_json = staticmethod(from_json)  # type: ignore

__all__ = [
    "BaseMessage",
    "CompletionMessage",
    "ErrorMessage",
    "LogMessage",
    "Message",
    "ProgressMessage",
    "ProtocolError",
    "from_json",
]
