"""
Base Exporter for Azure Tenant Graph Export

This module provides the abstract base class for all export formats.
All exporters inherit from BaseExporter and implement the export() method.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Set

import networkx as nx


class BaseExporter(ABC):
    """
    Abstract base class for graph export formats.

    All export formats must inherit from this class and implement
    the export() method. Exporters receive sampled node IDs, node
    properties, and the sampled graph, then write to the specified path.
    """

    @abstractmethod
    async def export(
        self,
        node_ids: Set[str],
        node_properties: Dict[str, Dict[str, Any]],
        sampled_graph: nx.DiGraph[str],
        output_path: str,
    ) -> None:
        """
        Export sampled graph to specified format.

        Args:
            node_ids: Set of sampled node IDs
            node_properties: Properties for all nodes
            sampled_graph: NetworkX graph of sample
            output_path: Output file or directory path

        Raises:
            ValueError: If parameters are invalid
            Exception: If export fails
        """
        pass
