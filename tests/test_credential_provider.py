"""
Tests for Credential Provider Module

Tests the credential provider's operation-based credential selection,
caching, and logging behavior.
"""

from unittest.mock import Mock, patch

import pytest

from src.credential_provider import OperationType, TenantCredentialProvider
from src.dual_tenant_config import DualTenantConfig, TenantCredentials


class TestOperationType:
    """Tests for OperationType enum."""

    def test_operation_types(self):
        """Test all operation types are defined."""
        assert OperationType.DISCOVERY.value == "discovery"
        assert OperationType.DEPLOYMENT.value == "deployment"
        assert OperationType.VALIDATION.value == "validation"


class TestTenantCredentialProvider:
    """Tests for TenantCredentialProvider class."""

    @pytest.fixture
    def single_tenant_config(self):
        """Fixture for single-tenant configuration."""
        source_creds = TenantCredentials(
            tenant_id="single-tenant-id",
            client_id="single-client-id",
            client_secret="single-secret",
            subscription_id="single-subscription-id",
            role="Reader",
        )

        return DualTenantConfig(
            source_tenant=source_creds,
            target_tenant=None,
            operation_mode="single",
            auto_switch=False,
        )

    @pytest.fixture
    def dual_tenant_config(self):
        """Fixture for dual-tenant configuration."""
        source_creds = TenantCredentials(
            tenant_id="source-tenant-id",
            client_id="source-client-id",
            client_secret="source-secret",
            subscription_id="source-subscription-id",
            role="Reader",
        )

        target_creds = TenantCredentials(
            tenant_id="target-tenant-id",
            client_id="target-client-id",
            client_secret="target-secret",
            subscription_id="target-subscription-id",
            role="Contributor",
        )

        return DualTenantConfig(
            source_tenant=source_creds,
            target_tenant=target_creds,
            operation_mode="dual",
            auto_switch=True,
        )

    def test_init_validates_config(self, single_tenant_config):
        """Test provider validates config on initialization."""
        provider = TenantCredentialProvider(single_tenant_config)

        assert provider.config == single_tenant_config
        assert provider._credential_cache == {}
        assert provider._current_tenant_id is None

    def test_init_invalid_config(self):
        """Test provider rejects invalid config."""
        invalid_config = DualTenantConfig(
            source_tenant=None, target_tenant=None, operation_mode="dual"
        )

        with pytest.raises(ValueError):
            TenantCredentialProvider(invalid_config)

    @patch("src.credential_provider.ClientSecretCredential")
    def test_single_tenant_discovery(
        self, mock_credential_class, single_tenant_config
    ):
        """Test single-tenant mode uses same credential for discovery."""
        mock_credential = Mock()
        mock_credential_class.return_value = mock_credential

        provider = TenantCredentialProvider(single_tenant_config)
        credential, tenant_id = provider.get_credential(OperationType.DISCOVERY)

        assert credential == mock_credential
        assert tenant_id == "single-tenant-id"

        # Verify credential was created correctly
        mock_credential_class.assert_called_once_with(
            tenant_id="single-tenant-id",
            client_id="single-client-id",
            client_secret="single-secret",
        )

    @patch("src.credential_provider.ClientSecretCredential")
    def test_single_tenant_deployment(
        self, mock_credential_class, single_tenant_config
    ):
        """Test single-tenant mode uses same credential for deployment."""
        mock_credential = Mock()
        mock_credential_class.return_value = mock_credential

        provider = TenantCredentialProvider(single_tenant_config)
        credential, tenant_id = provider.get_credential(OperationType.DEPLOYMENT)

        assert credential == mock_credential
        assert tenant_id == "single-tenant-id"

    @patch("src.credential_provider.ClientSecretCredential")
    def test_dual_tenant_discovery(self, mock_credential_class, dual_tenant_config):
        """Test dual-tenant mode uses source credential for discovery."""
        mock_credential = Mock()
        mock_credential_class.return_value = mock_credential

        provider = TenantCredentialProvider(dual_tenant_config)
        credential, tenant_id = provider.get_credential(OperationType.DISCOVERY)

        assert credential == mock_credential
        assert tenant_id == "source-tenant-id"

        # Verify source credential was created
        mock_credential_class.assert_called_once_with(
            tenant_id="source-tenant-id",
            client_id="source-client-id",
            client_secret="source-secret",
        )

    @patch("src.credential_provider.ClientSecretCredential")
    def test_dual_tenant_deployment(self, mock_credential_class, dual_tenant_config):
        """Test dual-tenant mode uses target credential for deployment."""
        mock_credential = Mock()
        mock_credential_class.return_value = mock_credential

        provider = TenantCredentialProvider(dual_tenant_config)
        credential, tenant_id = provider.get_credential(OperationType.DEPLOYMENT)

        assert credential == mock_credential
        assert tenant_id == "target-tenant-id"

        # Verify target credential was created
        mock_credential_class.assert_called_once_with(
            tenant_id="target-tenant-id",
            client_id="target-client-id",
            client_secret="target-secret",
        )

    @patch("src.credential_provider.ClientSecretCredential")
    def test_dual_tenant_validation(self, mock_credential_class, dual_tenant_config):
        """Test dual-tenant mode uses source credential for validation."""
        mock_credential = Mock()
        mock_credential_class.return_value = mock_credential

        provider = TenantCredentialProvider(dual_tenant_config)
        credential, tenant_id = provider.get_credential(OperationType.VALIDATION)

        assert credential == mock_credential
        assert tenant_id == "source-tenant-id"

    @patch("src.credential_provider.ClientSecretCredential")
    def test_credential_caching(self, mock_credential_class, dual_tenant_config):
        """Test credentials are cached per tenant."""
        mock_source_cred = Mock()
        mock_target_cred = Mock()
        mock_credential_class.side_effect = [mock_source_cred, mock_target_cred]

        provider = TenantCredentialProvider(dual_tenant_config)

        # First call creates credential
        cred1, _ = provider.get_credential(OperationType.DISCOVERY)
        assert cred1 == mock_source_cred

        # Second call returns cached credential
        cred2, _ = provider.get_credential(OperationType.DISCOVERY)
        assert cred2 == mock_source_cred

        # Only one credential created for source tenant
        assert mock_credential_class.call_count == 1

        # Different operation (deployment) creates new credential
        cred3, _ = provider.get_credential(OperationType.DEPLOYMENT)
        assert cred3 == mock_target_cred
        assert mock_credential_class.call_count == 2

    @patch("src.credential_provider.ClientSecretCredential")
    @patch("src.credential_provider.logger")
    def test_tenant_switch_logging(
        self, mock_logger, mock_credential_class, dual_tenant_config
    ):
        """Test tenant switches are logged."""
        mock_source_cred = Mock()
        mock_target_cred = Mock()
        mock_credential_class.side_effect = [mock_source_cred, mock_target_cred]

        provider = TenantCredentialProvider(dual_tenant_config)

        # First operation logs switch
        provider.get_credential(OperationType.DISCOVERY)
        assert mock_logger.info.called
        log_msg = mock_logger.info.call_args[0][0]
        assert "source tenant" in log_msg.lower()
        assert "DISCOVERY" in log_msg

        # Same operation doesn't log again
        mock_logger.reset_mock()
        provider.get_credential(OperationType.DISCOVERY)
        assert not mock_logger.info.called

        # Different operation logs switch
        provider.get_credential(OperationType.DEPLOYMENT)
        assert mock_logger.info.called
        log_msg = mock_logger.info.call_args[0][0]
        assert "target tenant" in log_msg.lower()
        assert "DEPLOYMENT" in log_msg

    def test_get_tenant_id(self, dual_tenant_config):
        """Test get_tenant_id returns correct tenant."""
        provider = TenantCredentialProvider(dual_tenant_config)

        assert provider.get_tenant_id(OperationType.DISCOVERY) == "source-tenant-id"
        assert provider.get_tenant_id(OperationType.DEPLOYMENT) == "target-tenant-id"
        assert provider.get_tenant_id(OperationType.VALIDATION) == "source-tenant-id"

    def test_get_subscription_id(self, dual_tenant_config):
        """Test get_subscription_id returns correct subscription."""
        provider = TenantCredentialProvider(dual_tenant_config)

        assert (
            provider.get_subscription_id(OperationType.DISCOVERY)
            == "source-subscription-id"
        )
        assert (
            provider.get_subscription_id(OperationType.DEPLOYMENT)
            == "target-subscription-id"
        )
        assert (
            provider.get_subscription_id(OperationType.VALIDATION)
            == "source-subscription-id"
        )

    def test_get_subscription_id_none(self):
        """Test get_subscription_id when no subscription configured."""
        source_creds = TenantCredentials(
            tenant_id="source-tenant-id",
            client_id="source-client-id",
            client_secret="source-secret",
            subscription_id=None,  # No subscription
        )

        config = DualTenantConfig(
            source_tenant=source_creds,
            target_tenant=None,
            operation_mode="single",
        )

        provider = TenantCredentialProvider(config)
        assert provider.get_subscription_id(OperationType.DISCOVERY) is None

    @patch("src.credential_provider.ClientSecretCredential")
    def test_clear_cache(self, mock_credential_class, dual_tenant_config):
        """Test cache clearing works."""
        mock_cred1 = Mock()
        mock_cred2 = Mock()
        mock_credential_class.side_effect = [mock_cred1, mock_cred2]

        provider = TenantCredentialProvider(dual_tenant_config)

        # Create credential
        provider.get_credential(OperationType.DISCOVERY)
        assert len(provider._credential_cache) == 1

        # Clear cache
        provider.clear_cache()
        assert len(provider._credential_cache) == 0
        assert provider._current_tenant_id is None

        # Next call creates new credential
        provider.get_credential(OperationType.DISCOVERY)
        assert mock_credential_class.call_count == 2

    def test_get_current_tenant_id(self, dual_tenant_config):
        """Test get_current_tenant_id tracks current tenant."""
        provider = TenantCredentialProvider(dual_tenant_config)

        assert provider.get_current_tenant_id() is None

        provider.get_credential(OperationType.DISCOVERY)
        assert provider.get_current_tenant_id() == "source-tenant-id"

        provider.get_credential(OperationType.DEPLOYMENT)
        assert provider.get_current_tenant_id() == "target-tenant-id"

    def test_is_dual_mode(self, single_tenant_config, dual_tenant_config):
        """Test is_dual_mode returns correct value."""
        single_provider = TenantCredentialProvider(single_tenant_config)
        assert not single_provider.is_dual_mode()

        dual_provider = TenantCredentialProvider(dual_tenant_config)
        assert dual_provider.is_dual_mode()

    def test_unknown_operation_type(self, dual_tenant_config):
        """Test unknown operation type raises error."""
        provider = TenantCredentialProvider(dual_tenant_config)

        # Create a mock invalid operation type
        invalid_operation = Mock()
        invalid_operation.value = "invalid"

        with pytest.raises(ValueError, match="Unknown operation type"):
            provider._select_tenant_credentials(invalid_operation)

    def test_no_credentials_configured(self):
        """Test error when no credentials configured in single mode."""
        config = DualTenantConfig(
            source_tenant=None, target_tenant=None, operation_mode="single"
        )

        # Single mode with no credentials should pass validation but fail on use
        provider = TenantCredentialProvider(config)

        # Should fail when trying to get credentials
        with pytest.raises(ValueError, match="No credentials configured"):
            provider.get_credential(OperationType.DISCOVERY)

    def test_missing_target_credentials_in_dual_mode(self):
        """Test error when target credentials missing in dual mode."""
        source_creds = TenantCredentials(
            tenant_id="source-tenant-id",
            client_id="source-client-id",
            client_secret="source-secret",
        )

        config = DualTenantConfig(
            source_tenant=source_creds,
            target_tenant=None,  # Missing target
            operation_mode="dual",
        )

        # Should fail validation
        with pytest.raises(ValueError):
            TenantCredentialProvider(config)
