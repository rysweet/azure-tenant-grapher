"""Importance-weighted sampling using graph embeddings.

This module extends stratified sampling with embedding-based importance
weighting to preserve hub and bridge nodes in graph abstractions. It uses
node2vec embeddings to identify structurally important nodes and biases
sampling towards them while maintaining resource type distribution.
"""

from __future__ import annotations

import logging
import random
from typing import Dict, List

import networkx as nx
import numpy as np
from neo4j import Driver

from src.services.graph_abstraction_sampler import StratifiedSampler
from src.services.graph_embedding_cache import GraphEmbeddingCache
from src.services.graph_embedding_generator import GraphEmbeddingGenerator

logger = logging.getLogger(__name__)


class EmbeddingSampler(StratifiedSampler):
    """Importance-weighted stratified sampling using node embeddings.

    Extends StratifiedSampler with embedding-based importance scores that
    bias sampling towards hub and bridge nodes while preserving resource
    type distribution. Falls back to uniform sampling on errors.
    """

    def __init__(
        self,
        driver: Driver,
        dimensions: int = 64,
        walk_length: int = 30,
        num_walks: int = 200,
        importance_weight: float = 0.7,
        use_cache: bool = True,
        cache_dir: str = ".embeddings_cache",
    ):
        """Initialize embedding-based sampler.

        Args:
            driver: Neo4j database driver
            dimensions: Embedding vector dimensions (default: 64)
            walk_length: Random walk length (default: 30)
            num_walks: Number of walks per node (default: 200)
            importance_weight: Weight for importance sampling [0, 1]
                             0 = uniform, 1 = pure importance (default: 0.7)
            use_cache: Whether to use cached embeddings (default: True)
            cache_dir: Directory for embedding cache (default: .embeddings_cache)
        """
        super().__init__(driver)
        self.dimensions = dimensions
        self.walk_length = walk_length
        self.num_walks = num_walks
        self.importance_weight = importance_weight
        self.use_cache = use_cache

        # Initialize components
        self.generator = GraphEmbeddingGenerator(
            driver=driver,
            dimensions=dimensions,
            walk_length=walk_length,
            num_walks=num_walks,
        )
        self.cache = GraphEmbeddingCache(cache_dir=cache_dir)

        # State
        self.embeddings: Dict[str, np.ndarray] = {}
        self.importance_scores: Dict[str, float] = {}
        self.graph: nx.Graph[str] | None = None

    def sample_by_type(
        self,
        tenant_id: str,
        sample_size: int,
        total_resources: int,
        seed: int | None = None,
    ) -> Dict[str, List[str]]:
        """Sample node IDs using importance-weighted stratified sampling.

        Generates embeddings (or loads from cache), calculates importance
        scores, and performs weighted sampling within each resource type
        stratum. Falls back to uniform sampling on errors.

        Args:
            tenant_id: Source tenant ID to sample from
            sample_size: Target number of nodes to sample
            total_resources: Total number of resources in source graph
            seed: Random seed for reproducibility (optional)

        Returns:
            Dictionary mapping resource type to list of sampled node IDs
        """
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

        # Try to load or generate embeddings
        try:
            self._load_or_generate_embeddings(tenant_id)
        except Exception as e:
            logger.warning(
                f"Embedding generation failed: {e}. Falling back to uniform sampling"
            )
            return super().sample_by_type(tenant_id, sample_size, total_resources, seed)

        # Get resource type distribution
        type_counts = self._get_type_distribution(tenant_id)

        if not type_counts:
            raise ValueError(f"No resources found for tenant {tenant_id}")

        # Calculate per-type quotas (same as parent class)
        quotas = self._calculate_quotas(type_counts, sample_size)

        # Perform importance-weighted sampling per type
        sampled_ids = {}
        for resource_type, quota in quotas.items():
            try:
                node_ids = self._sample_type_weighted(tenant_id, resource_type, quota)
                sampled_ids[resource_type] = node_ids
                logger.info(
                    f"Sampled {len(node_ids)} of {type_counts[resource_type]} "
                    f"{resource_type} (weighted)"
                )
            except Exception as e:
                logger.warning(
                    f"Weighted sampling failed for {resource_type}: {e}. "
                    "Using uniform sampling"
                )
                node_ids = self._sample_type(tenant_id, resource_type, quota)
                sampled_ids[resource_type] = node_ids

        return sampled_ids

    def _load_or_generate_embeddings(self, tenant_id: str) -> None:
        """Load embeddings from cache or generate new ones.

        Args:
            tenant_id: Tenant ID to load/generate embeddings for
        """
        # Try cache first if enabled
        if self.use_cache:
            cached_embeddings = self.cache.get(
                tenant_id=tenant_id,
                dimensions=self.dimensions,
                walk_length=self.walk_length,
                num_walks=self.num_walks,
            )

            if cached_embeddings:
                logger.info(str(f"Using cached embeddings for tenant {tenant_id}"))
                self.embeddings = cached_embeddings
                self._calculate_importance_scores()
                return

        # Generate new embeddings
        logger.info(str(f"Generating new embeddings for tenant {tenant_id}"))
        self.embeddings = self.generator.generate_embeddings(
            tenant_id=tenant_id, use_cache=False
        )

        # Cache for future use
        if self.use_cache:
            self.cache.put(
                tenant_id=tenant_id,
                embeddings=self.embeddings,
                dimensions=self.dimensions,
                walk_length=self.walk_length,
                num_walks=self.num_walks,
            )

        # Calculate importance scores
        self._calculate_importance_scores()

    def _calculate_importance_scores(self) -> None:
        """Calculate importance scores from embeddings.

        Uses embedding magnitude combined with degree centrality to identify
        hub and bridge nodes.
        """
        if not self.embeddings:
            logger.warning("No embeddings available for importance calculation")
            return

        # Build graph for degree centrality (if not already built)
        if not self.graph:
            # Get tenant_id from first embedding key (hacky but works)
            # In production, pass tenant_id explicitly
            logger.debug("Building graph for degree centrality calculation")
            self.graph = nx.Graph[str]()
            # Add nodes from embeddings
            for node_id in self.embeddings:
                self.graph.add_node(node_id)

        # Calculate importance scores
        self.importance_scores = self.generator.get_node_importance_scores(
            embeddings=self.embeddings, graph=self.graph
        )

        logger.info(
            f"Calculated importance scores for {len(self.importance_scores)} nodes"
        )

    def _sample_type_weighted(
        self, tenant_id: str, resource_type: str, quota: int
    ) -> List[str]:
        """Sample nodes for a resource type using importance weighting.

        Combines importance scores with uniform distribution based on
        importance_weight parameter. Higher importance nodes have higher
        probability of selection.

        Args:
            tenant_id: Tenant ID
            resource_type: Resource type to sample
            quota: Number of nodes to sample

        Returns:
            List of sampled node IDs
        """
        # Get all node IDs for this type
        query = """
        MATCH (n:Resource {tenant_id: $tenant_id, type: $resource_type})
        RETURN n.id AS node_id
        """

        with self.driver.session() as session:
            result = session.run(
                query, tenant_id=tenant_id, resource_type=resource_type
            )
            all_ids = [record["node_id"] for record in result]

        if not all_ids:
            return []

        # Build probability distribution
        probabilities = self._compute_sampling_probabilities(all_ids)

        # Sample with replacement to handle edge cases, then deduplicate
        sample_count = min(quota, len(all_ids))
        sampled = np.random.choice(
            all_ids,
            size=min(sample_count * 2, len(all_ids)),  # Oversample for deduplication
            replace=True,
            p=probabilities,
        )

        # Deduplicate and trim to quota
        unique_sampled = []
        seen = set()
        for node_id in sampled:
            if node_id not in seen:
                unique_sampled.append(node_id)
                seen.add(node_id)
            if len(unique_sampled) >= sample_count:
                break

        # If we didn't get enough unique samples, fill with remaining nodes
        if len(unique_sampled) < sample_count:
            remaining = [nid for nid in all_ids if nid not in seen]
            additional_needed = sample_count - len(unique_sampled)
            additional = random.sample(
                remaining, min(additional_needed, len(remaining))
            )
            unique_sampled.extend(additional)

        return unique_sampled[:sample_count]

    def _compute_sampling_probabilities(self, node_ids: List[str]) -> List[float]:
        """Compute sampling probability for each node.

        Blends uniform distribution with importance-based distribution
        according to importance_weight parameter.

        Args:
            node_ids: List of node IDs to compute probabilities for

        Returns:
            List of probabilities (same length as node_ids, sums to 1.0)
        """
        n = len(node_ids)
        uniform_prob = 1.0 / n

        # Get importance scores for these nodes
        scores = []
        for node_id in node_ids:
            score = self.importance_scores.get(node_id, 0.0)
            scores.append(score)

        # Normalize importance scores to probabilities
        total_score = sum(scores) if sum(scores) > 0 else 1.0
        importance_probs = [score / total_score for score in scores]

        # Blend uniform and importance-based probabilities
        blended_probs = [
            (1 - self.importance_weight) * uniform_prob
            + self.importance_weight * imp_prob
            for imp_prob in importance_probs
        ]

        # Ensure probabilities sum to 1.0 (handle floating point errors)
        total_prob = sum(blended_probs)
        if total_prob > 0:
            blended_probs = [p / total_prob for p in blended_probs]
        else:
            # Fallback to uniform if something went wrong
            blended_probs = [uniform_prob] * n

        return blended_probs

    def get_embedding_stats(self) -> Dict:
        """Get statistics about current embeddings.

        Returns:
            Dictionary with embedding statistics
        """
        if not self.embeddings:
            return {"status": "no embeddings loaded"}

        return {
            "status": "embeddings loaded",
            "num_nodes": len(self.embeddings),
            "dimensions": self.dimensions,
            "importance_scores_available": len(self.importance_scores),
            "avg_importance": (
                np.mean(list(self.importance_scores.values()))
                if self.importance_scores
                else 0.0
            ),
            "max_importance": (
                max(self.importance_scores.values()) if self.importance_scores else 0.0
            ),
            "min_importance": (
                min(self.importance_scores.values()) if self.importance_scores else 0.0
            ),
        }
