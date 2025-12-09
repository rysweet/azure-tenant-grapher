"""
Unit tests for ResourceComparator service.

Tests all classification scenarios: NEW, EXACT_MATCH, DRIFTED, ORPHANED.
"""

from typing import Any, Dict
from unittest.mock import MagicMock, Mock

import pytest

from src.iac.resource_comparator import (
    ComparisonResult,
    ResourceComparator,
    ResourceState,
)
from src.iac.target_scanner import TargetResource, TargetScanResult


@pytest.fixture
def mock_session_manager():
    """Create a mock Neo4jSessionManager."""
    mock_manager = MagicMock()
    mock_session = MagicMock()
    mock_manager.session.return_value.__enter__.return_value = mock_session
    mock_manager.session.return_value.__exit__ = Mock(return_value=False)
    return mock_manager


@pytest.fixture
def comparator(mock_session_manager):
    """Create a ResourceComparator instance with mocked session manager."""
    return ResourceComparator(mock_session_manager)


@pytest.fixture
def sample_abstracted_resource() -> Dict[str, Any]:
    """Sample abstracted resource from graph."""
    return {
        "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm-a1b2c3d4",
        "name": "vm-a1b2c3d4",
        "type": "Microsoft.Compute/virtualMachines",
        "location": "eastus",
        "tags": {"Environment": "Production", "Owner": "TeamA"},
        "original_id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/my-original-vm",
    }


@pytest.fixture
def sample_target_resource() -> TargetResource:
    """Sample target resource from scan."""
    return TargetResource(
        id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/my-original-vm",
        type="Microsoft.Compute/virtualMachines",
        name="my-original-vm",
        location="eastus",
        resource_group="rg1",
        subscription_id="sub1",
        properties={},
        tags={"Environment": "Production", "Owner": "TeamA"},
    )


class TestResourceState:
    """Test ResourceState enum."""

    def test_resource_state_values(self):
        """Test that ResourceState has correct values."""
        assert ResourceState.NEW.value == "new"
        assert ResourceState.EXACT_MATCH.value == "exact_match"
        assert ResourceState.DRIFTED.value == "drifted"
        assert ResourceState.ORPHANED.value == "orphaned"


