"""
Scale-Down Service for Azure Tenant Grapher

This service provides graph sampling and downscaling capabilities using
state-of-the-art sampling algorithms. It operates ONLY on the abstracted
layer (:Resource nodes) and never touches the Original layer.

Key Features:
- Neo4j to NetworkX conversion with streaming
- Multiple sampling algorithms (Forest Fire, MHRW, Random Walk)
- Pattern-based sampling (resource types, tags, security)
- Motif discovery (3-5 node patterns)
- Quality metrics (degree distribution, clustering, components)
- Multiple export formats (YAML, JSON, Neo4j, IaC)

Architecture:
1. Extract: Stream Neo4j graph to NetworkX (5000 record batches)
2. Sample: Apply sampling algorithm to select subset
3. Export: Write sampled graph to requested format

Performance Target: 10% of 10K nodes in <10 seconds
"""

# type: ignore - Suppress various pyright warnings for NetworkX generic types
# pyright: reportMissingTypeArgument=false, reportArgumentType=false

import json
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import littleballoffur as lbof
import networkx as nx
import yaml
from neo4j.exceptions import Neo4jError

from src.iac.emitters.arm_emitter import ArmEmitter
from src.iac.emitters.bicep_emitter import BicepEmitter
from src.iac.emitters.terraform_emitter import TerraformEmitter
from src.iac.traverser import TenantGraph
from src.services.base_scale_service import BaseScaleService
from src.utils.session_manager import Neo4jSessionManager

logger = logging.getLogger(__name__)


# Whitelist of allowed properties for pattern matching (security: prevent injection)
ALLOWED_PATTERN_PROPERTIES = {
    # Resource properties
    "type",
    "name",
    "location",
    "id",
    "tenant_id",
    "resource_group",
    "sku",
    "kind",
    "provisioning_state",
    # Tag properties (nested)
    "tags.environment",
    "tags.owner",
    "tags.cost_center",
    "tags.project",
    "tags.application",
    "tags.department",
    # Network properties
    "subnet_id",
    "vnet_id",
    "nsg_id",
    # Identity properties
    "identity_type",
    "principal_id",
    # Synthetic properties
    "synthetic",
    "scale_operation_id",
}


def _escape_cypher_string(value: str) -> str:
    """
    Escape special characters for Cypher string literals.

    Args:
        value: String value to escape

    Returns:
        Safely escaped string for Cypher
    """
    # Escape backslashes first
    value = value.replace("\\", "\\\\")
    # Escape double quotes
    value = value.replace('"', '\\"')
    # Escape newlines
    value = value.replace("\n", "\\n")
    value = value.replace("\r", "\\r")
    value = value.replace("\t", "\\t")
    return value


def _escape_cypher_identifier(name: str) -> str:
    """
    Escape identifiers (property names, relationship types) for Cypher.

    Args:
        name: Identifier to escape

    Returns:
        Safely escaped identifier for Cypher
    """
    # If identifier contains only alphanumeric and underscore, no escaping needed
    if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name):
        return name

    # Otherwise, use backticks and escape any backticks in the name
    escaped = name.replace("`", "``")
    return f"`{escaped}`"


def _is_safe_cypher_identifier(name: str) -> bool:
    """Check if identifier is safe without escaping."""
    return bool(re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name)) and len(name) <= 100


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
        >>> print(f"Sampling quality: {metrics.sampling_ratio:.1%}")
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


