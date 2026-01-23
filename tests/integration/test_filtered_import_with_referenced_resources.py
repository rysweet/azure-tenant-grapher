"""Integration tests for filtered imports with referenced resource inclusion.

Tests end-to-end flow of filtered import with automatic inclusion of:
- User-assigned managed identities from different resource groups
- System-assigned managed identity details
- RBAC principals (users, groups, service principals)

Issue #228: Subscription and Resource Group Filtering with Referenced Resources
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.azure_tenant_grapher import AzureTenantGrapher
from src.config_manager import AzureTenantGrapherConfig
from src.models.filter_config import FilterConfig


@pytest.fixture
def mock_config():
    """Create a mock AzureTenantGrapher config."""
    config = MagicMock(spec=AzureTenantGrapherConfig)
    config.tenant_id = str(uuid4())
    config.processing.auto_start_container = False
    config.processing.enable_aad_import = True
    config.processing.resource_limit = None
    config.azure_openai.is_configured.return_value = False
    return config


@pytest.fixture
def sample_filtered_resources():
    """Sample resources from rg1 subscription."""
    sub_id = str(uuid4())
    return [
        {
            "id": f"/subscriptions/{sub_id}/resourceGroups/rg1/providers/Microsoft.Web/sites/webapp1",
            "name": "webapp1",
            "type": "Microsoft.Web/sites",
            "subscription_id": sub_id,
            "resource_group": "rg1",
            "location": "eastus",
            "identity": {
                "type": "UserAssigned",
                "userAssignedIdentities": {
                    f"/subscriptions/{sub_id}/resourceGroups/shared-identities/providers/Microsoft.ManagedIdentity/userAssignedIdentities/webapp-identity": {
                        "principalId": "user-principal-001",
                        "clientId": "client-001",
                    }
                },
            },
            "properties": {
                "roleAssignments": [
                    {
                        "principalId": "user-rbac-001",
                        "principalType": "User",
                        "roleDefinitionId": f"/subscriptions/{sub_id}/providers/Microsoft.Authorization/roleDefinitions/role-contributor",
                    }
                ]
            },
        }
    ]


@pytest.fixture
def sample_user_assigned_identity():
    """Sample user-assigned identity from different RG."""
    sub_id = str(uuid4())
    return {
        "id": f"/subscriptions/{sub_id}/resourceGroups/shared-identities/providers/Microsoft.ManagedIdentity/userAssignedIdentities/webapp-identity",
        "name": "webapp-identity",
        "type": "Microsoft.ManagedIdentity/userAssignedIdentities",
        "subscription_id": sub_id,
        "resource_group": "shared-identities",
        "location": "eastus",
        "properties": {
            "principalId": "user-principal-001",
            "clientId": "client-001",
            "tenantId": "tenant-001",
        },
    }


@pytest.mark.asyncio
@pytest.mark.integration
class TestFilteredImportWithReferencedResources:
    """Integration tests for complete filtered import flow."""

    async def test_filtered_build_includes_cross_rg_identity(
        self, mock_config, sample_filtered_resources, sample_user_assigned_identity
    ):
        """Test that filtered build includes user-assigned identity from different RG."""
        # Setup mocks
        with patch(
            "src.azure_tenant_grapher.Neo4jSessionManager"
        ) as mock_session_mgr, patch(
            "src.azure_tenant_grapher.AzureDiscoveryService"
        ) as mock_discovery, patch(
            "src.azure_tenant_grapher.ResourceProcessingService"
        ) as mock_processing, patch(
            "src.azure_tenant_grapher.TenantSpecificationService"
        ), patch("src.azure_tenant_grapher.AADGraphService") as mock_aad:
            # Mock discovery service
            mock_discovery_instance = AsyncMock()
            mock_discovery.return_value = mock_discovery_instance
            mock_discovery_instance.discover_subscriptions.return_value = [
                {"id": mock_config.tenant_id, "name": "Test Subscription"}
            ]
            mock_discovery_instance.discover_resources_in_subscription.return_value = (
                sample_filtered_resources
            )

            # Mock AAD service
            mock_aad_instance = AsyncMock()
            mock_aad.return_value = mock_aad_instance
            mock_aad_instance.get_service_principals.return_value = []
            mock_aad_instance.get_users_by_ids.return_value = [
                {
                    "id": "user-rbac-001",
                    "displayName": "Test User",
                    "userPrincipalName": "test@contoso.com",
                }
            ]
            mock_aad_instance.get_groups_by_ids.return_value = []
            mock_aad_instance.get_service_principals_by_ids.return_value = []

            # Mock processing service
            mock_processing_instance = AsyncMock()
            mock_processing.return_value = mock_processing_instance
            mock_processing_instance.process_resources.return_value = None

            # Create grapher
            grapher = AzureTenantGrapher(mock_config)

            # Create filter config for rg1 only
            filter_config = FilterConfig(
                subscription_ids=[mock_config.tenant_id],
                resource_group_names=["rg1"],
                include_referenced_resources=True,
            )

            # Mock ReferencedResourceCollector to return user-assigned identity
            with patch(
                "src.azure_tenant_grapher.ReferencedResourceCollector"
            ) as mock_collector_class:
                mock_collector = AsyncMock()
                mock_collector_class.return_value = mock_collector
                mock_collector.collect_referenced_resources.return_value = [
                    sample_user_assigned_identity
                ]

                # Execute build
                result = await grapher.build_graph(filter_config=filter_config)

                # Verify ReferencedResourceCollector was called
                mock_collector.collect_referenced_resources.assert_called_once()
                call_args = mock_collector.collect_referenced_resources.call_args
                assert call_args[1]["filter_config"] == filter_config

                # Verify resources were processed (including referenced identity)
                mock_processing_instance.process_resources.assert_called_once()
                processed_resources = (
                    mock_processing_instance.process_resources.call_args[0][0]
                )

                # Should include original filtered resource + referenced identity
                assert len(processed_resources) >= 2

    async def test_filtered_build_includes_rbac_principals(
        self, mock_config, sample_filtered_resources
    ):
        """Test that filtered build includes RBAC principals from AAD."""
        with patch("src.azure_tenant_grapher.Neo4jSessionManager"), patch(
            "src.azure_tenant_grapher.AzureDiscoveryService"
        ) as mock_discovery, patch(
            "src.azure_tenant_grapher.ResourceProcessingService"
        ) as mock_processing, patch(
            "src.azure_tenant_grapher.TenantSpecificationService"
        ), patch("src.azure_tenant_grapher.AADGraphService") as mock_aad:
            # Mock discovery
            mock_discovery_instance = AsyncMock()
            mock_discovery.return_value = mock_discovery_instance
            mock_discovery_instance.discover_subscriptions.return_value = [
                {"id": mock_config.tenant_id}
            ]
            mock_discovery_instance.discover_resources_in_subscription.return_value = (
                sample_filtered_resources
            )

            # Mock AAD to return RBAC user
            mock_aad_instance = AsyncMock()
            mock_aad.return_value = mock_aad_instance
            mock_aad_instance.get_service_principals.return_value = []
            mock_aad_instance.get_users_by_ids.return_value = [
                {
                    "id": "user-rbac-001",
                    "displayName": "RBAC User",
                    "userPrincipalName": "rbac@contoso.com",
                }
            ]
            mock_aad_instance.get_groups_by_ids.return_value = []
            mock_aad_instance.get_service_principals_by_ids.return_value = []

            # Mock processing
            mock_processing_instance = AsyncMock()
            mock_processing.return_value = mock_processing_instance
            mock_processing_instance.process_resources.return_value = None

            grapher = AzureTenantGrapher(mock_config)

            filter_config = FilterConfig(
                resource_group_names=["rg1"], include_referenced_resources=True
            )

            # Mock collector to return RBAC principal as Graph resource
            with patch(
                "src.azure_tenant_grapher.ReferencedResourceCollector"
            ) as mock_collector_class:
                mock_collector = AsyncMock()
                mock_collector_class.return_value = mock_collector
                mock_collector.collect_referenced_resources.return_value = [
                    {
                        "id": "/users/user-rbac-001",
                        "name": "RBAC User",
                        "type": "Microsoft.Graph/users",
                        "properties": {
                            "displayName": "RBAC User",
                            "userPrincipalName": "rbac@contoso.com",
                        },
                    }
                ]

                result = await grapher.build_graph(filter_config=filter_config)

                # Verify RBAC principal was included
                mock_collector.collect_referenced_resources.assert_called_once()

    async def test_filtered_build_with_no_include_references_flag(
        self, mock_config, sample_filtered_resources
    ):
        """Test that referenced resources are NOT included when flag is False."""
        with patch("src.azure_tenant_grapher.Neo4jSessionManager"), patch(
            "src.azure_tenant_grapher.AzureDiscoveryService"
        ) as mock_discovery, patch(
            "src.azure_tenant_grapher.ResourceProcessingService"
        ) as mock_processing, patch(
            "src.azure_tenant_grapher.TenantSpecificationService"
        ), patch("src.azure_tenant_grapher.AADGraphService"):
            mock_discovery_instance = AsyncMock()
            mock_discovery.return_value = mock_discovery_instance
            mock_discovery_instance.discover_subscriptions.return_value = [
                {"id": mock_config.tenant_id}
            ]
            mock_discovery_instance.discover_resources_in_subscription.return_value = (
                sample_filtered_resources
            )

            mock_processing_instance = AsyncMock()
            mock_processing.return_value = mock_processing_instance
            mock_processing_instance.process_resources.return_value = None

            grapher = AzureTenantGrapher(mock_config)

            filter_config = FilterConfig(
                resource_group_names=["rg1"],
                include_referenced_resources=False,  # Disabled
            )

            with patch(
                "src.azure_tenant_grapher.ReferencedResourceCollector"
            ) as mock_collector_class:
                mock_collector = AsyncMock()
                mock_collector_class.return_value = mock_collector

                result = await grapher.build_graph(filter_config=filter_config)

                # ReferencedResourceCollector should NOT be created or called
                mock_collector_class.assert_not_called()
                mock_collector.collect_referenced_resources.assert_not_called()

    async def test_unfiltered_build_unchanged(self, mock_config):
        """Test that unfiltered builds work as before (no filter_config)."""
        with patch("src.azure_tenant_grapher.Neo4jSessionManager"), patch(
            "src.azure_tenant_grapher.AzureDiscoveryService"
        ) as mock_discovery, patch(
            "src.azure_tenant_grapher.ResourceProcessingService"
        ) as mock_processing, patch(
            "src.azure_tenant_grapher.TenantSpecificationService"
        ), patch("src.azure_tenant_grapher.AADGraphService") as mock_aad:
            mock_discovery_instance = AsyncMock()
            mock_discovery.return_value = mock_discovery_instance
            mock_discovery_instance.discover_subscriptions.return_value = [
                {"id": mock_config.tenant_id}
            ]
            mock_discovery_instance.discover_resources_in_subscription.return_value = [
                {
                    "id": f"/subscriptions/{mock_config.tenant_id}/resourceGroups/any-rg/providers/Microsoft.Compute/virtualMachines/vm1",
                    "name": "vm1",
                    "type": "Microsoft.Compute/virtualMachines",
                }
            ]

            mock_aad_instance = AsyncMock()
            mock_aad.return_value = mock_aad_instance
            mock_aad_instance.get_service_principals.return_value = []

            mock_processing_instance = AsyncMock()
            mock_processing.return_value = mock_processing_instance
            mock_processing_instance.process_resources.return_value = None

            grapher = AzureTenantGrapher(mock_config)

            with patch(
                "src.azure_tenant_grapher.ReferencedResourceCollector"
            ) as mock_collector_class:
                # No filter_config = unfiltered build
                result = await grapher.build_graph(filter_config=None)

                # ReferencedResourceCollector should NOT be used for unfiltered builds
                mock_collector_class.assert_not_called()

                # Regular processing should occur
                mock_processing_instance.process_resources.assert_called_once()

    async def test_filtered_build_empty_filter_no_referenced_collection(
        self, mock_config
    ):
        """Test that empty FilterConfig (no filters) skips referenced resource collection."""
        with patch("src.azure_tenant_grapher.Neo4jSessionManager"), patch(
            "src.azure_tenant_grapher.AzureDiscoveryService"
        ) as mock_discovery, patch(
            "src.azure_tenant_grapher.ResourceProcessingService"
        ) as mock_processing, patch(
            "src.azure_tenant_grapher.TenantSpecificationService"
        ), patch("src.azure_tenant_grapher.AADGraphService") as mock_aad:
            mock_discovery_instance = AsyncMock()
            mock_discovery.return_value = mock_discovery_instance
            mock_discovery_instance.discover_subscriptions.return_value = [
                {"id": mock_config.tenant_id}
            ]
            mock_discovery_instance.discover_resources_in_subscription.return_value = []

            mock_aad_instance = AsyncMock()
            mock_aad.return_value = mock_aad_instance
            mock_aad_instance.get_service_principals.return_value = []

            mock_processing_instance = AsyncMock()
            mock_processing.return_value = mock_processing_instance
            mock_processing_instance.process_resources.return_value = None

            grapher = AzureTenantGrapher(mock_config)

            # Empty FilterConfig - no actual filters
            filter_config = FilterConfig()

            with patch(
                "src.azure_tenant_grapher.ReferencedResourceCollector"
            ) as mock_collector_class:
                result = await grapher.build_graph(filter_config=filter_config)

                # Should not collect references when no filters are active
                mock_collector_class.assert_not_called()
