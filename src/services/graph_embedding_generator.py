"""Graph embedding generation using node2vec for importance-weighted sampling.

This module generates vector embeddings of graph nodes using the node2vec
algorithm, which captures network topology and enables importance-based
sampling that preserves hub and bridge nodes.
"""

import logging
from typing import Dict, Optional

import networkx as nx
import numpy as np
from neo4j import Driver
from node2vec import Node2Vec

logger = logging.getLogger(__name__)


class GraphEmbeddingGenerator:
    """Generate node embeddings using node2vec algorithm.

    Node2vec creates vector representations of nodes by performing biased
    random walks that balance breadth-first (structural role) and depth-first
    (local community) exploration. These embeddings capture graph topology
    and enable importance-based sampling.
    """

    def __init__(
        self,
        driver: Driver,
        dimensions: int = 64,
        walk_length: int = 30,
        num_walks: int = 200,
        workers: int = 4,
        p: float = 1.0,
        q: float = 1.0,
    ):
        """Initialize embedding generator.

        Args:
            driver: Neo4j database driver
            dimensions: Embedding vector dimensions (default: 64)
            walk_length: Length of each random walk (default: 30)
            num_walks: Number of walks per node (default: 200)
            workers: Parallel workers for walk generation (default: 4)
            p: Return parameter - controls likelihood of returning to previous node
                (default: 1.0)
            q: In-out parameter - controls exploration vs exploitation
                (default: 1.0 for balanced BFS/DFS)
        """
        self.driver = driver
        self.dimensions = dimensions
        self.walk_length = walk_length
        self.num_walks = num_walks
        self.workers = workers
        self.p = p
        self.q = q

    def generate_embeddings(
        self, tenant_id: str, use_cache: bool = True
    ) -> Dict[str, np.ndarray]:
        """Generate node embeddings for all resources in tenant.

        Args:
            tenant_id: Tenant ID to generate embeddings for
            use_cache: Whether to use cached embeddings if available

        Returns:
            Dictionary mapping node IDs to embedding vectors

        Raises:
            ValueError: If tenant has no resources or graph cannot be built
        """
        logger.info(f"Generating embeddings for tenant {tenant_id}")

        # Build NetworkX graph from Neo4j
        graph = self._build_networkx_graph(tenant_id)

        if len(graph.nodes) == 0:
            raise ValueError(f"No resources found for tenant {tenant_id}")

        logger.info(f"Built graph: {len(graph.nodes)} nodes, {len(graph.edges)} edges")

        # Generate node2vec embeddings
        embeddings = self._train_node2vec(graph)

        logger.info(f"Generated embeddings for {len(embeddings)} nodes")

        return embeddings

    def _build_networkx_graph(self, tenant_id: str) -> nx.Graph[str]:
        """Build NetworkX graph from Neo4j relationships.

        Extracts all Resource nodes and their relationships for the specified
        tenant. Uses undirected graph since node2vec works best with undirected.

        Args:
            tenant_id: Tenant ID to build graph for

        Returns:
            NetworkX undirected graph
        """
        query = """
        MATCH (source:Resource {tenant_id: $tenant_id})
        OPTIONAL MATCH (source)-[r]-(target:Resource {tenant_id: $tenant_id})
        WHERE type(r) IN [
            'CONTAINS', 'USES_IDENTITY', 'CONNECTED_TO', 'DEPENDS_ON',
            'USES_SUBNET', 'SECURED_BY', 'USES_SERVICE', 'MANAGES'
        ]
        RETURN source.id AS source_id, target.id AS target_id
        """

        graph = nx.Graph[str]()

        with self.driver.session() as session:
            result = session.run(query, tenant_id=tenant_id)

            for record in result:
                source_id = record["source_id"]
                target_id = record["target_id"]

                # Add nodes (will not duplicate if already exists)
                if source_id:
                    graph.add_node(source_id)

                # Add edge only if we have both source and target
                if source_id and target_id:
                    graph.add_edge(source_id, target_id)

        return graph

    def _train_node2vec(self, graph: nx.Graph[str]) -> Dict[str, np.ndarray]:
        """Train node2vec model and return embeddings.

        Args:
            graph: NetworkX graph to train on

        Returns:
            Dictionary mapping node IDs to embedding vectors
        """
        logger.info("Training node2vec model...")

        # Create node2vec model
        node2vec = Node2Vec(
            graph,
            dimensions=self.dimensions,
            walk_length=self.walk_length,
            num_walks=self.num_walks,
            workers=self.workers,
            p=self.p,
            q=self.q,
        )

        # Train model (using word2vec under the hood)
        model = node2vec.fit(window=10, min_count=1, batch_words=4)

        # Extract embeddings
        embeddings = {}
        for node_id in graph.nodes:
            # node2vec stores nodes as strings
            vector = model.wv[str(node_id)]
            embeddings[node_id] = vector

        logger.info("Node2vec training complete")

        return embeddings

    def get_node_importance_scores(
        self, embeddings: Dict[str, np.ndarray], graph: Optional[nx.Graph[str]] = None
    ) -> Dict[str, float]:
        """Calculate importance scores for nodes based on embeddings.

        Combines embedding magnitude (captures centrality) with optional
        degree centrality for hybrid importance scoring.

        Args:
            embeddings: Dictionary of node embeddings
            graph: Optional NetworkX graph for degree centrality calculation

        Returns:
            Dictionary mapping node IDs to importance scores [0, 1]
        """
        scores = {}

        # Calculate embedding magnitudes
        embedding_scores = {}
        for node_id, vector in embeddings.items():
            magnitude = float(np.linalg.norm(vector))
            embedding_scores[node_id] = magnitude

        # Normalize embedding scores to [0, 1]
        max_magnitude = max(embedding_scores.values()) if embedding_scores else 1.0
        normalized_embedding = {
            node_id: score / max_magnitude
            for node_id, score in embedding_scores.items()
        }

        # If graph provided, combine with degree centrality
        if graph:
            degree_centrality = nx.degree_centrality(graph)
            # Hybrid score: 70% embedding + 30% degree centrality
            for node_id in embeddings:
                emb_score = normalized_embedding.get(node_id, 0.0)
                deg_score = degree_centrality.get(node_id, 0.0)
                scores[node_id] = 0.7 * emb_score + 0.3 * deg_score
        else:
            # Use embedding scores only
            scores = normalized_embedding

        return scores
