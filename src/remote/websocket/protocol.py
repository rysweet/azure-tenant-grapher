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


# Create a MessageProtocol class for backward compatibility with tests
# that expect Message.from_json()
class MessageProtocol:
    """
    Compatibility wrapper for Message Union type.

    Provides from_json() as a class method for tests that expect it.
    """

    @staticmethod
    def from_json(json_str: str) -> Message:
        """Deserialize message from JSON string."""
        return from_json(json_str)


# For compatibility, allow both patterns:
# - from_json(json_str) - direct function call
# - MessageProtocol.from_json(json_str) - class method style
# Tests can import Message and use Message.from_json by importing MessageProtocol as Message

__all__ = [
    "BaseMessage",
    "CompletionMessage",
    "ErrorMessage",
    "LogMessage",
    "Message",
    "MessageProtocol",
    "ProgressMessage",
    "ProtocolError",
    "from_json",
]
