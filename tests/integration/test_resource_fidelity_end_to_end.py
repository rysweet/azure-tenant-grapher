"""
Integration tests for Resource-Level Fidelity Validation.

Tests end-to-end workflows including Neo4j integration, cross-subscription
comparison, and historical tracking.

Testing pyramid distribution: 30% integration tests (this file)
"""

import json
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock, patch

import pytest

# These imports will fail initially - that's expected for TDD
try:
    from src.utils.session_manager import Neo4jSessionManager
    from src.validation.resource_fidelity_calculator import (
        PropertyComparison,
        RedactionLevel,
        ResourceFidelityCalculator,
        ResourceFidelityMetrics,
        ResourceStatus,
    )
except ImportError:
    # TDD: Modules don't exist yet
    pass


@pytest.mark.integration
class TestResourceFidelityWithNeo4j:
    """Test resource fidelity validation with real Neo4j queries."""

    @pytest.fixture
    def neo4j_manager(self):
        """Create Neo4j session manager for testing."""
        # Mock Neo4j connection
        manager = Mock(spec=Neo4jSessionManager)
        manager.execute_read = AsyncMock()
        manager.execute_write = AsyncMock()
        return manager

    @pytest.fixture
    def calculator(self, neo4j_manager):
        """Create ResourceFidelityCalculator with Neo4j manager."""
        return ResourceFidelityCalculator(
            session_manager=neo4j_manager,
            source_subscription_id="source-sub-abc123",
            target_subscription_id="target-sub-def456",
        )

    @pytest.mark.asyncio
    async def test_query_source_resources_from_neo4j(self, calculator, neo4j_manager):
        """Test querying source resources from Neo4j."""
        # Mock Neo4j response
        neo4j_manager.execute_read.return_value = [
            {
                "id": "/subscriptions/source-sub-abc123/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1",
                "name": "storage1",
                "type": "Microsoft.Storage/storageAccounts",
                "location": "eastus",
                "properties": {
                    "sku": {"name": "Standard_LRS"},
                    "accessTier": "Hot",
                },
                "tags": {"environment": "production"},
            },
            {
                "id": "/subscriptions/source-sub-abc123/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
                "name": "vm1",
                "type": "Microsoft.Compute/virtualMachines",
                "location": "eastus",
                "properties": {
                    "hardwareProfile": {"vmSize": "Standard_D2s_v3"},
                },
            },
        ]

        resources = await calculator._query_source_resources()

        # Verify Neo4j query was called
        neo4j_manager.execute_read.assert_called_once()

        # Verify resources were returned
        assert len(resources) == 2
        assert resources[0]["name"] == "storage1"
        assert resources[1]["name"] == "vm1"

    @pytest.mark.asyncio
    async def test_query_target_resources_from_neo4j(self, calculator, neo4j_manager):
        """Test querying target resources from Neo4j."""
        neo4j_manager.execute_read.return_value = [
            {
                "id": "/subscriptions/target-sub-def456/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1",
                "name": "storage1",
                "type": "Microsoft.Storage/storageAccounts",
                "location": "westus",  # Different region
                "properties": {
                    "sku": {"name": "Premium_LRS"},  # Different SKU
                    "accessTier": "Hot",
                },
                "tags": {"environment": "production"},
            }
        ]

        resources = await calculator._query_target_resources()

        neo4j_manager.execute_read.assert_called_once()
        assert len(resources) == 1
        assert resources[0]["location"] == "westus"

    @pytest.mark.asyncio
    async def test_query_with_resource_type_filter(self, calculator, neo4j_manager):
        """Test Neo4j query with resource type filtering."""
        neo4j_manager.execute_read.return_value = [
            {
                "id": "/subscriptions/source-sub-abc123/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1",
                "name": "storage1",
                "type": "Microsoft.Storage/storageAccounts",
                "properties": {},
            }
        ]

        resources = await calculator._query_source_resources(resource_type="Microsoft.Storage/storageAccounts")

        # Verify filter was applied in query
        call_args = neo4j_manager.execute_read.call_args
        # Query should include WHERE clause for resource type
        assert "Microsoft.Storage/storageAccounts" in str(call_args)


