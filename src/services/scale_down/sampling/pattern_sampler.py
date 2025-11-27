"""
Pattern-Based Sampler for Azure Tenant Graph Sampling

This module implements pattern-based sampling using Cypher queries.
Pattern sampling selects nodes matching specific attributes.

Security Note:
Uses property whitelist and parameterized queries to prevent Cypher injection.
"""

import logging
from typing import Any, Callable, Dict, Optional, Set

import networkx as nx
from neo4j.exceptions import Neo4jError

from src.services.scale_down.sampling.base_sampler import BaseSampler
from src.utils.session_manager import Neo4jSessionManager

logger = logging.getLogger(__name__)

# Whitelist of allowed properties for pattern matching (security: prevent injection)
ALLOWED_PATTERN_PROPERTIES = {
    # Resource properties
    "type",
    "name",
    "location",
    "id",
    "tenant_id",
    "resource_group",
    "sku",
    "kind",
    "provisioning_state",
    # Tag properties (nested)
    "tags.environment",
    "tags.owner",
    "tags.cost_center",
    "tags.project",
    "tags.application",
    "tags.department",
    # Network properties
    "subnet_id",
    "vnet_id",
    "nsg_id",
    # Identity properties
    "identity_type",
    "principal_id",
    # Synthetic properties
    "synthetic",
    "scale_operation_id",
}


class PatternSampler(BaseSampler):
    """
    Pattern-based sampling using Cypher queries.

    Pattern-based sampling selects nodes matching specific attributes,
    enabling targeted sampling by resource type, tags, location, etc.

    Security:
    - Property whitelist prevents Cypher injection
    - Parameterized queries for all user input
    - Strict validation of criteria
    """

    def __init__(self, session_manager: Neo4jSessionManager) -> None:
        """
        Initialize the pattern sampler.

        Args:
            session_manager: Neo4j session manager for database operations
        """
        self.session_manager = session_manager
        self.logger = logging.getLogger(__name__)

    async def sample(
        self,
        graph: nx.DiGraph,
        target_count: int,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> Set[str]:
        """
        Sample graph using pattern matching.

        Note: This method signature is for compatibility with BaseSampler.
        For pattern sampling, use sample_by_criteria() instead.

        Args:
            graph: NetworkX graph (unused)
            target_count: Target number of nodes (unused)
            progress_callback: Optional progress callback

        Returns:
            Set[str]: Empty set (use sample_by_criteria instead)

        Raises:
            NotImplementedError: Pattern sampling requires criteria
        """
        raise NotImplementedError(
            "Pattern sampling requires criteria. "
            "Use sample_by_criteria(tenant_id, criteria) instead."
        )

    async def sample_by_criteria(
        self,
        tenant_id: str,
        criteria: Dict[str, Any],
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> Set[str]:
        """
        Sample graph based on pattern matching criteria.

        Pattern-based sampling selects nodes matching specific attributes,
        enabling targeted sampling by resource type, tags, location, etc.

        Args:
            tenant_id: Azure tenant ID to sample
            criteria: Matching criteria dictionary, e.g.:
                {
                    "type": "Microsoft.Compute/virtualMachines",
                    "tags.environment": "production",
                    "location": "eastus"
                }
            progress_callback: Optional progress callback

        Returns:
            Set[str]: Set of matching node IDs

        Raises:
            ValueError: If tenant not found or criteria invalid
            Exception: If query fails

        Example:
            >>> sampler = PatternSampler(session_manager)
            >>> criteria = {
            ...     "type": "Microsoft.Compute/virtualMachines",
            ...     "tags.environment": "production"
            ... }
            >>> node_ids = await sampler.sample_by_criteria(
            ...     "00000000-0000-0000-0000-000000000000",
            ...     criteria
            ... )
            >>> print(f"Found {len(node_ids)} matching nodes")
        """
        self.logger.info(
            f"Sampling by pattern for tenant {tenant_id[:8]}... "
            f"with {len(criteria)} criteria"
        )

        if not criteria:
            raise ValueError("Criteria cannot be empty")

        if len(criteria) > 20:
            raise ValueError("Too many criteria (max 20)")

        # Validate all property keys against whitelist
        for key in criteria.keys():
            if key not in ALLOWED_PATTERN_PROPERTIES:
                raise ValueError(
                    f"Invalid pattern property: {key}. "
                    f"Allowed properties: {sorted(ALLOWED_PATTERN_PROPERTIES)}"
                )

        # Build query with property accessor syntax for nested properties
        where_clauses = ["NOT r:Original", "r.tenant_id = $tenant_id"]
        params: Dict[str, Any] = {"tenant_id": tenant_id}

        for key, value in criteria.items():
            param_name = f"param_{key.replace('.', '_')}"

            # Use Cypher property accessor for nested properties
            # Since key is validated against whitelist, this is safe
            if "." in key:
                # For tags.environment, we need r.tags.environment
                parts = key.split(".")
                # Build nested property access safely
                property_ref = f"r.{parts[0]}.{parts[1]}"
            else:
                property_ref = f"r.{key}"

            where_clauses.append(f"{property_ref} = ${param_name}")
            params[param_name] = value

        where_clause = " AND ".join(where_clauses)

        query = f"""
        MATCH (r:Resource)
        WHERE {where_clause}
        RETURN r.id as id
        """

        self.logger.debug(f"Pattern matching with {len(criteria)} validated criteria")
        self.logger.debug(f"Cypher query: {query}")
        self.logger.debug(f"Query parameters: {params}")

        matching_ids: Set[str] = set()

        try:
            with self.session_manager.session() as session:
                result = session.run(query, params)

                for record in result:
                    matching_ids.add(record["id"])

                    if progress_callback and len(matching_ids) % 100 == 0:
                        progress_callback(
                            "Pattern matching", len(matching_ids), len(matching_ids)
                        )

            self.logger.info(
                f"Pattern matching completed: {len(matching_ids)} nodes matched"
            )

            # Add helpful message when no nodes match
            if len(matching_ids) == 0:
                self.logger.warning(
                    f"No resources found matching criteria: {criteria}. "
                    f"Check that resources with these properties exist in tenant {tenant_id}. "
                    f"For resource type matching, verify the 'type' property matches exactly "
                    f"(e.g., 'Microsoft.Network/virtualNetworks')."
                )

            return matching_ids

        except (Neo4jError, ValueError) as e:
            self.logger.exception(f"Pattern matching failed: {e}")
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error during pattern matching: {e}")
            raise
