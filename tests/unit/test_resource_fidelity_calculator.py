"""
Unit tests for ResourceFidelityCalculator.

This module provides TDD tests for resource-level fidelity validation.
These tests are written BEFORE implementation and will fail initially.

Testing pyramid distribution: 60% unit tests (this file)
"""

from typing import Any, Dict, List
from unittest.mock import MagicMock, Mock, patch

import pytest

# These imports will fail initially - that's expected for TDD
try:
    from src.validation.resource_fidelity_calculator import (
        PropertyComparison,
        RedactionLevel,
        ResourceClassification,
        ResourceFidelityCalculator,
        ResourceFidelityMetrics,
        ResourceStatus,
    )
except ImportError:
    # TDD: Module doesn't exist yet - tests will fail
    pass


class TestResourceStatus:
    """Test ResourceStatus enum classification."""

    def test_resource_status_has_expected_values(self):
        """Test that ResourceStatus enum has all required states."""
        assert hasattr(ResourceStatus, "EXACT_MATCH")
        assert hasattr(ResourceStatus, "DRIFTED")
        assert hasattr(ResourceStatus, "MISSING_TARGET")
        assert hasattr(ResourceStatus, "MISSING_SOURCE")

    def test_resource_status_values(self):
        """Test ResourceStatus enum values match expected strings."""
        assert ResourceStatus.EXACT_MATCH.value == "exact_match"
        assert ResourceStatus.DRIFTED.value == "drifted"
        assert ResourceStatus.MISSING_TARGET.value == "missing_target"
        assert ResourceStatus.MISSING_SOURCE.value == "missing_source"


class TestRedactionLevel:
    """Test RedactionLevel enum for security controls."""

    def test_redaction_level_has_expected_values(self):
        """Test that RedactionLevel enum has all required levels."""
        assert hasattr(RedactionLevel, "FULL")
        assert hasattr(RedactionLevel, "MINIMAL")
        assert hasattr(RedactionLevel, "NONE")

    def test_redaction_level_values(self):
        """Test RedactionLevel enum values."""
        assert RedactionLevel.FULL.value == "full"
        assert RedactionLevel.MINIMAL.value == "minimal"
        assert RedactionLevel.NONE.value == "none"


class TestPropertyComparison:
    """Test PropertyComparison dataclass for property-level comparisons."""

    def test_property_comparison_initialization(self):
        """Test PropertyComparison creation with all fields."""
        comparison = PropertyComparison(
            property_path="sku.name",
            source_value="Standard_LRS",
            target_value="Premium_LRS",
            match=False,
            redacted=False,
        )

        assert comparison.property_path == "sku.name"
        assert comparison.source_value == "Standard_LRS"
        assert comparison.target_value == "Premium_LRS"
        assert comparison.match is False
        assert comparison.redacted is False

    def test_property_comparison_redacted(self):
        """Test PropertyComparison with redacted values."""
        comparison = PropertyComparison(
            property_path="properties.connectionStrings[0]",
            source_value="[REDACTED]",
            target_value="[REDACTED]",
            match=True,
            redacted=True,
        )

        assert comparison.redacted is True
        assert comparison.source_value == "[REDACTED]"
        assert comparison.target_value == "[REDACTED]"


class TestResourceClassification:
    """Test ResourceClassification dataclass."""

    def test_resource_classification_exact_match(self):
        """Test classification for resources with exact property matches."""
        classification = ResourceClassification(
            resource_id="/subscriptions/abc/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/storage1",
            resource_name="storage1",
            resource_type="Microsoft.Storage/storageAccounts",
            status=ResourceStatus.EXACT_MATCH,
            source_exists=True,
            target_exists=True,
            property_comparisons=[
                PropertyComparison("sku.name", "Standard_LRS", "Standard_LRS", True, False),
                PropertyComparison("location", "eastus", "eastus", True, False),
            ],
            mismatch_count=0,
            match_count=2,
        )

        assert classification.status == ResourceStatus.EXACT_MATCH
        assert classification.mismatch_count == 0
        assert classification.match_count == 2
        assert len(classification.property_comparisons) == 2

    def test_resource_classification_drifted(self):
        """Test classification for drifted resources."""
        classification = ResourceClassification(
            resource_id="/subscriptions/abc/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/storage1",
            resource_name="storage1",
            resource_type="Microsoft.Storage/storageAccounts",
            status=ResourceStatus.DRIFTED,
            source_exists=True,
            target_exists=True,
            property_comparisons=[
                PropertyComparison("sku.name", "Standard_LRS", "Premium_LRS", False, False),
                PropertyComparison("location", "eastus", "eastus", True, False),
            ],
            mismatch_count=1,
            match_count=1,
        )

        assert classification.status == ResourceStatus.DRIFTED
        assert classification.mismatch_count == 1
        assert classification.match_count == 1

    def test_resource_classification_missing_target(self):
        """Test classification for resources missing in target."""
        classification = ResourceClassification(
            resource_id="/subscriptions/abc/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm1",
            resource_name="vm1",
            resource_type="Microsoft.Compute/virtualMachines",
            status=ResourceStatus.MISSING_TARGET,
            source_exists=True,
            target_exists=False,
            property_comparisons=[],
            mismatch_count=0,
            match_count=0,
        )

        assert classification.status == ResourceStatus.MISSING_TARGET
        assert classification.source_exists is True
        assert classification.target_exists is False
        assert len(classification.property_comparisons) == 0


