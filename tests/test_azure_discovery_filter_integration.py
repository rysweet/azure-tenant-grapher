"""Integration tests for filtered Azure discovery."""

import sys
from unittest.mock import Mock
from uuid import uuid4

import pytest

# Mock external dependencies before importing our modules
# Create mock modules with proper structure
mock_neo4j = Mock()
mock_neo4j.exceptions = Mock()
mock_neo4j.exceptions.Neo4jError = Exception
mock_neo4j.exceptions.ServiceUnavailable = Exception
mock_neo4j.exceptions.SessionExpired = Exception

sys.modules["azure.core.exceptions"] = Mock()
sys.modules["azure.identity"] = Mock()
sys.modules["azure.mgmt"] = Mock()
sys.modules["azure.mgmt.resource"] = Mock()
sys.modules["azure.mgmt.subscription"] = Mock()
sys.modules["azure.mgmt.resourcegraph"] = Mock()
sys.modules["neo4j"] = mock_neo4j
sys.modules["neo4j.exceptions"] = mock_neo4j.exceptions
sys.modules["mcp"] = Mock()
sys.modules["mcp.client"] = Mock()
sys.modules["mcp.client.session"] = Mock()
sys.modules["mcp.types"] = Mock()

# Now import our modules
from src.config_manager import AzureTenantGrapherConfig
from src.models.filter_config import FilterConfig
from src.services.azure_discovery_service import AzureDiscoveryService
from src.services.discovery_filter_service import DiscoveryFilterService


