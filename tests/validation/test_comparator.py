"""Tests for graph comparator module."""

from src.validation.comparator import (
    ComparisonResult,
    compare_filtered_graphs,
    compare_graphs,
)


class TestCompareGraphs:
    """Tests for compare_graphs function."""

    def test_compare_identical_graphs(self):
        """Test comparison of identical graphs returns 100% similarity."""
        resources = [
            {"id": "res1", "type": "Microsoft.Compute/virtualMachines", "name": "vm1"},
            {
                "id": "res2",
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet1",
            },
        ]

        result = compare_graphs(resources, resources)

        assert result.source_resource_count == 2
        assert result.target_resource_count == 2
        assert result.similarity_score == 100.0
        assert len(result.missing_resources) == 0
        assert len(result.extra_resources) == 0

    def test_compare_empty_graphs(self):
        """Test comparison of empty graphs."""
        result = compare_graphs([], [])

        assert result.source_resource_count == 0
        assert result.target_resource_count == 0
        assert result.similarity_score == 100.0
        assert len(result.missing_resources) == 0
        assert len(result.extra_resources) == 0

    def test_compare_with_missing_resources(self):
        """Test comparison where target is missing resources."""
        source = [
            {"id": "res1", "type": "Microsoft.Compute/virtualMachines"},
            {"id": "res2", "type": "Microsoft.Network/virtualNetworks"},
        ]
        target = [{"id": "res1", "type": "Microsoft.Compute/virtualMachines"}]

        result = compare_graphs(source, target)

        assert result.source_resource_count == 2
        assert result.target_resource_count == 1
        assert result.similarity_score == 50.0
        assert len(result.missing_resources) == 1
        assert "Microsoft.Network/virtualNetworks" in result.missing_resources[0]

    def test_compare_with_extra_resources(self):
        """Test comparison where target has extra resources."""
        source = [{"id": "res1", "type": "Microsoft.Compute/virtualMachines"}]
        target = [
            {"id": "res1", "type": "Microsoft.Compute/virtualMachines"},
            {"id": "res2", "type": "Microsoft.Network/virtualNetworks"},
        ]

        result = compare_graphs(source, target)

        assert result.source_resource_count == 1
        assert result.target_resource_count == 2
        assert result.similarity_score == 50.0
        assert len(result.extra_resources) == 1
        assert "Microsoft.Network/virtualNetworks" in result.extra_resources[0]

    def test_compare_source_empty_target_nonempty(self):
        """Test comparison where source is empty but target has resources."""
        source = []
        target = [{"id": "res1", "type": "Microsoft.Compute/virtualMachines"}]

        result = compare_graphs(source, target)

        assert result.source_resource_count == 0
        assert result.target_resource_count == 1
        assert result.similarity_score == 0.0

    def test_compare_source_nonempty_target_empty(self):
        """Test comparison where source has resources but target is empty."""
        source = [{"id": "res1", "type": "Microsoft.Compute/virtualMachines"}]
        target = []

        result = compare_graphs(source, target)

        assert result.source_resource_count == 1
        assert result.target_resource_count == 0
        assert result.similarity_score == 0.0

    def test_resource_type_counts(self):
        """Test that resource type counts are correctly calculated."""
        source = [
            {"id": "res1", "type": "Microsoft.Compute/virtualMachines"},
            {"id": "res2", "type": "Microsoft.Compute/virtualMachines"},
            {"id": "res3", "type": "Microsoft.Storage/storageAccounts"},
        ]
        target = [
            {"id": "res1", "type": "Microsoft.Compute/virtualMachines"},
            {"id": "res2", "type": "Microsoft.Storage/storageAccounts"},
            {"id": "res3", "type": "Microsoft.Storage/storageAccounts"},
        ]

        result = compare_graphs(source, target)

        assert result.resource_type_counts["Microsoft.Compute/virtualMachines"] == {
            "source": 2,
            "target": 1,
        }
        assert result.resource_type_counts["Microsoft.Storage/storageAccounts"] == {
            "source": 1,
            "target": 2,
        }

    def test_resources_without_type(self):
        """Test handling of resources without type attribute."""
        source = [
            {"id": "res1"},
            {"id": "res2", "type": "Microsoft.Compute/virtualMachines"},
        ]
        target = [
            {"id": "res1"},
            {"id": "res2", "type": "Microsoft.Compute/virtualMachines"},
        ]

        result = compare_graphs(source, target)

        assert result.source_resource_count == 2
        assert result.target_resource_count == 2
        assert "unknown" in result.resource_type_counts


class TestCompareFilteredGraphs:
    """Tests for compare_filtered_graphs function."""

    def test_filter_by_resource_group(self):
        """Test filtering resources by resourceGroup attribute."""
        source = [
            {"id": "res1", "type": "VM", "resourceGroup": "RG1"},
            {"id": "res2", "type": "VM", "resourceGroup": "RG2"},
        ]
        target = [
            {"id": "res3", "type": "VM", "resourceGroup": "RG1"},
            {"id": "res4", "type": "VM", "resourceGroup": "RG3"},
        ]

        result = compare_filtered_graphs(
            source, target, "resourceGroup=RG1", "resourceGroup=RG1"
        )

        assert result.source_resource_count == 1
        assert result.target_resource_count == 1
        assert result.similarity_score == 100.0

    def test_no_filter(self):
        """Test that None filters compare all resources."""
        source = [{"id": "res1", "type": "VM"}]
        target = [{"id": "res1", "type": "VM"}]

        result = compare_filtered_graphs(source, target, None, None)

        assert result.source_resource_count == 1
        assert result.target_resource_count == 1

    def test_invalid_filter_format(self):
        """Test that invalid filter format is handled gracefully."""
        source = [{"id": "res1", "type": "VM"}]
        target = [{"id": "res1", "type": "VM"}]

        # Invalid filter (no = sign) should be ignored
        result = compare_filtered_graphs(source, target, "invalid", None)

        assert result.source_resource_count == 1
        assert result.target_resource_count == 1

    def test_filter_no_matches(self):
        """Test filtering when no resources match."""
        source = [{"id": "res1", "type": "VM", "location": "eastus"}]
        target = [{"id": "res2", "type": "VM", "location": "westus"}]

        result = compare_filtered_graphs(
            source, target, "location=westus", "location=eastus"
        )

        assert result.source_resource_count == 0
        assert result.target_resource_count == 0
        assert result.similarity_score == 100.0


class TestComparisonResult:
    """Tests for ComparisonResult dataclass."""

    def test_comparison_result_creation(self):
        """Test creating ComparisonResult instance."""
        result = ComparisonResult(
            source_resource_count=10,
            target_resource_count=8,
            resource_type_counts={"VM": {"source": 10, "target": 8}},
            missing_resources=["VM (2 missing)"],
            extra_resources=[],
            similarity_score=80.0,
        )

        assert result.source_resource_count == 10
        assert result.target_resource_count == 8
        assert result.similarity_score == 80.0
        assert len(result.missing_resources) == 1
        assert len(result.extra_resources) == 0
