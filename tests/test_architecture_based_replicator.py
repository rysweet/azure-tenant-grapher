"""
Unit tests for ArchitecturePatternReplicator.

Tests architecture-based tenant replication including pattern selection,
spectral matching, proportional sampling, and configuration coherence.

Fixtures are defined in tests/conftest.py and automatically discovered by pytest.
"""

from __future__ import annotations

import json
from unittest.mock import Mock, patch

import networkx as nx
import pytest

from src.architectural_pattern_analyzer import ArchitecturalPatternAnalyzer


class TestInitialization:
    def sample_pattern_graph(self):
        """Sample pattern graph for testing."""
        graph = nx.MultiDiGraph()
        graph.add_node("virtualMachines", count=10)
        graph.add_node("disks", count=15)
        graph.add_node("networkInterfaces", count=10)
        graph.add_edge(
            "virtualMachines", "disks", relationship="DEPENDS_ON", frequency=10
        )
        graph.add_edge(
            "virtualMachines",
            "networkInterfaces",
            relationship="DEPENDS_ON",
            frequency=10,
        )
        return graph

    @pytest.fixture
    def sample_detected_patterns(self):
        """Sample detected patterns for testing."""
        return {
            "Virtual Machine Workload": {
                "matched_resources": ["virtualMachines", "disks", "networkInterfaces"],
                "missing_resources": ["networkSecurityGroups"],
                "completeness": 75.0,
                "connection_count": 20,
            },
            "Web Application": {
                "matched_resources": ["sites", "serverFarms"],
                "missing_resources": ["storageAccounts"],
                "completeness": 66.7,
                "connection_count": 5,
            },
        }

    @pytest.fixture
    def sample_pattern_resources(self):
        """Sample pattern resources (instances) for testing."""
        return {
            "Virtual Machine Workload": [
                [
                    {"id": "vm1", "type": "virtualMachines", "name": "vm-1"},
                    {"id": "disk1", "type": "disks", "name": "disk-1"},
                    {"id": "nic1", "type": "networkInterfaces", "name": "nic-1"},
                ],
                [
                    {"id": "vm2", "type": "virtualMachines", "name": "vm-2"},
                    {"id": "disk2", "type": "disks", "name": "disk-2"},
                    {"id": "nic2", "type": "networkInterfaces", "name": "nic-2"},
                ],
            ],
            "Web Application": [
                [
                    {"id": "site1", "type": "sites", "name": "site-1"},
                    {"id": "farm1", "type": "serverFarms", "name": "farm-1"},
                ]
            ],
        }


class TestInitialization:
    """Test replicator initialization."""

    def test_init_basic(self, replicator):
        """Test basic initialization."""
        assert replicator.neo4j_uri == "bolt://localhost:7687"
        assert replicator.neo4j_user == "neo4j"
        assert isinstance(replicator.analyzer, ArchitecturalPatternAnalyzer)

    def test_init_creates_analyzer(self, replicator):
        """Test that analyzer is created with correct credentials."""
        assert replicator.analyzer.neo4j_uri == replicator.neo4j_uri
        assert replicator.analyzer.neo4j_user == replicator.neo4j_user


