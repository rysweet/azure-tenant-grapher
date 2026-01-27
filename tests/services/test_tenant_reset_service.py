"""Unit tests for Tenant Reset Service.

Philosophy:
- Comprehensive safety testing
- Mock all Azure/Entra/Neo4j operations
- Verify ATG SP preservation in all scenarios
- Test confirmation token validation

Issue #627: Tenant Reset Feature with Granular Scopes
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from src.services.tenant_reset_service import (
    CONFIRMATION_TOKEN,
    InvalidConfirmationTokenError,
    TenantResetService,
)
from src.services.tenant_reset_models import (
    ResetScope,
    ResetStatus,
    ScopeType,
)


@pytest.fixture
def mock_credential():
    """Mock Azure credential."""
    return Mock()


@pytest.fixture
def mock_graph_client():
    """Mock Microsoft Graph API client."""
    return AsyncMock()


@pytest.fixture
def mock_neo4j_driver():
    """Mock Neo4j driver."""
    driver = AsyncMock()
    session = AsyncMock()
    driver.session.return_value.__aenter__.return_value = session
    return driver


@pytest.fixture
def atg_sp_id():
    """ATG service principal ID to preserve."""
    return "atg-sp-12345678-1234-1234-1234-123456789abc"


@pytest.fixture
def tenant_reset_service(mock_credential, mock_graph_client, mock_neo4j_driver, atg_sp_id):
    """Create TenantResetService instance with mocks."""
    return TenantResetService(
        azure_credential=mock_credential,
        graph_client=mock_graph_client,
        neo4j_driver=mock_neo4j_driver,
        atg_sp_id=atg_sp_id,
        dry_run=False,
    )


# ========================================================================
# Confirmation Token Validation Tests
# ========================================================================


@pytest.mark.asyncio
async def test_execute_tenant_reset_requires_exact_confirmation_token(tenant_reset_service):
    """Test that execution requires exact confirmation token 'DELETE'."""
    # Wrong token
    with pytest.raises(InvalidConfirmationTokenError):
        await tenant_reset_service.execute_tenant_reset(confirmation_token="delete")

    # Wrong token (uppercase but different)
    with pytest.raises(InvalidConfirmationTokenError):
        await tenant_reset_service.execute_tenant_reset(confirmation_token="CONFIRM")

    # Empty token
    with pytest.raises(InvalidConfirmationTokenError):
        await tenant_reset_service.execute_tenant_reset(confirmation_token="")

    # Partial match
    with pytest.raises(InvalidConfirmationTokenError):
        await tenant_reset_service.execute_tenant_reset(confirmation_token="DEL")


@pytest.mark.asyncio
async def test_execute_subscription_reset_requires_exact_confirmation_token(tenant_reset_service):
    """Test that subscription reset requires exact confirmation token."""
    with pytest.raises(InvalidConfirmationTokenError):
        await tenant_reset_service.execute_subscription_reset(
            subscription_id="sub-123", confirmation_token="wrong"
        )


@pytest.mark.asyncio
async def test_execute_resource_group_reset_requires_exact_confirmation_token(tenant_reset_service):
    """Test that resource group reset requires exact confirmation token."""
    with pytest.raises(InvalidConfirmationTokenError):
        await tenant_reset_service.execute_resource_group_reset(
            subscription_id="sub-123", rg_name="rg-test", confirmation_token="wrong"
        )


@pytest.mark.asyncio
async def test_execute_resource_reset_requires_exact_confirmation_token(tenant_reset_service):
    """Test that resource reset requires exact confirmation token."""
    with pytest.raises(InvalidConfirmationTokenError):
        await tenant_reset_service.execute_resource_reset(
            resource_id="/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/vm1",
            confirmation_token="wrong",
        )


# ========================================================================
# ATG Service Principal Preservation Tests (CRITICAL SAFETY)
# ========================================================================


def test_is_atg_service_principal_identifies_correctly(tenant_reset_service, atg_sp_id):
    """Test that ATG SP is correctly identified."""
    # Should identify ATG SP
    assert tenant_reset_service._is_atg_service_principal(atg_sp_id) is True

    # Should not identify other SPs
    assert tenant_reset_service._is_atg_service_principal("other-sp-12345") is False
    assert tenant_reset_service._is_atg_service_principal("") is False


@pytest.mark.asyncio
async def test_delete_entra_service_principals_preserves_atg_sp(
    tenant_reset_service, atg_sp_id, mock_graph_client
):
    """Test that ATG SP is NEVER deleted when deleting service principals."""
    # Mock service principals response including ATG SP
    mock_sp1 = Mock()
    mock_sp1.id = "sp-1"
    mock_sp1.display_name = "Regular SP 1"

    mock_sp_atg = Mock()
    mock_sp_atg.id = atg_sp_id
    mock_sp_atg.display_name = "ATG Service Principal"

    mock_sp2 = Mock()
    mock_sp2.id = "sp-2"
    mock_sp2.display_name = "Regular SP 2"

    mock_response = Mock()
    mock_response.value = [mock_sp1, mock_sp_atg, mock_sp2]
    mock_graph_client.service_principals.get.return_value = mock_response

    # Mock successful deletion for by_service_principal_id chain
    mock_sp_resource = Mock()
    mock_sp_resource.delete = AsyncMock()
    mock_graph_client.service_principals.by_service_principal_id = Mock(return_value=mock_sp_resource)

    # Execute deletion
    results = await tenant_reset_service._delete_entra_service_principals()

    # Verify ATG SP was filtered out (correct behavior: filtered SPs are not in results)
    # Should have 2 results (2 successful deletions, ATG SP was filtered out before deletion)
    assert len(results) == 2

    # Verify ATG SP is not in results (it was filtered out)
    atg_sp_results = [r for r in results if r.object_id == atg_sp_id]
    assert len(atg_sp_results) == 0, "ATG SP should have been filtered out"

    # Verify only non-ATG SPs were deleted successfully
    assert all(r.success for r in results), "All non-ATG SPs should be deleted successfully"
    assert all(r.object_id != atg_sp_id for r in results), "ATG SP should not be in results"
    assert all(r.object_id in ["sp-1", "sp-2"] for r in results), "Only non-ATG SPs should be in results"


@pytest.mark.asyncio
async def test_preview_tenant_reset_warns_if_atg_sp_not_configured():
    """Test that preview warns if ATG SP ID is not configured."""
    service = TenantResetService(
        azure_credential=Mock(),
        graph_client=AsyncMock(),
        neo4j_driver=AsyncMock(),
        atg_sp_id=None,  # Not configured
        dry_run=False,
    )

    # Mock count methods
    with patch.object(service, '_count_azure_resources', return_value=10):
        with patch.object(service, '_count_entra_objects', return_value=(5, 3, 2)):
            with patch.object(service, '_count_graph_nodes', return_value=20):
                preview = await service.preview_tenant_reset()

    # Should have warning about ATG SP preservation
    assert any("ATG service principal ID not configured" in w for w in preview.warnings)


# ========================================================================
# Dry-Run Mode Tests
# ========================================================================


@pytest.mark.asyncio
async def test_dry_run_mode_does_not_delete_resources():
    """Test that dry-run mode prevents actual deletion."""
    service = TenantResetService(
        azure_credential=Mock(),
        graph_client=AsyncMock(),
        neo4j_driver=AsyncMock(),
        atg_sp_id="atg-sp-123",
        dry_run=True,  # Enable dry-run
    )

    # Mock count methods
    with patch.object(service, '_count_azure_resources', return_value=10):
        with patch.object(service, '_count_entra_objects', return_value=(5, 3, 2)):
            with patch.object(service, '_count_graph_nodes', return_value=20):
                # Execute should complete without actual deletion
                result = await service.execute_tenant_reset(confirmation_token=CONFIRMATION_TOKEN)

    # Should have zero deletions (dry-run)
    assert result.deleted_azure_resources == 0
    assert result.deleted_entra_users == 0
    assert result.deleted_entra_groups == 0
    assert result.deleted_entra_service_principals == 0


# ========================================================================
# Preview Tests
# ========================================================================


@pytest.mark.asyncio
async def test_preview_tenant_reset_returns_accurate_counts(tenant_reset_service):
    """Test that preview returns accurate resource counts."""
    # Mock count methods
    with patch.object(tenant_reset_service, '_count_azure_resources', return_value=47):
        with patch.object(tenant_reset_service, '_count_entra_objects', return_value=(12, 5, 8)):
            with patch.object(tenant_reset_service, '_count_graph_nodes', return_value=72):
                preview = await tenant_reset_service.preview_tenant_reset()

    assert preview.azure_resources_count == 47
    assert preview.entra_users_count == 12
    assert preview.entra_groups_count == 5
    assert preview.entra_service_principals_count == 8
    assert preview.graph_nodes_count == 72
    assert preview.estimated_duration_seconds > 0
    assert len(preview.warnings) > 0


@pytest.mark.asyncio
async def test_preview_subscription_reset_returns_accurate_counts(tenant_reset_service):
    """Test that subscription preview returns accurate counts."""
    subscription_id = "sub-12345678-1234-1234-1234-123456789abc"

    with patch.object(tenant_reset_service, '_count_azure_resources', return_value=25):
        with patch.object(tenant_reset_service, '_count_graph_nodes', return_value=30):
            preview = await tenant_reset_service.preview_subscription_reset(
                subscription_id=subscription_id
            )

    assert preview.azure_resources_count == 25
    assert preview.graph_nodes_count == 30
    assert preview.entra_users_count == 0  # Subscription scope doesn't affect Entra
    assert preview.scope.subscription_id == subscription_id


@pytest.mark.asyncio
async def test_preview_resource_group_reset_returns_accurate_counts(tenant_reset_service):
    """Test that resource group preview returns accurate counts."""
    subscription_id = "sub-12345"
    rg_name = "rg-test"

    with patch.object(tenant_reset_service, '_count_azure_resources', return_value=15):
        with patch.object(tenant_reset_service, '_count_graph_nodes', return_value=18):
            preview = await tenant_reset_service.preview_resource_group_reset(
                subscription_id=subscription_id, rg_name=rg_name
            )

    assert preview.azure_resources_count == 15
    assert preview.graph_nodes_count == 18
    assert preview.scope.subscription_id == subscription_id
    assert preview.scope.resource_group_name == rg_name


@pytest.mark.asyncio
async def test_preview_resource_reset_returns_correct_counts(tenant_reset_service):
    """Test that resource preview returns correct counts."""
    resource_id = "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/vm1"

    preview = await tenant_reset_service.preview_resource_reset(resource_id=resource_id)

    assert preview.azure_resources_count == 1
    assert preview.graph_nodes_count == 1
    assert preview.scope.resource_id == resource_id


# ========================================================================
# Scope Validation Tests
# ========================================================================


def test_reset_scope_validates_subscription_scope():
    """Test that subscription scope requires subscription_id."""
    with pytest.raises(ValueError, match="subscription_id required"):
        ResetScope(scope_type=ScopeType.SUBSCRIPTION)


def test_reset_scope_validates_resource_group_scope():
    """Test that resource group scope requires subscription_id and resource_group_name."""
    with pytest.raises(ValueError, match="subscription_id and resource_group_name required"):
        ResetScope(scope_type=ScopeType.RESOURCE_GROUP)

    with pytest.raises(ValueError, match="subscription_id and resource_group_name required"):
        ResetScope(
            scope_type=ScopeType.RESOURCE_GROUP,
            subscription_id="sub-123",
        )


def test_reset_scope_validates_resource_scope():
    """Test that resource scope requires resource_id."""
    with pytest.raises(ValueError, match="resource_id required"):
        ResetScope(scope_type=ScopeType.RESOURCE)


def test_reset_scope_tenant_requires_no_parameters():
    """Test that tenant scope doesn't require additional parameters."""
    scope = ResetScope(scope_type=ScopeType.TENANT)
    assert scope.scope_type == ScopeType.TENANT
    assert scope.subscription_id is None
    assert scope.resource_group_name is None
    assert scope.resource_id is None


