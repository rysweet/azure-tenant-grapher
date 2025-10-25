"""
Tests for Dual Tenant Configuration Module

Tests the dual tenant configuration loading, validation, and backward compatibility.
"""

import os
from unittest.mock import patch

import pytest

from src.dual_tenant_config import (
    DualTenantConfig,
    TenantCredentials,
    create_dual_tenant_config_from_env,
)


class TestTenantCredentials:
    """Tests for TenantCredentials dataclass."""

    def test_valid_credentials(self):
        """Test creating valid tenant credentials."""
        creds = TenantCredentials(
            tenant_id="test-tenant-id",
            client_id="test-client-id",
            client_secret="test-secret",
            subscription_id="test-subscription-id",
            role="Reader",
        )

        assert creds.tenant_id == "test-tenant-id"
        assert creds.client_id == "test-client-id"
        assert creds.client_secret == "test-secret"
        assert creds.subscription_id == "test-subscription-id"
        assert creds.role == "Reader"

    def test_credentials_without_subscription(self):
        """Test credentials without subscription ID."""
        creds = TenantCredentials(
            tenant_id="test-tenant-id",
            client_id="test-client-id",
            client_secret="test-secret",
        )

        assert creds.subscription_id is None
        assert creds.role == "Reader"  # Default role

    def test_missing_tenant_id(self):
        """Test validation fails without tenant ID."""
        with pytest.raises(ValueError, match="Tenant ID is required"):
            TenantCredentials(
                tenant_id="",
                client_id="test-client-id",
                client_secret="test-secret",
            )

    def test_missing_client_id(self):
        """Test validation fails without client ID."""
        with pytest.raises(ValueError, match="Client ID is required"):
            TenantCredentials(
                tenant_id="test-tenant-id",
                client_id="",
                client_secret="test-secret",
            )

    def test_missing_client_secret(self):
        """Test validation fails without client secret."""
        with pytest.raises(ValueError, match="Client secret is required"):
            TenantCredentials(
                tenant_id="test-tenant-id",
                client_id="test-client-id",
                client_secret="",
            )

    def test_mask_secret(self):
        """Test secret masking for logging."""
        creds = TenantCredentials(
            tenant_id="test-tenant-id",
            client_id="test-client-id",
            client_secret="super-secret",
            role="Reader",
        )

        masked = creds.mask_secret()
        assert "super-secret" not in masked
        assert "test-tenant-id" in masked
        assert "test-client-id" in masked
        assert "Reader" in masked


