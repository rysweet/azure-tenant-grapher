"""Tests for ReferencedResourceCollector service.

Tests automatic inclusion of referenced resources (managed identities, RBAC principals)
when using filtered imports.

Issue #228: Subscription and Resource Group Filtering
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.filter_config import FilterConfig
from src.services.referenced_resource_collector import ReferencedResourceCollector


@pytest.fixture
def mock_discovery_service():
    """Mock AzureDiscoveryService."""
    service = AsyncMock()
    return service


@pytest.fixture
def mock_identity_resolver():
    """Mock ManagedIdentityResolver."""
    resolver = MagicMock()
    resolver.resolve_identities.return_value = {}
    return resolver


@pytest.fixture
def mock_aad_graph_service():
    """Mock AADGraphService."""
    service = AsyncMock()
    service.get_users_by_ids.return_value = []
    service.get_groups_by_ids.return_value = []
    service.get_service_principals_by_ids.return_value = []
    return service


@pytest.fixture
def sample_resources_with_identities():
    """Sample Azure resources with various identity configurations."""
    return [
        # VM with system-assigned identity
        {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "resource_group": "rg1",
            "identity": {
                "type": "SystemAssigned",
                "principalId": "sys-principal-001",
                "tenantId": "tenant-001",
            },
        },
        # Web App with user-assigned identity
        {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Web/sites/webapp1",
            "name": "webapp1",
            "type": "Microsoft.Web/sites",
            "resource_group": "rg1",
            "identity": {
                "type": "UserAssigned",
                "userAssignedIdentities": {
                    "/subscriptions/sub1/resourceGroups/shared-identities/providers/Microsoft.ManagedIdentity/userAssignedIdentities/webapp-identity": {
                        "principalId": "user-principal-001",
                        "clientId": "client-001",
                    }
                },
            },
        },
        # AKS with both system and user-assigned
        {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.ContainerService/managedClusters/aks1",
            "name": "aks1",
            "type": "Microsoft.ContainerService/managedClusters",
            "resource_group": "rg1",
            "identity": {
                "type": "SystemAssigned, UserAssigned",
                "principalId": "sys-principal-002",
                "tenantId": "tenant-001",
                "userAssignedIdentities": {
                    "/subscriptions/sub1/resourceGroups/shared-identities/providers/Microsoft.ManagedIdentity/userAssignedIdentities/aks-identity": {
                        "principalId": "user-principal-002",
                        "clientId": "client-002",
                    }
                },
            },
        },
    ]


@pytest.fixture
def sample_resources_with_rbac():
    """Sample Azure resources with RBAC role assignments."""
    return [
        # Storage Account with RBAC assignments
        {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1",
            "name": "storage1",
            "type": "Microsoft.Storage/storageAccounts",
            "resource_group": "rg1",
            "properties": {
                "roleAssignments": [
                    {
                        "principalId": "user-principal-rbac-001",
                        "principalType": "User",
                        "roleDefinitionId": "/subscriptions/sub1/providers/Microsoft.Authorization/roleDefinitions/role-contributor",
                    },
                    {
                        "principalId": "group-principal-rbac-001",
                        "principalType": "Group",
                        "roleDefinitionId": "/subscriptions/sub1/providers/Microsoft.Authorization/roleDefinitions/role-reader",
                    },
                    {
                        "principalId": "sp-principal-rbac-001",
                        "principalType": "ServicePrincipal",
                        "roleDefinitionId": "/subscriptions/sub1/providers/Microsoft.Authorization/roleDefinitions/role-owner",
                    },
                ]
            },
        },
        # Key Vault with different RBAC format
        {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1",
            "name": "kv1",
            "type": "Microsoft.KeyVault/vaults",
            "resource_group": "rg1",
            "properties": {
                "accessPolicies": [
                    {
                        "objectId": "user-principal-rbac-002",
                        "objectType": "User",
                        "permissions": {"keys": ["get", "list"], "secrets": ["get"]},
                    },
                    {
                        "objectId": "sp-principal-rbac-002",
                        "objectType": "ServicePrincipal",
                        "permissions": {"secrets": ["all"]},
                    },
                ]
            },
        },
    ]


class TestReferencedResourceCollectorInit:
    """Tests for ReferencedResourceCollector initialization."""

    def test_init_with_all_services(
        self, mock_discovery_service, mock_identity_resolver, mock_aad_graph_service
    ):
        """Test collector initialization with all services."""
        collector = ReferencedResourceCollector(
            discovery_service=mock_discovery_service,
            identity_resolver=mock_identity_resolver,
            aad_graph_service=mock_aad_graph_service,
        )

        assert collector.discovery_service == mock_discovery_service
        assert collector.identity_resolver == mock_identity_resolver
        assert collector.aad_graph_service == mock_aad_graph_service

    def test_init_without_aad_service(
        self, mock_discovery_service, mock_identity_resolver
    ):
        """Test collector initialization without AAD service (RBAC disabled)."""
        collector = ReferencedResourceCollector(
            discovery_service=mock_discovery_service,
            identity_resolver=mock_identity_resolver,
            aad_graph_service=None,
        )

        assert collector.discovery_service == mock_discovery_service
        assert collector.identity_resolver == mock_identity_resolver
        assert collector.aad_graph_service is None


class TestExtractIdentityReferences:
    """Tests for identity reference extraction."""

    def test_extract_system_assigned_identity_references(
        self,
        mock_discovery_service,
        mock_identity_resolver,
        sample_resources_with_identities,
    ):
        """Test extraction of system-assigned identity principal IDs."""
        collector = ReferencedResourceCollector(
            discovery_service=mock_discovery_service,
            identity_resolver=mock_identity_resolver,
        )

        # Extract from first resource (VM with system-assigned identity)
        refs = collector._extract_identity_references(
            [sample_resources_with_identities[0]]
        )

        assert "sys-principal-001" in refs
        assert len(refs) == 1

    def test_extract_user_assigned_identity_references(
        self,
        mock_discovery_service,
        mock_identity_resolver,
        sample_resources_with_identities,
    ):
        """Test extraction of user-assigned identity resource IDs."""
        collector = ReferencedResourceCollector(
            discovery_service=mock_discovery_service,
            identity_resolver=mock_identity_resolver,
        )

        # Extract from second resource (Web App with user-assigned identity)
        refs = collector._extract_identity_references(
            [sample_resources_with_identities[1]]
        )

        expected_id = "/subscriptions/sub1/resourceGroups/shared-identities/providers/Microsoft.ManagedIdentity/userAssignedIdentities/webapp-identity"
        assert expected_id in refs
        assert len(refs) == 1

    def test_extract_combined_identity_references(
        self,
        mock_discovery_service,
        mock_identity_resolver,
        sample_resources_with_identities,
    ):
        """Test extraction of both system and user-assigned identities."""
        collector = ReferencedResourceCollector(
            discovery_service=mock_discovery_service,
            identity_resolver=mock_identity_resolver,
        )

        # Extract from third resource (AKS with both identity types)
        refs = collector._extract_identity_references(
            [sample_resources_with_identities[2]]
        )

        assert "sys-principal-002" in refs  # System-assigned
        expected_user_id = "/subscriptions/sub1/resourceGroups/shared-identities/providers/Microsoft.ManagedIdentity/userAssignedIdentities/aks-identity"
        assert expected_user_id in refs  # User-assigned
        assert len(refs) == 2

    def test_extract_identity_references_from_multiple_resources(
        self,
        mock_discovery_service,
        mock_identity_resolver,
        sample_resources_with_identities,
    ):
        """Test extraction from multiple resources returns unique set."""
        collector = ReferencedResourceCollector(
            discovery_service=mock_discovery_service,
            identity_resolver=mock_identity_resolver,
        )

        refs = collector._extract_identity_references(sample_resources_with_identities)

        # Should have 4 unique identity references (2 system + 2 user-assigned)
        assert len(refs) == 4
        assert "sys-principal-001" in refs
        assert "sys-principal-002" in refs

    def test_extract_identity_references_no_identities(
        self, mock_discovery_service, mock_identity_resolver
    ):
        """Test extraction returns empty set when no identities present."""
        collector = ReferencedResourceCollector(
            discovery_service=mock_discovery_service,
            identity_resolver=mock_identity_resolver,
        )

        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1",
                "name": "vnet1",
                "type": "Microsoft.Network/virtualNetworks",
                "resource_group": "rg1",
                # No identity field
            }
        ]

        refs = collector._extract_identity_references(resources)
        assert len(refs) == 0


class TestExtractRBACPrincipalIds:
    """Tests for RBAC principal ID extraction."""

    def test_extract_rbac_from_role_assignments(
        self, mock_discovery_service, mock_identity_resolver, sample_resources_with_rbac
    ):
        """Test extraction of RBAC principals from roleAssignments."""
        collector = ReferencedResourceCollector(
            discovery_service=mock_discovery_service,
            identity_resolver=mock_identity_resolver,
        )

        principal_ids = collector._extract_rbac_principal_ids(
            [sample_resources_with_rbac[0]]
        )

        assert "user-principal-rbac-001" in principal_ids["users"]
        assert "group-principal-rbac-001" in principal_ids["groups"]
        assert "sp-principal-rbac-001" in principal_ids["service_principals"]
        assert len(principal_ids["users"]) == 1
        assert len(principal_ids["groups"]) == 1
        assert len(principal_ids["service_principals"]) == 1

    def test_extract_rbac_from_access_policies(
        self, mock_discovery_service, mock_identity_resolver, sample_resources_with_rbac
    ):
        """Test extraction of RBAC principals from accessPolicies (KeyVault format)."""
        collector = ReferencedResourceCollector(
            discovery_service=mock_discovery_service,
            identity_resolver=mock_identity_resolver,
        )

        principal_ids = collector._extract_rbac_principal_ids(
            [sample_resources_with_rbac[1]]
        )

        assert "user-principal-rbac-002" in principal_ids["users"]
        assert "sp-principal-rbac-002" in principal_ids["service_principals"]
        assert len(principal_ids["users"]) == 1
        assert len(principal_ids["service_principals"]) == 1

    def test_extract_rbac_from_multiple_resources(
        self, mock_discovery_service, mock_identity_resolver, sample_resources_with_rbac
    ):
        """Test extraction from multiple resources with different RBAC formats."""
        collector = ReferencedResourceCollector(
            discovery_service=mock_discovery_service,
            identity_resolver=mock_identity_resolver,
        )

        principal_ids = collector._extract_rbac_principal_ids(
            sample_resources_with_rbac
        )

        # Should have unique principals from both resources
        assert len(principal_ids["users"]) == 2  # user-001, user-002
        assert len(principal_ids["groups"]) == 1  # group-001
        assert len(principal_ids["service_principals"]) == 2  # sp-001, sp-002

    def test_extract_rbac_no_assignments(
        self, mock_discovery_service, mock_identity_resolver
    ):
        """Test extraction returns empty sets when no RBAC assignments present."""
        collector = ReferencedResourceCollector(
            discovery_service=mock_discovery_service,
            identity_resolver=mock_identity_resolver,
        )

        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1",
                "name": "vnet1",
                "type": "Microsoft.Network/virtualNetworks",
                "resource_group": "rg1",
                "properties": {},
            }
        ]

        principal_ids = collector._extract_rbac_principal_ids(resources)

        assert len(principal_ids["users"]) == 0
        assert len(principal_ids["groups"]) == 0
        assert len(principal_ids["service_principals"]) == 0


class TestFetchUserAssignedIdentities:
    """Tests for fetching user-assigned managed identities."""

    @pytest.mark.asyncio
    async def test_fetch_user_assigned_identities_from_different_rg(
        self, mock_discovery_service, mock_identity_resolver
    ):
        """Test fetching user-assigned identities from different resource groups."""
        # Mock discovery service to return user-assigned identity resource
        mock_identity_resource = {
            "id": "/subscriptions/sub1/resourceGroups/shared-identities/providers/Microsoft.ManagedIdentity/userAssignedIdentities/webapp-identity",
            "name": "webapp-identity",
            "type": "Microsoft.ManagedIdentity/userAssignedIdentities",
            "location": "eastus",
            "resource_group": "shared-identities",
            "properties": {
                "principalId": "user-principal-001",
                "clientId": "client-001",
                "tenantId": "tenant-001",
            },
        }
        mock_discovery_service.discover_resources_in_subscription.return_value = [
            mock_identity_resource
        ]

        collector = ReferencedResourceCollector(
            discovery_service=mock_discovery_service,
            identity_resolver=mock_identity_resolver,
        )

        filter_config = FilterConfig(
            subscription_ids=["sub1"],
            resource_group_names=[
                "rg1"
            ],  # Filtered to rg1, but identity is in shared-identities
        )

        identity_ids = {
            "/subscriptions/sub1/resourceGroups/shared-identities/providers/Microsoft.ManagedIdentity/userAssignedIdentities/webapp-identity"
        }

        result = await collector._fetch_user_assigned_identities(
            identity_ids, filter_config
        )

        assert len(result) == 1
        assert result[0]["id"] == mock_identity_resource["id"]
        assert result[0]["resource_group"] == "shared-identities"

    @pytest.mark.asyncio
    async def test_fetch_user_assigned_identities_handles_missing(
        self, mock_discovery_service, mock_identity_resolver
    ):
        """Test graceful handling when user-assigned identity cannot be fetched."""
        # Mock discovery service to return empty list (identity not found)
        mock_discovery_service.discover_resources_in_subscription.return_value = []

        collector = ReferencedResourceCollector(
            discovery_service=mock_discovery_service,
            identity_resolver=mock_identity_resolver,
        )

        filter_config = FilterConfig(subscription_ids=["sub1"])
        identity_ids = {
            "/subscriptions/sub1/resourceGroups/missing-rg/providers/Microsoft.ManagedIdentity/userAssignedIdentities/missing-identity"
        }

        result = await collector._fetch_user_assigned_identities(
            identity_ids, filter_config
        )

        # Should return empty list and log warning (checked in logs)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_fetch_user_assigned_identities_cross_subscription(
        self, mock_discovery_service, mock_identity_resolver
    ):
        """Test fetching user-assigned identities from subscriptions outside filter."""
        # Identity in sub2, but filter is for sub1
        mock_identity_resource = {
            "id": "/subscriptions/sub2/resourceGroups/shared-identities/providers/Microsoft.ManagedIdentity/userAssignedIdentities/cross-sub-identity",
            "name": "cross-sub-identity",
            "type": "Microsoft.ManagedIdentity/userAssignedIdentities",
            "location": "eastus",
            "resource_group": "shared-identities",
            "properties": {
                "principalId": "user-principal-cross",
                "clientId": "client-cross",
                "tenantId": "tenant-001",
            },
        }
        mock_discovery_service.discover_resources_in_subscription.return_value = [
            mock_identity_resource
        ]

        collector = ReferencedResourceCollector(
            discovery_service=mock_discovery_service,
            identity_resolver=mock_identity_resolver,
        )

        filter_config = FilterConfig(subscription_ids=["sub1"])
        identity_ids = {
            "/subscriptions/sub2/resourceGroups/shared-identities/providers/Microsoft.ManagedIdentity/userAssignedIdentities/cross-sub-identity"
        }

        result = await collector._fetch_user_assigned_identities(
            identity_ids, filter_config
        )

        # Should fetch despite being outside subscription filter
        assert len(result) == 1
        assert result[0]["id"] == mock_identity_resource["id"]


class TestFetchRBACPrincipals:
    """Tests for fetching RBAC principals from AAD."""

    @pytest.mark.asyncio
    async def test_fetch_rbac_principals_users(
        self, mock_discovery_service, mock_identity_resolver, mock_aad_graph_service
    ):
        """Test fetching users from AAD Graph API."""
        mock_users = [
            {
                "id": "user-principal-rbac-001",
                "displayName": "John Doe",
                "userPrincipalName": "john@contoso.com",
                "mail": "john@contoso.com",
            }
        ]
        mock_aad_graph_service.get_users_by_ids.return_value = mock_users

        collector = ReferencedResourceCollector(
            discovery_service=mock_discovery_service,
            identity_resolver=mock_identity_resolver,
            aad_graph_service=mock_aad_graph_service,
        )

        principal_ids = {
            "users": {"user-principal-rbac-001"},
            "groups": set(),
            "service_principals": set(),
        }

        result = await collector._fetch_rbac_principals(principal_ids)

        assert len(result) == 1
        assert result[0]["id"] == "/users/user-principal-rbac-001"
        assert result[0]["type"] == "Microsoft.Graph/users"
        assert result[0]["name"] == "John Doe"

    @pytest.mark.asyncio
    async def test_fetch_rbac_principals_groups(
        self, mock_discovery_service, mock_identity_resolver, mock_aad_graph_service
    ):
        """Test fetching groups from AAD Graph API."""
        mock_groups = [
            {
                "id": "group-principal-rbac-001",
                "displayName": "Developers",
                "mailEnabled": True,
                "securityEnabled": True,
            }
        ]
        mock_aad_graph_service.get_groups_by_ids.return_value = mock_groups

        collector = ReferencedResourceCollector(
            discovery_service=mock_discovery_service,
            identity_resolver=mock_identity_resolver,
            aad_graph_service=mock_aad_graph_service,
        )

        principal_ids = {
            "users": set(),
            "groups": {"group-principal-rbac-001"},
            "service_principals": set(),
        }

        result = await collector._fetch_rbac_principals(principal_ids)

        assert len(result) == 1
        assert result[0]["id"] == "/groups/group-principal-rbac-001"
        assert result[0]["type"] == "Microsoft.Graph/groups"
        assert result[0]["name"] == "Developers"

    @pytest.mark.asyncio
    async def test_fetch_rbac_principals_service_principals(
        self, mock_discovery_service, mock_identity_resolver, mock_aad_graph_service
    ):
        """Test fetching service principals from AAD Graph API."""
        mock_sps = [
            {
                "id": "sp-principal-rbac-001",
                "displayName": "MyApp Service Principal",
                "appId": "app-id-001",
                "servicePrincipalType": "Application",
            }
        ]
        mock_aad_graph_service.get_service_principals_by_ids.return_value = mock_sps

        collector = ReferencedResourceCollector(
            discovery_service=mock_discovery_service,
            identity_resolver=mock_identity_resolver,
            aad_graph_service=mock_aad_graph_service,
        )

        principal_ids = {
            "users": set(),
            "groups": set(),
            "service_principals": {"sp-principal-rbac-001"},
        }

        result = await collector._fetch_rbac_principals(principal_ids)

        assert len(result) == 1
        assert result[0]["id"] == "/servicePrincipals/sp-principal-rbac-001"
        assert result[0]["type"] == "Microsoft.Graph/servicePrincipals"
        assert result[0]["name"] == "MyApp Service Principal"

    @pytest.mark.asyncio
    async def test_fetch_rbac_principals_all_types(
        self, mock_discovery_service, mock_identity_resolver, mock_aad_graph_service
    ):
        """Test fetching all principal types in single call."""
        mock_aad_graph_service.get_users_by_ids.return_value = [
            {"id": "user-001", "displayName": "User One"}
        ]
        mock_aad_graph_service.get_groups_by_ids.return_value = [
            {"id": "group-001", "displayName": "Group One"}
        ]
        mock_aad_graph_service.get_service_principals_by_ids.return_value = [
            {"id": "sp-001", "displayName": "SP One"}
        ]

        collector = ReferencedResourceCollector(
            discovery_service=mock_discovery_service,
            identity_resolver=mock_identity_resolver,
            aad_graph_service=mock_aad_graph_service,
        )

        principal_ids = {
            "users": {"user-001"},
            "groups": {"group-001"},
            "service_principals": {"sp-001"},
        }

        result = await collector._fetch_rbac_principals(principal_ids)

        assert len(result) == 3
        types = {r["type"] for r in result}
        assert "Microsoft.Graph/users" in types
        assert "Microsoft.Graph/groups" in types
        assert "Microsoft.Graph/servicePrincipals" in types

    @pytest.mark.asyncio
    async def test_fetch_rbac_principals_without_aad_service(
        self, mock_discovery_service, mock_identity_resolver
    ):
        """Test RBAC principal fetching when AAD service is not available."""
        collector = ReferencedResourceCollector(
            discovery_service=mock_discovery_service,
            identity_resolver=mock_identity_resolver,
            aad_graph_service=None,  # No AAD service
        )

        principal_ids = {
            "users": {"user-001"},
            "groups": {"group-001"},
            "service_principals": {"sp-001"},
        }

        result = await collector._fetch_rbac_principals(principal_ids)

        # Should return empty list when AAD service unavailable
        assert len(result) == 0


class TestCollectReferencedResources:
    """Tests for complete referenced resource collection flow."""

    @pytest.mark.asyncio
    async def test_collect_referenced_resources_full_flow(
        self,
        mock_discovery_service,
        mock_identity_resolver,
        mock_aad_graph_service,
        sample_resources_with_identities,
        sample_resources_with_rbac,
    ):
        """Test complete flow: extract + fetch identities + fetch RBAC principals."""
        # Setup mocks
        mock_identity_resource = {
            "id": "/subscriptions/sub1/resourceGroups/shared-identities/providers/Microsoft.ManagedIdentity/userAssignedIdentities/webapp-identity",
            "name": "webapp-identity",
            "type": "Microsoft.ManagedIdentity/userAssignedIdentities",
            "resource_group": "shared-identities",
        }
        mock_discovery_service.discover_resources_in_subscription.return_value = [
            mock_identity_resource
        ]

        mock_aad_graph_service.get_users_by_ids.return_value = [
            {"id": "user-rbac-001", "displayName": "User"}
        ]
        mock_aad_graph_service.get_groups_by_ids.return_value = [
            {"id": "group-rbac-001", "displayName": "Group"}
        ]
        mock_aad_graph_service.get_service_principals_by_ids.return_value = [
            {"id": "sp-rbac-001", "displayName": "SP"}
        ]

        collector = ReferencedResourceCollector(
            discovery_service=mock_discovery_service,
            identity_resolver=mock_identity_resolver,
            aad_graph_service=mock_aad_graph_service,
        )

        filter_config = FilterConfig(
            subscription_ids=["sub1"],
            resource_group_names=["rg1"],
            include_referenced_resources=True,
        )

        # Combine resources with identities and RBAC
        filtered_resources = (
            sample_resources_with_identities + sample_resources_with_rbac
        )

        result = await collector.collect_referenced_resources(
            filtered_resources, filter_config
        )

        # Should return user-assigned identity + 3 RBAC principals
        assert len(result) > 0
        types = {r.get("type") for r in result}
        assert (
            "Microsoft.ManagedIdentity/userAssignedIdentities" in types
            or "Microsoft.Graph/users" in types
        )

    @pytest.mark.asyncio
    async def test_collect_when_include_flag_false(
        self,
        mock_discovery_service,
        mock_identity_resolver,
        mock_aad_graph_service,
        sample_resources_with_identities,
    ):
        """Test collection returns empty when include_referenced_resources is False."""
        collector = ReferencedResourceCollector(
            discovery_service=mock_discovery_service,
            identity_resolver=mock_identity_resolver,
            aad_graph_service=mock_aad_graph_service,
        )

        filter_config = FilterConfig(
            subscription_ids=["sub1"],
            resource_group_names=["rg1"],
            include_referenced_resources=False,  # Disabled
        )

        result = await collector.collect_referenced_resources(
            sample_resources_with_identities, filter_config
        )

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_collect_with_no_references(
        self, mock_discovery_service, mock_identity_resolver, mock_aad_graph_service
    ):
        """Test collection returns empty when resources have no references."""
        collector = ReferencedResourceCollector(
            discovery_service=mock_discovery_service,
            identity_resolver=mock_identity_resolver,
            aad_graph_service=mock_aad_graph_service,
        )

        filter_config = FilterConfig(
            subscription_ids=["sub1"], resource_group_names=["rg1"]
        )

        # Resources with no identities or RBAC
        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1",
                "name": "vnet1",
                "type": "Microsoft.Network/virtualNetworks",
                "resource_group": "rg1",
            }
        ]

        result = await collector.collect_referenced_resources(resources, filter_config)

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_collect_deduplicates_references(
        self, mock_discovery_service, mock_identity_resolver, mock_aad_graph_service
    ):
        """Test collection deduplicates when multiple resources reference same identity."""
        mock_identity_resource = {
            "id": "/subscriptions/sub1/resourceGroups/shared-identities/providers/Microsoft.ManagedIdentity/userAssignedIdentities/shared-identity",
            "name": "shared-identity",
            "type": "Microsoft.ManagedIdentity/userAssignedIdentities",
            "resource_group": "shared-identities",
        }
        mock_discovery_service.discover_resources_in_subscription.return_value = [
            mock_identity_resource
        ]

        collector = ReferencedResourceCollector(
            discovery_service=mock_discovery_service,
            identity_resolver=mock_identity_resolver,
            aad_graph_service=mock_aad_graph_service,
        )

        filter_config = FilterConfig(
            subscription_ids=["sub1"], resource_group_names=["rg1"]
        )

        # Two resources referencing the same user-assigned identity
        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Web/sites/webapp1",
                "name": "webapp1",
                "resource_group": "rg1",
                "identity": {
                    "type": "UserAssigned",
                    "userAssignedIdentities": {
                        "/subscriptions/sub1/resourceGroups/shared-identities/providers/Microsoft.ManagedIdentity/userAssignedIdentities/shared-identity": {}
                    },
                },
            },
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Web/sites/webapp2",
                "name": "webapp2",
                "resource_group": "rg1",
                "identity": {
                    "type": "UserAssigned",
                    "userAssignedIdentities": {
                        "/subscriptions/sub1/resourceGroups/shared-identities/providers/Microsoft.ManagedIdentity/userAssignedIdentities/shared-identity": {}
                    },
                },
            },
        ]

        result = await collector.collect_referenced_resources(resources, filter_config)

        # Should only include the identity once despite two references
        identity_count = sum(
            1
            for r in result
            if r.get("type") == "Microsoft.ManagedIdentity/userAssignedIdentities"
        )
        assert identity_count == 1
