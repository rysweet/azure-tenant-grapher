"""
Authentication Middleware for ATG Remote Service.

Philosophy:
- Decorator-based authentication for FastAPI endpoints
- Clear error messages
- Request context for authenticated requests

This module provides authentication middleware compatible with the tests.
"""

from functools import wraps
from typing import Any, Callable, Optional

from fastapi import Request

from ..common.exceptions import AuthenticationError
from .api_keys import APIKeyStore

# Global API key store (will be set during service initialization)
_api_key_store: Optional[APIKeyStore] = None


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


def require_api_key(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator for requiring API key authentication.

    This decorator checks the Authorization header for a valid Bearer token,
    validates it against the API key store, and sets the auth context on the
    request object.

    Usage:
        @require_api_key
        async def protected_endpoint(request):
            # request.auth_context contains environment and client_id
            return {"status": "authenticated"}

    Args:
        func: Async function to wrap

    Returns:
        Wrapped function

    Raises:
        AuthenticationError: If authentication fails
    """

    @wraps(func)
    async def wrapper(request: Request, *args: Any, **kwargs: Any) -> Any:
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

        # Set auth context on request
        request.auth_context = {  # type: ignore[misc]
            "environment": validation["environment"],
            "client_id": validation["client_id"],
        }

        # Call original function
        return await func(request, *args, **kwargs)

    return wrapper


__all__ = [
    "get_api_key_store",
    "require_api_key",
    "set_api_key_store",
]
