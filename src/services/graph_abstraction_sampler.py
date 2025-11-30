"""Stratified sampling by Azure resource type for graph abstraction.

This module implements the core sampling algorithm that creates representative
subsets of Azure tenant graphs while preserving resource type distribution.
"""

import logging
import random
from typing import Dict, List

from neo4j import Driver

logger = logging.getLogger(__name__)


class StratifiedSampler:
    """Stratified sampling by resource type with distribution validation.

    Samples nodes from a Neo4j graph using proportional allocation across
    resource types to preserve the original distribution.
    """

    def __init__(self, driver: Driver):
        """Initialize sampler with Neo4j driver.

        Args:
            driver: Neo4j database driver
        """
        self.driver = driver

    def sample_by_type(
        self,
        tenant_id: str,
        sample_size: int,
        total_resources: int,
        seed: int | None = None,
    ) -> Dict[str, List[str]]:
        """Sample node IDs stratified by resource type.

        Args:
            tenant_id: Source tenant ID to sample from
            sample_size: Target number of nodes to sample
            total_resources: Total number of resources in source graph
            seed: Random seed for reproducibility (optional)

        Returns:
            Dictionary mapping resource type to list of sampled node IDs

        Raises:
            ValueError: If parameters are invalid
        """
        if sample_size > total_resources:
            logger.warning(
                f"Sample size {sample_size} > total resources {total_resources}, "
                "using all resources"
            )
            sample_size = total_resources

        # Set random seed for reproducibility
        if seed is not None:
            random.seed(seed)

        # Get resource type distribution
        type_counts = self._get_type_distribution(tenant_id)

        if not type_counts:
            raise ValueError(f"No resources found for tenant {tenant_id}")

        # Calculate per-type quotas
        quotas = self._calculate_quotas(type_counts, sample_size)

        # Validate quotas
        if not self._validate_distribution(type_counts, quotas):
            logger.warning("Quota distribution exceeds tolerance threshold")

        # Sample node IDs per type
        sampled_ids = {}
        for resource_type, quota in quotas.items():
            node_ids = self._sample_type(tenant_id, resource_type, quota)
            sampled_ids[resource_type] = node_ids
            logger.info(
                f"Sampled {len(node_ids)} of {type_counts[resource_type]} {resource_type}"
            )

        return sampled_ids

    def _get_type_distribution(self, tenant_id: str) -> Dict[str, int]:
        """Get resource type counts from Neo4j.

        Args:
            tenant_id: Tenant ID to query

        Returns:
            Dictionary mapping resource type to count
        """
        query = """
        MATCH (n:Resource {tenant_id: $tenant_id})
        WHERE n.type IS NOT NULL
        RETURN n.type AS resource_type, count(n) AS count
        ORDER BY count DESC
        """

        with self.driver.session() as session:
            result = session.run(query, tenant_id=tenant_id)
            return {record["resource_type"]: record["count"] for record in result}

    def _calculate_quotas(
        self, type_counts: Dict[str, int], sample_size: int
    ) -> Dict[str, int]:
        """Calculate per-type sampling quotas using proportional allocation.

        Args:
            type_counts: Resource type counts
            sample_size: Total nodes to sample

        Returns:
            Dictionary mapping resource type to quota
        """
        total_resources = sum(type_counts.values())
        quotas = {}
        remaining = sample_size

        # Phase 1: Proportional allocation with minimum 1
        for resource_type, count in type_counts.items():
            proportion = count / total_resources
            quota = max(1, int(proportion * sample_size))
            # Cap quota at available resources
            quota = min(quota, count)
            quotas[resource_type] = quota
            remaining -= quota

        # Phase 2: Distribute remainder to largest types
        if remaining > 0:
            # Sort types by count (descending)
            sorted_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)
            for resource_type, count in sorted_types:
                if remaining <= 0:
                    break
                # Only add if we haven't reached the type's limit
                if quotas[resource_type] < count:
                    quotas[resource_type] += 1
                    remaining -= 1

        # Phase 3: Handle over-allocation (if any)
        elif remaining < 0:
            # Remove from types with largest quotas first (preserves minimum 1 per type)
            sorted_quotas = sorted(quotas.items(), key=lambda x: x[1], reverse=True)
            for resource_type, quota in sorted_quotas:
                if remaining >= 0:
                    break
                if quota > 1:
                    reduction = min(quota - 1, abs(remaining))
                    quotas[resource_type] -= reduction
                    remaining += reduction

        return quotas

    def _validate_distribution(
        self, type_counts: Dict[str, int], sampled_counts: Dict[str, int]
    ) -> bool:
        """Validate sampled distribution matches source within tolerance.

        Args:
            type_counts: Original resource type counts
            sampled_counts: Sampled resource type quotas

        Returns:
            True if distribution valid, False otherwise
        """
        tolerance = 0.15  # ±15%
        buffer = 0.02  # Additional 2% buffer for small samples
        effective_tolerance = tolerance + buffer

        total_original = sum(type_counts.values())
        total_sampled = sum(sampled_counts.values())

        for resource_type in type_counts:
            original_pct = type_counts[resource_type] / total_original
            sampled_pct = sampled_counts.get(resource_type, 0) / total_sampled
            delta = abs(original_pct - sampled_pct)

            if delta > effective_tolerance:
                logger.warning(
                    f"Type {resource_type}: distribution delta {delta:.2%} "
                    f"exceeds tolerance {effective_tolerance:.2%}"
                )
                return False

        return True

    def _sample_type(self, tenant_id: str, resource_type: str, quota: int) -> List[str]:
        """Sample node IDs for a specific resource type.

        Args:
            tenant_id: Tenant ID
            resource_type: Resource type to sample
            quota: Number of nodes to sample

        Returns:
            List of sampled node IDs
        """
        query = """
        MATCH (n:Resource {tenant_id: $tenant_id, type: $resource_type})
        RETURN n.id AS node_id
        """

        with self.driver.session() as session:
            result = session.run(
                query, tenant_id=tenant_id, resource_type=resource_type
            )
            all_ids = [record["node_id"] for record in result]

        # Random sample (without replacement)
        sample_count = min(quota, len(all_ids))
        return random.sample(all_ids, sample_count)
