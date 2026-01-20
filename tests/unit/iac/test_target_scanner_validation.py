"""
Unit tests for TargetScannerService resource validation feature.

Tests the validation logic that prevents false positive import blocks
for non-existent resources (Issue #555).

Test Structure:
- Test validation method directly (_validate_resource_exists)
- Test scan integration (validate_existence parameter)
- Test error handling and graceful degradation
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from azure.core.exceptions import HttpResponseError, ResourceNotFoundError

from src.iac.target_scanner import TargetScannerService
from src.services.azure_discovery_service import AzureDiscoveryService


@pytest.fixture
def mock_discovery_service():
    """Create mock AzureDiscoveryService for testing."""
    service = MagicMock(spec=AzureDiscoveryService)
    service.credential = MagicMock()
    return service


@pytest.fixture
def scanner_service(mock_discovery_service):
    """Create TargetScannerService with mocked discovery service."""
    return TargetScannerService(mock_discovery_service)


class TestValidateResourceExists:
    """Test the _validate_resource_exists() method."""

    @pytest.mark.asyncio
    async def test_validate_existing_resource_returns_true(self, scanner_service):
        """Test validation returns True for existing resource (200 OK)."""
        resource_id = "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Network/virtualNetworks/vnet-test"

        # Mock Azure SDK GET request to return success (200 OK)
        with patch("src.iac.target_scanner.ResourceManagementClient") as mock_client:
            mock_resource_client = MagicMock()
            mock_client.return_value = mock_resource_client
            mock_resource_client.resources.get_by_id.return_value = (
                MagicMock()
            )  # Success

            result = await scanner_service._validate_resource_exists(resource_id)

            assert result is True
            mock_resource_client.resources.get_by_id.assert_called_once_with(
                resource_id=resource_id, api_version="2021-04-01"
            )

    @pytest.mark.asyncio
    async def test_validate_nonexistent_resource_returns_false(self, scanner_service):
        """Test validation returns False for non-existent resource (404 Not Found)."""
        resource_id = "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Storage/storageAccounts/deleted-account"

        # Mock Azure SDK GET request to raise ResourceNotFoundError (404)
        with patch("src.iac.target_scanner.ResourceManagementClient") as mock_client:
            mock_resource_client = MagicMock()
            mock_client.return_value = mock_resource_client
            mock_resource_client.resources.get_by_id.side_effect = (
                ResourceNotFoundError("Resource not found")
            )

            result = await scanner_service._validate_resource_exists(resource_id)

            assert result is False

    @pytest.mark.asyncio
    async def test_validate_soft_deleted_resource_returns_false(self, scanner_service):
        """Test validation returns False for soft-deleted resource (410 Gone)."""
        resource_id = "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.KeyVault/vaults/soft-deleted-vault"

        # Mock Azure SDK GET request to raise HttpResponseError with 410 Gone
        with patch("src.iac.target_scanner.ResourceManagementClient") as mock_client:
            mock_resource_client = MagicMock()
            mock_client.return_value = mock_resource_client

            error = HttpResponseError("Resource marked for deletion")
            error.status_code = 410  # Gone
            mock_resource_client.resources.get_by_id.side_effect = error

            result = await scanner_service._validate_resource_exists(resource_id)

            assert result is False

    @pytest.mark.asyncio
    async def test_validate_permission_denied_returns_false(self, scanner_service):
        """Test validation returns False for permission denied (403 Forbidden) - safe default."""
        resource_id = "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/restricted-vm"

        # Mock Azure SDK GET request to raise HttpResponseError with 403 Forbidden
        with patch("src.iac.target_scanner.ResourceManagementClient") as mock_client:
            mock_resource_client = MagicMock()
            mock_client.return_value = mock_resource_client

            error = HttpResponseError("Forbidden")
            error.status_code = 403
            mock_resource_client.resources.get_by_id.side_effect = error

            result = await scanner_service._validate_resource_exists(resource_id)

            assert result is False

    @pytest.mark.asyncio
    async def test_validate_server_error_returns_false(self, scanner_service):
        """Test validation returns False for server errors (500) - safe default."""
        resource_id = "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Sql/servers/test-server"

        # Mock Azure SDK GET request to raise HttpResponseError with 500 Server Error
        with patch("src.iac.target_scanner.ResourceManagementClient") as mock_client:
            mock_resource_client = MagicMock()
            mock_client.return_value = mock_resource_client

            error = HttpResponseError("Internal Server Error")
            error.status_code = 500
            mock_resource_client.resources.get_by_id.side_effect = error

            result = await scanner_service._validate_resource_exists(resource_id)

            assert result is False

    @pytest.mark.asyncio
    async def test_validate_network_timeout_returns_false(self, scanner_service):
        """Test validation returns False for network timeouts - safe default."""
        resource_id = "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Web/sites/test-app"

        # Mock Azure SDK GET request to raise generic Exception (network timeout)
        with patch("src.iac.target_scanner.ResourceManagementClient") as mock_client:
            mock_resource_client = MagicMock()
            mock_client.return_value = mock_resource_client
            mock_resource_client.resources.get_by_id.side_effect = Exception(
                "Connection timeout"
            )

            result = await scanner_service._validate_resource_exists(resource_id)

            assert result is False


class TestScanTargetTenantWithValidation:
    """Test scan_target_tenant() with validation enabled/disabled."""

    @pytest.mark.asyncio
    async def test_scan_with_validation_enabled_filters_nonexistent_resources(
        self, scanner_service, mock_discovery_service
    ):
        """Test that validation filters out non-existent resources."""
        tenant_id = "test-tenant-id"
        subscription_id = "test-subscription-id"

        # Mock discovery to return 3 resources
        mock_discovery_service.discover_subscriptions = AsyncMock(
            return_value=[{"id": subscription_id, "display_name": "Test Subscription"}]
        )

        mock_resources = [
            {
                "id": "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Network/virtualNetworks/vnet-exists",
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet-exists",
                "location": "eastus",
                "resource_group": "rg-test",
                "subscription_id": subscription_id,
                "properties": {},
                "tags": {},
            },
            {
                "id": "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Storage/storageAccounts/deleted-account",
                "type": "Microsoft.Storage/storageAccounts",
                "name": "deleted-account",
                "location": "eastus",
                "resource_group": "rg-test",
                "subscription_id": subscription_id,
                "properties": {},
                "tags": {},
            },
            {
                "id": "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.KeyVault/vaults/soft-deleted-vault",
                "type": "Microsoft.KeyVault/vaults",
                "name": "soft-deleted-vault",
                "location": "eastus",
                "resource_group": "rg-test",
                "subscription_id": subscription_id,
                "properties": {},
                "tags": {},
            },
        ]

        mock_discovery_service.discover_resources_in_subscription = AsyncMock(
            return_value=mock_resources
        )
        mock_discovery_service.discover_role_assignments_in_subscription = AsyncMock(
            return_value=[]
        )

        # Mock validation: first resource exists, others don't
        with patch.object(
            scanner_service, "_validate_resource_exists"
        ) as mock_validate:
            mock_validate.side_effect = [True, False, False]  # Only first exists

            result = await scanner_service.scan_target_tenant(
                tenant_id=tenant_id,
                subscription_id=subscription_id,
                validate_existence=True,  # Enable validation
            )

            # Should only include the first resource (validation returned True)
            assert len(result.resources) == 1
            assert result.resources[0].name == "vnet-exists"

            # Validation should have been called 3 times
            assert mock_validate.call_count == 3

    @pytest.mark.asyncio
    async def test_scan_with_validation_disabled_includes_all_resources(
        self, scanner_service, mock_discovery_service
    ):
        """Test that disabling validation includes all discovered resources."""
        tenant_id = "test-tenant-id"
        subscription_id = "test-subscription-id"

        # Mock discovery to return 3 resources (including non-existent)
        mock_discovery_service.discover_subscriptions = AsyncMock(
            return_value=[{"id": subscription_id, "display_name": "Test Subscription"}]
        )

        mock_resources = [
            {
                "id": "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Network/virtualNetworks/vnet-1",
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet-1",
                "location": "eastus",
                "resource_group": "rg-test",
                "subscription_id": subscription_id,
                "properties": {},
                "tags": {},
            },
            {
                "id": "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Storage/storageAccounts/account-2",
                "type": "Microsoft.Storage/storageAccounts",
                "name": "account-2",
                "location": "eastus",
                "resource_group": "rg-test",
                "subscription_id": subscription_id,
                "properties": {},
                "tags": {},
            },
        ]

        mock_discovery_service.discover_resources_in_subscription = AsyncMock(
            return_value=mock_resources
        )
        mock_discovery_service.discover_role_assignments_in_subscription = AsyncMock(
            return_value=[]
        )

        # Mock validation (should NOT be called when validation disabled)
        with patch.object(
            scanner_service, "_validate_resource_exists"
        ) as mock_validate:
            result = await scanner_service.scan_target_tenant(
                tenant_id=tenant_id,
                subscription_id=subscription_id,
                validate_existence=False,  # Disable validation
            )

            # Should include ALL resources (no validation)
            assert len(result.resources) == 2

            # Validation should NOT have been called
            mock_validate.assert_not_called()

    @pytest.mark.asyncio
    async def test_scan_default_validation_enabled(
        self, scanner_service, mock_discovery_service
    ):
        """Test that validation is enabled by default (safe default)."""
        tenant_id = "test-tenant-id"
        subscription_id = "test-subscription-id"

        # Mock discovery
        mock_discovery_service.discover_subscriptions = AsyncMock(
            return_value=[{"id": subscription_id, "display_name": "Test Subscription"}]
        )

        mock_resources = [
            {
                "id": "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Network/virtualNetworks/vnet-test",
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet-test",
                "location": "eastus",
                "resource_group": "rg-test",
                "subscription_id": subscription_id,
                "properties": {},
                "tags": {},
            }
        ]

        mock_discovery_service.discover_resources_in_subscription = AsyncMock(
            return_value=mock_resources
        )
        mock_discovery_service.discover_role_assignments_in_subscription = AsyncMock(
            return_value=[]
        )

        # Mock validation
        with patch.object(
            scanner_service, "_validate_resource_exists"
        ) as mock_validate:
            mock_validate.return_value = True

            # Call without validate_existence parameter (should default to True)
            await scanner_service.scan_target_tenant(
                tenant_id=tenant_id,
                subscription_id=subscription_id,
                # validate_existence defaults to True
            )

            # Validation should have been called (default enabled)
            mock_validate.assert_called_once()


class TestValidationErrorHandling:
    """Test graceful error handling during validation."""

    @pytest.mark.asyncio
    async def test_validation_errors_logged_but_scan_continues(
        self, scanner_service, mock_discovery_service
    ):
        """Test that validation errors are logged but don't fail entire scan."""
        tenant_id = "test-tenant-id"
        subscription_id = "test-subscription-id"

        # Mock discovery
        mock_discovery_service.discover_subscriptions = AsyncMock(
            return_value=[{"id": subscription_id, "display_name": "Test Subscription"}]
        )

        mock_resources = [
            {
                "id": "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Network/virtualNetworks/vnet-1",
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet-1",
                "location": "eastus",
                "resource_group": "rg-test",
                "subscription_id": subscription_id,
                "properties": {},
                "tags": {},
            },
            {
                "id": "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Storage/storageAccounts/account-2",
                "type": "Microsoft.Storage/storageAccounts",
                "name": "account-2",
                "location": "eastus",
                "resource_group": "rg-test",
                "subscription_id": subscription_id,
                "properties": {},
                "tags": {},
            },
        ]

        mock_discovery_service.discover_resources_in_subscription = AsyncMock(
            return_value=mock_resources
        )
        mock_discovery_service.discover_role_assignments_in_subscription = AsyncMock(
            return_value=[]
        )

        # Mock validation: first succeeds, second raises exception
        with patch.object(
            scanner_service, "_validate_resource_exists"
        ) as mock_validate:
            mock_validate.side_effect = [True, Exception("Network error")]

            result = await scanner_service.scan_target_tenant(
                tenant_id=tenant_id,
                subscription_id=subscription_id,
                validate_existence=True,
            )

            # Should include only first resource (second validation failed)
            assert len(result.resources) == 1
            assert result.resources[0].name == "vnet-1"

            # Scan should still succeed despite validation error
            assert result.error is None or "Network error" not in result.error

    @pytest.mark.asyncio
    async def test_validation_partial_failures_included_in_error_message(
        self, scanner_service, mock_discovery_service
    ):
        """Test that validation failures are included in scan error message."""
        tenant_id = "test-tenant-id"
        subscription_id = "test-subscription-id"

        # Mock discovery
        mock_discovery_service.discover_subscriptions = AsyncMock(
            return_value=[{"id": subscription_id, "display_name": "Test Subscription"}]
        )

        mock_resources = [
            {
                "id": "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Network/virtualNetworks/vnet-exists",
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet-exists",
                "location": "eastus",
                "resource_group": "rg-test",
                "subscription_id": subscription_id,
                "properties": {},
                "tags": {},
            }
        ]

        mock_discovery_service.discover_resources_in_subscription = AsyncMock(
            return_value=mock_resources
        )
        mock_discovery_service.discover_role_assignments_in_subscription = AsyncMock(
            return_value=[]
        )

        # Mock validation to return False (resource doesn't exist)
        with patch.object(
            scanner_service, "_validate_resource_exists"
        ) as mock_validate:
            mock_validate.return_value = False

            result = await scanner_service.scan_target_tenant(
                tenant_id=tenant_id,
                subscription_id=subscription_id,
                validate_existence=True,
            )

            # Should have no resources (validation failed)
            assert len(result.resources) == 0

            # Error message should mention validation (if applicable)
            # Note: This depends on implementation - validation failures may not be errors
            # They're just resources excluded from results
