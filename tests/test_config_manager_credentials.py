"""
Tests for Config Manager Credential Helper Functions

Tests backward compatibility and dual-tenant support in config_manager.py
"""

import os
from unittest.mock import patch

import pytest

from src.config_manager import get_source_credentials, get_target_credentials


class TestGetSourceCredentials:
    """Tests for get_source_credentials function."""

    def test_source_credentials_from_dual_tenant_vars(self):
        """Test loading source credentials from dual-tenant env vars."""
        env = {
            "AZURE_SOURCE_TENANT_ID": "source-tenant-id",
            "AZURE_SOURCE_TENANT_CLIENT_ID": "source-client-id",
            "AZURE_SOURCE_TENANT_CLIENT_SECRET": "source-secret",
            "AZURE_SOURCE_TENANT_SUBSCRIPTION_ID": "source-subscription-id",
        }

        with patch.dict(os.environ, env, clear=True):
            creds = get_source_credentials()

            assert creds["tenant_id"] == "source-tenant-id"
            assert creds["client_id"] == "source-client-id"
            assert creds["client_secret"] == "source-secret"
            assert creds["subscription_id"] == "source-subscription-id"

    def test_source_credentials_fallback_to_single_tenant(self):
        """Test fallback to single-tenant env vars when source vars not set."""
        env = {
            "AZURE_TENANT_ID": "single-tenant-id",
            "AZURE_CLIENT_ID": "single-client-id",
            "AZURE_CLIENT_SECRET": "single-secret",
            "AZURE_SUBSCRIPTION_ID": "single-subscription-id",
        }

        with patch.dict(os.environ, env, clear=True):
            creds = get_source_credentials()

            assert creds["tenant_id"] == "single-tenant-id"
            assert creds["client_id"] == "single-client-id"
            assert creds["client_secret"] == "single-secret"
            assert creds["subscription_id"] == "single-subscription-id"

    def test_source_credentials_mixed_fallback(self):
        """Test partial fallback when some source vars set."""
        env = {
            "AZURE_SOURCE_TENANT_ID": "source-tenant-id",
            # No source client ID - should fall back
            "AZURE_CLIENT_ID": "fallback-client-id",
            "AZURE_SOURCE_TENANT_CLIENT_SECRET": "source-secret",
            "AZURE_SUBSCRIPTION_ID": "fallback-subscription-id",
        }

        with patch.dict(os.environ, env, clear=True):
            creds = get_source_credentials()

            assert creds["tenant_id"] == "source-tenant-id"
            assert creds["client_id"] == "fallback-client-id"
            assert creds["client_secret"] == "source-secret"
            assert creds["subscription_id"] == "fallback-subscription-id"

    def test_source_credentials_without_subscription(self):
        """Test source credentials work without subscription ID."""
        env = {
            "AZURE_SOURCE_TENANT_ID": "source-tenant-id",
            "AZURE_SOURCE_TENANT_CLIENT_ID": "source-client-id",
            "AZURE_SOURCE_TENANT_CLIENT_SECRET": "source-secret",
            # No subscription ID
        }

        with patch.dict(os.environ, env, clear=True):
            creds = get_source_credentials()

            assert creds["tenant_id"] == "source-tenant-id"
            assert creds["subscription_id"] == ""  # Empty string, not None

    def test_source_credentials_missing_tenant_id(self):
        """Test error when tenant ID not configured."""
        env = {
            # No tenant ID
            "AZURE_SOURCE_TENANT_CLIENT_ID": "source-client-id",
            "AZURE_SOURCE_TENANT_CLIENT_SECRET": "source-secret",
        }

        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="Source tenant ID not configured"):
                get_source_credentials()

    def test_source_credentials_missing_client_id(self):
        """Test error when client ID not configured."""
        env = {
            "AZURE_SOURCE_TENANT_ID": "source-tenant-id",
            # No client ID
            "AZURE_SOURCE_TENANT_CLIENT_SECRET": "source-secret",
        }

        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="Source client ID not configured"):
                get_source_credentials()

    def test_source_credentials_missing_client_secret(self):
        """Test error when client secret not configured."""
        env = {
            "AZURE_SOURCE_TENANT_ID": "source-tenant-id",
            "AZURE_SOURCE_TENANT_CLIENT_ID": "source-client-id",
            # No client secret
        }

        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="Source client secret not configured"):
                get_source_credentials()


