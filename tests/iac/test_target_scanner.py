"""
Unit tests for Target Scanner Service

Tests the TargetScannerService's ability to scan target tenants and discover resources
without persisting to Neo4j.
"""

from datetime import datetime
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.iac.target_scanner import (
    TargetResource,
    TargetScannerService,
    TargetScanResult,
)


@pytest.fixture
def mock_discovery_service():
    """Create a mock AzureDiscoveryService."""
    service = MagicMock()
    service.credential = MagicMock()
    service.discover_subscriptions = AsyncMock()
    service.discover_resources_in_subscription = AsyncMock()
    service.discover_role_assignments_in_subscription = AsyncMock()
    return service


@pytest.fixture
def sample_subscriptions() -> List[Dict[str, Any]]:
    """Sample subscription data."""
    return [
        {"id": "sub-123", "display_name": "Production"},
        {"id": "sub-456", "display_name": "Development"},
    ]


@pytest.fixture
def sample_resources() -> List[Dict[str, Any]]:
    """Sample resource data in Azure API format."""
    return [
        {
            "id": "/subscriptions/sub-123/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "location": "eastus",
            "resource_group": "rg1",
            "subscription_id": "sub-123",
            "properties": {
                "hardwareProfile": {"vmSize": "Standard_D2s_v3"},
                "osProfile": {"computerName": "vm1"},
            },
            "tags": {"environment": "production", "owner": "team-a"},
        },
        {
            "id": "/subscriptions/sub-123/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1",
            "name": "vnet1",
            "type": "Microsoft.Network/virtualNetworks",
            "location": "eastus",
            "resource_group": "rg1",
            "subscription_id": "sub-123",
            "properties": {
                "addressSpace": {"addressPrefixes": ["10.0.0.0/16"]},
            },
            "tags": {},
        },
    ]


@pytest.fixture
def sample_role_assignments() -> List[Dict[str, Any]]:
    """Sample role assignment data in Azure API format."""
    return [
        {
            "id": "/subscriptions/sub-123/providers/Microsoft.Authorization/roleAssignments/assignment-1",
            "name": "assignment-1",
            "type": "Microsoft.Authorization/roleAssignments",
            "location": None,
            "resource_group": "",
            "subscription_id": "sub-123",
            "properties": {
                "principalId": "principal-123",
                "principalType": "ServicePrincipal",
                "roleDefinitionId": "/subscriptions/sub-123/providers/Microsoft.Authorization/roleDefinitions/contributor",
                "scope": "/subscriptions/sub-123",
            },
            "tags": {},
        },
        {
            "id": "/subscriptions/sub-123/resourceGroups/rg1/providers/Microsoft.Authorization/roleAssignments/assignment-2",
            "name": "assignment-2",
            "type": "Microsoft.Authorization/roleAssignments",
            "location": None,
            "resource_group": "rg1",
            "subscription_id": "sub-123",
            "properties": {
                "principalId": "principal-456",
                "principalType": "User",
                "roleDefinitionId": "/subscriptions/sub-123/providers/Microsoft.Authorization/roleDefinitions/reader",
                "scope": "/subscriptions/sub-123/resourceGroups/rg1",
            },
            "tags": {},
        },
    ]


class TestTargetResource:
    """Test TargetResource dataclass."""

    def test_target_resource_creation(self):
        """Test creating a TargetResource with all fields."""
        resource = TargetResource(
            id="/subscriptions/sub-123/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            type="Microsoft.Compute/virtualMachines",
            name="vm1",
            location="eastus",
            resource_group="rg1",
            subscription_id="sub-123",
            properties={"vmSize": "Standard_D2s_v3"},
            tags={"env": "prod"},
        )

        assert resource.id.endswith("vm1")
        assert resource.type == "Microsoft.Compute/virtualMachines"
        assert resource.name == "vm1"
        assert resource.location == "eastus"
        assert resource.resource_group == "rg1"
        assert resource.subscription_id == "sub-123"
        assert resource.properties["vmSize"] == "Standard_D2s_v3"
        assert resource.tags["env"] == "prod"

    def test_target_resource_defaults(self):
        """Test TargetResource with default values."""
        resource = TargetResource(
            id="test-id",
            type="test-type",
            name="test-name",
            location="eastus",
            resource_group="rg1",
            subscription_id="sub-123",
        )

        assert resource.properties == {}
        assert resource.tags == {}


