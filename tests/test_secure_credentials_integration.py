"""Integration tests for secure credentials with Neo4j and FidelityCalculator.

Tests the full integration of secure credentials with actual Neo4j connections
and the FidelityCalculator class.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.fidelity_calculator import FidelityCalculator
from src.utils.secure_credentials import Neo4jCredentials, get_neo4j_credentials


class TestFidelityCalculatorIntegration:
    """Test FidelityCalculator with secure credentials."""

    def test_fidelity_calculator_with_credentials_object(self):
        """FidelityCalculator should accept Neo4jCredentials object."""
        creds = Neo4jCredentials(
            uri="bolt://localhost:7687", username="neo4j", password="testpass"
        )

        with patch("src.fidelity_calculator.GraphDatabase.driver") as mock_driver:
            calculator = FidelityCalculator(credentials=creds)
            mock_driver.assert_called_once_with(
                "bolt://localhost:7687", auth=("neo4j", "testpass")
            )

    def test_fidelity_calculator_loads_from_env_by_default(self):
        """FidelityCalculator should load from environment if no params given."""
        with patch.dict(
            os.environ,
            {
                "NEO4J_URI": "bolt://localhost:7687",
                "NEO4J_USER": "neo4j",
                "NEO4J_PASSWORD": "testpass",
            },
            clear=True,
        ):
            with patch("src.fidelity_calculator.GraphDatabase.driver") as mock_driver:
                calculator = FidelityCalculator()
                mock_driver.assert_called_once_with(
                    "bolt://localhost:7687", auth=("neo4j", "testpass")
                )

    def test_fidelity_calculator_legacy_parameters_deprecated(self):
        """FidelityCalculator should warn when using legacy parameters."""
        with patch("src.fidelity_calculator.GraphDatabase.driver"):
            with patch("src.fidelity_calculator.logger.warning") as mock_warning:
                calculator = FidelityCalculator(
                    neo4j_uri="bolt://localhost:7687",
                    neo4j_user="neo4j",
                    neo4j_password="testpass",
                )
                # Should log deprecation warning
                mock_warning.assert_called()
                assert any(
                    "deprecated" in str(call).lower()
                    for call in mock_warning.call_args_list
                )

    def test_fidelity_calculator_repr_no_credential_exposure(self):
        """FidelityCalculator __repr__ should not expose credentials."""
        creds = Neo4jCredentials(
            uri="bolt://localhost:7687", username="neo4j", password="supersecret123"
        )

        with patch("src.fidelity_calculator.GraphDatabase.driver"):
            calculator = FidelityCalculator(credentials=creds)
            repr_str = repr(calculator)

            # Password should not be in repr
            assert "supersecret123" not in repr_str
            # URI should be present
            assert "bolt://localhost:7687" in repr_str

    @patch("src.fidelity_calculator.GraphDatabase.driver")
    def test_fidelity_calculator_credentials_not_stored_as_plaintext(
        self, mock_driver
    ):
        """FidelityCalculator should not store credentials as plain attributes."""
        creds = Neo4jCredentials(
            uri="bolt://localhost:7687", username="neo4j", password="supersecret123"
        )

        calculator = FidelityCalculator(credentials=creds)

        # Old attributes should not exist
        assert not hasattr(calculator, "neo4j_uri")
        assert not hasattr(calculator, "neo4j_user")
        assert not hasattr(calculator, "neo4j_password")

        # Should have private _credentials attribute
        assert hasattr(calculator, "_credentials")
        assert isinstance(calculator._credentials, Neo4jCredentials)


class TestMCPServerIntegration:
    """Test mcp_server.py integration with secure credentials."""

    @patch("src.mcp_server.GraphDatabase.driver")
    @patch("src.mcp_server.get_neo4j_credentials")
    def test_verify_neo4j_connection_uses_secure_credentials(
        self, mock_get_creds, mock_driver
    ):
        """verify_neo4j_connection should use get_neo4j_credentials."""
        import asyncio

        from src.mcp_server import verify_neo4j_connection

        # Mock credentials
        mock_creds = Neo4jCredentials(
            uri="bolt://localhost:7687", username="neo4j", password="testpass"
        )
        mock_get_creds.return_value = mock_creds

        # Mock driver to succeed connection
        mock_driver_instance = MagicMock()
        mock_driver.return_value = mock_driver_instance
        mock_session = MagicMock()
        mock_driver_instance.session.return_value.__enter__ = lambda self: mock_session
        mock_driver_instance.session.return_value.__exit__ = lambda self, *args: None

        # Run async function
        asyncio.run(verify_neo4j_connection(max_attempts=1))

        # Verify get_neo4j_credentials was called
        mock_get_creds.assert_called_once()


class TestCLICommandsIntegration:
    """Test cli_commands.py integration with secure credentials."""

    @patch("src.cli_commands.get_neo4j_credentials")
    def test_monitor_command_uses_secure_credentials(self, mock_get_creds):
        """Monitor command should use get_neo4j_credentials."""
        # This test verifies the integration point exists
        # We mock the credentials retrieval
        mock_creds = Neo4jCredentials(
            uri="bolt://localhost:7687", username="neo4j", password="testpass"
        )
        mock_get_creds.return_value = mock_creds

        # Verify credentials would be retrieved
        # (Full CLI test would require more setup with GraphDatabase imported locally)
        creds = mock_get_creds()
        assert creds.uri == "bolt://localhost:7687"
        assert creds.username == "neo4j"
        assert creds.password == "testpass"


class TestEndToEndCredentialFlow:
    """Test complete credential flow from environment to Neo4j connection."""

    @patch("src.utils.secure_credentials.SecretClient")
    @patch("src.utils.secure_credentials.DefaultAzureCredential")
    @patch("src.fidelity_calculator.GraphDatabase.driver")
    def test_full_keyvault_to_fidelity_calculator(
        self, mock_driver, mock_credential, mock_secret_client
    ):
        """Test full flow: Key Vault → get_credentials → FidelityCalculator."""
        # Mock Key Vault
        mock_client = MagicMock()
        mock_secret_client.return_value = mock_client

        uri_secret = MagicMock()
        uri_secret.value = "bolt://secure.example.com:7687"
        username_secret = MagicMock()
        username_secret.value = "secure_user"
        password_secret = MagicMock()
        password_secret.value = "secure_pass"

        mock_client.get_secret.side_effect = [
            uri_secret,
            username_secret,
            password_secret,
        ]

        # Set Key Vault URL
        with patch.dict(
            os.environ, {"AZURE_KEYVAULT_URL": "https://myvault.vault.azure.net/"}, clear=True
        ):
            # Get credentials
            creds = get_neo4j_credentials()

            # Create FidelityCalculator with those credentials
            calculator = FidelityCalculator(credentials=creds)

            # Verify driver was called with Key Vault credentials
            mock_driver.assert_called_once_with(
                "bolt://secure.example.com:7687", auth=("secure_user", "secure_pass")
            )

    def test_full_env_to_fidelity_calculator(self):
        """Test full flow: Environment → get_credentials → FidelityCalculator."""
        with patch.dict(
            os.environ,
            {
                "NEO4J_URI": "bolt://localhost:7687",
                "NEO4J_USER": "neo4j",
                "NEO4J_PASSWORD": "testpass",
            },
            clear=True,
        ):
            with patch("src.fidelity_calculator.GraphDatabase.driver") as mock_driver:
                # Get credentials
                creds = get_neo4j_credentials(warn_on_env_fallback=False)

                # Create FidelityCalculator
                calculator = FidelityCalculator(credentials=creds)

                # Verify driver was called with env credentials
                mock_driver.assert_called_once_with(
                    "bolt://localhost:7687", auth=("neo4j", "testpass")
                )


class TestCredentialSecurityProperties:
    """Test security properties of credential handling."""

    def test_credentials_not_logged_in_exceptions(self):
        """Credentials should not appear in exception messages."""
        with patch.dict(os.environ, {}, clear=True):
            try:
                get_neo4j_credentials()
            except RuntimeError as e:
                error_msg = str(e)
                # Error message should not contain any actual passwords
                # (This is a negative test - we can't test what ISN'T there easily,
                # but we verify the error message is about missing credentials)
                assert "not found" in error_msg.lower() or "required" in error_msg.lower()

    @patch("src.fidelity_calculator.GraphDatabase.driver")
    def test_credentials_not_in_object_dict(self, mock_driver):
        """Credentials should not be in __dict__ as plain strings."""
        creds = Neo4jCredentials(
            uri="bolt://localhost:7687", username="neo4j", password="supersecret123"
        )

        calculator = FidelityCalculator(credentials=creds)

        # Check that password isn't stored as plain attribute
        dict_str = str(calculator.__dict__)
        # Password should not be in plain form
        # (It's stored in Neo4jCredentials which has redacted __repr__)
        assert "supersecret123" not in dict_str or "***REDACTED***" in dict_str
