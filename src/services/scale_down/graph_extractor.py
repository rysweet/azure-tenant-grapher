"""
Graph Extractor for Azure Tenant Grapher

This module handles extraction of Neo4j graphs to NetworkX format.
It operates ONLY on the abstracted layer (:Resource nodes without :Original label)
and excludes SCAN_SOURCE_NODE relationships.

Key Features:
- Streaming extraction in configurable batches (default: 5000)
- Memory-efficient processing for large graphs
- Operates only on abstracted layer
- Excludes SCAN_SOURCE_NODE relationships
"""

import logging
from typing import Any, Callable, Dict, Optional, Tuple
import networkx as nx
from src.utils.session_manager import Neo4jSessionManager
from src.services.base_scale_service import BaseScaleService

logger = logging.getLogger(__name__)


class GraphExtractor(BaseScaleService):
    """
    Extract Neo4j graphs to NetworkX format with streaming support.

    This extractor queries the abstracted layer of the dual-graph
    architecture, providing a clean view of resources for sampling.
    """

    def __init__(self, session_manager: Neo4jSessionManager) -> None:
        """
        Initialize the graph extractor.

        Args:
            session_manager: Neo4j session manager for database operations
        """
        super().__init__(session_manager)
        self.session_manager = session_manager
        self.logger = logging.getLogger(__name__)

    async def extract_graph(
        self,
        tenant_id: str,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        batch_size: int = 5000
    ) -> Tuple[nx.DiGraph, Dict[str, Dict[str, Any]]]:
        """
        Convert Neo4j graph to NetworkX directed graph.

        Streams data in configurable batches for memory efficiency.
        Queries ONLY the abstracted layer (:Resource nodes without :Original label).
        Excludes SCAN_SOURCE_NODE relationships.

        Args:
            tenant_id: Azure tenant ID to extract
            progress_callback: Optional callback(phase, current, total)
            batch_size: Number of records per batch (default: 5000)

        Returns:
            Tuple[nx.DiGraph, Dict[str, Dict[str, Any]]]:
                - NetworkX directed graph with node IDs
                - Dictionary mapping node IDs to full properties

        Raises:
            ValueError: If tenant not found or has no resources
            Exception: If database query fails

        Example:
            >>> extractor = GraphExtractor(session_manager)
            >>> G, node_props = await extractor.extract_graph(
            ...     "00000000-0000-0000-0000-000000000000"
            ... )
            >>> print(f"Loaded {G.number_of_nodes()} nodes")
        """
        self.logger.info(f"Converting Neo4j graph to NetworkX for tenant {tenant_id}")

        # Validate tenant exists
        if not await self.validate_tenant_exists(tenant_id):
            raise ValueError(f"Tenant {tenant_id} not found in database")

        G = nx.DiGraph()
        node_properties: Dict[str, Dict[str, Any]] = {}

        # Step 1: Load nodes from abstracted layer
        node_query = """
        MATCH (r:Resource)
        WHERE NOT r:Original
        RETURN r.id as id, properties(r) as props
        SKIP $skip
        LIMIT $limit
        """

        nodes_loaded = 0
        skip = 0

        with self.session_manager.session() as session:
            while True:
                result = session.run(
                    node_query,
                    {"tenant_id": tenant_id, "skip": skip, "limit": batch_size},
                )
                batch = list(result)

                if not batch:
                    break

                for record in batch:
                    node_id = record["id"]
                    props = dict(record["props"])

                    # Add node to graph
                    G.add_node(node_id)

                    # Store full properties
                    node_properties[node_id] = props

                    nodes_loaded += 1

                if progress_callback:
                    progress_callback("Loading nodes", nodes_loaded, nodes_loaded)

                skip += batch_size

                # Log progress
                if nodes_loaded % 10000 == 0:
                    self.logger.debug(f"Loaded {nodes_loaded} nodes...")

        self.logger.info(f"Loaded {nodes_loaded} nodes from Neo4j")

        if nodes_loaded == 0:
            raise ValueError(f"No resources found for tenant {tenant_id}")

        # Step 2: Load relationships (exclude SCAN_SOURCE_NODE)
        # Only include Resource->Resource for NetworkX (sampling needs consistent node types)
        edge_query = """
        MATCH (r1:Resource)-[rel]->(r2:Resource)
        WHERE NOT r1:Original AND NOT r2:Original
          AND type(rel) <> 'SCAN_SOURCE_NODE'
        RETURN r1.id as source, r2.id as target, type(rel) as rel_type,
               properties(rel) as rel_props
        SKIP $skip
        LIMIT $limit
        """

        edges_loaded = 0
        skip = 0

        with self.session_manager.session() as session:
            while True:
                result = session.run(
                    edge_query,
                    {"tenant_id": tenant_id, "skip": skip, "limit": batch_size},
                )
                batch = list(result)

                if not batch:
                    break

                for record in batch:
                    source = record["source"]
                    target = record["target"]
                    rel_type = record["rel_type"]
                    rel_props = dict(record["rel_props"]) if record["rel_props"] else {}

                    # Only add edge if both nodes exist in our graph
                    if source in G.nodes and target in G.nodes:
                        G.add_edge(
                            source, target, relationship_type=rel_type, **rel_props
                        )
                        edges_loaded += 1

                if progress_callback:
                    progress_callback("Loading edges", edges_loaded, edges_loaded)

                skip += batch_size

                # Log progress
                if edges_loaded % 10000 == 0:
                    self.logger.debug(f"Loaded {edges_loaded} edges...")

        self.logger.info(f"Loaded {edges_loaded} edges from Neo4j")
        self.logger.info(
            f"Conversion complete: {G.number_of_nodes()} nodes, "
            f"{G.number_of_edges()} edges"
        )

        return G, node_properties
