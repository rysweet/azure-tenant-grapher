"""
Server Configuration for ATG Remote Service.

Philosophy:
- Ruthless simplicity - Load from env vars
- Zero-BS - All validation works
- Security by default - strict validation

Public API:
    ATGServerConfig: Server configuration
    Neo4jConfig: Neo4j connection configuration
"""

import os
import re
from dataclasses import dataclass, field
from typing import List

from ..common.exceptions import ConfigurationError


@dataclass
class ATGServerConfig:
    """
    Server-side configuration for ATG service.

    Philosophy: Simple dataclass with strict validation for security.

    Attributes:
        host: Server bind host (default: 0.0.0.0)
        port: Server bind port (default: 8000)
        workers: Number of worker processes (default: 4)
        api_keys: List of valid API keys
        target_tenant_id: Azure tenant ID to scan
        use_managed_identity: Use Azure Managed Identity (default: True)
        max_concurrent_operations: Max concurrent scans (default: 3)
        environment: Deployment environment (dev/integration/prod)
    """

    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    api_keys: List[str] = field(default_factory=list)
    target_tenant_id: str = ""
    use_managed_identity: bool = True
    max_concurrent_operations: int = 3
    environment: str = "dev"

    def validate(self) -> None:
        """
        Validate configuration is secure and complete.

        Raises:
            ConfigurationError: If validation fails
        """
        # Validate port range
        if not (1 <= self.port <= 65535):
            raise ConfigurationError(
                f"Port must be between 1 and 65535, got {self.port}"
            )

        # Validate worker count
        if self.workers < 1:
            raise ConfigurationError(f"Workers must be at least 1, got {self.workers}")

        # Validate tenant ID format (UUID or prefixed UUID in non-production)
        if self.target_tenant_id and not self._is_valid_tenant_id(self.target_tenant_id):
            raise ConfigurationError(
                f"Invalid tenant ID format: {self.target_tenant_id}. "
                f"Must be a valid UUID"
            )

        # Validate API keys in production
        if self.environment == "production" and not self.api_keys:
            raise ConfigurationError(
                "At least one API key required in production environment"
            )

        # Validate API keys match environment prefix (production only)
        if self.environment == "production":
            for api_key in self.api_keys:
                if not self._api_key_matches_environment(api_key):
                    raise ConfigurationError(
                        f"Environment mismatch: API key prefix does not match "
                        f"environment '{self.environment}'. "
                        f"Expected prefix: atg_{self.environment}_"
                    )

    @staticmethod
    def _is_valid_uuid(uuid_str: str) -> bool:
        """Validate UUID format."""
        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            re.IGNORECASE,
        )
        return bool(uuid_pattern.match(uuid_str))

    def _is_valid_tenant_id(self, tenant_id: str) -> bool:
        """Validate tenant ID format (UUID or prefixed UUID in non-production)."""
        if self._is_valid_uuid(tenant_id):
            return True

        if self.environment in ("dev", "integration"):
            parts = tenant_id.split("-", 2)
            if len(parts) >= 2:
                potential_uuid = tenant_id.split("-", 1)[1]
                if potential_uuid.startswith("tenant-"):
                    potential_uuid = potential_uuid[7:]
                return self._is_valid_uuid(potential_uuid)

        return False

    def _api_key_matches_environment(self, api_key: str) -> bool:
        """Check if API key prefix matches environment."""
        expected_prefix = f"atg_{self.environment}_"
        return api_key.startswith(expected_prefix)

    @classmethod
    def from_env(cls) -> "ATGServerConfig":
        """
        Load configuration from environment variables.

        Environment Variables:
            ATG_SERVER_HOST: Server bind host
            ATG_SERVER_PORT: Server bind port
            ATG_SERVER_WORKERS: Number of workers
            ATG_API_KEYS: Comma-separated API keys
            ATG_TARGET_TENANT_ID: Azure tenant ID
            ATG_USE_MANAGED_IDENTITY: Use managed identity (true/false)
            ATG_MAX_CONCURRENT_OPS: Max concurrent operations
            ENVIRONMENT: Deployment environment (dev/integration/prod)

        Returns:
            ATGServerConfig instance

        Raises:
            ConfigurationError: If validation fails
        """
        # Parse API keys (comma-separated, filter empty)
        api_keys_str = os.getenv("ATG_API_KEYS", "")
        api_keys = [k.strip() for k in api_keys_str.split(",") if k.strip()]

        config = cls(
            host=os.getenv("ATG_SERVER_HOST", "0.0.0.0"),
            port=int(os.getenv("ATG_SERVER_PORT", "8000")),
            workers=int(os.getenv("ATG_SERVER_WORKERS", "4")),
            api_keys=api_keys,
            target_tenant_id=os.getenv("ATG_TARGET_TENANT_ID", ""),
            use_managed_identity=cls._parse_bool(
                os.getenv("ATG_USE_MANAGED_IDENTITY", "true")
            ),
            max_concurrent_operations=int(os.getenv("ATG_MAX_CONCURRENT_OPS", "3")),
            environment=os.getenv("ENVIRONMENT", "dev"),
        )

        config.validate()
        return config

    @staticmethod
    def _parse_bool(value: str) -> bool:
        """Parse boolean from string."""
        return value.lower() in ("true", "1", "yes", "on")

    def __str__(self) -> str:
        """String representation with redacted API keys."""
        return (
            f"ATGServerConfig(host={self.host}, port={self.port}, "
            f"workers={self.workers}, api_keys=[REDACTED], "
            f"target_tenant_id={self._redact_tenant_id(self.target_tenant_id)}, "
            f"environment={self.environment})"
        )

    @staticmethod
    def _redact_tenant_id(tenant_id: str) -> str:
        """Redact tenant ID for logging."""
        if not tenant_id or len(tenant_id) < 20:
            return "***"
        # Show first 8 and last 12 chars
        return f"{tenant_id[:8]}-****-****-****-{tenant_id[-12:]}"


