"""Tests for cross-tenant resource filter."""

import pytest

from src.iac.filters.cross_tenant_filter import CrossTenantResourceFilter, FilterResult


class TestCrossTenantResourceFilter:
    """Test suite for CrossTenantResourceFilter."""

    @pytest.fixture
    def source_sub_id(self):
        """Source subscription ID."""
        return "11111111-1111-1111-1111-111111111111"

    @pytest.fixture
    def target_sub_id(self):
        """Target subscription ID."""
        return "22222222-2222-2222-2222-222222222222"

    @pytest.fixture
    def filter_instance(self, source_sub_id, target_sub_id):
        """Create filter instance."""
        return CrossTenantResourceFilter(
            source_subscription_id=source_sub_id,
            target_subscription_id=target_sub_id,
        )

    def test_initialization(self, filter_instance, source_sub_id, target_sub_id):
        """Test filter initialization."""
        assert filter_instance.source_subscription_id == source_sub_id.lower()
        assert filter_instance.target_subscription_id == target_sub_id.lower()

    def test_same_subscription_no_filtering(self, source_sub_id):
        """Test that same source and target subscription skips filtering."""
        filter_instance = CrossTenantResourceFilter(
            source_subscription_id=source_sub_id,
            target_subscription_id=source_sub_id,
        )

        resources = [
            {"id": "resource1", "type": "Microsoft.Compute/virtualMachines"},
            {"id": "resource2", "type": "Microsoft.Network/virtualNetworks"},
        ]

        result = filter_instance.filter_resources(resources)

        assert result.resources_before == 2
        assert result.resources_after == 2
        assert result.filtered_count == 0

    def test_filter_role_assignment_with_source_scope(
        self, filter_instance, source_sub_id
    ):
        """Test filtering role assignment with source subscription scope."""
        resources = [
            {
                "id": f"/subscriptions/{source_sub_id}/providers/Microsoft.Authorization/roleAssignments/abc123",
                "type": "Microsoft.Authorization/roleAssignments",
                "properties": {
                    "scope": f"/subscriptions/{source_sub_id}",
                    "roleDefinitionId": "/subscriptions/other/providers/Microsoft.Authorization/roleDefinitions/xyz",
                },
            }
        ]

        result = filter_instance.filter_resources(resources)

        assert result.resources_before == 1
        assert result.resources_after == 0
        assert result.filtered_count == 1

    def test_filter_policy_assignment_with_source_reference(
        self, filter_instance, source_sub_id
    ):
        """Test filtering policy assignment referencing source subscription."""
        resources = [
            {
                "id": "/subscriptions/target/providers/Microsoft.Authorization/policyAssignments/policy1",
                "type": "Microsoft.Authorization/policyAssignments",
                "properties": {
                    "policyDefinitionId": f"/subscriptions/{source_sub_id}/providers/Microsoft.Authorization/policyDefinitions/def1"
                },
            }
        ]

        result = filter_instance.filter_resources(resources)

        assert result.resources_before == 1
        assert result.resources_after == 0
        assert result.filtered_count == 1

    def test_filter_diagnostic_settings_with_source_workspace(
        self, filter_instance, source_sub_id
    ):
        """Test filtering diagnostic settings with source workspace."""
        resources = [
            {
                "id": "/subscriptions/target/resourceGroups/rg1/providers/Microsoft.Insights/diagnosticSettings/diag1",
                "type": "Microsoft.Insights/diagnosticSettings",
                "properties": {
                    "workspaceId": f"/subscriptions/{source_sub_id}/resourceGroups/monitoring/providers/Microsoft.OperationalInsights/workspaces/workspace1"
                },
            }
        ]

        result = filter_instance.filter_resources(resources)

        assert result.resources_before == 1
        assert result.resources_after == 0
        assert result.filtered_count == 1

    def test_keep_valid_resources(self, filter_instance, target_sub_id):
        """Test that valid resources are kept."""
        resources = [
            {
                "id": f"/subscriptions/{target_sub_id}/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
                "type": "Microsoft.Compute/virtualMachines",
                "properties": {"vmSize": "Standard_D2s_v3"},
            },
            {
                "id": f"/subscriptions/{target_sub_id}/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1",
                "type": "Microsoft.Network/virtualNetworks",
                "properties": {"addressSpace": {"addressPrefixes": ["10.0.0.0/16"]}},
            },
        ]

        result = filter_instance.filter_resources(resources)

        assert result.resources_before == 2
        assert result.resources_after == 2
        assert result.filtered_count == 0

    def test_mixed_resources_partial_filtering(
        self, filter_instance, source_sub_id, target_sub_id
    ):
        """Test filtering mixed resources (some filtered, some kept)."""
        resources = [
            {
                "id": f"/subscriptions/{target_sub_id}/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
                "type": "Microsoft.Compute/virtualMachines",
            },
            {
                "id": f"/subscriptions/{source_sub_id}/providers/Microsoft.Authorization/roleAssignments/role1",
                "type": "Microsoft.Authorization/roleAssignments",
                "properties": {"scope": f"/subscriptions/{source_sub_id}"},
            },
            {
                "id": f"/subscriptions/{target_sub_id}/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1",
                "type": "Microsoft.Network/virtualNetworks",
            },
        ]

        result = filter_instance.filter_resources(resources)

        assert result.resources_before == 3
        assert result.resources_after == 2
        assert result.filtered_count == 1

    def test_normalize_subscription_id(self, filter_instance):
        """Test subscription ID normalization."""
        # Test with /subscriptions/ prefix
        normalized = filter_instance._normalize_subscription_id(
            "/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/rg1"
        )
        assert normalized == "11111111-1111-1111-1111-111111111111"

        # Test without prefix
        normalized = filter_instance._normalize_subscription_id(
            "22222222-2222-2222-2222-222222222222"
        )
        assert normalized == "22222222-2222-2222-2222-222222222222"

    def test_get_filter_summary(self, filter_instance):
        """Test filter summary generation."""
        result = FilterResult(
            resources_before=10,
            resources_after=8,
            filter_reasons={
                "resource1": "Filtered due to cross-tenant reference",
                "resource2": "Filtered due to source subscription scope",
            },
        )

        summary = filter_instance.get_filter_summary(result)

        assert "Resources before: 10" in summary
        assert "Resources after: 8" in summary
        assert "Filtered out: 2" in summary
        assert "resource1" in summary
        assert "resource2" in summary

    def test_no_subscription_ids_skips_filtering(self):
        """Test that missing subscription IDs skips filtering."""
        filter_instance = CrossTenantResourceFilter()

        resources = [
            {"id": "resource1", "type": "Microsoft.Compute/virtualMachines"},
        ]

        result = filter_instance.filter_resources(resources)

        assert result.resources_before == 1
        assert result.resources_after == 1
        assert result.filtered_count == 0

    def test_filter_security_pricings(self, filter_instance):
        """Test filtering Security Center pricings (subscription-level)."""
        resources = [
            {
                "id": "/subscriptions/source/providers/Microsoft.Security/pricings/default",
                "type": "Microsoft.Security/pricings",
            }
        ]

        result = filter_instance.filter_resources(resources)

        assert result.resources_before == 1
        assert result.resources_after == 0
        assert result.filtered_count == 1
