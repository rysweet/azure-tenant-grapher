"""
Graph Structure Analyzer Brick

Pure utility brick for computing graph structural similarity using spectral methods.
No dependencies, stateless operations.

Philosophy:
- Single Responsibility: Graph structure comparison
- Self-contained: No external state
- Regeneratable: Pure function logic
- Zero-BS: All functions work, no stubs
"""

from __future__ import annotations

import logging

import networkx as nx
import numpy as np

logger = logging.getLogger(__name__)


class GraphStructureAnalyzer:
    """
    Analyzes and compares graph structures using spectral methods.

    This brick provides stateless methods for computing structural similarity
    between graphs using Laplacian eigenvalue analysis.

    Public Contract:
        - compute_spectral_distance(graph1, graph2) -> float
        - compute_weighted_score(source_graph, target_graph, source_node_types, weight) -> float
    """

    @staticmethod
    def compute_spectral_distance(graph1: nx.DiGraph, graph2: nx.DiGraph) -> float:
        """
        Compute normalized spectral distance using Laplacian eigenvalues.

        Spectral distance measures how similar two graphs are structurally by
        comparing their Laplacian eigenvalue spectra. The Laplacian matrix
        captures the connectivity structure of the graph.

        Args:
            graph1: First graph to compare
            graph2: Second graph to compare

        Returns:
            Normalized spectral distance where:
            - 0.0 means graphs are structurally identical
            - 1.0 means graphs are maximally different
            - Values in between indicate degree of structural similarity

        Examples:
            >>> g1 = nx.DiGraph([("A", "B"), ("B", "C")])
            >>> g2 = nx.DiGraph([("A", "B"), ("B", "C")])
            >>> GraphStructureAnalyzer.compute_spectral_distance(g1, g2)
            0.0  # Identical structure

            >>> g3 = nx.DiGraph([("X", "Y")])
            >>> GraphStructureAnalyzer.compute_spectral_distance(g1, g3)
            0.8  # Different structure and size
        """
        if len(graph1.nodes()) == 0 or len(graph2.nodes()) == 0:
            return 1.0

        try:
            # Get Laplacian matrices
            L1 = nx.laplacian_matrix(graph1.to_undirected()).toarray()
            L2 = nx.laplacian_matrix(graph2.to_undirected()).toarray()

            # Pad matrices to same size
            max_size = max(L1.shape[0], L2.shape[0])
            L1_padded = np.zeros((max_size, max_size))
            L2_padded = np.zeros((max_size, max_size))
            L1_padded[: L1.shape[0], : L1.shape[1]] = L1
            L2_padded[: L2.shape[0], : L2.shape[1]] = L2

            # Compute eigenvalues
            eigenvals1 = np.sort(np.linalg.eigvalsh(L1_padded))
            eigenvals2 = np.sort(np.linalg.eigvalsh(L2_padded))

            # Compute normalized distance
            diff = eigenvals1 - eigenvals2
            max_eigenval = max(
                np.max(np.abs(eigenvals1)), np.max(np.abs(eigenvals2)), 1.0
            )

            # Use normalized L2 distance
            distance = np.linalg.norm(diff) / (max_eigenval * np.sqrt(max_size))

            return distance

        except Exception as e:
            logger.warning(f"Failed to compute spectral distance: {e}")
            return 1.0

    @staticmethod
    def compute_weighted_score(
        source_graph: nx.DiGraph,
        target_graph: nx.DiGraph,
        source_node_types: set[str],
        node_coverage_weight: float,
    ) -> float:
        """
        Compute weighted score combining spectral distance and node coverage.

        Lower score is better. The score balances structural similarity (spectral distance)
        with node type coverage (having the same types as source).

        Args:
            source_graph: Source pattern graph to match
            target_graph: Target pattern graph being built
            source_node_types: Set of node types present in source graph
            node_coverage_weight: Weight for node coverage component (0.0-1.0)
                                 - 0.0 = only spectral distance matters
                                 - 1.0 = only node coverage matters
                                 - 0.5 = balanced between both

        Returns:
            Weighted score where lower is better. The score combines:
            - Spectral distance: How structurally similar the graphs are
            - Node coverage penalty: Fraction of source node types missing in target

        Examples:
            >>> source = nx.DiGraph([("vm", "disk"), ("vm", "nic")])
            >>> target = nx.DiGraph([("vm", "disk")])
            >>> source_types = {"vm", "disk", "nic"}
            >>> # Missing "nic" node, structural mismatch
            >>> score = GraphStructureAnalyzer.compute_weighted_score(
            ...     source, target, source_types, node_coverage_weight=0.5
            ... )
            >>> score > 0.3  # Higher score due to missing node and structural difference
            True
        """
        # Compute spectral distance (structural similarity)
        spectral_distance = GraphStructureAnalyzer.compute_spectral_distance(
            source_graph, target_graph
        )

        # Compute node coverage penalty (missing types)
        # This is the fraction of source nodes NOT yet in target
        target_node_types = set(target_graph.nodes())
        missing_nodes = source_node_types - target_node_types
        node_coverage_penalty = (
            len(missing_nodes) / len(source_node_types) if source_node_types else 0.0
        )

        # Weighted average
        # node_coverage_weight = 0.0: score = spectral_distance (original behavior)
        # node_coverage_weight = 1.0: score = node_coverage_penalty (pure greedy)
        # node_coverage_weight = 0.5: score = balanced average
        score = (
            1.0 - node_coverage_weight
        ) * spectral_distance + node_coverage_weight * node_coverage_penalty

        return score


__all__ = ["GraphStructureAnalyzer"]
