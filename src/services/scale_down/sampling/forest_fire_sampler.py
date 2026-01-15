"""
Forest Fire Sampler for Azure Tenant Graph Sampling

This module implements the Forest Fire sampling algorithm.
Forest Fire spreads through the graph like a wildfire, preserving
local community structure.

Reference:
Leskovec, J., & Faloutsos, C. (2006). "Sampling from large graphs."
"""

from __future__ import annotations

import logging
import random
from typing import Callable, Optional, Set

import networkx as nx

from src.services.scale_down.sampling.base_sampler import BaseSampler

logger = logging.getLogger(__name__)


class ForestFireSampler(BaseSampler):
    """
    Forest Fire sampling algorithm.

    Forest Fire sampling spreads through the graph like a wildfire,
    preserving local community structure. Good for sampling densely
    connected subgraphs.

    Algorithm:
    1. Start from a random seed node
    2. Sample neighbors with probability p
    3. Recursively spread to sampled neighbors
    4. Continue until target size reached
    """

    def __init__(self) -> None:
        """Initialize the Forest Fire sampler."""
        self.logger = logging.getLogger(__name__)

    async def sample(
        self,
        graph: nx.DiGraph[str],
        target_count: int,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> Set[str]:
        """
        Sample graph using Forest Fire algorithm.

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
            >>> sampler = ForestFireSampler()
            >>> sampled_ids = await sampler.sample(G, 1000)
            >>> print(str(f"Sampled {len(sampled_ids)} nodes"))
        """
        self.logger.info(str(f"Applying Forest Fire sampling (target={target_count})"))

        if not graph.nodes():
            raise ValueError("Graph has no nodes")

        if target_count <= 0:
            raise ValueError(f"target_count must be positive, got {target_count}")

        # Forest Fire requires undirected graph
        G_undirected = graph.to_undirected()

        # Calculate sampling probability (p parameter)
        # Higher p = larger samples
        sampling_ratio = target_count / graph.number_of_nodes()
        p = min(0.7, sampling_ratio * 2)  # Heuristic: scale p with ratio

        try:
            sampled_nodes = set()
            nodes_list = list(G_undirected.nodes())

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
                        target_count - len(sampled_nodes),
                    )
                    burned = random.sample(unvisited_neighbors, num_to_burn)
                    for node in burned:
                        sampled_nodes.add(node)
                        queue.append(node)

                if progress_callback and len(sampled_nodes) % 100 == 0:
                    progress_callback(
                        "Forest Fire sampling", len(sampled_nodes), target_count
                    )

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