@pytest.mark.integration
class TestCrossSubscriptionComparison:
    """Test comparing resources across different Azure subscriptions."""

    @pytest.fixture
    def calculator_with_mock_data(self):
        """Create calculator with mocked source and target data."""
        manager = Mock()
        calculator = ResourceFidelityCalculator(
            session_manager=manager,
            source_subscription_id="source-sub-abc123",
            target_subscription_id="target-sub-def456",
        )

        # Mock query methods
        calculator._query_source_resources = AsyncMock(
            return_value=[
                {
                    "id": "/subscriptions/source-sub-abc123/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1",
                    "name": "storage1",
                    "type": "Microsoft.Storage/storageAccounts",
                    "properties": {
                        "sku": {"name": "Standard_LRS"},
                        "accessTier": "Hot",
                    },
                },
                {
                    "id": "/subscriptions/source-sub-abc123/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
                    "name": "vm1",
                    "type": "Microsoft.Compute/virtualMachines",
                    "properties": {
                        "hardwareProfile": {"vmSize": "Standard_D2s_v3"},
                    },
                },
            ]
        )

        calculator._query_target_resources = AsyncMock(
            return_value=[
                {
                    "id": "/subscriptions/target-sub-def456/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1",
                    "name": "storage1",
                    "type": "Microsoft.Storage/storageAccounts",
                    "properties": {
                        "sku": {"name": "Premium_LRS"},  # Drifted
                        "accessTier": "Hot",
                    },
                }
                # vm1 missing in target
            ]
        )

        return calculator

    @pytest.mark.asyncio
    async def test_detects_drifted_resources(self, calculator_with_mock_data):
        """Test detection of resources with property differences."""
        result = await calculator_with_mock_data.calculate_fidelity()

        # Should detect storage1 as DRIFTED (SKU mismatch)
        drifted = [c for c in result.classifications if c.status == ResourceStatus.DRIFTED]
        assert len(drifted) >= 1
        assert "storage1" in drifted[0].resource_name

    @pytest.mark.asyncio
    async def test_detects_missing_target_resources(self, calculator_with_mock_data):
        """Test detection of resources missing in target subscription."""
        result = await calculator_with_mock_data.calculate_fidelity()

        # Should detect vm1 as MISSING_TARGET
        missing = [c for c in result.classifications if c.status == ResourceStatus.MISSING_TARGET]
        assert len(missing) >= 1
        assert "vm1" in missing[0].resource_name

    @pytest.mark.asyncio
    async def test_metrics_reflect_cross_subscription_comparison(self, calculator_with_mock_data):
        """Test that metrics accurately reflect cross-subscription state."""
        result = await calculator_with_mock_data.calculate_fidelity()

        # Should have 2 total resources (from source)
        assert result.metrics.total_resources == 2
        # Should have 1 drifted (storage1)
        assert result.metrics.drifted == 1
        # Should have 1 missing_target (vm1)
        assert result.metrics.missing_target == 1
        # Match percentage should be 0% (no exact matches)
        assert result.metrics.match_percentage == 0.0


@pytest.mark.integration
class TestMultipleResourceTypes:
    """Test validation across multiple Azure resource types."""

    @pytest.fixture
    def multi_type_calculator(self):
        """Create calculator with multiple resource types."""
        manager = Mock()
        calculator = ResourceFidelityCalculator(
            session_manager=manager,
            source_subscription_id="source-sub",
            target_subscription_id="target-sub",
        )

        calculator._query_source_resources = AsyncMock(
            return_value=[
                {
                    "id": "/subscriptions/source-sub/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/storage1",
                    "name": "storage1",
                    "type": "Microsoft.Storage/storageAccounts",
                    "properties": {"sku": {"name": "Standard_LRS"}},
                },
                {
                    "id": "/subscriptions/source-sub/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm1",
                    "name": "vm1",
                    "type": "Microsoft.Compute/virtualMachines",
                    "properties": {"hardwareProfile": {"vmSize": "Standard_D2s_v3"}},
                },
                {
                    "id": "/subscriptions/source-sub/resourceGroups/rg/providers/Microsoft.Network/virtualNetworks/vnet1",
                    "name": "vnet1",
                    "type": "Microsoft.Network/virtualNetworks",
                    "properties": {"addressSpace": {"addressPrefixes": ["10.0.0.0/16"]}},
                },
            ]
        )

        calculator._query_target_resources = AsyncMock(
            return_value=[
                {
                    "id": "/subscriptions/target-sub/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/storage1",
                    "name": "storage1",
                    "type": "Microsoft.Storage/storageAccounts",
                    "properties": {"sku": {"name": "Standard_LRS"}},  # Match
                },
                {
                    "id": "/subscriptions/target-sub/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm1",
                    "name": "vm1",
                    "type": "Microsoft.Compute/virtualMachines",
                    "properties": {"hardwareProfile": {"vmSize": "Standard_D4s_v3"}},  # Drifted
                },
                {
                    "id": "/subscriptions/target-sub/resourceGroups/rg/providers/Microsoft.Network/virtualNetworks/vnet1",
                    "name": "vnet1",
                    "type": "Microsoft.Network/virtualNetworks",
                    "properties": {"addressSpace": {"addressPrefixes": ["10.1.0.0/16"]}},  # Drifted
                },
            ]
        )

        return calculator

    @pytest.mark.asyncio
    async def test_validates_multiple_resource_types(self, multi_type_calculator):
        """Test validation handles multiple Azure resource types correctly."""
        result = await multi_type_calculator.calculate_fidelity()

        # Should have classifications for all resource types
        assert result.metrics.total_resources == 3

        # Verify each resource type is present
        types = {c.resource_type for c in result.classifications}
        assert "Microsoft.Storage/storageAccounts" in types
        assert "Microsoft.Compute/virtualMachines" in types
        assert "Microsoft.Network/virtualNetworks" in types

    @pytest.mark.asyncio
    async def test_metrics_by_resource_type(self, multi_type_calculator):
        """Test that metrics can be broken down by resource type."""
        result = await multi_type_calculator.calculate_fidelity()

        # Should be able to group classifications by type
        classifications_by_type = {}
        for classification in result.classifications:
            rtype = classification.resource_type
            if rtype not in classifications_by_type:
                classifications_by_type[rtype] = []
            classifications_by_type[rtype].append(classification)

        # Each type should have 1 classification
        assert len(classifications_by_type["Microsoft.Storage/storageAccounts"]) == 1
        assert len(classifications_by_type["Microsoft.Compute/virtualMachines"]) == 1
        assert len(classifications_by_type["Microsoft.Network/virtualNetworks"]) == 1


