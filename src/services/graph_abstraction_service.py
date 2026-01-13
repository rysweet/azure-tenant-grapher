"""Graph abstraction service for creating representative tenant subsets.

This service orchestrates the graph abstraction workflow:
1. Sample nodes using stratified sampling
2. (Optional) Augment with security pattern preservation
3. Create :SAMPLE_OF relationships in Neo4j
4. Return abstraction statistics
"""

import logging
from typing import Any, Dict, List, Optional

from neo4j import Driver

from src.services.graph_abstraction_sampler import StratifiedSampler
from src.services.graph_embedding_sampler import EmbeddingSampler
from src.services.security_preserving_sampler import (
    SecurityPatternRegistry,
    SecurityPreservingSampler,
)

logger = logging.getLogger(__name__)


class GraphAbstractionService:
    """Service for creating abstracted graph subsets.

    Creates smaller, representative subsets of Azure tenant graphs while
    preserving resource type distribution and (optionally) security patterns.
    Supports both uniform stratified sampling and embedding-based importance sampling.
    """

    def __init__(
        self,
        driver: Driver,
        method: str = "stratified",
        dimensions: int = 128,
        walk_length: int = 80,
        num_walks: int = 10,
        hub_weight: float = 2.0,
        bridge_weight: float = 2.0,
    ):
        """Initialize service with Neo4j driver.

        Args:
            driver: Neo4j database driver
            method: Sampling method - "stratified" (uniform) or "embedding" (importance-weighted)
            dimensions: Embedding dimensions for embedding method
            walk_length: Random walk length for embedding method
            num_walks: Number of walks per node for embedding method
            hub_weight: Weight multiplier for hub nodes in embedding method
            bridge_weight: Weight multiplier for bridge nodes in embedding method
        """
        self.driver = driver
        self.method = method

        # Initialize appropriate sampler based on method
        if method == "embedding":
            self.sampler = EmbeddingSampler(
                driver,
                dimensions=dimensions,
                walk_length=walk_length,
                num_walks=num_walks,
                hub_weight=hub_weight,
                bridge_weight=bridge_weight,
            )
        else:
            self.sampler = StratifiedSampler(driver)

        # Initialize security sampler (used optionally)
        self.security_sampler = SecurityPreservingSampler(
            driver, SecurityPatternRegistry()
        )

    async def abstract_tenant_graph(
        self,
        tenant_id: str,
        sample_size: int,
        seed: int | None = None,
        clear_existing: bool = False,
        preserve_security_patterns: bool = False,
        security_patterns: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create abstracted graph subset with optional security preservation.

        Args:
            tenant_id: Source tenant ID to abstract from
            sample_size: Target number of nodes in abstraction
            seed: Random seed for reproducibility (optional)
            clear_existing: Clear existing :SAMPLE_OF relationships first
            preserve_security_patterns: Enable security-aware sampling
            security_patterns: Pattern names to preserve (default: all HIGH)

        Returns:
            Dictionary with abstraction statistics including:
            - tenant_id: Source tenant ID
            - target_size: Requested sample size
            - base_sample_size: Base stratified sample size
            - actual_size: Final sample size (may be larger if security enabled)
            - type_distribution: Resources per type
            - security_metrics: Security pattern preservation stats (if enabled)

        Raises:
            ValueError: If tenant not found or parameters invalid
        """
        # Validate input
        if sample_size <= 0:
            raise ValueError(f"Sample size must be positive, got {sample_size}")

        if not tenant_id or not tenant_id.strip():
            raise ValueError("Tenant ID must be a non-empty string")

        # Get total resources for this tenant
        total_resources = self._get_resource_count(tenant_id)

        if total_resources == 0:
            raise ValueError(f"No resources found for tenant {tenant_id}")

        logger.info(
            f"Creating abstraction of {sample_size} nodes from "
            f"{total_resources} resources for tenant {tenant_id}"
        )

        # Clear existing abstraction if requested
        if clear_existing:
            self._clear_sample_of_relationships(tenant_id)

        # Phase 1: Base stratified sampling
        sampled_ids_dict = self.sampler.sample_by_type(
            tenant_id=tenant_id,
            sample_size=sample_size,
            total_resources=total_resources,
            seed=seed,
        )

        # Flatten to set of IDs
        base_sample_ids = set()
        for ids_list in sampled_ids_dict.values():
            base_sample_ids.update(ids_list)

        base_sample_size = len(base_sample_ids)

        # Phase 2: Security augmentation (optional)
        security_metrics = None
        if preserve_security_patterns:
            logger.info("Augmenting sample with security pattern preservation")
            security_result = self.security_sampler.augment_sample(
                tenant_id=tenant_id,
                base_sample_ids=base_sample_ids,
                patterns_to_preserve=security_patterns,
            )

            final_sample_ids = security_result["augmented_sample_ids"]
            security_metrics = {
                "patterns_preserved": security_result["preserved_patterns"],
                "coverage_percentages": security_result["coverage_metrics"],
                "nodes_added_for_security": security_result["added_node_count"],
            }
        else:
            final_sample_ids = base_sample_ids

        # Create :SAMPLE_OF relationships
        self._create_sample_relationships_from_set(tenant_id, final_sample_ids)

        # Calculate statistics
        actual_size = len(final_sample_ids)
        type_distribution = self._get_sample_type_distribution(
            tenant_id, final_sample_ids
        )

        logger.info(
            f"Abstraction complete: {actual_size} nodes "
            f"(base: {base_sample_size}, security: {actual_size - base_sample_size})"
        )

        return {
            "tenant_id": tenant_id,
            "target_size": sample_size,
            "base_sample_size": base_sample_size,
            "actual_size": actual_size,
            "type_distribution": type_distribution,
            "security_metrics": security_metrics,
        }

    def _get_resource_count(self, tenant_id: str) -> int:
        """Get total resource count for tenant.

        Args:
            tenant_id: Tenant ID to query

        Returns:
            Total number of resources
        """
        query = """
        MATCH (n:Resource {tenant_id: $tenant_id})
        WHERE n.type IS NOT NULL
        RETURN count(n) AS count
        """

        with self.driver.session() as session:
            result = session.run(query, tenant_id=tenant_id)
            record = result.single()
            return record["count"] if record else 0

    def _clear_sample_of_relationships(self, tenant_id: str) -> None:
        """Clear existing :SAMPLE_OF relationships for tenant.

        Args:
            tenant_id: Tenant ID to clear
        """
        query = """
        MATCH (sample:Resource)-[r:SAMPLE_OF]->(source:Resource)
        WHERE source.tenant_id = $tenant_id
        DELETE r
        """

        with self.driver.session() as session:
            result = session.run(query, tenant_id=tenant_id)
            deleted = result.consume().counters.relationships_deleted
            if deleted > 0:
                logger.info(str(f"Cleared {deleted} existing :SAMPLE_OF relationships"))

    def _create_sample_relationships(
        self, tenant_id: str, sampled_ids: Dict[str, list[str]]
    ) -> None:
        """Create :SAMPLE_OF relationships from sampled nodes to originals.

        Note: Uses MERGE which can create duplicates if called concurrently.
        Use --clear flag or run sequentially to avoid race conditions.

        Args:
            tenant_id: Tenant ID
            sampled_ids: Dictionary of resource type to list of node IDs
        """
        # Flatten sampled IDs
        all_sampled_ids = []
        for ids in sampled_ids.values():
            all_sampled_ids.extend(ids)

        query = """
        UNWIND $node_ids AS node_id
        MATCH (sample:Resource {id: node_id, tenant_id: $tenant_id})
        MATCH (source:Resource {id: node_id, tenant_id: $tenant_id})
        MERGE (sample)-[:SAMPLE_OF]->(source)
        """

        with self.driver.session() as session:
            result = session.run(query, node_ids=all_sampled_ids, tenant_id=tenant_id)
            created = result.consume().counters.relationships_created
            logger.info(str(f"Created {created} :SAMPLE_OF relationships"))

    def _create_sample_relationships_from_set(
        self, tenant_id: str, sample_ids: set[str]
    ) -> None:
        """Create :SAMPLE_OF relationships from set of node IDs.

        Args:
            tenant_id: Tenant ID
            sample_ids: Set of node IDs to create relationships for
        """
        query = """
        UNWIND $node_ids AS node_id
        MATCH (sample:Resource {id: node_id, tenant_id: $tenant_id})
        MATCH (source:Resource {id: node_id, tenant_id: $tenant_id})
        MERGE (sample)-[:SAMPLE_OF]->(source)
        """

        with self.driver.session() as session:
            result = session.run(query, node_ids=list(sample_ids), tenant_id=tenant_id)
            created = result.consume().counters.relationships_created
            logger.info(str(f"Created {created} :SAMPLE_OF relationships"))

    def _get_sample_type_distribution(
        self, tenant_id: str, sample_ids: set[str]
    ) -> Dict[str, int]:
        """Get resource type distribution for sampled nodes.

        Args:
            tenant_id: Tenant ID
            sample_ids: Set of sampled node IDs

        Returns:
            Dictionary mapping resource type to count
        """
        query = """
        UNWIND $node_ids AS node_id
        MATCH (n:Resource {id: node_id, tenant_id: $tenant_id})
        RETURN n.type AS resource_type, count(n) AS count
        """

        with self.driver.session() as session:
            result = session.run(query, node_ids=list(sample_ids), tenant_id=tenant_id)
            return {record["resource_type"]: record["count"] for record in result}
