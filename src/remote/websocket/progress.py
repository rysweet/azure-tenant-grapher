"""
WebSocket progress re-exports for test compatibility.

This module re-exports the ProgressStream from the server implementation
to maintain backward compatibility with existing tests.
"""

from src.remote.server.websocket.progress import ProgressStream

__all__ = ["ProgressStream"]
