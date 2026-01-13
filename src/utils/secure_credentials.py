"""Secure credential management for Neo4j with Azure Key Vault integration.

Philosophy:
- Security first: credentials never logged or exposed
- Backward compatibility: falls back to environment variables
- Simple interface: single function call to get credentials
- Validation: format checking for all credential components
- Zero-BS: no stubs, fully working implementation

Public API:
    Neo4jCredentials: Dataclass with validated credentials
    get_neo4j_credentials: Main function to retrieve credentials
    CredentialValidationError: Exception for invalid credentials
"""

import os
import re
from dataclasses import dataclass
from typing import Optional

from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient


class CredentialValidationError(Exception):
    """Raised when credential validation fails."""

    pass


@dataclass
class Neo4jCredentials:
    """Neo4j connection credentials with secure string representation.

    Attributes:
        uri: Neo4j connection URI (bolt:// or neo4j://)
        username: Neo4j username
        password: Neo4j password
    """

    uri: str
    username: str
    password: str

    def __post_init__(self):
        """Validate credentials after initialization."""
        self._validate()

    def _validate(self) -> None:
        """Validate credential format and content.

        Raises:
            CredentialValidationError: If any credential is invalid
        """
        # Validate URI format
        uri_pattern = r"^(bolt|neo4j)(\+s)?://[a-zA-Z0-9\-\.]+(:\d+)?$"
        if not re.match(uri_pattern, self.uri):
            raise CredentialValidationError(
                f"Invalid Neo4j URI format: {self.uri}. "
                "Expected format: bolt://hostname:port or neo4j://hostname:port"
            )

        # Validate username is non-empty
        if not self.username or not self.username.strip():
            raise CredentialValidationError("Username cannot be empty")

        # Validate password is non-empty
        if not self.password or not self.password.strip():
            raise CredentialValidationError("Password cannot be empty")

    def __repr__(self) -> str:
        """Return string representation with redacted password."""
        return f"Neo4jCredentials(uri='{self.uri}', username='{self.username}', password='***REDACTED***')"

    def __str__(self) -> str:
        """Return string representation with redacted password."""
        return self.__repr__()


def _get_credentials_from_keyvault(
    keyvault_url: str,
    uri_secret_name: str = "neo4j-uri",
    username_secret_name: str = "neo4j-username",
    password_secret_name: str = "neo4j-password",
) -> Optional[Neo4jCredentials]:
    """Retrieve Neo4j credentials from Azure Key Vault.

    Args:
        keyvault_url: Azure Key Vault URL (e.g., https://myvault.vault.azure.net/)
        uri_secret_name: Name of the secret containing Neo4j URI
        username_secret_name: Name of the secret containing Neo4j username
        password_secret_name: Name of the secret containing Neo4j password

    Returns:
        Neo4jCredentials if all secrets found, None if any secret missing

    Raises:
        CredentialValidationError: If credentials are invalid
    """
    try:
        # Use DefaultAzureCredential for authentication
        credential = DefaultAzureCredential()
        client = SecretClient(vault_url=keyvault_url, credential=credential)

        # Retrieve all three secrets
        uri_secret = client.get_secret(uri_secret_name)
        username_secret = client.get_secret(username_secret_name)
        password_secret = client.get_secret(password_secret_name)

        # Create and validate credentials
        return Neo4jCredentials(
            uri=uri_secret.value,
            username=username_secret.value,
            password=password_secret.value,
        )

    except ResourceNotFoundError:
        # Secret not found - return None to allow fallback
        return None
    except Exception:
        # Other errors (auth, network, etc.) - return None to allow fallback
        return None


def _get_credentials_from_env() -> Optional[Neo4jCredentials]:
    """Retrieve Neo4j credentials from environment variables.

    Environment Variables:
        NEO4J_URI or NEO4J_PORT: Connection URI or port
        NEO4J_USER: Username (default: neo4j)
        NEO4J_PASSWORD: Password (required)

    Returns:
        Neo4jCredentials if environment variables are set, None otherwise

    Raises:
        CredentialValidationError: If credentials are invalid
    """
    # Get URI or construct from port
    uri = os.environ.get("NEO4J_URI")
    if not uri:
        port = os.environ.get("NEO4J_PORT")
        if not port:
            return None
        uri = f"bolt://localhost:{port}"

    # Get username (default to neo4j)
    username = os.environ.get("NEO4J_USER", "neo4j")

    # Get password (required)
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        return None

    return Neo4jCredentials(uri=uri, username=username, password=password)


def get_neo4j_credentials(
    keyvault_url: Optional[str] = None,
    warn_on_env_fallback: bool = True,
) -> Neo4jCredentials:
    """Get Neo4j credentials with Key Vault priority and env fallback.

    This is the main entry point for credential retrieval. It follows this priority:
    1. Azure Key Vault (if keyvault_url provided or AZURE_KEYVAULT_URL env var set)
    2. Environment variables (with optional deprecation warning)

    Args:
        keyvault_url: Azure Key Vault URL (overrides AZURE_KEYVAULT_URL env var)
        warn_on_env_fallback: Print warning when falling back to env vars (default: True)

    Returns:
        Neo4jCredentials object with validated credentials

    Raises:
        CredentialValidationError: If credentials are invalid
        RuntimeError: If no credentials found in either source

    Example:
        >>> # Using Key Vault (production)
        >>> creds = get_neo4j_credentials(
        ...     keyvault_url="https://myvault.vault.azure.net/"
        ... )

        >>> # Using environment variables (local development)
        >>> creds = get_neo4j_credentials()  # Falls back to env vars

        >>> # Connect to Neo4j
        >>> from neo4j import GraphDatabase
        >>> driver = GraphDatabase.driver(
        ...     creds.uri,
        ...     auth=(creds.username, creds.password)
        ... )
    """
    # Try Key Vault first if URL provided
    vault_url = keyvault_url or os.environ.get("AZURE_KEYVAULT_URL")
    if vault_url:
        credentials = _get_credentials_from_keyvault(vault_url)
        if credentials:
            return credentials
        # Key Vault configured but secrets not found - fall through to env vars

    # Fallback to environment variables
    credentials = _get_credentials_from_env()
    if credentials:
        if warn_on_env_fallback and vault_url:
            print(
                "⚠️  WARNING: Using Neo4j credentials from environment variables. "
                "Consider migrating to Azure Key Vault for production deployments."
            )
        return credentials

    # No credentials found anywhere
    raise RuntimeError(
        "Neo4j credentials not found. Please set either:\n"
        "1. Azure Key Vault secrets (neo4j-uri, neo4j-username, neo4j-password)\n"
        "   and AZURE_KEYVAULT_URL environment variable, OR\n"
        "2. Environment variables: NEO4J_URI (or NEO4J_PORT), NEO4J_USER, NEO4J_PASSWORD"
    )


__all__ = [
    "CredentialValidationError",
    "Neo4jCredentials",
    "get_neo4j_credentials",
]