class TestSourceTenantAnalysis:
    """Test source tenant analysis."""

    def test_analyze_source_tenant_basic(self, replicator, sample_pattern_graph):
        """Test basic source tenant analysis."""
        with patch.object(replicator.analyzer, "connect"):
            with patch.object(replicator.analyzer, "close"):
                with patch.object(
                    replicator.analyzer,
                    "fetch_all_relationships",
                    return_value=[
                        {
                            "source_labels": ["Resource"],
                            "source_type": "Microsoft.Compute/virtualMachines",
                            "rel_type": "DEPENDS_ON",
                            "target_labels": ["Resource"],
                            "target_type": "Microsoft.Compute/disks",
                        }
                    ],
                ):
                    with patch.object(
                        replicator,
                        "_fetch_pattern_resources",
                    ):
                        summary = replicator.analyze_source_tenant()

                        assert "total_relationships" in summary
                        assert "detected_patterns" in summary
                        assert replicator.source_pattern_graph is not None

    def test_analyze_source_tenant_configuration_coherence_enabled(self, replicator):
        """Test analysis with configuration coherence enabled."""
        with patch.object(replicator.analyzer, "connect"):
            with patch.object(replicator.analyzer, "close"):
                with patch.object(
                    replicator.analyzer,
                    "fetch_all_relationships",
                    return_value=[],
                ):
                    with patch.object(
                        replicator,
                        "_fetch_pattern_resources",
                    ) as mock_fetch:
                        summary = replicator.analyze_source_tenant(
                            use_configuration_coherence=True, coherence_threshold=0.7
                        )

                        mock_fetch.assert_called_once_with(True, 0.7, True)
                        assert summary["configuration_coherence_enabled"] is True

    def test_analyze_source_tenant_configuration_coherence_disabled(self, replicator):
        """Test analysis with configuration coherence disabled."""
        with patch.object(replicator.analyzer, "connect"):
            with patch.object(replicator.analyzer, "close"):
                with patch.object(
                    replicator.analyzer,
                    "fetch_all_relationships",
                    return_value=[],
                ):
                    with patch.object(
                        replicator,
                        "_fetch_pattern_resources",
                    ) as mock_fetch:
                        summary = replicator.analyze_source_tenant(
                            use_configuration_coherence=False
                        )

                        mock_fetch.assert_called_once_with(False, 0.5, True)
                        assert summary["configuration_coherence_enabled"] is False


class TestConfigurationSimilarity:
    """Test configuration similarity computation."""

    def test_compute_configuration_similarity_identical(self, replicator):
        """Test similarity between identical configurations."""
        fp1 = {
            "location": "eastus",
            "sku": "Standard_D2s_v3",
            "tags": {"env": "prod", "app": "web"},
        }
        fp2 = {
            "location": "eastus",
            "sku": "Standard_D2s_v3",
            "tags": {"env": "prod", "app": "web"},
        }

        similarity = replicator._compute_configuration_similarity(fp1, fp2)

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

        # Location mismatch should reduce similarity by 0.5 (location weight)
        assert similarity < 1.0
        assert similarity >= 0.0

    def test_compute_configuration_similarity_same_sku_tier(self, replicator):
        """Test similarity with same SKU tier."""
        fp1 = {
            "location": "eastus",
            "sku": "Standard_D2s_v3",
            "tags": {},
        }
        fp2 = {
            "location": "eastus",
            "sku": "Standard_D4s_v3",
            "tags": {},
        }

        similarity = replicator._compute_configuration_similarity(fp1, fp2)

        # Same location (0.5) + same tier (0.3) = 0.8
        assert similarity >= 0.7

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

        # Only location match (0.5)
        assert 0.4 <= similarity <= 0.6

    def test_compute_configuration_similarity_tag_overlap(self, replicator):
        """Test similarity with partial tag overlap."""
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

        # Location + SKU + partial tags should give high similarity
        assert similarity > 0.8

    def test_compute_configuration_similarity_empty_tags(self, replicator):
        """Test similarity with empty tags."""
        fp1 = {
            "location": "eastus",
            "sku": "Standard_D2s_v3",
            "tags": {},
        }
        fp2 = {
            "location": "eastus",
            "sku": "Standard_D2s_v3",
            "tags": {},
        }

        similarity = replicator._compute_configuration_similarity(fp1, fp2)

        # Location + SKU = 0.8 (no tag contribution when both empty)
        assert similarity == 0.8

    def test_compute_configuration_similarity_json_string_tags(self, replicator):
        """Test similarity when tags are JSON strings."""
        fp1 = {
            "location": "eastus",
            "sku": "Standard_D2s_v3",
            "tags": '{"env": "prod", "app": "web"}',
        }
        fp2 = {
            "location": "eastus",
            "sku": "Standard_D2s_v3",
            "tags": '{"env": "prod"}',
        }

        similarity = replicator._compute_configuration_similarity(fp1, fp2)

        # Should parse JSON strings and compute tag overlap
        assert similarity > 0.8


