"""Tests for graph sampling library imports and basic functionality."""


def test_networkx_import():
    """Test NetworkX can be imported."""
    import networkx as nx

    G = nx.DiGraph()
    assert G is not None


def test_custom_sampler_imports():
    """Test custom sampler modules can be imported."""
    from src.services.scale_down.sampling.base_sampler import BaseSampler
    from src.services.scale_down.sampling.mhrw_sampler import MHRWSampler

    assert BaseSampler is not None
    assert MHRWSampler is not None