class TestGetTargetCredentials:
    """Tests for get_target_credentials function."""

    def test_target_credentials_from_dual_tenant_vars(self):
        """Test loading target credentials from dual-tenant env vars."""
        env = {
            "AZURE_TARGET_TENANT_ID": "target-tenant-id",
            "AZURE_TARGET_TENANT_CLIENT_ID": "target-client-id",
            "AZURE_TARGET_TENANT_CLIENT_SECRET": "target-secret",
            "AZURE_TARGET_TENANT_SUBSCRIPTION_ID": "target-subscription-id",
        }

        with patch.dict(os.environ, env, clear=True):
            creds = get_target_credentials()

            assert creds["tenant_id"] == "target-tenant-id"
            assert creds["client_id"] == "target-client-id"
            assert creds["client_secret"] == "target-secret"
            assert creds["subscription_id"] == "target-subscription-id"

    def test_target_credentials_fallback_to_single_tenant(self):
        """Test fallback to single-tenant env vars when target vars not set."""
        env = {
            "AZURE_TENANT_ID": "single-tenant-id",
            "AZURE_CLIENT_ID": "single-client-id",
            "AZURE_CLIENT_SECRET": "single-secret",
            "AZURE_SUBSCRIPTION_ID": "single-subscription-id",
        }

        with patch.dict(os.environ, env, clear=True):
            creds = get_target_credentials()

            assert creds["tenant_id"] == "single-tenant-id"
            assert creds["client_id"] == "single-client-id"
            assert creds["client_secret"] == "single-secret"
            assert creds["subscription_id"] == "single-subscription-id"

    def test_target_credentials_mixed_fallback(self):
        """Test partial fallback when some target vars set."""
        env = {
            "AZURE_TARGET_TENANT_ID": "target-tenant-id",
            "AZURE_TARGET_TENANT_CLIENT_ID": "target-client-id",
            # No target secret - should fall back
            "AZURE_CLIENT_SECRET": "fallback-secret",
            "AZURE_TARGET_TENANT_SUBSCRIPTION_ID": "target-subscription-id",
        }

        with patch.dict(os.environ, env, clear=True):
            creds = get_target_credentials()

            assert creds["tenant_id"] == "target-tenant-id"
            assert creds["client_id"] == "target-client-id"
            assert creds["client_secret"] == "fallback-secret"
            assert creds["subscription_id"] == "target-subscription-id"

    def test_target_credentials_without_subscription(self):
        """Test target credentials work without subscription ID."""
        env = {
            "AZURE_TARGET_TENANT_ID": "target-tenant-id",
            "AZURE_TARGET_TENANT_CLIENT_ID": "target-client-id",
            "AZURE_TARGET_TENANT_CLIENT_SECRET": "target-secret",
            # No subscription ID
        }

        with patch.dict(os.environ, env, clear=True):
            creds = get_target_credentials()

            assert creds["tenant_id"] == "target-tenant-id"
            assert creds["subscription_id"] == ""  # Empty string, not None

    def test_target_credentials_missing_tenant_id(self):
        """Test error when tenant ID not configured."""
        env = {
            # No tenant ID
            "AZURE_TARGET_TENANT_CLIENT_ID": "target-client-id",
            "AZURE_TARGET_TENANT_CLIENT_SECRET": "target-secret",
        }

        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="Target tenant ID not configured"):
                get_target_credentials()

    def test_target_credentials_missing_client_id(self):
        """Test error when client ID not configured."""
        env = {
            "AZURE_TARGET_TENANT_ID": "target-tenant-id",
            # No client ID
            "AZURE_TARGET_TENANT_CLIENT_SECRET": "target-secret",
        }

        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="Target client ID not configured"):
                get_target_credentials()

    def test_target_credentials_missing_client_secret(self):
        """Test error when client secret not configured."""
        env = {
            "AZURE_TARGET_TENANT_ID": "target-tenant-id",
            "AZURE_TARGET_TENANT_CLIENT_ID": "target-client-id",
            # No client secret
        }

        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="Target client secret not configured"):
                get_target_credentials()


class TestBackwardCompatibility:
    """Tests for backward compatibility with existing setups."""

    def test_both_functions_work_with_single_tenant_env(self):
        """Test both functions work with legacy single-tenant environment."""
        env = {
            "AZURE_TENANT_ID": "legacy-tenant-id",
            "AZURE_CLIENT_ID": "legacy-client-id",
            "AZURE_CLIENT_SECRET": "legacy-secret",
            "AZURE_SUBSCRIPTION_ID": "legacy-subscription-id",
        }

        with patch.dict(os.environ, env, clear=True):
            source_creds = get_source_credentials()
            target_creds = get_target_credentials()

            # Both should return same credentials
            assert source_creds == target_creds
            assert source_creds["tenant_id"] == "legacy-tenant-id"
            assert source_creds["client_id"] == "legacy-client-id"
            assert source_creds["client_secret"] == "legacy-secret"
            assert source_creds["subscription_id"] == "legacy-subscription-id"

    def test_dual_tenant_takes_precedence(self):
        """Test dual-tenant vars take precedence over single-tenant vars."""
        env = {
            # Single-tenant vars (should be ignored)
            "AZURE_TENANT_ID": "single-tenant-id",
            "AZURE_CLIENT_ID": "single-client-id",
            "AZURE_CLIENT_SECRET": "single-secret",
            # Dual-tenant source vars (should be used)
            "AZURE_SOURCE_TENANT_ID": "source-tenant-id",
            "AZURE_SOURCE_TENANT_CLIENT_ID": "source-client-id",
            "AZURE_SOURCE_TENANT_CLIENT_SECRET": "source-secret",
            # Dual-tenant target vars (should be used)
            "AZURE_TARGET_TENANT_ID": "target-tenant-id",
            "AZURE_TARGET_TENANT_CLIENT_ID": "target-client-id",
            "AZURE_TARGET_TENANT_CLIENT_SECRET": "target-secret",
        }

        with patch.dict(os.environ, env, clear=True):
            source_creds = get_source_credentials()
            target_creds = get_target_credentials()

            # Source should use source vars
            assert source_creds["tenant_id"] == "source-tenant-id"
            assert source_creds["client_id"] == "source-client-id"
            assert source_creds["client_secret"] == "source-secret"

            # Target should use target vars
            assert target_creds["tenant_id"] == "target-tenant-id"
            assert target_creds["client_id"] == "target-client-id"
            assert target_creds["client_secret"] == "target-secret"
