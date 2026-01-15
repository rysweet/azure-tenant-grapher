"""
Base Sampler for Azure Tenant Graph Sampling

This module provides the abstract base class for all sampling algorithms.
All samplers inherit from BaseSampler and implement the sample() method.
"""

from abc import ABC, abstractmethod
from typing import Callable, Optional, Set

import networkx as nx


class BaseSampler(ABC):
    """
    Abstract base class for graph sampling algorithms.

    All sampling algorithms must inherit from this class and implement
    the sample() method. Samplers operate on NetworkX graphs and return
    a set of node IDs representing the sampled subgraph.
    """

    @abstractmethod
    async def sample(
        self,
        graph: nx.DiGraph,
        target_count: int,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> Set[str]:
        """
        Sample nodes from the graph.

        Args:
            graph: NetworkX directed graph to sample
            target_count: Target number of nodes to sample
            progress_callback: Optional callback(phase, current, total)

        Returns:
            Set[str]: Set of sampled node IDs

        Raises:
            ValueError: If parameters are invalid
            Exception: If sampling fails
        """
        pass
