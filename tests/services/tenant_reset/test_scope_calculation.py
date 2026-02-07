"""
Tests for Scope Calculation (Issue #627).

Test Coverage:
- Tenant scope calculation
- Subscription scope calculation
- Resource group scope calculation
- Resource scope calculation
- Scope boundary validation
- Multi-subscription support
- Multi-resource-group support
- Empty scope handling

Target: 100% coverage for scope calculation logic
"""

from unittest.mock import Mock, patch

import pytest

from src.services.reset_confirmation import SecurityError

# Imports will fail until implementation exists
from src.services.tenant_reset_service import TenantResetService


class TestTenantScopeCalculation:
    """Test tenant-level scope calculation."""

    @pytest.fixture
    def service(self):
        """Create TenantResetService instance."""
        return TenantResetService(
            credential=Mock(), tenant_id="12345678-1234-1234-1234-123456789abc"
        )

    @pytest.mark.asyncio
    async def test_tenant_scope_includes_all_subscriptions(self, service):
        """Test that tenant scope includes resources from all subscriptions."""
        mock_subscriptions = [
            {"subscription_id": "11111111-1111-1111-1111-111111111111"},
            {"subscription_id": "22222222-2222-2222-2222-222222222222"},
            {"subscription_id": "33333333-3333-3333-3333-333333333333"},
        ]

        with patch.object(
            service, "_list_all_subscriptions", return_value=mock_subscriptions
        ):
            with patch.object(
                service,
                "_list_resources_in_subscription",
                side_effect=[
                    ["resource-sub1-1", "resource-sub1-2"],
                    ["resource-sub2-1"],
                    ["resource-sub3-1", "resource-sub3-2", "resource-sub3-3"],
                ],
            ):
                with patch.object(
                    service,
                    "identify_atg_service_principal",
                    return_value="atg-sp-id",
                ):
                    scope_data = await service.calculate_scope_tenant(
                        tenant_id="12345678-1234-1234-1234-123456789abc"
                    )

                    # Should have resources from all subscriptions
                    assert len(scope_data["to_delete"]) == 6
                    assert "resource-sub1-1" in scope_data["to_delete"]
                    assert "resource-sub2-1" in scope_data["to_delete"]
                    assert "resource-sub3-3" in scope_data["to_delete"]

    @pytest.mark.asyncio
    async def test_tenant_scope_includes_all_identities(self, service):
        """Test that tenant scope includes all Entra ID identities."""
        with patch.object(
            service,
            "_list_all_service_principals",
            return_value=[
                {"id": "sp-1"},
                {"id": "sp-2"},
                {"id": "atg-sp-id"},
            ],
        ):
            with patch.object(
                service,
                "_list_all_users",
                return_value=[
                    {"id": "user-1"},
                    {"id": "user-2"},
                ],
            ):
                with patch.object(
                    service,
                    "_list_all_groups",
                    return_value=[
                        {"id": "group-1"},
                    ],
                ):
                    with patch.object(
                        service,
                        "identify_atg_service_principal",
                        return_value="atg-sp-id",
                    ):
                        scope_data = await service.calculate_scope_tenant(
                            tenant_id="12345678-1234-1234-1234-123456789abc"
                        )

                        # Should have all identities except ATG SP
                        assert "sp-1" in scope_data["to_delete"]
                        assert "sp-2" in scope_data["to_delete"]
                        assert "user-1" in scope_data["to_delete"]
                        assert "user-2" in scope_data["to_delete"]
                        assert "group-1" in scope_data["to_delete"]

                        # ATG SP should be preserved
                        assert "atg-sp-id" not in scope_data["to_delete"]
                        assert "atg-sp-id" in scope_data["to_preserve"]

    @pytest.mark.asyncio
    async def test_tenant_scope_empty_tenant(self, service):
        """Test tenant scope calculation for empty tenant."""
        with patch.object(service, "_list_all_subscriptions", return_value=[]):
            with patch.object(service, "_list_all_service_principals", return_value=[]):
                with patch.object(
                    service,
                    "identify_atg_service_principal",
                    return_value="atg-sp-id",
                ):
                    scope_data = await service.calculate_scope_tenant(
                        tenant_id="12345678-1234-1234-1234-123456789abc"
                    )

                    assert len(scope_data["to_delete"]) == 0
                    assert len(scope_data["to_preserve"]) >= 1  # At least ATG SP


