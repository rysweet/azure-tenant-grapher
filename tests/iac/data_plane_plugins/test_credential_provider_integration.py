"""
Integration tests for Credential Provider with real Azure credentials.

These tests require real Azure credentials to be configured.
They can be run with pytest -m integration flag.

Set up test credentials via:
- Environment variables: AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID
- Or Azure CLI: az login
"""

import os
import pytest
from azure.core.exceptions import ClientAuthenticationError

from src.iac.data_plane_plugins.credential_provider import (
    CredentialConfig,
    CredentialProvider,
)


# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture
def has_azure_credentials():
    """Check if Azure credentials are available."""
    # Check for explicit credentials
    has_explicit = all(
        [
            os.getenv("AZURE_CLIENT_ID"),
            os.getenv("AZURE_CLIENT_SECRET"),
            os.getenv("AZURE_TENANT_ID"),
        ]
    )

    # For integration tests, we need explicit credentials
    if not has_explicit:
        pytest.skip("Azure credentials not configured (requires AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID)")

    return True


def test_real_credential_resolution(has_azure_credentials):
    """Test credential resolution with real Azure credentials from environment."""
    config = CredentialConfig(use_environment=True)
    provider = CredentialProvider(config)

    credential = provider.get_credential()

    assert credential is not None
    assert provider.get_credential_source() == "environment"


def test_real_credential_validation(has_azure_credentials):
    """Test that real credentials can be validated."""
    config = CredentialConfig(use_environment=True)
    provider = CredentialProvider(config)

    # This should not raise an exception
    credential = provider.get_credential()

    # Verify we can actually get a token
    token = credential.get_token("https://management.azure.com/.default")
    assert token is not None
    assert token.token is not None
    assert len(token.token) > 0


def test_explicit_credentials_real(has_azure_credentials):
    """Test explicit credential configuration with real values."""
    config = CredentialConfig(
        client_id=os.getenv("AZURE_CLIENT_ID"),
        client_secret=os.getenv("AZURE_CLIENT_SECRET"),
        tenant_id=os.getenv("AZURE_TENANT_ID"),
    )
    provider = CredentialProvider(config)

    credential = provider.get_credential()

    assert credential is not None
    assert provider.get_credential_source() == "explicit"

    # Verify token can be obtained
    token = credential.get_token("https://management.azure.com/.default")
    assert token is not None


def test_invalid_credentials_real():
    """Test that invalid credentials fail validation."""
    config = CredentialConfig(
        client_id="invalid-client-id",
        client_secret="invalid-client-secret",
        tenant_id="invalid-tenant-id",
    )
    provider = CredentialProvider(config)

    # Should raise ClientAuthenticationError
    with pytest.raises(ClientAuthenticationError):
        provider.get_credential()


def test_credential_caching_real(has_azure_credentials):
    """Test that credentials are cached across multiple calls."""
    config = CredentialConfig(use_environment=True)
    provider = CredentialProvider(config)

    # First call
    cred1 = provider.get_credential()
    token1 = cred1.get_token("https://management.azure.com/.default")

    # Second call (should be cached)
    cred2 = provider.get_credential()
    token2 = cred2.get_token("https://management.azure.com/.default")

    # Should be the same credential object
    assert cred1 is cred2

    # Tokens should be valid
    assert token1.token is not None
    assert token2.token is not None


def test_clear_cache_real(has_azure_credentials):
    """Test cache clearing with real credentials."""
    config = CredentialConfig(use_environment=True)
    provider = CredentialProvider(config)

    # Get credential
    cred1 = provider.get_credential()
    source1 = provider.get_credential_source()
    assert source1 == "environment"

    # Clear cache
    provider.clear_cache()
    assert provider.get_credential_source() is None

    # Get credential again (should re-resolve)
    cred2 = provider.get_credential()
    source2 = provider.get_credential_source()
    assert source2 == "environment"

    # Credentials should still work
    token = cred2.get_token("https://management.azure.com/.default")
    assert token is not None


@pytest.mark.skipif(
    not os.getenv("TEST_MULTIPLE_TENANTS"),
    reason="Multiple tenant test requires TEST_MULTIPLE_TENANTS env var",
)
def test_multiple_tenant_support():
    """Test support for multiple tenants (requires special test setup)."""
    # This test requires AZURE_TENANT_1_* and AZURE_TENANT_2_* env vars
    tenant1_config = CredentialConfig(
        client_id=os.getenv("AZURE_TENANT_1_CLIENT_ID"),
        client_secret=os.getenv("AZURE_TENANT_1_CLIENT_SECRET"),
        tenant_id=os.getenv("AZURE_TENANT_1_ID"),
    )
    tenant2_config = CredentialConfig(
        client_id=os.getenv("AZURE_TENANT_2_CLIENT_ID"),
        client_secret=os.getenv("AZURE_TENANT_2_CLIENT_SECRET"),
        tenant_id=os.getenv("AZURE_TENANT_2_ID"),
    )

    provider1 = CredentialProvider(tenant1_config)
    provider2 = CredentialProvider(tenant2_config)

    # Both should resolve successfully
    cred1 = provider1.get_credential()
    cred2 = provider2.get_credential()

    assert cred1 is not None
    assert cred2 is not None

    # Both should get valid tokens
    token1 = cred1.get_token("https://management.azure.com/.default")
    token2 = cred2.get_token("https://management.azure.com/.default")

    assert token1 is not None
    assert token2 is not None

    # Tokens should be different (different tenants)
    assert token1.token != token2.token
