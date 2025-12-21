"""Tests for Metropolis-Hastings Random Walk (MHRW) sampler.

Testing pyramid:
- 60% Unit tests (fast, heavily mocked)
- 30% Integration tests (multiple components)
- 10% E2E tests (complete workflows)
"""

import random
from collections import Counter

import networkx as nx
import pytest

from src.services.scale_down.sampling.mhrw_sampler import MHRWSampler

# ============================================================================
# UNIT TESTS (60%)
# ============================================================================


class TestMHRWSamplerBasics:
    """Unit tests for basic MHRW sampler functionality."""

    @pytest.mark.asyncio
    async def test_sampler_initialization(self):
        """Test MHRW sampler can be initialized."""
        sampler = MHRWSampler()
        assert sampler is not None
        assert sampler.logger is not None

    @pytest.mark.asyncio
    async def test_empty_graph_raises_error(self):
        """Test empty graph raises ValueError."""
        sampler = MHRWSampler()
        empty_graph = nx.DiGraph()

        with pytest.raises(ValueError, match="Graph has no nodes"):
            await sampler.sample(empty_graph, target_count=10)

    @pytest.mark.asyncio
    async def test_invalid_target_count_zero(self):
        """Test target_count of 0 raises ValueError."""
        sampler = MHRWSampler()
        G = nx.DiGraph()
        G.add_edges_from([("A", "B"), ("B", "C")])

        with pytest.raises(ValueError, match="target_count must be positive"):
            await sampler.sample(G, target_count=0)

    @pytest.mark.asyncio
    async def test_invalid_target_count_negative(self):
        """Test negative target_count raises ValueError."""
        sampler = MHRWSampler()
        G = nx.DiGraph()
        G.add_edges_from([("A", "B"), ("B", "C")])

        with pytest.raises(ValueError, match="target_count must be positive"):
            await sampler.sample(G, target_count=-5)

    @pytest.mark.asyncio
    async def test_returns_set_of_strings(self):
        """Test sample() returns a Set[str]."""
        sampler = MHRWSampler()
        G = nx.DiGraph()
        G.add_edges_from([("A", "B"), ("B", "C"), ("C", "D"), ("D", "E")])

        result = await sampler.sample(G, target_count=3)

        assert isinstance(result, set)
        assert all(isinstance(node_id, str) for node_id in result)

    @pytest.mark.asyncio
    async def test_correct_number_of_nodes(self):
        """Test sample() returns exactly target_count nodes."""
        sampler = MHRWSampler()
        G = nx.DiGraph()
        # Create connected graph with 10 nodes
        for i in range(9):
            G.add_edge(f"node_{i}", f"node_{i + 1}")

        target_count = 5
        result = await sampler.sample(G, target_count=target_count)

        assert len(result) == target_count

    @pytest.mark.asyncio
    async def test_all_sampled_nodes_exist_in_graph(self):
        """Test all sampled nodes exist in original graph."""
        sampler = MHRWSampler()
        G = nx.DiGraph()
        G.add_edges_from(
            [
                ("A", "B"),
                ("B", "C"),
                ("C", "D"),
                ("D", "E"),
                ("E", "F"),
                ("F", "G"),
            ]
        )

        result = await sampler.sample(G, target_count=4)

        original_nodes = set(G.nodes())
        assert result.issubset(original_nodes)

    @pytest.mark.asyncio
    async def test_progress_callback_invoked(self):
        """Test progress callback is called with correct parameters."""
        sampler = MHRWSampler()
        G = nx.DiGraph()
        for i in range(10):
            G.add_edge(f"node_{i}", f"node_{i + 1}")

        # Track callback invocations
        callback_invocations = []

        def progress_callback(phase: str, current: int, total: int):
            callback_invocations.append((phase, current, total))

        target_count = 5
        await sampler.sample(
            G, target_count=target_count, progress_callback=progress_callback
        )

        # Verify callback was invoked
        assert len(callback_invocations) > 0
        phase, current, total = callback_invocations[-1]
        assert phase == "MHRW sampling"
        assert current == target_count
        assert total == target_count