@pytest.mark.integration
class TestHistoricalTracking:
    """Test historical tracking of fidelity metrics."""

    @pytest.fixture
    def calculator_with_tracking(self):
        """Create calculator with tracking enabled."""
        manager = Mock()
        manager.execute_write = AsyncMock()

        calculator = ResourceFidelityCalculator(
            session_manager=manager,
            source_subscription_id="source-sub",
            target_subscription_id="target-sub",
        )

        calculator._query_source_resources = AsyncMock(return_value=[])
        calculator._query_target_resources = AsyncMock(return_value=[])

        return calculator

    @pytest.mark.asyncio
    async def test_save_metrics_to_database(self, calculator_with_tracking):
        """Test saving fidelity metrics to Neo4j for historical tracking."""
        result = await calculator_with_tracking.calculate_fidelity()

        # Save metrics with tracking
        await calculator_with_tracking.save_metrics(result.metrics, track=True)

        # Verify write operation was called
        calculator_with_tracking.session_manager.execute_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_metrics_include_timestamp(self, calculator_with_tracking):
        """Test that tracked metrics include timestamp."""
        result = await calculator_with_tracking.calculate_fidelity()

        # Metrics should have timestamp
        assert hasattr(result.metrics, "timestamp")
        assert result.metrics.timestamp is not None

    @pytest.mark.asyncio
    async def test_query_historical_metrics(self, calculator_with_tracking):
        """Test querying historical fidelity metrics."""
        calculator_with_tracking.session_manager.execute_read.return_value = [
            {
                "timestamp": "2026-02-05T14:30:00Z",
                "total_resources": 100,
                "exact_match": 95,
                "drifted": 5,
                "match_percentage": 95.0,
            },
            {
                "timestamp": "2026-02-04T14:30:00Z",
                "total_resources": 100,
                "exact_match": 98,
                "drifted": 2,
                "match_percentage": 98.0,
            },
        ]

        history = await calculator_with_tracking.get_historical_metrics(days=7)

        # Should return historical data
        assert len(history) == 2
        assert history[0]["match_percentage"] == 95.0
        assert history[1]["match_percentage"] == 98.0


