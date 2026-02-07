"""
Unit tests for AzureDiscoveryService.fetch_resource_by_id() method.

Tests verify that the discovery service can fetch individual resources by ID
for cross-RG dependency collection.

Following TDD methodology - these tests will FAIL until implementation is complete.
"""

from unittest.mock import Mock

import pytest

from src.services.azure_discovery_service import AzureDiscoveryService


class TestFetchResourceByIdSuccess:
    """Tests for successful resource fetching by ID."""

    @pytest.mark.asyncio
    async def test_fetch_resource_by_id_success(self):
        """Test fetching a resource by ID successfully."""
        # Mock Azure SDK client
        mock_client = Mock()
        mock_client.resources = Mock()
        mock_client.resources.get_by_id = Mock(
            return_value={
                "id": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic1",
                "name": "nic1",
                "type": "Microsoft.Network/networkInterfaces",
                "location": "eastus",
                "properties": {
                    "ipConfigurations": [
                        {
                            "name": "ipconfig1",
                            "properties": {
                                "privateIPAddress": "10.0.0.4",
                                "subnet": {
                                    "id": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1"
                                },
                            },
                        }
                    ]
                },
            }
        )

        discovery_service = AzureDiscoveryService(client=mock_client)

        resource_id = "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic1"

        # Act
        resource = await discovery_service.fetch_resource_by_id(resource_id)

        # Assert
        assert resource is not None, "Should return resource"
        assert resource["name"] == "nic1"
        assert resource["type"] == "Microsoft.Network/networkInterfaces"
        assert "properties" in resource
        assert (
            resource["properties"]["ipConfigurations"][0]["properties"][
                "privateIPAddress"
            ]
            == "10.0.0.4"
        )

        # Verify correct API call
        mock_client.resources.get_by_id.assert_called_once()


class TestFetchResourceByIdFailures:
    """Tests for handling failures when fetching resources by ID."""

    @pytest.mark.asyncio
    async def test_fetch_resource_by_id_not_found_returns_none(self):
        """Test that fetch_resource_by_id returns None when resource not found."""
        # Mock Azure SDK client that raises ResourceNotFoundError
        mock_client = Mock()
        mock_client.resources = Mock()
        mock_client.resources.get_by_id = Mock(
            side_effect=Exception(
                "ResourceNotFoundError: The Resource 'nic1' was not found."
            )
        )

        discovery_service = AzureDiscoveryService(client=mock_client)

        resource_id = "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic1"

        # Act
        resource = await discovery_service.fetch_resource_by_id(resource_id)

        # Assert
        assert resource is None, "Should return None when resource not found"

    @pytest.mark.asyncio
    async def test_fetch_resource_by_id_invalid_format_returns_none(self):
        """Test that fetch_resource_by_id returns None for malformed resource IDs."""
        mock_client = Mock()

        discovery_service = AzureDiscoveryService(client=mock_client)

        # Malformed resource ID (missing providers segment)
        invalid_resource_id = (
            "/subscriptions/sub1/resourceGroups/rg-network/networkInterfaces/nic1"
        )

        # Act
        resource = await discovery_service.fetch_resource_by_id(invalid_resource_id)

        # Assert
        assert resource is None, "Should return None for invalid resource ID format"
        # Should NOT call Azure SDK with invalid ID


class TestFetchResourceByIdApiVersion:
    """Tests for API version handling when fetching resources."""

    @pytest.mark.asyncio
    async def test_fetch_resource_by_id_uses_cached_api_version(self):
        """Test that fetch_resource_by_id uses cached API versions for efficiency."""
        # Mock Azure SDK client
        mock_client = Mock()
        mock_client.resources = Mock()
        mock_client.resources.get_by_id = Mock(
            return_value={
                "id": "/subscriptions/sub1/resourceGroups/rg-compute/providers/Microsoft.Compute/virtualMachines/vm1",
                "name": "vm1",
                "type": "Microsoft.Compute/virtualMachines",
                "location": "eastus",
            }
        )

        # Mock API version cache
        mock_api_version_cache = {
            "Microsoft.Compute/virtualMachines": "2023-03-01",
        }

        discovery_service = AzureDiscoveryService(
            client=mock_client,
            api_version_cache=mock_api_version_cache,
        )

        resource_id = "/subscriptions/sub1/resourceGroups/rg-compute/providers/Microsoft.Compute/virtualMachines/vm1"

        # Act
        resource = await discovery_service.fetch_resource_by_id(resource_id)

        # Assert
        assert resource is not None
        # Verify API version was used from cache (no additional lookup needed)
        # This should be observable through logging or instrumentation


