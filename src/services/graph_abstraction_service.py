"""Graph abstraction service for creating representative tenant subsets.

This service orchestrates the graph abstraction workflow:
1. Sample nodes using stratified sampling
2. Create :SAMPLE_OF relationships in Neo4j
3. Return abstraction statistics
"""

import logging
from typing import Any, Dict

from neo4j import Driver

from src.services.graph_abstraction_sampler import StratifiedSampler
from src.services.graph_embedding_sampler import EmbeddingSampler

logger = logging.getLogger(__name__)


class GraphAbstractionService:
    """Service for creating abstracted graph subsets.

    Creates smaller, representative subsets of Azure tenant graphs while
    preserving resource type distribution and creating linkage relationships.
    Supports both uniform stratified sampling and embedding-based importance sampling.
    """

    def __init__(self, driver: Driver, method: str = "stratified"):
        """Initialize service with Neo4j driver.

        Args:
            driver: Neo4j database driver
            method: Sampling method - "stratified" (uniform) or "embedding" (importance-weighted)
        """
        self.driver = driver
        self.method = method

        if method == "embedding":
            self.sampler = EmbeddingSampler(driver)
        else:
            self.sampler = StratifiedSampler(driver)

    async def abstract_tenant_graph(
        self,
        tenant_id: str,
        sample_size: int,
        seed: int | None = None,
        clear_existing: bool = False,
    ) -> Dict[str, Any]:
        """Create abstracted graph subset.

        Args:
            tenant_id: Source tenant ID to abstract from
            sample_size: Target number of nodes in abstraction
            seed: Random seed for reproducibility (optional)
            clear_existing: Clear existing :SAMPLE_OF relationships first

        Returns:
            Dictionary with abstraction statistics including:
            - tenant_id: Source tenant ID
            - target_size: Requested sample size
            - actual_size: Actual nodes sampled
            - type_distribution: Resources per type

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

        # Perform stratified sampling
        sampled_ids = self.sampler.sample_by_type(
            tenant_id=tenant_id,
            sample_size=sample_size,
            total_resources=total_resources,
            seed=seed,
        )

        # Create :SAMPLE_OF relationships
        self._create_sample_relationships(tenant_id, sampled_ids)

        # Calculate statistics
        actual_size = sum(len(ids) for ids in sampled_ids.values())
        type_distribution = {
            resource_type: len(ids) for resource_type, ids in sampled_ids.items()
        }

        logger.info(f"Abstraction complete: {actual_size} nodes sampled")

        return {
            "tenant_id": tenant_id,
            "target_size": sample_size,
            "actual_size": actual_size,
            "type_distribution": type_distribution,
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
                logger.info(f"Cleared {deleted} existing :SAMPLE_OF relationships")

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
            logger.info(f"Created {created} :SAMPLE_OF relationships")
