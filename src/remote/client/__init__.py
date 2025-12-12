"""
ATG Client Module - Remote Mode Support

Philosophy:
- Single responsibility: Enable CLI to communicate with remote service
- Standard library + httpx for HTTP client
- Self-contained and regeneratable

Public API (the "studs"):
    ATGClientConfig: Client configuration
    RemoteClient: HTTP + WebSocket client for remote ATG service
"""

from .config import ATGClientConfig
from .remote_client import RemoteClient

__all__ = ["ATGClientConfig", "RemoteClient"]
