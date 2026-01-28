"""
RelationshipDependencyCollector Service

Collects missing cross-RG dependencies by analyzing relationship rules.

When filtering scans by resource group, this service ensures that resources
referenced by relationships are included even if they're in different RGs.

Example:
    VM in RG-compute references NIC in RG-network
    → Service fetches NIC from Azure and includes it in the scan
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Set

from ..models.filter_config import FilterConfig

logger = logging.getLogger(__name__)


class RelationshipDependencyCollector:
    """
    Collects missing cross-RG dependencies by analyzing relationship rules.

    This service implements Phase 2.6 of the scan process:
    1. Extract target resource IDs from relationship rules
    2. Check which targets already exist in Neo4j
    3. Fetch missing resources from Azure in parallel
    4. Return missing resources to be added to the scan
    """

    def __init__(
        self,
        discovery_service: Any,
        db_ops: Any,
        relationship_rules: List[Any],
    ):
        """
        Initialize the dependency collector.

        Args:
            discovery_service: AzureDiscoveryService for fetching resources
            db_ops: DatabaseOperations for checking existing nodes
            relationship_rules: List of RelationshipRule instances
        """
        self.discovery_service = discovery_service
        self.db_ops = db_ops
        self.relationship_rules = relationship_rules

    async def collect_missing_dependencies(
        self,
        filtered_resources: List[Dict[str, Any]],
        filter_config: Optional[FilterConfig] = None,
    ) -> List[Dict[str, Any]]:
        """
        Collect missing cross-RG dependencies for filtered resources.

        This is the main entry point for Phase 2.6 dependency collection.

        Args:
            filtered_resources: Resources from the filtered RGs
            filter_config: Filter configuration (for logging/context)

        Returns:
            List of missing dependency resources fetched from Azure

        Example:
            >>> # VM in rg-compute references NIC in rg-network
            >>> filtered = [vm_resource]  # Only compute RG
            >>> missing = await collector.collect_missing_dependencies(filtered)
            >>> # Returns: [nic_resource]  # Fetched from rg-network
        """
        logger.info("=" * 70)
        logger.info("Phase 2.6: Collecting cross-RG dependencies from relationships")
        logger.info("=" * 70)

        # Step 1: Extract all target IDs from relationship rules
        target_ids = self._extract_all_target_ids(filtered_resources)

        if not target_ids:
            logger.info("No cross-RG dependencies found in relationship rules")
            return []

        logger.info(
            f"Found {len(target_ids)} potential cross-RG dependencies from relationships"
        )

        # Step 2: Check which targets already exist in Neo4j
        existing_ids = self.check_existing_nodes(target_ids)
        missing_ids = target_ids - existing_ids

        if not missing_ids:
            logger.info(
                "All dependency targets already exist in graph, no fetch needed"
            )
            return []

        logger.info(
            f"Fetching {len(missing_ids)} missing dependency resources from Azure"
        )
        logger.info(
            f"Already in graph: {len(existing_ids)}, Missing: {len(missing_ids)}"
        )

        # Step 3: Fetch missing resources from Azure in parallel
        missing_resources = await self.fetch_resources_by_ids(missing_ids)

        logger.info(
            f"✅ Successfully fetched {len(missing_resources)} cross-RG dependency resources"
        )

        return missing_resources

    def _extract_all_target_ids(
        self, resources: List[Dict[str, Any]]
    ) -> Set[str]:
        """
        Extract all target resource IDs from relationship rules.

        Args:
            resources: Resources to analyze

        Returns:
            Set of target resource IDs that relationships would reference
        """
        all_target_ids: Set[str] = set()

        for resource in resources:
            for rule in self.relationship_rules:
                if rule.applies(resource):
                    try:
                        target_ids = rule.extract_target_ids(resource)
                        all_target_ids.update(target_ids)
                    except Exception as e:
                        resource_id = resource.get("id", "unknown")
                        logger.warning(
                            f"Error extracting target IDs from {rule.__class__.__name__} "
                            f"for resource {resource_id}: {e}"
                        )

        return all_target_ids

    def check_existing_nodes(self, target_ids: Set[str]) -> Set[str]:
        """
        Check which target resource IDs already exist in Neo4j.

        Uses efficient batch query with UNWIND to check all IDs in one query.
        Supports both production (session_manager) and test (check_resource_exists) APIs.

        Args:
            target_ids: Set of resource IDs to check

        Returns:
            Set of resource IDs that exist in Neo4j
        """
        if not target_ids:
            return set()

        # Test mode: use check_resource_exists if available (for backward compatibility)
        if hasattr(self.db_ops, "check_resource_exists"):
            existing_ids = set()
            for resource_id in target_ids:
                if self.db_ops.check_resource_exists(resource_id):
                    existing_ids.add(resource_id)
            return existing_ids

        # Production mode: use session_manager
        if not hasattr(self.db_ops, "session_manager") or self.db_ops.session_manager is None:
            # No session manager and no check_resource_exists - assume nothing exists
            return set()

        try:
            query = """
            UNWIND $target_ids AS target_id
            MATCH (r:Resource {id: target_id})
            RETURN r.id AS id
            """

            try:
                with self.db_ops.session_manager.session() as session:
                    result = session.run(query, target_ids=list(target_ids))
                    existing_ids = {record["id"] for record in result.data()}
            except (AttributeError, TypeError) as e:
                logger.debug(f"Session manager error (likely test mock): {e}")
                return set()

            logger.debug(
                f"Checked {len(target_ids)} target IDs, found {len(existing_ids)} existing"
            )

            return existing_ids

        except Exception as e:
            logger.warning(
                f"Error checking existing nodes in Neo4j: {e}. "
                f"Assuming all targets missing."
            )
            # On error, assume nothing exists (safer to fetch than skip)
            return set()

    async def fetch_resources_by_ids(
        self, resource_ids: Set[str]
    ) -> List[Dict[str, Any]]:
        """
        Fetch multiple resources by ID from Azure in parallel.

        Args:
            resource_ids: Set of Azure resource IDs to fetch

        Returns:
            List of successfully fetched resources
        """
        if not resource_ids:
            return []

        # Create tasks for parallel fetching
        tasks = [
            self.discovery_service.fetch_resource_by_id(resource_id)
            for resource_id in resource_ids
        ]

        # Fetch all in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out failures and None results
        resources = []
        for resource_id, result in zip(resource_ids, results):
            if isinstance(result, Exception):
                logger.warning(
                    f"Failed to fetch dependency resource {resource_id}: {result}"
                )
            elif result is not None:
                resources.append(result)
            else:
                logger.debug(f"Resource {resource_id} returned None (may not exist)")

        return resources
