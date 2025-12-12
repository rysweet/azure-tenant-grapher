"""
ATG Remote Module - Client-Server Architecture

Philosophy:
- Ruthless simplicity - No unnecessary abstractions
- Zero-BS - All code must work (no stubs!)
- Modular design - Clear brick boundaries
- Self-contained and regeneratable

Public API (the "studs"):
    ATGClientConfig: Client configuration
    RemoteClient: HTTP + WebSocket client
    ExecutionDispatcher: Local vs remote routing
    execute_with_remote_support: CLI integration helper
    is_remote_mode_enabled: Check if remote mode enabled
    add_remote_option: Decorator to add --remote flag
"""

from .cli_integration import (
    add_remote_option,
    execute_with_remote_support,
    is_remote_mode_enabled,
)
from .client import ATGClientConfig, RemoteClient
from .dispatcher import ExecutionDispatcher

__all__ = [
    "ATGClientConfig",
    "ExecutionDispatcher",
    "RemoteClient",
    "add_remote_option",
    "execute_with_remote_support",
    "is_remote_mode_enabled",
]