class ScaleDownService(BaseScaleService):
    """
    Scale-down service for sampling Azure tenant graphs.

    This service provides sophisticated graph sampling capabilities using
    state-of-the-art algorithms from the Little Ball of Fur library.
    It operates exclusively on the abstracted graph layer.

    Supported Sampling Algorithms:
    - forest_fire: Preserves local structure, spreads like wildfire
    - mhrw: Metropolis-Hastings Random Walk, unbiased sampling
    - random_walk: Simple random walk sampling
    - pattern: Pattern-based sampling by resource attributes

    Export Formats:
    - yaml: Human-readable node/edge list
    - json: Machine-readable node/edge list
    - neo4j: New tenant in separate Neo4j database
    - terraform/arm/bicep: IaC templates

    Examples:
        >>> session_manager = Neo4jSessionManager(uri, user, password)
        >>> service = ScaleDownService(session_manager)
        >>> node_ids, metrics = await service.sample_graph(
        ...     tenant_id="00000000-0000-0000-0000-000000000000",
        ...     algorithm="forest_fire",
        ...     target_size=0.1,
        ...     output_mode="yaml",
        ...     output_path="/tmp/sample.yaml"
        ... )
        >>> print(f"Sampled {len(node_ids)} nodes")
        >>> print(metrics)
    """

    def __init__(self, session_manager: Neo4jSessionManager) -> None:
        """
        Initialize the scale-down service.

        Args:
            session_manager: Neo4j session manager for database operations
        """
        super().__init__(session_manager)
        self.logger = logging.getLogger(__name__)

    async def neo4j_to_networkx(
        self,
        tenant_id: str,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> Tuple[nx.DiGraph, Dict[str, Dict[str, Any]]]:
        """
        Convert Neo4j graph to NetworkX directed graph.

        Streams data in batches of 5000 records for memory efficiency.
        Queries ONLY the abstracted layer (:Resource nodes without :Original label).
        Excludes SCAN_SOURCE_NODE relationships.

        Args:
            tenant_id: Azure tenant ID to extract
            progress_callback: Optional callback(phase, current, total)

        Returns:
            Tuple[nx.DiGraph, Dict[str, Dict[str, Any]]]:
                - NetworkX directed graph with node IDs
                - Dictionary mapping node IDs to full properties

        Raises:
            ValueError: If tenant not found or has no resources
            Exception: If database query fails

        Example:
            >>> G, node_props = await service.neo4j_to_networkx(
            ...     "00000000-0000-0000-0000-000000000000"
            ... )
            >>> print(f"Loaded {G.number_of_nodes()} nodes")
            >>> print(f"Loaded {G.number_of_edges()} edges")
        """
        self.logger.info(f"Converting Neo4j graph to NetworkX for tenant {tenant_id}")

        # Validate tenant exists
        if not await self.validate_tenant_exists(tenant_id):
            raise ValueError(f"Tenant {tenant_id} not found in database")

        G = nx.DiGraph()
        node_properties: Dict[str, Dict[str, Any]] = {}

        # Query abstracted layer only, exclude SCAN_SOURCE_NODE
        # Stream in batches for memory efficiency
        batch_size = 5000

        # Step 1: Load nodes
        # Note: Resource nodes don't have tenant_id property, validated separately above
        node_query = """
        MATCH (r:Resource)
        WHERE NOT r:Original
        RETURN r.id as id, properties(r) as props
        SKIP $skip
        LIMIT $limit
        """

        nodes_loaded = 0
        skip = 0

        with self.session_manager.session() as session:
            while True:
                result = session.run(
                    node_query,
                    {"tenant_id": tenant_id, "skip": skip, "limit": batch_size},
                )
                batch = list(result)

                if not batch:
                    break

                for record in batch:
                    node_id = record["id"]
                    props = dict(record["props"])

                    # Add node to graph
                    G.add_node(node_id)

                    # Store full properties
                    node_properties[node_id] = props

                    nodes_loaded += 1

                if progress_callback:
                    progress_callback("Loading nodes", nodes_loaded, nodes_loaded)

                skip += batch_size

                # Log progress
                if nodes_loaded % 10000 == 0:
                    self.logger.debug(f"Loaded {nodes_loaded} nodes...")

        self.logger.info(f"Loaded {nodes_loaded} nodes from Neo4j")

        if nodes_loaded == 0:
            raise ValueError(f"No resources found for tenant {tenant_id}")

        # Step 2: Load relationships (exclude SCAN_SOURCE_NODE)
        # Note: Only include Resource->Resource for NetworkX (sampling needs consistent node types)
        # LOCATED_IN, TAGGED_WITH go to non-Resource nodes, exclude from sampling graph
        edge_query = """
        MATCH (r1:Resource)-[rel]->(r2:Resource)
        WHERE NOT r1:Original AND NOT r2:Original
          AND type(rel) <> 'SCAN_SOURCE_NODE'
        RETURN r1.id as source, r2.id as target, type(rel) as rel_type,
               properties(rel) as rel_props
        SKIP $skip
        LIMIT $limit
        """

        edges_loaded = 0
        skip = 0

        with self.session_manager.session() as session:
            while True:
                result = session.run(
                    edge_query,
                    {"tenant_id": tenant_id, "skip": skip, "limit": batch_size},
                )
                batch = list(result)

                if not batch:
                    break

                for record in batch:
                    source = record["source"]
                    target = record["target"]
                    rel_type = record["rel_type"]
                    rel_props = dict(record["rel_props"]) if record["rel_props"] else {}

                    # Only add edge if both nodes exist in our graph
                    if source in G.nodes and target in G.nodes:
                        G.add_edge(
                            source, target, relationship_type=rel_type, **rel_props
                        )
                        edges_loaded += 1

                if progress_callback:
                    progress_callback("Loading edges", edges_loaded, edges_loaded)

                skip += batch_size

                # Log progress
                if edges_loaded % 10000 == 0:
                    self.logger.debug(f"Loaded {edges_loaded} edges...")

        self.logger.info(f"Loaded {edges_loaded} edges from Neo4j")
        self.logger.info(
            f"Conversion complete: {G.number_of_nodes()} nodes, "
            f"{G.number_of_edges()} edges"
        )

        return G, node_properties

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
            >>> kl_div = service._calculate_kl_divergence(dist1, dist2)
            >>> print(f"KL divergence: {kl_div:.4f}")
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

    def _calculate_quality_metrics(
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
            >>> metrics = service._calculate_quality_metrics(
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
            self.logger.warning(f"Failed to calculate clustering coefficient: {e}")
            clustering_diff = 0.0
        except Exception as e:
            self.logger.exception(f"Unexpected error calculating clustering coefficient: {e}")
            raise

        # Connected components
        try:
            # Use weakly connected for directed graphs
            components_original = nx.number_weakly_connected_components(original_graph)
            components_sampled = nx.number_weakly_connected_components(sampled_graph)
        except (ValueError, nx.NetworkXError) as e:
            self.logger.warning(f"Failed to calculate connected components: {e}")
            components_original = 0
            components_sampled = 0
        except Exception as e:
            self.logger.exception(f"Unexpected error calculating connected components: {e}")
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
            self.logger.warning(f"Failed to calculate type preservation: {e}")
            type_preservation = 0.0
        except Exception as e:
            self.logger.exception(f"Unexpected error calculating type preservation: {e}")
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

        self.logger.info(f"Quality metrics calculated:\n{metrics}")

        return metrics

    async def sample_graph(
        self,
        tenant_id: str,
        algorithm: str,
        target_size: float,
        output_mode: str,
        output_path: Optional[str] = None,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        target_layer_id: Optional[str] = None,
        new_layer: Optional[str] = None,
    ) -> Tuple[Set[str], QualityMetrics, int]:
        """
        Sample a tenant graph using specified algorithm.

        This is the main entry point for graph sampling operations.
        It coordinates extraction, sampling, and optional export/deletion.

        Args:
            tenant_id: Azure tenant ID to sample
            algorithm: Sampling algorithm (forest_fire, mhrw, random_walk)
            target_size: Target sample size as fraction (0.0-1.0) or node count (>1)
            output_mode: Mode (delete, export, new-tenant, yaml, json, neo4j, terraform, arm, bicep)
            output_path: Optional output path for export
            progress_callback: Optional callback(phase, current, total)

        Returns:
            Tuple[Set[str], QualityMetrics, int]:
                - Set of sampled node IDs (nodes to KEEP)
                - Quality metrics comparing original and sample
                - Number of nodes deleted (0 if not in delete mode)

        Raises:
            ValueError: If parameters are invalid
            Exception: If sampling or export fails

        Example:
            >>> node_ids, metrics, deleted = await service.sample_graph(
            ...     tenant_id="00000000-0000-0000-0000-000000000000",
            ...     algorithm="forest_fire",
            ...     target_size=0.1,
            ...     output_mode="delete"
            ... )
            >>> print(f"Kept {len(node_ids)} nodes, deleted {deleted} nodes")
        """
        start_time = datetime.now(UTC)

        self.logger.info(
            f"Starting graph sampling for tenant {tenant_id} "
            f"with algorithm={algorithm}, target_size={target_size}"
        )

        # Validate parameters
        valid_algorithms = ["forest_fire", "mhrw", "random_walk", "pattern"]
        if algorithm not in valid_algorithms:
            raise ValueError(
                f"Invalid algorithm: {algorithm}. Must be one of: {valid_algorithms}"
            )

        # BUG FIX #2: Align valid_output_modes with what CLI offers
        # CLI offers: delete, export, new-tenant
        # But 'export' mode requires a format: yaml, json, neo4j, terraform, arm, bicep
        # Keep both sets for compatibility, but validate properly
        valid_output_modes = ["delete", "export", "new-tenant", "yaml", "json", "neo4j", "terraform", "arm", "bicep"]
        if output_mode not in valid_output_modes:
            raise ValueError(
                f"Invalid output_mode: {output_mode}. "
                f"Must be one of: {valid_output_modes}"
            )

        if target_size <= 0:
            raise ValueError(f"target_size must be positive, got {target_size}")

        # Stage 1: Extract - Neo4j to NetworkX
        if progress_callback:
            progress_callback("Extracting graph", 0, 100)

        G, node_properties = await self.neo4j_to_networkx(tenant_id, progress_callback)

        # Calculate target node count
        if target_size < 1.0:
            # Fraction of nodes
            target_node_count = int(G.number_of_nodes() * target_size)
        else:
            # Absolute node count
            target_node_count = int(target_size)

        target_node_count = max(1, target_node_count)  # At least 1 node
        target_node_count = min(
            target_node_count, G.number_of_nodes()
        )  # At most all nodes

        # Calculate sampling ratio for logging (avoid division by zero)
        if G.number_of_nodes() > 0:
            sampling_ratio_pct = f"({target_node_count / G.number_of_nodes():.1%})"
        else:
            sampling_ratio_pct = "(0%)"

        self.logger.info(
            f"Target sample size: {target_node_count} nodes {sampling_ratio_pct}"
        )

        # Stage 2: Sample - Apply algorithm
        if progress_callback:
            progress_callback("Sampling graph", 0, 100)

        sampling_start = datetime.now(UTC)

        if algorithm == "forest_fire":
            sampled_node_ids = await self._sample_forest_fire(
                G, target_node_count, progress_callback
            )
        elif algorithm == "mhrw":
            sampled_node_ids = await self._sample_mhrw(
                G, target_node_count, progress_callback
            )
        elif algorithm == "random_walk":
            sampled_node_ids = await self._sample_random_walk(
                G, target_node_count, progress_callback
            )
        else:
            raise ValueError(f"Algorithm not implemented: {algorithm}")

        sampling_time = (datetime.now(UTC) - sampling_start).total_seconds()

        self.logger.info(
            f"Sampled {len(sampled_node_ids)} nodes in {sampling_time:.2f}s"
        )

        # Create sampled subgraph
        sampled_graph = G.subgraph(sampled_node_ids).copy()

        # Stage 3: Calculate quality metrics
        if progress_callback:
            progress_callback("Calculating metrics", 0, 100)

        metrics = self._calculate_quality_metrics(
            G, sampled_graph, node_properties, sampled_node_ids, sampling_time
        )

        # Stage 4: Handle output mode
        nodes_deleted = 0

        if output_mode == "delete":
            # BUG FIX: Implement deletion logic
            # Delete all nodes NOT in sampled_node_ids (abstracted layer only)
            if progress_callback:
                progress_callback("Deleting non-sampled nodes", 0, 100)

            nodes_deleted = await self._delete_non_sampled_nodes(
                sampled_node_ids,
                progress_callback
            )

            self.logger.info(f"Deleted {nodes_deleted} non-sampled nodes")
        elif output_path:
            # Export mode
            if progress_callback:
                progress_callback("Exporting sample", 0, 100)

            await self.export_sample(
                sampled_node_ids,
                node_properties,
                sampled_graph,
                output_mode,
                output_path,
            )

        total_time = (datetime.now(UTC) - start_time).total_seconds()
        self.logger.info(
            f"Graph sampling completed in {total_time:.2f}s: "
            f"{len(sampled_node_ids)} nodes sampled, {nodes_deleted} nodes deleted"
        )

        return sampled_node_ids, metrics, nodes_deleted

    async def _sample_forest_fire(
        self,
        G: nx.DiGraph,
        target_count: int,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> Set[str]:
        """
        Sample graph using Forest Fire algorithm.

        Forest Fire sampling spreads through the graph like a wildfire,
        preserving local community structure. Good for sampling densely
        connected subgraphs.

        Args:
            G: NetworkX graph to sample
            target_count: Target number of nodes to sample
            progress_callback: Optional progress callback

        Returns:
            Set[str]: Set of sampled node IDs

        Example:
            >>> sampled_ids = await service._sample_forest_fire(G, 1000)
            >>> print(f"Sampled {len(sampled_ids)} nodes")
        """
        self.logger.info(f"Applying Forest Fire sampling (target={target_count})")

        # Forest Fire requires undirected graph
        G_undirected = G.to_undirected()

        # Calculate sampling probability (p parameter)
        # Higher p = larger samples
        sampling_ratio = target_count / G.number_of_nodes()
        p = min(0.7, sampling_ratio * 2)  # Heuristic: scale p with ratio

        try:
            # Custom Forest Fire implementation to handle sparse graphs
            # and avoid littleballoffur library bugs
            import random

            sampled_nodes = set()
            nodes_list = list(G_undirected.nodes())

            if not nodes_list:
                raise ValueError("Graph has no nodes")

            # Start from random seed node
            seed = random.choice(nodes_list)
            queue = [seed]
            sampled_nodes.add(seed)

            # Spread the fire
            while len(sampled_nodes) < target_count and queue:
                current = queue.pop(0)

                # Get neighbors
                neighbors = list(G_undirected.neighbors(current))
                if not neighbors:
                    # If current node has no neighbors, pick a random unvisited node
                    unvisited = [n for n in nodes_list if n not in sampled_nodes]
                    if unvisited and len(sampled_nodes) < target_count:
                        new_seed = random.choice(unvisited)
                        queue.append(new_seed)
                        sampled_nodes.add(new_seed)
                    continue

                # Sample neighbors with probability p
                unvisited_neighbors = [n for n in neighbors if n not in sampled_nodes]
                if unvisited_neighbors:
                    num_to_burn = min(
                        len(unvisited_neighbors),
                        max(1, int(len(unvisited_neighbors) * p)),
                        target_count - len(sampled_nodes)
                    )
                    burned = random.sample(unvisited_neighbors, num_to_burn)
                    for node in burned:
                        sampled_nodes.add(node)
                        queue.append(node)

            # If we didn't reach target (disconnected graph), add random nodes
            if len(sampled_nodes) < target_count:
                remaining = [n for n in nodes_list if n not in sampled_nodes]
                needed = min(target_count - len(sampled_nodes), len(remaining))
                sampled_nodes.update(random.sample(remaining, needed))

            self.logger.info(
                f"Forest Fire sampling completed: {len(sampled_nodes)} nodes"
            )

            return sampled_nodes

        except (ValueError, nx.NetworkXError) as e:
            self.logger.exception(f"Forest Fire sampling failed: {e}")
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error during Forest Fire sampling: {e}")
            raise

    async def _sample_mhrw(
        self,
        G: nx.DiGraph,
        target_count: int,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> Set[str]:
        """
        Sample graph using Metropolis-Hastings Random Walk (MHRW).

        MHRW provides unbiased, uniform sampling across the graph.
        Good for representative samples without structural bias.

        Args:
            G: NetworkX graph to sample
            target_count: Target number of nodes to sample
            progress_callback: Optional progress callback

        Returns:
            Set[str]: Set of sampled node IDs

        Example:
            >>> sampled_ids = await service._sample_mhrw(G, 1000)
            >>> print(f"Sampled {len(sampled_ids)} nodes")
        """
        self.logger.info(
            f"Applying Metropolis-Hastings Random Walk sampling (target={target_count})"
        )

        # MHRW requires undirected graph
        G_undirected = G.to_undirected()

        try:
            # littleballoffur requires integer node IDs
            # Create bidirectional mapping: string <-> integer
            node_to_int = {node: i for i, node in enumerate(G_undirected.nodes())}
            int_to_node = {i: node for node, i in node_to_int.items()}

            # Relabel graph to use integer IDs
            G_int = nx.relabel_nodes(G_undirected, node_to_int)

            # Apply sampler with integer IDs
            sampler = lbof.MetropolisHastingsRandomWalkSampler(
                number_of_nodes=target_count
            )
            sampled_graph = sampler.sample(G_int)

            # Convert integer IDs back to original string IDs
            sampled_node_ids = {int_to_node[node_id] for node_id in sampled_graph.nodes()}

            self.logger.info(f"MHRW sampling completed: {len(sampled_node_ids)} nodes")

            return sampled_node_ids

        except (ValueError, nx.NetworkXError) as e:
            self.logger.exception(f"MHRW sampling failed: {e}")
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error during MHRW sampling: {e}")
            raise

    async def _sample_random_walk(
        self,
        G: nx.DiGraph,
        target_count: int,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> Set[str]:
        """
        Sample graph using simple Random Walk.

        Random walk sampling explores the graph by taking random steps
        from each node. Simpler than MHRW but potentially biased toward
        high-degree nodes.

        Args:
            G: NetworkX graph to sample
            target_count: Target number of nodes to sample
            progress_callback: Optional progress callback

        Returns:
            Set[str]: Set of sampled node IDs

        Example:
            >>> sampled_ids = await service._sample_random_walk(G, 1000)
            >>> print(f"Sampled {len(sampled_ids)} nodes")
        """
        self.logger.info(f"Applying Random Walk sampling (target={target_count})")

        # Random walk requires undirected graph
        G_undirected = G.to_undirected()

        try:
            # Custom Random Walk implementation to handle sparse graphs
            # and avoid littleballoffur library bugs with empty sequences
            import random

            sampled_nodes = set()
            nodes_list = list(G_undirected.nodes())

            if not nodes_list:
                raise ValueError("Graph has no nodes")

            # Start from random seed node
            current = random.choice(nodes_list)
            sampled_nodes.add(current)

            # Perform random walk
            while len(sampled_nodes) < target_count:
                # Get unvisited neighbors
                neighbors = list(G_undirected.neighbors(current))
                unvisited_neighbors = [n for n in neighbors if n not in sampled_nodes]

                if unvisited_neighbors:
                    # Walk to random unvisited neighbor
                    current = random.choice(unvisited_neighbors)
                    sampled_nodes.add(current)
                else:
                    # Stuck - no unvisited neighbors
                    # Jump to random unvisited node
                    unvisited = [n for n in nodes_list if n not in sampled_nodes]
                    if not unvisited:
                        # All nodes visited
                        break
                    current = random.choice(unvisited)
                    sampled_nodes.add(current)

            self.logger.info(
                f"Random Walk sampling completed: {len(sampled_nodes)} nodes"
            )

            return sampled_nodes

        except (ValueError, nx.NetworkXError) as e:
            self.logger.exception(f"Random Walk sampling failed: {e}")
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error during Random Walk sampling: {e}")
            raise

    async def sample_by_pattern(
        self,
        tenant_id: str,
        criteria: Dict[str, Any],
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> Set[str]:
        """
        Sample graph based on pattern matching criteria.

        Pattern-based sampling selects nodes matching specific attributes,
        enabling targeted sampling by resource type, tags, location, etc.

        Args:
            tenant_id: Azure tenant ID to sample
            criteria: Matching criteria dictionary, e.g.:
                {
                    "resource_type": "Microsoft.Compute/virtualMachines",
                    "tags.environment": "production",
                    "location": "eastus"
                }
            progress_callback: Optional progress callback

        Returns:
            Set[str]: Set of matching node IDs

        Raises:
            ValueError: If tenant not found or criteria invalid
            Exception: If query fails

        Example:
            >>> criteria = {
            ...     "resource_type": "Microsoft.Compute/virtualMachines",
            ...     "tags.environment": "production"
            ... }
            >>> node_ids = await service.sample_by_pattern(
            ...     "00000000-0000-0000-0000-000000000000",
            ...     criteria
            ... )
            >>> print(f"Found {len(node_ids)} matching nodes")
        """
        self.logger.info(
            f"Sampling by pattern for tenant {tenant_id[:8]}... "
            f"with {len(criteria)} criteria"
        )

        # Validate tenant exists
        if not await self.validate_tenant_exists(tenant_id):
            raise ValueError(f"Tenant {tenant_id} not found in database")

        if not criteria:
            raise ValueError("Criteria cannot be empty")

        if len(criteria) > 20:
            raise ValueError("Too many criteria (max 20)")

        # Validate all property keys against whitelist
        for key in criteria.keys():
            if key not in ALLOWED_PATTERN_PROPERTIES:
                raise ValueError(
                    f"Invalid pattern property: {key}. "
                    f"Allowed properties: {sorted(ALLOWED_PATTERN_PROPERTIES)}"
                )

        # Build query with property accessor syntax for nested properties
        where_clauses = ["NOT r:Original", "r.tenant_id = $tenant_id"]
        params: Dict[str, Any] = {"tenant_id": tenant_id}

        for key, value in criteria.items():
            param_name = f"param_{key.replace('.', '_')}"

            # Use Cypher property accessor for nested properties
            # Since key is validated against whitelist, this is safe
            if "." in key:
                # For tags.environment, we need r.tags.environment
                parts = key.split(".")
                # Build nested property access safely
                property_ref = f"r.{parts[0]}.{parts[1]}"
            else:
                property_ref = f"r.{key}"

            where_clauses.append(f"{property_ref} = ${param_name}")
            params[param_name] = value

        where_clause = " AND ".join(where_clauses)

        query = f"""
        MATCH (r:Resource)
        WHERE {where_clause}
        RETURN r.id as id
        """

        self.logger.debug(f"Pattern matching with {len(criteria)} validated criteria")
        self.logger.debug(f"Cypher query: {query}")
        self.logger.debug(f"Query parameters: {params}")

        matching_ids: Set[str] = set()

        try:
            with self.session_manager.session() as session:
                result = session.run(query, params)

                for record in result:
                    matching_ids.add(record["id"])

                    if progress_callback and len(matching_ids) % 100 == 0:
                        progress_callback(
                            "Pattern matching", len(matching_ids), len(matching_ids)
                        )

            self.logger.info(
                f"Pattern matching completed: {len(matching_ids)} nodes matched"
            )

            # BUG FIX #3: Add helpful message when no nodes match
            if len(matching_ids) == 0:
                self.logger.warning(
                    f"No resources found matching criteria: {criteria}. "
                    f"Check that resources with these properties exist in tenant {tenant_id}. "
                    f"For resource type matching, verify the 'type' property matches exactly "
                    f"(e.g., 'Microsoft.Network/virtualNetworks')."
                )

            return matching_ids

        except (Neo4jError, ValueError) as e:
            self.logger.exception(f"Pattern matching failed: {e}")
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error during pattern matching: {e}")
            raise

    async def export_sample(
        self,
        node_ids: Set[str],
        node_properties: Dict[str, Dict[str, Any]],
        sampled_graph: nx.DiGraph,
        format: str,
        output_path: str,
    ) -> None:
        """
        Export sampled graph to specified format.

        Supports multiple export formats:
        - yaml: Human-readable YAML with nodes and relationships
        - json: Machine-readable JSON with nodes and relationships
        - neo4j: New tenant in separate Neo4j database
        - terraform/arm/bicep: IaC templates

        Args:
            node_ids: Set of sampled node IDs
            node_properties: Properties for all nodes
            sampled_graph: NetworkX graph of sample
            format: Export format (yaml, json, neo4j, terraform, arm, bicep)
            output_path: Output file or directory path

        Raises:
            ValueError: If format is invalid
            Exception: If export fails

        Example:
            >>> await service.export_sample(
            ...     sampled_ids,
            ...     node_props,
            ...     G_sampled,
            ...     "yaml",
            ...     "/tmp/sample.yaml"
            ... )
        """
        self.logger.info(f"Exporting sample to {format} at {output_path}")

        if format == "yaml":
            await self._export_yaml(
                node_ids, node_properties, sampled_graph, output_path
            )
        elif format == "json":
            await self._export_json(
                node_ids, node_properties, sampled_graph, output_path
            )
        elif format == "neo4j":
            await self._export_neo4j(
                node_ids, node_properties, sampled_graph, output_path
            )
        elif format in ["terraform", "arm", "bicep"]:
            await self._export_iac(
                node_ids, node_properties, sampled_graph, format, output_path
            )
        else:
            raise ValueError(f"Unsupported export format: {format}")

        self.logger.info(f"Export completed: {output_path}")

    async def _export_yaml(
        self,
        node_ids: Set[str],
        node_properties: Dict[str, Dict[str, Any]],
        sampled_graph: nx.DiGraph,
        output_path: str,
    ) -> None:
        """Export sample to YAML format."""
        nodes = []
        for node_id in node_ids:
            if node_id in node_properties:
                nodes.append({"id": node_id, "properties": node_properties[node_id]})

        relationships = []
        for source, target, data in sampled_graph.edges(data=True):
            relationships.append(
                {
                    "source": source,
                    "target": target,
                    "type": data.get("relationship_type", "UNKNOWN"),
                    "properties": {
                        k: v for k, v in data.items() if k != "relationship_type"
                    },
                }
            )

        output_data = {
            "metadata": {
                "format": "yaml",
                "node_count": len(nodes),
                "relationship_count": len(relationships),
                "generated_at": datetime.now(UTC).isoformat(),
            },
            "nodes": nodes,
            "relationships": relationships,
        }

        with open(output_path, "w") as f:
            yaml.dump(output_data, f, default_flow_style=False, sort_keys=False)

        self.logger.info(f"YAML export completed: {output_path}")

    async def _export_json(
        self,
        node_ids: Set[str],
        node_properties: Dict[str, Dict[str, Any]],
        sampled_graph: nx.DiGraph,
        output_path: str,
    ) -> None:
        """Export sample to JSON format."""
        nodes = []
        for node_id in node_ids:
            if node_id in node_properties:
                nodes.append({"id": node_id, "properties": node_properties[node_id]})

        relationships = []
        for source, target, data in sampled_graph.edges(data=True):
            relationships.append(
                {
                    "source": source,
                    "target": target,
                    "type": data.get("relationship_type", "UNKNOWN"),
                    "properties": {
                        k: v for k, v in data.items() if k != "relationship_type"
                    },
                }
            )

        output_data = {
            "metadata": {
                "format": "json",
                "node_count": len(nodes),
                "relationship_count": len(relationships),
                "generated_at": datetime.now(UTC).isoformat(),
            },
            "nodes": nodes,
            "relationships": relationships,
        }

        with open(output_path, "w") as f:
            json.dump(output_data, f, indent=2)

        self.logger.info(f"JSON export completed: {output_path}")

    async def _export_neo4j(
        self,
        node_ids: Set[str],
        node_properties: Dict[str, Dict[str, Any]],
        sampled_graph: nx.DiGraph,
        output_path: str,
    ) -> None:
        """
        Export sample to new Neo4j database as Cypher statements.

        Creates properly escaped Cypher statements for importing into a new database.

        Note: This creates Cypher statements in a file.
        Actual database creation would require separate Neo4j instance.

        Args:
            node_ids: Set of node IDs to export
            node_properties: Properties for all nodes
            sampled_graph: NetworkX graph of sample
            output_path: Output file path

        Raises:
            ValueError: If export fails
        """
        cypher_statements = []

        # Add header with metadata
        cypher_statements.append("// Neo4j Import Cypher Statements")
        cypher_statements.append(f"// Generated: {datetime.now(UTC).isoformat()}")
        cypher_statements.append(f"// Nodes: {len(node_ids)}")
        cypher_statements.append(f"// Relationships: {sampled_graph.number_of_edges()}")
        cypher_statements.append("// WARNING: Review this file before executing")
        cypher_statements.append("")

        # Create nodes with proper escaping
        cypher_statements.append("// Create nodes")

        for node_id in sorted(node_ids):  # Sort for deterministic output
            if node_id not in node_properties:
                continue

            props = node_properties[node_id]

            # Build property map with proper escaping
            prop_strings = []
            for key, value in props.items():
                # Validate and escape property name
                if not _is_safe_cypher_identifier(key):
                    self.logger.warning(f"Skipping property with unsafe name: {key}")
                    continue

                safe_key = _escape_cypher_identifier(key)

                # Handle different value types
                if value is None:
                    # Skip null values
                    continue
                elif isinstance(value, str):
                    # Escape string values
                    safe_value = _escape_cypher_string(value)
                    prop_strings.append(f'{safe_key}: "{safe_value}"')
                elif isinstance(value, bool):
                    # Use lowercase boolean literals
                    prop_strings.append(f"{safe_key}: {str(value).lower()}")
                elif isinstance(value, (int, float)):
                    # Numbers are safe
                    prop_strings.append(f"{safe_key}: {json.dumps(value)}")
                elif isinstance(value, (list, dict)):
                    # Use JSON representation for complex types
                    json_value = json.dumps(value)
                    safe_value = _escape_cypher_string(json_value)
                    prop_strings.append(f'{safe_key}: "{safe_value}"')
                else:
                    # Skip unsupported types
                    self.logger.warning(
                        f"Skipping property {key} with unsupported type {type(value)}"
                    )
                    continue

            props_str = ", ".join(prop_strings) if prop_strings else ""

            # Get resource type for label
            resource_type = props.get("type", "Resource")

            # Extract last part of resource type for label
            # e.g., "Microsoft.Compute/virtualMachines" -> "virtualMachines"
            if "/" in resource_type:
                label_name = resource_type.split("/")[-1]
            else:
                label_name = "Resource"

            # Validate and escape label
            safe_label = _escape_cypher_identifier(label_name)

            # Generate CREATE statement
            cypher_statements.append(f"CREATE (:{safe_label}:Resource {{{props_str}}});")

        cypher_statements.append("")

        # Create relationships with proper escaping
        cypher_statements.append("// Create relationships")

        for source, target, data in sampled_graph.edges(data=True):
            # Escape node IDs
            safe_source = _escape_cypher_string(source)
            safe_target = _escape_cypher_string(target)

            # Get and validate relationship type
            rel_type = data.get("relationship_type", "RELATED_TO")
            if not _is_safe_cypher_identifier(rel_type):
                self.logger.warning(f"Skipping relationship with unsafe type: {rel_type}")
                continue

            safe_rel_type = _escape_cypher_identifier(rel_type)

            # Generate MATCH + CREATE statement
            cypher_statements.append(
                f'MATCH (a:Resource {{id: "{safe_source}"}}), '
                f'(b:Resource {{id: "{safe_target}"}}) '
                f"CREATE (a)-[:{safe_rel_type}]->(b);"
            )

        # Write to file
        with open(output_path, "w") as f:
            f.write("\n".join(cypher_statements))

        self.logger.info(f"Neo4j Cypher export completed: {output_path}")

    async def _export_iac(
        self,
        node_ids: Set[str],
        node_properties: Dict[str, Dict[str, Any]],
        sampled_graph: nx.DiGraph,
        format: str,
        output_path: str,
    ) -> None:
        """
        Export sample to IaC format (Terraform, ARM, or Bicep).

        This uses the existing IaC emitters to generate templates
        from the sampled graph.
        """
        # Build TenantGraph from sampled data
        resources = []
        for node_id in node_ids:
            if node_id in node_properties:
                resources.append(node_properties[node_id])

        relationships = []
        for source, target, data in sampled_graph.edges(data=True):
            relationships.append(
                {
                    "source": source,
                    "target": target,
                    "type": data.get("relationship_type", "UNKNOWN"),
                }
            )

        tenant_graph = TenantGraph(resources=resources, relationships=relationships)

        # Select emitter
        if format == "terraform":
            emitter = TerraformEmitter()
        elif format == "arm":
            emitter = ArmEmitter()
        elif format == "bicep":
            emitter = BicepEmitter()
        else:
            raise ValueError(f"Unsupported IaC format: {format}")

        # Generate IaC templates
        await emitter.emit_template(tenant_graph, output_path)

        self.logger.info(f"IaC export completed ({format}): {output_path}")

    async def _delete_non_sampled_nodes(
        self,
        sampled_node_ids: Set[str],
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> int:
        """
        Delete all nodes NOT in the sampled set (abstracted layer only).

        This method implements the deletion logic for scale-down delete mode.
        It deletes all abstracted Resource nodes that are NOT in the sampled set.
        Original nodes (:Resource:Original) are preserved.

        Args:
            sampled_node_ids: Set of node IDs to KEEP
            progress_callback: Optional progress callback

        Returns:
            int: Number of nodes deleted

        Raises:
            Neo4jError: If deletion fails
            Exception: If unexpected error occurs

        Example:
            >>> deleted = await service._delete_non_sampled_nodes(
            ...     {"node1", "node2", "node3"}
            ... )
            >>> print(f"Deleted {deleted} nodes")
        """
        self.logger.info(f"Deleting non-sampled nodes (keeping {len(sampled_node_ids)} nodes)")

        if not sampled_node_ids:
            self.logger.warning("No nodes to keep - would delete entire graph. Aborting deletion.")
            return 0

        try:
            # Build parameterized query to delete nodes NOT in sampled set
            # IMPORTANT: Only delete abstracted layer (:Resource without :Original)
            # Use DETACH DELETE to remove relationships automatically
            query = """
            MATCH (r:Resource)
            WHERE NOT r:Original
              AND NOT r.id IN $keep_ids
            DETACH DELETE r
            RETURN count(r) as deleted_count
            """

            nodes_deleted = 0

            with self.session_manager.session() as session:
                result = session.run(query, {"keep_ids": list(sampled_node_ids)})
                record = result.single()

                if record:
                    nodes_deleted = record["deleted_count"]

            self.logger.info(f"Successfully deleted {nodes_deleted} non-sampled nodes")

            if progress_callback:
                progress_callback("Deletion complete", nodes_deleted, nodes_deleted)

            return nodes_deleted

        except Neo4jError as e:
            self.logger.exception(f"Neo4j error during deletion: {e}")
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error during deletion: {e}")
            raise

    async def discover_motifs(
        self,
        tenant_id: str,
        motif_size: int = 3,
        max_motifs: int = 100,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> List[Set[str]]:
        """
        Discover common motifs (recurring patterns) in the graph.

        Motifs are small, recurring subgraph patterns that represent
        common architectural patterns in the Azure tenant.

        Note: This is a simplified motif discovery implementation using
        breadth-first traversal. For production use with large graphs,
        consider using specialized algorithms like:
        - FANMOD (Fast Network Motif Detection)
        - MODA (Motif Discovery Algorithm)
        - ESU (Enumerate Subgraphs)

        These algorithms provide better performance and statistical
        significance testing for motif discovery in large networks.

        Args:
            tenant_id: Azure tenant ID to analyze
            motif_size: Size of motifs to find (3-5 nodes recommended)
            max_motifs: Maximum number of motifs to return
            progress_callback: Optional progress callback

        Returns:
            List[Set[str]]: List of motifs, each as a set of node IDs

        Raises:
            ValueError: If parameters are invalid
            Exception: If motif discovery fails

        Example:
            >>> motifs = await service.discover_motifs(
            ...     "00000000-0000-0000-0000-000000000000",
            ...     motif_size=3,
            ...     max_motifs=10
            ... )
            >>> print(f"Found {len(motifs)} motifs")
            >>> for i, motif in enumerate(motifs[:5]):
            ...     print(f"Motif {i+1}: {len(motif)} nodes")
        """
        self.logger.info(
            f"Discovering motifs for tenant {tenant_id} "
            f"(size={motif_size}, max={max_motifs})"
        )

        if motif_size < 2 or motif_size > 10:
            raise ValueError(f"Motif size must be 2-10, got {motif_size}")

        if max_motifs < 1:
            raise ValueError(f"max_motifs must be positive, got {max_motifs}")

        # Convert to NetworkX
        G, node_properties = await self.neo4j_to_networkx(tenant_id, progress_callback)

        # Find all connected subgraphs of specified size
        # This is a simplified motif discovery - production would use
        # more sophisticated algorithms (e.g., FANMOD, MODA)

        motifs: List[Set[str]] = []
        seen_patterns: Set[frozenset] = set()

        # Sample random starting points
        import random

        nodes = list(G.nodes())
        random.shuffle(nodes)

        for start_node in nodes[: max_motifs * 10]:  # Sample more than needed
            if len(motifs) >= max_motifs:
                break

            # BFS to find connected subgraph of target size
            subgraph_nodes: Set[str] = {start_node}
            frontier = [start_node]

            while len(subgraph_nodes) < motif_size and frontier:
                current = frontier.pop(0)

                # Add neighbors
                for neighbor in G.neighbors(current):
                    if neighbor not in subgraph_nodes:
                        subgraph_nodes.add(neighbor)
                        frontier.append(neighbor)

                        if len(subgraph_nodes) >= motif_size:
                            break

            # Only keep if we found a full motif
            if len(subgraph_nodes) == motif_size:
                pattern = frozenset(subgraph_nodes)

                # Avoid duplicates
                if pattern not in seen_patterns:
                    seen_patterns.add(pattern)
                    motifs.append(subgraph_nodes)

        self.logger.info(f"Discovered {len(motifs)} unique motifs of size {motif_size}")

        return motifs
