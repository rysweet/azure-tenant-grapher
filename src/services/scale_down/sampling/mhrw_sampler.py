"""
Metropolis-Hastings Random Walk (MHRW) Sampler

This module implements the MHRW sampling algorithm.
MHRW provides unbiased, uniform sampling across the graph.

Reference:
Gjoka, M., Kurant, M., Butts, C. T., & Markopoulou, A. (2010).
"Walking in Facebook: A case study of unbiased sampling of OSNs."
"""

import logging
from typing import Callable, Optional, Set

import littleballoffur as lbof
import networkx as nx

from src.services.scale_down.sampling.base_sampler import BaseSampler

logger = logging.getLogger(__name__)


class MHRWSampler(BaseSampler):
    """
    Metropolis-Hastings Random Walk (MHRW) sampling algorithm.

    MHRW provides unbiased, uniform sampling across the graph.
    Good for representative samples without structural bias.

    Algorithm:
    1. Start from a random node
    2. Propose a move to a random neighbor
    3. Accept/reject based on degree-corrected probability
    4. Continue until target size reached
    """

    def __init__(self) -> None:
        """Initialize the MHRW sampler."""
        self.logger = logging.getLogger(__name__)

    async def sample(
        self,
        graph: nx.DiGraph,
        target_count: int,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> Set[str]:
        """
        Sample graph using Metropolis-Hastings Random Walk.

        Args:
            graph: NetworkX graph to sample
            target_count: Target number of nodes to sample
            progress_callback: Optional progress callback

        Returns:
            Set[str]: Set of sampled node IDs

        Raises:
            ValueError: If graph is empty or target_count invalid
            Exception: If sampling fails

        Example:
            >>> sampler = MHRWSampler()
            >>> sampled_ids = await sampler.sample(G, 1000)
            >>> print(f"Sampled {len(sampled_ids)} nodes")
        """
        self.logger.info(
            f"Applying Metropolis-Hastings Random Walk sampling (target={target_count})"
        )

        if not graph.nodes():
            raise ValueError("Graph has no nodes")

        if target_count <= 0:
            raise ValueError(f"target_count must be positive, got {target_count}")

        # MHRW requires undirected graph
        G_undirected = graph.to_undirected()

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

            if progress_callback:
                progress_callback("MHRW sampling", len(sampled_node_ids), target_count)

            return sampled_node_ids

        except (ValueError, nx.NetworkXError) as e:
            self.logger.exception(f"MHRW sampling failed: {e}")
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error during MHRW sampling: {e}")
            raise