class TestSpectralDistance:
    """Test spectral distance computation."""

    def test_compute_spectral_distance_identical(self, replicator):
        """Test spectral distance between identical graphs."""
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
        """Test spectral distance with different graph structures."""
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

    def test_compute_spectral_distance_error_handling(self, replicator):
        """Test error handling in spectral distance computation."""
        with patch("numpy.linalg.eigvalsh", side_effect=Exception("Eigenvalue error")):
            graph1 = nx.MultiDiGraph()
            graph1.add_node("A", count=1)
            graph2 = nx.MultiDiGraph()
            graph2.add_node("A", count=1)

            distance = replicator._compute_spectral_distance(graph1, graph2)

            assert distance == 1.0  # Falls back to max distance on error


class TestWeightedScore:
    """Test weighted score computation."""

    def test_compute_weighted_score_spectral_only(
        self, replicator, sample_pattern_graph
    ):
        """Test weighted score with only spectral distance (weight=0.0)."""
        target_graph = nx.MultiDiGraph()
        target_graph.add_node("virtualMachines", count=5)
        target_graph.add_node("disks", count=5)

        source_nodes = set(sample_pattern_graph.nodes())

        score = replicator._compute_weighted_score(
            sample_pattern_graph, target_graph, source_nodes, node_coverage_weight=0.0
        )

        # Score should be purely spectral distance
        spectral_distance = replicator._compute_spectral_distance(
            sample_pattern_graph, target_graph
        )
        assert abs(score - spectral_distance) < 0.01

    def test_compute_weighted_score_coverage_only(
        self, replicator, sample_pattern_graph
    ):
        """Test weighted score with only node coverage (weight=1.0)."""
        target_graph = nx.MultiDiGraph()
        target_graph.add_node("virtualMachines", count=5)
        target_graph.add_node("disks", count=5)
        # Missing networkInterfaces

        source_nodes = set(sample_pattern_graph.nodes())

        score = replicator._compute_weighted_score(
            sample_pattern_graph, target_graph, source_nodes, node_coverage_weight=1.0
        )

        # Score should be purely coverage penalty
        # Missing 1 of 3 nodes = 1/3 = 0.333...
        expected_penalty = 1.0 / 3.0
        assert abs(score - expected_penalty) < 0.01

    def test_compute_weighted_score_balanced(self, replicator, sample_pattern_graph):
        """Test weighted score with balanced weights (0.5)."""
        target_graph = nx.MultiDiGraph()
        target_graph.add_node("virtualMachines", count=5)
        target_graph.add_node("disks", count=5)

        source_nodes = set(sample_pattern_graph.nodes())

        score = replicator._compute_weighted_score(
            sample_pattern_graph, target_graph, source_nodes, node_coverage_weight=0.5
        )

        # Score should be average of spectral and coverage
        spectral_distance = replicator._compute_spectral_distance(
            sample_pattern_graph, target_graph
        )
        missing_nodes = source_nodes - set(target_graph.nodes())
        coverage_penalty = len(missing_nodes) / len(source_nodes)
        expected_score = 0.5 * spectral_distance + 0.5 * coverage_penalty

        assert abs(score - expected_score) < 0.01


class TestProportionalSelection:
    """Test proportional instance selection."""

    def test_select_instances_proportionally_basic(
        self, replicator, sample_pattern_resources
    ):
        """Test basic proportional selection."""
        replicator.pattern_resources = sample_pattern_resources

        pattern_targets = {
            "Virtual Machine Workload": 1,
            "Web Application": 1,
        }

        selected = replicator._select_instances_proportionally(
            pattern_targets, use_configuration_coherence=False
        )

        assert len(selected) == 2
        assert any(p == "Virtual Machine Workload" for p, _ in selected)
        assert any(p == "Web Application" for p, _ in selected)

    def test_select_instances_proportionally_more_than_available(
        self, replicator, sample_pattern_resources
    ):
        """Test proportional selection requesting more than available."""
        replicator.pattern_resources = sample_pattern_resources

        pattern_targets = {
            "Virtual Machine Workload": 10,  # Only 2 available
            "Web Application": 5,  # Only 1 available
        }

        selected = replicator._select_instances_proportionally(
            pattern_targets, use_configuration_coherence=False
        )

        # Should only get what's available
        assert len(selected) == 3  # 2 VM + 1 Web

    def test_select_instances_proportionally_configuration_coherence(
        self, replicator, sample_pattern_resources
    ):
        """Test proportional selection with configuration coherence."""
        replicator.pattern_resources = sample_pattern_resources

        pattern_targets = {
            "Virtual Machine Workload": 1,
        }

        selected = replicator._select_instances_proportionally(
            pattern_targets, use_configuration_coherence=True
        )

        assert len(selected) == 1
        assert selected[0][0] == "Virtual Machine Workload"

    def test_select_instances_proportionally_missing_pattern(
        self, replicator, sample_pattern_resources
    ):
        """Test proportional selection with pattern not in resources."""
        replicator.pattern_resources = sample_pattern_resources

        pattern_targets = {
            "NonExistent Pattern": 5,
        }

        selected = replicator._select_instances_proportionally(
            pattern_targets, use_configuration_coherence=False
        )

        assert len(selected) == 0

    def test_select_instances_proportionally_empty_pattern(self, replicator):
        """Test proportional selection with empty pattern resources."""
        replicator.pattern_resources = {
            "Empty Pattern": [],
        }

        pattern_targets = {
            "Empty Pattern": 5,
        }

        selected = replicator._select_instances_proportionally(
            pattern_targets, use_configuration_coherence=False
        )

        assert len(selected) == 0


