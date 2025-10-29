"""
Unit tests for Credential Provider.

Tests all 4 priority levels with mocked credentials:
1. Explicit credentials (CLI flags)
2. Environment variables
3. DefaultAzureCredential
4. Interactive login
"""

import os
import threading
import pytest
from unittest.mock import Mock, patch, MagicMock
from azure.core.credentials import AccessToken
from azure.core.exceptions import ClientAuthenticationError

from src.iac.data_plane_plugins.credential_provider import (
    CredentialConfig,
    CredentialProvider,
)


# ============ Fixtures ============


@pytest.fixture
def mock_token():
    """Mock Azure access token."""
    return AccessToken(token="mock_token_12345", expires_on=9999999999)


@pytest.fixture
def mock_credential(mock_token):
    """Mock Azure credential that returns a valid token."""
    credential = Mock()
    credential.get_token.return_value = mock_token
    return credential


@pytest.fixture
def env_vars_backup():
    """Backup and restore environment variables."""
    backup = {
        "AZURE_CLIENT_ID": os.getenv("AZURE_CLIENT_ID"),
        "AZURE_CLIENT_SECRET": os.getenv("AZURE_CLIENT_SECRET"),
        "AZURE_TENANT_ID": os.getenv("AZURE_TENANT_ID"),
    }

    yield backup

    # Restore original values
    for key, value in backup.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@pytest.fixture
def clean_env(env_vars_backup):
    """Clean environment variables for testing."""
    os.environ.pop("AZURE_CLIENT_ID", None)
    os.environ.pop("AZURE_CLIENT_SECRET", None)
    os.environ.pop("AZURE_TENANT_ID", None)
    yield


# ============ CredentialConfig Tests ============


def test_credential_config_defaults():
    """Test CredentialConfig default values."""
    config = CredentialConfig()

    assert config.client_id is None
    assert config.client_secret is None
    assert config.tenant_id is None
    assert config.allow_interactive is False
    assert config.use_environment is True
    assert config.connection_strings == {}


def test_credential_config_with_values():
    """Test CredentialConfig with explicit values."""
    config = CredentialConfig(
        client_id="test-client-id",
        client_secret="test-client-secret",
        tenant_id="test-tenant-id",
        allow_interactive=True,
        use_environment=False,
        connection_strings={"resource1": "conn_str_1"},
    )

    assert config.client_id == "test-client-id"
    assert config.client_secret == "test-client-secret"
    assert config.tenant_id == "test-tenant-id"
    assert config.allow_interactive is True
    assert config.use_environment is False
    assert config.connection_strings == {"resource1": "conn_str_1"}


# ============ Priority Level 1: Explicit Credentials Tests ============


@patch("src.iac.data_plane_plugins.credential_provider.ClientSecretCredential")
def test_priority_level_1_explicit_credentials(mock_client_secret_cred, mock_credential):
    """Test priority level 1: explicit credentials via config."""
    mock_client_secret_cred.return_value = mock_credential

    config = CredentialConfig(
        client_id="explicit-client-id",
        client_secret="explicit-client-secret",
        tenant_id="explicit-tenant-id",
    )

    provider = CredentialProvider(config)
    credential = provider.get_credential()

    # Verify ClientSecretCredential was created with correct values
    mock_client_secret_cred.assert_called_once_with(
        tenant_id="explicit-tenant-id",
        client_id="explicit-client-id",
        client_secret="explicit-client-secret",
    )

    # Verify correct credential returned
    assert credential == mock_credential

    # Verify source is tracked
    assert provider.get_credential_source() == "explicit"


@patch("src.iac.data_plane_plugins.credential_provider.ClientSecretCredential")
def test_explicit_credentials_override_env(
    mock_client_secret_cred, mock_credential, env_vars_backup
):
    """Test explicit credentials take priority over environment variables."""
    # Set environment variables
    os.environ["AZURE_CLIENT_ID"] = "env-client-id"
    os.environ["AZURE_CLIENT_SECRET"] = "env-client-secret"
    os.environ["AZURE_TENANT_ID"] = "env-tenant-id"

    mock_client_secret_cred.return_value = mock_credential

    config = CredentialConfig(
        client_id="explicit-client-id",
        client_secret="explicit-client-secret",
        tenant_id="explicit-tenant-id",
    )

    provider = CredentialProvider(config)
    provider.get_credential()

    # Verify explicit credentials were used, not environment
    mock_client_secret_cred.assert_called_once_with(
        tenant_id="explicit-tenant-id",
        client_id="explicit-client-id",
        client_secret="explicit-client-secret",
    )
    assert provider.get_credential_source() == "explicit"