class TestResourceFidelityMetrics:
    """Test ResourceFidelityMetrics dataclass."""

    def test_metrics_initialization(self):
        """Test metrics creation with summary data."""
        metrics = ResourceFidelityMetrics(
            total_resources=100,
            exact_match=85,
            drifted=10,
            missing_target=5,
            missing_source=0,
            match_percentage=85.0,
            top_mismatched_properties=[
                {"property": "sku.name", "count": 8},
                {"property": "location", "count": 2},
            ],
        )

        assert metrics.total_resources == 100
        assert metrics.exact_match == 85
        assert metrics.drifted == 10
        assert metrics.missing_target == 5
        assert metrics.match_percentage == 85.0

    def test_metrics_calculation_percentages(self):
        """Test that match percentage is correctly calculated."""
        metrics = ResourceFidelityMetrics(
            total_resources=50,
            exact_match=40,
            drifted=8,
            missing_target=2,
            missing_source=0,
            match_percentage=80.0,  # 40/50 = 80%
            top_mismatched_properties=[],
        )

        assert metrics.match_percentage == 80.0


class TestResourceFidelityCalculator:
    """Test ResourceFidelityCalculator core functionality."""

    @pytest.fixture
    def mock_session_manager(self):
        """Create mock Neo4j session manager."""
        manager = Mock()
        manager.execute_read = Mock()  # Use synchronous Mock, not AsyncMock
        manager.execute_write = Mock()
        return manager

    @pytest.fixture
    def mock_resource_comparator(self):
        """Create mock ResourceComparator."""
        comparator = Mock()
        return comparator

    @pytest.fixture
    def calculator(self, mock_session_manager, mock_resource_comparator):
        """Create ResourceFidelityCalculator instance with mocks."""
        with patch("src.validation.resource_fidelity_calculator.ResourceComparator", return_value=mock_resource_comparator):
            calc = ResourceFidelityCalculator(
                session_manager=mock_session_manager,
                source_subscription_id="source-sub-123",
                target_subscription_id="target-sub-456",
            )
            return calc

    def test_initialization(self, mock_session_manager):
        """Test ResourceFidelityCalculator initialization."""
        with patch("src.validation.resource_fidelity_calculator.ResourceComparator"):
            calculator = ResourceFidelityCalculator(
                session_manager=mock_session_manager,
                source_subscription_id="source-sub-123",
                target_subscription_id="target-sub-456",
            )

            assert calculator.source_subscription_id == "source-sub-123"
            assert calculator.target_subscription_id == "target-sub-456"
            assert calculator.session_manager == mock_session_manager

    def test_query_resources_builds_correct_cypher_source(self, calculator):
        """Test that resource query constructs correct Cypher for source."""
        # Mock Neo4j query execution
        calculator.session_manager.execute_read.return_value = [
            {
                "id": "/subscriptions/source-sub-123/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/storage1",
                "name": "storage1",
                "type": "Microsoft.Storage/storageAccounts",
                "properties": {"sku": {"name": "Standard_LRS"}},
            }
        ]

        resources = calculator._query_resources(calculator.source_subscription_id)

        # Verify query was called
        calculator.session_manager.execute_read.assert_called_once()
        # Verify results contain expected resource
        assert len(resources) == 1
        assert resources[0]["name"] == "storage1"

    def test_query_resources_with_filter(self, calculator):
        """Test resource query with resource type filter."""
        calculator.session_manager.execute_read.return_value = [
            {
                "id": "/subscriptions/source-sub-123/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm1",
                "name": "vm1",
                "type": "Microsoft.Compute/virtualMachines",
                "properties": {},
            }
        ]

        resources = calculator._query_resources(calculator.source_subscription_id, resource_type="Microsoft.Compute/virtualMachines")

        # Verify filter was applied in query
        calculator.session_manager.execute_read.assert_called_once()
        assert len(resources) == 1
        assert resources[0]["type"] == "Microsoft.Compute/virtualMachines"

    def test_query_resources_builds_correct_cypher_target(self, calculator):
        """Test that resource query constructs correct Cypher for target."""
        calculator.session_manager.execute_read.return_value = [
            {
                "id": "/subscriptions/target-sub-456/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/storage1",
                "name": "storage1",
                "type": "Microsoft.Storage/storageAccounts",
                "properties": {"sku": {"name": "Premium_LRS"}},
            }
        ]

        resources = calculator._query_resources(calculator.target_subscription_id)

        calculator.session_manager.execute_read.assert_called_once()
        assert len(resources) == 1
        assert resources[0]["name"] == "storage1"

    def test_compare_properties_exact_match(self, calculator):
        """Test property comparison for exact matches."""
        source_props = {"sku": {"name": "Standard_LRS"}, "location": "eastus"}
        target_props = {"sku": {"name": "Standard_LRS"}, "location": "eastus"}

        comparisons = calculator._compare_properties(source_props, target_props, RedactionLevel.FULL)

        # Should have comparison for each property
        assert len(comparisons) >= 2
        # All should match
        assert all(c.match for c in comparisons)

    def test_compare_properties_mismatches(self, calculator):
        """Test property comparison detects mismatches."""
        source_props = {"sku": {"name": "Standard_LRS"}, "location": "eastus"}
        target_props = {"sku": {"name": "Premium_LRS"}, "location": "eastus"}

        comparisons = calculator._compare_properties(source_props, target_props, RedactionLevel.FULL)

        # Should detect sku mismatch
        sku_comparisons = [c for c in comparisons if "sku" in c.property_path]
        assert any(not c.match for c in sku_comparisons)

    def test_compare_properties_missing_properties(self, calculator):
        """Test property comparison handles missing properties in target."""
        source_props = {"sku": {"name": "Standard_LRS"}, "location": "eastus", "tags": {"env": "prod"}}
        target_props = {"sku": {"name": "Standard_LRS"}, "location": "eastus"}

        comparisons = calculator._compare_properties(source_props, target_props, RedactionLevel.FULL)

        # Should have comparisons for all source properties
        tag_comparisons = [c for c in comparisons if "tags" in c.property_path]
        assert len(tag_comparisons) > 0

    def test_redact_sensitive_properties_full_redaction(self, calculator):
        """Test that FULL redaction level redacts sensitive properties."""
        comparison = PropertyComparison(
            property_path="properties.connectionStrings[0].password",
            source_value="SecretPassword123!",
            target_value="SecretPassword456!",
            match=False,
            redacted=False,
        )

        redacted = calculator._redact_if_sensitive(comparison, RedactionLevel.FULL)

        assert redacted.redacted is True
        assert redacted.source_value == "[REDACTED]"
        assert redacted.target_value == "[REDACTED]"

    def test_redact_sensitive_properties_minimal_redaction(self, calculator):
        """Test that MINIMAL redaction preserves connection strings but redacts passwords."""
        comparison = PropertyComparison(
            property_path="properties.connectionStrings[0].connectionString",
            source_value="Server=tcp:myserver.database.windows.net;Password=Secret123;",
            target_value="Server=tcp:myserver.database.windows.net;Password=Secret456;",
            match=False,
            redacted=False,
        )

        redacted = calculator._redact_if_sensitive(comparison, RedactionLevel.MINIMAL)

        # MINIMAL should redact password part but keep server info
        assert "myserver.database.windows.net" in redacted.source_value
        assert "Password" not in redacted.source_value or "[REDACTED]" in redacted.source_value

    def test_redact_sensitive_properties_none_redaction(self, calculator):
        """Test that NONE redaction level keeps all values."""
        comparison = PropertyComparison(
            property_path="properties.password",
            source_value="SecretPassword123!",
            target_value="SecretPassword456!",
            match=False,
            redacted=False,
        )

        redacted = calculator._redact_if_sensitive(comparison, RedactionLevel.NONE)

        assert redacted.redacted is False
        assert redacted.source_value == "SecretPassword123!"
        assert redacted.target_value == "SecretPassword456!"

    def test_sensitive_property_patterns(self, calculator):
        """Test detection of sensitive property patterns."""
        sensitive_paths = [
            "properties.password",
            "properties.adminPassword",
            "properties.connectionStrings[0].password",
            "properties.secretKey",
            "properties.apiKey",
            "properties.token",
            "properties.storageAccountKeys",
        ]

        for path in sensitive_paths:
            assert calculator._is_sensitive_property(path) is True

    def test_non_sensitive_property_patterns(self, calculator):
        """Test that non-sensitive properties are not redacted."""
        non_sensitive_paths = [
            "sku.name",
            "location",
            "properties.sku.tier",
            "tags.environment",
            "properties.accessTier",
        ]

        for path in non_sensitive_paths:
            assert calculator._is_sensitive_property(path) is False

    def test_calculate_fidelity_end_to_end(self, calculator):
        """Test end-to-end fidelity calculation."""
        # Mock source resources
        calculator.session_manager.execute_read.side_effect = [
            # Source resources
            [
                {
                    "id": "/subscriptions/source-sub-123/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/storage1",
                    "name": "storage1",
                    "type": "Microsoft.Storage/storageAccounts",
                    "properties": {"sku": {"name": "Standard_LRS"}},
                }
            ],
            # Target resources
            [
                {
                    "id": "/subscriptions/target-sub-456/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/storage1",
                    "name": "storage1",
                    "type": "Microsoft.Storage/storageAccounts",
                    "properties": {"sku": {"name": "Premium_LRS"}},
                }
            ],
        ]

        # calculate_fidelity is synchronous, not async
        result = calculator.calculate_fidelity()

        # Should have classifications and metrics
        assert result is not None
        assert hasattr(result, "classifications")
        assert hasattr(result, "metrics")

    def test_calculate_metrics_from_classifications(self, calculator):
        """Test metrics calculation from resource classifications."""
        classifications = [
            ResourceClassification(
                resource_id="resource1",
                resource_name="res1",
                resource_type="Microsoft.Storage/storageAccounts",
                status=ResourceStatus.EXACT_MATCH,
                source_exists=True,
                target_exists=True,
                property_comparisons=[],
                mismatch_count=0,
                match_count=5,
            ),
            ResourceClassification(
                resource_id="resource2",
                resource_name="res2",
                resource_type="Microsoft.Compute/virtualMachines",
                status=ResourceStatus.DRIFTED,
                source_exists=True,
                target_exists=True,
                property_comparisons=[],
                mismatch_count=2,
                match_count=3,
            ),
            ResourceClassification(
                resource_id="resource3",
                resource_name="res3",
                resource_type="Microsoft.Network/virtualNetworks",
                status=ResourceStatus.MISSING_TARGET,
                source_exists=True,
                target_exists=False,
                property_comparisons=[],
                mismatch_count=0,
                match_count=0,
            ),
        ]

        metrics = calculator._calculate_metrics(classifications)

        assert metrics.total_resources == 3
        assert metrics.exact_match == 1
        assert metrics.drifted == 1
        assert metrics.missing_target == 1
        # 1 exact match out of 3 total = 33.33%
        assert metrics.match_percentage >= 33.0
        assert metrics.match_percentage <= 34.0


class TestResourceFidelityCalculatorEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def calculator(self):
        """Create calculator with mock dependencies."""
        manager = Mock()
        # Use synchronous Mock, not AsyncMock - execute_read is sync in Neo4jSessionManager
        manager.execute_read = Mock()
        with patch("src.validation.resource_fidelity_calculator.ResourceComparator"):
            return ResourceFidelityCalculator(
                session_manager=manager,
                source_subscription_id="source-sub-123",
                target_subscription_id="target-sub-456",
            )

    def test_compare_properties_handles_null_values(self, calculator):
        """Test property comparison handles null/None values gracefully."""
        source_props = {"sku": None, "location": "eastus"}
        target_props = {"sku": None, "location": "eastus"}

        comparisons = calculator._compare_properties(source_props, target_props, RedactionLevel.FULL)

        # Should handle None without crashing
        assert len(comparisons) > 0

    def test_compare_properties_handles_nested_objects(self, calculator):
        """Test property comparison handles deeply nested objects."""
        source_props = {
            "properties": {
                "networkProfile": {
                    "networkInterfaces": [
                        {"id": "/subscriptions/abc/networkInterfaces/nic1", "primary": True}
                    ]
                }
            }
        }
        target_props = {
            "properties": {
                "networkProfile": {
                    "networkInterfaces": [
                        {"id": "/subscriptions/def/networkInterfaces/nic1", "primary": True}
                    ]
                }
            }
        }

        comparisons = calculator._compare_properties(source_props, target_props, RedactionLevel.FULL)

        # Should recursively compare nested properties
        assert len(comparisons) > 0
        # Should detect ID difference
        id_comparisons = [c for c in comparisons if "networkInterfaces" in c.property_path]
        assert len(id_comparisons) > 0

    def test_calculate_fidelity_handles_empty_subscriptions(self, calculator):
        """Test fidelity calculation with no resources in subscriptions."""
        calculator.session_manager.execute_read.side_effect = [
            [],  # No source resources
            [],  # No target resources
        ]

        result = calculator.calculate_fidelity()

        # Should handle empty gracefully
        assert result.metrics.total_resources == 0

    def test_calculate_fidelity_handles_query_errors(self, calculator):
        """Test that calculator handles Neo4j query errors gracefully."""
        calculator.session_manager.execute_read.side_effect = Exception("Neo4j connection failed")

        # Should raise or log error appropriately
        with pytest.raises(Exception):
            calculator.calculate_fidelity()