class TestSubscriptionScopeCalculation:
    """Test subscription-level scope calculation."""

    @pytest.fixture
    def service(self):
        """Create TenantResetService instance."""
        return TenantResetService(
            credential=Mock(), tenant_id="12345678-1234-1234-1234-123456789abc"
        )

    @pytest.mark.asyncio
    async def test_subscription_scope_single_subscription(self, service):
        """Test subscription scope for single subscription."""
        subscription_id = "11111111-1111-1111-1111-111111111111"

        with patch.object(
            service,
            "_list_resources_in_subscription",
            return_value=["resource-1", "resource-2", "resource-3"],
        ):
            with patch.object(
                service,
                "identify_atg_service_principal",
                return_value="atg-sp-id",
            ):
                scope_data = await service.calculate_scope_subscription(
                    [subscription_id]
                )

                assert len(scope_data["to_delete"]) == 3
                assert "resource-1" in scope_data["to_delete"]
                assert "resource-2" in scope_data["to_delete"]
                assert "resource-3" in scope_data["to_delete"]

    @pytest.mark.asyncio
    async def test_subscription_scope_multiple_subscriptions(self, service):
        """Test subscription scope for multiple subscriptions."""
        subscription_ids = [
            "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
        ]

        with patch.object(
            service,
            "_list_resources_in_subscription",
            side_effect=[
                ["resource-sub1-1", "resource-sub1-2"],
                ["resource-sub2-1"],
            ],
        ):
            with patch.object(
                service,
                "identify_atg_service_principal",
                return_value="atg-sp-id",
            ):
                scope_data = await service.calculate_scope_subscription(
                    subscription_ids
                )

                assert len(scope_data["to_delete"]) == 3
                assert "resource-sub1-1" in scope_data["to_delete"]
                assert "resource-sub1-2" in scope_data["to_delete"]
                assert "resource-sub2-1" in scope_data["to_delete"]

    @pytest.mark.asyncio
    async def test_subscription_scope_empty_subscription(self, service):
        """Test subscription scope for empty subscription."""
        subscription_id = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"

        with patch.object(service, "_list_resources_in_subscription", return_value=[]):
            with patch.object(
                service,
                "identify_atg_service_principal",
                return_value="atg-sp-id",
            ):
                scope_data = await service.calculate_scope_subscription(
                    [subscription_id]
                )

                assert len(scope_data["to_delete"]) == 0

    @pytest.mark.asyncio
    async def test_subscription_scope_nonexistent_subscription(self, service):
        """Test subscription scope for nonexistent subscription."""
        subscription_id = "99999999-9999-9999-9999-999999999999"

        with patch.object(
            service,
            "_list_resources_in_subscription",
            side_effect=Exception("Subscription not found"),
        ):
            with pytest.raises(Exception) as exc:
                await service.calculate_scope_subscription([subscription_id])

            assert "Subscription not found" in str(exc.value)


