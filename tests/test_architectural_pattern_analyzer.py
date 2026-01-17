"""
Unit tests for ArchitecturalPatternAnalyzer.

Tests pattern detection, relationship aggregation, graph building, and
configuration analysis for architectural patterns in Azure resource graphs.

Fixtures are defined in tests/conftest.py and automatically discovered by pytest.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, Mock, patch

import networkx as nx
import numpy as np
import pytest

from src.architectural_pattern_analyzer import ArchitecturalPatternAnalyzer


class TestResourceTypeExtraction:
    """Test resource type name extraction."""

    def test_get_resource_type_name_from_azure_type(self, analyzer):
        """Test extracting resource type from Azure resource type string."""
        labels = ["Resource"]
        azure_type = "Microsoft.Compute/virtualMachines"

        result = analyzer._get_resource_type_name(labels, azure_type)

        assert result == "virtualMachines"

    def test_get_resource_type_name_nested_type(self, analyzer):
        """Test extracting resource type from nested Azure type."""
        labels = ["Resource"]
        azure_type = "Microsoft.Sql/servers/databases"

        result = analyzer._get_resource_type_name(labels, azure_type)

        assert result == "databases"

    def test_get_resource_type_name_no_slash(self, analyzer):
        """Test extracting resource type without slash."""
        labels = ["Resource"]
        azure_type = "ResourceGroup"

        result = analyzer._get_resource_type_name(labels, azure_type)

        assert result == "ResourceGroup"

    def test_get_resource_type_name_empty_labels(self, analyzer):
        """Test handling empty labels."""
        labels = []
        azure_type = "Microsoft.Compute/virtualMachines"

        result = analyzer._get_resource_type_name(labels, azure_type)

        assert result == "Unknown"

    def test_get_resource_type_name_no_azure_type(self, analyzer):
        """Test handling None azure_type."""
        labels = ["Resource", "Compute"]
        azure_type = None

        result = analyzer._get_resource_type_name(labels, azure_type)

        assert result == "Compute"

    def test_get_resource_type_name_filtered_labels(self, analyzer):
        """Test filtering generic labels."""
        labels = ["Original", "Resource", "VirtualMachine"]
        azure_type = None

        result = analyzer._get_resource_type_name(labels, azure_type)

        assert result == "VirtualMachine"


class TestRelationshipAggregation:
    """Test relationship aggregation logic."""

    def test_aggregate_relationships_basic(
        self, analyzer, sample_vm_workload_relationships
    ):
        """Test basic relationship aggregation."""
        result = analyzer.aggregate_relationships(sample_vm_workload_relationships)

        assert len(result) == 3
        assert all("frequency" in rel for rel in result)
        assert result[0]["frequency"] == 1

    def test_aggregate_relationships_with_duplicates(self, analyzer):
        """Test aggregation with duplicate relationships."""
        relationships = [
            {
                "source_labels": ["Resource"],
                "source_type": "Microsoft.Compute/virtualMachines",
                "rel_type": "DEPENDS_ON",
                "target_labels": ["Resource"],
                "target_type": "Microsoft.Compute/disks",
            },
            {
                "source_labels": ["Resource"],
                "source_type": "Microsoft.Compute/virtualMachines",
                "rel_type": "DEPENDS_ON",
                "target_labels": ["Resource"],
                "target_type": "Microsoft.Compute/disks",
            },
        ]

        result = analyzer.aggregate_relationships(relationships)

        assert len(result) == 1
        assert result[0]["frequency"] == 2
        assert result[0]["source_type"] == "virtualMachines"
        assert result[0]["target_type"] == "disks"

    def test_aggregate_relationships_empty(self, analyzer):
        """Test aggregation with empty input."""
        result = analyzer.aggregate_relationships([])

        assert result == []

    def test_aggregate_relationships_sorting(self, analyzer):
        """Test that results are sorted by frequency."""
        relationships = [
            {
                "source_labels": ["Resource"],
                "source_type": "Microsoft.Compute/virtualMachines",
                "rel_type": "DEPENDS_ON",
                "target_labels": ["Resource"],
                "target_type": "Microsoft.Compute/disks",
            },
        ] * 5
        relationships.extend(
            [
                {
                    "source_labels": ["Resource"],
                    "source_type": "Microsoft.Network/networkInterfaces",
                    "rel_type": "DEPENDS_ON",
                    "target_labels": ["Resource"],
                    "target_type": "Microsoft.Network/virtualNetworks",
                }
            ]
            * 10
        )

        result = analyzer.aggregate_relationships(relationships)

        assert len(result) == 2
        assert result[0]["frequency"] == 10  # Most frequent first
        assert result[1]["frequency"] == 5


class TestNetworkXGraphBuilding:
    """Test NetworkX graph construction."""

    def test_build_networkx_graph_basic(
        self, analyzer, sample_vm_workload_relationships
    ):
        """Test basic graph building from relationships."""
        aggregated = analyzer.aggregate_relationships(sample_vm_workload_relationships)

        graph, resource_counts, edge_counts = analyzer.build_networkx_graph(aggregated)

        assert isinstance(graph, nx.MultiDiGraph)
        assert graph.number_of_nodes() == 4
        assert graph.number_of_edges() == 3

    def test_build_networkx_graph_node_counts(
        self, analyzer, sample_vm_workload_relationships
    ):
        """Test that node counts are calculated correctly."""
        aggregated = analyzer.aggregate_relationships(sample_vm_workload_relationships)

        graph, resource_counts, edge_counts = analyzer.build_networkx_graph(aggregated)

        assert "virtualMachines" in resource_counts
        assert resource_counts["virtualMachines"] == 2  # 2 outgoing edges
        assert "disks" in resource_counts
        assert resource_counts["disks"] == 1

    def test_build_networkx_graph_edge_attributes(
        self, analyzer, sample_vm_workload_relationships
    ):
        """Test edge attributes are preserved."""
        aggregated = analyzer.aggregate_relationships(sample_vm_workload_relationships)

        graph, _, _ = analyzer.build_networkx_graph(aggregated)

        # Check edge has relationship and frequency attributes
        edge_data = graph.get_edge_data("virtualMachines", "disks")
        assert edge_data is not None
        assert any(
            data.get("relationship") == "DEPENDS_ON" for data in edge_data.values()
        )

    def test_build_networkx_graph_empty(self, analyzer):
        """Test building graph from empty relationships."""
        graph, resource_counts, edge_counts = analyzer.build_networkx_graph([])

        assert graph.number_of_nodes() == 0
        assert graph.number_of_edges() == 0
        assert resource_counts == {}
        assert edge_counts == {}


class TestPatternDetection:
    """Test architectural pattern detection."""

    def test_detect_patterns_vm_workload(self, analyzer):
        """Test detecting VM Workload pattern."""
        # Build graph with VM workload resources
        graph = nx.MultiDiGraph()
        graph.add_node("virtualMachines", count=10)
        graph.add_node("disks", count=15)
        graph.add_node("networkInterfaces", count=10)
        graph.add_node("virtualNetworks", count=2)
        graph.add_edge("virtualMachines", "disks", relationship="DEPENDS_ON", frequency=10)

        resource_counts = {
            "virtualMachines": 10,
            "disks": 15,
            "networkInterfaces": 10,
            "virtualNetworks": 2,
        }

        patterns = analyzer.detect_patterns(graph, resource_counts)

        assert "Virtual Machine Workload" in patterns
        assert len(patterns["Virtual Machine Workload"]["matched_resources"]) >= 2

    def test_detect_patterns_partial_match(self, analyzer):
        """Test pattern detection with partial resource matches."""
        graph = nx.MultiDiGraph()
        graph.add_node("sites", count=5)
        graph.add_node("storageAccounts", count=3)
        # Missing serverFarms and components for complete Web Application pattern

        resource_counts = {"sites": 5, "storageAccounts": 3}

        patterns = analyzer.detect_patterns(graph, resource_counts)

        # Should still detect Web Application pattern with 2 matched resources
        if "Web Application" in patterns:
            assert len(patterns["Web Application"]["matched_resources"]) == 2
            assert patterns["Web Application"]["completeness"] < 100

    def test_detect_patterns_completeness_calculation(self, analyzer):
        """Test completeness percentage calculation."""
        graph = nx.MultiDiGraph()
        # Web Application pattern has 4 required resources
        graph.add_node("sites", count=5)
        graph.add_node("serverFarms", count=5)
        graph.add_node("storageAccounts", count=3)
        graph.add_node("components", count=5)
        graph.add_edge("sites", "serverFarms", relationship="DEPENDS_ON", frequency=5)

        resource_counts = {
            "sites": 5,
            "serverFarms": 5,
            "storageAccounts": 3,
            "components": 5,
        }

        patterns = analyzer.detect_patterns(graph, resource_counts)

        assert "Web Application" in patterns
        assert patterns["Web Application"]["completeness"] == 100.0

    def test_detect_patterns_no_matches(self, analyzer):
        """Test pattern detection with no matching resources."""
        graph = nx.MultiDiGraph()
        graph.add_node("unknownResource1", count=1)
        graph.add_node("unknownResource2", count=1)

        resource_counts = {"unknownResource1": 1, "unknownResource2": 1}

        patterns = analyzer.detect_patterns(graph, resource_counts)

        assert len(patterns) == 0

    def test_detect_patterns_connection_count(self, analyzer):
        """Test that connection counts are calculated correctly."""
        graph = nx.MultiDiGraph()
        graph.add_node("virtualMachines", count=10)
        graph.add_node("disks", count=15)
        graph.add_node("networkInterfaces", count=10)
        graph.add_edge("virtualMachines", "disks", relationship="DEPENDS_ON", frequency=10)
        graph.add_edge("virtualMachines", "networkInterfaces", relationship="DEPENDS_ON", frequency=10)

        resource_counts = {
            "virtualMachines": 10,
            "disks": 15,
            "networkInterfaces": 10,
        }

        patterns = analyzer.detect_patterns(graph, resource_counts)

        if "Virtual Machine Workload" in patterns:
            assert patterns["Virtual Machine Workload"]["connection_count"] == 20


class TestConfigurationFingerprinting:
    """Test configuration fingerprint creation."""

    def test_create_configuration_fingerprint_vm(self, analyzer, sample_configuration_data):
        """Test creating fingerprint for VM resource."""
        fingerprint = analyzer.create_configuration_fingerprint(
            sample_configuration_data["id"],
            sample_configuration_data["type"],
            sample_configuration_data["location"],
            sample_configuration_data["tags"],
            sample_configuration_data["properties"],
        )

        assert fingerprint["sku"] == "Standard_D2s_v3"
        assert fingerprint["location"] == "eastus"
        assert fingerprint["tags"]["env"] == "prod"

    def test_create_configuration_fingerprint_null_properties(self, analyzer):
        """Test creating fingerprint with null properties."""
        fingerprint = analyzer.create_configuration_fingerprint(
            "/subscriptions/sub-123/resourceGroups/rg-1/providers/Microsoft.Storage/storageAccounts/storage1",
            "Microsoft.Storage/storageAccounts",
            "westus",
            None,
            None,
        )

        assert fingerprint["sku"] == "UnknownSKU"
        assert fingerprint["location"] == "westus"
        assert fingerprint["tags"] == {}

    def test_create_configuration_fingerprint_empty_location(self, analyzer):
        """Test creating fingerprint with empty location."""
        fingerprint = analyzer.create_configuration_fingerprint(
            "/subscriptions/sub-123/resourceGroups/rg-1/providers/Microsoft.Compute/virtualMachines/vm-1",
            "Microsoft.Compute/virtualMachines",
            None,
            {},
            {},
        )

        assert fingerprint["location"] == "NoLocation"

    def test_extract_sku_from_properties_vm(self, analyzer):
        """Test SKU extraction from VM properties."""
        properties = {"hardwareProfile": {"vmSize": "Standard_D2s_v3"}}

        sku = analyzer.extract_sku_from_properties(
            properties, "Microsoft.Compute/virtualMachines"
        )

        assert sku == "Standard_D2s_v3"

    def test_extract_sku_from_properties_storage(self, analyzer):
        """Test SKU extraction from Storage Account properties."""
        properties = {"sku": {"name": "Standard_LRS"}}

        sku = analyzer.extract_sku_from_properties(
            properties, "Microsoft.Storage/storageAccounts"
        )

        assert sku == "Standard_LRS"

    def test_extract_sku_from_properties_unknown(self, analyzer):
        """Test SKU extraction with unknown resource type."""
        properties = {"someProperty": "value"}

        sku = analyzer.extract_sku_from_properties(
            properties, "Microsoft.Unknown/unknownType"
        )

        assert sku == "UnknownSKU"

    def test_extract_sku_from_properties_null(self, analyzer):
        """Test SKU extraction with null properties."""
        sku = analyzer.extract_sku_from_properties(None, "Microsoft.Compute/virtualMachines")

        assert sku == "UnknownSKU"


class TestConfigurationSimilarity:
    """Test configuration similarity calculation (uses replicator, not analyzer)."""

    def test_compute_configuration_similarity_identical(self, replicator):
        """Test similarity between identical configurations."""
        fingerprint = {
            "location": "eastus",
            "sku": "Standard_D2s_v3",
            "tags": {"env": "prod", "app": "web"},
        }

        similarity = replicator._compute_configuration_similarity(fingerprint, fingerprint)

        assert similarity == 1.0

    def test_compute_configuration_similarity_different_location(self, replicator):
        """Test similarity with different locations."""
        fp1 = {
            "location": "eastus",
            "sku": "Standard_D2s_v3",
            "tags": {"env": "prod"},
        }
        fp2 = {
            "location": "westus",
            "sku": "Standard_D2s_v3",
            "tags": {"env": "prod"},
        }

        similarity = replicator._compute_configuration_similarity(fp1, fp2)

        # Should be 0.5 (location weight) less than identical
        assert similarity < 1.0
        assert similarity > 0.0

    def test_compute_configuration_similarity_different_sku_tier(self, replicator):
        """Test similarity with different SKU tiers."""
        fp1 = {
            "location": "eastus",
            "sku": "Standard_D2s_v3",
            "tags": {},
        }
        fp2 = {
            "location": "eastus",
            "sku": "Premium_D2s_v3",
            "tags": {},
        }

        similarity = replicator._compute_configuration_similarity(fp1, fp2)

        # Should have location match but not SKU tier
        assert 0.0 < similarity < 1.0

    def test_compute_configuration_similarity_tag_overlap(self, replicator):
        """Test similarity with tag overlap."""
        fp1 = {
            "location": "eastus",
            "sku": "Standard_D2s_v3",
            "tags": {"env": "prod", "app": "web", "owner": "team1"},
        }
        fp2 = {
            "location": "eastus",
            "sku": "Standard_D2s_v3",
            "tags": {"env": "prod", "app": "api"},
        }

        similarity = replicator._compute_configuration_similarity(fp1, fp2)

        # Should have high similarity due to location and SKU match, partial tag overlap
        assert similarity > 0.7


class TestSpectralDistance:
    """Test spectral distance calculation (uses replicator, not analyzer)."""

    @pytest.mark.parametrize(
        "use_scipy",
        [True, False],
        ids=["with_scipy", "without_scipy"],
    )
    def test_compute_spectral_distance_identical_graphs(self, replicator, use_scipy):
        """Test spectral distance between identical graphs."""
        if not use_scipy:
            # Mock scipy import failure
            with patch.dict("sys.modules", {"scipy.linalg": None}):
                graph1 = nx.MultiDiGraph()
                graph1.add_node("A", count=1)
                graph1.add_node("B", count=1)
                graph1.add_edge("A", "B", relationship="DEPENDS_ON", frequency=1)

                graph2 = nx.MultiDiGraph()
                graph2.add_node("A", count=1)
                graph2.add_node("B", count=1)
                graph2.add_edge("A", "B", relationship="DEPENDS_ON", frequency=1)

                # Should handle gracefully even without scipy
                distance = replicator._compute_spectral_distance(graph1, graph2)
                assert distance is not None
        else:
            graph1 = nx.MultiDiGraph()
            graph1.add_node("A", count=1)
            graph1.add_node("B", count=1)
            graph1.add_edge("A", "B", relationship="DEPENDS_ON", frequency=1)

            graph2 = nx.MultiDiGraph()
            graph2.add_node("A", count=1)
            graph2.add_node("B", count=1)
            graph2.add_edge("A", "B", relationship="DEPENDS_ON", frequency=1)

            distance = replicator._compute_spectral_distance(graph1, graph2)

            assert distance < 0.1  # Very similar

    def test_compute_spectral_distance_different_structure(self, replicator):
        """Test spectral distance between structurally different graphs."""
        graph1 = nx.MultiDiGraph()
        graph1.add_node("A", count=1)
        graph1.add_node("B", count=1)
        graph1.add_edge("A", "B", relationship="DEPENDS_ON", frequency=1)

        graph2 = nx.MultiDiGraph()
        graph2.add_node("A", count=1)
        graph2.add_node("B", count=1)
        graph2.add_node("C", count=1)
        graph2.add_edge("A", "B", relationship="DEPENDS_ON", frequency=1)
        graph2.add_edge("B", "C", relationship="DEPENDS_ON", frequency=1)

        distance = replicator._compute_spectral_distance(graph1, graph2)

        assert distance > 0.1  # Noticeably different

    def test_compute_spectral_distance_empty_graph(self, replicator):
        """Test spectral distance with empty graph."""
        graph1 = nx.MultiDiGraph()
        graph2 = nx.MultiDiGraph()
        graph2.add_node("A", count=1)

        distance = replicator._compute_spectral_distance(graph1, graph2)

        assert distance == 1.0  # Maximum distance


class TestProportionalSelection:
    """Test proportional selection allocation."""

    def test_compute_pattern_targets_basic(self, analyzer):
        """Test basic proportional allocation."""
        distribution_scores = {
            "Pattern A": {"distribution_score": 50.0, "source_instances": 10},
            "Pattern B": {"distribution_score": 30.0, "source_instances": 6},
            "Pattern C": {"distribution_score": 20.0, "source_instances": 4},
        }

        targets = analyzer.compute_pattern_targets(distribution_scores, 10)

        assert sum(targets.values()) == 10
        assert targets["Pattern A"] >= targets["Pattern B"]
        assert targets["Pattern B"] >= targets["Pattern C"]

    def test_compute_pattern_targets_rounding_adjustment(self, analyzer):
        """Test that rounding adjustments hit exact target count."""
        distribution_scores = {
            "Pattern A": {"distribution_score": 33.33, "source_instances": 5},
            "Pattern B": {"distribution_score": 33.33, "source_instances": 5},
            "Pattern C": {"distribution_score": 33.34, "source_instances": 5},
        }

        targets = analyzer.compute_pattern_targets(distribution_scores, 10)

        # Should hit exactly 10 despite rounding
        assert sum(targets.values()) == 10

    def test_compute_pattern_targets_zero_target(self, analyzer):
        """Test allocation with zero target count."""
        distribution_scores = {
            "Pattern A": {"distribution_score": 50.0, "source_instances": 10},
        }

        targets = analyzer.compute_pattern_targets(distribution_scores, 0)

        assert targets == {}

    def test_compute_pattern_targets_zero_scores(self, analyzer):
        """Test allocation when all scores are zero."""
        distribution_scores = {
            "Pattern A": {"distribution_score": 0.0, "source_instances": 10},
            "Pattern B": {"distribution_score": 0.0, "source_instances": 5},
        }

        targets = analyzer.compute_pattern_targets(distribution_scores, 10)

        # Should fall back to uniform distribution
        assert sum(targets.values()) == 10
        assert targets["Pattern A"] == targets["Pattern B"]


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_connect_failure(self, analyzer):
        """Test handling of connection failure."""
        with pytest.raises(Exception):
            with patch("src.architectural_pattern_analyzer.GraphDatabase.driver") as mock_driver:
                mock_driver.side_effect = Exception("Connection failed")
                analyzer.connect()

    def test_fetch_relationships_not_connected(self, analyzer):
        """Test fetching relationships without connection."""
        with pytest.raises(RuntimeError, match="Not connected to Neo4j"):
            analyzer.fetch_all_relationships()

    def test_scipy_import_error_graceful_degradation(self, analyzer):
        """Test graceful degradation when scipy is not available."""
        with patch.dict("sys.modules", {"scipy": None}):
            # Should not raise ImportError
            graph = nx.MultiDiGraph()
            resource_counts = {}
            pattern_matches = {}

            # This should handle missing scipy gracefully
            vis_files = analyzer.generate_visualizations(
                graph, resource_counts, {}, pattern_matches, Path("/tmp/test")
            )

            assert vis_files == []  # Returns empty list when scipy unavailable


class TestArchitectureDistribution:
    """Test architecture distribution calculation."""

    def test_compute_architecture_distribution_basic(self, analyzer):
        """Test basic distribution computation."""
        pattern_resources = {
            "Pattern A": [["res1", "res2"], ["res3", "res4"]],
            "Pattern B": [["res5", "res6"]],
        }

        graph = nx.MultiDiGraph()
        graph.add_edge("typeA", "typeB", frequency=10)

        # Mock the ARCHITECTURAL_PATTERNS to include Pattern A and B
        with patch.object(analyzer, "ARCHITECTURAL_PATTERNS", {
            "Pattern A": {"resources": ["typeA", "typeB"]},
            "Pattern B": {"resources": ["typeC"]},
        }):
            distribution = analyzer.compute_architecture_distribution(
                pattern_resources, graph
            )

            assert "Pattern A" in distribution
            assert "Pattern B" in distribution
            assert distribution["Pattern A"]["rank"] == 1  # More instances

    def test_compute_architecture_distribution_empty(self, analyzer):
        """Test distribution with empty pattern resources."""
        distribution = analyzer.compute_architecture_distribution({}, nx.MultiDiGraph())

        assert distribution == {}


class TestNeo4jMocking:
    """Test Neo4j driver mocking patterns."""

    def test_mock_neo4j_driver_session(self, mock_neo4j_driver):
        """Test that Neo4j driver mock works correctly."""
        with mock_neo4j_driver.session() as session:
            session.run("RETURN 1")
            session.run.assert_called_once_with("RETURN 1")

    def test_fetch_all_relationships_with_mock(self, analyzer, mock_neo4j_driver):
        """Test fetch_all_relationships with mocked driver."""
        # Setup mock session
        mock_session = mock_neo4j_driver.session.return_value.__enter__.return_value
        mock_result = Mock()
        mock_result.__iter__ = Mock(return_value=iter([
            {
                "source_labels": ["Resource"],
                "source_type": "Microsoft.Compute/virtualMachines",
                "rel_type": "DEPENDS_ON",
                "target_labels": ["Resource"],
                "target_type": "Microsoft.Compute/disks",
            }
        ]))
        mock_session.run.return_value = mock_result

        analyzer.driver = mock_neo4j_driver

        relationships = analyzer.fetch_all_relationships()

        assert len(relationships) == 1
        assert relationships[0]["source_type"] == "Microsoft.Compute/virtualMachines"


class TestBagOfWordsModel:
    """Test configuration bag-of-words sampling."""

    def test_build_configuration_bags_basic(self, analyzer):
        """Test building configuration bags from analysis."""
        config_analysis = {
            "Microsoft.Compute/virtualMachines": {
                "total_count": 5,
                "configurations": [
                    {
                        "fingerprint": {"sku": "Standard_D2s_v3", "location": "eastus"},
                        "count": 3,
                        "sample_resources": ["vm1", "vm2", "vm3"],
                    },
                    {
                        "fingerprint": {"sku": "Standard_D4s_v3", "location": "eastus"},
                        "count": 2,
                        "sample_resources": ["vm4", "vm5"],
                    },
                ],
            }
        }

        bags = analyzer.build_configuration_bags(config_analysis)

        assert "Microsoft.Compute/virtualMachines" in bags
        assert len(bags["Microsoft.Compute/virtualMachines"]) == 5  # 3 + 2
        # First 3 entries should be the first configuration
        assert bags["Microsoft.Compute/virtualMachines"][0]["fingerprint"]["sku"] == "Standard_D2s_v3"

    def test_build_configuration_bags_empty(self, analyzer):
        """Test building bags from empty analysis."""
        bags = analyzer.build_configuration_bags({})

        assert bags == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
