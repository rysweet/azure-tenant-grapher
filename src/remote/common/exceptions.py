"""
Custom exceptions for ATG Remote Module.

Philosophy:
- Clear, specific exception types
- Helpful error messages with context
- No generic exceptions

All exceptions inherit from a base RemoteError for easy catching.
"""


class RemoteError(Exception):
    """Base exception for all remote module errors."""

    pass


class ConfigurationError(RemoteError):
    """Raised when configuration is invalid or incomplete."""

    pass


class InvalidAPIKeyError(RemoteError):
    """Raised when API key format or validation fails."""

    pass


class AuthenticationError(RemoteError):
    """Raised when authentication fails (invalid/expired credentials)."""

    pass


class ConnectionError(RemoteError):
    """Raised when Neo4j connection or remote service connection fails."""

    pass


class CommandNotFoundError(RemoteError):
    """Raised when command is not supported."""

    pass


class ParameterValidationError(RemoteError):
    """Raised when required parameters are missing or invalid."""

    pass


class LocalExecutionError(RemoteError):
    """Raised when local execution fails."""

    pass


class RemoteExecutionError(RemoteError):
    """Raised when remote execution fails."""

    pass


__all__ = [
    "AuthenticationError",
    "CommandNotFoundError",
    "ConfigurationError",
    "ConnectionError",
    "InvalidAPIKeyError",
    "LocalExecutionError",
    "ParameterValidationError",
    "RemoteError",
    "RemoteExecutionError",
]
