"""
Quality Metrics for Graph Sampling

This module provides quality metrics for comparing original and sampled graphs.
Metrics quantify how well a sample preserves structural properties of the
original graph, enabling data-driven sampling decisions.
"""

# type: ignore - Suppress pyright warnings for NetworkX generic types
# pyright: reportMissingTypeArgument=false, reportArgumentType=false

import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, Set

import networkx as nx

logger = logging.getLogger(__name__)


@dataclass
class QualityMetrics:
    """
    Quality metrics for comparing original and sampled graphs.

    These metrics quantify how well a sample preserves the structural
    properties of the original graph, enabling data-driven sampling
    decisions.

    Attributes:
        original_nodes: Number of nodes in original graph
        sampled_nodes: Number of nodes in sampled graph
        original_edges: Number of edges in original graph
        sampled_edges: Number of edges in sampled graph
        sampling_ratio: Ratio of sampled to original nodes
        degree_distribution_similarity: KL divergence of degree distributions
            (0=identical)
        clustering_coefficient_diff: Difference in average clustering coefficient
        connected_components_original: Number of connected components in original
        connected_components_sampled: Number of connected components in sample
        resource_type_preservation: Ratio of resource types preserved
        avg_degree_original: Average degree in original graph
        avg_degree_sampled: Average degree in sampled graph
        computation_time_seconds: Time taken to compute sample
        additional_metrics: Additional domain-specific metrics

    Examples:
        >>> metrics = QualityMetrics(
        ...     original_nodes=10000,
        ...     sampled_nodes=1000,
        ...     original_edges=25000,
        ...     sampled_edges=2500,
        ...     sampling_ratio=0.1,
        ...     degree_distribution_similarity=0.05,
        ...     clustering_coefficient_diff=0.02,
        ...     connected_components_original=1,
        ...     connected_components_sampled=1
        ... )
        >>> print(str(f"Sampling quality: {metrics.sampling_ratio:.1%}"))
        Sampling quality: 10.0%
    """

    original_nodes: int
    sampled_nodes: int
    original_edges: int
    sampled_edges: int
    sampling_ratio: float
    degree_distribution_similarity: float
    clustering_coefficient_diff: float
    connected_components_original: int
    connected_components_sampled: int
    resource_type_preservation: float = 0.0
    avg_degree_original: float = 0.0
    avg_degree_sampled: float = 0.0
    computation_time_seconds: float = 0.0
    additional_metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert metrics to dictionary format.

        Returns:
            Dict[str, Any]: Dictionary representation suitable for JSON serialization

        Example:
            >>> metrics = QualityMetrics(...)
            >>> data = metrics.to_dict()
            >>> print(data["sampling_ratio"])
            0.1
        """
        return {
            "original_nodes": self.original_nodes,
            "sampled_nodes": self.sampled_nodes,
            "original_edges": self.original_edges,
            "sampled_edges": self.sampled_edges,
            "sampling_ratio": self.sampling_ratio,
            "degree_distribution_similarity": self.degree_distribution_similarity,
            "clustering_coefficient_diff": self.clustering_coefficient_diff,
            "connected_components_original": self.connected_components_original,
            "connected_components_sampled": self.connected_components_sampled,
            "resource_type_preservation": self.resource_type_preservation,
            "avg_degree_original": self.avg_degree_original,
            "avg_degree_sampled": self.avg_degree_sampled,
            "computation_time_seconds": self.computation_time_seconds,
            "additional_metrics": self.additional_metrics,
        }

    def __str__(self) -> str:
        """
        Human-readable string representation.

        Returns:
            str: Formatted metrics summary

        Example:
            >>> metrics = QualityMetrics(...)
            >>> print(metrics)
            Quality Metrics:
              Nodes: 1000/10000 (10.0%)
              ...
        """
        return f"""Quality Metrics:
  Nodes: {self.sampled_nodes}/{self.original_nodes} ({self.sampling_ratio:.1%})
  Edges: {self.sampled_edges}/{self.original_edges}
  Degree Distribution Similarity: {self.degree_distribution_similarity:.4f}
  Clustering Coefficient Diff: {self.clustering_coefficient_diff:.4f}
  Connected Components: {self.connected_components_sampled}/{self.connected_components_original}
  Resource Type Preservation: {self.resource_type_preservation:.1%}
  Computation Time: {self.computation_time_seconds:.2f}s"""


class QualityMetricsCalculator:
    """
    Calculate quality metrics comparing original and sampled graphs.

    This calculator provides comprehensive metrics for evaluating
    sampling quality, including structural and domain-specific measures.
    """

    def __init__(self) -> None:
        """Initialize the quality metrics calculator."""
        self.logger = logging.getLogger(__name__)

    def _calculate_kl_divergence(
        self, dist1: Dict[int, int], dist2: Dict[int, int]
    ) -> float:
        """
        Calculate KL divergence between two degree distributions.

        KL divergence measures how one probability distribution differs from
        another. Lower values indicate more similar distributions.

        Args:
            dist1: First degree distribution (degree -> count)
            dist2: Second degree distribution (degree -> count)

        Returns:
            float: KL divergence value (0 = identical, higher = more different)

        Example:
            >>> dist1 = {0: 10, 1: 20, 2: 30}
            >>> dist2 = {0: 12, 1: 18, 2: 30}
            >>> kl_div = calculator._calculate_kl_divergence(dist1, dist2)
            >>> print(str(f"KL divergence: {kl_div:.4f}"))
        """
        # Convert counts to probabilities
        total1 = sum(dist1.values())
        total2 = sum(dist2.values())

        if total1 == 0 or total2 == 0:
            return float("inf")

        prob1 = {k: v / total1 for k, v in dist1.items()}
        prob2 = {k: v / total2 for k, v in dist2.items()}

        # Calculate KL divergence: sum(p1 * log(p1/p2))
        # Add small epsilon to avoid log(0)
        epsilon = 1e-10
        kl_div = 0.0

        all_keys = set(prob1.keys()) | set(prob2.keys())
        for k in all_keys:
            p1 = prob1.get(k, epsilon)
            p2 = prob2.get(k, epsilon)
            kl_div += p1 * (p1 / p2 if p2 > 0 else 0)

        return kl_div

    def calculate_metrics(
        self,
        original_graph: nx.DiGraph,
        sampled_graph: nx.DiGraph,
        node_properties: Dict[str, Dict[str, Any]],
        sampled_node_ids: Set[str],
        computation_time: float,
    ) -> QualityMetrics:
        """
        Calculate quality metrics comparing original and sampled graphs.

        Args:
            original_graph: Full NetworkX graph
            sampled_graph: Sampled NetworkX graph
            node_properties: Properties for all nodes
            sampled_node_ids: Set of sampled node IDs
            computation_time: Time taken for sampling

        Returns:
            QualityMetrics: Comprehensive quality metrics

        Example:
            >>> calculator = QualityMetricsCalculator()
            >>> metrics = calculator.calculate_metrics(
            ...     G_original, G_sampled, props, sampled_ids, 2.5
            ... )
            >>> print(metrics)
        """
        self.logger.debug("Calculating quality metrics...")

        # Basic counts
        original_nodes = original_graph.number_of_nodes()
        sampled_nodes = sampled_graph.number_of_nodes()
        original_edges = original_graph.number_of_edges()
        sampled_edges = sampled_graph.number_of_edges()
        sampling_ratio = sampled_nodes / original_nodes if original_nodes > 0 else 0.0

        # Degree distributions
        original_degrees = dict(original_graph.degree())
        sampled_degrees = dict(sampled_graph.degree())

        # Convert to degree distribution histograms
        original_degree_dist = Counter(original_degrees.values())
        sampled_degree_dist = Counter(sampled_degrees.values())

        # Calculate KL divergence
        degree_similarity = self._calculate_kl_divergence(
            original_degree_dist, sampled_degree_dist
        )

        # Average degrees
        avg_degree_original = (
            sum(original_degrees.values()) / len(original_degrees)
            if original_degrees
            else 0.0
        )
        avg_degree_sampled = (
            sum(sampled_degrees.values()) / len(sampled_degrees)
            if sampled_degrees
            else 0.0
        )

        # Clustering coefficients
        try:
            # Convert to undirected for clustering coefficient
            original_undirected = original_graph.to_undirected()
            sampled_undirected = sampled_graph.to_undirected()

            clustering_original = nx.average_clustering(original_undirected)
            clustering_sampled = nx.average_clustering(sampled_undirected)
            clustering_diff = abs(clustering_original - clustering_sampled)
        except (ValueError, ZeroDivisionError, nx.NetworkXError) as e:
            self.logger.warning(str(f"Failed to calculate clustering coefficient: {e}"))
            clustering_diff = 0.0
        except Exception as e:
            self.logger.exception(
                f"Unexpected error calculating clustering coefficient: {e}"
            )
            raise

        # Connected components
        try:
            # Use weakly connected for directed graphs
            components_original = nx.number_weakly_connected_components(original_graph)
            components_sampled = nx.number_weakly_connected_components(sampled_graph)
        except (ValueError, nx.NetworkXError) as e:
            self.logger.warning(str(f"Failed to calculate connected components: {e}"))
            components_original = 0
            components_sampled = 0
        except Exception as e:
            self.logger.exception(
                f"Unexpected error calculating connected components: {e}"
            )
            raise

        # Resource type preservation
        try:
            original_types = set()
            sampled_types = set()

            for node_id in original_graph.nodes:
                if node_id in node_properties:
                    resource_type = node_properties[node_id].get("type", "Unknown")
                    original_types.add(resource_type)

            for node_id in sampled_node_ids:
                if node_id in node_properties:
                    resource_type = node_properties[node_id].get("type", "Unknown")
                    sampled_types.add(resource_type)

            type_preservation = (
                len(sampled_types) / len(original_types) if original_types else 0.0
            )
        except (ValueError, KeyError, TypeError) as e:
            self.logger.warning(str(f"Failed to calculate type preservation: {e}"))
            type_preservation = 0.0
        except Exception as e:
            self.logger.exception(
                f"Unexpected error calculating type preservation: {e}"
            )
            raise

        metrics = QualityMetrics(
            original_nodes=original_nodes,
            sampled_nodes=sampled_nodes,
            original_edges=original_edges,
            sampled_edges=sampled_edges,
            sampling_ratio=sampling_ratio,
            degree_distribution_similarity=degree_similarity,
            clustering_coefficient_diff=clustering_diff,
            connected_components_original=components_original,
            connected_components_sampled=components_sampled,
            resource_type_preservation=type_preservation,
            avg_degree_original=avg_degree_original,
            avg_degree_sampled=avg_degree_sampled,
            computation_time_seconds=computation_time,
        )

        self.logger.info(str(f"Quality metrics calculated:\n{metrics}"))

        return metrics
