"""
Client Configuration for ATG Remote Mode.

Philosophy:
- Ruthless simplicity - Load from env vars and .env files
- Zero-BS - All validation works (no stubs)
- Clear error messages for misconfiguration

Configuration Loading Order:
1. .env file (if exists)
2. Environment variables (override .env)
3. Validation

Public API:
    ATGClientConfig: Client configuration dataclass
    from_env(): Load from environment
    from_file(): Load from .env file
    to_dict(): Serialize (with redaction)
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from ..common.exceptions import ConfigurationError


@dataclass
class ATGClientConfig:
    """
    Client-side configuration for ATG operations.

    Philosophy: Simple dataclass with validation, no complex logic.

    Attributes:
        remote_mode: Enable remote execution (default: False)
        service_url: Base URL of ATG service
        api_key: Authentication API key
        request_timeout: Request timeout in seconds (default: 3600 = 60 min)
    """

    remote_mode: bool = False
    service_url: Optional[str] = None
    api_key: Optional[str] = None
    request_timeout: int = 3600  # 60 minutes default (no queue needed)

    def validate(self) -> None:
        """
        Validate configuration is complete and correct.

        Raises:
            ConfigurationError: If validation fails
        """
        if self.remote_mode:
            # Remote mode requires service URL and API key
            if not self.service_url:
                raise ConfigurationError(
                    "ATG_SERVICE_URL is required when remote mode is enabled"
                )

            if not self.api_key:
                raise ConfigurationError(
                    "ATG_API_KEY is required when remote mode is enabled"
                )

            # Validate service URL format
            if not self._is_valid_url(self.service_url):
                raise ConfigurationError(
                    f"Invalid URL format: {self.service_url}. "
                    f"Must start with https:// or http://"
                )

        # Validate timeout is positive
        if self.request_timeout <= 0:
            raise ConfigurationError(
                f"Request timeout must be positive, got {self.request_timeout}"
            )

    @staticmethod
    def _is_valid_url(url: str) -> bool:
        """Validate URL format (must be http:// or https://)."""
        try:
            result = urlparse(url)
            return all([result.scheme in ("http", "https"), result.netloc])
        except Exception:
            return False

    @staticmethod
    def _parse_bool(value: str) -> bool:
        """Parse boolean from string (handles various formats)."""
        if not value:
            return False
        return value.lower() in ("true", "1", "yes", "on")

    @classmethod
    def from_env(cls, validate: bool = False) -> "ATGClientConfig":
        """
        Load configuration from environment variables.

        Environment Variables:
            ATG_REMOTE_MODE: Enable remote mode (true/false)
            ATG_SERVICE_URL: Service base URL
            ATG_API_KEY: Authentication API key
            ATG_REQUEST_TIMEOUT: Request timeout in seconds

        Args:
            validate: Whether to validate config immediately (default: False)

        Returns:
            ATGClientConfig instance

        Raises:
            ConfigurationError: If validation enabled and fails
        """
        config = cls(
            remote_mode=cls._parse_bool(os.getenv("ATG_REMOTE_MODE", "false")),
            service_url=os.getenv("ATG_SERVICE_URL"),
            api_key=os.getenv("ATG_API_KEY"),
            request_timeout=int(os.getenv("ATG_REQUEST_TIMEOUT", "3600")),
        )

        if validate:
            config.validate()
        return config

    @classmethod
    def from_file(cls, filepath: str = ".env") -> "ATGClientConfig":
        """
        Load configuration from .env file.

        Environment variables override .env file values.

        Args:
            filepath: Path to .env file (default: .env)

        Returns:
            ATGClientConfig instance

        Raises:
            ConfigurationError: If file is malformed or validation fails
        """
        env_path = Path(filepath)

        # Load .env file if it exists
        if env_path.exists():
            try:
                env_vars = cls._parse_env_file(env_path)

                # Set as environment variables (will be overridden by actual env vars)
                for key, value in env_vars.items():
                    if key not in os.environ:
                        os.environ[key] = value
            except Exception as e:
                raise ConfigurationError(
                    f"Malformed .env file: {filepath}. Error: {e}"
                ) from e

        # Load from environment (includes .env values + overrides)
        return cls.from_env()

    @staticmethod
    def _parse_env_file(filepath: Path) -> Dict[str, str]:
        """
        Parse .env file into dictionary.

        Args:
            filepath: Path to .env file

        Returns:
            Dictionary of environment variables

        Raises:
            ConfigurationError: If file is malformed
        """
        env_vars = {}

        with open(filepath) as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()

                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue

                # Parse KEY=VALUE format
                if "=" not in line:
                    raise ConfigurationError(
                        f"Malformed line {line_num} in .env file: '{line}' "
                        f"(expected KEY=VALUE format)"
                    )

                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()

                # Remove quotes if present
                if value and value[0] in ('"', "'") and value[-1] == value[0]:
                    value = value[1:-1]

                env_vars[key] = value

        return env_vars

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for serialization.

        API keys are redacted for security.

        Returns:
            Dictionary representation with redacted secrets
        """
        return {
            "remote_mode": self.remote_mode,
            "service_url": self.service_url,
            "api_key": self._redact_api_key(self.api_key),
            "request_timeout": self.request_timeout,
        }

    @staticmethod
    def _redact_api_key(api_key: Optional[str]) -> Optional[str]:
        """Redact API key for logging/serialization."""
        if not api_key or len(api_key) < 12:
            return None

        # Show prefix only (e.g., "atg_dev_***")
        parts = api_key.split("_", 2)
        if len(parts) == 3:
            return f"{parts[0]}_{parts[1]}_***"
        return "***"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ATGClientConfig":
        """
        Create configuration from dictionary.

        Args:
            data: Configuration dictionary

        Returns:
            ATGClientConfig instance
        """
        return cls(
            remote_mode=data.get("remote_mode", False),
            service_url=data.get("service_url"),
            api_key=data.get("api_key"),
            request_timeout=data.get("request_timeout", 3600),
        )

    def __str__(self) -> str:
        """String representation with redacted secrets."""
        return (
            f"ATGClientConfig(remote_mode={self.remote_mode}, "
            f"service_url={self.service_url}, "
            f"api_key={self._redact_api_key(self.api_key)}, "
            f"request_timeout={self.request_timeout})"
        )


__all__ = ["ATGClientConfig"]