class TestResourceFidelityCalculatorIntegrationWithComparator:
    """Test integration between ResourceFidelityCalculator and ResourceComparator."""

    @pytest.fixture
    def mock_resource_comparator(self):
        """Create mock ResourceComparator with realistic behavior."""
        from src.iac.resource_comparator import ComparisonResult, ResourceClassification as IaCClassification, ResourceState

        comparator = Mock()

        # Mock comparison result
        comparator.compare_resources.return_value = ComparisonResult(
            classifications=[
                IaCClassification(
                    abstracted_resource={"id": "resource1", "type": "Microsoft.Storage/storageAccounts"},
                    target_resource=Mock(id="resource1", properties={"sku": {"name": "Standard_LRS"}}),
                    classification=ResourceState.EXACT_MATCH,
                    drift_details=None,
                )
            ],
            summary={"new": 0, "exact_match": 1, "drifted": 0, "orphaned": 0},
        )
        return comparator

    def test_calculator_uses_comparator_for_comparison(self, mock_resource_comparator):
        """Test that calculator delegates to ResourceComparator."""
        manager = Mock()
        # Use synchronous Mock, not AsyncMock
        manager.execute_read = Mock(return_value=[])

        with patch("src.validation.resource_fidelity_calculator.ResourceComparator", return_value=mock_resource_comparator):
            calculator = ResourceFidelityCalculator(
                session_manager=manager,
                source_subscription_id="source-sub-123",
                target_subscription_id="target-sub-456",
            )

            # Trigger comparison
            calculator.calculate_fidelity()

            # Verify comparator was used
            mock_resource_comparator.compare_resources.assert_called()

    def test_calculator_converts_comparator_results(self, mock_resource_comparator):
        """Test that calculator converts ResourceComparator results to fidelity format."""
        manager = Mock()
        # Use synchronous Mock, not AsyncMock
        manager.execute_read = Mock(return_value=[])

        with patch("src.validation.resource_fidelity_calculator.ResourceComparator", return_value=mock_resource_comparator):
            calculator = ResourceFidelityCalculator(
                session_manager=manager,
                source_subscription_id="source-sub-123",
                target_subscription_id="target-sub-456",
            )

            result = calculator.calculate_fidelity()

            # Should convert to fidelity-specific classification
            assert len(result.classifications) > 0
            assert result.classifications[0].status in [
                ResourceStatus.EXACT_MATCH,
                ResourceStatus.DRIFTED,
                ResourceStatus.MISSING_TARGET,
                ResourceStatus.MISSING_SOURCE,
            ]
