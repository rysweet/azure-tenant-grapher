"""
Orphan detection for architectural analysis.

This module identifies resource types not part of any detected pattern.
Extracted from architectural_pattern_analyzer.py god object (Issue #714).

Philosophy:
- Single Responsibility: Orphan node identification
- Brick & Studs: Public API via OrphanDetector class
- Ruthless Simplicity: NetworkX graph analysis
- Zero-BS: All detection logic works, no stubs
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import networkx as nx

logger = logging.getLogger(__name__)


class OrphanDetector:
    """
    Identifies orphaned nodes in resource graphs.

    Orphaned nodes are resource types that are not part of any
    detected architectural pattern.
    """

    def identify_orphaned_nodes(
        self,
        graph: nx.MultiDiGraph[str],
        pattern_matches: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Identify resource types that are not part of any detected pattern.

        Args:
            graph: NetworkX graph of resources
            pattern_matches: Detected architectural patterns

        Returns:
            List of orphaned nodes with their connection information
        """
        # Collect all nodes that are matched by at least one pattern
        matched_nodes = set()
        for _pattern_name, match in pattern_matches.items():
            matched_nodes.update(match["matched_resources"])

        # Find orphaned nodes (not in any pattern)
        all_nodes = set(graph.nodes())
        orphaned_nodes = all_nodes - matched_nodes

        # Gather connection information for each orphaned node
        orphaned_info = []
        for node in orphaned_nodes:
            # Find what this node connects to
            out_neighbors = list(graph.successors(node))
            in_neighbors = list(graph.predecessors(node))

            # Find edges
            outgoing_edges = []
            for target in out_neighbors:
                edges = graph.get_edge_data(node, target)
                if edges:
                    for _key, data in edges.items():
                        outgoing_edges.append(
                            {
                                "target": target,
                                "relationship": data.get("relationship", "UNKNOWN"),
                                "frequency": data.get("frequency", 0),
                            }
                        )

            incoming_edges = []
            for source in in_neighbors:
                edges = graph.get_edge_data(source, node)
                if edges:
                    for _key, data in edges.items():
                        incoming_edges.append(
                            {
                                "source": source,
                                "relationship": data.get("relationship", "UNKNOWN"),
                                "frequency": data.get("frequency", 0),
                            }
                        )

            orphaned_info.append(
                {
                    "resource_type": node,
                    "connection_count": graph.nodes[node].get("count", 0),
                    "in_degree": graph.in_degree(node),
                    "out_degree": graph.out_degree(node),
                    "total_degree": graph.degree(node),  # type: ignore[misc]
                    "outgoing_edges": outgoing_edges,
                    "incoming_edges": incoming_edges,
                    "connected_to": list(set(out_neighbors + in_neighbors)),
                }
            )

        # Sort by connection count (most connected first)
        orphaned_info.sort(key=lambda x: x["connection_count"], reverse=True)

        logger.info(
            f"Identified {len(orphaned_info)} orphaned nodes "
            f"out of {len(all_nodes)} total nodes"
        )
        return orphaned_info


__all__ = ["OrphanDetector"]
