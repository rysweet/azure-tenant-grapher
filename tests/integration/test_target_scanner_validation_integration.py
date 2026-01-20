"""
Integration tests for target scanner validation feature (Issue #555).

These tests verify the validation logic works end-to-end with mocked Azure API.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from azure.core.exceptions import ResourceNotFoundError

from src.iac.target_scanner import TargetScannerService
from src.services.azure_discovery_service import AzureDiscoveryService


@pytest.fixture
def mock_credential():
    """Create mock Azure credential."""
    return MagicMock()


@pytest.fixture
def mock_discovery_service(mock_credential):
    """Create mock AzureDiscoveryService for integration testing."""
    service = MagicMock(spec=AzureDiscoveryService)
    service.credential = mock_credential

    # Mock subscription discovery
    service.discover_subscriptions = AsyncMock(
        return_value=[{"id": "test-sub-123", "display_name": "Test Subscription"}]
    )

    # Mock empty role assignments for simplicity
    service.discover_role_assignments_in_subscription = AsyncMock(return_value=[])

    return service


@pytest.fixture
def scanner_service(mock_discovery_service):
    """Create TargetScannerService for integration testing."""
    return TargetScannerService(mock_discovery_service)


@pytest.mark.asyncio
class TestTargetScannerValidationIntegration:
    """Integration tests for validation feature."""

    async def test_simple_scenario_validation_filters_nonexistent_resources(
        self, scanner_service, mock_discovery_service
    ):
        """
        Simple Test: Verify validation filters out non-existent resources.

        Scenario:
        - Discover 2 resources from Azure
        - First resource exists (200 OK)
        - Second resource doesn't exist (404 Not Found)

        Expected: Only first resource in final results
        """
        # Mock resource discovery to return 2 resources
        discovered_resources = [
            {
                "id": "/subscriptions/test-sub-123/resourceGroups/rg-test/providers/Microsoft.Network/virtualNetworks/vnet-exists",
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet-exists",
                "location": "eastus",
                "resource_group": "rg-test",
                "subscription_id": "test-sub-123",
                "properties": {},
                "tags": {},
            },
            {
                "id": "/subscriptions/test-sub-123/resourceGroups/rg-test/providers/Microsoft.Storage/storageAccounts/stale-account",
                "type": "Microsoft.Storage/storageAccounts",
                "name": "stale-account",
                "location": "eastus",
                "resource_group": "rg-test",
                "subscription_id": "test-sub-123",
                "properties": {},
                "tags": {},
            },
        ]

        mock_discovery_service.discover_resources_in_subscription = AsyncMock(
            return_value=discovered_resources
        )

        # Mock validation: first exists, second doesn't
        with patch(
            "src.iac.target_scanner.ResourceManagementClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            # First call succeeds (vnet-exists)
            # Second call raises ResourceNotFoundError (stale-account)
            mock_client.resources.get_by_id.side_effect = [
                MagicMock(),  # Success
                ResourceNotFoundError("Resource not found"),  # Failure
            ]

            # Run scan with validation enabled (default)
            result = await scanner_service.scan_target_tenant(
                tenant_id="test-tenant-id", subscription_id="test-sub-123"
            )

            # Assert: Only first resource should be in results
            assert len(result.resources) == 1
            assert result.resources[0].name == "vnet-exists"

            # Assert: Validation was called twice
            assert mock_client.resources.get_by_id.call_count == 2

    async def test_complex_scenario_mixed_validation_results(
        self, scanner_service, mock_discovery_service
    ):
        """
        Complex Test: Verify validation handles mixed results correctly.

        Scenario:
        - Discover 4 resources from Azure
        - Resource 1: Exists (200 OK)
        - Resource 2: Not found (404)
        - Resource 3: Soft-deleted (410 Gone)
        - Resource 4: Exists (200 OK)

        Expected: Only resources 1 and 4 in final results
        """
        # Mock resource discovery to return 4 resources
        discovered_resources = [
            {
                "id": "/subscriptions/test-sub-123/resourceGroups/rg-test/providers/Microsoft.Network/virtualNetworks/vnet-1",
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet-1",
                "location": "eastus",
                "resource_group": "rg-test",
                "subscription_id": "test-sub-123",
                "properties": {},
                "tags": {},
            },
            {
                "id": "/subscriptions/test-sub-123/resourceGroups/rg-test/providers/Microsoft.Storage/storageAccounts/account-404",
                "type": "Microsoft.Storage/storageAccounts",
                "name": "account-404",
                "location": "eastus",
                "resource_group": "rg-test",
                "subscription_id": "test-sub-123",
                "properties": {},
                "tags": {},
            },
            {
                "id": "/subscriptions/test-sub-123/resourceGroups/rg-test/providers/Microsoft.KeyVault/vaults/vault-410",
                "type": "Microsoft.KeyVault/vaults",
                "name": "vault-410",
                "location": "eastus",
                "resource_group": "rg-test",
                "subscription_id": "test-sub-123",
                "properties": {},
                "tags": {},
            },
            {
                "id": "/subscriptions/test-sub-123/resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/vm-1",
                "type": "Microsoft.Compute/virtualMachines",
                "name": "vm-1",
                "location": "eastus",
                "resource_group": "rg-test",
                "subscription_id": "test-sub-123",
                "properties": {},
                "tags": {},
            },
        ]

        mock_discovery_service.discover_resources_in_subscription = AsyncMock(
            return_value=discovered_resources
        )

        # Mock validation with mixed results
        with patch(
            "src.iac.target_scanner.ResourceManagementClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            from azure.core.exceptions import HttpResponseError

            # Resource 1: Success
            # Resource 2: 404 Not Found
            # Resource 3: 410 Gone
            # Resource 4: Success
            error_410 = HttpResponseError("Resource soft-deleted")
            error_410.status_code = 410

            mock_client.resources.get_by_id.side_effect = [
                MagicMock(),  # vnet-1 exists
                ResourceNotFoundError("Not found"),  # account-404
                error_410,  # vault-410 soft-deleted
                MagicMock(),  # vm-1 exists
            ]

            # Run scan with validation enabled (default)
            result = await scanner_service.scan_target_tenant(
                tenant_id="test-tenant-id",
                subscription_id="test-sub-123",
                validate_existence=True,  # Explicit
            )

            # Assert: Only resources 1 and 4 should be in results
            assert len(result.resources) == 2
            assert result.resources[0].name == "vnet-1"
            assert result.resources[1].name == "vm-1"

            # Assert: Validation was called 4 times
            assert mock_client.resources.get_by_id.call_count == 4

    async def test_validation_disabled_includes_all_resources(
        self, scanner_service, mock_discovery_service
    ):
        """
        Verify that disabling validation includes all discovered resources.

        This ensures backward compatibility and performance optimization path.
        """
        # Mock resource discovery
        discovered_resources = [
            {
                "id": "/subscriptions/test-sub-123/resourceGroups/rg-test/providers/Microsoft.Network/virtualNetworks/vnet-1",
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet-1",
                "location": "eastus",
                "resource_group": "rg-test",
                "subscription_id": "test-sub-123",
                "properties": {},
                "tags": {},
            },
            {
                "id": "/subscriptions/test-sub-123/resourceGroups/rg-test/providers/Microsoft.Storage/storageAccounts/account-2",
                "type": "Microsoft.Storage/storageAccounts",
                "name": "account-2",
                "location": "eastus",
                "resource_group": "rg-test",
                "subscription_id": "test-sub-123",
                "properties": {},
                "tags": {},
            },
        ]

        mock_discovery_service.discover_resources_in_subscription = AsyncMock(
            return_value=discovered_resources
        )

        # Mock validation (should NOT be called)
        with patch(
            "src.iac.target_scanner.ResourceManagementClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            # Run scan with validation DISABLED
            result = await scanner_service.scan_target_tenant(
                tenant_id="test-tenant-id",
                subscription_id="test-sub-123",
                validate_existence=False,  # Disable validation
            )

            # Assert: ALL resources should be in results
            assert len(result.resources) == 2

            # Assert: Validation was NOT called
            mock_client.resources.get_by_id.assert_not_called()
