"""
Spectral Distance Calculator for Architecture-Based Replication.

This module handles spectral distance computations using graph Laplacian
eigenvalues to measure structural similarity between graphs.
"""

import logging
from typing import Optional

import networkx as nx
import numpy as np

logger = logging.getLogger(__name__)


class SpectralDistanceCalculator:
    """
    Computes spectral distance between graphs using Laplacian eigenvalues.
    
    Spectral distance measures structural similarity by comparing the
    eigenvalue spectra of graph Laplacians.
    """
    
    @staticmethod
    def compute_distance(graph1: nx.DiGraph, graph2: nx.DiGraph) -> float:
        """
        Compute normalized spectral distance using Laplacian eigenvalues.
        
        Args:
            graph1: First graph
            graph2: Second graph
            
        Returns:
            Normalized spectral distance (0.0 = identical, 1.0 = maximally different)
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
        spectral_distance: float,
        node_coverage_penalty: float,
        node_coverage_weight: Optional[float] = None,
    ) -> float:
        """
        Compute weighted score combining spectral distance and node coverage.
        
        Args:
            spectral_distance: Spectral distance between graphs
            node_coverage_penalty: Penalty for missing nodes
            node_coverage_weight: Weight for node coverage component (0.0-1.0)
                                 If None, defaults to 0.0 (pure spectral distance)
            
        Returns:
            Combined weighted score (lower is better)
        """
        if node_coverage_weight is None:
            node_coverage_weight = 0.0
        
        # Weighted average
        # node_coverage_weight = 0.0: score = spectral_distance (original behavior)
        # node_coverage_weight = 1.0: score = node_coverage_penalty (pure greedy)
        # node_coverage_weight = 0.5: score = balanced average
        score = (1.0 - node_coverage_weight) * spectral_distance + \
                node_coverage_weight * node_coverage_penalty
        
        return score


__all__ = ["SpectralDistanceCalculator"]