class TestFetchResourceByIdCrossSubscription:
    """Tests for fetching resources across subscriptions."""

    @pytest.mark.asyncio
    async def test_fetch_resource_by_id_cross_subscription(self):
        """Test fetching a resource from a different subscription."""
        # Mock Azure SDK client that can access multiple subscriptions
        mock_client = Mock()
        mock_client.resources = Mock()
        mock_client.resources.get_by_id = Mock(
            return_value={
                "id": "/subscriptions/sub2/resourceGroups/rg-shared/providers/Microsoft.ManagedIdentity/userAssignedIdentities/identity1",
                "name": "identity1",
                "type": "Microsoft.ManagedIdentity/userAssignedIdentities",
                "location": "eastus",
                "properties": {
                    "clientId": "12345678-1234-1234-1234-123456789012",
                    "principalId": "87654321-4321-4321-4321-210987654321",
                },
            }
        )

        discovery_service = AzureDiscoveryService(client=mock_client)

        # Resource in different subscription (sub2 instead of sub1)
        resource_id = "/subscriptions/sub2/resourceGroups/rg-shared/providers/Microsoft.ManagedIdentity/userAssignedIdentities/identity1"

        # Act
        resource = await discovery_service.fetch_resource_by_id(resource_id)

        # Assert
        assert resource is not None, "Should fetch resource from different subscription"
        assert resource["name"] == "identity1"
        assert "sub2" in resource["id"], "Should have correct subscription ID"


class TestFetchResourceByIdResourceTypes:
    """Tests for fetching different resource types."""

    @pytest.mark.asyncio
    async def test_fetch_network_interface_by_id(self):
        """Test fetching a network interface resource."""
        mock_client = Mock()
        mock_client.resources = Mock()
        mock_client.resources.get_by_id = Mock(
            return_value={
                "id": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic1",
                "name": "nic1",
                "type": "Microsoft.Network/networkInterfaces",
                "location": "eastus",
                "properties": {
                    "enableIPForwarding": False,
                    "enableAcceleratedNetworking": True,
                    "networkSecurityGroup": {
                        "id": "/subscriptions/sub1/resourceGroups/rg-security/providers/Microsoft.Network/networkSecurityGroups/nsg1"
                    },
                },
            }
        )

        discovery_service = AzureDiscoveryService(client=mock_client)

        resource_id = "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic1"
        resource = await discovery_service.fetch_resource_by_id(resource_id)

        assert resource is not None
        assert resource["type"] == "Microsoft.Network/networkInterfaces"
        assert resource["properties"]["enableAcceleratedNetworking"] is True

    @pytest.mark.asyncio
    async def test_fetch_user_assigned_identity_by_id(self):
        """Test fetching a user-assigned managed identity resource."""
        mock_client = Mock()
        mock_client.resources = Mock()
        mock_client.resources.get_by_id = Mock(
            return_value={
                "id": "/subscriptions/sub1/resourceGroups/rg-identity/providers/Microsoft.ManagedIdentity/userAssignedIdentities/webapp-identity",
                "name": "webapp-identity",
                "type": "Microsoft.ManagedIdentity/userAssignedIdentities",
                "location": "eastus",
                "properties": {
                    "clientId": "11111111-1111-1111-1111-111111111111",
                    "principalId": "22222222-2222-2222-2222-222222222222",
                    "tenantId": "33333333-3333-3333-3333-333333333333",
                },
            }
        )

        discovery_service = AzureDiscoveryService(client=mock_client)

        resource_id = "/subscriptions/sub1/resourceGroups/rg-identity/providers/Microsoft.ManagedIdentity/userAssignedIdentities/webapp-identity"
        resource = await discovery_service.fetch_resource_by_id(resource_id)

        assert resource is not None
        assert resource["type"] == "Microsoft.ManagedIdentity/userAssignedIdentities"
        assert (
            resource["properties"]["clientId"] == "11111111-1111-1111-1111-111111111111"
        )

    @pytest.mark.asyncio
    async def test_fetch_subnet_by_id(self):
        """Test fetching a subnet resource (child resource with special ID format)."""
        mock_client = Mock()
        mock_client.resources = Mock()
        mock_client.resources.get_by_id = Mock(
            return_value={
                "id": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1",
                "name": "subnet1",
                "type": "Microsoft.Network/virtualNetworks/subnets",
                "properties": {
                    "addressPrefix": "10.0.1.0/24",
                    "networkSecurityGroup": {
                        "id": "/subscriptions/sub1/resourceGroups/rg-security/providers/Microsoft.Network/networkSecurityGroups/nsg1"
                    },
                    "privateEndpointNetworkPolicies": "Disabled",
                },
            }
        )

        discovery_service = AzureDiscoveryService(client=mock_client)

        # Subnet has special ID format (child resource)
        resource_id = "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1"
        resource = await discovery_service.fetch_resource_by_id(resource_id)

        assert resource is not None
        assert resource["type"] == "Microsoft.Network/virtualNetworks/subnets"
        assert resource["properties"]["addressPrefix"] == "10.0.1.0/24"

    @pytest.mark.asyncio
    async def test_fetch_log_analytics_workspace_by_id(self):
        """Test fetching a Log Analytics workspace resource."""
        mock_client = Mock()
        mock_client.resources = Mock()
        mock_client.resources.get_by_id = Mock(
            return_value={
                "id": "/subscriptions/sub1/resourceGroups/rg-monitoring/providers/Microsoft.OperationalInsights/workspaces/workspace1",
                "name": "workspace1",
                "type": "Microsoft.OperationalInsights/workspaces",
                "location": "eastus",
                "properties": {
                    "sku": {"name": "PerGB2018"},
                    "retentionInDays": 30,
                    "customerId": "12345678-1234-1234-1234-123456789012",
                },
            }
        )

        discovery_service = AzureDiscoveryService(client=mock_client)

        resource_id = "/subscriptions/sub1/resourceGroups/rg-monitoring/providers/Microsoft.OperationalInsights/workspaces/workspace1"
        resource = await discovery_service.fetch_resource_by_id(resource_id)

        assert resource is not None
        assert resource["type"] == "Microsoft.OperationalInsights/workspaces"
        assert resource["properties"]["retentionInDays"] == 30


