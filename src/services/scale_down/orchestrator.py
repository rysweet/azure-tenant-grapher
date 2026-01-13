"""
Scale-Down Orchestrator for Azure Tenant Grapher

This module coordinates all scale-down operations by orchestrating
extraction, sampling, quality metrics, and export.

Main entry point for scale-down workflows.
"""

import logging
from datetime import UTC, datetime
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import networkx as nx

from src.services.base_scale_service import BaseScaleService
from src.services.scale_down.exporters.iac_exporter import IaCExporter
from src.services.scale_down.exporters.json_exporter import JsonExporter
from src.services.scale_down.exporters.neo4j_exporter import Neo4jExporter
from src.services.scale_down.exporters.yaml_exporter import YamlExporter
from src.services.scale_down.graph_extractor import GraphExtractor
from src.services.scale_down.graph_operations import GraphOperations
from src.services.scale_down.quality_metrics import (
    QualityMetrics,
    QualityMetricsCalculator,
)
from src.services.scale_down.sampling.forest_fire_sampler import ForestFireSampler
from src.services.scale_down.sampling.mhrw_sampler import MHRWSampler
from src.services.scale_down.sampling.pattern_sampler import PatternSampler
from src.services.scale_down.sampling.random_walk_sampler import RandomWalkSampler
from src.utils.session_manager import Neo4jSessionManager

logger = logging.getLogger(__name__)


