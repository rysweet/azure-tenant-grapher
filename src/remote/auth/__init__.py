"""
Authentication and Authorization for ATG Remote Service.

Philosophy:
- Security-first design
- Constant-time comparisons to prevent timing attacks
- Clear error messages without leaking information

Public API (the "studs"):
    validate_api_key: Validate API key format
    generate_api_key: Generate cryptographically secure API key
    APIKeyStore: Manage and validate API keys
    require_api_key: Authentication decorator for endpoints
"""

from .api_keys import (
    APIKeyStore,
    generate_api_key,
    validate_api_key,
)
from .middleware import get_api_key_store, require_api_key

__all__ = [
    "APIKeyStore",
    "generate_api_key",
    "get_api_key_store",
    "require_api_key",
    "validate_api_key",
]