class TestFetchResourceByIdPermissions:
    """Tests for handling permission issues when fetching resources."""

    @pytest.mark.asyncio
    async def test_fetch_resource_by_id_insufficient_permissions(self):
        """Test handling case where user lacks permissions to read resource."""
        # Mock Azure SDK client that raises AuthorizationError
        mock_client = Mock()
        mock_client.resources = Mock()
        mock_client.resources.get_by_id = Mock(
            side_effect=Exception(
                "AuthorizationFailed: The client 'user@example.com' does not have authorization to perform action 'Microsoft.Network/networkInterfaces/read'"
            )
        )

        discovery_service = AzureDiscoveryService(client=mock_client)

        resource_id = "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic1"

        # Act
        resource = await discovery_service.fetch_resource_by_id(resource_id)

        # Assert
        assert resource is None, "Should return None when user lacks permissions"
        # Should log warning about insufficient permissions


class TestFetchResourceByIdPerformance:
    """Tests for performance characteristics of fetch_resource_by_id."""

    @pytest.mark.asyncio
    async def test_fetch_resource_by_id_caches_api_versions(self):
        """Test that API version lookups are cached to avoid repeated queries."""
        mock_client = Mock()
        mock_client.resources = Mock()
        mock_client.resources.get_by_id = Mock(
            return_value={
                "id": "/subscriptions/sub1/resourceGroups/rg-compute/providers/Microsoft.Compute/virtualMachines/vm1",
                "name": "vm1",
                "type": "Microsoft.Compute/virtualMachines",
            }
        )

        # Start with empty cache
        discovery_service = AzureDiscoveryService(
            client=mock_client, api_version_cache={}
        )

        # Fetch same resource type twice
        await discovery_service.fetch_resource_by_id(
            "/subscriptions/sub1/resourceGroups/rg-compute/providers/Microsoft.Compute/virtualMachines/vm1"
        )
        await discovery_service.fetch_resource_by_id(
            "/subscriptions/sub1/resourceGroups/rg-compute/providers/Microsoft.Compute/virtualMachines/vm2"
        )

        # Assert: API version should be cached after first fetch
        # Second fetch should not require API version lookup
        # (This would be verified through instrumentation/logging)
        assert (
            "Microsoft.Compute/virtualMachines" in discovery_service.api_version_cache
        )


class TestFetchResourceByIdErrorRecovery:
    """Tests for error recovery and resilience."""

    @pytest.mark.asyncio
    async def test_fetch_resource_by_id_retries_on_transient_errors(self):
        """Test that fetch_resource_by_id retries on transient network errors."""
        # Mock Azure SDK client that fails first time, succeeds second time
        mock_client = Mock()
        mock_client.resources = Mock()

        call_count = 0

        def mock_get_by_id(resource_id, api_version):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception(
                    "ServiceUnavailable: The service is temporarily unavailable"
                )
            return {
                "id": resource_id,
                "name": "nic1",
                "type": "Microsoft.Network/networkInterfaces",
            }

        mock_client.resources.get_by_id = Mock(side_effect=mock_get_by_id)

        discovery_service = AzureDiscoveryService(
            client=mock_client,
            enable_retries=True,
            max_retries=3,
        )

        resource_id = "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic1"

        # Act
        resource = await discovery_service.fetch_resource_by_id(resource_id)

        # Assert
        assert resource is not None, "Should succeed after retry"
        assert call_count == 2, "Should have retried once"

    @pytest.mark.asyncio
    async def test_fetch_resource_by_id_gives_up_after_max_retries(self):
        """Test that fetch_resource_by_id gives up after maximum retries."""
        # Mock Azure SDK client that always fails
        mock_client = Mock()
        mock_client.resources = Mock()
        mock_client.resources.get_by_id = Mock(
            side_effect=Exception(
                "ServiceUnavailable: The service is temporarily unavailable"
            )
        )

        discovery_service = AzureDiscoveryService(
            client=mock_client,
            enable_retries=True,
            max_retries=3,
        )

        resource_id = "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic1"

        # Act
        resource = await discovery_service.fetch_resource_by_id(resource_id)

        # Assert
        assert resource is None, "Should return None after exhausting retries"
        assert mock_client.resources.get_by_id.call_count <= 3, (
            "Should not exceed max retries"
        )