# ============ Priority Level 2: Environment Variables Tests ============


@patch("src.iac.data_plane_plugins.credential_provider.ClientSecretCredential")
def test_priority_level_2_environment_variables(
    mock_client_secret_cred, mock_credential, clean_env
):
    """Test priority level 2: environment variables."""
    # Set environment variables
    os.environ["AZURE_CLIENT_ID"] = "env-client-id"
    os.environ["AZURE_CLIENT_SECRET"] = "env-client-secret"
    os.environ["AZURE_TENANT_ID"] = "env-tenant-id"

    mock_client_secret_cred.return_value = mock_credential

    config = CredentialConfig(use_environment=True)
    provider = CredentialProvider(config)
    credential = provider.get_credential()

    # Verify ClientSecretCredential was created with env values
    mock_client_secret_cred.assert_called_once_with(
        tenant_id="env-tenant-id",
        client_id="env-client-id",
        client_secret="env-client-secret",
    )

    assert credential == mock_credential
    assert provider.get_credential_source() == "environment"


@patch("src.iac.data_plane_plugins.credential_provider.DefaultAzureCredential")
def test_environment_disabled_skips_to_default(
    mock_default_cred, mock_credential, clean_env
):
    """Test that disabling environment skips to DefaultAzureCredential."""
    # Set environment variables (should be ignored)
    os.environ["AZURE_CLIENT_ID"] = "env-client-id"
    os.environ["AZURE_CLIENT_SECRET"] = "env-client-secret"
    os.environ["AZURE_TENANT_ID"] = "env-tenant-id"

    mock_default_cred.return_value = mock_credential

    config = CredentialConfig(use_environment=False)
    provider = CredentialProvider(config)
    provider.get_credential()

    # Verify DefaultAzureCredential was used
    mock_default_cred.assert_called_once()
    assert provider.get_credential_source() == "default"


# ============ Priority Level 3: DefaultAzureCredential Tests ============


@patch("src.iac.data_plane_plugins.credential_provider.DefaultAzureCredential")
def test_priority_level_3_default_credential(mock_default_cred, mock_credential, clean_env):
    """Test priority level 3: DefaultAzureCredential."""
    mock_default_cred.return_value = mock_credential

    config = CredentialConfig()
    provider = CredentialProvider(config)
    credential = provider.get_credential()

    # Verify DefaultAzureCredential was used
    mock_default_cred.assert_called_once()
    assert credential == mock_credential
    assert provider.get_credential_source() == "default"


# ============ Priority Level 4: Interactive Login Tests ============


@patch("src.iac.data_plane_plugins.credential_provider.InteractiveBrowserCredential")
@patch("src.iac.data_plane_plugins.credential_provider.DefaultAzureCredential")
def test_priority_level_4_interactive(
    mock_default_cred, mock_interactive_cred, mock_credential, clean_env
):
    """Test priority level 4: interactive login."""
    # Make DefaultAzureCredential fail validation
    failed_credential = Mock()
    failed_credential.get_token.side_effect = ClientAuthenticationError("Auth failed")
    mock_default_cred.return_value = failed_credential

    # Make InteractiveBrowserCredential succeed
    mock_interactive_cred.return_value = mock_credential

    config = CredentialConfig(allow_interactive=True)
    provider = CredentialProvider(config)
    credential = provider.get_credential()

    # Verify interactive credential was used
    mock_interactive_cred.assert_called_once()
    assert credential == mock_credential
    assert provider.get_credential_source() == "interactive"


