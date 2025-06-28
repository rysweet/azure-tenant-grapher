"""
Tests for Azure Discovery Service.

This module provides comprehensive test coverage for the AzureDiscoveryService,
including authentication, subscription discovery, resource discovery, and error
handling scenarios.
"""

from typing import Any, Callable
from unittest.mock import Mock, patch

import pytest

from src.config_manager import AzureTenantGrapherConfig
from src.exceptions import AzureAuthenticationError, AzureDiscoveryError
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
    def mock_subscription_client(self) -> Mock:
        """Provide a mock SubscriptionClient instance."""
        return Mock()

    @pytest.fixture
    def mock_resource_client(self) -> Mock:
        """Provide a mock ResourceManagementClient instance."""
        return Mock()

    @pytest.fixture
    def subscription_client_factory(
        self, mock_subscription_client: Mock
    ) -> Callable[[Any], Mock]:
        """Factory for SubscriptionClient."""
        return lambda credential: mock_subscription_client

    @pytest.fixture
    def resource_client_factory(
        self, mock_resource_client: Mock
    ) -> Callable[[Any, str], Mock]:
        """Factory for ResourceManagementClient."""
        return lambda credential, subscription_id: mock_resource_client

    @pytest.fixture
    def azure_service(
        self,
        mock_config: Mock,
        mock_credential: Mock,
        subscription_client_factory: Callable[[Any], Mock],
        resource_client_factory: Callable[[Any, str], Mock],
    ) -> AzureDiscoveryService:
        """Provide an Azure Discovery Service instance with injected factories."""
        return AzureDiscoveryService(
            mock_config,
            mock_credential,
            subscription_client_factory=subscription_client_factory,
            resource_client_factory=resource_client_factory,
        )

    def test_initialization(
        self,
        mock_config: Mock,
        mock_credential: Mock,
        subscription_client_factory: Callable[[Any], Mock],
        resource_client_factory: Callable[[Any, str], Mock],
    ) -> None:
        """Test service initialization."""
        service = AzureDiscoveryService(
            mock_config,
            mock_credential,
            subscription_client_factory=subscription_client_factory,
            resource_client_factory=resource_client_factory,
        )
        assert service.config == mock_config
        assert service.credential == mock_credential
        assert service.subscriptions == []

    def test_initialization_with_default_credential(
        self,
        mock_config: Mock,
        subscription_client_factory: Callable[[Any], Mock],
        resource_client_factory: Callable[[Any, str], Mock],
    ) -> None:
        """Test service initialization with default credential."""
        with patch(
            "src.services.azure_discovery_service.DefaultAzureCredential"
        ) as mock_cred_class:
            mock_credential = Mock()
            mock_cred_class.return_value = mock_credential
            service = AzureDiscoveryService(
                mock_config,
                subscription_client_factory=subscription_client_factory,
                resource_client_factory=resource_client_factory,
            )
            assert service.config == mock_config
            assert service.credential == mock_credential
            mock_cred_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_discover_subscriptions_success(
        self, azure_service: AzureDiscoveryService, mock_subscription_client: Mock
    ) -> None:
        """Test successful subscription discovery."""
        # Setup mock subscription
        mock_subscription = Mock()
        mock_subscription.subscription_id = "test-sub-id"
        mock_subscription.display_name = "Test Subscription"
        mock_subscription_client.subscriptions.list.return_value = [mock_subscription]

        subscriptions = await azure_service.discover_subscriptions()

        assert len(subscriptions) == 1
        assert subscriptions[0]["id"] == "test-sub-id"
        assert subscriptions[0]["display_name"] == "Test Subscription"
        # Only minimal fields present
        assert set(subscriptions[0].keys()) == {"id", "display_name"}
        # Check cached subscriptions
        assert azure_service.subscriptions == subscriptions

    @pytest.mark.asyncio
    async def test_discover_subscriptions_empty_result(
        self, azure_service: AzureDiscoveryService, mock_subscription_client: Mock
    ) -> None:
        """Test subscription discovery with no subscriptions found."""
        mock_subscription_client.subscriptions.list.return_value = []

        subscriptions = await azure_service.discover_subscriptions()
        assert subscriptions == []
        assert azure_service.subscriptions == []

    @pytest.mark.asyncio
    async def test_discover_subscriptions_authentication_fallback_failure(
        self, mock_config: Mock, mock_credential: Mock
    ) -> None:
        """Test authentication fallback failure with AzureCliCredential unavailable."""
        from azure.core.exceptions import AzureError
        from azure.identity import CredentialUnavailableError

        with patch(
            "src.services.azure_discovery_service.AzureCliCredential"
        ) as mock_cli_cred_class:
            # First call: AzureError, fallback: CredentialUnavailableError
            call_count = {"count": 0}

            def subscription_client_factory(credential: Any) -> Mock:
                call_count["count"] += 1
                client = Mock()
                client.subscriptions.list.side_effect = AzureError(
                    "DefaultAzureCredential authentication failed"
                )
                return client

            def resource_client_factory(credential: Any, sub_id: str) -> Mock:
                return Mock()

            azure_service = AzureDiscoveryService(
                mock_config,
                mock_credential,
                subscription_client_factory=subscription_client_factory,
                resource_client_factory=resource_client_factory,
            )

            # Patch AzureCliCredential fallback

            mock_cli_cred = Mock()
            mock_cli_cred.get_token.side_effect = CredentialUnavailableError(
                "cli unavailable"
            )
            mock_cli_cred_class.return_value = mock_cli_cred

            with pytest.raises(
                AzureAuthenticationError, match="credential unavailable"
            ):
                await azure_service.discover_subscriptions()

    @pytest.mark.asyncio
    async def test_discover_subscriptions_retry_logic_run(
        self, mock_config: Mock, mock_credential: Mock
    ) -> None:
        from azure.core.exceptions import AzureError

        # Fail twice, succeed on third attempt
        call_count = {"count": 0}

        def subscription_client_factory(credential: Any) -> Mock:
            call_count["count"] += 1
            client = Mock()
            if call_count["count"] <= 2:
                client.subscriptions.list.side_effect = AzureError(
                    f"transient error {call_count['count']}"
                )
            else:
                sub = Mock(subscription_id="retry-sub", display_name="Retry Sub")
                client.subscriptions.list.return_value = [sub]
            return client

        def resource_client_factory(credential: Any, sub_id: str) -> Mock:
            return Mock()

        azure_service = AzureDiscoveryService(
            mock_config,
            mock_credential,
            subscription_client_factory=subscription_client_factory,
            resource_client_factory=resource_client_factory,
        )

        subscriptions = await azure_service.discover_subscriptions()
        assert len(subscriptions) == 1
        assert subscriptions[0]["id"] == "retry-sub"
        assert subscriptions[0]["display_name"] == "Retry Sub"

    @pytest.mark.asyncio
    async def test_discover_resources_in_subscription_success(
        self, azure_service: AzureDiscoveryService, mock_resource_client: Mock
    ) -> None:
        """Test successful resource discovery in subscription."""
        # Setup mock resource
        mock_resource = Mock()
        mock_resource.id = "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm"
        mock_resource.name = "test-vm"
        mock_resource.type = "Microsoft.Compute/virtualMachines"
        mock_resource.location = "eastus"
        mock_resource.tags = {"Environment": "Test"}
        mock_resource_client.resources.list.return_value = [mock_resource]

        resources = await azure_service.discover_resources_in_subscription(
            "test-sub-id"
        )
        assert len(resources) == 1
        assert resources[0]["id"] == mock_resource.id
        assert resources[0]["name"] == "test-vm"
        assert resources[0]["type"] == "Microsoft.Compute/virtualMachines"
        assert resources[0]["location"] == "eastus"
        assert resources[0]["tags"] == {"Environment": "Test"}
        assert resources[0]["subscription_id"] == "test-sub"
        assert resources[0]["resource_group"] == "test-rg"
        # Check all expected fields are present
        assert set(resources[0].keys()) == {
            "id",
            "name",
            "type",
            "location",
            "tags",
            "subscription_id",
            "resource_group",
        }

    @pytest.mark.asyncio
    async def test_discover_resources_in_subscription_with_minimal_resource(
        self, azure_service: AzureDiscoveryService, mock_resource_client: Mock
    ) -> None:
        """Test resource discovery with minimal resource information."""
        # Setup mock resource with minimal data
        mock_resource = Mock()
        mock_resource.id = None
        mock_resource.name = "minimal-resource"
        mock_resource.type = "Microsoft.Resources/unknown"
        mock_resource.location = None
        mock_resource.tags = None
        mock_resource_client.resources.list.return_value = [mock_resource]

        resources = await azure_service.discover_resources_in_subscription(
            "test-sub-id"
        )
        assert len(resources) == 1
        assert resources[0]["name"] == "minimal-resource"
        assert resources[0]["tags"] == {}
        assert (
            resources[0]["subscription_id"] == "test-sub-id"
        )  # Falls back to parameter
        assert resources[0]["resource_group"] is None  # Cannot parse from None ID
        assert set(resources[0].keys()) == {
            "id",
            "name",
            "type",
            "location",
            "tags",
            "subscription_id",
            "resource_group",
        }

    @pytest.mark.asyncio
    async def test_discover_resources_in_subscription_retry_logic_run(
        self, mock_config: Mock, mock_credential: Mock
    ) -> None:
        from azure.core.exceptions import AzureError

        # Fail twice, succeed on third attempt
        call_count = {"count": 0}

        def subscription_client_factory(credential: Any) -> Mock:
            return Mock()

        def resource_client_factory(credential: Any, sub_id: str) -> Mock:
            call_count["count"] += 1
            client = Mock()
            if call_count["count"] <= 2:
                client.resources.list.side_effect = AzureError(
                    f"transient error {call_count['count']}"
                )
            else:
                mock_resource = Mock()
                mock_resource.id = "res-id"
                mock_resource.name = "res"
                mock_resource.type = "type"
                mock_resource.location = "loc"
                mock_resource.tags = {}
                client.resources.list.return_value = [mock_resource]
            return client

        azure_service = AzureDiscoveryService(
            mock_config,
            mock_credential,
            subscription_client_factory=subscription_client_factory,
            resource_client_factory=resource_client_factory,
        )

        resources = await azure_service.discover_resources_in_subscription(
            "test-sub-id"
        )
        assert len(resources) == 1
        assert resources[0]["id"] == "res-id"
        assert resources[0]["name"] == "res"

    @pytest.mark.asyncio
    async def test_discover_resources_in_subscription_exception(
        self, azure_service: AzureDiscoveryService, mock_resource_client: Mock
    ) -> None:
        """Test resource discovery handles exceptions."""
        mock_resource_client.resources.list.side_effect = Exception("API Error")

        with pytest.raises(AzureDiscoveryError):
            await azure_service.discover_resources_in_subscription("test-sub-id")

    def test_clear_cache(self, azure_service: AzureDiscoveryService) -> None:
        """Test clearing subscription cache."""
        azure_service.clear_cache()
        assert azure_service.subscriptions == []

    def test_is_authenticated_success(
        self,
        mock_config: Mock,
        subscription_client_factory: Callable[[Any], Mock],
        resource_client_factory: Callable[[Any, str], Mock],
    ) -> None:
        """Test successful authentication check."""
        mock_credential = Mock()
        mock_credential.get_token = Mock(return_value=Mock(token="valid-token"))
        service = AzureDiscoveryService(
            mock_config,
            mock_credential,
            subscription_client_factory=subscription_client_factory,
            resource_client_factory=resource_client_factory,
        )
        assert service.is_authenticated() is True

    def test_is_authenticated_failure(
        self,
        mock_config: Mock,
        subscription_client_factory: Callable[[Any], Mock],
        resource_client_factory: Callable[[Any, str], Mock],
    ) -> None:
        """Test failed authentication check."""
        mock_credential = Mock()
        mock_credential.get_token = Mock(side_effect=Exception("Authentication failed"))
        service = AzureDiscoveryService(
            mock_config,
            mock_credential,
            subscription_client_factory=subscription_client_factory,
            resource_client_factory=resource_client_factory,
        )
        assert service.is_authenticated() is False

    @pytest.mark.asyncio
    async def test_subscriptions_property(
        self, azure_service: AzureDiscoveryService, mock_subscription_client: Mock
    ) -> None:
        """Test subscriptions property returns a copy."""
        mock_subscription = Mock()
        mock_subscription.subscription_id = "test-sub"
        mock_subscription.display_name = "Test"
        mock_subscription_client.subscriptions.list.return_value = [mock_subscription]

        # Populate cache through discovery
        original_data = await azure_service.discover_subscriptions()
        result = azure_service.subscriptions
        assert result == original_data
        # Should return a copy (different list object but same content)
        assert result is not azure_service.get_cached_subscriptions()

    def test_parse_resource_id_valid(
        self, azure_service: AzureDiscoveryService
    ) -> None:
        """Test parsing valid Azure resource ID."""
        resource_id = "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/my-rg/providers/Microsoft.Compute/virtualMachines/my-vm"
        result = azure_service._parse_resource_id(resource_id)  # type: ignore[misc]

        assert result["subscription_id"] == "12345678-1234-1234-1234-123456789012"
        assert result["resource_group"] == "my-rg"

    def test_parse_resource_id_empty_string(
        self, azure_service: AzureDiscoveryService
    ) -> None:
        """Test parsing empty resource ID."""
        result = azure_service._parse_resource_id("")  # type: ignore[misc]
        assert result == {}

    def test_parse_resource_id_invalid_format(
        self, azure_service: AzureDiscoveryService
    ) -> None:
        """Test parsing malformed resource ID."""
        result = azure_service._parse_resource_id("invalid-resource-id")  # type: ignore[misc]
        assert result == {}

    def test_parse_resource_id_missing_subscription(
        self, azure_service: AzureDiscoveryService
    ) -> None:
        """Test parsing resource ID missing subscription."""
        resource_id = (
            "/resourceGroups/my-rg/providers/Microsoft.Compute/virtualMachines/my-vm"
        )
        result = azure_service._parse_resource_id(resource_id)  # type: ignore[misc]

        assert "subscription_id" not in result
        assert result["resource_group"] == "my-rg"

    def test_parse_resource_id_missing_resource_group(
        self, azure_service: AzureDiscoveryService
    ) -> None:
        """Test parsing resource ID missing resource group."""
        resource_id = "/subscriptions/12345678-1234-1234-1234-123456789012/providers/Microsoft.Authorization/roleAssignments/role1"
        result = azure_service._parse_resource_id(resource_id)  # type: ignore[misc]

        assert result["subscription_id"] == "12345678-1234-1234-1234-123456789012"
        assert "resource_group" not in result

    @pytest.mark.asyncio
    async def test_discover_resources_regression_test_validation(
        self, azure_service: AzureDiscoveryService, mock_resource_client: Mock
    ) -> None:
        """Regression test: Ensure discovered resources pass ResourceProcessor validation."""

        from src.resource_processor import DatabaseOperations

        # Setup mock resource with valid resource ID
        mock_resource = Mock()
        mock_resource.id = "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm"
        mock_resource.name = "test-vm"
        mock_resource.type = "Microsoft.Compute/virtualMachines"
        mock_resource.location = "eastus"
        mock_resource.tags = {"Environment": "Test"}
        mock_resource_client.resources.list.return_value = [mock_resource]

        resources = await azure_service.discover_resources_in_subscription("test-sub")

        # Verify the resource dict contains all required fields for ResourceProcessor
        assert len(resources) == 1
        resource = resources[0]

        required_fields = [
            "id",
            "name",
            "type",
            "location",
            "resource_group",
            "subscription_id",
        ]
        for field in required_fields:
            assert field in resource, f"Missing required field: {field}"
            assert resource[field] is not None, f"Required field {field} is None"

        # Mock a session manager and verify upsert_resource would succeed
        from unittest.mock import MagicMock

        mock_session = MagicMock()
        mock_session.run = Mock()

        # Ensure the mock session supports context manager protocol
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=None)

        # Create a mock session manager that returns the mock session as a context manager
        mock_session_manager = MagicMock()
        mock_session_manager.session.return_value = mock_session

        db_ops = DatabaseOperations(mock_session_manager)

        # This should not raise a ResourceDataValidationError
        success = db_ops.upsert_resource(resource)
        assert success is True
        # Should be called twice: once for Subscription, once for Resource
        assert mock_session.run.call_count == 2
        calls = mock_session.run.call_args_list
        # First call: Subscription upsert
        assert "MERGE (s:Subscription" in calls[0][0][0]
        # Second call: Resource upsert
        assert "MERGE (r:Resource" in calls[1][0][0]


class TestAzureDiscoveryServiceFactory:
    """Test cases for the factory function."""

    def test_create_azure_discovery_service_with_credential(self) -> None:
        """Test factory function with provided credential."""
        config = Mock()
        credential = Mock()

        def subscription_client_factory(credential: Any) -> Mock:
            return Mock()

        def resource_client_factory(credential: Any, sub_id: str) -> Mock:
            return Mock()

        service = create_azure_discovery_service(
            config,
            credential,
            subscription_client_factory=subscription_client_factory,
            resource_client_factory=resource_client_factory,
        )
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

            def subscription_client_factory(credential: Any) -> Mock:
                return Mock()

            def resource_client_factory(credential: Any, sub_id: str) -> Mock:
                return Mock()

            service = create_azure_discovery_service(
                config,
                subscription_client_factory=subscription_client_factory,
                resource_client_factory=resource_client_factory,
            )
            assert isinstance(service, AzureDiscoveryService)
            assert service.config == config
            assert service.credential == mock_credential