@pytest.mark.integration
class TestJSONExport:
    """Test JSON export functionality for validation results."""

    @pytest.fixture
    def calculator_with_results(self):
        """Create calculator with sample results."""
        manager = Mock()
        calculator = ResourceFidelityCalculator(
            session_manager=manager,
            source_subscription_id="source-sub",
            target_subscription_id="target-sub",
        )

        # Create sample result
        from dataclasses import dataclass
        from datetime import datetime

        @dataclass
        class FidelityResult:
            classifications: List[Any]
            metrics: ResourceFidelityMetrics
            timestamp: str = datetime.utcnow().isoformat()
            redaction_level: str = "FULL"

        calculator._result = FidelityResult(
            classifications=[
                ResourceClassification(
                    resource_id="/subscriptions/source-sub/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/storage1",
                    resource_name="storage1",
                    resource_type="Microsoft.Storage/storageAccounts",
                    status=ResourceStatus.DRIFTED,
                    source_exists=True,
                    target_exists=True,
                    property_comparisons=[
                        PropertyComparison("sku.name", "Standard_LRS", "Premium_LRS", False, False)
                    ],
                    mismatch_count=1,
                    match_count=2,
                )
            ],
            metrics=ResourceFidelityMetrics(
                total_resources=1,
                exact_match=0,
                drifted=1,
                missing_target=0,
                missing_source=0,
                match_percentage=0.0,
                top_mismatched_properties=[{"property": "sku.name", "count": 1}],
            ),
        )

        return calculator

    def test_export_to_json_file(self, calculator_with_results, tmp_path):
        """Test exporting validation results to JSON file."""
        output_file = tmp_path / "fidelity-report.json"

        calculator_with_results.export_to_json(str(output_file))

        # Verify file was created
        assert output_file.exists()

        # Verify file contains valid JSON
        with open(output_file) as f:
            data = json.load(f)

        assert "metadata" in data
        assert "resources" in data
        assert "summary" in data
        assert "security_warnings" in data

    def test_json_export_includes_metadata(self, calculator_with_results, tmp_path):
        """Test JSON export includes validation metadata."""
        output_file = tmp_path / "report.json"
        calculator_with_results.export_to_json(str(output_file))

        with open(output_file) as f:
            data = json.load(f)

        metadata = data["metadata"]
        assert "validation_timestamp" in metadata
        assert "source_subscription" in metadata
        assert "target_subscription" in metadata
        assert "redaction_level" in metadata

    def test_json_export_includes_resource_classifications(self, calculator_with_results, tmp_path):
        """Test JSON export includes detailed resource classifications."""
        output_file = tmp_path / "report.json"
        calculator_with_results.export_to_json(str(output_file))

        with open(output_file) as f:
            data = json.load(f)

        resources = data["resources"]
        assert len(resources) == 1
        assert resources[0]["resource_name"] == "storage1"
        assert resources[0]["status"] == "drifted"
        assert "property_comparisons" in resources[0]

    def test_json_export_includes_summary_metrics(self, calculator_with_results, tmp_path):
        """Test JSON export includes summary metrics."""
        output_file = tmp_path / "report.json"
        calculator_with_results.export_to_json(str(output_file))

        with open(output_file) as f:
            data = json.load(f)

        summary = data["summary"]
        assert summary["total_resources"] == 1
        assert summary["drifted"] == 1
        assert "top_mismatched_properties" in summary

    def test_json_export_includes_security_warnings(self, calculator_with_results, tmp_path):
        """Test JSON export includes security warnings."""
        output_file = tmp_path / "report.json"
        calculator_with_results.export_to_json(str(output_file))

        with open(output_file) as f:
            data = json.load(f)

        warnings = data["security_warnings"]
        assert len(warnings) > 0
        assert any("redacted" in w.lower() for w in warnings)


@pytest.mark.integration
class TestFilteredValidation:
    """Test validation with resource type filters."""

    @pytest.fixture
    def calculator(self):
        """Create calculator for testing."""
        manager = Mock()
        return ResourceFidelityCalculator(
            session_manager=manager,
            source_subscription_id="source-sub",
            target_subscription_id="target-sub",
        )

    @pytest.mark.asyncio
    async def test_filter_by_storage_accounts(self, calculator):
        """Test filtering validation to only Storage Accounts."""
        calculator._query_source_resources = AsyncMock(
            return_value=[
                {
                    "id": "/subscriptions/source-sub/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/storage1",
                    "name": "storage1",
                    "type": "Microsoft.Storage/storageAccounts",
                    "properties": {},
                }
            ]
        )
        calculator._query_target_resources = AsyncMock(return_value=[])

        result = await calculator.calculate_fidelity(resource_type="Microsoft.Storage/storageAccounts")

        # Should only have Storage Account resources
        assert all(c.resource_type == "Microsoft.Storage/storageAccounts" for c in result.classifications)

    @pytest.mark.asyncio
    async def test_filter_by_virtual_machines(self, calculator):
        """Test filtering validation to only Virtual Machines."""
        calculator._query_source_resources = AsyncMock(
            return_value=[
                {
                    "id": "/subscriptions/source-sub/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm1",
                    "name": "vm1",
                    "type": "Microsoft.Compute/virtualMachines",
                    "properties": {},
                }
            ]
        )
        calculator._query_target_resources = AsyncMock(return_value=[])

        result = await calculator.calculate_fidelity(resource_type="Microsoft.Compute/virtualMachines")

        assert all(c.resource_type == "Microsoft.Compute/virtualMachines" for c in result.classifications)