@patch("src.iac.data_plane_plugins.credential_provider.DefaultAzureCredential")
def test_interactive_not_allowed_fails(mock_default_cred, clean_env):
    """Test that credential resolution fails when interactive is not allowed."""
    # Make DefaultAzureCredential fail
    failed_credential = Mock()
    failed_credential.get_token.side_effect = ClientAuthenticationError("Auth failed")
    mock_default_cred.return_value = failed_credential

    config = CredentialConfig(allow_interactive=False)
    provider = CredentialProvider(config)

    # Should raise ValueError with helpful message
    with pytest.raises(ValueError) as exc_info:
        provider.get_credential()

    assert "Could not resolve Azure credentials" in str(exc_info.value)
    assert "CLI flags" in str(exc_info.value)
    assert "Environment variables" in str(exc_info.value)


# ============ Credential Caching Tests ============


@patch("src.iac.data_plane_plugins.credential_provider.ClientSecretCredential")
def test_credential_caching(mock_client_secret_cred, mock_credential):
    """Test that credentials are cached after first resolution."""
    mock_client_secret_cred.return_value = mock_credential

    config = CredentialConfig(
        client_id="test-id", client_secret="test-secret", tenant_id="test-tenant"
    )
    provider = CredentialProvider(config)

    # First call should create credential
    cred1 = provider.get_credential()
    assert mock_client_secret_cred.call_count == 1

    # Second call should use cached credential
    cred2 = provider.get_credential()
    assert mock_client_secret_cred.call_count == 1  # Still 1, not 2

    # Both should be the same object
    assert cred1 is cred2


@patch("src.iac.data_plane_plugins.credential_provider.ClientSecretCredential")
def test_clear_cache(mock_client_secret_cred, mock_credential):
    """Test that clear_cache() forces re-resolution."""
    mock_client_secret_cred.return_value = mock_credential

    config = CredentialConfig(
        client_id="test-id", client_secret="test-secret", tenant_id="test-tenant"
    )
    provider = CredentialProvider(config)

    # First call
    provider.get_credential()
    assert mock_client_secret_cred.call_count == 1

    # Clear cache
    provider.clear_cache()
    assert provider.get_credential_source() is None

    # Next call should re-resolve
    provider.get_credential()
    assert mock_client_secret_cred.call_count == 2


# ============ Thread Safety Tests ============


@patch("src.iac.data_plane_plugins.credential_provider.ClientSecretCredential")
def test_thread_safety(mock_client_secret_cred, mock_credential):
    """Test that credential provider is thread-safe."""
    mock_client_secret_cred.return_value = mock_credential

    config = CredentialConfig(
        client_id="test-id", client_secret="test-secret", tenant_id="test-tenant"
    )
    provider = CredentialProvider(config)

    credentials = []
    errors = []

    def get_credential_in_thread():
        """Thread worker function."""
        try:
            cred = provider.get_credential()
            credentials.append(cred)
        except Exception as e:
            errors.append(e)

    # Create 10 threads that try to get credentials simultaneously
    threads = [threading.Thread(target=get_credential_in_thread) for _ in range(10)]

    # Start all threads
    for thread in threads:
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    # Should have no errors
    assert len(errors) == 0

    # All threads should get the same cached credential
    assert len(credentials) == 10
    assert all(cred is credentials[0] for cred in credentials)

    # Should only create credential once (cached for all threads)
    assert mock_client_secret_cred.call_count == 1


# ============ Validation Tests ============


@patch("src.iac.data_plane_plugins.credential_provider.ClientSecretCredential")
def test_validation_success(mock_client_secret_cred, mock_credential):
    """Test successful credential validation."""
    mock_client_secret_cred.return_value = mock_credential

    config = CredentialConfig(
        client_id="test-id", client_secret="test-secret", tenant_id="test-tenant"
    )
    provider = CredentialProvider(config)
    credential = provider.get_credential()

    # Should succeed without raising
    assert credential is not None

    # Verify get_token was called for validation
    mock_credential.get_token.assert_called_with("https://management.azure.com/.default")