class TestGreedySelection:
    """Test greedy spectral-based instance selection."""

    def test_select_instances_greedy_basic(
        self, replicator, sample_pattern_graph, sample_pattern_resources
    ):
        """Test basic greedy selection."""
        replicator.source_pattern_graph = sample_pattern_graph
        replicator.detected_patterns = {
            "Virtual Machine Workload": {
                "matched_resources": ["virtualMachines", "disks", "networkInterfaces"]
            }
        }

        all_instances = [
            (
                "Virtual Machine Workload",
                sample_pattern_resources["Virtual Machine Workload"][0],
            ),
            (
                "Virtual Machine Workload",
                sample_pattern_resources["Virtual Machine Workload"][1],
            ),
        ]

        with patch.object(
            replicator, "_build_target_pattern_graph_from_instances"
        ) as mock_build:
            mock_build.return_value = sample_pattern_graph

            selected = replicator._select_instances_greedy(
                all_instances, target_instance_count=1, node_coverage_weight=0.0
            )

            assert len(selected) == 1

    def test_select_instances_greedy_coverage_weight(
        self, replicator, sample_pattern_graph
    ):
        """Test greedy selection with different coverage weights."""
        replicator.source_pattern_graph = sample_pattern_graph

        all_instances = [
            ("Pattern A", [{"id": "res1", "type": "virtualMachines", "name": "res1"}]),
            ("Pattern B", [{"id": "res2", "type": "disks", "name": "res2"}]),
        ]

        with patch.object(
            replicator, "_build_target_pattern_graph_from_instances"
        ) as mock_build:
            # Return graphs that add new nodes
            mock_build.side_effect = lambda instances: (
                self._create_graph_with_nodes(
                    {r["type"] for _, inst in instances for r in inst}
                )
            )

            selected = replicator._select_instances_greedy(
                all_instances, target_instance_count=2, node_coverage_weight=1.0
            )

            assert len(selected) == 2

    def _create_graph_with_nodes(self, node_types):
        """Helper to create graph with specific nodes."""
        graph = nx.MultiDiGraph()
        for node_type in node_types:
            graph.add_node(node_type, count=1)
        return graph


