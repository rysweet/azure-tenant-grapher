"""
Random Walk Sampler for Azure Tenant Graph Sampling

This module implements the simple Random Walk sampling algorithm.
Random walk explores the graph by taking random steps from each node.
"""

import logging
import random
from typing import Callable, Optional, Set

import networkx as nx

from src.services.scale_down.sampling.base_sampler import BaseSampler

logger = logging.getLogger(__name__)


class RandomWalkSampler(BaseSampler):
    """
    Simple Random Walk sampling algorithm.

    Random walk sampling explores the graph by taking random steps
    from each node. Simpler than MHRW but potentially biased toward
    high-degree nodes.

    Algorithm:
    1. Start from a random node
    2. Walk to a random neighbor
    3. Repeat until target size reached
    4. If stuck, jump to random unvisited node
    """

    def __init__(self) -> None:
        """Initialize the Random Walk sampler."""
        self.logger = logging.getLogger(__name__)

    async def sample(
        self,
        graph: nx.DiGraph,
        target_count: int,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> Set[str]:
        """
        Sample graph using simple Random Walk.

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
            >>> sampler = RandomWalkSampler()
            >>> sampled_ids = await sampler.sample(G, 1000)
            >>> print(str(f"Sampled {len(sampled_ids)} nodes"))
        """
        self.logger.info(str(f"Applying Random Walk sampling (target={target_count})"))

        if not graph.nodes():
            raise ValueError("Graph has no nodes")

        if target_count <= 0:
            raise ValueError(f"target_count must be positive, got {target_count}")

        # Random walk requires undirected graph
        G_undirected = graph.to_undirected()

        try:
            sampled_nodes = set()
            nodes_list = list(G_undirected.nodes())

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

                if progress_callback and len(sampled_nodes) % 100 == 0:
                    progress_callback(
                        "Random Walk sampling", len(sampled_nodes), target_count
                    )

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