class TestResourceGroupScopeCalculation:
    """Test resource group-level scope calculation."""

    @pytest.fixture
    def service(self):
        """Create TenantResetService instance."""
        return TenantResetService(
            credential=Mock(), tenant_id="12345678-1234-1234-1234-123456789abc"
        )

    @pytest.mark.asyncio
    async def test_resource_group_scope_single_rg(self, service):
        """Test resource group scope for single RG."""
        subscription_id = "11111111-1111-1111-1111-111111111111"
        resource_group = "test-rg"

        with patch.object(
            service,
            "_list_resources_in_resource_group",
            return_value=["resource-1", "resource-2"],
        ):
            with patch.object(
                service,
                "identify_atg_service_principal",
                return_value="atg-sp-id",
            ):
                scope_data = await service.calculate_scope_resource_group(
                    resource_group_names=[resource_group],
                    subscription_id=subscription_id,
                )

                assert len(scope_data["to_delete"]) == 2
                assert "resource-1" in scope_data["to_delete"]
                assert "resource-2" in scope_data["to_delete"]

    @pytest.mark.asyncio
    async def test_resource_group_scope_multiple_rgs(self, service):
        """Test resource group scope for multiple RGs."""
        subscription_id = "11111111-1111-1111-1111-111111111111"
        resource_groups = ["rg-1", "rg-2", "rg-3"]

        with patch.object(
            service,
            "_list_resources_in_resource_group",
            side_effect=[
                ["resource-rg1-1"],
                ["resource-rg2-1", "resource-rg2-2"],
                ["resource-rg3-1"],
            ],
        ):
            with patch.object(
                service,
                "identify_atg_service_principal",
                return_value="atg-sp-id",
            ):
                scope_data = await service.calculate_scope_resource_group(
                    resource_group_names=resource_groups,
                    subscription_id=subscription_id,
                )

                assert len(scope_data["to_delete"]) == 4
                assert "resource-rg1-1" in scope_data["to_delete"]
                assert "resource-rg2-1" in scope_data["to_delete"]
                assert "resource-rg2-2" in scope_data["to_delete"]
                assert "resource-rg3-1" in scope_data["to_delete"]

    @pytest.mark.asyncio
    async def test_resource_group_scope_empty_rg(self, service):
        """Test resource group scope for empty RG."""
        subscription_id = "11111111-1111-1111-1111-111111111111"
        resource_group = "empty-rg"

        with patch.object(
            service, "_list_resources_in_resource_group", return_value=[]
        ):
            with patch.object(
                service,
                "identify_atg_service_principal",
                return_value="atg-sp-id",
            ):
                scope_data = await service.calculate_scope_resource_group(
                    resource_group_names=[resource_group],
                    subscription_id=subscription_id,
                )

                assert len(scope_data["to_delete"]) == 0

    @pytest.mark.asyncio
    async def test_resource_group_scope_nonexistent_rg(self, service):
        """Test resource group scope for nonexistent RG."""
        subscription_id = "11111111-1111-1111-1111-111111111111"
        resource_group = "nonexistent-rg"

        with patch.object(
            service,
            "_list_resources_in_resource_group",
            side_effect=Exception("Resource group not found"),
        ):
            with pytest.raises(Exception) as exc:
                await service.calculate_scope_resource_group(
                    resource_group_names=[resource_group],
                    subscription_id=subscription_id,
                )

            assert "Resource group not found" in str(exc.value)


class TestResourceScopeCalculation:
    """Test single resource scope calculation."""

    @pytest.fixture
    def service(self):
        """Create TenantResetService instance."""
        return TenantResetService(
            credential=Mock(), tenant_id="12345678-1234-1234-1234-123456789abc"
        )

    @pytest.mark.asyncio
    async def test_resource_scope_single_resource(self, service):
        """Test resource scope for single resource."""
        resource_id = (
            "/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/rg-1/"
            "providers/Microsoft.Compute/virtualMachines/vm-1"
        )

        with patch.object(service, "_get_resource", return_value={"id": resource_id}):
            with patch.object(
                service,
                "identify_atg_service_principal",
                return_value="atg-sp-id",
            ):
                scope_data = await service.calculate_scope_resource(resource_id)

                assert len(scope_data["to_delete"]) == 1
                assert resource_id in scope_data["to_delete"]

    @pytest.mark.asyncio
    async def test_resource_scope_nonexistent_resource(self, service):
        """Test resource scope for nonexistent resource."""
        resource_id = (
            "/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/rg-1/"
            "providers/Microsoft.Compute/virtualMachines/nonexistent"
        )

        with patch.object(service, "_get_resource", return_value=None):
            with pytest.raises(Exception) as exc:
                await service.calculate_scope_resource(resource_id)

            assert "not found" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_resource_scope_atg_sp_blocked(self, service):
        """
        CRITICAL: Test that ATG SP cannot be targeted for deletion.
        """
        atg_sp_id = "87654321-4321-4321-4321-210987654321"

        with patch.object(
            service,
            "identify_atg_service_principal",
            return_value=atg_sp_id,
        ):
            with pytest.raises(SecurityError) as exc:
                await service.calculate_scope_resource(atg_sp_id)

            assert "ATG Service Principal cannot be deleted" in str(exc.value)


