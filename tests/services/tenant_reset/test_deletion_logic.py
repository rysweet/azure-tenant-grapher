"""
Tests for Deletion Logic and Error Handling (Issue #627).

Test Coverage:
- Dependency-aware deletion ordering
- Concurrent deletion execution
- Partial failure handling
- Azure SDK integration
- Entra ID deletion
- Graph cleanup
- Locked resource handling
- Permission errors
- API failures
- Retry logic

Target: 100% coverage for deletion execution
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from azure.core.exceptions import ResourceNotFoundError, HttpResponseError

# Imports will fail until implementation exists
from src.services.tenant_reset_service import TenantResetService


class TestDependencyOrdering:
    """Test dependency-aware resource ordering."""

    @pytest.fixture
    def service(self):
        """Create TenantResetService instance."""
        return TenantResetService(
            credential=Mock(),
            tenant_id="12345678-1234-1234-1234-123456789abc"
        )

    @pytest.mark.asyncio
    async def test_order_by_dependencies_vms_before_disks(self, service):
        """Test that VMs are deleted before disks."""
        resources = [
            "/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Compute/disks/disk-1",
            "/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Compute/virtualMachines/vm-1",
        ]

        waves = await service.order_by_dependencies(resources)

        # VMs should be in earlier wave than disks
        vm_wave_index = None
        disk_wave_index = None

        for i, wave in enumerate(waves):
            if any("virtualMachines" in r for r in wave):
                vm_wave_index = i
            if any("disks" in r for r in wave):
                disk_wave_index = i

        assert vm_wave_index is not None
        assert disk_wave_index is not None
        assert vm_wave_index < disk_wave_index

    @pytest.mark.asyncio
    async def test_order_by_dependencies_nics_before_vnets(self, service):
        """Test that NICs are deleted before VNets."""
        resources = [
            "/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Network/virtualNetworks/vnet-1",
            "/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Network/networkInterfaces/nic-1",
        ]

        waves = await service.order_by_dependencies(resources)

        # NICs should be in earlier wave than VNets
        nic_wave_index = None
        vnet_wave_index = None

        for i, wave in enumerate(waves):
            if any("networkInterfaces" in r for r in wave):
                nic_wave_index = i
            if any("virtualNetworks" in r for r in wave):
                vnet_wave_index = i

        assert nic_wave_index is not None
        assert vnet_wave_index is not None
        assert nic_wave_index < vnet_wave_index

    @pytest.mark.asyncio
    async def test_order_by_dependencies_resources_before_resource_groups(
        self, service
    ):
        """Test that resources are deleted before resource groups."""
        resources = [
            "/subscriptions/sub-1/resourceGroups/rg-1",
            "/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Compute/virtualMachines/vm-1",
        ]

        waves = await service.order_by_dependencies(resources)

        # Resources should be in earlier wave than resource groups
        resource_wave_index = None
        rg_wave_index = None

        for i, wave in enumerate(waves):
            if any("virtualMachines" in r for r in wave):
                resource_wave_index = i
            if any(r.endswith("/resourceGroups/rg-1") for r in wave):
                rg_wave_index = i

        assert resource_wave_index is not None
        assert rg_wave_index is not None
        assert resource_wave_index < rg_wave_index

    @pytest.mark.asyncio
    async def test_order_by_dependencies_empty_list(self, service):
        """Test dependency ordering with empty resource list."""
        resources = []

        waves = await service.order_by_dependencies(resources)

        assert len(waves) == 0


class TestDeletionExecution:
    """Test deletion execution with concurrency."""

    @pytest.fixture
    def service(self):
        """Create TenantResetService instance."""
        return TenantResetService(
            credential=Mock(),
            tenant_id="12345678-1234-1234-1234-123456789abc",
            concurrency=5
        )

    @pytest.mark.asyncio
    async def test_delete_resources_success(self, service):
        """Test successful resource deletion."""
        deletion_waves = [
            [
                "/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Compute/virtualMachines/vm-1",
                "/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Compute/virtualMachines/vm-2",
            ]
        ]

        with patch.object(
            service, "_delete_single_resource", new_callable=AsyncMock
        ) as mock_delete:
            mock_delete.return_value = None  # Successful deletion

            results = await service.delete_resources(deletion_waves, concurrency=5)

            assert len(results["deleted"]) == 2
            assert len(results["failed"]) == 0
            assert mock_delete.call_count == 2

    @pytest.mark.asyncio
    async def test_delete_resources_partial_failure(self, service):
        """Test deletion with partial failures."""
        deletion_waves = [
            [
                "/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Compute/virtualMachines/vm-1",
                "/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Compute/virtualMachines/vm-2",
                "/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Compute/virtualMachines/vm-3",
            ]
        ]

        async def mock_delete_side_effect(resource_id):
            if "vm-2" in resource_id:
                raise Exception("Resource has delete lock")

        with patch.object(
            service, "_delete_single_resource", new_callable=AsyncMock
        ) as mock_delete:
            mock_delete.side_effect = mock_delete_side_effect

            results = await service.delete_resources(deletion_waves, concurrency=5)

            assert len(results["deleted"]) == 2  # vm-1 and vm-3
            assert len(results["failed"]) == 1  # vm-2
            assert "vm-2" in results["failed"][0]
            assert "Resource has delete lock" in results["errors"][results["failed"][0]]

    @pytest.mark.asyncio
    async def test_delete_resources_respects_concurrency(self, service):
        """Test that deletion respects concurrency limit."""
        deletion_waves = [
            [f"/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Compute/virtualMachines/vm-{i}"
             for i in range(1, 11)  # 10 resources
            ]
        ]

        concurrent_deletes = []

        async def mock_delete_side_effect(resource_id):
            concurrent_deletes.append(resource_id)
            await asyncio.sleep(0.1)  # Simulate deletion time
            concurrent_deletes.remove(resource_id)

        with patch.object(
            service, "_delete_single_resource", new_callable=AsyncMock
        ) as mock_delete:
            mock_delete.side_effect = mock_delete_side_effect

            # Track max concurrent deletes
            max_concurrent = 0

            async def track_concurrent():
                nonlocal max_concurrent
                while True:
                    max_concurrent = max(max_concurrent, len(concurrent_deletes))
                    await asyncio.sleep(0.01)

            # Start tracking task
            track_task = asyncio.create_task(track_concurrent())

            await service.delete_resources(deletion_waves, concurrency=5)

            track_task.cancel()

            # Max concurrent should not exceed concurrency limit
            assert max_concurrent <= 5

    @pytest.mark.asyncio
    async def test_delete_resources_waves_sequential(self, service):
        """Test that deletion waves are executed sequentially."""
        deletion_waves = [
            ["/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Compute/virtualMachines/vm-1"],
            ["/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Network/networkInterfaces/nic-1"],
        ]

        execution_order = []

        async def mock_delete_side_effect(resource_id):
            execution_order.append(resource_id)

        with patch.object(
            service, "_delete_single_resource", new_callable=AsyncMock
        ) as mock_delete:
            mock_delete.side_effect = mock_delete_side_effect

            await service.delete_resources(deletion_waves, concurrency=5)

            # VM should be deleted before NIC
            assert "vm-1" in execution_order[0]
            assert "nic-1" in execution_order[1]


class TestAzureSDKIntegration:
    """Test Azure SDK integration for resource deletion."""

    @pytest.fixture
    def service(self):
        """Create TenantResetService instance."""
        return TenantResetService(
            credential=Mock(),
            tenant_id="12345678-1234-1234-1234-123456789abc"
        )

    @pytest.mark.asyncio
    async def test_delete_single_resource_azure_api_call(self, service):
        """Test that resource deletion calls Azure SDK correctly."""
        resource_id = (
            "/subscriptions/sub-1/resourceGroups/rg-1/"
            "providers/Microsoft.Compute/virtualMachines/vm-1"
        )

        mock_poller = Mock()
        mock_poller.result = Mock()

        mock_resource_client = Mock()
        mock_resource_client.resources.begin_delete_by_id = Mock(return_value=mock_poller)

        with patch.object(
            service, "_get_resource_management_client", return_value=mock_resource_client
        ):
            await service._delete_single_resource(resource_id)

            # Verify Azure SDK was called with correct resource ID
            mock_resource_client.resources.begin_delete_by_id.assert_called_once()
            call_args = mock_resource_client.resources.begin_delete_by_id.call_args
            assert resource_id in str(call_args)

    @pytest.mark.asyncio
    async def test_delete_single_resource_resource_not_found(self, service):
        """Test handling of already-deleted resources."""
        resource_id = (
            "/subscriptions/sub-1/resourceGroups/rg-1/"
            "providers/Microsoft.Compute/virtualMachines/vm-1"
        )

        mock_resource_client = Mock()
        mock_resource_client.resources.begin_delete_by_id = Mock(
            side_effect=ResourceNotFoundError("Resource not found")
        )

        with patch.object(
            service, "_get_resource_management_client", return_value=mock_resource_client
        ):
            # Should not raise - already deleted is success
            await service._delete_single_resource(resource_id)

    @pytest.mark.asyncio
    async def test_delete_single_resource_permission_error(self, service):
        """Test handling of permission errors."""
        resource_id = (
            "/subscriptions/sub-1/resourceGroups/rg-1/"
            "providers/Microsoft.Compute/virtualMachines/vm-1"
        )

        mock_resource_client = Mock()
        mock_resource_client.resources.begin_delete_by_id = Mock(
            side_effect=HttpResponseError(message="Insufficient permissions")
        )

        with patch.object(
            service, "_get_resource_management_client", return_value=mock_resource_client
        ):
            with pytest.raises(HttpResponseError):
                await service._delete_single_resource(resource_id)


class TestEntraIDDeletion:
    """Test Entra ID (Azure AD) identity deletion."""

    @pytest.fixture
    def service(self):
        """Create TenantResetService instance."""
        return TenantResetService(
            credential=Mock(),
            tenant_id="12345678-1234-1234-1234-123456789abc"
        )

    @pytest.mark.asyncio
    async def test_delete_service_principal(self, service):
        """Test service principal deletion."""
        sp_id = "sp-to-delete"

        mock_sp_request = Mock()
        mock_sp_request.delete = AsyncMock()

        mock_graph_client = AsyncMock()
        mock_graph_client.service_principals.by_service_principal_id = Mock(return_value=mock_sp_request)

        with patch.object(
            service, "_get_graph_client", return_value=mock_graph_client
        ):
            await service._delete_service_principal(sp_id)

            mock_graph_client.service_principals.by_service_principal_id.assert_called_once_with(sp_id)
            mock_sp_request.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_user(self, service):
        """Test user deletion."""
        user_id = "user-to-delete"

        mock_user_request = Mock()
        mock_user_request.delete = AsyncMock()

        mock_graph_client = AsyncMock()
        mock_graph_client.users.by_user_id = Mock(return_value=mock_user_request)

        with patch.object(
            service, "_get_graph_client", return_value=mock_graph_client
        ):
            await service._delete_user(user_id)

            mock_graph_client.users.by_user_id.assert_called_once_with(user_id)
            mock_user_request.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_group(self, service):
        """Test group deletion."""
        group_id = "group-to-delete"

        mock_group_request = Mock()
        mock_group_request.delete = AsyncMock()

        mock_graph_client = AsyncMock()
        mock_graph_client.groups.by_group_id = Mock(return_value=mock_group_request)

        with patch.object(
            service, "_get_graph_client", return_value=mock_graph_client
        ):
            await service._delete_group(group_id)

            mock_graph_client.groups.by_group_id.assert_called_once_with(group_id)
            mock_group_request.delete.assert_called_once()


class TestGraphCleanup:
    """Test Neo4j graph database cleanup."""

    @pytest.fixture
    def service(self):
        """Create TenantResetService instance."""
        return TenantResetService(
            credential=Mock(),
            tenant_id="12345678-1234-1234-1234-123456789abc"
        )

    @pytest.mark.asyncio
    async def test_cleanup_graph_after_deletion(self, service):
        """Test that deleted resources are removed from Neo4j graph."""
        deleted_resource_ids = [
            "/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Compute/virtualMachines/vm-1",
            "/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Compute/virtualMachines/vm-2",
        ]

        mock_neo4j_session = AsyncMock()
        mock_neo4j_session.run_query = AsyncMock()

        with patch.object(
            service, "_get_neo4j_session", return_value=mock_neo4j_session
        ):
            await service._cleanup_graph_resources(deleted_resource_ids)

            # Verify DELETE query was executed
            mock_neo4j_session.run_query.assert_called_once()
            call_args = str(mock_neo4j_session.run_query.call_args)
            assert "DELETE" in call_args.upper()

    @pytest.mark.asyncio
    async def test_cleanup_graph_parameterized_query(self, service):
        """
        Test that graph cleanup uses parameterized queries.

        Prevents Cypher injection attacks.
        """
        deleted_resource_ids = [
            "/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Compute/virtualMachines/vm-1"
        ]

        mock_neo4j_session = AsyncMock()
        mock_neo4j_session.run_query = AsyncMock()

        with patch.object(
            service, "_get_neo4j_session", return_value=mock_neo4j_session
        ):
            await service._cleanup_graph_resources(deleted_resource_ids)

            # Verify query uses parameters (not string interpolation)
            mock_neo4j_session.run_query.assert_called_once()
            call_args = mock_neo4j_session.run_query.call_args
            assert call_args[0][0]  # Query string (first positional arg)
            assert "resource_ids" in call_args[0][1]  # Parameters dict (second positional arg)


class TestErrorHandling:
    """Test error handling for various failure scenarios."""

    @pytest.fixture
    def service(self):
        """Create TenantResetService instance."""
        return TenantResetService(
            credential=Mock(),
            tenant_id="12345678-1234-1234-1234-123456789abc"
        )

    @pytest.mark.asyncio
    async def test_locked_resource_error_handling(self, service):
        """Test handling of locked resources."""
        resource_id = (
            "/subscriptions/sub-1/resourceGroups/rg-1/"
            "providers/Microsoft.Compute/virtualMachines/vm-locked"
        )

        mock_resource_client = Mock()
        mock_resource_client.resources.begin_delete_by_id = Mock(
            side_effect=HttpResponseError(message="Resource has delete lock")
        )

        with patch.object(
            service, "_get_resource_management_client", return_value=mock_resource_client
        ):
            with pytest.raises(HttpResponseError) as exc:
                await service._delete_single_resource(resource_id)

            assert "delete lock" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_api_rate_limit_error_handling(self, service):
        """Test handling of Azure API rate limit errors."""
        resource_id = (
            "/subscriptions/sub-1/resourceGroups/rg-1/"
            "providers/Microsoft.Compute/virtualMachines/vm-1"
        )

        # Create HttpResponseError with status_code attribute
        error = HttpResponseError(message="Too many requests")
        error.status_code = 429

        mock_resource_client = Mock()
        mock_resource_client.resources.begin_delete_by_id = Mock(side_effect=error)

        with patch.object(
            service, "_get_resource_management_client", return_value=mock_resource_client
        ):
            with pytest.raises(HttpResponseError) as exc:
                await service._delete_single_resource(resource_id)

            assert exc.value.status_code == 429

    @pytest.mark.asyncio
    async def test_network_error_handling(self, service):
        """Test handling of network errors."""
        resource_id = (
            "/subscriptions/sub-1/resourceGroups/rg-1/"
            "providers/Microsoft.Compute/virtualMachines/vm-1"
        )

        mock_resource_client = Mock()
        mock_resource_client.resources.begin_delete_by_id = Mock(
            side_effect=Exception("Connection timeout")
        )

        with patch.object(
            service, "_get_resource_management_client", return_value=mock_resource_client
        ):
            with pytest.raises(Exception) as exc:
                await service._delete_single_resource(resource_id)

            assert "timeout" in str(exc.value).lower()


pytestmark = pytest.mark.unit