class TestTargetScanResult:
    """Test TargetScanResult dataclass."""

    def test_scan_result_success(self):
        """Test creating a successful scan result."""
        resources = [
            TargetResource(
                id="test-id",
                type="test-type",
                name="test-name",
                location="eastus",
                resource_group="rg1",
                subscription_id="sub-123",
            )
        ]

        result = TargetScanResult(
            tenant_id="tenant-123",
            subscription_id="sub-123",
            resources=resources,
            scan_timestamp="2025-01-15T10:00:00Z",
            error=None,
        )

        assert result.tenant_id == "tenant-123"
        assert result.subscription_id == "sub-123"
        assert len(result.resources) == 1
        assert result.scan_timestamp == "2025-01-15T10:00:00Z"
        assert result.error is None

    def test_scan_result_with_error(self):
        """Test creating a scan result with error."""
        result = TargetScanResult(
            tenant_id="tenant-123",
            subscription_id=None,
            resources=[],
            scan_timestamp="2025-01-15T10:00:00Z",
            error="Failed to authenticate",
        )

        assert result.tenant_id == "tenant-123"
        assert result.subscription_id is None
        assert len(result.resources) == 0
        assert result.error == "Failed to authenticate"


class TestTargetScannerService:
    """Test TargetScannerService."""

    @pytest.mark.asyncio
    async def test_scan_single_subscription_success(
        self, mock_discovery_service, sample_resources
    ):
        """Test successful scan of a single subscription."""
        # Setup mocks
        mock_discovery_service.discover_resources_in_subscription.return_value = (
            sample_resources
        )

        # Create service and scan
        scanner = TargetScannerService(mock_discovery_service)
        result = await scanner.scan_target_tenant(
            tenant_id="tenant-123", subscription_id="sub-123"
        )

        # Verify result
        assert result.tenant_id == "tenant-123"
        assert result.subscription_id == "sub-123"
        assert len(result.resources) == 2
        assert result.error is None

        # Verify resources were converted correctly
        assert result.resources[0].name == "vm1"
        assert result.resources[0].type == "Microsoft.Compute/virtualMachines"
        assert result.resources[1].name == "vnet1"
        assert result.resources[1].type == "Microsoft.Network/virtualNetworks"

        # Verify discovery service was called correctly
        mock_discovery_service.discover_resources_in_subscription.assert_called_once_with(
            "sub-123"
        )

    @pytest.mark.asyncio
    async def test_scan_all_subscriptions_success(
        self, mock_discovery_service, sample_subscriptions, sample_resources
    ):
        """Test successful scan of all subscriptions in tenant."""
        # Setup mocks
        mock_discovery_service.discover_subscriptions.return_value = (
            sample_subscriptions
        )
        mock_discovery_service.discover_resources_in_subscription.return_value = (
            sample_resources
        )

        # Create service and scan
        scanner = TargetScannerService(mock_discovery_service)
        result = await scanner.scan_target_tenant(tenant_id="tenant-123")

        # Verify result
        assert result.tenant_id == "tenant-123"
        assert result.subscription_id is None
        assert len(result.resources) == 4  # 2 subscriptions * 2 resources each
        assert result.error is None

        # Verify discovery service calls
        mock_discovery_service.discover_subscriptions.assert_called_once()
        assert mock_discovery_service.discover_resources_in_subscription.call_count == 2

    @pytest.mark.asyncio
    async def test_scan_with_custom_credential(
        self, mock_discovery_service, sample_resources
    ):
        """Test scan with custom credential."""
        # Setup mocks
        mock_discovery_service.discover_resources_in_subscription.return_value = (
            sample_resources
        )
        custom_credential = MagicMock()
        original_credential = mock_discovery_service.credential

        # Create service and scan with custom credential
        scanner = TargetScannerService(mock_discovery_service)
        result = await scanner.scan_target_tenant(
            tenant_id="tenant-123",
            subscription_id="sub-123",
            credential=custom_credential,
        )

        # Verify credential was used and restored
        assert result.error is None
        assert mock_discovery_service.credential == original_credential

    @pytest.mark.asyncio
    async def test_scan_no_subscriptions_found(self, mock_discovery_service):
        """Test scan when no subscriptions are found."""
        # Setup mocks - return empty subscription list
        mock_discovery_service.discover_subscriptions.return_value = []

        # Create service and scan
        scanner = TargetScannerService(mock_discovery_service)
        result = await scanner.scan_target_tenant(tenant_id="tenant-123")

        # Verify result
        assert result.tenant_id == "tenant-123"
        assert len(result.resources) == 0
        assert result.error is not None
        assert "No subscriptions found" in result.error

    @pytest.mark.asyncio
    async def test_scan_subscription_discovery_fails(self, mock_discovery_service):
        """Test graceful handling when subscription discovery fails."""
        # Setup mocks - raise exception during subscription discovery
        mock_discovery_service.discover_subscriptions.side_effect = Exception(
            "Authentication failed"
        )

        # Create service and scan
        scanner = TargetScannerService(mock_discovery_service)
        result = await scanner.scan_target_tenant(tenant_id="tenant-123")

        # Verify result captures error but doesn't raise
        assert result.tenant_id == "tenant-123"
        assert len(result.resources) == 0
        assert result.error is not None
        assert "Failed to discover subscriptions" in result.error
        assert "Authentication failed" in result.error

    @pytest.mark.asyncio
    async def test_scan_partial_subscription_failure(
        self, mock_discovery_service, sample_subscriptions, sample_resources
    ):
        """Test partial success when one subscription fails."""
        # Setup mocks - first subscription succeeds, second fails
        mock_discovery_service.discover_subscriptions.return_value = (
            sample_subscriptions
        )

        async def mock_discover_resources(sub_id: str):
            if sub_id == "sub-123":
                return sample_resources
            else:
                raise Exception("Permission denied")

        mock_discovery_service.discover_resources_in_subscription.side_effect = (
            mock_discover_resources
        )

        # Create service and scan
        scanner = TargetScannerService(mock_discovery_service)
        result = await scanner.scan_target_tenant(tenant_id="tenant-123")

        # Verify partial success
        assert result.tenant_id == "tenant-123"
        assert len(result.resources) == 2  # Only from first subscription
        assert result.error is not None
        assert "Failed to scan subscription Development" in result.error
        assert "Permission denied" in result.error

    @pytest.mark.asyncio
    async def test_scan_resource_conversion_failure(
        self, mock_discovery_service, sample_subscriptions
    ):
        """Test graceful handling when resource conversion fails."""
        # Setup mocks with malformed resource (missing required field)
        mock_discovery_service.discover_subscriptions.return_value = [
            sample_subscriptions[0]
        ]
        mock_discovery_service.discover_resources_in_subscription.return_value = [
            {"name": "vm1", "type": "Microsoft.Compute/virtualMachines"}  # Missing 'id'
        ]

        # Create service and scan
        scanner = TargetScannerService(mock_discovery_service)
        result = await scanner.scan_target_tenant(tenant_id="tenant-123")

        # Verify scan continues despite conversion error
        assert result.tenant_id == "tenant-123"
        assert (
            len(result.resources) == 0
        )  # Resource wasn't added due to conversion error
        # No error at scan level - conversion errors are logged but don't fail the scan

    @pytest.mark.asyncio
    async def test_scan_complete_failure(self, mock_discovery_service):
        """Test complete failure during scan."""
        # Setup mocks - raise unexpected exception
        mock_discovery_service.discover_subscriptions.side_effect = RuntimeError(
            "Unexpected error"
        )

        # Create service and scan
        scanner = TargetScannerService(mock_discovery_service)
        result = await scanner.scan_target_tenant(tenant_id="tenant-123")

        # Verify error is captured
        assert result.tenant_id == "tenant-123"
        assert len(result.resources) == 0
        assert result.error is not None
        assert "Unexpected error" in result.error

    @pytest.mark.asyncio
    async def test_convert_to_target_resource_success(self, mock_discovery_service):
        """Test _convert_to_target_resource with valid resource."""
        scanner = TargetScannerService(mock_discovery_service)

        resource_dict = {
            "id": "/subscriptions/sub-123/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "location": "eastus",
            "resource_group": "rg1",
            "subscription_id": "sub-123",
            "properties": {"vmSize": "Standard_D2s_v3"},
            "tags": {"env": "prod"},
        }

        target_resource = scanner._convert_to_target_resource(resource_dict)

        assert target_resource.id == resource_dict["id"]
        assert target_resource.name == "vm1"
        assert target_resource.type == "Microsoft.Compute/virtualMachines"
        assert target_resource.location == "eastus"
        assert target_resource.resource_group == "rg1"
        assert target_resource.subscription_id == "sub-123"
        assert target_resource.properties["vmSize"] == "Standard_D2s_v3"
        assert target_resource.tags["env"] == "prod"

    @pytest.mark.asyncio
    async def test_convert_to_target_resource_missing_id(self, mock_discovery_service):
        """Test _convert_to_target_resource with missing id."""
        scanner = TargetScannerService(mock_discovery_service)

        resource_dict = {
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "location": "eastus",
        }

        with pytest.raises(ValueError, match="Resource missing 'id' field"):
            scanner._convert_to_target_resource(resource_dict)

    @pytest.mark.asyncio
    async def test_convert_to_target_resource_missing_type(
        self, mock_discovery_service
    ):
        """Test _convert_to_target_resource with missing type."""
        scanner = TargetScannerService(mock_discovery_service)

        resource_dict = {
            "id": "/subscriptions/sub-123/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "name": "vm1",
            "location": "eastus",
        }

        with pytest.raises(ValueError, match="missing 'type' field"):
            scanner._convert_to_target_resource(resource_dict)

    @pytest.mark.asyncio
    async def test_convert_to_target_resource_missing_name(
        self, mock_discovery_service
    ):
        """Test _convert_to_target_resource with missing name."""
        scanner = TargetScannerService(mock_discovery_service)

        resource_dict = {
            "id": "/subscriptions/sub-123/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "location": "eastus",
        }

        with pytest.raises(ValueError, match="missing 'name' field"):
            scanner._convert_to_target_resource(resource_dict)

    @pytest.mark.asyncio
    async def test_convert_to_target_resource_with_defaults(
        self, mock_discovery_service
    ):
        """Test _convert_to_target_resource with minimal fields (using defaults)."""
        scanner = TargetScannerService(mock_discovery_service)

        resource_dict = {
            "id": "/subscriptions/sub-123/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
        }

        target_resource = scanner._convert_to_target_resource(resource_dict)

        assert target_resource.id == resource_dict["id"]
        assert target_resource.name == "vm1"
        assert target_resource.type == "Microsoft.Compute/virtualMachines"
        assert target_resource.location == ""
        assert target_resource.resource_group == ""
        assert target_resource.subscription_id == ""
        assert target_resource.properties == {}
        assert target_resource.tags == {}

    @pytest.mark.asyncio
    async def test_convert_to_target_resource_invalid_properties(
        self, mock_discovery_service
    ):
        """Test _convert_to_target_resource with non-dict properties."""
        scanner = TargetScannerService(mock_discovery_service)

        resource_dict = {
            "id": "/subscriptions/sub-123/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "properties": "invalid",  # Not a dict
        }

        target_resource = scanner._convert_to_target_resource(resource_dict)

        # Should convert invalid properties to empty dict
        assert target_resource.properties == {}

    @pytest.mark.asyncio
    async def test_convert_to_target_resource_invalid_tags(
        self, mock_discovery_service
    ):
        """Test _convert_to_target_resource with non-dict tags."""
        scanner = TargetScannerService(mock_discovery_service)

        resource_dict = {
            "id": "/subscriptions/sub-123/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "tags": ["tag1", "tag2"],  # Not a dict
        }

        target_resource = scanner._convert_to_target_resource(resource_dict)

        # Should convert invalid tags to empty dict
        assert target_resource.tags == {}

    @pytest.mark.asyncio
    async def test_scan_timestamp_format(
        self, mock_discovery_service, sample_resources
    ):
        """Test that scan timestamp is in ISO8601 format."""
        mock_discovery_service.discover_resources_in_subscription.return_value = (
            sample_resources
        )

        scanner = TargetScannerService(mock_discovery_service)
        result = await scanner.scan_target_tenant(
            tenant_id="tenant-123", subscription_id="sub-123"
        )

        # Verify timestamp is valid ISO8601
        timestamp = datetime.fromisoformat(result.scan_timestamp.replace("Z", "+00:00"))
        assert timestamp.tzinfo is not None

    @pytest.mark.asyncio
    async def test_scan_subscription_without_id(
        self, mock_discovery_service, sample_subscriptions
    ):
        """Test that subscriptions without ID are skipped."""
        # Add a subscription without ID
        invalid_sub = {"display_name": "Invalid Subscription"}
        mock_discovery_service.discover_subscriptions.return_value = [
            sample_subscriptions[0],
            invalid_sub,
        ]
        mock_discovery_service.discover_resources_in_subscription.return_value = []
        mock_discovery_service.discover_role_assignments_in_subscription.return_value = []

        scanner = TargetScannerService(mock_discovery_service)
        result = await scanner.scan_target_tenant(tenant_id="tenant-123")

        # Should only call discover_resources_in_subscription for valid subscription
        assert mock_discovery_service.discover_resources_in_subscription.call_count == 1
        assert result.error is None

    # Issue #752: Role Assignment Detection Tests

    @pytest.mark.asyncio
    async def test_scan_includes_role_assignments(
        self, mock_discovery_service, sample_resources, sample_role_assignments
    ):
        """Test that scan_target_tenant includes role assignments (Issue #752)."""
        # Setup mocks - return both resources and role assignments
        mock_discovery_service.discover_resources_in_subscription.return_value = (
            sample_resources
        )
        mock_discovery_service.discover_role_assignments_in_subscription.return_value = sample_role_assignments

        # Create service and scan
        scanner = TargetScannerService(mock_discovery_service)
        result = await scanner.scan_target_tenant(
            tenant_id="tenant-123", subscription_id="sub-123"
        )

        # Verify both discovery methods were called
        mock_discovery_service.discover_resources_in_subscription.assert_called_once_with(
            "sub-123"
        )
        mock_discovery_service.discover_role_assignments_in_subscription.assert_called_once()

        # Verify result includes both regular resources and role assignments
        assert result.tenant_id == "tenant-123"
        assert result.subscription_id == "sub-123"
        assert len(result.resources) == 4  # 2 regular resources + 2 role assignments
        assert result.error is None

        # Verify role assignments are present in results
        role_assignment_types = [
            r.type
            for r in result.resources
            if r.type == "Microsoft.Authorization/roleAssignments"
        ]
        assert len(role_assignment_types) == 2

    @pytest.mark.asyncio
    async def test_scan_role_assignments_converted_correctly(
        self, mock_discovery_service, sample_role_assignments
    ):
        """Test that role assignments are converted to TargetResource correctly."""
        # Setup mocks - only role assignments, no regular resources
        mock_discovery_service.discover_resources_in_subscription.return_value = []
        mock_discovery_service.discover_role_assignments_in_subscription.return_value = sample_role_assignments

        # Create service and scan
        scanner = TargetScannerService(mock_discovery_service)
        result = await scanner.scan_target_tenant(
            tenant_id="tenant-123", subscription_id="sub-123"
        )

        # Verify role assignments were converted
        assert len(result.resources) == 2
        assert result.resources[0].name == "assignment-1"
        assert result.resources[0].type == "Microsoft.Authorization/roleAssignments"
        assert result.resources[0].properties["principalId"] == "principal-123"
        assert result.resources[0].properties["principalType"] == "ServicePrincipal"

        assert result.resources[1].name == "assignment-2"
        assert result.resources[1].type == "Microsoft.Authorization/roleAssignments"
        assert result.resources[1].properties["principalId"] == "principal-456"
        assert result.resources[1].properties["principalType"] == "User"

    @pytest.mark.asyncio
    async def test_scan_role_assignment_discovery_failure_graceful(
        self, mock_discovery_service, sample_resources
    ):
        """Test graceful handling when role assignment discovery fails."""
        # Setup mocks - regular resources succeed, role assignments fail
        mock_discovery_service.discover_resources_in_subscription.return_value = (
            sample_resources
        )
        mock_discovery_service.discover_role_assignments_in_subscription.side_effect = (
            Exception("Permission denied for role assignments")
        )

        # Create service and scan
        scanner = TargetScannerService(mock_discovery_service)
        result = await scanner.scan_target_tenant(
            tenant_id="tenant-123", subscription_id="sub-123"
        )

        # Verify partial success - regular resources still discovered
        assert result.tenant_id == "tenant-123"
        assert len(result.resources) == 2  # Only regular resources
        assert result.error is not None
        assert "role assignments" in result.error.lower()
        assert "Permission denied" in result.error

    @pytest.mark.asyncio
    async def test_scan_all_subscriptions_includes_role_assignments(
        self,
        mock_discovery_service,
        sample_subscriptions,
        sample_resources,
        sample_role_assignments,
    ):
        """Test that multi-subscription scan includes role assignments from all subscriptions."""
        # Setup mocks - return both resources and role assignments for all subscriptions
        mock_discovery_service.discover_subscriptions.return_value = (
            sample_subscriptions
        )
        mock_discovery_service.discover_resources_in_subscription.return_value = (
            sample_resources
        )
        mock_discovery_service.discover_role_assignments_in_subscription.return_value = sample_role_assignments

        # Create service and scan
        scanner = TargetScannerService(mock_discovery_service)
        result = await scanner.scan_target_tenant(tenant_id="tenant-123")

        # Verify both discovery methods called for each subscription
        assert mock_discovery_service.discover_resources_in_subscription.call_count == 2
        assert (
            mock_discovery_service.discover_role_assignments_in_subscription.call_count
            == 2
        )

        # Verify result includes resources and role assignments from all subscriptions
        # 2 subscriptions * (2 resources + 2 role assignments) = 8 total
        assert result.tenant_id == "tenant-123"
        assert len(result.resources) == 8
        assert result.error is None

        # Verify role assignments are present
        role_assignment_count = len(
            [
                r
                for r in result.resources
                if r.type == "Microsoft.Authorization/roleAssignments"
            ]
        )
        assert role_assignment_count == 4  # 2 per subscription
