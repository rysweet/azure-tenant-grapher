"""Tests for graph sampling library imports and basic functionality."""

import pytest


def test_littleballoffur_import():
    """Test Little Ball of Fur can be imported."""
    from littleballoffur import ForestFireSampler

    assert ForestFireSampler is not None


def test_networkx_import():
    """Test NetworkX can be imported."""
    import networkx as nx

    G = nx.DiGraph()
    assert G is not None


def test_sampling_workflow():
    """Test basic sampling workflow."""
    import networkx as nx
    from littleballoffur import RandomNodeSampler

    # Create small test graph
    G = nx.newman_watts_strogatz_graph(100, 10, 0.05)

    # Sample 10 nodes using RandomNodeSampler (simple and reliable)
    sampler = RandomNodeSampler(number_of_nodes=10)
    sampled = sampler.sample(G)

    assert len(sampled.nodes()) == 10
    assert len(sampled.edges()) <= len(G.edges())
