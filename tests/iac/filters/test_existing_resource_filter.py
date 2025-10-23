"""Tests for existing resource filter."""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from src.iac.filters.existing_resource_filter import (
    ExistingResourceFilter,
    ExistingResourceFilterResult,
)
from src.iac.conflict_detector import ConflictType, ResourceConflict


class TestExistingResourceFilter:
    """Test suite for ExistingResourceFilter."""

    @pytest.fixture
    def target_sub_id(self):
        """Target subscription ID."""
        return "22222222-2222-2222-2222-222222222222"

    @pytest.fixture
    def filter_instance(self, target_sub_id):
        """Create filter instance without async check."""
        return ExistingResourceFilter(
            target_subscription_id=target_sub_id,
            enable_async_check=False,
        )

    def test_initialization(self, target_sub_id):
        """Test filter initialization."""
        filter_instance = ExistingResourceFilter(
            target_subscription_id=target_sub_id,
            enable_async_check=False,
        )

        assert filter_instance.target_subscription_id == target_sub_id
        assert not filter_instance.enable_async_check
        assert filter_instance.conflict_detector is None

    def test_initialization_with_async_check(self, target_sub_id):
        """Test filter initialization with async check enabled."""
        with patch('src.iac.filters.existing_resource_filter.ConflictDetector'):
            filter_instance = ExistingResourceFilter(
                target_subscription_id=target_sub_id,
                enable_async_check=True,
            )

            assert filter_instance.enable_async_check

    def test_filter_disabled_async_check(self, filter_instance):
        """Test that filtering is skipped when async check is disabled."""
        resources = [
            {"id": "resource1", "type": "Microsoft.Compute/virtualMachines", "name": "vm1"},
            {"id": "resource2", "type": "Microsoft.Network/virtualNetworks", "name": "vnet1"},
        ]

        result = filter_instance.filter_resources(resources)

        assert result.resources_before == 2
        assert result.resources_after == 2
        assert result.filtered_count == 0

    def test_filter_no_subscription_id(self):
        """Test that filtering is skipped when subscription ID is missing."""
        filter_instance = ExistingResourceFilter(enable_async_check=True)

        resources = [
            {"id": "resource1", "type": "Microsoft.Compute/virtualMachines"},
        ]

        result = filter_instance.filter_resources(resources)

        assert result.resources_before == 1
        assert result.resources_after == 1
        assert result.filtered_count == 0

    @patch('src.iac.filters.existing_resource_filter.ConflictDetector')
    def test_filter_with_existing_resources(self, mock_detector_class, target_sub_id):
        """Test filtering resources that exist."""
        # Mock ConflictDetector
        mock_detector = Mock()
        mock_detector_class.return_value = mock_detector

        # Mock async detect_conflicts
        async def mock_detect_conflicts(resources):
            return [
                ResourceConflict(
                    conflict_type=ConflictType.EXISTING_RESOURCE,
                    resource_name="vm1",
                    resource_type="Microsoft.Compute/virtualMachines",
                    resource_group="rg1",
                )
            ]

        mock_detector.detect_conflicts = AsyncMock(side_effect=mock_detect_conflicts)

        filter_instance = ExistingResourceFilter(
            target_subscription_id=target_sub_id,
            enable_async_check=True,
        )
        filter_instance.conflict_detector = mock_detector

        resources = [
            {"id": "resource1", "type": "Microsoft.Compute/virtualMachines", "name": "vm1"},
            {"id": "resource2", "type": "Microsoft.Network/virtualNetworks", "name": "vnet1"},
        ]

        result = filter_instance.filter_resources(resources)

        assert result.resources_before == 2
        assert result.resources_after == 1
        assert result.filtered_count == 1
        assert "resource1" in result.existing_resources

    @patch('src.iac.filters.existing_resource_filter.ConflictDetector')
    def test_filter_error_handling(self, mock_detector_class, target_sub_id):
        """Test error handling during conflict detection."""
        # Mock ConflictDetector with error
        mock_detector = Mock()
        mock_detector_class.return_value = mock_detector

        async def mock_detect_conflicts_error(resources):
            raise Exception("API error")

        mock_detector.detect_conflicts = AsyncMock(side_effect=mock_detect_conflicts_error)

        filter_instance = ExistingResourceFilter(
            target_subscription_id=target_sub_id,
            enable_async_check=True,
        )
        filter_instance.conflict_detector = mock_detector

        resources = [
            {"id": "resource1", "type": "Microsoft.Compute/virtualMachines", "name": "vm1"},
        ]

        # Should not raise, but proceed without filtering
        result = filter_instance.filter_resources(resources)

        assert result.resources_before == 1
        assert result.resources_after == 1
        assert result.filtered_count == 0

    @patch('src.iac.filters.existing_resource_filter.ConflictDetector')
    def test_get_filter_summary(self, mock_detector_class, target_sub_id):
        """Test filter summary generation."""
        filter_instance = ExistingResourceFilter(
            target_subscription_id=target_sub_id,
            enable_async_check=False,
        )

        result = ExistingResourceFilterResult(
            resources_before=10,
            resources_after=8,
            existing_resources={"resource1", "resource2"},
            filter_reasons={
                "resource1": "Resource already exists: vm1",
                "resource2": "Resource already exists: vnet1",
            },
        )

        summary = filter_instance.get_filter_summary(result)

        assert "Resources before: 10" in summary
        assert "Resources after: 8" in summary
        assert "Filtered out: 2" in summary
        assert "resource1" in summary
        assert "resource2" in summary

    @patch('src.iac.filters.existing_resource_filter.ConflictDetector')
    def test_empty_resources_list(self, mock_detector_class, target_sub_id):
        """Test filtering empty resources list."""
        filter_instance = ExistingResourceFilter(
            target_subscription_id=target_sub_id,
            enable_async_check=False,
        )

        result = filter_instance.filter_resources([])

        assert result.resources_before == 0
        assert result.resources_after == 0
        assert result.filtered_count == 0

    @patch('src.iac.filters.existing_resource_filter.ConflictDetector')
    def test_no_existing_resources(self, mock_detector_class, target_sub_id):
        """Test when no resources exist in target."""
        mock_detector = Mock()
        mock_detector_class.return_value = mock_detector

        async def mock_detect_conflicts(resources):
            return []  # No conflicts

        mock_detector.detect_conflicts = AsyncMock(side_effect=mock_detect_conflicts)

        filter_instance = ExistingResourceFilter(
            target_subscription_id=target_sub_id,
            enable_async_check=True,
        )
        filter_instance.conflict_detector = mock_detector

        resources = [
            {"id": "resource1", "type": "Microsoft.Compute/virtualMachines", "name": "vm1"},
            {"id": "resource2", "type": "Microsoft.Network/virtualNetworks", "name": "vnet1"},
        ]

        result = filter_instance.filter_resources(resources)

        assert result.resources_before == 2
        assert result.resources_after == 2
        assert result.filtered_count == 0