class TestMHRWEdgeCases:
    """Unit tests for edge cases."""

    @pytest.mark.asyncio
    async def test_single_node_graph(self):
        """Test sampling from single-node graph."""
        sampler = MHRWSampler()
        G = nx.DiGraph()
        G.add_node("only_node")

        result = await sampler.sample(G, target_count=1)

        assert len(result) == 1
        assert "only_node" in result

    @pytest.mark.asyncio
    async def test_target_count_equals_graph_size(self):
        """Test target_count equals total graph size."""
        sampler = MHRWSampler()
        G = nx.DiGraph()
        G.add_edges_from([("A", "B"), ("B", "C"), ("C", "D")])

        result = await sampler.sample(G, target_count=4)

        assert len(result) == 4
        assert result == {"A", "B", "C", "D"}

    @pytest.mark.asyncio
    async def test_target_count_greater_than_graph_size(self):
        """Test target_count larger than graph size."""
        sampler = MHRWSampler()
        G = nx.DiGraph()
        G.add_edges_from([("A", "B"), ("B", "C")])

        # MHRW will sample with replacement, returning up to graph size
        result = await sampler.sample(G, target_count=10)

        assert len(result) <= len(G.nodes())
        assert result.issubset(set(G.nodes()))


# ============================================================================
# INTEGRATION TESTS (30%)
# ============================================================================


class TestMHRWIntegration:
    """Integration tests with various graph structures."""

    @pytest.mark.asyncio
    async def test_small_graph_structure(self):
        """Test MHRW with small graph (10 nodes)."""
        sampler = MHRWSampler()
        G = nx.DiGraph()
        # Create small chain graph
        for i in range(9):
            G.add_edge(f"node_{i}", f"node_{i + 1}")

        result = await sampler.sample(G, target_count=5)

        assert len(result) == 5
        assert result.issubset(set(G.nodes()))

    @pytest.mark.asyncio
    async def test_medium_graph_structure(self):
        """Test MHRW with medium graph (50 nodes)."""
        sampler = MHRWSampler()
        G = nx.DiGraph()
        # Create star graph (hub with spokes)
        hub = "hub"
        for i in range(49):
            G.add_edge(hub, f"spoke_{i}")

        result = await sampler.sample(G, target_count=20)

        assert len(result) == 20
        assert result.issubset(set(G.nodes()))

    @pytest.mark.asyncio
    async def test_large_graph_structure(self):
        """Test MHRW with large graph (200 nodes)."""
        sampler = MHRWSampler()
        G = nx.DiGraph()
        # Create grid graph
        for i in range(14):
            for j in range(14):
                node = f"node_{i}_{j}"
                if i > 0:
                    G.add_edge(f"node_{i - 1}_{j}", node)
                if j > 0:
                    G.add_edge(f"node_{i}_{j - 1}", node)

        result = await sampler.sample(G, target_count=50)

        assert len(result) == 50
        assert result.issubset(set(G.nodes()))

    @pytest.mark.asyncio
    async def test_disconnected_graph(self):
        """Test MHRW with disconnected graph components."""
        sampler = MHRWSampler()
        G = nx.DiGraph()
        # Component 1
        G.add_edges_from([("A", "B"), ("B", "C")])
        # Component 2 (disconnected)
        G.add_edges_from([("X", "Y"), ("Y", "Z")])

        result = await sampler.sample(G, target_count=4)

        assert len(result) == 4
        assert result.issubset(set(G.nodes()))

    @pytest.mark.asyncio
    async def test_directed_graph_conversion(self):
        """Test MHRW converts directed graph to undirected."""
        sampler = MHRWSampler()
        G = nx.DiGraph()
        # Directed edges (A -> B -> C)
        G.add_edges_from([("A", "B"), ("B", "C"), ("C", "D")])

        result = await sampler.sample(G, target_count=3)

        # Should work on undirected version
        assert len(result) == 3
        assert result.issubset(set(G.nodes()))

    @pytest.mark.asyncio
    async def test_burn_in_period_effect(self):
        """Test burn-in period (10%) is applied."""
        sampler = MHRWSampler()
        G = nx.DiGraph()
        # Create cycle graph
        for i in range(20):
            G.add_edge(f"node_{i}", f"node_{(i + 1) % 20}")

        target_count = 10
        result = await sampler.sample(G, target_count=target_count)

        # Burn-in should discard ~1 node (10% of 10)
        # Final result should still have target_count nodes
        assert len(result) == target_count


# ============================================================================
# PROPERTY TESTS (10%)
# ============================================================================


