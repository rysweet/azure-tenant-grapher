"""
API Key Management for ATG Remote Service.

Philosophy:
- Cryptographically secure key generation
- Constant-time comparison to prevent timing attacks
- Clear validation with helpful error messages

API Key Format:
    atg_{environment}_{64-hex-chars}
    Example: atg_dev_a1b2c3d4e5f67890...

Security Requirements:
    - 256-bit entropy (64 hex characters)
    - Environment prefix for access control
    - Expiration timestamps
    - Constant-time validation
"""

import hmac
import re
import secrets
from datetime import datetime, timezone
from typing import Any, Dict

from ..common.exceptions import InvalidAPIKeyError

# API key format: atg_{environment}_{64-hex-chars}
API_KEY_PATTERN = re.compile(r"^atg_(dev|integration)_[0-9a-f]{64}$", re.IGNORECASE)


def validate_api_key(api_key: str) -> bool:
    """
    Validate API key format.

    Args:
        api_key: API key to validate

    Returns:
        True if valid format

    Raises:
        InvalidAPIKeyError: If key format is invalid with specific reason
    """
    if not api_key:
        raise InvalidAPIKeyError("API key is required")

    if len(api_key) < 72:  # atg_xxx_ (8-9) + 64 hex = ~72-73
        raise InvalidAPIKeyError("API key too short (expected at least 72 characters)")

    # Check for proper prefix
    if not api_key.startswith("atg_"):
        raise InvalidAPIKeyError(
            "Invalid format: API key must start with 'atg_' prefix. "
            "Expected: atg_{environment}_{64-hex-chars}"
        )

    # Check environment (dev or integration)
    parts = api_key.split("_", 2)  # Split into ['atg', environment, hex_part]
    if len(parts) < 3:
        raise InvalidAPIKeyError(
            "Invalid format: API key missing environment or hex portion. "
            "Expected: atg_{environment}_{64-hex-chars}"
        )

    environment = parts[1]
    hex_part = parts[2]

    if environment not in ("dev", "integration"):
        raise InvalidAPIKeyError(
            f"Invalid format: unsupported environment '{environment}'. "
            f"Expected 'dev' or 'integration'"
        )

    # Check hex portion length
    if len(hex_part) != 64:
        raise InvalidAPIKeyError(
            f"Invalid format: hex portion must be exactly 64 characters, got {len(hex_part)}"
        )

    # Check if hex portion contains only valid hex characters
    if not all(c in "0123456789abcdefABCDEF" for c in hex_part):
        raise InvalidAPIKeyError(
            "Invalid format: hex portion contains non-hexadecimal characters. "
            "Only 0-9 and a-f are allowed"
        )

    return True


def generate_api_key(environment: str = "dev") -> str:
    """
    Generate cryptographically secure API key.

    Uses secrets module (not random) for cryptographic security.

    Args:
        environment: Environment name (dev/integration/prod)

    Returns:
        API key in format: atg_{environment}_{64-hex-chars}

    Example:
        >>> key = generate_api_key("dev")
        >>> key.startswith("atg_dev_")
        True
        >>> len(key)
        72
    """
    if environment not in ("dev", "integration", "prod"):
        raise ValueError(
            f"Invalid environment: {environment}. Must be dev, integration, or prod"
        )

    # Generate 256-bit (32-byte) random value, convert to 64-char hex string
    random_hex = secrets.token_hex(32)

    return f"atg_{environment}_{random_hex}"


class APIKeyStore:
    """
    Secure API key storage and validation.

    Philosophy:
    - Constant-time comparison to prevent timing attacks
    - Expiration checking
    - Clear validation results

    Example:
        >>> config = {
        ...     "api_keys": {
        ...         "atg_dev_abc123...": {
        ...             "environment": "dev",
        ...             "client_id": "cli-001",
        ...             "expires_at": "2026-01-01T00:00:00"
        ...         }
        ...     }
        ... }
        >>> store = APIKeyStore(config)
        >>> result = store.validate("atg_dev_abc123...")
        >>> result["valid"]
        True
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize API key store.

        Args:
            config: Configuration dictionary with 'api_keys' key
        """
        self.keys = config.get("api_keys", {})

    def validate(self, api_key: str) -> Dict[str, Any]:
        """
        Validate API key using constant-time comparison.

        Args:
            api_key: API key to validate

        Returns:
            Dictionary with validation result:
            {
                "valid": bool,
                "environment": str (if valid),
                "client_id": str (if valid),
                "reason": str (if invalid)
            }
        """
        # Check format first (fail fast)
        try:
            validate_api_key(api_key)
        except InvalidAPIKeyError:
            return {"valid": False, "reason": "invalid_format"}

        # Check if key exists using constant-time comparison
        # This prevents timing attacks that could leak key information
        key_data = None
        for stored_key, data in self.keys.items():
            if hmac.compare_digest(stored_key, api_key):
                key_data = data
                break

        if not key_data:
            return {"valid": False, "reason": "unknown"}

        # Check expiration
        expires_at_str = key_data.get("expires_at")
        if expires_at_str:
            try:
                expires_at = datetime.fromisoformat(expires_at_str)
                # If expires_at is timezone-naive, assume it's UTC
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) > expires_at:
                    return {"valid": False, "reason": "expired"}
            except (ValueError, TypeError):
                return {"valid": False, "reason": "invalid_expiration"}

        # Valid key
        return {
            "valid": True,
            "environment": key_data.get("environment"),
            "client_id": key_data.get("client_id"),
        }


__all__ = [
    "APIKeyStore",
    "generate_api_key",
    "validate_api_key",
]