@dataclass
class Neo4jConfig:
    """
    Neo4j connection configuration.

    Philosophy: Security-focused with password strength validation.

    Attributes:
        uri: Neo4j connection URI
        user: Neo4j username (default: neo4j)
        password: Neo4j password
        max_pool_size: Max connection pool size (default: 50 for dev, 30 for integration)
    """

    uri: str
    user: str = "neo4j"
    password: str = ""
    max_pool_size: int = 50

    def validate(self) -> None:
        """
        Validate Neo4j configuration and password strength.

        Raises:
            ConfigurationError: If validation fails
        """
        if not self.uri:
            raise ConfigurationError("Neo4j URI is required")

        if not self.user:
            raise ConfigurationError("Neo4j user is required")

        if not self.password:
            raise ConfigurationError("Neo4j password is required")

        # Validate password strength (security requirement)
        if len(self.password) < 16:
            raise ConfigurationError(
                f"Neo4j password must be at least 16 characters, "
                f"got {len(self.password)}"
            )

        # Check complexity (uppercase, lowercase, digit, special)
        has_upper = any(c.isupper() for c in self.password)
        has_lower = any(c.islower() for c in self.password)
        has_digit = any(c.isdigit() for c in self.password)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in self.password)

        if not all([has_upper, has_lower, has_digit, has_special]):
            raise ConfigurationError(
                "Neo4j password must contain uppercase, lowercase, "
                "digit, and special character"
            )

    @classmethod
    def from_env(cls, environment: str = "dev") -> "Neo4jConfig":
        """
        Load Neo4j configuration from environment variables.

        Environment Variables:
            NEO4J_URI: Neo4j connection URI
            NEO4J_USER: Neo4j username (default: neo4j)
            NEO4J_PASSWORD: Neo4j password
            NEO4J_DEV_POOL_SIZE: Pool size for dev (default: 50)
            NEO4J_INTEGRATION_POOL_SIZE: Pool size for integration (default: 30)

        Args:
            environment: Environment name (dev/integration)

        Returns:
            Neo4jConfig instance

        Raises:
            ConfigurationError: If validation fails
        """
        # Get environment-specific pool size
        pool_size_var = f"NEO4J_{environment.upper()}_POOL_SIZE"
        default_pool_size = 50 if environment == "dev" else 30
        pool_size = int(os.getenv(pool_size_var, str(default_pool_size)))

        config = cls(
            uri=os.getenv("NEO4J_URI", ""),
            user=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", ""),
            max_pool_size=pool_size,
        )

        config.validate()
        return config


__all__ = ["ATGServerConfig", "Neo4jConfig"]
