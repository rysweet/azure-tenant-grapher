"""
Graph Operations for Azure Tenant Grapher

This module provides graph manipulation operations for scale-down workflows.
Operations include node deletion and motif discovery.

Key Features:
- Delete non-sampled nodes (abstracted layer only)
- Discover recurring graph patterns (motifs)
- BFS-based pattern discovery
"""

from __future__ import annotations

import logging
import random
from typing import Callable, List, Optional, Set

import networkx as nx
from neo4j.exceptions import Neo4jError

from src.services.base_scale_service import BaseScaleService
from src.utils.session_manager import Neo4jSessionManager

logger = logging.getLogger(__name__)


class GraphOperations(BaseScaleService):
    """
    Perform graph manipulation operations for scale-down workflows.

    This class handles operations that modify the graph structure,
    including deletion of non-sampled nodes and discovery of motifs.
    """

    def __init__(self, session_manager: Neo4jSessionManager) -> None:
        """
        Initialize the graph operations handler.

        Args:
            session_manager: Neo4j session manager for database operations
        """
        super().__init__(session_manager)
        self.session_manager = session_manager
        self.logger = logging.getLogger(__name__)

    async def delete_non_sampled_nodes(
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
            >>> ops = GraphOperations(session_manager)
            >>> deleted = await ops.delete_non_sampled_nodes(
            ...     {"node1", "node2", "node3"}
            ... )
            >>> print(str(f"Deleted {deleted} nodes"))
        """
        self.logger.info(
            f"Deleting non-sampled nodes (keeping {len(sampled_node_ids)} nodes)"
        )

        if not sampled_node_ids:
            self.logger.warning(
                "No nodes to keep - would delete entire graph. Aborting deletion."
            )
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

            self.logger.info(
                str(f"Successfully deleted {nodes_deleted} non-sampled nodes")
            )

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
        graph: nx.DiGraph[str],
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
            graph: NetworkX graph to analyze
            motif_size: Size of motifs to find (3-5 nodes recommended)
            max_motifs: Maximum number of motifs to return
            progress_callback: Optional progress callback

        Returns:
            List[Set[str]]: List of motifs, each as a set of node IDs

        Raises:
            ValueError: If parameters are invalid
            Exception: If motif discovery fails

        Example:
            >>> ops = GraphOperations(session_manager)
            >>> motifs = await ops.discover_motifs(
            ...     graph,
            ...     motif_size=3,
            ...     max_motifs=10
            ... )
            >>> print(str(f"Found {len(motifs)} motifs"))
        """
        self.logger.info(
            str(f"Discovering motifs (size={motif_size}, max={max_motifs})")
        )

        if motif_size < 2 or motif_size > 10:
            raise ValueError(f"Motif size must be 2-10, got {motif_size}")

        if max_motifs < 1:
            raise ValueError(f"max_motifs must be positive, got {max_motifs}")

        # Find all connected subgraphs of specified size
        # This is a simplified motif discovery - production would use
        # more sophisticated algorithms (e.g., FANMOD, MODA)

        motifs: List[Set[str]] = []
        seen_patterns: Set[frozenset] = set()

        # Sample random starting points
        nodes = list(graph.nodes())
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
                for neighbor in graph.neighbors(current):
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

            if progress_callback and len(motifs) % 10 == 0:
                progress_callback("Discovering motifs", len(motifs), max_motifs)

        self.logger.info(
            str(f"Discovered {len(motifs)} unique motifs of size {motif_size}")
        )

        return motifs