class TestDualTenantConfig:
    """Tests for DualTenantConfig dataclass."""

    def test_single_tenant_mode(self):
        """Test single tenant mode configuration."""
        source_creds = TenantCredentials(
            tenant_id="source-tenant",
            client_id="source-client",
            client_secret="source-secret",
        )

        config = DualTenantConfig(
            source_tenant=source_creds,
            target_tenant=None,
            operation_mode="single",
        )

        assert not config.is_dual_tenant_mode()
        assert config.operation_mode == "single"

    def test_dual_tenant_mode(self):
        """Test dual tenant mode configuration."""
        source_creds = TenantCredentials(
            tenant_id="source-tenant",
            client_id="source-client",
            client_secret="source-secret",
            role="Reader",
        )

        target_creds = TenantCredentials(
            tenant_id="target-tenant",
            client_id="target-client",
            client_secret="target-secret",
            role="Contributor",
        )

        config = DualTenantConfig(
            source_tenant=source_creds,
            target_tenant=target_creds,
            operation_mode="dual",
            auto_switch=True,
        )

        assert config.is_dual_tenant_mode()
        assert config.operation_mode == "dual"
        assert config.auto_switch is True

    def test_validate_dual_mode_success(self):
        """Test validation passes for valid dual mode config."""
        source_creds = TenantCredentials(
            tenant_id="source-tenant",
            client_id="source-client",
            client_secret="source-secret",
        )

        target_creds = TenantCredentials(
            tenant_id="target-tenant",
            client_id="target-client",
            client_secret="target-secret",
        )

        config = DualTenantConfig(
            source_tenant=source_creds,
            target_tenant=target_creds,
            operation_mode="dual",
        )

        # Should not raise
        config.validate()

    def test_validate_dual_mode_missing_source(self):
        """Test validation fails for dual mode without source tenant."""
        target_creds = TenantCredentials(
            tenant_id="target-tenant",
            client_id="target-client",
            client_secret="target-secret",
        )

        config = DualTenantConfig(
            source_tenant=None, target_tenant=target_creds, operation_mode="dual"
        )

        with pytest.raises(
            ValueError, match="Source tenant credentials required when dual-tenant"
        ):
            config.validate()

    def test_validate_dual_mode_missing_target(self):
        """Test validation fails for dual mode without target tenant."""
        source_creds = TenantCredentials(
            tenant_id="source-tenant",
            client_id="source-client",
            client_secret="source-secret",
        )

        config = DualTenantConfig(
            source_tenant=source_creds, target_tenant=None, operation_mode="dual"
        )

        with pytest.raises(
            ValueError, match="Target tenant credentials required when dual-tenant"
        ):
            config.validate()

    def test_validate_invalid_mode(self):
        """Test validation fails for invalid operation mode."""
        config = DualTenantConfig(operation_mode="invalid")  # type: ignore

        with pytest.raises(ValueError, match="Invalid operation mode"):
            config.validate()