# ========================================================================
# Result Tests
# ========================================================================


def test_reset_result_success_property():
    """Test that ResetResult.success property works correctly."""
    from src.services.tenant_reset_models import ResetResult

    # Successful result
    result = ResetResult(
        scope=ResetScope(scope_type=ScopeType.TENANT),
        status=ResetStatus.COMPLETED,
        errors=[],
    )
    assert result.success is True

    # Failed result
    result = ResetResult(
        scope=ResetScope(scope_type=ScopeType.TENANT),
        status=ResetStatus.FAILED,
        errors=["Error 1"],
    )
    assert result.success is False

    # Partial result
    result = ResetResult(
        scope=ResetScope(scope_type=ScopeType.TENANT),
        status=ResetStatus.PARTIAL,
        errors=["Error 1"],
    )
    assert result.success is False


def test_reset_result_to_dict_serialization():
    """Test that ResetResult can be serialized to dict."""
    from datetime import datetime
    from src.services.tenant_reset_models import ResetResult

    result = ResetResult(
        scope=ResetScope(scope_type=ScopeType.TENANT),
        status=ResetStatus.COMPLETED,
        deleted_azure_resources=10,
        deleted_entra_users=5,
        errors=[],
        duration_seconds=120.5,
        started_at=datetime(2026, 1, 27, 12, 0, 0),
        completed_at=datetime(2026, 1, 27, 12, 2, 0),
    )

    result_dict = result.to_dict()

    assert result_dict['status'] == 'completed'
    assert result_dict['success'] is True
    assert result_dict['deleted_azure_resources'] == 10
    assert result_dict['deleted_entra_users'] == 5
    assert result_dict['duration_seconds'] == 120.5
    assert result_dict['started_at'] is not None
    assert result_dict['completed_at'] is not None