class TestTargetGraphBuilding:
    """Test building target pattern graph from instances."""

    def test_build_target_pattern_graph_from_instances_basic(
        self, replicator, sample_pattern_resources, mock_neo4j_driver
    ):
        """Test building target graph from selected instances."""
        selected_instances = [
            (
                "Virtual Machine Workload",
                sample_pattern_resources["Virtual Machine Workload"][0],
            )
        ]

        # Mock Neo4j session
        mock_session = mock_neo4j_driver.session.return_value.__enter__.return_value
        mock_result = Mock()
        mock_result.__iter__ = Mock(
            return_value=iter(
                [
                    {
                        "source_labels": ["Resource"],
                        "source_type": "Microsoft.Compute/virtualMachines",
                        "rel_type": "DEPENDS_ON",
                        "target_labels": ["Resource"],
                        "target_type": "Microsoft.Compute/disks",
                    }
                ]
            )
        )
        mock_session.run.return_value = mock_result

        with patch(
            "src.architecture_based_replicator.GraphDatabase.driver"
        ) as mock_driver:
            mock_driver.return_value = mock_neo4j_driver

            graph = replicator._build_target_pattern_graph_from_instances(
                selected_instances
            )

            assert isinstance(graph, nx.MultiDiGraph)
            # Graph should have nodes from selected instances
            assert graph.number_of_nodes() >= 1

    def test_build_target_pattern_graph_empty_instances(self, replicator):
        """Test building graph from empty instances."""
        with patch("src.architecture_based_replicator.GraphDatabase.driver"):
            graph = replicator._build_target_pattern_graph_from_instances([])

            assert graph.number_of_nodes() == 0
            assert graph.number_of_edges() == 0


class TestOrphanedNodeHandling:
    """Test orphaned node detection and handling."""

    def test_find_orphaned_node_instances_basic(
        self, replicator, sample_pattern_graph, sample_detected_patterns
    ):
        """Test finding instances with orphaned resource types."""
        replicator.source_pattern_graph = sample_pattern_graph
        replicator.detected_patterns = sample_detected_patterns

        # Set source_resource_type_counts with no orphaned types (all types are in patterns)
        # Pattern types from sample_detected_patterns:
        # - Virtual Machine Workload: virtualMachines, disks, networkInterfaces
        # - Web Application: sites, serverFarms
        replicator.source_resource_type_counts = {
            "virtualMachines": 10,
            "disks": 5,
            "networkInterfaces": 8,
            "sites": 4,
            "serverFarms": 2
        }

        # Mock the orphaned handler's response
        with patch.object(replicator.orphaned_handler, 'find_orphaned_node_instances', return_value=[]):
            orphaned_instances = replicator._find_orphaned_node_instances()

            assert isinstance(orphaned_instances, list)
            assert len(orphaned_instances) == 0  # No orphans since all types are in patterns

    def test_find_orphaned_node_instances_with_orphans(
        self,
        replicator,
        sample_pattern_graph,
        sample_detected_patterns,
        mock_neo4j_driver,
    ):
        """Test finding orphaned instances when orphans exist."""
        replicator.source_pattern_graph = sample_pattern_graph
        replicator.detected_patterns = sample_detected_patterns

        # Set source_resource_type_counts with orphaned types (not in patterns)
        # Pattern types: virtualMachines, virtualNetworks, storageAccounts, sites, serverFarms
        # Orphaned type: Microsoft.Insights/actiongroups
        replicator.source_resource_type_counts = {
            "virtualMachines": 10,
            "virtualNetworks": 5,
            "storageAccounts": 3,
            "sites": 4,
            "serverFarms": 2,
            "Microsoft.Insights/actiongroups": 1  # Orphaned - not in any pattern
        }

        # Mock the orphaned handler to return orphaned instances
        mock_orphaned_result = [
            (
                "Orphaned: actiongroups",
                [
                    {
                        "id": "action1",
                        "type": "actiongroups",
                        "name": "action-1",
                    }
                ]
            )
        ]
        
        with patch.object(replicator.orphaned_handler, 'find_orphaned_node_instances', return_value=mock_orphaned_result):
            orphaned_instances = replicator._find_orphaned_node_instances()

            assert isinstance(orphaned_instances, list)
            assert len(orphaned_instances) > 0  # Should find orphaned instances