class TestScopeBoundaryValidation:
    """Test scope boundary validation."""

    @pytest.fixture
    def service(self):
        """Create TenantResetService instance."""
        return TenantResetService(
            credential=Mock(), tenant_id="12345678-1234-1234-1234-123456789abc"
        )

    @pytest.mark.asyncio
    async def test_scope_subscription_not_in_tenant(self, service):
        """Test that subscriptions from other tenants are rejected."""
        # Subscription from different tenant
        subscription_id = "other-tenant-sub"

        with patch.object(
            service,
            "_validate_subscription_in_tenant",
            side_effect=ValueError("Subscription not in tenant"),
        ):
            with pytest.raises(ValueError) as exc:
                await service.calculate_scope_subscription([subscription_id])

            assert "not in tenant" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_scope_resource_group_not_in_subscription(self, service):
        """Test that resource groups from other subscriptions are rejected."""
        subscription_id = "11111111-1111-1111-1111-111111111111"
        resource_group = "rg-from-different-subscription"

        with patch.object(
            service,
            "_validate_resource_group_in_subscription",
            side_effect=ValueError("Resource group not in subscription"),
        ):
            with pytest.raises(ValueError) as exc:
                await service.calculate_scope_resource_group(
                    resource_group_names=[resource_group],
                    subscription_id=subscription_id,
                )

            assert "not in subscription" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_scope_resource_not_in_resource_group(self, service):
        """Test that resources are correctly scoped to resource group."""
        resource_id = (
            "/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/rg-1/"
            "providers/Microsoft.Compute/virtualMachines/vm-1"
        )

        # Try to calculate scope for resource group rg-2
        # But resource is in rg-1
        with patch.object(
            service,
            "_list_resources_in_resource_group",
            return_value=[],  # rg-2 is empty
        ):
            with patch.object(
                service,
                "identify_atg_service_principal",
                return_value="atg-sp-id",
            ):
                scope_data = await service.calculate_scope_resource_group(
                    resource_group_names=["rg-2"],
                    subscription_id="11111111-1111-1111-1111-111111111111",
                )

                # Resource should not be in scope
                assert resource_id not in scope_data["to_delete"]


class TestScopeDataStructure:
    """Test scope data structure format."""

    @pytest.fixture
    def service(self):
        """Create TenantResetService instance."""
        return TenantResetService(
            credential=Mock(), tenant_id="12345678-1234-1234-1234-123456789abc"
        )

    @pytest.mark.asyncio
    async def test_scope_data_has_required_keys(self, service):
        """Test that scope data has required keys."""
        subscription_id = "11111111-1111-1111-1111-111111111111"

        with patch.object(
            service,
            "_list_resources_in_subscription",
            return_value=["resource-1"],
        ):
            with patch.object(
                service,
                "identify_atg_service_principal",
                return_value="atg-sp-id",
            ):
                scope_data = await service.calculate_scope_subscription(
                    [subscription_id]
                )

                assert "to_delete" in scope_data
                assert "to_preserve" in scope_data
                assert isinstance(scope_data["to_delete"], list)
                assert isinstance(scope_data["to_preserve"], list)

    @pytest.mark.asyncio
    async def test_scope_data_no_duplicates(self, service):
        """Test that scope data contains no duplicate resource IDs."""
        subscription_ids = [
            "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
        ]

        # Simulate overlapping resources (should be deduplicated)
        with patch.object(
            service,
            "_list_resources_in_subscription",
            side_effect=[
                ["resource-1", "resource-2"],
                ["resource-2", "resource-3"],  # resource-2 appears twice
            ],
        ):
            with patch.object(
                service,
                "identify_atg_service_principal",
                return_value="atg-sp-id",
            ):
                scope_data = await service.calculate_scope_subscription(
                    subscription_ids
                )

                # Should have 3 unique resources, not 4
                assert len(scope_data["to_delete"]) == 3
                assert scope_data["to_delete"].count("resource-2") == 1


pytestmark = pytest.mark.unit
