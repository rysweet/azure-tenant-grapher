"""
Test credential redaction in debug output.

Verifies that sensitive credentials (NEO4J_PASSWORD, NEO4J_AUTH, AZURE_CLIENT_SECRET)
are properly redacted from debug output to prevent exposure in logs.
"""
import os
from io import StringIO
from unittest.mock import patch

from src.container_manager import Neo4jContainerManager


def test_credential_redaction_in_debug_output():
    """Test that sensitive credentials are redacted in debug mode."""
    # Set up test environment with fake test values (not real secrets)
    # pragma: allowlist-secret (these are test values for verifying redaction)
    test_password = "super-secret-password-123"  # pragma: allowlist secret
    test_client_secret = "azure-secret-456"  # pragma: allowlist secret
    test_api_key = "openai-key-789"  # pragma: allowlist secret
    test_anthropic_key = "anthropic-key-abc"  # pragma: allowlist secret

    os.environ["NEO4J_PORT"] = "7687"
    os.environ["NEO4J_PASSWORD"] = test_password
    os.environ["AZURE_CLIENT_SECRET"] = test_client_secret
    os.environ["OPENAI_API_KEY"] = test_api_key
    os.environ["ANTHROPIC_API_KEY"] = test_anthropic_key

    # Capture stdout to check debug output
    with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
        # Create manager with debug enabled
        manager = Neo4jContainerManager(debug=True)

        # Get the captured output
        output = mock_stdout.getvalue()

        # Verify sensitive values are NOT in output
        assert test_password not in output, "NEO4J_PASSWORD should be redacted"
        assert test_client_secret not in output, "AZURE_CLIENT_SECRET should be redacted"
        assert test_api_key not in output, "OPENAI_API_KEY should be redacted"
        assert test_anthropic_key not in output, "ANTHROPIC_API_KEY should be redacted"

        # Verify redaction marker IS in output
        assert "***REDACTED***" in output, "Redaction marker should be present"

        # Verify non-sensitive values ARE in output
        assert "7687" in output, "NEO4J_PORT should be visible"


def test_no_debug_output_without_debug_flag():
    """Test that no debug output is produced when debug is disabled."""
    os.environ["NEO4J_PORT"] = "7687"
    os.environ["NEO4J_PASSWORD"] = "test-password"  # pragma: allowlist secret

    with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
        # Create manager without debug
        manager = Neo4jContainerManager(debug=False)

        output = mock_stdout.getvalue()

        # Verify no debug output at all
        assert "[DEBUG]" not in output, "No debug output should be present"


def test_start_container_debug_redaction():
    """Test that credentials are redacted in start_neo4j_container debug output."""
    os.environ["NEO4J_PORT"] = "7687"
    os.environ["NEO4J_PASSWORD"] = "secret-password-xyz"  # pragma: allowlist secret

    manager = Neo4jContainerManager(debug=True)

    # Mock docker availability to avoid actually starting containers
    with patch.object(manager, 'is_docker_available', return_value=False):
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            # Attempt to start container (will fail due to mock)
            manager.start_neo4j_container()

            output = mock_stdout.getvalue()

            # If there's any debug output, verify credentials are redacted
            if "[CONTAINER MANAGER DEBUG]" in output:
                assert "secret-password-xyz" not in output, "Password should be redacted"
                assert "***REDACTED***" in output, "Redaction marker should be present"


def test_azure_tenant_secrets_redacted():
    """Test that Azure tenant client secrets are redacted."""
    # Fake test values for verifying redaction (not real secrets)
    os.environ["NEO4J_PORT"] = "7687"
    os.environ["AZURE_TENANT_1_CLIENT_SECRET"] = "tenant1-secret-123"  # pragma: allowlist secret
    os.environ["AZURE_TENANT_2_CLIENT_SECRET"] = "tenant2-secret-456"  # pragma: allowlist secret
    os.environ["AZURE_CLIENT_SECRET"] = "main-azure-secret-789"  # pragma: allowlist secret

    with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
        manager = Neo4jContainerManager(debug=True)

        output = mock_stdout.getvalue()

        # Verify all Azure secrets are redacted
        assert "tenant1-secret-123" not in output, "AZURE_TENANT_1_CLIENT_SECRET should be redacted"
        assert "tenant2-secret-456" not in output, "AZURE_TENANT_2_CLIENT_SECRET should be redacted"
        assert "main-azure-secret-789" not in output, "AZURE_CLIENT_SECRET should be redacted"
        assert "***REDACTED***" in output, "Redaction marker should be present"
