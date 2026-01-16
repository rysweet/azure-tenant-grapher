"""
Credential Provider for Data Plane Plugins.

This module implements a flexible credential resolution system with a priority chain:
1. Explicit credentials (CLI flags)
2. Environment variables
3. DefaultAzureCredential (Managed Identity, Azure CLI, etc.)
4. Interactive browser login (optional)

Features:
- Thread-safe credential caching
- Credential validation
- Support for multiple tenants
- Clear error messages with debugging information
- Protocol-based interface for plugin integration
"""

import logging
import os
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional

from azure.core.credentials import TokenCredential  # type: ignore[import-untyped]
from azure.core.exceptions import (
    ClientAuthenticationError,  # type: ignore[import-untyped]
)
from azure.identity import (  # type: ignore[import-untyped]
    ClientSecretCredential,
    DefaultAzureCredential,
    InteractiveBrowserCredential,
)

logger = logging.getLogger(__name__)


@dataclass
class CredentialConfig:
    """Configuration for credential resolution.

    Attributes:
        client_id: Azure service principal client ID (explicit credentials - priority 1)
        client_secret: Azure service principal client secret (explicit credentials - priority 1)
        tenant_id: Azure tenant ID (explicit credentials - priority 1)
        allow_interactive: Allow interactive browser login as last resort (priority 4)
        use_environment: Read credentials from environment variables (priority 2)
        connection_strings: Optional resource-specific connection strings
    """

    # Explicit credentials (highest priority - Level 1)
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    tenant_id: Optional[str] = None

    # Flags
    allow_interactive: bool = False  # Prompt user if needed (Level 4)
    use_environment: bool = True  # Read from env vars (Level 2)

    # Resource-specific connection strings
    connection_strings: Optional[Dict[str, str]] = field(default_factory=dict)


