"""Integration tests for filtered identity inclusion feature."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.filter_config import FilterConfig
from src.services.identity_collector import IdentityCollector
from src.services.managed_identity_resolver import ManagedIdentityResolver
from src.services.resource_processing_service import ResourceProcessingService


class TestIdentityCollector:
    """Test the IdentityCollector service."""

    def test_extract_system_assigned_identity(self):
        """Test extraction of system-assigned managed identity."""
        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Web/sites/webapp1",
                "type": "Microsoft.Web/sites",
                "identity": {
                    "type": "SystemAssigned",
                    "principalId": "principal-123",
                    "tenantId": "tenant-456",
                },
            }
        ]

        collector = IdentityCollector()
        refs = collector.collect_identity_references(resources)

        assert "principal-123" in refs.managed_identities
        assert len(refs.managed_identities) == 1
        assert len(refs.users) == 0
        assert len(refs.service_principals) == 0
        assert len(refs.groups) == 0

    def test_extract_user_assigned_identities(self):
        """Test extraction of user-assigned managed identities."""
        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Web/sites/webapp2",
                "type": "Microsoft.Web/sites",
                "identity": {
                    "type": "UserAssigned",
                    "userAssignedIdentities": {
                        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.ManagedIdentity/userAssignedIdentities/identity1": {
                            "principalId": "uai-principal-111",
                            "clientId": "uai-client-111",
                        },
                        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.ManagedIdentity/userAssignedIdentities/identity2": {
                            "principalId": "uai-principal-222",
                            "clientId": "uai-client-222",
                        },
                    },
                },
            }
        ]

        collector = IdentityCollector()
        refs = collector.collect_identity_references(resources)

        # Should extract both the resource IDs and principal IDs
        assert len(refs.managed_identities) == 4
        assert (
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.ManagedIdentity/userAssignedIdentities/identity1"
            in refs.managed_identities
        )
        assert (
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.ManagedIdentity/userAssignedIdentities/identity2"
            in refs.managed_identities
        )
        assert "uai-principal-111" in refs.managed_identities
        assert "uai-principal-222" in refs.managed_identities

    def test_extract_role_assignment_principals(self):
        """Test extraction of principals from role assignments."""
        resources = [
            {
                "id": "/subscriptions/sub1/providers/Microsoft.Authorization/roleAssignments/ra1",
                "type": "Microsoft.Authorization/roleAssignments",
                "properties": {
                    "principalId": "user-001",
                    "principalType": "User",
                    "roleDefinitionId": "/subscriptions/sub1/providers/Microsoft.Authorization/roleDefinitions/contributor",
                },
            },
            {
                "id": "/subscriptions/sub1/providers/Microsoft.Authorization/roleAssignments/ra2",
                "type": "Microsoft.Authorization/roleAssignments",
                "properties": {
                    "principalId": "sp-002",
                    "principalType": "ServicePrincipal",
                    "roleDefinitionId": "/subscriptions/sub1/providers/Microsoft.Authorization/roleDefinitions/reader",
                },
            },
            {
                "id": "/subscriptions/sub1/providers/Microsoft.Authorization/roleAssignments/ra3",
                "type": "Microsoft.Authorization/roleAssignments",
                "properties": {
                    "principalId": "group-003",
                    "principalType": "Group",
                    "roleDefinitionId": "/subscriptions/sub1/providers/Microsoft.Authorization/roleDefinitions/owner",
                },
            },
        ]

        collector = IdentityCollector()
        refs = collector.collect_identity_references(resources)

        assert "user-001" in refs.users
        assert "sp-002" in refs.service_principals
        assert "group-003" in refs.groups
        assert len(refs.users) == 1
        assert len(refs.service_principals) == 1
        assert len(refs.groups) == 1
        assert len(refs.managed_identities) == 0

    def test_mixed_identity_extraction(self):
        """Test extraction from resources with multiple identity types."""
        resources = [
            # Web app with system-assigned identity
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Web/sites/webapp1",
                "type": "Microsoft.Web/sites",
                "identity": {
                    "type": "SystemAssigned",
                    "principalId": "system-principal-001",
                },
            },
            # Role assignment for a user
            {
                "id": "/subscriptions/sub1/providers/Microsoft.Authorization/roleAssignments/ra1",
                "type": "Microsoft.Authorization/roleAssignments",
                "properties": {"principalId": "user-001", "principalType": "User"},
            },
            # VM with both system and user-assigned identities
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
                "type": "Microsoft.Compute/virtualMachines",
                "identity": {
                    "type": "SystemAssigned,UserAssigned",
                    "principalId": "system-principal-002",
                    "userAssignedIdentities": {
                        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.ManagedIdentity/userAssignedIdentities/identity1": {
                            "principalId": "uai-principal-001"
                        }
                    },
                },
            },
        ]

        collector = IdentityCollector()
        refs = collector.collect_identity_references(resources)

        assert refs.total_count() == 5
        assert len(refs.users) == 1
        assert (
            len(refs.managed_identities) == 4
        )  # 2 system + 1 UAI resource ID + 1 UAI principal

        summary = collector.get_summary(refs)
        assert "5 identities" in summary
        assert "1 users" in summary
        assert "4 managed identities" in summary


class TestManagedIdentityResolver:
    """Test the ManagedIdentityResolver service."""

    def test_resolve_user_assigned_identity_by_resource_id(self):
        """Test resolving user-assigned identity by its resource ID."""
        identity_refs = {
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.ManagedIdentity/userAssignedIdentities/identity1"
        }

        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.ManagedIdentity/userAssignedIdentities/identity1",
                "type": "Microsoft.ManagedIdentity/userAssignedIdentities",
                "name": "identity1",
                "location": "eastus",
                "properties": {
                    "principalId": "uai-principal-001",
                    "clientId": "uai-client-001",
                    "tenantId": "tenant-001",
                },
            }
        ]

        resolver = ManagedIdentityResolver()
        resolved = resolver.resolve_identities(identity_refs, resources)

        assert len(resolved) == 1
        identity_id = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.ManagedIdentity/userAssignedIdentities/identity1"
        assert identity_id in resolved
        assert resolved[identity_id]["type"] == "UserAssignedManagedIdentity"
        assert resolved[identity_id]["principalId"] == "uai-principal-001"
        assert resolved[identity_id]["clientId"] == "uai-client-001"

    def test_resolve_system_assigned_identity(self):
        """Test resolving system-assigned identity from resource."""
        identity_refs = {"system-principal-001"}

        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Web/sites/webapp1",
                "type": "Microsoft.Web/sites",
                "name": "webapp1",
                "identity": {
                    "type": "SystemAssigned",
                    "principalId": "system-principal-001",
                    "tenantId": "tenant-001",
                },
            }
        ]

        resolver = ManagedIdentityResolver()
        resolved = resolver.resolve_identities(identity_refs, resources)

        assert len(resolved) == 1
        assert "system-principal-001" in resolved
        assert (
            resolved["system-principal-001"]["type"] == "SystemAssignedManagedIdentity"
        )
        assert (
            resolved["system-principal-001"]["resourceId"]
            == "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Web/sites/webapp1"
        )
        assert resolved["system-principal-001"]["resourceName"] == "webapp1"

    def test_get_identity_summary(self):
        """Test generating human-readable summary of resolved identities."""
        resolved_identities = {
            "system-001": {"type": "SystemAssignedManagedIdentity"},
            "system-002": {"type": "SystemAssignedManagedIdentity"},
            "uai-001": {"type": "UserAssignedManagedIdentity"},
        }

        resolver = ManagedIdentityResolver()
        summary = resolver.get_identity_summary(resolved_identities)

        assert "3 managed identities" in summary
        assert "2 system-assigned" in summary
        assert "1 user-assigned" in summary


@pytest.mark.asyncio
class TestResourceProcessingServiceWithFiltering:
    """Test ResourceProcessingService with identity filtering."""

    async def test_filtered_identity_import(self):
        """Test that filtered builds import only referenced identities."""
        # Setup mocks
        session_manager = MagicMock()
        llm_generator = None
        config = MagicMock()
        config.enable_aad_import = True
        config.max_concurrency = 5

        # Mock AADGraphService
        aad_service = AsyncMock()
        aad_service.ingest_filtered_identities = AsyncMock()

        # Create filter config with valid UUIDs
        filter_config = FilterConfig(
            subscription_ids={"12345678-1234-1234-1234-123456789012"},
            resource_group_names={"rg1"},
        )

        # Sample resources with identities
        resources = [
            {
                "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg1/providers/Microsoft.Web/sites/webapp1",
                "type": "Microsoft.Web/sites",
                "resource_group": "rg1",
                "identity": {
                    "type": "SystemAssigned",
                    "principalId": "system-principal-001",
                },
            },
            {
                "id": "/subscriptions/12345678-1234-1234-1234-123456789012/providers/Microsoft.Authorization/roleAssignments/ra1",
                "type": "Microsoft.Authorization/roleAssignments",
                "properties": {"principalId": "user-001", "principalType": "User"},
            },
        ]

        # Mock processor
        processor_mock = AsyncMock()
        processor_mock.process_resources = AsyncMock(
            return_value=MagicMock(total_resources=2, processed=2, successful=2)
        )
        processor_mock.db_ops = MagicMock()

        processor_factory = MagicMock(return_value=processor_mock)

        # Create service
        service = ResourceProcessingService(
            session_manager,
            llm_generator,
            config,
            processor_factory=processor_factory,
            aad_graph_service=aad_service,
        )

        # Process resources with filtering
        await service.process_resources(resources, filter_config=filter_config)

        # Verify filtered identity import was called
        aad_service.ingest_filtered_identities.assert_called_once()
        call_args = aad_service.ingest_filtered_identities.call_args[1]

        # Should have extracted the user and managed identity
        assert "user-001" in call_args["user_ids"]
        # System-assigned identities are actually service principals in Azure AD
        # The ResourceProcessingService puts them in service_principal_ids
        assert len(call_args["service_principal_ids"]) == 1
        assert "system-principal-001" in call_args["service_principal_ids"]
        assert call_args["db_ops"] == processor_mock.db_ops

    async def test_no_filtering_imports_all_identities(self):
        """Test that builds without filtering import all AAD identities."""
        # Setup mocks
        session_manager = MagicMock()
        llm_generator = None
        config = MagicMock()
        config.enable_aad_import = True
        config.max_concurrency = 5

        # Mock AADGraphService
        aad_service = AsyncMock()
        aad_service.ingest_into_graph = AsyncMock()

        # No filter config
        filter_config = None

        resources = [{"id": "resource1"}]

        # Mock processor
        processor_mock = AsyncMock()
        processor_mock.process_resources = AsyncMock(
            return_value=MagicMock(total_resources=1, processed=1, successful=1)
        )
        processor_mock.db_ops = MagicMock()

        processor_factory = MagicMock(return_value=processor_mock)

        # Create service
        service = ResourceProcessingService(
            session_manager,
            llm_generator,
            config,
            processor_factory=processor_factory,
            aad_graph_service=aad_service,
        )

        # Process resources without filtering
        await service.process_resources(resources, filter_config=filter_config)

        # Verify full AAD import was called
        aad_service.ingest_into_graph.assert_called_once_with(processor_mock.db_ops)
        # Filtered import should NOT be called
        aad_service.ingest_filtered_identities.assert_not_called()

    async def test_no_identities_in_filtered_resources(self):
        """Test handling when filtered resources have no identity references."""
        # Setup mocks
        session_manager = MagicMock()
        llm_generator = None
        config = MagicMock()
        config.enable_aad_import = True
        config.max_concurrency = 5

        # Mock AADGraphService
        aad_service = AsyncMock()
        aad_service.ingest_filtered_identities = AsyncMock()

        # Create filter config
        filter_config = FilterConfig(resource_group_names={"rg1"})

        # Resources without any identities
        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1",
                "type": "Microsoft.Storage/storageAccounts",
                "resource_group": "rg1",
            }
        ]

        # Mock processor
        processor_mock = AsyncMock()
        processor_mock.process_resources = AsyncMock(
            return_value=MagicMock(total_resources=1, processed=1, successful=1)
        )
        processor_mock.db_ops = MagicMock()

        processor_factory = MagicMock(return_value=processor_mock)

        # Create service
        service = ResourceProcessingService(
            session_manager,
            llm_generator,
            config,
            processor_factory=processor_factory,
            aad_graph_service=aad_service,
        )

        # Process resources with filtering
        await service.process_resources(resources, filter_config=filter_config)

        # Verify filtered identity import was NOT called (no identities to import)
        aad_service.ingest_filtered_identities.assert_not_called()
