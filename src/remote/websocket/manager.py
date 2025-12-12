"""
WebSocket manager re-exports for test compatibility.

This module re-exports the WebSocketManager from the server implementation
to maintain backward compatibility with existing tests.
"""

from src.remote.server.websocket.manager import WebSocketManager

__all__ = ["WebSocketManager"]