class TestResourceComparator:
    """Test ResourceComparator service."""

    def test_initialization(self, mock_session_manager):
        """Test ResourceComparator initialization."""
        comparator = ResourceComparator(mock_session_manager)
        assert comparator.session_manager == mock_session_manager

    def test_compare_resources_empty_lists(self, comparator):
        """Test comparison with empty resource lists."""
        target_scan = TargetScanResult(
            tenant_id="tenant1",
            subscription_id="sub1",
            resources=[],
            scan_timestamp="2025-01-01T00:00:00Z",
        )

        result = comparator.compare_resources([], target_scan)

        assert isinstance(result, ComparisonResult)
        assert len(result.classifications) == 0
        assert result.summary[ResourceState.NEW.value] == 0
        assert result.summary[ResourceState.EXACT_MATCH.value] == 0
        assert result.summary[ResourceState.DRIFTED.value] == 0
        assert result.summary[ResourceState.ORPHANED.value] == 0

    def test_classify_new_resource_no_original_id(
        self, comparator, sample_abstracted_resource
    ):
        """Test classification of NEW resource (no original_id property)."""
        # Remove original_id to force Neo4j query
        abstracted_resource = sample_abstracted_resource.copy()
        del abstracted_resource["original_id"]

        target_scan = TargetScanResult(
            tenant_id="tenant1",
            subscription_id="sub1",
            resources=[],
            scan_timestamp="2025-01-01T00:00:00Z",
        )

        # Mock Neo4j query to return no original ID
        mock_result = MagicMock()
        mock_result.single.return_value = None
        comparator.session_manager.session.return_value.__enter__.return_value.run.return_value = mock_result

        result = comparator.compare_resources([abstracted_resource], target_scan)

        assert len(result.classifications) == 1
        classification = result.classifications[0]
        assert classification.classification == ResourceState.NEW
        assert classification.target_resource is None
        assert result.summary[ResourceState.NEW.value] == 1

    def test_classify_new_resource_not_in_target(
        self, comparator, sample_abstracted_resource
    ):
        """Test classification of NEW resource (not found in target)."""
        target_scan = TargetScanResult(
            tenant_id="tenant1",
            subscription_id="sub1",
            resources=[],  # Empty target
            scan_timestamp="2025-01-01T00:00:00Z",
        )

        result = comparator.compare_resources([sample_abstracted_resource], target_scan)

        assert len(result.classifications) == 1
        classification = result.classifications[0]
        assert classification.classification == ResourceState.NEW
        assert classification.target_resource is None
        assert result.summary[ResourceState.NEW.value] == 1

    def test_classify_exact_match(
        self, comparator, sample_abstracted_resource, sample_target_resource
    ):
        """Test classification of EXACT_MATCH resource."""
        # Ensure abstracted resource name matches target's original name
        abstracted_resource = sample_abstracted_resource.copy()
        abstracted_resource["name"] = sample_target_resource.name

        target_scan = TargetScanResult(
            tenant_id="tenant1",
            subscription_id="sub1",
            resources=[sample_target_resource],
            scan_timestamp="2025-01-01T00:00:00Z",
        )

        result = comparator.compare_resources([abstracted_resource], target_scan)

        assert len(result.classifications) == 1
        classification = result.classifications[0]
        assert classification.classification == ResourceState.EXACT_MATCH
        assert classification.target_resource == sample_target_resource
        assert classification.drift_details is None
        assert result.summary[ResourceState.EXACT_MATCH.value] == 1

    def test_classify_drifted_name_difference(
        self, comparator, sample_abstracted_resource, sample_target_resource
    ):
        """Test classification of DRIFTED resource (name differs)."""
        # Abstracted resource has different name
        abstracted_resource = sample_abstracted_resource.copy()
        abstracted_resource["name"] = "different-vm-name"

        target_scan = TargetScanResult(
            tenant_id="tenant1",
            subscription_id="sub1",
            resources=[sample_target_resource],
            scan_timestamp="2025-01-01T00:00:00Z",
        )

        result = comparator.compare_resources([abstracted_resource], target_scan)

        assert len(result.classifications) == 1
        classification = result.classifications[0]
        assert classification.classification == ResourceState.DRIFTED
        assert classification.target_resource == sample_target_resource
        assert classification.drift_details is not None
        assert len(classification.drift_details["property_differences"]) >= 1

        # Check name difference is captured
        name_diff = next(
            (
                d
                for d in classification.drift_details["property_differences"]
                if d["property"] == "name"
            ),
            None,
        )
        assert name_diff is not None
        assert name_diff["expected"] == "different-vm-name"
        assert name_diff["actual"] == sample_target_resource.name

    def test_classify_drifted_location_difference(
        self, comparator, sample_abstracted_resource, sample_target_resource
    ):
        """Test classification of DRIFTED resource (location differs)."""
        # Abstracted resource has different location
        abstracted_resource = sample_abstracted_resource.copy()
        abstracted_resource["name"] = sample_target_resource.name  # Match name
        abstracted_resource["location"] = "westus"

        # Update target to have different location
        target_resource = TargetResource(
            id=sample_target_resource.id,
            type=sample_target_resource.type,
            name=sample_target_resource.name,
            location="eastus",
            resource_group=sample_target_resource.resource_group,
            subscription_id=sample_target_resource.subscription_id,
            properties={},
            tags=sample_target_resource.tags,
        )

        target_scan = TargetScanResult(
            tenant_id="tenant1",
            subscription_id="sub1",
            resources=[target_resource],
            scan_timestamp="2025-01-01T00:00:00Z",
        )

        result = comparator.compare_resources([abstracted_resource], target_scan)

        assert len(result.classifications) == 1
        classification = result.classifications[0]
        assert classification.classification == ResourceState.DRIFTED

        # Check location difference is captured
        location_diff = next(
            (
                d
                for d in classification.drift_details["property_differences"]
                if d["property"] == "location"
            ),
            None,
        )
        assert location_diff is not None
        assert location_diff["expected"] == "westus"
        assert location_diff["actual"] == "eastus"

    def test_classify_drifted_tags_difference(
        self, comparator, sample_abstracted_resource, sample_target_resource
    ):
        """Test classification of DRIFTED resource (tags differ)."""
        # Abstracted resource has different tags
        abstracted_resource = sample_abstracted_resource.copy()
        abstracted_resource["name"] = sample_target_resource.name  # Match name
        abstracted_resource["tags"] = {
            "Environment": "Dev",  # Different value
            "Owner": "TeamA",
            "NewTag": "NewValue",  # Extra tag
        }

        target_scan = TargetScanResult(
            tenant_id="tenant1",
            subscription_id="sub1",
            resources=[sample_target_resource],
            scan_timestamp="2025-01-01T00:00:00Z",
        )

        result = comparator.compare_resources([abstracted_resource], target_scan)

        assert len(result.classifications) == 1
        classification = result.classifications[0]
        assert classification.classification == ResourceState.DRIFTED

        # Check tag differences are captured
        tag_diffs = [
            d
            for d in classification.drift_details["property_differences"]
            if d["property"].startswith("tags.")
        ]
        assert len(tag_diffs) >= 1

        # Check Environment tag difference
        env_diff = next(
            (d for d in tag_diffs if d["property"] == "tags.Environment"), None
        )
        assert env_diff is not None
        assert env_diff["expected"] == "Dev"
        assert env_diff["actual"] == "Production"

    def test_classify_orphaned_resource(self, comparator, sample_target_resource):
        """Test detection of ORPHANED resource (in target but not in abstracted)."""
        # Empty abstracted resources
        target_scan = TargetScanResult(
            tenant_id="tenant1",
            subscription_id="sub1",
            resources=[sample_target_resource],
            scan_timestamp="2025-01-01T00:00:00Z",
        )

        result = comparator.compare_resources([], target_scan)

        assert len(result.classifications) == 1
        classification = result.classifications[0]
        assert classification.classification == ResourceState.ORPHANED
        assert classification.target_resource == sample_target_resource
        assert result.summary[ResourceState.ORPHANED.value] == 1

    def test_compare_resources_mixed_states(
        self, comparator, sample_abstracted_resource, sample_target_resource
    ):
        """Test comparison with resources in multiple states."""
        # Create multiple abstracted resources
        abstracted_resource_new = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage-xyz",
            "name": "storage-xyz",
            "type": "Microsoft.Storage/storageAccounts",
            "location": "eastus",
            "tags": {},
            "original_id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/original-storage",
        }

        abstracted_resource_match = sample_abstracted_resource.copy()
        abstracted_resource_match["name"] = sample_target_resource.name

        abstracted_resource_drifted = sample_abstracted_resource.copy()
        abstracted_resource_drifted["name"] = "drifted-vm"
        abstracted_resource_drifted["original_id"] = (
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm2"
        )

        # Create target resources
        target_resource_match = sample_target_resource
        target_resource_drifted = TargetResource(
            id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm2",
            type="Microsoft.Compute/virtualMachines",
            name="vm2",
            location="eastus",
            resource_group="rg1",
            subscription_id="sub1",
            properties={},
            tags={},
        )
        target_resource_orphaned = TargetResource(
            id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet-orphaned",
            type="Microsoft.Network/virtualNetworks",
            name="vnet-orphaned",
            location="eastus",
            resource_group="rg1",
            subscription_id="sub1",
            properties={},
            tags={},
        )

        target_scan = TargetScanResult(
            tenant_id="tenant1",
            subscription_id="sub1",
            resources=[
                target_resource_match,
                target_resource_drifted,
                target_resource_orphaned,
            ],
            scan_timestamp="2025-01-01T00:00:00Z",
        )

        result = comparator.compare_resources(
            [
                abstracted_resource_new,
                abstracted_resource_match,
                abstracted_resource_drifted,
            ],
            target_scan,
        )

        # Should have 4 classifications: 1 NEW, 1 EXACT_MATCH, 1 DRIFTED, 1 ORPHANED
        assert len(result.classifications) == 4
        assert result.summary[ResourceState.NEW.value] == 1
        assert result.summary[ResourceState.EXACT_MATCH.value] == 1
        assert result.summary[ResourceState.DRIFTED.value] == 1
        assert result.summary[ResourceState.ORPHANED.value] == 1

    def test_case_insensitive_matching(self, comparator, sample_abstracted_resource):
        """Test that resource ID matching is case-insensitive."""
        # Create target resource with different case in ID
        target_resource = TargetResource(
            id="/SUBSCRIPTIONS/SUB1/RESOURCEGROUPS/RG1/PROVIDERS/MICROSOFT.COMPUTE/VIRTUALMACHINES/MY-ORIGINAL-VM",
            type="Microsoft.Compute/virtualMachines",
            name="my-original-vm",
            location="eastus",
            resource_group="rg1",
            subscription_id="sub1",
            properties={},
            tags={"Environment": "Production", "Owner": "TeamA"},
        )

        abstracted_resource = sample_abstracted_resource.copy()
        abstracted_resource["name"] = target_resource.name

        target_scan = TargetScanResult(
            tenant_id="tenant1",
            subscription_id="sub1",
            resources=[target_resource],
            scan_timestamp="2025-01-01T00:00:00Z",
        )

        result = comparator.compare_resources([abstracted_resource], target_scan)

        # Should match despite case difference
        assert len(result.classifications) == 1
        classification = result.classifications[0]
        assert classification.classification == ResourceState.EXACT_MATCH

    def test_neo4j_query_error_handling(self, comparator, sample_abstracted_resource):
        """Test that Neo4j query errors are handled gracefully."""
        # Remove original_id to force Neo4j query
        abstracted_resource = sample_abstracted_resource.copy()
        del abstracted_resource["original_id"]

        # Mock Neo4j query to raise exception
        comparator.session_manager.session.return_value.__enter__.return_value.run.side_effect = Exception(
            "Database connection failed"
        )

        target_scan = TargetScanResult(
            tenant_id="tenant1",
            subscription_id="sub1",
            resources=[],
            scan_timestamp="2025-01-01T00:00:00Z",
        )

        # Should not raise exception - should classify as NEW (safe default)
        result = comparator.compare_resources([abstracted_resource], target_scan)

        assert len(result.classifications) == 1
        classification = result.classifications[0]
        assert classification.classification == ResourceState.NEW

    def test_missing_abstracted_resource_id(self, comparator):
        """Test handling of abstracted resource without ID."""
        abstracted_resource = {
            "name": "vm-test",
            "type": "Microsoft.Compute/virtualMachines",
            # Missing 'id' field
        }

        target_scan = TargetScanResult(
            tenant_id="tenant1",
            subscription_id="sub1",
            resources=[],
            scan_timestamp="2025-01-01T00:00:00Z",
        )

        result = comparator.compare_resources([abstracted_resource], target_scan)

        # Should classify as NEW (safe default)
        assert len(result.classifications) == 1
        classification = result.classifications[0]
        assert classification.classification == ResourceState.NEW

    def test_location_case_insensitive_comparison(
        self, comparator, sample_abstracted_resource
    ):
        """Test that location comparison is case-insensitive."""
        abstracted_resource = sample_abstracted_resource.copy()
        abstracted_resource["name"] = "my-original-vm"
        abstracted_resource["location"] = "EASTUS"  # Uppercase

        target_resource = TargetResource(
            id=sample_abstracted_resource["original_id"],
            type="Microsoft.Compute/virtualMachines",
            name="my-original-vm",
            location="eastus",  # Lowercase
            resource_group="rg1",
            subscription_id="sub1",
            properties={},
            tags={"Environment": "Production", "Owner": "TeamA"},
        )

        target_scan = TargetScanResult(
            tenant_id="tenant1",
            subscription_id="sub1",
            resources=[target_resource],
            scan_timestamp="2025-01-01T00:00:00Z",
        )

        result = comparator.compare_resources([abstracted_resource], target_scan)

        # Should match despite case difference
        assert len(result.classifications) == 1
        classification = result.classifications[0]
        assert classification.classification == ResourceState.EXACT_MATCH

    def test_tags_none_handling(self, comparator, sample_abstracted_resource):
        """Test handling of None tags."""
        abstracted_resource = sample_abstracted_resource.copy()
        abstracted_resource["name"] = "my-original-vm"
        abstracted_resource["tags"] = None  # None tags

        target_resource = TargetResource(
            id=sample_abstracted_resource["original_id"],
            type="Microsoft.Compute/virtualMachines",
            name="my-original-vm",
            location="eastus",
            resource_group="rg1",
            subscription_id="sub1",
            properties={},
            tags=None,  # None tags
        )

        target_scan = TargetScanResult(
            tenant_id="tenant1",
            subscription_id="sub1",
            resources=[target_resource],
            scan_timestamp="2025-01-01T00:00:00Z",
        )

        result = comparator.compare_resources([abstracted_resource], target_scan)

        # Should handle None tags gracefully
        assert len(result.classifications) == 1
        classification = result.classifications[0]
        # Both have None/empty tags, should match
        assert classification.classification == ResourceState.EXACT_MATCH

    def test_summary_generation(self, comparator):
        """Test that summary is correctly generated."""
        # Create resources in each state
        abstracted_new = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage-new",
            "name": "storage-new",
            "type": "Microsoft.Storage/storageAccounts",
            "location": "eastus",
            "tags": {},
            "original_id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/original-storage-new",
        }

        abstracted_match = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage-match",
            "name": "storage-match",
            "type": "Microsoft.Storage/storageAccounts",
            "location": "eastus",
            "tags": {},
            "original_id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage-match",
        }

        target_match = TargetResource(
            id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage-match",
            type="Microsoft.Storage/storageAccounts",
            name="storage-match",
            location="eastus",
            resource_group="rg1",
            subscription_id="sub1",
            properties={},
            tags={},
        )

        target_orphaned = TargetResource(
            id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet-orphaned",
            type="Microsoft.Network/virtualNetworks",
            name="vnet-orphaned",
            location="eastus",
            resource_group="rg1",
            subscription_id="sub1",
            properties={},
            tags={},
        )

        target_scan = TargetScanResult(
            tenant_id="tenant1",
            subscription_id="sub1",
            resources=[target_match, target_orphaned],
            scan_timestamp="2025-01-01T00:00:00Z",
        )

        result = comparator.compare_resources(
            [abstracted_new, abstracted_match], target_scan
        )

        # Verify summary counts
        assert result.summary[ResourceState.NEW.value] == 1
        assert result.summary[ResourceState.EXACT_MATCH.value] == 1
        assert result.summary[ResourceState.DRIFTED.value] == 0
        assert result.summary[ResourceState.ORPHANED.value] == 1

    def test_bug_111_none_id_in_target_resource(self, comparator):
        """Test Bug #111: Handle None ID in target resource."""
        # Create target resource with None ID (should be skipped)
        target_resource_none = TargetResource(
            id=None,
            type="Microsoft.Compute/virtualMachines",
            name="vm-broken",
            location="eastus",
            resource_group="rg1",
            subscription_id="sub1",
            properties={},
            tags={},
        )

        target_resource_valid = TargetResource(
            id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm-valid",
            type="Microsoft.Compute/virtualMachines",
            name="vm-valid",
            location="eastus",
            resource_group="rg1",
            subscription_id="sub1",
            properties={},
            tags={},
        )

        target_scan = TargetScanResult(
            tenant_id="tenant1",
            subscription_id="sub1",
            resources=[target_resource_none, target_resource_valid],
            scan_timestamp="2025-01-01T00:00:00Z",
        )

        # Should not crash and should skip None ID resource
        result = comparator.compare_resources([], target_scan)

        # Only the valid resource should be orphaned, None ID resource should be skipped
        assert len(result.classifications) == 1
        assert result.classifications[0].target_resource == target_resource_valid
        assert result.summary[ResourceState.ORPHANED.value] == 1

    def test_bug_111_none_location_in_target_resource(
        self, comparator, sample_abstracted_resource
    ):
        """Test Bug #111: Handle None location in target resource."""
        abstracted_resource = sample_abstracted_resource.copy()
        abstracted_resource["name"] = "my-original-vm"

        # Create target resource with None location
        target_resource = TargetResource(
            id=sample_abstracted_resource["original_id"],
            type="Microsoft.Compute/virtualMachines",
            name="my-original-vm",
            location=None,  # None location
            resource_group="rg1",
            subscription_id="sub1",
            properties={},
            tags={},
        )

        target_scan = TargetScanResult(
            tenant_id="tenant1",
            subscription_id="sub1",
            resources=[target_resource],
            scan_timestamp="2025-01-01T00:00:00Z",
        )

        # Should not crash when comparing locations
        result = comparator.compare_resources([abstracted_resource], target_scan)

        # Should detect location difference (abstracted has location, target doesn't)
        assert len(result.classifications) == 1
        classification = result.classifications[0]
        assert classification.classification == ResourceState.DRIFTED

    def test_bug_111_none_normalized_id(self, comparator):
        """Test Bug #111: Handle None normalized_id in classification."""
        # Create abstracted resource with no ID and no original_id
        abstracted_resource = {
            "name": "vm-no-id",
            "type": "Microsoft.Compute/virtualMachines",
            # Missing both 'id' and 'original_id'
        }

        target_scan = TargetScanResult(
            tenant_id="tenant1",
            subscription_id="sub1",
            resources=[],
            scan_timestamp="2025-01-01T00:00:00Z",
        )

        # Should not crash and classify as NEW
        result = comparator.compare_resources([abstracted_resource], target_scan)

        assert len(result.classifications) == 1
        classification = result.classifications[0]
        assert classification.classification == ResourceState.NEW

    def test_bug_111_multiple_none_values_comprehensive(self, comparator):
        """Test Bug #111: Comprehensive test with multiple None values."""
        # Create abstracted resources with various None scenarios
        abstracted_no_id = {
            "name": "vm-no-id",
            "type": "Microsoft.Compute/virtualMachines",
        }

        abstracted_none_location = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1",
            "name": "storage1",
            "type": "Microsoft.Storage/storageAccounts",
            "location": None,
            "original_id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1",
        }

        # Create target resources with None values
        target_none_id = TargetResource(
            id=None,
            type="Microsoft.Network/virtualNetworks",
            name="vnet-none-id",
            location="eastus",
            resource_group="rg1",
            subscription_id="sub1",
            properties={},
            tags={},
        )

        target_none_location = TargetResource(
            id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1",
            type="Microsoft.Storage/storageAccounts",
            name="storage1",
            location=None,
            resource_group="rg1",
            subscription_id="sub1",
            properties={},
            tags={},
        )

        target_scan = TargetScanResult(
            tenant_id="tenant1",
            subscription_id="sub1",
            resources=[target_none_id, target_none_location],
            scan_timestamp="2025-01-01T00:00:00Z",
        )

        # Should handle all None values gracefully
        result = comparator.compare_resources(
            [abstracted_no_id, abstracted_none_location], target_scan
        )

        # Should have classifications for both abstracted resources
        # abstracted_no_id -> NEW
        # abstracted_none_location -> EXACT_MATCH (both have None location)
        # target_none_id should be skipped (None ID)
        assert len(result.classifications) >= 2