class TestCreateDualTenantConfigFromEnv:
    """Tests for create_dual_tenant_config_from_env factory function."""

    def test_dual_mode_from_env(self):
        """Test creating dual mode config from environment variables."""
        env = {
            "AZTG_DUAL_TENANT_MODE": "true",
            "AZURE_SOURCE_TENANT_ID": "source-tenant-id",
            "AZURE_SOURCE_TENANT_CLIENT_ID": "source-client-id",
            "AZURE_SOURCE_TENANT_CLIENT_SECRET": "source-secret",
            "AZURE_SOURCE_TENANT_SUBSCRIPTION_ID": "source-subscription-id",
            "AZURE_TARGET_TENANT_ID": "target-tenant-id",
            "AZURE_TARGET_TENANT_CLIENT_ID": "target-client-id",
            "AZURE_TARGET_TENANT_CLIENT_SECRET": "target-secret",
            "AZURE_TARGET_TENANT_SUBSCRIPTION_ID": "target-subscription-id",
        }

        with patch.dict(os.environ, env, clear=True):
            config = create_dual_tenant_config_from_env()

            assert config.is_dual_tenant_mode()
            assert config.operation_mode == "dual"
            assert config.auto_switch is True

            assert config.source_tenant is not None
            assert config.source_tenant.tenant_id == "source-tenant-id"
            assert config.source_tenant.client_id == "source-client-id"
            assert config.source_tenant.subscription_id == "source-subscription-id"
            assert config.source_tenant.role == "Reader"

            assert config.target_tenant is not None
            assert config.target_tenant.tenant_id == "target-tenant-id"
            assert config.target_tenant.client_id == "target-client-id"
            assert config.target_tenant.subscription_id == "target-subscription-id"
            assert config.target_tenant.role == "Contributor"

    def test_dual_mode_without_auto_switch(self):
        """Test dual mode with auto-switch disabled."""
        env = {
            "AZTG_DUAL_TENANT_MODE": "true",
            "AZTG_AUTO_SWITCH": "false",
            "AZURE_SOURCE_TENANT_ID": "source-tenant-id",
            "AZURE_SOURCE_TENANT_CLIENT_ID": "source-client-id",
            "AZURE_SOURCE_TENANT_CLIENT_SECRET": "source-secret",
            "AZURE_TARGET_TENANT_ID": "target-tenant-id",
            "AZURE_TARGET_TENANT_CLIENT_ID": "target-client-id",
            "AZURE_TARGET_TENANT_CLIENT_SECRET": "target-secret",
        }

        with patch.dict(os.environ, env, clear=True):
            config = create_dual_tenant_config_from_env()

            assert config.is_dual_tenant_mode()
            assert config.auto_switch is False

    def test_dual_mode_incomplete_credentials(self):
        """Test dual mode fails with incomplete credentials."""
        env = {
            "AZTG_DUAL_TENANT_MODE": "true",
            "AZURE_SOURCE_TENANT_ID": "source-tenant-id",
            "AZURE_SOURCE_TENANT_CLIENT_ID": "source-client-id",
            # Missing source secret
            "AZURE_TARGET_TENANT_ID": "target-tenant-id",
            "AZURE_TARGET_TENANT_CLIENT_ID": "target-client-id",
            "AZURE_TARGET_TENANT_CLIENT_SECRET": "target-secret",
        }

        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="credentials are incomplete"):
                create_dual_tenant_config_from_env()

    def test_single_mode_from_env(self):
        """Test creating single mode config from standard env variables."""
        env = {
            "AZURE_TENANT_ID": "single-tenant-id",
            "AZURE_CLIENT_ID": "single-client-id",
            "AZURE_CLIENT_SECRET": "single-secret",
            "AZURE_SUBSCRIPTION_ID": "single-subscription-id",
        }

        with patch.dict(os.environ, env, clear=True):
            config = create_dual_tenant_config_from_env()

            assert not config.is_dual_tenant_mode()
            assert config.operation_mode == "single"
            assert config.auto_switch is False

            assert config.source_tenant is not None
            assert config.source_tenant.tenant_id == "single-tenant-id"
            assert config.source_tenant.client_id == "single-client-id"
            assert config.source_tenant.subscription_id == "single-subscription-id"

            assert config.target_tenant is None

    def test_no_credentials(self):
        """Test behavior when no credentials are configured."""
        with patch.dict(os.environ, {}, clear=True):
            config = create_dual_tenant_config_from_env()

            assert not config.is_dual_tenant_mode()
            assert config.operation_mode == "single"
            assert config.source_tenant is None
            assert config.target_tenant is None

    def test_backward_compatibility(self):
        """Test backward compatibility with existing single-tenant setups."""
        # Existing setup with only AZURE_TENANT_ID, etc.
        env = {
            "AZURE_TENANT_ID": "legacy-tenant-id",
            "AZURE_CLIENT_ID": "legacy-client-id",
            "AZURE_CLIENT_SECRET": "legacy-secret",
        }

        with patch.dict(os.environ, env, clear=True):
            config = create_dual_tenant_config_from_env()

            # Should work in single-tenant mode
            assert not config.is_dual_tenant_mode()
            assert config.source_tenant is not None
            assert config.source_tenant.tenant_id == "legacy-tenant-id"

    def test_dual_mode_without_subscription_ids(self):
        """Test dual mode works without subscription IDs."""
        env = {
            "AZTG_DUAL_TENANT_MODE": "true",
            "AZURE_SOURCE_TENANT_ID": "source-tenant-id",
            "AZURE_SOURCE_TENANT_CLIENT_ID": "source-client-id",
            "AZURE_SOURCE_TENANT_CLIENT_SECRET": "source-secret",
            "AZURE_TARGET_TENANT_ID": "target-tenant-id",
            "AZURE_TARGET_TENANT_CLIENT_ID": "target-client-id",
            "AZURE_TARGET_TENANT_CLIENT_SECRET": "target-secret",
            # No subscription IDs
        }

        with patch.dict(os.environ, env, clear=True):
            config = create_dual_tenant_config_from_env()

            assert config.is_dual_tenant_mode()
            assert config.source_tenant is not None
            assert config.source_tenant.subscription_id is None
            assert config.target_tenant is not None
            assert config.target_tenant.subscription_id is None