class CredentialProvider:
    """
    Manages Azure credential resolution with priority chain.

    Priority Chain:
    1. Explicit credentials (service principal via client_id, client_secret, tenant_id)
    2. Environment variables (AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID)
    3. DefaultAzureCredential (Managed Identity, Azure CLI, VS Code, etc.)
    4. Interactive browser login (if allowed)

    Features:
    - Thread-safe credential caching
    - Credential validation
    - Clear error messages
    - Debugging information about which level was used

    Example:
        >>> config = CredentialConfig(
        ...     client_id="xxx",
        ...     client_secret="yyy",  # pragma: allowlist secret  # pragma: allowlist secret
        ...     tenant_id="zzz"
        ... )
        >>> provider = CredentialProvider(config)
        >>> credential = provider.get_credential()
        >>> # Use credential with Azure SDK
    """

    def __init__(self, config: Optional[CredentialConfig] = None):
        """Initialize credential provider with optional configuration.

        Args:
            config: Optional CredentialConfig. If None, uses default config.
        """
        self.config = config or CredentialConfig()
        self._credential_cache: Optional[TokenCredential] = None
        self._credential_source: Optional[str] = None
        self._lock = threading.Lock()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def get_credential(self) -> TokenCredential:
        """Get Azure credential using priority chain.

        This method is thread-safe and caches credentials for the session.

        Returns:
            Azure TokenCredential object

        Raises:
            ValueError: If no credentials could be resolved
            ClientAuthenticationError: If credential validation fails for all available sources
        """
        # Thread-safe credential caching
        with self._lock:
            if self._credential_cache:
                self.logger.debug(
                    f"Using cached credential from: {self._credential_source}"
                )
                return self._credential_cache

            # Try each priority level in order with validation
            # Priority 1: Explicit credentials
            if self._has_explicit_credentials():
                credential, source = self._get_explicit_credential()
                if self._validate_credential(credential):
                    self._credential_cache = credential
                    self._credential_source = source
                    self.logger.info(
                        f"Successfully resolved credentials from: {source}"
                    )
                    return credential
                else:
                    self.logger.warning("Explicit credentials failed validation")

            # Priority 2: Environment variables
            if self.config.use_environment and self._has_env_credentials():
                credential, source = self._get_env_credential()
                if self._validate_credential(credential):
                    self._credential_cache = credential
                    self._credential_source = source
                    self.logger.info(
                        f"Successfully resolved credentials from: {source}"
                    )
                    return credential
                else:
                    self.logger.warning("Environment credentials failed validation")

            # Priority 3: DefaultAzureCredential
            if self._try_default_credential():
                try:
                    credential, source = self._get_default_credential()
                    if self._validate_credential(credential):
                        self._credential_cache = credential
                        self._credential_source = source
                        self.logger.info(
                            f"Successfully resolved credentials from: {source}"
                        )
                        return credential
                    else:
                        self.logger.warning("DefaultAzureCredential failed validation")
                except Exception as e:
                    self.logger.warning(str(f"DefaultAzureCredential failed: {e}"))

            # Priority 4: Interactive (if allowed)
            if self.config.allow_interactive:
                credential, source = self._get_interactive_credential()
                if self._validate_credential(credential):
                    self._credential_cache = credential
                    self._credential_source = source
                    self.logger.info(
                        f"Successfully resolved credentials from: {source}"
                    )
                    return credential
                else:
                    self.logger.error("Interactive credentials failed validation")

            # Failed to resolve credentials from any source
            raise ValueError(
                "Could not resolve Azure credentials. Please provide credentials via one of:\n"
                "  1. CLI flags: --sp-client-id, --sp-client-secret, --sp-tenant-id\n"
                "  2. Environment variables: AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID\n"
                "  3. Azure CLI: Run 'az login' to authenticate\n"
                "  4. Interactive login: Use --dataplane-interactive flag"
            )

    def get_credential_source(self) -> Optional[str]:
        """Get the source of the current credential for debugging.

        Returns:
            String describing credential source (e.g., "explicit", "environment", "default", "interactive")
            or None if no credential is cached.
        """
        return self._credential_source

    def get_connection_string(self, resource_id: str) -> Optional[str]:
        """Get resource-specific connection string if available.

        Args:
            resource_id: Azure resource ID

        Returns:
            Connection string or None if not configured
        """
        if not self.config.connection_strings:
            return None
        return self.config.connection_strings.get(resource_id)

    def clear_cache(self) -> None:
        """Clear cached credential. Next get_credential() call will re-resolve."""
        with self._lock:
            self._credential_cache = None
            self._credential_source = None
            self.logger.debug("Credential cache cleared")

    # ============ Priority Level 1: Explicit Credentials ============

    def _has_explicit_credentials(self) -> bool:
        """Check if explicit credentials are configured."""
        return bool(
            self.config.client_id
            and self.config.client_secret
            and self.config.tenant_id
        )

    def _get_explicit_credential(self) -> tuple[TokenCredential, str]:
        """Get credential from explicit configuration.

        Returns:
            Tuple of (credential, source_description)
        """
        self.logger.info("Using explicit service principal credentials")
        credential = ClientSecretCredential(
            tenant_id=self.config.tenant_id,  # type: ignore[arg-type]
            client_id=self.config.client_id,  # type: ignore[arg-type]
            client_secret=self.config.client_secret,  # type: ignore[arg-type]
        )
        return credential, "explicit"

    # ============ Priority Level 2: Environment Variables ============

    def _has_env_credentials(self) -> bool:
        """Check if environment variables are set."""
        return bool(
            os.getenv("AZURE_CLIENT_ID")
            and os.getenv("AZURE_CLIENT_SECRET")
            and os.getenv("AZURE_TENANT_ID")
        )

    def _get_env_credential(self) -> tuple[TokenCredential, str]:
        """Get credential from environment variables.

        Returns:
            Tuple of (credential, source_description)
        """
        self.logger.info("Using credentials from environment variables")
        credential = ClientSecretCredential(
            tenant_id=os.getenv("AZURE_TENANT_ID"),  # type: ignore[arg-type]
            client_id=os.getenv("AZURE_CLIENT_ID"),  # type: ignore[arg-type]
            client_secret=os.getenv("AZURE_CLIENT_SECRET"),  # type: ignore[arg-type]
        )
        return credential, "environment"

    # ============ Priority Level 3: DefaultAzureCredential ============

    def _try_default_credential(self) -> bool:
        """Check if DefaultAzureCredential is likely to work.

        This is a best-effort check. We'll still validate the credential later.

        Returns:
            True if DefaultAzureCredential should be attempted
        """
        # Check for common indicators that DefaultAzureCredential will work
        # - Azure CLI logged in
        # - Running in Azure (managed identity)
        # - VS Code authenticated
        # For now, always attempt DefaultAzureCredential as it's the fallback
        return True

    def _get_default_credential(self) -> tuple[TokenCredential, str]:
        """Get credential using DefaultAzureCredential.

        Returns:
            Tuple of (credential, source_description)
        """
        self.logger.info(
            "Using DefaultAzureCredential (Managed Identity, Azure CLI, VS Code, etc.)"
        )
        credential = DefaultAzureCredential()
        return credential, "default"

    # ============ Priority Level 4: Interactive Login ============

    def _get_interactive_credential(self) -> tuple[TokenCredential, str]:
        """Get credential via interactive browser login.

        Returns:
            Tuple of (credential, source_description)
        """
        self.logger.info("Prompting for interactive browser login")
        credential = InteractiveBrowserCredential()
        return credential, "interactive"

    # ============ Validation ============

    def _validate_credential(self, credential: TokenCredential) -> bool:
        """Validate credential by attempting to get a token.

        Args:
            credential: Credential to validate

        Returns:
            True if credential is valid, False otherwise
        """
        try:
            # Attempt to get a token for Azure Resource Manager
            # This validates the credential without making any actual API calls
            token = credential.get_token("https://management.azure.com/.default")

            if not token or not token.token:
                self.logger.warning("Credential validation failed: empty token")
                return False

            self.logger.debug("Credential validation successful")
            return True

        except ClientAuthenticationError as e:
            self.logger.error(str(f"Credential validation failed: {e}"))
            return False
        except Exception as e:
            self.logger.error(
                str(f"Unexpected error during credential validation: {e}")
            )
            return False


# Protocol-based interface for duck-typing
class CredentialProviderProtocol:
    """Protocol for credential provider (duck typing).

    This allows plugins to accept any object that implements these methods,
    not just CredentialProvider instances.
    """

    def get_credential(self) -> TokenCredential:
        """Get Azure credential."""
        ...

    def get_connection_string(self, resource_id: str) -> Optional[str]:
        """Get resource-specific connection string."""
        ...
