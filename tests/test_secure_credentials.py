"""Unit tests for secure credentials module.

Tests credential validation, Key Vault integration, and environment fallback.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.utils.secure_credentials import (
    CredentialValidationError,
    Neo4jCredentials,
    get_neo4j_credentials,
)


class TestNeo4jCredentials:
    """Test Neo4jCredentials dataclass validation and security."""

    def test_valid_credentials_bolt(self):
        """Valid bolt:// URI should pass validation."""
        creds = Neo4jCredentials(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="test123",  # pragma: allowlist secret
        )
        assert creds.uri == "bolt://localhost:7687"
        assert creds.username == "neo4j"
        assert creds.password == "test123"  # pragma: allowlist secret

    def test_valid_credentials_neo4j(self):
        """Valid neo4j:// URI should pass validation."""
        creds = Neo4jCredentials(
            uri="neo4j://localhost:7687",
            username="neo4j",
            password="test123",  # pragma: allowlist secret
        )
        assert creds.uri == "neo4j://localhost:7687"

    def test_valid_credentials_with_ssl(self):
        """Valid bolt+s:// URI should pass validation."""
        creds = Neo4jCredentials(
            uri="bolt+s://secure.neo4j.io:7687",
            username="neo4j",
            password="test123",  # pragma: allowlist secret
        )
        assert creds.uri == "bolt+s://secure.neo4j.io:7687"

    def test_invalid_uri_format(self):
        """Invalid URI format should raise validation error."""
        with pytest.raises(CredentialValidationError) as exc_info:
            Neo4jCredentials(
                uri="http://localhost:7687",
                username="neo4j",
                password="test123",  # pragma: allowlist secret
            )
        assert "Invalid Neo4j URI format" in str(exc_info.value)

    def test_invalid_uri_missing_hostname(self):
        """URI without hostname should raise validation error."""
        with pytest.raises(CredentialValidationError):
            Neo4jCredentials(
                uri="bolt://", username="neo4j", password="test123"
            )  # pragma: allowlist secret

    def test_empty_username(self):
        """Empty username should raise validation error."""
        with pytest.raises(CredentialValidationError) as exc_info:
            Neo4jCredentials(
                uri="bolt://localhost:7687",
                username="",
                password="test123",  # pragma: allowlist secret
            )
        assert "Username cannot be empty" in str(exc_info.value)

    def test_whitespace_username(self):
        """Whitespace-only username should raise validation error."""
        with pytest.raises(CredentialValidationError):
            Neo4jCredentials(
                uri="bolt://localhost:7687",
                username="   ",
                password="test123",  # pragma: allowlist secret
            )

    def test_empty_password(self):
        """Empty password should raise validation error."""
        with pytest.raises(CredentialValidationError) as exc_info:
            Neo4jCredentials(uri="bolt://localhost:7687", username="neo4j", password="")
        assert "Password cannot be empty" in str(exc_info.value)

    def test_whitespace_password(self):
        """Whitespace-only password should raise validation error."""
        with pytest.raises(CredentialValidationError):
            Neo4jCredentials(
                uri="bolt://localhost:7687",
                username="neo4j",
                password="   ",  # pragma: allowlist secret
            )

    def test_repr_redacts_password(self):
        """__repr__ should redact password."""
        creds = Neo4jCredentials(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="supersecret123",  # pragma: allowlist secret
        )
        repr_str = repr(creds)
        assert "supersecret123" not in repr_str  # pragma: allowlist secret
        assert "***REDACTED***" in repr_str
        assert "neo4j" in repr_str
        assert "bolt://localhost:7687" in repr_str

    def test_str_redacts_password(self):
        """__str__ should redact password."""
        creds = Neo4jCredentials(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="supersecret123",  # pragma: allowlist secret
        )
        str_str = str(creds)
        assert "supersecret123" not in str_str  # pragma: allowlist secret
        assert "***REDACTED***" in str_str


