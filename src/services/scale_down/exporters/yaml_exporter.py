"""
YAML Exporter for Azure Tenant Graph Sampling

This module exports sampled graphs to human-readable YAML format.
Includes nodes, relationships, and metadata.
"""

import logging
from datetime import UTC, datetime
from typing import Any, Dict, Set

import networkx as nx
import yaml

from src.services.scale_down.exporters.base_exporter import BaseExporter

logger = logging.getLogger(__name__)


class YamlExporter(BaseExporter):
    """
    Export sampled graph to YAML format.

    Creates a human-readable YAML file with:
    - Metadata (timestamp, counts)
    - Nodes (IDs and properties)
    - Relationships (source, target, type, properties)
    """

    def __init__(self) -> None:
        """Initialize the YAML exporter."""
        self.logger = logging.getLogger(__name__)

    async def export(
        self,
        node_ids: Set[str],
        node_properties: Dict[str, Dict[str, Any]],
        sampled_graph: nx.DiGraph,
        output_path: str
    ) -> None:
        """
        Export sample to YAML format.

        Args:
            node_ids: Set of sampled node IDs
            node_properties: Properties for all nodes
            sampled_graph: NetworkX graph of sample
            output_path: Output file path

        Raises:
            ValueError: If output path is invalid
            Exception: If export fails

        Example:
            >>> exporter = YamlExporter()
            >>> await exporter.export(
            ...     sampled_ids,
            ...     node_props,
            ...     G_sampled,
            ...     "/tmp/sample.yaml"
            ... )
        """
        self.logger.info(f"Exporting sample to YAML at {output_path}")

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