class ScaleDownOrchestrator(BaseScaleService):
    """
    Main coordinator for scale-down operations.

    This orchestrator coordinates all scale-down workflows:
    1. Extract: Neo4j to NetworkX conversion
    2. Sample: Apply sampling algorithm
    3. Calculate: Quality metrics
    4. Export/Delete: Output or modify database

    Supported Sampling Algorithms:
    - forest_fire: Preserves local structure, spreads like wildfire
    - mhrw: Metropolis-Hastings Random Walk, unbiased sampling
    - random_walk: Simple random walk sampling
    - pattern: Pattern-based sampling by resource attributes

    Export Formats:
    - yaml: Human-readable node/edge list
    - json: Machine-readable node/edge list
    - neo4j: Cypher statements with proper escaping
    - terraform/arm/bicep: IaC templates

    Examples:
        >>> session_manager = Neo4jSessionManager(uri, user, password)
        >>> orchestrator = ScaleDownOrchestrator(session_manager)
        >>> node_ids, metrics = await orchestrator.sample_graph(
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
        Initialize the scale-down orchestrator.

        Args:
            session_manager: Neo4j session manager for database operations
        """
        super().__init__(session_manager)
        self.logger = logging.getLogger(__name__)

        # Initialize components
        self.extractor = GraphExtractor(session_manager)
        self.operations = GraphOperations(session_manager)
        self.metrics_calculator = QualityMetricsCalculator()

        # Initialize samplers
        self.samplers = {
            "forest_fire": ForestFireSampler(),
            "mhrw": MHRWSampler(),
            "random_walk": RandomWalkSampler(),
            "pattern": PatternSampler(session_manager),
        }

        # Initialize exporters
        self.exporters = {
            "yaml": YamlExporter(),
            "json": JsonExporter(),
            "neo4j": Neo4jExporter(),
        }

    async def neo4j_to_networkx(
        self,
        tenant_id: str,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> Tuple[nx.DiGraph[str], Dict[str, Dict[str, Any]]]:
        """
        Convert Neo4j graph to NetworkX directed graph.

        Backward compatibility wrapper for graph_extractor.extract_graph().

        Args:
            tenant_id: Azure tenant ID to extract
            progress_callback: Optional callback(phase, current, total)

        Returns:
            Tuple[nx.DiGraph[str], Dict[str, Dict[str, Any]]]:
                - NetworkX directed graph with node IDs
                - Dictionary mapping node IDs to full properties

        Raises:
            ValueError: If tenant not found or has no resources
            Exception: If database query fails

        Example:
            >>> G, node_props = await orchestrator.neo4j_to_networkx(
            ...     "00000000-0000-0000-0000-000000000000"
            ... )
            >>> print(f"Loaded {G.number_of_nodes()} nodes")
        """
        # Ensure extractor uses the orchestrator's validate_tenant_exists for consistent mocking
        # Copy validation state from orchestrator to extractor for test mocking
        if hasattr(self, "validate_tenant_exists"):
            self.extractor.validate_tenant_exists = self.validate_tenant_exists
        return await self.extractor.extract_graph(tenant_id, progress_callback)

    async def sample_graph(
        self,
        tenant_id: str,
        algorithm: str,
        target_size: float,
        output_mode: str,
        output_path: Optional[str] = None,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
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
            >>> node_ids, metrics, deleted = await orchestrator.sample_graph(
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

        # Align valid_output_modes with what CLI offers
        valid_output_modes = [
            "delete",
            "export",
            "new-tenant",
            "yaml",
            "json",
            "neo4j",
            "terraform",
            "arm",
            "bicep",
        ]
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

        G, node_properties = await self.extractor.extract_graph(
            tenant_id, progress_callback
        )

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

        # Calculate sampling ratio for logging
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

        # Get appropriate sampler
        if algorithm not in self.samplers:
            raise ValueError(f"Algorithm not implemented: {algorithm}")

        sampler = self.samplers[algorithm]
        sampled_node_ids = await sampler.sample(G, target_node_count, progress_callback)

        sampling_time = (datetime.now(UTC) - sampling_start).total_seconds()

        self.logger.info(
            f"Sampled {len(sampled_node_ids)} nodes in {sampling_time:.2f}s"
        )

        # Create sampled subgraph
        sampled_graph = G.subgraph(sampled_node_ids).copy()

        # Stage 3: Calculate quality metrics
        if progress_callback:
            progress_callback("Calculating metrics", 0, 100)

        metrics = self.metrics_calculator.calculate_metrics(
            G, sampled_graph, node_properties, sampled_node_ids, sampling_time
        )

        # Stage 4: Handle output mode
        nodes_deleted = 0

        if output_mode == "delete":
            # Delete all nodes NOT in sampled_node_ids (abstracted layer only)
            if progress_callback:
                progress_callback("Deleting non-sampled nodes", 0, 100)

            nodes_deleted = await self.operations.delete_non_sampled_nodes(
                sampled_node_ids, progress_callback
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

    async def export_sample(
        self,
        node_ids: Set[str],
        node_properties: Dict[str, Dict[str, Any]],
        sampled_graph: nx.DiGraph[str],
        format: str,
        output_path: str,
    ) -> None:
        """
        Export sampled graph to specified format.

        Supports multiple export formats:
        - yaml: Human-readable YAML with nodes and relationships
        - json: Machine-readable JSON with nodes and relationships
        - neo4j: Cypher statements with proper escaping
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
            >>> await orchestrator.export_sample(
            ...     sampled_ids,
            ...     node_props,
            ...     G_sampled,
            ...     "yaml",
            ...     "/tmp/sample.yaml"
            ... )
        """
        self.logger.info(f"Exporting sample to {format} at {output_path}")

        # Handle IaC formats separately (require instantiation)
        if format in ["terraform", "arm", "bicep"]:
            exporter = IaCExporter(format)
            await exporter.export(node_ids, node_properties, sampled_graph, output_path)
        elif format in self.exporters:
            exporter = self.exporters[format]
            await exporter.export(node_ids, node_properties, sampled_graph, output_path)
        else:
            raise ValueError(f"Unsupported export format: {format}")

        self.logger.info(f"Export completed: {output_path}")

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
                    "type": "Microsoft.Compute/virtualMachines",
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
            ...     "type": "Microsoft.Compute/virtualMachines",
            ...     "tags.environment": "production"
            ... }
            >>> node_ids = await orchestrator.sample_by_pattern(
            ...     "00000000-0000-0000-0000-000000000000",
            ...     criteria
            ... )
            >>> print(f"Found {len(node_ids)} matching nodes")
        """
        # Validate tenant exists
        if not await self.validate_tenant_exists(tenant_id):
            raise ValueError(f"Tenant {tenant_id} not found in database")

        # Use pattern sampler
        pattern_sampler = self.samplers["pattern"]
        return await pattern_sampler.sample_by_criteria(
            tenant_id, criteria, progress_callback
        )

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
            >>> motifs = await orchestrator.discover_motifs(
            ...     "00000000-0000-0000-0000-000000000000",
            ...     motif_size=3,
            ...     max_motifs=10
            ... )
            >>> print(f"Found {len(motifs)} motifs")
        """
        # Extract graph
        G, _ = await self.extractor.extract_graph(tenant_id, progress_callback)

        # Discover motifs
        return await self.operations.discover_motifs(
            G, motif_size, max_motifs, progress_callback
        )

    # ========================================================================
    # BACKWARD COMPATIBILITY METHODS (for existing tests)
    # ========================================================================

    async def _sample_mhrw(
        self, graph: nx.Graph[str], target_count: int, progress_callback=None
    ) -> List[str]:
        """Backward compatibility wrapper for MHRW sampling."""
        return await self.samplers["mhrw"].sample(
            graph, target_count, progress_callback
        )

    async def _sample_random_walk(
        self, graph: nx.Graph[str], target_count: int, progress_callback=None
    ) -> List[str]:
        """Backward compatibility wrapper for Random Walk sampling."""
        return await self.samplers["random_walk"].sample(
            graph, target_count, progress_callback
        )

    def _calculate_quality_metrics(
        self,
        original_graph: nx.Graph[str],
        sampled_graph: nx.Graph[str],
        node_properties: Optional[Dict] = None,
        sampled_ids: Optional[Set[str]] = None,
        computation_time: Optional[float] = None,
    ):
        """Backward compatibility wrapper for quality metrics calculation."""
        # Provide defaults if not given
        if node_properties is None:
            node_properties = {}
        if sampled_ids is None:
            sampled_ids = set(sampled_graph.nodes())
        if computation_time is None:
            computation_time = 0.0

        return self.metrics_calculator.calculate_metrics(
            original_graph,
            sampled_graph,
            node_properties,
            sampled_ids,
            computation_time,
        )

    def _calculate_kl_divergence(
        self, dist1: Dict[int, int], dist2: Dict[int, int]
    ) -> float:
        """Backward compatibility wrapper for KL divergence calculation."""
        return self.metrics_calculator._calculate_kl_divergence(dist1, dist2)

    async def _export_yaml(
        self,
        sampled_ids: List[str],
        node_properties: Dict,
        graph: nx.Graph[str],
        output_file: str,
    ):
        """Backward compatibility wrapper for YAML export (old signature)."""
        # Convert to new format expected by exporter
        # The new exporters expect (graph, output_file, tenant_id, metadata)
        metadata = {"sampled_ids": sampled_ids, "node_properties": node_properties}
        return await self.exporters["yaml"].export(
            graph, output_file, "legacy", metadata
        )

    async def _export_json(
        self,
        sampled_ids: List[str],
        node_properties: Dict,
        graph: nx.Graph[str],
        output_file: str,
    ):
        """Backward compatibility wrapper for JSON export (old signature)."""
        metadata = {"sampled_ids": sampled_ids, "node_properties": node_properties}
        return await self.exporters["json"].export(
            graph, output_file, "legacy", metadata
        )

    async def _export_neo4j(
        self,
        sampled_ids: List[str],
        node_properties: Dict,
        graph: nx.Graph[str],
        output_file: str,
    ):
        """Backward compatibility wrapper for Neo4j export (old signature)."""
        metadata = {"sampled_ids": sampled_ids, "node_properties": node_properties}
        return await self.exporters["neo4j"].export(
            graph, output_file, "legacy", metadata
        )