class TestGetNeo4jCredentials:
    """Test get_neo4j_credentials function with various sources."""

    def test_environment_variables_full_uri(self):
        """Should load from NEO4J_URI env var."""
        with patch.dict(
            os.environ,
            {
                "NEO4J_URI": "bolt://localhost:7687",
                "NEO4J_USER": "neo4j",
                "NEO4J_PASSWORD": "testpass",  # pragma: allowlist secret
            },
            clear=True,
        ):
            creds = get_neo4j_credentials()
            assert creds.uri == "bolt://localhost:7687"
            assert creds.username == "neo4j"
            assert creds.password == "testpass"  # pragma: allowlist secret

    def test_environment_variables_port_only(self):
        """Should construct URI from NEO4J_PORT."""
        with patch.dict(
            os.environ,
            {
                "NEO4J_PORT": "7688",
                "NEO4J_USER": "neo4j",
                "NEO4J_PASSWORD": "testpass",
            },  # pragma: allowlist secret
            clear=True,
        ):
            creds = get_neo4j_credentials()
            assert creds.uri == "bolt://localhost:7688"
            assert creds.username == "neo4j"
            assert creds.password == "testpass"  # pragma: allowlist secret

    def test_environment_variables_default_username(self):
        """Should use default username if NEO4J_USER not set."""
        with patch.dict(
            os.environ,
            {
                "NEO4J_URI": "bolt://localhost:7687",
                "NEO4J_PASSWORD": "testpass",
            },  # pragma: allowlist secret
            clear=True,
        ):
            creds = get_neo4j_credentials()
            assert creds.username == "neo4j"

    def test_environment_variables_missing_password(self):
        """Should raise error if NEO4J_PASSWORD not set."""
        with patch.dict(os.environ, {"NEO4J_URI": "bolt://localhost:7687"}, clear=True):
            with pytest.raises(RuntimeError) as exc_info:
                get_neo4j_credentials()
            assert "not found" in str(exc_info.value).lower()

    def test_environment_variables_missing_uri_and_port(self):
        """Should raise error if neither URI nor PORT set."""
        with patch.dict(
            os.environ, {"NEO4J_PASSWORD": "testpass"}, clear=True
        ):  # pragma: allowlist secret
            with pytest.raises(RuntimeError):
                get_neo4j_credentials()

    @patch("src.utils.secure_credentials.SecretClient")
    @patch("src.utils.secure_credentials.DefaultAzureCredential")
    def test_keyvault_success(self, mock_credential, mock_secret_client):
        """Should load from Key Vault when configured."""
        # Mock Key Vault responses
        mock_client = MagicMock()
        mock_secret_client.return_value = mock_client

        # Mock secrets
        uri_secret = MagicMock()
        uri_secret.value = "bolt://keyvault.example.com:7687"
        username_secret = MagicMock()
        username_secret.value = "kv_user"
        password_secret = MagicMock()
        password_secret.value = "kv_pass"

        mock_client.get_secret.side_effect = [
            uri_secret,
            username_secret,
            password_secret,
        ]

        # Clear environment except Key Vault URL
        with patch.dict(
            os.environ,
            {"AZURE_KEYVAULT_URL": "https://myvault.vault.azure.net/"},
            clear=True,
        ):
            creds = get_neo4j_credentials()
            assert creds.uri == "bolt://keyvault.example.com:7687"
            assert creds.username == "kv_user"
            assert creds.password == "kv_pass"  # pragma: allowlist secret

    @patch("src.utils.secure_credentials.SecretClient")
    @patch("src.utils.secure_credentials.DefaultAzureCredential")
    def test_keyvault_fallback_to_env(self, mock_credential, mock_secret_client):
        """Should fall back to env vars if Key Vault secrets not found."""
        # Mock Key Vault to raise ResourceNotFoundError
        from azure.core.exceptions import ResourceNotFoundError

        mock_client = MagicMock()
        mock_secret_client.return_value = mock_client
        mock_client.get_secret.side_effect = ResourceNotFoundError("Secret not found")

        # Set environment variables as fallback
        with patch.dict(
            os.environ,
            {
                "AZURE_KEYVAULT_URL": "https://myvault.vault.azure.net/",
                "NEO4J_URI": "bolt://localhost:7687",
                "NEO4J_USER": "neo4j",
                "NEO4J_PASSWORD": "testpass",  # pragma: allowlist secret
            },
            clear=True,
        ):
            with patch("builtins.print") as mock_print:
                creds = get_neo4j_credentials()
                # Should warn about fallback
                mock_print.assert_called()
                assert any("WARNING" in str(call) for call in mock_print.call_args_list)

            assert creds.uri == "bolt://localhost:7687"
            assert creds.username == "neo4j"
            assert creds.password == "testpass"  # pragma: allowlist secret

    def test_no_credentials_anywhere(self):
        """Should raise clear error if no credentials found."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RuntimeError) as exc_info:
                get_neo4j_credentials()
            error_msg = str(exc_info.value)
            assert "not found" in error_msg.lower()
            assert "Key Vault" in error_msg or "Environment" in error_msg

    @patch("src.utils.secure_credentials.SecretClient")
    @patch("src.utils.secure_credentials.DefaultAzureCredential")
    def test_keyvault_url_parameter_override(self, mock_credential, mock_secret_client):
        """Should use keyvault_url parameter over environment variable."""
        mock_client = MagicMock()
        mock_secret_client.return_value = mock_client

        # Mock secrets
        uri_secret = MagicMock()
        uri_secret.value = "bolt://param.example.com:7687"
        username_secret = MagicMock()
        username_secret.value = "param_user"
        password_secret = MagicMock()
        password_secret.value = "param_pass"

        mock_client.get_secret.side_effect = [
            uri_secret,
            username_secret,
            password_secret,
        ]

        with patch.dict(
            os.environ,
            {"AZURE_KEYVAULT_URL": "https://env.vault.azure.net/"},
            clear=True,
        ):
            get_neo4j_credentials(keyvault_url="https://param.vault.azure.net/")
            # Verify parameter URL was used
            mock_secret_client.assert_called_with(
                vault_url="https://param.vault.azure.net/", credential=mock_credential()
            )

    def test_warn_on_env_fallback_disabled(self):
        """Should not warn when warn_on_env_fallback=False."""
        with patch.dict(
            os.environ,
            {
                "NEO4J_URI": "bolt://localhost:7687",
                "NEO4J_PASSWORD": "testpass",  # pragma: allowlist secret
            },
            clear=True,
        ):
            with patch("builtins.print") as mock_print:
                creds = get_neo4j_credentials(warn_on_env_fallback=False)
                mock_print.assert_not_called()

            assert creds.uri == "bolt://localhost:7687"


class TestCredentialValidation:
    """Test edge cases and validation logic."""

    def test_credentials_with_special_characters_in_password(self):
        """Password with special characters should be accepted."""
        creds = Neo4jCredentials(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="p@ssw0rd!#$%^&*()",  # pragma: allowlist secret
        )
        assert creds.password == "p@ssw0rd!#$%^&*()"  # pragma: allowlist secret

    def test_credentials_with_ipv4_uri(self):
        """IPv4 address in URI should be accepted."""
        creds = Neo4jCredentials(
            uri="bolt://192.168.1.100:7687",
            username="neo4j",
            password="test123",  # pragma: allowlist secret
        )
        assert creds.uri == "bolt://192.168.1.100:7687"

    def test_credentials_with_domain_uri(self):
        """Domain name in URI should be accepted."""
        creds = Neo4jCredentials(
            uri="bolt://neo4j.example.com:7687",
            username="neo4j",
            password="test123",  # pragma: allowlist secret
        )
        assert creds.uri == "bolt://neo4j.example.com:7687"

    def test_credentials_without_port(self):
        """URI without port should be accepted (will use default)."""
        creds = Neo4jCredentials(
            uri="bolt://localhost",
            username="neo4j",
            password="test123",  # pragma: allowlist secret
        )
        assert creds.uri == "bolt://localhost"
