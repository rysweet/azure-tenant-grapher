"""
Graph Builder Module

Builds NetworkX graphs from Neo4j relationships.
Extracted from architectural_pattern_analyzer.py god object (Issue #714).

Philosophy:
- Single Responsibility: NetworkX graph construction
- Zero-BS: All functions work, no stubs
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List, Tuple

import networkx as nx
from neo4j import Driver

logger = logging.getLogger(__name__)


class GraphBuilder:
    """Builds NetworkX graphs from aggregated relationships."""

    def __init__(self, driver: Driver):
        self.driver = driver

    def fetch_all_relationships(self) -> List[Dict[str, Any]]:
        """
        Query all relationships from Neo4j graph.

        Filters out SCAN_SOURCE_NODE relationships which are internal dual-graph
        bookkeeping links and not actual architectural relationships.

        Returns:
            List of relationship records with source/target labels and types
        """
        if not self.driver:
            raise RuntimeError("Not connected to Neo4j. Call connect() first.")

        query = """
        MATCH (source)-[r]->(target)
        WHERE type(r) <> 'SCAN_SOURCE_NODE'
        RETURN labels(source) as source_labels,
               source.type as source_type,
               type(r) as rel_type,
               labels(target) as target_labels,
               target.type as target_type
        """

        all_relationships = []
        with self.driver.session() as session:
            result = session.run(query)
            for record in result:
                all_relationships.append(
                    {
                        "source_labels": record["source_labels"],
                        "source_type": record["source_type"],
                        "rel_type": record["rel_type"],
                        "target_labels": record["target_labels"],
                        "target_type": record["target_type"],
                    }
                )

        logger.info(str(f"Loaded {len(all_relationships)} relationships from graph"))
        return all_relationships


    def build_networkx_graph(
        self, aggregated_relationships: List[Dict[str, Any]]
    ) -> Tuple[nx.MultiDiGraph[str], Dict[str, int], Dict[Tuple[str, str], int]]:
        """
        Build NetworkX graph from aggregated relationships.

        Args:
            aggregated_relationships: List of aggregated relationships

        Returns:
            Tuple of (graph, resource_type_counts, edge_counts)
        """
        G: nx.MultiDiGraph[str] = nx.MultiDiGraph()

        # Collect all unique resource types and their frequencies
        resource_type_counts: Dict[str, int] = defaultdict(int)

        # Count occurrences of each resource type from relationships
        for rel in aggregated_relationships:
            resource_type_counts[rel["source_type"]] += rel["frequency"]
            resource_type_counts[rel["target_type"]] += rel["frequency"]

        # Add nodes for all resource types
        for resource_type, count in resource_type_counts.items():
            G.add_node(resource_type, count=count)

        # Add edges for relationships
        edge_counts: Dict[Tuple[str, str], int] = defaultdict(int)
        for rel in aggregated_relationships:
            source = rel["source_type"]
            target = rel["target_type"]
            rel_type = rel["rel_type"]
            frequency = rel["frequency"]

            # Add edge
            G.add_edge(source, target, relationship=rel_type, frequency=frequency)

            # Track aggregated edge counts (for visualization)
            edge_key = (source, target)
            edge_counts[edge_key] += frequency

        logger.info(
            f"Graph constructed: {G.number_of_nodes()} nodes, "
            f"{G.number_of_edges()} edges"
        )
        return G, dict(resource_type_counts), dict(edge_counts)


__all__ = ["GraphBuilder"]