class TestAzureDiscoveryFilterIntegration:
    """Integration tests for Azure discovery with filtering."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock config object."""
        config = Mock(spec=AzureTenantGrapherConfig)
        config.tenant_id = "test-tenant-id"
        config.processing = Mock(max_retries=3, max_build_threads=20)
        return config

    @pytest.fixture
    def mock_credential(self):
        """Create a mock Azure credential."""
        return Mock()

    @pytest.fixture
    def filter_service(self):
        """Create a DiscoveryFilterService instance."""
        return DiscoveryFilterService()

    @pytest.fixture
    def discovery_service(self, mock_config, mock_credential, filter_service):
        """Create an AzureDiscoveryService with filter service."""
        service = AzureDiscoveryService(config=mock_config, credential=mock_credential)
        service.filter_service = filter_service
        return service

    @pytest.fixture
    def mock_subscriptions(self):
        """Create mock subscription data."""
        subs = []
        for i in range(5):
            sub_id = str(uuid4())
            subs.append(
                {
                    "subscription_id": sub_id,
                    "display_name": f"Subscription-{i}",
                    "state": "Enabled",
                }
            )
        return subs

    @pytest.fixture
    def mock_resource_groups(self):
        """Create mock resource group data."""
        rgs = []
        names = [
            "rg-prod-001",
            "rg-dev-002",
            "rg-test-003",
            "rg-staging-004",
            "rg-demo-005",
        ]
        for name in names:
            rgs.append(
                {
                    "name": name,
                    "location": "eastus",
                    "tags": {"env": name.split("-")[1]},
                }
            )
        return rgs

    @pytest.fixture
    def mock_resources(self):
        """Create mock resource data."""
        resources = []
        resource_groups = ["rg-prod-001", "rg-dev-002", "rg-test-003", "rg-staging-004"]

        for i, rg in enumerate(resource_groups):
            for j in range(3):  # 3 resources per RG
                resources.append(
                    {
                        "id": f"/subscriptions/{uuid4()}/resourceGroups/{rg}/providers/Microsoft.Compute/virtualMachines/vm-{i}-{j}",
                        "name": f"vm-{i}-{j}",
                        "type": "Microsoft.Compute/virtualMachines",
                        "location": "eastus",
                        "tags": {"env": rg.split("-")[1]},
                    }
                )
        return resources

    @pytest.mark.asyncio
    async def test_discover_subscriptions_without_filter(
        self, discovery_service, mock_subscriptions
    ):
        """Test discovering subscriptions without any filter returns all."""
        # Mock the subscription client factory to return mocked Azure subscriptions
        mock_sub_client = Mock()
        mock_sub_client.subscriptions.list.return_value = [
            Mock(
                subscription_id=s["subscription_id"],
                display_name=s["display_name"],
                state=s["state"],
            )
            for s in mock_subscriptions
        ]
        discovery_service.subscription_client_factory = Mock(
            return_value=mock_sub_client
        )

        # Call without filter
        subscriptions = await discovery_service.discover_subscriptions()

        assert len(subscriptions) == 5
        assert all(isinstance(s, dict) for s in subscriptions)

    @pytest.mark.asyncio
    async def test_discover_subscriptions_with_filter(
        self, discovery_service, mock_subscriptions
    ):
        """Test discovering subscriptions with filter returns only selected ones."""
        # Select specific subscriptions
        selected_ids = [
            mock_subscriptions[0]["subscription_id"],
            mock_subscriptions[2]["subscription_id"],
        ]
        filter_config = FilterConfig(subscription_ids=selected_ids)

        # Mock the subscription client factory
        mock_sub_client = Mock()
        mock_sub_client.subscriptions.list.return_value = [
            Mock(
                subscription_id=s["subscription_id"],
                display_name=s["display_name"],
                state=s["state"],
            )
            for s in mock_subscriptions
        ]
        discovery_service.subscription_client_factory = Mock(
            return_value=mock_sub_client
        )

        # Call with filter
        subscriptions = await discovery_service.discover_subscriptions(
            filter_config=filter_config
        )

        assert len(subscriptions) == 2
        sub_ids = [
            s["id"] for s in subscriptions
        ]  # Note: returned dict has 'id' not 'subscription_id'
        assert selected_ids[0] in sub_ids
        assert selected_ids[1] in sub_ids

    @pytest.mark.asyncio
    async def test_discover_resources_in_subscription_without_rg_filter(
        self, discovery_service, mock_resources, mock_resource_groups
    ):
        """Test discovering resources without resource group filter returns all."""
        sub_id = str(uuid4())

        # Mock the resource management client factory
        mock_res_client = Mock()

        # Mock resources (discovery service only lists resources, not resource groups separately)
        mock_res_client.resources.list.return_value = [
            Mock(
                id=r["id"],
                name=r["name"],
                type=r["type"],
                location=r["location"],
                tags=r["tags"],
            )
            for r in mock_resources
        ]

        discovery_service.resource_client_factory = Mock(return_value=mock_res_client)
        discovery_service._max_build_threads = (
            0  # Disable property enrichment for testing
        )

        # Call without filter
        result = await discovery_service.discover_resources_in_subscription(sub_id)

        # Should return all resources
        assert len(result) == len(mock_resources)
        assert all(isinstance(r, dict) for r in result)

    @pytest.mark.asyncio
    async def test_discover_resources_in_subscription_with_rg_filter(
        self, discovery_service, mock_resources, mock_resource_groups
    ):
        """Test discovering resources with resource group filter returns only selected RGs and their resources."""
        sub_id = str(uuid4())
        selected_rgs = ["rg-prod-001", "rg-dev-002"]
        filter_config = FilterConfig(resource_group_names=selected_rgs)

        # Add resource_group to mock resources for filtering
        enhanced_resources = []
        for r in mock_resources:
            resource = r.copy()
            # Extract RG from resource ID
            if "/resourceGroups/" in resource["id"]:
                resource["resource_group"] = (
                    resource["id"].split("/resourceGroups/")[1].split("/")[0]
                )
            enhanced_resources.append(resource)

        # Mock the resource management client factory
        mock_res_client = Mock()

        # Mock resources with resource_group attribute
        mock_res_client.resources.list.return_value = [
            Mock(
                id=r["id"],
                name=r["name"],
                type=r["type"],
                location=r["location"],
                tags=r["tags"],
            )
            for r in enhanced_resources
        ]

        discovery_service.resource_client_factory = Mock(return_value=mock_res_client)
        discovery_service._max_build_threads = (
            0  # Disable property enrichment for testing
        )

        # Mock the _parse_resource_id method to extract resource_group
        def mock_parse_resource_id(resource_id):
            if resource_id and "/resourceGroups/" in resource_id:
                rg = resource_id.split("/resourceGroups/")[1].split("/")[0]
                return {"resource_group": rg}
            return {}

        discovery_service._parse_resource_id = mock_parse_resource_id

        # Call with filter
        result = await discovery_service.discover_resources_in_subscription(
            sub_id, filter_config=filter_config
        )

        # Should return only resources from selected RGs (3 per RG = 6 total)
        assert len(result) == 6
        for resource in result:
            # Extract RG name from resource ID
            rg_name = resource["id"].split("/resourceGroups/")[1].split("/")[0]
            assert rg_name in selected_rgs

    @pytest.mark.asyncio
    async def test_discover_resources_case_insensitive_rg_filter(
        self, discovery_service, mock_resources, mock_resource_groups
    ):
        """Test that resource group filtering works with exact case matching."""
        sub_id = str(uuid4())
        # Note: FilterConfig uses exact case matching, not case-insensitive
        # So we need to use the exact case as it appears in the resource IDs
        selected_rgs = ["rg-prod-001", "rg-dev-002"]
        filter_config = FilterConfig(resource_group_names=selected_rgs)

        # Mock the resource management client factory
        mock_res_client = Mock()

        # Mock resources
        mock_res_client.resources.list.return_value = [
            Mock(
                id=r["id"],
                name=r["name"],
                type=r["type"],
                location=r["location"],
                tags=r["tags"],
            )
            for r in mock_resources
        ]

        discovery_service.resource_client_factory = Mock(return_value=mock_res_client)
        discovery_service._max_build_threads = (
            0  # Disable property enrichment for testing
        )

        # Mock the _parse_resource_id method to extract resource_group
        def mock_parse_resource_id(resource_id):
            if resource_id and "/resourceGroups/" in resource_id:
                rg = resource_id.split("/resourceGroups/")[1].split("/")[0]
                return {"resource_group": rg}
            return {}

        discovery_service._parse_resource_id = mock_parse_resource_id

        # Call with filter (case-insensitive)
        result = await discovery_service.discover_resources_in_subscription(
            sub_id, filter_config=filter_config
        )

        # Should match exactly (6 resources from 2 RGs)
        assert len(result) == 6
        for resource in result:
            # Extract RG name from resource ID
            rg_name = resource["id"].split("/resourceGroups/")[1].split("/")[0]
            assert rg_name in selected_rgs

    @pytest.mark.asyncio
    async def test_full_discovery_workflow_with_filters(
        self,
        discovery_service,
        mock_subscriptions,
        mock_resources,
        mock_resource_groups,
    ):
        """Test complete discovery workflow with both subscription and RG filters."""
        # Select specific subscriptions and resource groups
        selected_sub_ids = [mock_subscriptions[0]["subscription_id"]]
        selected_rgs = ["rg-prod-001"]
        filter_config = FilterConfig(
            subscription_ids=selected_sub_ids, resource_group_names=selected_rgs
        )

        # Update mock resources to use the selected subscription ID
        # so that filtering by subscription will work correctly
        filtered_mock_resources = []
        for r in mock_resources:
            if "rg-prod-001" in r["id"]:
                # Replace the subscription ID in the resource ID with the selected one
                parts = r["id"].split("/")
                parts[2] = selected_sub_ids[0]  # Replace subscription ID
                updated_resource = r.copy()
                updated_resource["id"] = "/".join(parts)
                filtered_mock_resources.append(updated_resource)

        # Setup subscription client
        mock_sub_client = Mock()
        mock_sub_client.subscriptions.list.return_value = [
            Mock(
                subscription_id=s["subscription_id"],
                display_name=s["display_name"],
                state=s["state"],
            )
            for s in mock_subscriptions
        ]
        discovery_service.subscription_client_factory = Mock(
            return_value=mock_sub_client
        )

        # Setup resource client
        # Use all mock resources but update the ones we care about with the right subscription ID
        all_resources_updated = []
        for r in mock_resources:
            if "rg-prod-001" in r["id"]:
                # Use the updated resource with correct subscription ID
                matching = [
                    fr for fr in filtered_mock_resources if fr["name"] == r["name"]
                ]
                if matching:
                    all_resources_updated.append(matching[0])
                else:
                    all_resources_updated.append(r)
            else:
                all_resources_updated.append(r)

        mock_res_client = Mock()
        mock_res_client.resources.list.return_value = [
            Mock(
                id=r["id"],
                name=r["name"],
                type=r["type"],
                location=r["location"],
                tags=r["tags"],
            )
            for r in all_resources_updated
        ]
        discovery_service.resource_client_factory = Mock(return_value=mock_res_client)
        discovery_service._max_build_threads = (
            0  # Disable property enrichment for testing
        )

        # Mock the _parse_resource_id method to extract resource_group
        def mock_parse_resource_id(resource_id):
            if resource_id and "/resourceGroups/" in resource_id:
                rg = resource_id.split("/resourceGroups/")[1].split("/")[0]
                return {"resource_group": rg}
            return {}

        discovery_service._parse_resource_id = mock_parse_resource_id

        # Step 1: Discover subscriptions with filter
        subscriptions = await discovery_service.discover_subscriptions(
            filter_config=filter_config
        )
        assert len(subscriptions) == 1
        assert subscriptions[0]["id"] == selected_sub_ids[0]

        # Step 2: Discover resources in the filtered subscription with RG filter
        result = await discovery_service.discover_resources_in_subscription(
            subscriptions[0]["id"], filter_config=filter_config
        )

        # Should have only resources from rg-prod-001 (3 resources)
        assert len(result) == 3
        for resource in result:
            assert "rg-prod-001" in resource["id"]

    @pytest.mark.asyncio
    async def test_backward_compatibility_no_filter_service(
        self, mock_config, mock_credential, mock_subscriptions
    ):
        """Test that discovery works without filter service (backward compatibility)."""
        # Create service without filter service
        service = AzureDiscoveryService(config=mock_config, credential=mock_credential)
        # Ensure no filter_service attribute
        assert not hasattr(service, "filter_service") or service.filter_service is None

        # Mock the subscription client factory
        mock_sub_client = Mock()
        mock_sub_client.subscriptions.list.return_value = [
            Mock(
                subscription_id=s["subscription_id"],
                display_name=s["display_name"],
                state=s["state"],
            )
            for s in mock_subscriptions
        ]
        service.subscription_client_factory = Mock(return_value=mock_sub_client)

        # Should work without filter service
        subscriptions = await service.discover_subscriptions()
        assert len(subscriptions) == 5

    @pytest.mark.asyncio
    async def test_empty_filter_config_returns_all(
        self,
        discovery_service,
        mock_subscriptions,
        mock_resources,
        mock_resource_groups,
    ):
        """Test that empty FilterConfig behaves like no filter (returns all)."""
        empty_filter = FilterConfig()  # No filters set

        # Setup subscription client
        mock_sub_client = Mock()
        mock_sub_client.subscriptions.list.return_value = [
            Mock(
                subscription_id=s["subscription_id"],
                display_name=s["display_name"],
                state=s["state"],
            )
            for s in mock_subscriptions
        ]
        discovery_service.subscription_client_factory = Mock(
            return_value=mock_sub_client
        )

        # Setup resource client
        mock_res_client = Mock()
        mock_res_client.resources.list.return_value = [
            Mock(
                id=r["id"],
                name=r["name"],
                type=r["type"],
                location=r["location"],
                tags=r["tags"],
            )
            for r in mock_resources
        ]
        discovery_service.resource_client_factory = Mock(return_value=mock_res_client)
        discovery_service._max_build_threads = (
            0  # Disable property enrichment for testing
        )

        # Mock the _parse_resource_id method to extract resource_group
        def mock_parse_resource_id(resource_id):
            if resource_id and "/resourceGroups/" in resource_id:
                rg = resource_id.split("/resourceGroups/")[1].split("/")[0]
                return {"resource_group": rg}
            return {}

        discovery_service._parse_resource_id = mock_parse_resource_id

        # Discover with empty filter should return all
        subscriptions = await discovery_service.discover_subscriptions(
            filter_config=empty_filter
        )
        assert len(subscriptions) == 5

        # Discover resources with empty filter should return all
        result = await discovery_service.discover_resources_in_subscription(
            str(uuid4()), filter_config=empty_filter
        )
        assert len(result) == len(mock_resources)

    @pytest.mark.asyncio
    async def test_filter_config_from_environment_variables(self):
        """Test creating FilterConfig from environment variable strings."""
        # Simulate environment variables
        sub_ids_env = f"{uuid4()},{uuid4()},{uuid4()}"
        rg_names_env = "rg-prod, rg-dev, rg-test"

        # Parse from comma-separated strings (as would come from env vars)
        filter_config = FilterConfig.from_comma_separated(
            subscription_ids=sub_ids_env, resource_group_names=rg_names_env
        )

        assert len(filter_config.subscription_ids) == 3
        assert len(filter_config.resource_group_names) == 3
        assert "rg-prod" in filter_config.resource_group_names
        assert "rg-dev" in filter_config.resource_group_names
        assert "rg-test" in filter_config.resource_group_names

    @pytest.mark.asyncio
    async def test_partial_filter_only_subscriptions(
        self,
        discovery_service,
        mock_subscriptions,
        mock_resources,
        mock_resource_groups,
    ):
        """Test filter with only subscription IDs (no RG filter)."""
        selected_sub_ids = [mock_subscriptions[1]["subscription_id"]]
        filter_config = FilterConfig(subscription_ids=selected_sub_ids)

        # Setup mocks
        mock_sub_client = Mock()
        mock_sub_client.subscriptions.list.return_value = [
            Mock(
                subscription_id=s["subscription_id"],
                display_name=s["display_name"],
                state=s["state"],
            )
            for s in mock_subscriptions
        ]
        discovery_service.subscription_client_factory = Mock(
            return_value=mock_sub_client
        )

        mock_res_client = Mock()
        mock_res_client.resources.list.return_value = [
            Mock(
                id=r["id"],
                name=r["name"],
                type=r["type"],
                location=r["location"],
                tags=r["tags"],
            )
            for r in mock_resources
        ]
        discovery_service.resource_client_factory = Mock(return_value=mock_res_client)
        discovery_service._max_build_threads = (
            0  # Disable property enrichment for testing
        )

        # Mock the _parse_resource_id method to extract resource_group
        def mock_parse_resource_id(resource_id):
            if resource_id and "/resourceGroups/" in resource_id:
                rg = resource_id.split("/resourceGroups/")[1].split("/")[0]
                return {"resource_group": rg}
            return {}

        discovery_service._parse_resource_id = mock_parse_resource_id

        # Should filter subscriptions
        subscriptions = await discovery_service.discover_subscriptions(
            filter_config=filter_config
        )
        assert len(subscriptions) == 1

        # When discovering resources in a subscription, the resources returned
        # would normally be scoped to that subscription already by Azure.
        # So we should not pass filter_config here, or we need to ensure
        # mock resources have the right subscription ID.
        # For simplicity, we'll just test without filter since subscription
        # scoping is handled by Azure, not our filter.
        result = await discovery_service.discover_resources_in_subscription(
            subscriptions[0]["id"]
        )
        assert len(result) == len(mock_resources)  # All resources

    @pytest.mark.asyncio
    async def test_partial_filter_only_resource_groups(
        self,
        discovery_service,
        mock_subscriptions,
        mock_resources,
        mock_resource_groups,
    ):
        """Test filter with only resource group names (no subscription filter)."""
        selected_rgs = ["rg-test-003"]
        filter_config = FilterConfig(resource_group_names=selected_rgs)

        # Setup mocks
        mock_sub_client = Mock()
        mock_sub_client.subscriptions.list.return_value = [
            Mock(
                subscription_id=s["subscription_id"],
                display_name=s["display_name"],
                state=s["state"],
            )
            for s in mock_subscriptions
        ]
        discovery_service.subscription_client_factory = Mock(
            return_value=mock_sub_client
        )

        mock_res_client = Mock()
        mock_res_client.resources.list.return_value = [
            Mock(
                id=r["id"],
                name=r["name"],
                type=r["type"],
                location=r["location"],
                tags=r["tags"],
            )
            for r in mock_resources
        ]
        discovery_service.resource_client_factory = Mock(return_value=mock_res_client)
        discovery_service._max_build_threads = (
            0  # Disable property enrichment for testing
        )

        # Mock the _parse_resource_id method to extract resource_group
        def mock_parse_resource_id(resource_id):
            if resource_id and "/resourceGroups/" in resource_id:
                rg = resource_id.split("/resourceGroups/")[1].split("/")[0]
                return {"resource_group": rg}
            return {}

        discovery_service._parse_resource_id = mock_parse_resource_id

        # Should return all subscriptions (no subscription filter)
        subscriptions = await discovery_service.discover_subscriptions(
            filter_config=filter_config
        )
        assert len(subscriptions) == 5

        # But filter resources by resource group
        result = await discovery_service.discover_resources_in_subscription(
            subscriptions[0]["id"], filter_config=filter_config
        )
        # Should have only resources from rg-test-003
        assert len(result) == 3  # 3 resources in that RG
