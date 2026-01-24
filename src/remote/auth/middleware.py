"""
Authentication Middleware for ATG Remote Service.

Philosophy:
- Decorator-based authentication for FastAPI endpoints
- Clear error messages
- Request context for authenticated requests

This module provides authentication middleware compatible with the tests.
"""

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec, TypedDict, TypeVar

from fastapi import Request

from ..common.exceptions import AuthenticationError
from .api_keys import APIKeyStore


class AuthContext(TypedDict):
    """
    Authentication context attached to authenticated requests.

    This is added to request.state.auth by the require_api_key middleware.
    """

    environment: str
    client_id: str


T = TypeVar("T")
P = ParamSpec("P")

# Global API key store (will be set during service initialization)
_api_key_store: APIKeyStore | None = None


def get_api_key_store() -> APIKeyStore:
    """
    Get the global API key store.

    Returns:
        APIKeyStore instance

    Raises:
        RuntimeError: If store not initialized
    """
    if _api_key_store is None:
        raise RuntimeError("API key store not initialized")
    return _api_key_store


def set_api_key_store(store: APIKeyStore) -> None:
    """
    Set the global API key store.

    Args:
        store: APIKeyStore instance
    """
    global _api_key_store
    _api_key_store = store


def require_api_key(
    func: Callable[P, Awaitable[T]],
) -> Callable[P, Awaitable[T]]:
    """
    Decorator for requiring API key authentication.

    This decorator checks the Authorization header for a valid Bearer token,
    validates it against the API key store, and sets the auth context on the
    request.state object.

    Usage:
        @require_api_key
        async def protected_endpoint(request: Request):
            # Access auth context via request.state.auth
            auth = request.state.auth
            return {"environment": auth["environment"]}

    Args:
        func: Async function to wrap

    Returns:
        Wrapped function

    Raises:
        AuthenticationError: If authentication fails
    """

    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        # Extract request from first argument
        request = args[0] if args else kwargs.get("request")
        if not isinstance(request, Request):
            raise AuthenticationError("First argument must be a FastAPI Request")
        # Extract Authorization header
        auth_header = request.headers.get("Authorization", "")

        if not auth_header:
            raise AuthenticationError("Missing Authorization header")

        if not auth_header.startswith("Bearer "):
            raise AuthenticationError(
                "Invalid Authorization format. Expected: Bearer <api_key>"
            )

        # Extract API key
        api_key = auth_header[7:]  # Remove "Bearer " prefix

        # Validate API key
        store = get_api_key_store()
        validation = store.validate(api_key)

        if not validation["valid"]:
            reason = validation.get("reason", "unknown")
            if reason == "expired":
                raise AuthenticationError("API key expired. Please request a new key.")
            else:
                raise AuthenticationError("Invalid API key")

        # Set auth context on request.state (type-safe way to extend Request)
        auth_context: AuthContext = {
            "environment": validation["environment"],
            "client_id": validation["client_id"],
        }
        request.state.auth = auth_context

        # Call original function
        return await func(*args, **kwargs)

    return wrapper


__all__ = [
    "AuthContext",
    "get_api_key_store",
    "require_api_key",
    "set_api_key_store",
]
