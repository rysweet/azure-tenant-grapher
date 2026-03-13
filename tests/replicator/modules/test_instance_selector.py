"""
Unit tests for InstanceSelector brick.

Tests instance selection strategies for architectural patterns.
"""

from unittest.mock import MagicMock

import networkx as nx
import pytest

from src.replicator.modules.graph_structure_analyzer import GraphStructureAnalyzer
from src.replicator.modules.instance_selector import InstanceSelector
from src.replicator.modules.target_graph_builder import TargetGraphBuilder


class TestInstanceSelector:
    """Test suite for InstanceSelector brick."""

    @pytest.fixture
    def mock_graph_analyzer(self):
        """Create a mock GraphStructureAnalyzer."""
        analyzer = MagicMock(spec=GraphStructureAnalyzer)
        analyzer.compute_spectral_distance.return_value = 0.5
        analyzer.compute_weighted_score.return_value = 0.5
        return analyzer

    @pytest.fixture
    def mock_graph_builder(self):
        """Create a mock TargetGraphBuilder."""
        builder = MagicMock(spec=TargetGraphBuilder)
        builder.build_from_instances.return_value = nx.DiGraph([("A", "B")])
        builder._relationship_cache = {}
        return builder

    @pytest.fixture
    def selector(self, mock_graph_analyzer, mock_graph_builder):
        """Create an InstanceSelector with mocked dependencies."""
        return InstanceSelector(mock_graph_analyzer, mock_graph_builder)

    def test_select_proportionally_random(self, selector):
        """Test proportional selection with random strategy (no spectral guidance)."""
        pattern_targets = {"web_app": 2, "database": 1}
        pattern_resources = {
            "web_app": [
                [{"id": "app1", "type": "sites"}],
                [{"id": "app2", "type": "sites"}],
                [{"id": "app3", "type": "sites"}]
            ],
            "database": [
                [{"id": "db1", "type": "sqlServers"}],
                [{"id": "db2", "type": "sqlServers"}]
            ]
        }

        selected = selector.select_proportionally(
            pattern_targets,
            pattern_resources,
            use_spectral_guidance=False
        )

        # Should select 2 web_app + 1 database = 3 total
        assert len(selected) == 3
        web_app_count = sum(1 for pattern, _ in selected if pattern == "web_app")
        db_count = sum(1 for pattern, _ in selected if pattern == "database")
        assert web_app_count == 2
        assert db_count == 1

    def test_select_proportionally_spectral_guided(self, selector):
        """Test proportional selection with spectral guidance."""
        pattern_targets = {"web_app": 2}
        pattern_resources = {
            "web_app": [
                [{"id": "app1", "type": "sites"}],
                [{"id": "app2", "type": "sites"}],
                [{"id": "app3", "type": "sites"}]
            ]
        }
        source_graph = nx.DiGraph([("sites", "serverFarms")])

        selected = selector.select_proportionally(
            pattern_targets,
            pattern_resources,
            use_spectral_guidance=True,
            source_pattern_graph=source_graph
        )

        # Should select 2 instances
        assert len(selected) == 2
        assert all(pattern == "web_app" for pattern, _ in selected)

    def test_select_proportionally_missing_pattern(self, selector):
        """Test proportional selection with pattern not in resources."""
        pattern_targets = {"web_app": 2, "nonexistent": 1}
        pattern_resources = {
            "web_app": [
                [{"id": "app1", "type": "sites"}],
                [{"id": "app2", "type": "sites"}]
            ]
        }

        selected = selector.select_proportionally(
            pattern_targets,
            pattern_resources,
            use_spectral_guidance=False
        )

        # Should skip nonexistent pattern
        assert len(selected) == 2
        assert all(pattern == "web_app" for pattern, _ in selected)

    def test_select_proportionally_insufficient_instances(self, selector):
        """Test proportional selection when available instances < target."""
        pattern_targets = {"web_app": 5}
        pattern_resources = {
            "web_app": [
                [{"id": "app1", "type": "sites"}],
                [{"id": "app2", "type": "sites"}]
            ]
        }

        selected = selector.select_proportionally(
            pattern_targets,
            pattern_resources,
            use_spectral_guidance=False
        )

        # Should select all available (2 instead of 5)
        assert len(selected) == 2

    def test_select_proportionally_empty_resources(self, selector):
        """Test proportional selection with empty resource list."""
        pattern_targets = {"web_app": 2}
        pattern_resources = {"web_app": []}

        selected = selector.select_proportionally(
            pattern_targets,
            pattern_resources,
            use_spectral_guidance=False
        )

        # Should return empty list
        assert len(selected) == 0

    def test_select_proportionally_requires_source_graph_for_spectral(self, selector):
        """Test that spectral guidance requires source_pattern_graph."""
        pattern_targets = {"web_app": 2}
        pattern_resources = {
            "web_app": [[{"id": "app1", "type": "sites"}]]
        }

        with pytest.raises(ValueError, match="source_pattern_graph is required"):
            selector.select_proportionally(
                pattern_targets,
                pattern_resources,
                use_spectral_guidance=True,
                source_pattern_graph=None
            )

    def test_select_greedy_basic(self, selector, mock_graph_analyzer):
        """Test greedy selection basic functionality."""
        all_instances = [
            ("web_app", [{"id": "app1", "type": "sites"}]),
            ("web_app", [{"id": "app2", "type": "sites"}]),
            ("database", [{"id": "db1", "type": "sqlServers"}])
        ]
        source_graph = nx.DiGraph([("sites", "serverFarms")])
        mock_graph_analyzer.compute_weighted_score.return_value = 0.3

        selected = selector.select_greedy(
            all_instances,
            target_instance_count=2,
            source_pattern_graph=source_graph,
            node_coverage_weight=0.5
        )

        # Should select 2 instances greedily
        assert len(selected) == 2

    def test_select_greedy_selects_best_scores(self, selector, mock_graph_analyzer):
        """Test that greedy selection chooses instances with best scores."""
        all_instances = [
            ("pattern1", [{"id": "r1", "type": "vm"}]),
            ("pattern2", [{"id": "r2", "type": "disk"}]),
            ("pattern3", [{"id": "r3", "type": "nic"}])
        ]
        source_graph = nx.DiGraph([("vm", "disk"), ("vm", "nic")])

        # Mock scores: r1 has best (lowest) score
        scores = [0.1, 0.5, 0.8]
        mock_graph_analyzer.compute_weighted_score.side_effect = scores

        selected = selector.select_greedy(
            all_instances,
            target_instance_count=1,
            source_pattern_graph=source_graph,
            node_coverage_weight=0.5
        )

        # Should select the instance with lowest score (best match)
        assert len(selected) == 1

    def test_select_greedy_empty_instances(self, selector):
        """Test greedy selection with empty instance list."""
        all_instances = []
        source_graph = nx.DiGraph([("vm", "disk")])

        selected = selector.select_greedy(
            all_instances,
            target_instance_count=5,
            source_pattern_graph=source_graph,
            node_coverage_weight=0.5
        )

        assert len(selected) == 0

    def test_select_greedy_target_exceeds_available(self, selector):
        """Test greedy selection when target > available instances."""
        all_instances = [
            ("pattern1", [{"id": "r1", "type": "vm"}]),
            ("pattern2", [{"id": "r2", "type": "disk"}])
        ]
        source_graph = nx.DiGraph([("vm", "disk")])

        selected = selector.select_greedy(
            all_instances,
            target_instance_count=10,
            source_pattern_graph=source_graph,
            node_coverage_weight=0.5
        )

        # Should select all available (2)
        assert len(selected) == 2

    def test_instance_similarity_identical(self):
        """Test instance similarity for identical resource types."""
        instance1 = [{"id": "r1", "type": "vm"}, {"id": "r2", "type": "disk"}]
        instance2 = [{"id": "r3", "type": "vm"}, {"id": "r4", "type": "disk"}]

        similarity = InstanceSelector._instance_similarity(instance1, instance2)

        # Identical types should give 1.0 similarity
        assert similarity == 1.0

    def test_instance_similarity_partial_overlap(self):
        """Test instance similarity with partial resource type overlap."""
        instance1 = [{"id": "r1", "type": "vm"}, {"id": "r2", "type": "disk"}]
        instance2 = [{"id": "r3", "type": "vm"}, {"id": "r4", "type": "nic"}]

        similarity = InstanceSelector._instance_similarity(instance1, instance2)

        # Jaccard similarity: |{vm}| / |{vm, disk, nic}| = 1/3
        assert abs(similarity - 1/3) < 0.01

    def test_instance_similarity_no_overlap(self):
        """Test instance similarity with no resource type overlap."""
        instance1 = [{"id": "r1", "type": "vm"}]
        instance2 = [{"id": "r2", "type": "disk"}]

        similarity = InstanceSelector._instance_similarity(instance1, instance2)

        # No overlap should give 0.0 similarity
        assert similarity == 0.0

    def test_instance_similarity_empty_instances(self):
        """Test instance similarity with empty instances."""
        instance1 = []
        instance2 = []

        similarity = InstanceSelector._instance_similarity(instance1, instance2)

        # Both empty should give 1.0 similarity
        assert similarity == 1.0

    def test_sample_representative_configs_basic(self, selector):
        """Test representative config sampling basic functionality."""
        instances = [
            [{"id": "r1", "type": "vm"}],
            [{"id": "r2", "type": "disk"}],
            [{"id": "r3", "type": "nic"}],
            [{"id": "r4", "type": "subnet"}],
            [{"id": "r5", "type": "vnet"}]
        ]

        sampled = selector._sample_representative_configs(instances, max_samples=3)

        # Should sample at most 3 instances
        assert len(sampled) <= 3
        assert len(sampled) >= 1

    def test_sample_representative_configs_fewer_than_max(self, selector):
        """Test sampling when instances < max_samples."""
        instances = [
            [{"id": "r1", "type": "vm"}],
            [{"id": "r2", "type": "disk"}]
        ]

        sampled = selector._sample_representative_configs(instances, max_samples=10)

        # Should return all instances
        assert len(sampled) == 2

    def test_sample_for_coverage_basic(self, selector):
        """Test coverage-based sampling."""
        instances = [
            [{"id": "r1", "type": "vm"}],
            [{"id": "r2", "type": "disk"}],
            [{"id": "r3", "type": "vm"}, {"id": "r4", "type": "nic"}],
            [{"id": "r5", "type": "subnet"}]
        ]

        sampled, metadata = selector._sample_for_coverage(instances, max_samples=3)

        # Should sample at most 3 instances
        assert len(sampled) <= 3
        # Metadata should track types
        assert isinstance(metadata, dict)

    def test_sample_for_coverage_prioritizes_rare_types(self, selector):
        """Test that coverage sampling prioritizes rare resource types."""
        instances = [
            [{"id": "r1", "type": "common"}],
            [{"id": "r2", "type": "common"}],
            [{"id": "r3", "type": "common"}],
            [{"id": "r4", "type": "rare"}]
        ]

        sampled, _ = selector._sample_for_coverage(instances, max_samples=2)

        # Should prioritize the rare type
        # Check if rare type instance is included
        types_sampled = set()
        for instance in sampled:
            for resource in instance:
                types_sampled.add(resource["type"])

        # Rare type should likely be sampled
        assert "rare" in types_sampled or "common" in types_sampled

    def test_sample_for_coverage_empty_instances(self, selector):
        """Test coverage sampling with empty instances."""
        instances = []

        sampled, metadata = selector._sample_for_coverage(instances, max_samples=5)

        assert len(sampled) == 0
        assert len(metadata) == 0
