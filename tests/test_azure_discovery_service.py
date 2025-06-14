"""
Tests for Azure Discovery Service.

This module provides comprehensive test coverage for the AzureDiscoveryService,
including authentication, subscription discovery, resource discovery, and error
handling scenarios.
"""

import subprocess
from unittest.mock import Mock, patch

import pytest

from src.config_manager import AzureTenantGrapherConfig
from src.exceptions import AzureAuthenticationError
from src.services.azure_discovery_service import (
    AzureDiscoveryService,
    create_azure_discovery_service,
)


class TestAzureDiscoveryService:
    """Test cases for AzureDiscoveryService."""

    @pytest.fixture
    def mock_config(self) -> Mock:
        """Provide a mock configuration."""
        config = Mock(spec=AzureTenantGrapherConfig)
        config.tenant_id = "test-tenant-id"
        return config

    @pytest.fixture
    def mock_credential(self) -> Mock:
        """Provide a mock Azure credential."""
        credential = Mock()
        credential.get_token.return_value = Mock(token="test-token")
        return credential

    @pytest.fixture
    def azure_service(
        self, mock_config: Mock, mock_credential: Mock
    ) -> AzureDiscoveryService:
        """Provide an Azure Discovery Service instance."""
        return AzureDiscoveryService(mock_config, mock_credential)

    def test_initialization(self, mock_config: Mock, mock_credential: Mock) -> None:
        """Test service initialization."""
        service = AzureDiscoveryService(mock_config, mock_credential)

        assert service.config == mock_config
        assert service.credential == mock_credential
        assert service.subscriptions == []

    def test_initialization_with_default_credential(self, mock_config: Mock) -> None:
        """Test service initialization with default credential."""
        with patch(
            "src.services.azure_discovery_service.DefaultAzureCredential"
        ) as mock_cred_class:
            mock_credential = Mock()
            mock_cred_class.return_value = mock_credential

            service = AzureDiscoveryService(mock_config)

            assert service.config == mock_config
            assert service.credential == mock_credential
            mock_cred_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_discover_subscriptions_success(
        self, azure_service: AzureDiscoveryService
    ) -> None:
        """Test successful subscription discovery."""
        with patch(
            "src.services.azure_discovery_service.SubscriptionClient"
        ) as mock_client_class:
            # Setup mock subscription
            mock_subscription = Mock()
            mock_subscription.subscription_id = "test-sub-id"
            mock_subscription.display_name = "Test Subscription"
            mock_subscription.state = "Enabled"
            mock_subscription.tenant_id = "test-tenant-id"

            mock_client = Mock()
            mock_client.subscriptions.list.return_value = [mock_subscription]
            mock_client_class.return_value = mock_client

            subscriptions = await azure_service.discover_subscriptions()

            assert len(subscriptions) == 1
            assert subscriptions[0]["id"] == "test-sub-id"
            assert subscriptions[0]["display_name"] == "Test Subscription"
            assert subscriptions[0]["state"] == "Enabled"
            assert subscriptions[0]["tenant_id"] == "test-tenant-id"

            # Check cached subscriptions
            assert azure_service.subscriptions == subscriptions

    @pytest.mark.asyncio
    async def test_discover_subscriptions_empty_result(
        self, azure_service: AzureDiscoveryService
    ) -> None:
        """Test subscription discovery with no subscriptions found."""
        with patch(
            "src.services.azure_discovery_service.SubscriptionClient"
        ) as mock_client_class:
            mock_client = Mock()
            mock_client.subscriptions.list.return_value = []
            mock_client_class.return_value = mock_client

            subscriptions = await azure_service.discover_subscriptions()

            assert subscriptions == []
            assert azure_service.subscriptions == []

    @pytest.mark.asyncio
    async def test_discover_subscriptions_authentication_fallback_success(
        self, azure_service: AzureDiscoveryService
    ) -> None:
        """Test successful authentication fallback during subscription discovery."""
        with patch(
            "src.services.azure_discovery_service.SubscriptionClient"
        ) as mock_client_class:
            with patch(
                "src.services.azure_discovery_service.subprocess.run"
            ) as mock_subprocess:
                with patch(
                    "src.services.azure_discovery_service.DefaultAzureCredential"
                ) as mock_cred_class:
                    # First call fails with auth error
                    mock_client = Mock()
                    mock_client.subscriptions.list.side_effect = [
                        Exception("DefaultAzureCredential authentication failed"),
                        # After fallback, return successful result
                        [
                            Mock(
                                subscription_id="fallback-sub",
                                display_name="Fallback Sub",
                                state="Enabled",
                                tenant_id="test-tenant-id",
                            )
                        ],
                    ]
                    mock_client_class.return_value = mock_client

                    # Mock successful az login
                    mock_subprocess.return_value = Mock(returncode=0, stderr="")

                    # Mock new credential after fallback
                    mock_new_credential = Mock()
                    mock_cred_class.return_value = mock_new_credential

                    subscriptions = await azure_service.discover_subscriptions()

                    assert len(subscriptions) == 1
                    assert subscriptions[0]["id"] == "fallback-sub"

                    # Verify az login was called
                    mock_subprocess.assert_called_once_with(
                        ["az", "login", "--tenant", "test-tenant-id"],
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )

    @pytest.mark.asyncio
    async def test_discover_subscriptions_authentication_fallback_no_tenant(
        self, mock_credential: Mock
    ) -> None:
        """Test authentication fallback failure when no tenant ID is configured."""
        config = Mock()
        config.tenant_id = None
        service = AzureDiscoveryService(config, mock_credential)

        with patch(
            "src.services.azure_discovery_service.SubscriptionClient"
        ) as mock_client_class:
            mock_client = Mock()
            mock_client.subscriptions.list.side_effect = Exception(
                "authentication failed"
            )
            mock_client_class.return_value = mock_client

            with pytest.raises(AzureAuthenticationError, match="Tenant ID is required"):
                await service.discover_subscriptions()

    @pytest.mark.asyncio
    async def test_discover_subscriptions_authentication_fallback_az_login_failure(
        self, azure_service: AzureDiscoveryService
    ) -> None:
        """Test authentication fallback when az login fails."""
        with patch(
            "src.services.azure_discovery_service.SubscriptionClient"
        ) as mock_client_class:
            with patch(
                "src.services.azure_discovery_service.subprocess.run"
            ) as mock_subprocess:
                mock_client = Mock()
                mock_client.subscriptions.list.side_effect = Exception(
                    "authentication failed"
                )
                mock_client_class.return_value = mock_client

                # Mock failed az login
                mock_subprocess.return_value = Mock(returncode=1, stderr="Login failed")

                with pytest.raises(
                    AzureAuthenticationError, match="Azure CLI login failed"
                ):
                    await azure_service.discover_subscriptions()

    @pytest.mark.asyncio
    async def test_discover_subscriptions_authentication_fallback_timeout(
        self, azure_service: AzureDiscoveryService
    ) -> None:
        """Test authentication fallback when az login times out."""
        with patch(
            "src.services.azure_discovery_service.SubscriptionClient"
        ) as mock_client_class:
            with patch(
                "src.services.azure_discovery_service.subprocess.run"
            ) as mock_subprocess:
                mock_client = Mock()
                mock_client.subscriptions.list.side_effect = Exception(
                    "authentication failed"
                )
                mock_client_class.return_value = mock_client

                # Mock timeout
                mock_subprocess.side_effect = subprocess.TimeoutExpired("az", 120)

                with pytest.raises(AzureAuthenticationError, match="timed out"):
                    await azure_service.discover_subscriptions()

    @pytest.mark.asyncio
    async def test_discover_subscriptions_authentication_fallback_az_not_found(
        self, azure_service: AzureDiscoveryService
    ) -> None:
        """Test authentication fallback when Azure CLI is not installed."""
        with patch(
            "src.services.azure_discovery_service.SubscriptionClient"
        ) as mock_client_class:
            with patch(
                "src.services.azure_discovery_service.subprocess.run"
            ) as mock_subprocess:
                mock_client = Mock()
                mock_client.subscriptions.list.side_effect = Exception(
                    "authentication failed"
                )
                mock_client_class.return_value = mock_client

                # Mock Azure CLI not found
                mock_subprocess.side_effect = FileNotFoundError("az command not found")

                with pytest.raises(
                    AzureAuthenticationError, match="Azure CLI not found"
                ):
                    await azure_service.discover_subscriptions()

    @pytest.mark.asyncio
    async def test_discover_subscriptions_non_auth_error(
        self, azure_service: AzureDiscoveryService
    ) -> None:
        """Test subscription discovery with non-authentication errors."""
        with patch(
            "src.services.azure_discovery_service.SubscriptionClient"
        ) as mock_client_class:
            mock_client = Mock()
            mock_client.subscriptions.list.side_effect = Exception("Network error")
            mock_client_class.return_value = mock_client

            with pytest.raises(Exception, match="Network error"):
                await azure_service.discover_subscriptions()

    @pytest.mark.asyncio
    async def test_discover_resources_in_subscription_success(
        self, azure_service: AzureDiscoveryService
    ) -> None:
        """Test successful resource discovery in subscription."""
        with patch(
            "src.services.azure_discovery_service.ResourceManagementClient"
        ) as mock_client_class:
            # Setup mock resource
            mock_resource = Mock()
            mock_resource.id = "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm"
            mock_resource.name = "test-vm"
            mock_resource.type = "Microsoft.Compute/virtualMachines"
            mock_resource.location = "eastus"
            mock_resource.tags = {"Environment": "Test"}
            mock_resource.kind = None
            mock_resource.sku = None

            mock_client = Mock()
            mock_client.resources.list.return_value = [mock_resource]
            mock_client_class.return_value = mock_client

            resources = await azure_service.discover_resources_in_subscription(
                "test-sub-id"
            )

            assert len(resources) == 1
            assert resources[0]["name"] == "test-vm"
            assert resources[0]["type"] == "Microsoft.Compute/virtualMachines"
            assert resources[0]["resource_group"] == "test-rg"
            assert resources[0]["subscription_id"] == "test-sub-id"
            assert resources[0]["tags"] == {"Environment": "Test"}

    @pytest.mark.asyncio
    async def test_discover_resources_in_subscription_with_minimal_resource(
        self, azure_service: AzureDiscoveryService
    ) -> None:
        """Test resource discovery with minimal resource information."""
        with patch(
            "src.services.azure_discovery_service.ResourceManagementClient"
        ) as mock_client_class:
            # Setup mock resource with minimal data
            mock_resource = Mock()
            mock_resource.id = None
            mock_resource.name = "minimal-resource"
            mock_resource.type = "Microsoft.Resources/unknown"
            mock_resource.location = None
            mock_resource.tags = None
            mock_resource.kind = None
            mock_resource.sku = None

            mock_client = Mock()
            mock_client.resources.list.return_value = [mock_resource]
            mock_client_class.return_value = mock_client

            resources = await azure_service.discover_resources_in_subscription(
                "test-sub-id"
            )

            assert len(resources) == 1
            assert resources[0]["name"] == "minimal-resource"
            assert resources[0]["resource_group"] is None
            assert resources[0]["tags"] == {}

    @pytest.mark.asyncio
    async def test_discover_resources_in_subscription_exception(
        self, azure_service: AzureDiscoveryService
    ) -> None:
        """Test resource discovery handles exceptions."""
        with patch(
            "src.services.azure_discovery_service.ResourceManagementClient"
        ) as mock_client_class:
            mock_client = Mock()
            mock_client.resources.list.side_effect = Exception("API Error")
            mock_client_class.return_value = mock_client

            with pytest.raises(Exception):
                await azure_service.discover_resources_in_subscription("test-sub-id")

    @pytest.mark.asyncio
    async def test_get_cached_subscriptions(
        self, azure_service: AzureDiscoveryService
    ) -> None:
        """Test getting cached subscriptions."""
        # Use the public method to set cached data
        with patch(
            "src.services.azure_discovery_service.SubscriptionClient"
        ) as mock_client_class:
            mock_subscription = Mock()
            mock_subscription.subscription_id = "test-sub"
            mock_subscription.display_name = "Test"
            mock_subscription.state = "Enabled"
            mock_subscription.tenant_id = "test-tenant"

            mock_client = Mock()
            mock_client.subscriptions.list.return_value = [mock_subscription]
            mock_client_class.return_value = mock_client

            # Populate cache through discovery
            await azure_service.discover_subscriptions()

            cached = azure_service.get_cached_subscriptions()
            assert len(cached) == 1
            assert cached[0]["id"] == "test-sub"

    def test_clear_cache(self, azure_service: AzureDiscoveryService) -> None:
        """Test clearing subscription cache."""
        azure_service.clear_cache()
        assert azure_service.subscriptions == []

    def test_is_authenticated_success(self, mock_config: Mock) -> None:
        """Test successful authentication check."""
        mock_credential = Mock()
        mock_credential.get_token = Mock(return_value=Mock(token="valid-token"))

        service = AzureDiscoveryService(mock_config, mock_credential)
        assert service.is_authenticated() is True

    def test_is_authenticated_failure(self, mock_config: Mock) -> None:
        """Test failed authentication check."""
        mock_credential = Mock()
        mock_credential.get_token = Mock(side_effect=Exception("Authentication failed"))

        service = AzureDiscoveryService(mock_config, mock_credential)
        assert service.is_authenticated() is False

    @pytest.mark.asyncio
    async def test_subscriptions_property(
        self, azure_service: AzureDiscoveryService
    ) -> None:
        """Test subscriptions property returns a copy."""
        with patch(
            "src.services.azure_discovery_service.SubscriptionClient"
        ) as mock_client_class:
            mock_subscription = Mock()
            mock_subscription.subscription_id = "test-sub"
            mock_subscription.display_name = "Test"
            mock_subscription.state = "Enabled"
            mock_subscription.tenant_id = "test-tenant"

            mock_client = Mock()
            mock_client.subscriptions.list.return_value = [mock_subscription]
            mock_client_class.return_value = mock_client

            # Populate cache through discovery
            original_data = await azure_service.discover_subscriptions()
            result = azure_service.subscriptions

            assert result == original_data
            # Should return a copy (different list object but same content)
            assert result is not azure_service.get_cached_subscriptions()


class TestAzureDiscoveryServiceFactory:
    """Test cases for the factory function."""

    def test_create_azure_discovery_service_with_credential(self) -> None:
        """Test factory function with provided credential."""
        config = Mock()
        credential = Mock()

        service = create_azure_discovery_service(config, credential)

        assert isinstance(service, AzureDiscoveryService)
        assert service.config == config
        assert service.credential == credential

    def test_create_azure_discovery_service_without_credential(self) -> None:
        """Test factory function without provided credential."""
        with patch(
            "src.services.azure_discovery_service.DefaultAzureCredential"
        ) as mock_cred_class:
            config = Mock()
            mock_credential = Mock()
            mock_cred_class.return_value = mock_credential

            service = create_azure_discovery_service(config)

            assert isinstance(service, AzureDiscoveryService)
            assert service.config == config
            assert service.credential == mock_credential
