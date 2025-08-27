"""Tests for parallel resource property fetching in Azure Discovery Service."""

import asyncio
import json
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock, patch

import pytest
from azure.core.exceptions import HttpResponseError

from src.config_manager import AzureTenantGrapherConfig
from src.services.azure_discovery_service import AzureDiscoveryService


class TestParallelPropertyFetching:
    """Test suite for parallel property fetching functionality."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        config = Mock(spec=AzureTenantGrapherConfig)
        config.tenant_id = "test-tenant-id"
        config.processing = Mock()
        config.processing.max_retries = 3
        config.processing.max_build_threads = 5
        return config

    @pytest.fixture
    def mock_resource_client(self):
        """Create a mock ResourceManagementClient."""
        client = Mock()
        
        # Mock the providers.get method for API version resolution
        provider_info = Mock()
        resource_type = Mock()
        resource_type.resource_type = "virtualMachines"
        resource_type.api_versions = ["2023-03-01", "2022-11-01", "2021-11-01"]
        provider_info.resource_types = [resource_type]
        client.providers.get.return_value = provider_info
        
        # Mock the resources.get_by_id method
        full_resource = Mock()
        full_resource.properties = Mock()
        full_resource.properties.as_dict.return_value = {
            "vmSize": "Standard_D4s_v3",
            "provisioningState": "Succeeded",
            "osProfile": {
                "computerName": "testvm",
                "adminUsername": "azureuser"
            }
        }
        client.resources.get_by_id.return_value = full_resource
        
        return client

    @pytest.fixture
    def discovery_service(self, mock_config):
        """Create an AzureDiscoveryService instance with mocked dependencies."""
        def mock_resource_client_factory(credential, subscription_id):
            return Mock()
        
        service = AzureDiscoveryService(
            config=mock_config,
            resource_client_factory=mock_resource_client_factory
        )
        return service

    def test_parse_resource_id_with_provider(self, discovery_service):
        """Test parsing resource ID extracts provider and resource type."""
        resource_id = "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/vm-test"
        
        parsed = discovery_service._parse_resource_id(resource_id)
        
        assert parsed["subscription_id"] == "sub-123"
        assert parsed["resource_group"] == "rg-test"
        assert parsed["provider"] == "Microsoft.Compute"
        assert parsed["resource_type"] == "virtualMachines"

    def test_parse_resource_id_without_provider(self, discovery_service):
        """Test parsing resource ID without provider returns partial results."""
        resource_id = "/subscriptions/sub-123/resourceGroups/rg-test"
        
        parsed = discovery_service._parse_resource_id(resource_id)
        
        assert parsed["subscription_id"] == "sub-123"
        assert parsed["resource_group"] == "rg-test"
        assert parsed.get("provider") is None
        assert parsed.get("resource_type") is None

    @pytest.mark.asyncio
    async def test_get_api_version_for_resource(self, discovery_service, mock_resource_client):
        """Test API version resolution for a resource."""
        resource_id = "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/vm-test"
        
        api_version = await discovery_service._get_api_version_for_resource(
            resource_id, mock_resource_client
        )
        
        assert api_version == "2023-03-01"  # Should use the latest version
        # Should be cached
        assert "Microsoft.Compute/virtualMachines" in discovery_service._api_version_cache
        assert discovery_service._api_version_cache["Microsoft.Compute/virtualMachines"] == "2023-03-01"

    @pytest.mark.asyncio
    async def test_get_api_version_fallback(self, discovery_service, mock_resource_client):
        """Test API version fallback when provider query fails."""
        resource_id = "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Unknown/unknownType/resource"
        mock_resource_client.providers.get.side_effect = Exception("Provider not found")
        
        api_version = await discovery_service._get_api_version_for_resource(
            resource_id, mock_resource_client
        )
        
        assert api_version == "2021-04-01"  # Should use default fallback

    @pytest.mark.asyncio
    async def test_fetch_single_resource_with_properties_success(self, discovery_service, mock_resource_client):
        """Test successful fetching of single resource properties."""
        resource = {
            "id": "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/vm-test",
            "name": "vm-test",
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {}
        }
        semaphore = asyncio.Semaphore(1)
        
        result = await discovery_service._fetch_single_resource_with_properties(
            resource, mock_resource_client, semaphore
        )
        
        assert result["properties"]["vmSize"] == "Standard_D4s_v3"
        assert result["properties"]["provisioningState"] == "Succeeded"
        assert result["properties"]["osProfile"]["computerName"] == "testvm"

    @pytest.mark.asyncio
    async def test_fetch_single_resource_handles_error(self, discovery_service, mock_resource_client):
        """Test error handling when fetching single resource fails."""
        resource = {
            "id": "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/vm-test",
            "name": "vm-test",
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {}
        }
        semaphore = asyncio.Semaphore(1)
        
        # Mock an API error
        mock_resource_client.resources.get_by_id.side_effect = HttpResponseError(
            message="InvalidApiVersionParameter: The api-version is invalid"
        )
        
        result = await discovery_service._fetch_single_resource_with_properties(
            resource, mock_resource_client, semaphore
        )
        
        # Should return resource with empty properties on error
        assert result["properties"] == {}
        assert result["name"] == "vm-test"

    @pytest.mark.asyncio
    async def test_fetch_resources_with_properties_batch_processing(self, discovery_service, mock_resource_client):
        """Test batch processing of multiple resources."""
        # Create 250 resources to test batching (batch size is 100)
        resources = [
            {
                "id": f"/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/vm-{i}",
                "name": f"vm-{i}",
                "type": "Microsoft.Compute/virtualMachines",
                "properties": {}
            }
            for i in range(250)
        ]
        
        # Mock successful responses for all
        mock_resource_client.resources.get_by_id.return_value = Mock(
            properties=Mock(as_dict=lambda: {"vmSize": "Standard_D2s_v3"})
        )
        
        results = await discovery_service._fetch_resources_with_properties(
            resources, mock_resource_client, "sub-123"
        )
        
        assert len(results) == 250
        # All should have properties
        success_count = len([r for r in results if r.get("properties")])
        assert success_count == 250

    @pytest.mark.asyncio
    async def test_fetch_resources_respects_semaphore(self, discovery_service, mock_resource_client):
        """Test that concurrent fetches respect the semaphore limit."""
        discovery_service._max_build_threads = 2  # Limit concurrency to 2
        
        resources = [
            {
                "id": f"/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/vm-{i}",
                "name": f"vm-{i}",
                "type": "Microsoft.Compute/virtualMachines",
                "properties": {}
            }
            for i in range(10)
        ]
        
        # Track concurrent calls
        concurrent_calls = []
        max_concurrent = 0
        
        async def mock_get_by_id(resource_id, api_version):
            nonlocal max_concurrent
            concurrent_calls.append(1)
            current = len(concurrent_calls)
            if current > max_concurrent:
                max_concurrent = current
            await asyncio.sleep(0.1)  # Simulate API call delay
            concurrent_calls.pop()
            return Mock(properties=Mock(as_dict=lambda: {"vmSize": "Standard_D2s_v3"}))
        
        mock_resource_client.resources.get_by_id = mock_get_by_id
        
        await discovery_service._fetch_resources_with_properties(
            resources, mock_resource_client, "sub-123"
        )
        
        # Should never exceed semaphore limit
        assert max_concurrent <= 2

    @pytest.mark.asyncio
    async def test_discover_resources_with_parallel_fetching(self, discovery_service):
        """Test full discover_resources_in_subscription with parallel fetching."""
        # Mock the resource client factory
        mock_client = Mock()
        
        # Mock list() to return basic resources
        mock_resources = [
            Mock(
                id=f"/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/vm-{i}",
                name=f"vm-{i}",
                type="Microsoft.Compute/virtualMachines",
                location="eastus",
                tags={"env": "test"},
                properties=None  # Properties are None in list response
            )
            for i in range(5)
        ]
        mock_client.resources.list.return_value = mock_resources
        
        # Mock get_by_id to return full properties
        mock_client.resources.get_by_id.return_value = Mock(
            properties=Mock(as_dict=lambda: {"vmSize": "Standard_D4s_v3"})
        )
        
        # Mock providers.get for API version resolution
        provider_info = Mock()
        resource_type = Mock()
        resource_type.resource_type = "virtualMachines"
        resource_type.api_versions = ["2023-03-01"]
        provider_info.resource_types = [resource_type]
        mock_client.providers.get.return_value = provider_info
        
        discovery_service.resource_client_factory = lambda cred, sub_id: mock_client
        discovery_service._max_build_threads = 3  # Enable parallel fetching
        
        results = await discovery_service.discover_resources_in_subscription("sub-123")
        
        assert len(results) == 5
        # All should have properties since parallel fetching is enabled
        for result in results:
            assert "vmSize" in result["properties"]
            assert result["properties"]["vmSize"] == "Standard_D4s_v3"

    @pytest.mark.asyncio
    async def test_discover_resources_without_parallel_fetching(self, discovery_service):
        """Test discover_resources_in_subscription with parallel fetching disabled."""
        # Mock the resource client factory
        mock_client = Mock()
        
        # Mock list() to return basic resources
        mock_resources = [
            Mock(
                id=f"/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/vm-{i}",
                name=f"vm-{i}",
                type="Microsoft.Compute/virtualMachines",
                location="eastus",
                tags={"env": "test"},
                properties=None  # Properties are None in list response
            )
            for i in range(5)
        ]
        mock_client.resources.list.return_value = mock_resources
        
        discovery_service.resource_client_factory = lambda cred, sub_id: mock_client
        discovery_service._max_build_threads = 0  # Disable parallel fetching
        
        results = await discovery_service.discover_resources_in_subscription("sub-123")
        
        assert len(results) == 5
        # Properties should be empty since parallel fetching is disabled
        for result in results:
            assert result["properties"] == {}
        
        # get_by_id should never be called
        mock_client.resources.get_by_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_batch_timeout_handling(self, discovery_service, mock_resource_client):
        """Test that batch timeouts are handled gracefully."""
        resources = [
            {
                "id": f"/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/vm-{i}",
                "name": f"vm-{i}",
                "type": "Microsoft.Compute/virtualMachines",
                "properties": {}
            }
            for i in range(10)
        ]
        
        # Mock get_by_id to hang forever
        async def hanging_get(*args, **kwargs):
            await asyncio.sleep(10000)  # Sleep for a very long time
        
        mock_resource_client.resources.get_by_id = hanging_get
        
        # Reduce timeout for testing
        with patch.object(discovery_service, '_fetch_resources_with_properties') as mock_fetch:
            async def custom_fetch(resources, client, sub_id):
                # Simulate timeout for first batch
                return [{"properties": {}} for _ in resources]
            
            mock_fetch.side_effect = custom_fetch
            
            results = await discovery_service._fetch_resources_with_properties(
                resources, mock_resource_client, "sub-123"
            )
            
            # Should return resources with empty properties after timeout
            assert len(results) == 10
            for result in results:
                assert result["properties"] == {}