class TestReplicationPlanGeneration:
    """Test complete replication plan generation."""

    def test_generate_replication_plan_not_analyzed(self, replicator):
        """Test plan generation without analysis."""
        with pytest.raises(RuntimeError, match="Must call analyze_source_tenant"):
            replicator.generate_replication_plan()

    def test_generate_replication_plan_no_patterns(
        self, replicator, sample_pattern_graph
    ):
        """Test plan generation with no detected patterns."""
        replicator.source_pattern_graph = sample_pattern_graph
        replicator.detected_patterns = {}

        with pytest.raises(RuntimeError, match="No patterns detected"):
            replicator.generate_replication_plan()

    def test_generate_replication_plan_architecture_distribution_enabled(
        self,
        replicator,
        sample_pattern_graph,
        sample_detected_patterns,
        sample_pattern_resources,
    ):
        """Test plan generation with architecture distribution enabled."""
        replicator.source_pattern_graph = sample_pattern_graph
        replicator.detected_patterns = sample_detected_patterns
        replicator.pattern_resources = sample_pattern_resources

        # Set source_resource_type_counts (required by new _find_orphaned_node_instances implementation)
        replicator.source_resource_type_counts = {
            "virtualMachines": 10,
            "disks": 5,
            "networkInterfaces": 8,
            "sites": 4,
            "serverFarms": 2
        }

        with patch.object(
            replicator.analyzer, "compute_architecture_distribution"
        ) as mock_dist:
            mock_dist.return_value = {
                "Virtual Machine Workload": {
                    "distribution_score": 60.0,
                    "source_instances": 2,
                    "rank": 1,
                },
                "Web Application": {
                    "distribution_score": 40.0,
                    "source_instances": 1,
                    "rank": 2,
                },
            }

            with patch.object(
                replicator.analyzer, "compute_pattern_targets"
            ) as mock_targets:
                mock_targets.return_value = {
                    "Virtual Machine Workload": 2,
                    "Web Application": 1,
                }

                with patch.object(
                    replicator, "_select_instances_proportionally"
                ) as mock_select:
                    mock_select.return_value = [
                        (
                            "Virtual Machine Workload",
                            sample_pattern_resources["Virtual Machine Workload"][0],
                        )
                    ]

                    with patch.object(
                        replicator, "_build_target_pattern_graph_from_instances"
                    ) as mock_build:
                        mock_build.return_value = sample_pattern_graph

                        with patch.object(
                            replicator.analyzer, "validate_proportional_sampling"
                        ) as mock_validate:
                            mock_validate.return_value = {
                                "target_distribution_match": 0.95,
                                "interpretation": "Close match",
                            }

                            # Mock _find_orphaned_node_instances since default is now include_orphaned_node_patterns=True
                            with patch.object(
                                replicator, "_find_orphaned_node_instances"
                            ) as mock_orphaned:
                                mock_orphaned.return_value = []

                                selected, history, metadata = (
                                    replicator.generate_replication_plan(
                                        target_instance_count=3,
                                        use_architecture_distribution=True,
                                    )
                                )

                                assert isinstance(selected, list)
                                assert isinstance(history, list)
                                assert metadata is not None
                                assert metadata["selection_mode"] in [
                                    "proportional",
                                    "proportional_spectral",
                                ]

    def test_generate_replication_plan_greedy_fallback(
        self,
        replicator,
        sample_pattern_graph,
        sample_detected_patterns,
        sample_pattern_resources,
    ):
        """Test plan generation with greedy fallback mode."""
        replicator.source_pattern_graph = sample_pattern_graph
        replicator.detected_patterns = sample_detected_patterns
        replicator.pattern_resources = sample_pattern_resources

        # Set source_resource_type_counts (required by new _find_orphaned_node_instances implementation)
        replicator.source_resource_type_counts = {
            "virtualMachines": 10,
            "disks": 5,
            "networkInterfaces": 8,
            "sites": 4,
            "serverFarms": 2
        }

        # Mock _find_orphaned_node_instances since default is now include_orphaned_node_patterns=True
        with patch.object(replicator, "_find_orphaned_node_instances") as mock_orphaned:
            mock_orphaned.return_value = []

            with patch.object(replicator, "_select_instances_greedy") as mock_greedy:
                mock_greedy.return_value = [
                    (
                        "Virtual Machine Workload",
                        sample_pattern_resources["Virtual Machine Workload"][0],
                    )
                ]

                with patch.object(
                    replicator, "_build_target_pattern_graph_from_instances"
                ) as mock_build:
                    mock_build.return_value = sample_pattern_graph

                    selected, history, metadata = replicator.generate_replication_plan(
                        target_instance_count=1,
                        use_architecture_distribution=False,
                        node_coverage_weight=0.5,
                    )

                    assert isinstance(selected, list)
                    assert metadata["selection_mode"] == "greedy_spectral"
                    mock_greedy.assert_called_once()


