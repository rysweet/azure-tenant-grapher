"""
Resource Comparator Service

Compares abstracted graph resources with target tenant scan results to classify
each resource for IaC generation. This module implements the core comparison logic
for determining which resources need to be created, imported, or updated.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from ..utils.session_manager import Neo4jSessionManager
from .target_scanner import TargetResource, TargetScanResult

logger = logging.getLogger(__name__)


class ResourceState(Enum):
    """State of resource in target vs. abstracted graph."""

    NEW = "new"  # Not in target, needs CREATE
    EXACT_MATCH = "exact_match"  # In target, properties match, needs IMPORT only
    DRIFTED = "drifted"  # In target, properties differ, needs IMPORT + resource block
    ORPHANED = "orphaned"  # In target but not in abstracted graph (report only)


@dataclass
class ResourceClassification:
    """Classification of a single resource."""

    abstracted_resource: Dict[str, Any]  # From graph
    target_resource: Optional[TargetResource]  # From target scan (None if not found)
    classification: ResourceState
    drift_details: Optional[Dict[str, Any]] = None  # Details if DRIFTED


@dataclass
class ComparisonResult:
    """Result of comparing abstracted graph with target scan."""

    classifications: List[ResourceClassification]
    summary: Dict[str, int]  # Counts per ResourceState


class ResourceComparator:
    """Compares abstracted graph resources with target scan results."""

    # Properties to ignore during comparison (read-only/metadata)
    IGNORED_PROPERTIES = {
        "id",
        "created_time",
        "updated_time",
        "provisioning_state",
        "provisioning_state_code",
        "resource_guid",
        "etag",
        "changed_time",
        "created_by",
        "changed_by",
        "unique_identifier",
    }

    def __init__(
        self,
        session_manager: Neo4jSessionManager,
        source_subscription_id: Optional[str] = None,
        target_subscription_id: Optional[str] = None,
    ):
        """
        Initialize with Neo4j session manager for graph queries.

        Args:
            session_manager: Neo4jSessionManager instance for database operations
            source_subscription_id: Source subscription ID for cross-tenant comparison
            target_subscription_id: Target subscription ID for cross-tenant comparison
        """
        self.session_manager = session_manager
        self.source_subscription_id = source_subscription_id
        self.target_subscription_id = target_subscription_id

    def compare_resources(
        self,
        abstracted_resources: List[Dict[str, Any]],
        target_scan: TargetScanResult,
    ) -> ComparisonResult:
        """
        Compare abstracted graph resources with target scan.

        This method performs the core comparison logic:
        1. For each abstracted resource, find its original Azure ID via SCAN_SOURCE_NODE
        2. Match against target scan resources
        3. Classify as NEW, EXACT_MATCH, or DRIFTED
        4. Detect ORPHANED resources in target but not in abstracted graph

        Args:
            abstracted_resources: Resources from abstracted graph
            target_scan: Result of target tenant scan

        Returns:
            ComparisonResult with classifications and summary

        Note:
            Never raises exceptions - all errors are logged and resources
            are classified as NEW (safe default) on errors.
        """
        logger.info(
            f"Starting resource comparison: {len(abstracted_resources)} abstracted "
            f"resources vs {len(target_scan.resources)} target resources"
        )

        classifications: List[ResourceClassification] = []
        matched_target_ids = set()  # Track which target resources we've matched

        # Build lookup map of target resources by ID (case-insensitive)
        target_resource_map = self._build_target_resource_map(target_scan.resources)

        # Process each abstracted resource
        for abstracted_resource in abstracted_resources:
            classification = self._classify_abstracted_resource(
                abstracted_resource, target_resource_map
            )
            classifications.append(classification)

            # Track matched target resources
            if classification.target_resource:
                # Bug #111: Ensure id is not None before calling .lower()
                if classification.target_resource.id:
                    matched_target_ids.add(
                        classification.target_resource.id.lower()
                    )  # Case-insensitive

        # Detect orphaned resources (in target but not in abstracted graph)
        orphaned_classifications = self._detect_orphaned_resources(
            target_scan.resources, matched_target_ids
        )
        classifications.extend(orphaned_classifications)

        # Generate summary
        summary = self._generate_summary(classifications)

        logger.info(
            f"Resource comparison complete: {summary[ResourceState.NEW.value]} new, "
            f"{summary[ResourceState.EXACT_MATCH.value]} exact matches, "
            f"{summary[ResourceState.DRIFTED.value]} drifted, "
            f"{summary[ResourceState.ORPHANED.value]} orphaned"
        )

        return ComparisonResult(classifications=classifications, summary=summary)

    def _build_target_resource_map(
        self, target_resources: List[TargetResource]
    ) -> Dict[str, TargetResource]:
        """
        Build lookup map of target resources by ID (case-insensitive).

        Args:
            target_resources: List of target resources

        Returns:
            Dictionary mapping lowercase resource ID to TargetResource
        """
        resource_map = {}
        for resource in target_resources:
            # Bug #111: Skip resources with None ID
            if not resource.id:
                logger.warning(
                    f"Target resource has no ID, skipping: {resource.type if hasattr(resource, 'type') else 'unknown'}"
                )
                continue

            key = resource.id.lower()  # Case-insensitive matching
            if key in resource_map:
                logger.warning(
                    f"Duplicate target resource ID found: {resource.id} "
                    "(keeping first occurrence)"
                )
            else:
                resource_map[key] = resource
        return resource_map

    def _classify_abstracted_resource(
        self,
        abstracted_resource: Dict[str, Any],
        target_resource_map: Dict[str, TargetResource],
    ) -> ResourceClassification:
        """
        Classify a single abstracted resource by comparing with target.

        Args:
            abstracted_resource: Resource from abstracted graph
            target_resource_map: Map of target resources by ID

        Returns:
            ResourceClassification for this resource
        """
        abstracted_id = abstracted_resource.get("id", "unknown")

        # Step 1: Get original Azure ID via SCAN_SOURCE_NODE or fallback to abstracted ID
        original_id = self._get_original_azure_id(abstracted_resource)

        # Bug #16 fix: If no original_id (SCAN_SOURCE_NODE missing), use abstracted ID
        # In cross-tenant mode, we'll normalize it anyway
        if not original_id:
            original_id = abstracted_resource.get("id")
            if not original_id:
                # No ID at all - classify as NEW (safe default)
                logger.debug(
                    f"No ID found for abstracted resource {abstracted_id}, "
                    "classifying as NEW"
                )
                return ResourceClassification(
                    abstracted_resource=abstracted_resource,
                    target_resource=None,
                    classification=ResourceState.NEW,
                )
            # Fallback: use abstracted ID with heuristic cleanup
            logger.warning(
                f"No SCAN_SOURCE_NODE found for {abstracted_id}, using heuristic-cleaned abstracted ID"
            )
            original_id = self._cleanup_abstracted_id_heuristics(original_id)

        # Step 2: Normalize ID for cross-tenant comparison (Bug #13 fix)
        # In cross-tenant mode, replace source subscription with target subscription
        normalized_id = self._normalize_resource_id_for_comparison(original_id)

        # Bug #111: Check if normalized_id is None before calling .lower()
        if not normalized_id:
            logger.warning(
                f"Normalized ID is None for resource {abstracted_id}, classifying as NEW"
            )
            return ResourceClassification(
                abstracted_resource=abstracted_resource,
                target_resource=None,
                classification=ResourceState.NEW,
            )

        # Step 3: Find in target scan (case-insensitive)
        target_resource = target_resource_map.get(normalized_id.lower())

        if not target_resource:
            # Resource not found in target - it's NEW
            logger.debug(
                f"Resource {abstracted_id} (original: {original_id}) not found in "
                "target, classifying as NEW"
            )
            return ResourceClassification(
                abstracted_resource=abstracted_resource,
                target_resource=None,
                classification=ResourceState.NEW,
            )

        # Step 3: Compare properties
        property_differences = self._compare_properties(
            abstracted_resource, target_resource
        )

        if not property_differences:
            # Properties match - EXACT_MATCH
            logger.debug(
                f"Resource {abstracted_id} matches target exactly, classifying as "
                "EXACT_MATCH"
            )
            return ResourceClassification(
                abstracted_resource=abstracted_resource,
                target_resource=target_resource,
                classification=ResourceState.EXACT_MATCH,
            )
        else:
            # Properties differ - DRIFTED
            logger.debug(
                f"Resource {abstracted_id} has {len(property_differences)} property "
                "differences, classifying as DRIFTED"
            )
            drift_details = {"property_differences": property_differences}
            return ResourceClassification(
                abstracted_resource=abstracted_resource,
                target_resource=target_resource,
                classification=ResourceState.DRIFTED,
                drift_details=drift_details,
            )

    def _cleanup_abstracted_id_heuristics(self, resource_id: str) -> str:
        """
        Apply heuristic cleanup to abstracted IDs for better matching.

        Handles common transformations applied during graph abstraction:
        - Remove hash suffixes (e.g., '_abc123')
        - Replace underscores with hyphens
        - Normalize to lowercase

        Args:
            resource_id: Abstracted resource ID

        Returns:
            Cleaned ID more likely to match real Azure ID
        """
        if not resource_id:
            return resource_id

        import re

        # Remove hash suffix (6+ alphanumeric characters after underscore)
        cleaned = re.sub(r"_[a-f0-9]{6,}$", "", resource_id, flags=re.IGNORECASE)

        # Replace underscores with hyphens (common transformation)
        cleaned = cleaned.replace("_", "-")

        # Normalize to lowercase
        cleaned = cleaned.lower()

        return cleaned

    def _get_original_azure_id(
        self, abstracted_resource: Dict[str, Any]
    ) -> Optional[str]:
        """
        Get original Azure ID by querying SCAN_SOURCE_NODE relationship.

        Args:
            abstracted_resource: Resource from abstracted graph

        Returns:
            Original Azure resource ID, or None if not found
        """
        abstracted_id = abstracted_resource.get("id")
        if not abstracted_id:
            logger.warning(
                f"Abstracted resource missing 'id' field: {abstracted_resource}"
            )
            return None

        # Check if resource already has original_id property (optimization)
        if "original_id" in abstracted_resource:
            original_id = abstracted_resource["original_id"]
            if original_id:
                logger.debug(
                    f"Using cached original_id for {abstracted_id}: {original_id}"
                )
                return original_id

        # Query Neo4j for SCAN_SOURCE_NODE relationship
        query = """
        MATCH (abs:Resource {id: $abstracted_id})
        MATCH (abs)-[:SCAN_SOURCE_NODE]->(orig:Resource:Original)
        RETURN orig.id AS original_id
        LIMIT 1
        """

        try:
            with self.session_manager.session() as session:
                result = session.run(query, {"abstracted_id": abstracted_id})
                record = result.single()

                if record and record.get("original_id"):
                    original_id = record["original_id"]
                    logger.debug(
                        f"Found original ID for {abstracted_id}: {original_id}"
                    )
                    return original_id
                else:
                    logger.debug(
                        f"No SCAN_SOURCE_NODE relationship found for {abstracted_id}"
                    )
                    return None

        except Exception as e:
            logger.warning(
                f"Error querying SCAN_SOURCE_NODE for {abstracted_id}: {e}",
                exc_info=True,
            )
            return None

    def _normalize_resource_id_for_comparison(self, resource_id: str) -> str:
        """
        Normalize resource ID for cross-tenant comparison.

        In cross-tenant mode, replaces source subscription ID with target subscription ID
        so that resources can be matched even when deployed to different subscriptions.

        Args:
            resource_id: Original Azure resource ID (may contain source subscription)

        Returns:
            Normalized ID with target subscription (if cross-tenant) or original ID

        Example:
            Input:  /subscriptions/SOURCE_SUB/resourceGroups/test-rg/providers/...
            Output: /subscriptions/TARGET_SUB/resourceGroups/test-rg/providers/...
        """
        # Only normalize if both source and target subscriptions are configured
        if not self.source_subscription_id or not self.target_subscription_id:
            return resource_id

        # Only normalize if source subscription is in the ID
        if f"/subscriptions/{self.source_subscription_id}/" not in resource_id:
            return resource_id

        # Replace source subscription with target subscription
        normalized_id = resource_id.replace(
            f"/subscriptions/{self.source_subscription_id}/",
            f"/subscriptions/{self.target_subscription_id}/",
        )

        logger.debug(
            f"Normalized resource ID for cross-tenant comparison: "
            f"{resource_id[:80]}... -> {normalized_id[:80]}..."
        )

        return normalized_id

    def _compare_properties(
        self, abstracted_resource: Dict[str, Any], target_resource: TargetResource
    ) -> List[Dict[str, Any]]:
        """
        Compare properties between abstracted and target resources.

        Args:
            abstracted_resource: Resource from abstracted graph
            target_resource: Resource from target scan

        Returns:
            List of property differences, empty list if all match
        """
        differences = []

        # Compare name (must match exactly)
        abs_name = abstracted_resource.get("name", "")
        target_name = target_resource.name
        if abs_name != target_name:
            differences.append(
                {
                    "property": "name",
                    "expected": abs_name,
                    "actual": target_name,
                }
            )

        # Compare location (case-insensitive)
        # Bug #111: Ensure abstracted location is not None before calling .lower()
        abs_location = (abstracted_resource.get("location") or "").lower()
        # Bug #111: Ensure location is not None before calling .lower()
        target_location = (target_resource.location or "").lower()
        if abs_location and target_location and abs_location != target_location:
            differences.append(
                {
                    "property": "location",
                    "expected": abstracted_resource.get("location", ""),
                    "actual": target_resource.location,
                }
            )

        # Compare tags (keys and values)
        abs_tags = abstracted_resource.get("tags", {})
        target_tags = target_resource.tags or {}

        # Ensure both are dicts (convert from Any to dict if needed)
        if not isinstance(abs_tags, dict):
            abs_tags = {}

        # Check for tag differences
        tag_differences = self._compare_tags(abs_tags, target_tags)
        differences.extend(tag_differences)

        return differences

    def _compare_tags(
        self, abs_tags: Dict[str, Any], target_tags: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Compare tag dictionaries and return differences.

        Args:
            abs_tags: Tags from abstracted resource
            target_tags: Tags from target resource

        Returns:
            List of tag differences
        """
        differences = []

        # Find tags in abstracted but missing or different in target
        for key, abs_value in abs_tags.items():
            target_value = target_tags.get(key)
            if target_value is None:
                differences.append(
                    {
                        "property": f"tags.{key}",
                        "expected": abs_value,
                        "actual": None,
                    }
                )
            elif str(abs_value) != str(target_value):
                differences.append(
                    {
                        "property": f"tags.{key}",
                        "expected": abs_value,
                        "actual": target_value,
                    }
                )

        # Find tags in target but missing in abstracted
        for key, target_value in target_tags.items():
            if key not in abs_tags:
                differences.append(
                    {
                        "property": f"tags.{key}",
                        "expected": None,
                        "actual": target_value,
                    }
                )

        return differences

    def _detect_orphaned_resources(
        self, target_resources: List[TargetResource], matched_target_ids: set[str]
    ) -> List[ResourceClassification]:
        """
        Detect orphaned resources (in target but not in abstracted graph).

        Args:
            target_resources: All resources from target scan
            matched_target_ids: Set of target resource IDs that were matched

        Returns:
            List of ResourceClassification for orphaned resources
        """
        orphaned_classifications = []

        for target_resource in target_resources:
            # Bug #111: Skip resources with None ID
            if not target_resource.id:
                logger.warning(
                    f"Target resource has no ID in orphan detection, skipping: "
                    f"{target_resource.type if hasattr(target_resource, 'type') else 'unknown'}"
                )
                continue

            target_id_lower = target_resource.id.lower()
            if target_id_lower not in matched_target_ids:
                logger.debug(
                    f"Resource {target_resource.id} found in target but not in "
                    "abstracted graph, classifying as ORPHANED"
                )

                # Create a pseudo-abstracted resource for consistency
                pseudo_abstracted = {
                    "id": target_resource.id,
                    "name": target_resource.name,
                    "type": target_resource.type,
                    "location": target_resource.location,
                    "tags": target_resource.tags,
                }

                orphaned_classifications.append(
                    ResourceClassification(
                        abstracted_resource=pseudo_abstracted,
                        target_resource=target_resource,
                        classification=ResourceState.ORPHANED,
                    )
                )

        logger.info(str(f"Detected {len(orphaned_classifications)} orphaned resources"))
        return orphaned_classifications

    def _generate_summary(
        self, classifications: List[ResourceClassification]
    ) -> Dict[str, int]:
        """
        Generate summary statistics from classifications.

        Args:
            classifications: List of resource classifications

        Returns:
            Dictionary mapping ResourceState value to count
        """
        summary = {state.value: 0 for state in ResourceState}

        for classification in classifications:
            state_value = classification.classification.value
            summary[state_value] += 1

        return summary