# ========================================================================
# Error Handling Tests
# ========================================================================


@pytest.mark.asyncio
async def test_execute_handles_azure_resource_deletion_errors_gracefully(tenant_reset_service):
    """Test that execution handles Azure deletion errors gracefully."""
    # Mock count methods
    with patch.object(tenant_reset_service, '_count_azure_resources', return_value=5):
        with patch.object(tenant_reset_service, '_count_entra_objects', return_value=(0, 0, 0)):
            with patch.object(tenant_reset_service, '_count_graph_nodes', return_value=5):
                # Mock deletion to raise error
                with patch.object(
                    tenant_reset_service,
                    '_delete_azure_resources',
                    side_effect=Exception("Azure API error"),
                ):
                    result = await tenant_reset_service.execute_tenant_reset(
                        confirmation_token=CONFIRMATION_TOKEN
                    )

    # Should capture error
    assert result.status == ResetStatus.FAILED
    assert len(result.errors) > 0
    assert any("Azure API error" in error for error in result.errors)


@pytest.mark.asyncio
async def test_execute_continues_after_partial_azure_deletion_failure(tenant_reset_service):
    """Test that execution continues to graph cleanup even if some Azure deletions fail."""
    from src.services.tenant_reset_models import ResourceDeletionResult

    # Mock count methods
    with patch.object(tenant_reset_service, '_count_azure_resources', return_value=3):
        with patch.object(tenant_reset_service, '_count_entra_objects', return_value=(0, 0, 0)):
            with patch.object(tenant_reset_service, '_count_graph_nodes', return_value=3):
                # Mock partial deletion failure
                mock_results = [
                    ResourceDeletionResult(
                        resource_id="res-1",
                        resource_type="VM",
                        success=True,
                    ),
                    ResourceDeletionResult(
                        resource_id="res-2",
                        resource_type="Storage",
                        success=False,
                        error="Deletion failed",
                    ),
                    ResourceDeletionResult(
                        resource_id="res-3",
                        resource_type="Network",
                        success=True,
                    ),
                ]
                with patch.object(
                    tenant_reset_service, '_delete_azure_resources', return_value=mock_results
                ):
                    with patch.object(
                        tenant_reset_service,
                        '_delete_entra_objects',
                        return_value=[],
                    ):
                        with patch.object(
                            tenant_reset_service,
                            '_cleanup_graph_data',
                            return_value=Mock(
                                nodes_deleted=3,
                                relationships_deleted=0,
                                success=True,
                            ),
                        ):
                            result = await tenant_reset_service.execute_tenant_reset(
                                confirmation_token=CONFIRMATION_TOKEN
                            )

    # Should be partial success
    assert result.status == ResetStatus.PARTIAL
    assert result.deleted_azure_resources == 2  # 2 successful out of 3
    assert result.deleted_graph_nodes == 3  # Graph cleanup still executed
    assert len(result.errors) == 1  # One error captured
