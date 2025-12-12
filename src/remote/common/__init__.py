"""
Common utilities and exceptions for ATG Remote Module.

Philosophy:
- Single responsibility: Shared utilities across remote module
- Standard library only (minimal dependencies)
- Self-contained and regeneratable

Public API (the "studs"):
    ConfigurationError: Configuration validation errors
    InvalidAPIKeyError: API key validation errors
    AuthenticationError: Authentication failures
    ConnectionError: Neo4j connection errors
"""

from .exceptions import (
    AuthenticationError,
    ConfigurationError,
    ConnectionError,
    InvalidAPIKeyError,
)

__all__ = [
    "AuthenticationError",
    "ConfigurationError",
    "ConnectionError",
    "InvalidAPIKeyError",
]