@patch("src.iac.data_plane_plugins.credential_provider.DefaultAzureCredential")
@patch("src.iac.data_plane_plugins.credential_provider.ClientSecretCredential")
def test_validation_failure(mock_client_secret_cred, mock_default_cred, clean_env):
    """Test credential validation failure falls through all levels."""
    # Create credential that fails validation
    failed_credential = Mock()
    failed_credential.get_token.side_effect = ClientAuthenticationError("Invalid credentials")
    mock_client_secret_cred.return_value = failed_credential
    mock_default_cred.return_value = failed_credential

    config = CredentialConfig(
        client_id="bad-id",
        client_secret="bad-secret",
        tenant_id="bad-tenant",
        allow_interactive=False  # Don't allow interactive to test failure
    )
    provider = CredentialProvider(config)

    # Should raise ValueError (no valid credentials found)
    with pytest.raises(ValueError) as exc_info:
        provider.get_credential()

    assert "Could not resolve Azure credentials" in str(exc_info.value)


@patch("src.iac.data_plane_plugins.credential_provider.DefaultAzureCredential")
@patch("src.iac.data_plane_plugins.credential_provider.ClientSecretCredential")
def test_validation_empty_token(mock_client_secret_cred, mock_default_cred, clean_env):
    """Test validation with empty token falls through all levels."""
    # Create credential that returns empty token
    failed_credential = Mock()
    failed_credential.get_token.return_value = AccessToken(token="", expires_on=0)
    mock_client_secret_cred.return_value = failed_credential
    mock_default_cred.return_value = failed_credential

    config = CredentialConfig(
        client_id="test-id",
        client_secret="test-secret",
        tenant_id="test-tenant",
        allow_interactive=False  # Don't allow interactive to test failure
    )
    provider = CredentialProvider(config)

    # Should raise ValueError (no valid credentials found)
    with pytest.raises(ValueError) as exc_info:
        provider.get_credential()

    assert "Could not resolve Azure credentials" in str(exc_info.value)


# ============ Connection String Tests ============


def test_get_connection_string():
    """Test getting resource-specific connection strings."""
    config = CredentialConfig(
        connection_strings={
            "resource1": "connection_string_1",
            "resource2": "connection_string_2",
        }
    )
    provider = CredentialProvider(config)

    assert provider.get_connection_string("resource1") == "connection_string_1"
    assert provider.get_connection_string("resource2") == "connection_string_2"
    assert provider.get_connection_string("resource3") is None


def test_get_connection_string_empty():
    """Test connection string with no configured strings."""
    config = CredentialConfig()
    provider = CredentialProvider(config)

    assert provider.get_connection_string("any_resource") is None


# ============ Error Message Tests ============


def test_error_message_no_credentials(clean_env):
    """Test helpful error message when no credentials available."""
    # Patch DefaultAzureCredential to fail
    with patch(
        "src.iac.data_plane_plugins.credential_provider.DefaultAzureCredential"
    ) as mock_default:
        failed_cred = Mock()
        failed_cred.get_token.side_effect = ClientAuthenticationError("No auth")
        mock_default.return_value = failed_cred

        config = CredentialConfig(allow_interactive=False)
        provider = CredentialProvider(config)

        with pytest.raises(ValueError) as exc_info:
            provider.get_credential()

        error_msg = str(exc_info.value)
        # Check that error message includes all 4 options
        assert "CLI flags" in error_msg
        assert "Environment variables" in error_msg
        assert "Azure CLI" in error_msg
        assert "Interactive login" in error_msg


# ============ Edge Cases ============


def test_provider_with_none_config():
    """Test provider with None config uses defaults."""
    provider = CredentialProvider(None)

    assert provider.config is not None
    assert isinstance(provider.config, CredentialConfig)
    assert provider.config.use_environment is True
    assert provider.config.allow_interactive is False


@patch("src.iac.data_plane_plugins.credential_provider.ClientSecretCredential")
def test_partial_explicit_credentials_falls_through(mock_client_secret_cred, mock_credential, clean_env):
    """Test that partial explicit credentials fall through to next level."""
    mock_client_secret_cred.return_value = mock_credential

    # Only client_id set, missing client_secret and tenant_id
    config = CredentialConfig(client_id="test-id")

    with patch(
        "src.iac.data_plane_plugins.credential_provider.DefaultAzureCredential"
    ) as mock_default:
        mock_default.return_value = mock_credential
        provider = CredentialProvider(config)
        credential = provider.get_credential()

        # Should fall through to DefaultAzureCredential (partial creds don't pass _has_explicit_credentials)
        mock_default.assert_called_once()
        assert provider.get_credential_source() == "default"
        assert credential == mock_credential
