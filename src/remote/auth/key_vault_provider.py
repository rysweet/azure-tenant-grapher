"""Azure Key Vault secret provider for production deployments.

Philosophy:
- Ruthless simplicity: Fetch secrets from Key Vault
- Graceful fallback: Use env vars if Key Vault unavailable
- Zero-BS: Working implementation with error handling

Issue #580: Security hardening for production deployment
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class KeyVaultProvider:
    """Fetches secrets from Azure Key Vault with env var fallback.

    In production, secrets come from Key Vault.
    In development, falls back to environment variables.
    """

    def __init__(self, vault_url: Optional[str] = None):
        """Initialize Key Vault provider.

        Args:
            vault_url: Key Vault URL (e.g., https://my-vault.vault.azure.net/)
                      If None, uses AZURE_KEYVAULT_URL env var
        """
        self.vault_url = vault_url or os.getenv("AZURE_KEYVAULT_URL")
        self.client = None

        if self.vault_url:
            try:
                from azure.identity import DefaultAzureCredential
                from azure.keyvault.secrets import SecretClient

                credential = DefaultAzureCredential()
                self.client = SecretClient(
                    vault_url=self.vault_url, credential=credential
                )
                logger.info(f"Key Vault provider initialized: {self.vault_url}")
            except ImportError:
                logger.warning(
                    "Azure Key Vault SDK not available - falling back to env vars"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to initialize Key Vault client: {e} - falling back to env vars"
                )
        else:
            logger.info("No Key Vault URL configured - using env vars only")

    def get_secret(
        self, secret_name: str, env_var_name: Optional[str] = None
    ) -> Optional[str]:
        """Get secret from Key Vault with env var fallback.

        Args:
            secret_name: Name of secret in Key Vault
            env_var_name: Environment variable name for fallback

        Returns:
            Secret value or None if not found
        """
        # Try Key Vault first
        if self.client:
            try:
                secret = self.client.get_secret(secret_name)
                logger.debug(f"Retrieved secret '{secret_name}' from Key Vault")
                return secret.value
            except Exception as e:
                logger.warning(
                    f"Failed to fetch secret '{secret_name}' from Key Vault: {e}"
                )

        # Fallback to environment variable
        env_name = env_var_name or secret_name.upper().replace("-", "_")
        value = os.getenv(env_name)

        if value:
            logger.debug(
                f"Using env var '{env_name}' as fallback for secret '{secret_name}'"
            )
        else:
            logger.warning(
                f"Secret '{secret_name}' not found in Key Vault or env var '{env_name}'"
            )

        return value

    def get_neo4j_credentials(self) -> tuple[str, str]:
        """Get Neo4j credentials (username, password).

        Returns:
            Tuple of (username, password)
        """
        username = self.get_secret("neo4j-username", "NEO4J_USER") or "neo4j"
        password = self.get_secret("neo4j-password", "NEO4J_PASSWORD") or "password"
        return username, password

    def get_api_keys(self) -> list[str]:
        """Get valid API keys for authentication.

        Returns:
            List of valid API keys
        """
        # Try Key Vault first
        keys_str = self.get_secret("api-keys", "API_KEYS")
        if not keys_str:
            logger.warning("No API keys configured!")
            return []

        # API keys can be comma-separated
        keys = [k.strip() for k in keys_str.split(",") if k.strip()]
        logger.info(f"Loaded {len(keys)} API keys")
        return keys


__all__ = ["KeyVaultProvider"]