class TestConfigurationBasedPlan:
    """Test configuration-based replication plan."""

    def test_generate_configuration_based_plan_basic(self, replicator):
        """Test basic configuration-based plan generation."""
        config_analysis = {
            "Microsoft.Compute/virtualMachines": {
                "total_count": 10,
                "configurations": [
                    {
                        "fingerprint": {"sku": "Standard_D2s_v3", "location": "eastus"},
                        "count": 6,
                        "sample_resources": ["vm1", "vm2", "vm3"],
                    },
                    {
                        "fingerprint": {"sku": "Standard_D4s_v3", "location": "eastus"},
                        "count": 4,
                        "sample_resources": ["vm4", "vm5"],
                    },
                ],
            }
        }

        with patch.object(
            replicator.analyzer, "analyze_configuration_distributions"
        ) as mock_analyze:
            mock_analyze.return_value = config_analysis

            with patch.object(
                replicator.analyzer, "build_configuration_bags"
            ) as mock_bags:
                mock_bags.return_value = {
                    "Microsoft.Compute/virtualMachines": [
                        {
                            "fingerprint": {"sku": "Standard_D2s_v3"},
                            "sample_resources": ["vm1"],
                        }
                    ]
                    * 10
                }

                with patch.object(
                    replicator, "_compute_distribution_similarity"
                ) as mock_similarity:
                    mock_similarity.return_value = {}

                    selected, mapping = replicator.generate_configuration_based_plan(
                        target_resource_counts={"Microsoft.Compute/virtualMachines": 5},
                        seed=42,
                    )

                    assert "Microsoft.Compute/virtualMachines" in selected
                    assert len(selected["Microsoft.Compute/virtualMachines"]) == 5
                    assert "metadata" in mapping
                    assert "mappings" in mapping


class TestDistributionSimilarity:
    """Test distribution similarity computation."""

    @pytest.mark.parametrize(
        "scipy_available",
        [True, False],
        ids=["with_scipy", "without_scipy"],
    )
    def test_compute_distribution_similarity_basic(self, replicator, scipy_available):
        """Test basic distribution similarity computation."""
        source_analysis = {
            "Microsoft.Compute/virtualMachines": {
                "configurations": [
                    {
                        "fingerprint": {"sku": "Standard_D2s_v3", "location": "eastus"},
                        "count": 6,
                    },
                    {
                        "fingerprint": {"sku": "Standard_D4s_v3", "location": "eastus"},
                        "count": 4,
                    },
                ]
            }
        }

        target_distributions = {
            "Microsoft.Compute/virtualMachines": {
                json.dumps(
                    {"sku": "Standard_D2s_v3", "location": "eastus"}, sort_keys=True
                ): 3,
                json.dumps(
                    {"sku": "Standard_D4s_v3", "location": "eastus"}, sort_keys=True
                ): 2,
            }
        }

        target_counts = {"Microsoft.Compute/virtualMachines": 5}

        if not scipy_available:
            # scipy is required for this method, so skip test if we want to test without it
            # The method will raise ImportError if scipy is not available
            pytest.skip("Cannot test without scipy as method requires it")
        else:
            result = replicator._compute_distribution_similarity(
                source_analysis, target_distributions, target_counts
            )

            assert "Microsoft.Compute/virtualMachines" in result
            assert (
                "distribution_similarity" in result["Microsoft.Compute/virtualMachines"]
            )


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_fetch_pattern_resources_no_patterns(self, replicator):
        """Test fetching resources with no detected patterns."""
        replicator.detected_patterns = None

        replicator._fetch_pattern_resources()

        # Should log warning and return without error

    def test_build_target_graph_neo4j_error(self, replicator):
        """Test target graph building with Neo4j error."""
        with patch(
            "src.architecture_based_replicator.GraphDatabase.driver"
        ) as mock_driver:
            mock_driver.side_effect = Exception("Connection failed")

            with pytest.raises(Exception, match="Connection failed"):
                replicator._build_target_pattern_graph_from_instances(
                    [
                        (
                            "Pattern",
                            [{"id": "res1", "type": "virtualMachines", "name": "res1"}],
                        )
                    ]
                )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
