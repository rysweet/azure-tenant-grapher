"""Tests for subset selection functionality."""

import pytest

from src.iac.subset import SubsetFilter, SubsetSelector
from src.iac.traverser import TenantGraph


class TestSubsetFilter:
    """Test SubsetFilter parsing and initialization."""

    def test_empty_filter(self):
        """Test parsing empty filter string."""
        filter_obj = SubsetFilter.parse("")
        assert filter_obj.node_ids is None
        assert filter_obj.resource_types is None
        assert filter_obj.labels is None
        assert filter_obj.cypher_query is None

    def test_parse_node_ids(self):
        """Test parsing node IDs filter."""
        filter_obj = SubsetFilter.parse("nodeIds=abc123,def456")
        assert filter_obj.node_ids == ["abc123", "def456"]

    def test_parse_resource_types(self):
        """Test parsing resource types filter."""
        filter_obj = SubsetFilter.parse("types=Microsoft.Storage/*,Microsoft.Compute/*")
        assert filter_obj.resource_types == [
            "Microsoft.Storage/*",
            "Microsoft.Compute/*",
        ]

    def test_parse_labels(self):
        """Test parsing labels filter."""
        filter_obj = SubsetFilter.parse("label=DMZ")
        assert filter_obj.labels == ["DMZ"]

    def test_parse_complex_filter(self):
        """Test parsing complex filter with multiple predicates."""
        filter_obj = SubsetFilter.parse(
            "types=Microsoft.Storage/*;label=DMZ;nodeIds=abc123"
        )
        assert filter_obj.resource_types == ["Microsoft.Storage/*"]
        assert filter_obj.labels == ["DMZ"]
        assert filter_obj.node_ids == ["abc123"]


class TestSubsetSelector:
    """Test SubsetSelector functionality."""

    @pytest.fixture
    def sample_graph(self):
        """Create a sample tenant graph for testing."""
        resources = [
            {
                "id": "storage1",
                "type": "Microsoft.Storage/storageAccounts",
                "name": "mystorageaccount",
            },
            {"id": "vm1", "type": "Microsoft.Compute/virtualMachines", "name": "myvm"},
            {
                "id": "rg1",
                "type": "Microsoft.Resources/resourceGroups",
                "name": "myresourcegroup",
            },
        ]
        relationships = []
        return TenantGraph(resources=resources, relationships=relationships)

    def test_has_filters_empty(self):
        """Test has_filters with empty filter."""
        selector = SubsetSelector()
        filter_obj = SubsetFilter()
        assert not selector.has_filters(filter_obj)

    def test_has_filters_with_types(self):
        """Test has_filters with resource types."""
        selector = SubsetSelector()
        filter_obj = SubsetFilter(resource_types=["Microsoft.Storage/*"])
        assert selector.has_filters(filter_obj)

    def test_apply_type_filter(self, sample_graph):
        """Test applying type filter to graph."""
        selector = SubsetSelector()
        filter_obj = SubsetFilter(resource_types=["Microsoft.Storage/*"])

        filtered_graph = selector.apply(sample_graph, filter_obj)

        # Should only include storage account
        assert len(filtered_graph.resources) == 1
        assert filtered_graph.resources[0]["id"] == "storage1"

    def test_apply_no_filter_returns_full_graph(self, sample_graph):
        """Test that applying empty filter returns full graph."""
        selector = SubsetSelector()
        filter_obj = SubsetFilter()

        filtered_graph = selector.apply(sample_graph, filter_obj)

        # Should return same graph
        assert len(filtered_graph.resources) == len(sample_graph.resources)
        assert filtered_graph.resources == sample_graph.resources
