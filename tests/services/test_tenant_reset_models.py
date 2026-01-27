"""Unit tests for Tenant Reset Models.

Philosophy:
- Test type safety and validation
- Test serialization/deserialization
- Test enum values

Issue #627: Tenant Reset Feature with Granular Scopes
"""

import pytest
from datetime import datetime

from src.services.tenant_reset_models import (
    EntraObjectDeletionResult,
    GraphCleanupResult,
    ResetPreview,
    ResetResult,
    ResetScope,
    ResetStatus,
    ResourceDeletionResult,
    ScopeType,
)


# ========================================================================
# ResetScope Tests
# ========================================================================


def test_reset_scope_tenant_creation():
    """Test creating tenant scope."""
    scope = ResetScope(scope_type=ScopeType.TENANT)
    assert scope.scope_type == ScopeType.TENANT
    assert scope.subscription_id is None
    assert scope.resource_group_name is None
    assert scope.resource_id is None


def test_reset_scope_subscription_creation():
    """Test creating subscription scope."""
    scope = ResetScope(
        scope_type=ScopeType.SUBSCRIPTION,
        subscription_id="sub-12345",
    )
    assert scope.scope_type == ScopeType.SUBSCRIPTION
    assert scope.subscription_id == "sub-12345"


def test_reset_scope_subscription_requires_subscription_id():
    """Test that subscription scope requires subscription_id."""
    with pytest.raises(ValueError, match="subscription_id required"):
        ResetScope(scope_type=ScopeType.SUBSCRIPTION)


def test_reset_scope_resource_group_creation():
    """Test creating resource group scope."""
    scope = ResetScope(
        scope_type=ScopeType.RESOURCE_GROUP,
        subscription_id="sub-12345",
        resource_group_name="rg-test",
    )
    assert scope.scope_type == ScopeType.RESOURCE_GROUP
    assert scope.subscription_id == "sub-12345"
    assert scope.resource_group_name == "rg-test"


def test_reset_scope_resource_group_requires_both_params():
    """Test that resource group scope requires both subscription_id and resource_group_name."""
    with pytest.raises(ValueError):
        ResetScope(scope_type=ScopeType.RESOURCE_GROUP)

    with pytest.raises(ValueError):
        ResetScope(
            scope_type=ScopeType.RESOURCE_GROUP,
            subscription_id="sub-12345",
        )


def test_reset_scope_resource_creation():
    """Test creating resource scope."""
    scope = ResetScope(
        scope_type=ScopeType.RESOURCE,
        resource_id="/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/vm1",
    )
    assert scope.scope_type == ScopeType.RESOURCE
    assert scope.resource_id.startswith("/subscriptions/")


def test_reset_scope_resource_requires_resource_id():
    """Test that resource scope requires resource_id."""
    with pytest.raises(ValueError, match="resource_id required"):
        ResetScope(scope_type=ScopeType.RESOURCE)


def test_reset_scope_to_dict():
    """Test ResetScope serialization to dict."""
    scope = ResetScope(
        scope_type=ScopeType.SUBSCRIPTION,
        subscription_id="sub-12345",
    )
    scope_dict = scope.to_dict()

    assert scope_dict['scope_type'] == 'subscription'
    assert scope_dict['subscription_id'] == 'sub-12345'
    assert scope_dict['resource_group_name'] is None
    assert scope_dict['resource_id'] is None


# ========================================================================
# ResetPreview Tests
# ========================================================================


def test_reset_preview_creation():
    """Test creating ResetPreview."""
    scope = ResetScope(scope_type=ScopeType.TENANT)
    preview = ResetPreview(
        scope=scope,
        azure_resources_count=47,
        entra_users_count=12,
        entra_groups_count=5,
        entra_service_principals_count=8,
        graph_nodes_count=72,
        estimated_duration_seconds=120,
        warnings=["Warning 1", "Warning 2"],
    )

    assert preview.azure_resources_count == 47
    assert preview.entra_users_count == 12
    assert preview.entra_groups_count == 5
    assert preview.entra_service_principals_count == 8
    assert preview.graph_nodes_count == 72
    assert preview.estimated_duration_seconds == 120
    assert len(preview.warnings) == 2


def test_reset_preview_to_dict():
    """Test ResetPreview serialization."""
    scope = ResetScope(scope_type=ScopeType.TENANT)
    preview = ResetPreview(
        scope=scope,
        azure_resources_count=10,
        warnings=["Test warning"],
    )
    preview_dict = preview.to_dict()

    assert preview_dict['azure_resources_count'] == 10
    assert preview_dict['warnings'] == ["Test warning"]
    assert 'scope' in preview_dict


# ========================================================================
# ResetResult Tests
# ========================================================================


def test_reset_result_creation():
    """Test creating ResetResult."""
    scope = ResetScope(scope_type=ScopeType.TENANT)
    result = ResetResult(
        scope=scope,
        status=ResetStatus.COMPLETED,
        deleted_azure_resources=47,
        deleted_entra_users=12,
        errors=[],
        duration_seconds=120.5,
    )

    assert result.status == ResetStatus.COMPLETED
    assert result.deleted_azure_resources == 47
    assert result.deleted_entra_users == 12
    assert result.duration_seconds == 120.5
    assert result.success is True


