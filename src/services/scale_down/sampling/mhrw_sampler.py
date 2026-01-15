"""
Metropolis-Hastings Random Walk (MHRW) Sampler

Custom implementation for Python 3.11-3.13 compatibility.
Replaces littleballoffur dependency with pure NetworkX implementation.

Algorithm Reference:
Gjoka, M., Kurant, M., Butts, C. T., & Markopoulou, A. (2010).
"Walking in Facebook: A case study of unbiased sampling of OSNs."
INFOCOM, 2010 Proceedings IEEE.
"""

import logging
import random
from typing import Callable, Optional, Set

import networkx as nx

from src.services.scale_down.sampling.base_sampler import BaseSampler

logger = logging.getLogger(__name__)


class MHRWSampler(BaseSampler):
    """
    Metropolis-Hastings Random Walk (MHRW) sampling algorithm.

    Pure NetworkX implementation providing unbiased, uniform sampling.

    Algorithm:
    1. Convert directed graph to undirected
    2. Start from random node
    3. Propose move to random neighbor
    4. Accept with probability: min(1, degree(current) / degree(candidate))
    5. If accepted: move to candidate, else: stay at current
    6. Repeat until target_count unique nodes sampled
    7. Includes 10% burn-in period to reduce initialization bias
    """

    def __init__(self) -> None:
        """Initialize the MHRW sampler."""
        self.logger = logging.getLogger(__name__)

    async def sample(
        self,
        graph: nx.DiGraph,
        target_count: int,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
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

        Example:
            >>> sampler = MHRWSampler()
            >>> sampled_ids = await sampler.sample(G, 1000)
            >>> print(str(f"Sampled {len(sampled_ids)} nodes"))
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
            # Custom MHRW implementation
            sampled_nodes = self._mhrw_sample(
                G_undirected, target_count, progress_callback
            )

            self.logger.info(
                str(f"MHRW sampling completed: {len(sampled_nodes)} nodes")
            )

            if progress_callback:
                progress_callback("MHRW sampling", len(sampled_nodes), target_count)

            return sampled_nodes

        except (ValueError, nx.NetworkXError) as e:
            self.logger.exception(f"MHRW sampling failed: {e}")
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error during MHRW sampling: {e}")
            raise

    def _mhrw_sample(
        self,
        graph: nx.Graph,
        target_count: int,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> Set[str]:
        """
        Core MHRW sampling algorithm.

        Implements Metropolis-Hastings acceptance probability:
        P(accept) = min(1, degree(current) / degree(candidate))

        Args:
            graph: Undirected NetworkX graph
            target_count: Number of nodes to sample
            progress_callback: Optional callback for progress updates

        Returns:
            Set of sampled node IDs
        """
        # Handle edge cases
        all_nodes = list(graph.nodes())
        if target_count >= len(all_nodes):
            return set(all_nodes)

        # Start at random node
        current = random.choice(all_nodes)
        sampled = set()

        # Calculate burn-in period (10% of target)
        burn_in = int(target_count * 0.1)

        # Perform random walk with Metropolis-Hastings acceptance
        steps = 0
        steps_without_new_sample = 0
        max_steps_without_progress = 100

        while len(sampled) < target_count:
            steps += 1
            prev_sampled_count = len(sampled)

            # Safety check: if no progress for too long, jump to unsampled node
            if steps_without_new_sample >= max_steps_without_progress:
                # Find unsampled nodes
                unsampled = set(all_nodes) - sampled
                if unsampled:
                    current = random.choice(list(unsampled))
                    steps_without_new_sample = 0
                    # Force add current to sample
                    if steps > burn_in:
                        sampled.add(current)
                    continue
                else:
                    # All nodes sampled
                    break

            # Get neighbors of current node
            neighbors = list(graph.neighbors(current))
            if not neighbors:
                # Isolated node - add it to sample and pick new random node
                if steps > burn_in:
                    sampled.add(current)
                    if len(sampled) >= target_count:
                        break
                # Jump to a random unsampled node if possible
                unsampled = set(all_nodes) - sampled
                if unsampled:
                    current = random.choice(list(unsampled))
                else:
                    current = random.choice(all_nodes)
                continue

            # Propose move to random neighbor
            candidate = random.choice(neighbors)

            # Metropolis-Hastings acceptance probability
            current_degree = graph.degree(current)
            candidate_degree = graph.degree(candidate)

            # Accept with probability min(1, degree(current) / degree(candidate))
            acceptance_prob = min(1.0, current_degree / candidate_degree)

            if random.random() < acceptance_prob:
                current = candidate

            # Add to sample after burn-in period
            if steps > burn_in:
                sampled.add(current)

            # Track progress
            if len(sampled) == prev_sampled_count:
                steps_without_new_sample += 1
            else:
                steps_without_new_sample = 0

            # Progress callback every 10% of target
            if progress_callback and steps % max(1, target_count // 10) == 0:
                progress_callback("MHRW sampling", len(sampled), target_count)

        return sampled
