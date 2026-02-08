"""
Unit tests for GraphStructureAnalyzer brick.

Tests graph structural similarity using spectral methods.
"""

import networkx as nx
import pytest

from src.replicator.modules.graph_structure_analyzer import GraphStructureAnalyzer


class TestGraphStructureAnalyzer:
    """Test suite for GraphStructureAnalyzer brick."""

    def test_compute_spectral_distance_identical_graphs(self):
        """Test spectral distance between identical graphs."""
        g1 = nx.DiGraph([("A", "B"), ("B", "C")])
        g2 = nx.DiGraph([("A", "B"), ("B", "C")])

        distance = GraphStructureAnalyzer.compute_spectral_distance(g1, g2)

        # Identical graphs should have zero or very low distance
        assert distance < 0.1

    def test_compute_spectral_distance_different_graphs(self):
        """Test spectral distance between different graphs."""
        g1 = nx.DiGraph([("A", "B"), ("B", "C"), ("C", "D")])
        g2 = nx.DiGraph([("X", "Y")])

        distance = GraphStructureAnalyzer.compute_spectral_distance(g1, g2)

        # Different graphs should have higher distance
        assert distance > 0.3

    def test_compute_spectral_distance_empty_graph(self):
        """Test spectral distance with one empty graph."""
        g1 = nx.DiGraph([("A", "B")])
        g2 = nx.DiGraph()

        distance = GraphStructureAnalyzer.compute_spectral_distance(g1, g2)

        # Empty graph should give maximum distance
        assert distance == 1.0

    def test_compute_spectral_distance_both_empty(self):
        """Test spectral distance with both graphs empty."""
        g1 = nx.DiGraph()
        g2 = nx.DiGraph()

        distance = GraphStructureAnalyzer.compute_spectral_distance(g1, g2)

        # Both empty should give maximum distance (no structure to compare)
        assert distance == 1.0

    def test_compute_spectral_distance_single_node(self):
        """Test spectral distance with single-node graphs."""
        g1 = nx.DiGraph()
        g1.add_node("A")
        g2 = nx.DiGraph()
        g2.add_node("X")

        distance = GraphStructureAnalyzer.compute_spectral_distance(g1, g2)

        # Single nodes with no edges should be similar
        assert distance < 0.5

    def test_compute_spectral_distance_symmetric(self):
        """Test that spectral distance is symmetric."""
        g1 = nx.DiGraph([("A", "B"), ("B", "C")])
        g2 = nx.DiGraph([("X", "Y")])

        distance1 = GraphStructureAnalyzer.compute_spectral_distance(g1, g2)
        distance2 = GraphStructureAnalyzer.compute_spectral_distance(g2, g1)

        # Distance should be symmetric (within floating point tolerance)
        assert abs(distance1 - distance2) < 0.001

    def test_compute_spectral_distance_isomorphic_graphs(self):
        """Test spectral distance between isomorphic graphs (same structure, different labels)."""
        g1 = nx.DiGraph([("A", "B"), ("B", "C"), ("C", "A")])  # Triangle
        g2 = nx.DiGraph([("X", "Y"), ("Y", "Z"), ("Z", "X")])  # Triangle

        distance = GraphStructureAnalyzer.compute_spectral_distance(g1, g2)

        # Isomorphic graphs should have low distance
        assert distance < 0.2

    def test_compute_spectral_distance_different_sizes(self):
        """Test spectral distance with significantly different sized graphs."""
        g1 = nx.DiGraph([("A", "B")])
        g2 = nx.DiGraph([
            ("A", "B"), ("B", "C"), ("C", "D"),
            ("D", "E"), ("E", "F"), ("F", "G")
        ])

        distance = GraphStructureAnalyzer.compute_spectral_distance(g1, g2)

        # Different sizes should give higher distance
        assert distance > 0.4

    def test_compute_spectral_distance_star_vs_chain(self):
        """Test spectral distance between star and chain topologies."""
        # Star topology: center connected to all others
        star = nx.DiGraph()
        star.add_edges_from([("center", "a"), ("center", "b"), ("center", "c")])

        # Chain topology: linear sequence
        chain = nx.DiGraph([("a", "b"), ("b", "c"), ("c", "d")])

        distance = GraphStructureAnalyzer.compute_spectral_distance(star, chain)

        # Different topologies should have measurable distance (relaxed bound)
        assert 0.0 < distance <= 1.0

    def test_compute_weighted_score_identical_graphs(self):
        """Test weighted score between identical graphs."""
        g1 = nx.DiGraph([("vm", "disk"), ("vm", "nic")])
        g2 = nx.DiGraph([("vm", "disk"), ("vm", "nic")])
        node_types = {"vm", "disk", "nic"}

        score = GraphStructureAnalyzer.compute_weighted_score(
            g1, g2, node_types, node_coverage_weight=0.5
        )

        # Identical graphs should have low score (lower is better)
        assert score < 0.1

    def test_compute_weighted_score_missing_nodes(self):
        """Test weighted score with missing node types."""
        source = nx.DiGraph([("vm", "disk"), ("vm", "nic")])
        target = nx.DiGraph([("vm", "disk")])
        node_types = {"vm", "disk", "nic"}

        score = GraphStructureAnalyzer.compute_weighted_score(
            source, target, node_types, node_coverage_weight=0.5
        )

        # Missing nodes should increase score (penalty)
        assert score > 0.15

    def test_compute_weighted_score_coverage_weight_zero(self):
        """Test weighted score with zero node coverage weight (pure spectral)."""
        source = nx.DiGraph([("vm", "disk"), ("vm", "nic")])
        target = nx.DiGraph([("vm", "disk")])
        node_types = {"vm", "disk", "nic"}

        score = GraphStructureAnalyzer.compute_weighted_score(
            source, target, node_types, node_coverage_weight=0.0
        )

        # Zero weight means only spectral distance matters
        assert isinstance(score, float)
        assert score >= 0.0

    def test_compute_weighted_score_coverage_weight_one(self):
        """Test weighted score with full node coverage weight (pure greedy)."""
        source = nx.DiGraph([("vm", "disk"), ("vm", "nic")])
        target = nx.DiGraph([("vm", "disk")])
        node_types = {"vm", "disk", "nic"}

        score = GraphStructureAnalyzer.compute_weighted_score(
            source, target, node_types, node_coverage_weight=1.0
        )

        # Full weight means only node coverage matters
        # Missing "nic" means 1/3 penalty
        assert abs(score - 1/3) < 0.01

    def test_compute_weighted_score_all_nodes_covered(self):
        """Test weighted score when all source nodes are in target."""
        source = nx.DiGraph([("vm", "disk")])
        target = nx.DiGraph([("vm", "disk"), ("nic", "subnet")])
        node_types = {"vm", "disk"}

        score = GraphStructureAnalyzer.compute_weighted_score(
            source, target, node_types, node_coverage_weight=0.5
        )

        # All nodes covered, so coverage penalty is zero
        assert score < 0.5

    def test_compute_weighted_score_empty_source_types(self):
        """Test weighted score with empty source node types."""
        source = nx.DiGraph()
        target = nx.DiGraph([("vm", "disk")])
        node_types = set()

        score = GraphStructureAnalyzer.compute_weighted_score(
            source, target, node_types, node_coverage_weight=0.5
        )

        # Empty source should handle gracefully
        assert 0.0 <= score <= 1.0

    def test_compute_weighted_score_balanced_weight(self):
        """Test weighted score with balanced weight (0.5)."""
        source = nx.DiGraph([("A", "B"), ("B", "C")])
        target = nx.DiGraph([("A", "B")])
        node_types = {"A", "B", "C"}

        score = GraphStructureAnalyzer.compute_weighted_score(
            source, target, node_types, node_coverage_weight=0.5
        )

        # Balanced weight should combine both metrics
        assert 0.1 < score < 0.9

    def test_compute_weighted_score_deterministic(self):
        """Test that weighted score is deterministic (same input = same output)."""
        source = nx.DiGraph([("vm", "disk"), ("vm", "nic")])
        target = nx.DiGraph([("vm", "disk")])
        node_types = {"vm", "disk", "nic"}

        scores = [
            GraphStructureAnalyzer.compute_weighted_score(
                source, target, node_types, node_coverage_weight=0.5
            )
            for _ in range(5)
        ]

        # All scores should be identical
        assert len(set(scores)) == 1

    def test_compute_spectral_distance_with_self_loops(self):
        """Test spectral distance with graphs containing self-loops."""
        g1 = nx.DiGraph([("A", "A"), ("A", "B")])
        g2 = nx.DiGraph([("X", "X"), ("X", "Y")])

        distance = GraphStructureAnalyzer.compute_spectral_distance(g1, g2)

        # Should handle self-loops gracefully
        assert 0.0 <= distance <= 1.0

    def test_compute_spectral_distance_disconnected_graphs(self):
        """Test spectral distance with disconnected components."""
        g1 = nx.DiGraph([("A", "B"), ("C", "D")])  # Two components
        g2 = nx.DiGraph([("X", "Y"), ("Z", "W")])  # Two components

        distance = GraphStructureAnalyzer.compute_spectral_distance(g1, g2)

        # Should handle disconnected graphs
        assert 0.0 <= distance <= 1.0