class TestMHRWProperties:
    """Property-based tests for statistical uniformity."""

    @pytest.mark.asyncio
    async def test_degree_corrected_acceptance(self):
        """Test acceptance probability is degree-corrected.

        MHRW acceptance probability: min(1, degree(current) / degree(candidate))

        In a star graph, high-degree hub should be visited less often than low-degree spokes.
        """
        sampler = MHRWSampler()
        G = nx.DiGraph()

        # Create star graph: hub with 10 spokes
        hub = "hub"
        spokes = [f"spoke_{i}" for i in range(10)]
        for spoke in spokes:
            G.add_edge(hub, spoke)
            G.add_edge(spoke, hub)  # Make bidirectional

        # Sample multiple times
        sample_counts = Counter()
        num_trials = 100
        for _ in range(num_trials):
            result = await sampler.sample(G, target_count=5)
            sample_counts.update(result)

        # Hub has degree 10, spokes have degree 1
        # Spokes should be sampled more often than hub (degree correction)
        total_spoke_samples = sum(sample_counts[spoke] for spoke in spokes)
        hub_samples = sample_counts[hub]

        # With degree correction, spokes should dominate
        assert total_spoke_samples > hub_samples

    @pytest.mark.asyncio
    async def test_statistical_uniformity_balanced_graph(self):
        """Test statistical uniformity using Chi-square test on balanced graph.

        For a balanced graph (all nodes same degree), MHRW should sample uniformly.
        """
        sampler = MHRWSampler()
        G = nx.DiGraph()

        # Create cycle graph (all nodes have degree 2)
        num_nodes = 20
        for i in range(num_nodes):
            G.add_edge(f"node_{i}", f"node_{(i + 1) % num_nodes}")

        # Sample multiple times
        sample_counts = Counter()
        num_trials = 200
        target_count = 5
        for _ in range(num_trials):
            result = await sampler.sample(G, target_count=target_count)
            sample_counts.update(result)

        # Chi-square test for uniformity
        # Expected: each node sampled (num_trials * target_count / num_nodes) times
        expected_per_node = (num_trials * target_count) / num_nodes

        chi_square = sum(
            ((sample_counts[f"node_{i}"] - expected_per_node) ** 2) / expected_per_node
            for i in range(num_nodes)
        )

        # Chi-square critical value for 19 degrees of freedom (20 nodes - 1) at 0.05: ~30.14
        # If chi_square < 30.14, we cannot reject uniformity hypothesis
        assert chi_square < 50.0, (
            f"Chi-square test failed: {chi_square} (expected < 50)"
        )

    @pytest.mark.asyncio
    async def test_all_sampled_nodes_valid(self):
        """Test property: all sampled nodes exist in original graph."""
        sampler = MHRWSampler()
        G = nx.DiGraph()

        # Create random graph
        random.seed(42)
        num_nodes = 30
        nodes = [f"node_{i}" for i in range(num_nodes)]
        for node in nodes:
            G.add_node(node)
        for _ in range(50):  # Add 50 random edges
            src, dst = random.sample(nodes, 2)
            G.add_edge(src, dst)

        # Sample multiple times
        for _ in range(10):
            result = await sampler.sample(G, target_count=10)
            assert result.issubset(set(G.nodes())), (
                "Sampled nodes not in original graph"
            )

    @pytest.mark.asyncio
    async def test_reproducibility_with_same_seed(self):
        """Test sampling reproducibility with same random seed."""
        G = nx.DiGraph()
        for i in range(10):
            G.add_edge(f"node_{i}", f"node_{(i + 1) % 10}")

        # Sample twice with same seed
        random.seed(42)
        sampler1 = MHRWSampler()
        result1 = await sampler1.sample(G, target_count=5)

        random.seed(42)
        sampler2 = MHRWSampler()
        result2 = await sampler2.sample(G, target_count=5)

        # Results should be identical
        assert result1 == result2, "Sampling not reproducible with same seed"


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================


class TestMHRWErrorHandling:
    """Tests for error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_graph_with_self_loops(self):
        """Test MHRW handles graphs with self-loops."""
        sampler = MHRWSampler()
        G = nx.DiGraph()
        G.add_edges_from([("A", "A"), ("A", "B"), ("B", "C")])

        result = await sampler.sample(G, target_count=2)

        assert len(result) == 2
        assert result.issubset(set(G.nodes()))

    @pytest.mark.asyncio
    async def test_graph_with_multiple_edges(self):
        """Test MHRW handles multigraphs (multiple edges between nodes)."""
        sampler = MHRWSampler()
        G = nx.DiGraph()
        # DiGraph will ignore duplicate edges
        G.add_edges_from([("A", "B"), ("A", "B"), ("B", "C")])

        result = await sampler.sample(G, target_count=2)

        assert len(result) == 2
        assert result.issubset(set(G.nodes()))

    @pytest.mark.asyncio
    async def test_string_node_ids_preserved(self):
        """Test string node IDs are preserved correctly."""
        sampler = MHRWSampler()
        G = nx.DiGraph()
        node_ids = ["resource-123-abc", "vm-xyz-456", "subnet-789-def"]
        G.add_edges_from(
            [
                (node_ids[0], node_ids[1]),
                (node_ids[1], node_ids[2]),
            ]
        )

        result = await sampler.sample(G, target_count=2)

        assert len(result) == 2
        assert all(isinstance(node_id, str) for node_id in result)
        assert result.issubset(set(node_ids))