def test_reset_result_success_property_with_completed_status():
    """Test that success property returns True for completed status with no errors."""
    scope = ResetScope(scope_type=ScopeType.TENANT)
    result = ResetResult(
        scope=scope,
        status=ResetStatus.COMPLETED,
        errors=[],
    )
    assert result.success is True


def test_reset_result_success_property_with_errors():
    """Test that success property returns False when errors exist."""
    scope = ResetScope(scope_type=ScopeType.TENANT)
    result = ResetResult(
        scope=scope,
        status=ResetStatus.COMPLETED,
        errors=["Error 1"],
    )
    assert result.success is False


def test_reset_result_success_property_with_failed_status():
    """Test that success property returns False for failed status."""
    scope = ResetScope(scope_type=ScopeType.TENANT)
    result = ResetResult(
        scope=scope,
        status=ResetStatus.FAILED,
        errors=[],
    )
    assert result.success is False


def test_reset_result_success_property_with_partial_status():
    """Test that success property returns False for partial status."""
    scope = ResetScope(scope_type=ScopeType.TENANT)
    result = ResetResult(
        scope=scope,
        status=ResetStatus.PARTIAL,
        errors=["Partial error"],
    )
    assert result.success is False


def test_reset_result_to_dict():
    """Test ResetResult serialization."""
    scope = ResetScope(scope_type=ScopeType.TENANT)
    started_at = datetime(2026, 1, 27, 12, 0, 0)
    completed_at = datetime(2026, 1, 27, 12, 2, 0)

    result = ResetResult(
        scope=scope,
        status=ResetStatus.COMPLETED,
        deleted_azure_resources=10,
        deleted_entra_users=5,
        errors=[],
        duration_seconds=120.5,
        started_at=started_at,
        completed_at=completed_at,
    )

    result_dict = result.to_dict()

    assert result_dict['status'] == 'completed'
    assert result_dict['success'] is True
    assert result_dict['deleted_azure_resources'] == 10
    assert result_dict['deleted_entra_users'] == 5
    assert result_dict['duration_seconds'] == 120.5
    assert result_dict['started_at'] == '2026-01-27T12:00:00'
    assert result_dict['completed_at'] == '2026-01-27T12:02:00'


# ========================================================================
# ResourceDeletionResult Tests
# ========================================================================


def test_resource_deletion_result_success():
    """Test creating successful ResourceDeletionResult."""
    result = ResourceDeletionResult(
        resource_id="/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/vm1",
        resource_type="Microsoft.Compute/virtualMachines",
        success=True,
        duration_seconds=5.2,
    )

    assert result.success is True
    assert result.error is None
    assert result.duration_seconds == 5.2


def test_resource_deletion_result_failure():
    """Test creating failed ResourceDeletionResult."""
    result = ResourceDeletionResult(
        resource_id="/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Storage/storageAccounts/sa1",
        resource_type="Microsoft.Storage/storageAccounts",
        success=False,
        error="Deletion failed: resource locked",
        duration_seconds=1.0,
    )

    assert result.success is False
    assert result.error == "Deletion failed: resource locked"


# ========================================================================
# EntraObjectDeletionResult Tests
# ========================================================================


def test_entra_object_deletion_result_user():
    """Test creating EntraObjectDeletionResult for user."""
    result = EntraObjectDeletionResult(
        object_id="user-12345",
        object_type="user",
        display_name="Test User",
        success=True,
    )

    assert result.object_type == "user"
    assert result.display_name == "Test User"
    assert result.success is True
    assert result.error is None


def test_entra_object_deletion_result_service_principal():
    """Test creating EntraObjectDeletionResult for service principal."""
    result = EntraObjectDeletionResult(
        object_id="sp-12345",
        object_type="service_principal",
        display_name="Test SP",
        success=False,
        error="Cannot delete ATG service principal",
    )

    assert result.object_type == "service_principal"
    assert result.success is False
    assert result.error == "Cannot delete ATG service principal"


# ========================================================================
# GraphCleanupResult Tests
# ========================================================================


def test_graph_cleanup_result_success():
    """Test creating successful GraphCleanupResult."""
    result = GraphCleanupResult(
        nodes_deleted=47,
        relationships_deleted=120,
        success=True,
        duration_seconds=2.5,
    )

    assert result.nodes_deleted == 47
    assert result.relationships_deleted == 120
    assert result.success is True
    assert result.error is None


def test_graph_cleanup_result_failure():
    """Test creating failed GraphCleanupResult."""
    result = GraphCleanupResult(
        nodes_deleted=0,
        relationships_deleted=0,
        success=False,
        error="Neo4j connection failed",
        duration_seconds=0.1,
    )

    assert result.success is False
    assert result.error == "Neo4j connection failed"


# ========================================================================
# Enum Tests
# ========================================================================


def test_scope_type_enum_values():
    """Test ScopeType enum has expected values."""
    assert ScopeType.TENANT.value == "tenant"
    assert ScopeType.SUBSCRIPTION.value == "subscription"
    assert ScopeType.RESOURCE_GROUP.value == "resource_group"
    assert ScopeType.RESOURCE.value == "resource"


def test_reset_status_enum_values():
    """Test ResetStatus enum has expected values."""
    assert ResetStatus.PENDING.value == "pending"
    assert ResetStatus.RUNNING.value == "running"
    assert ResetStatus.COMPLETED.value == "completed"
    assert ResetStatus.FAILED.value == "failed"
    assert ResetStatus.PARTIAL.value == "partial"
