"""Existing resource filter for IaC generation.

This module filters out resources that already exist in the target subscription,
preventing AlreadyExists errors (67 errors).

Leverages the existing ConflictDetector to identify existing resources.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from ..conflict_detector import ConflictDetector, ConflictType

logger = logging.getLogger(__name__)


@dataclass
class ExistingResourceFilterResult:
    """Result of existing resource filtering operation."""

    resources_before: int
    resources_after: int
    filtered_resources: List[Dict[str, Any]] = field(default_factory=list)
    existing_resources: Set[str] = field(default_factory=set)
    filter_reasons: Dict[str, str] = field(default_factory=dict)

    @property
    def filtered_count(self) -> int:
        """Number of resources filtered out."""
        return self.resources_before - self.resources_after


class ExistingResourceFilter:
    """Filter resources that already exist in target subscription.

    Uses ConflictDetector to identify existing resources before IaC generation.
    """

    def __init__(
        self,
        target_subscription_id: Optional[str] = None,
        enable_async_check: bool = True,
    ) -> None:
        """Initialize existing resource filter.

        Args:
            target_subscription_id: Target subscription ID for deployment
            enable_async_check: Whether to perform async Azure API checks
        """
        self.target_subscription_id = target_subscription_id
        self.enable_async_check = enable_async_check
        self.conflict_detector: Optional[ConflictDetector] = None

        if enable_async_check and target_subscription_id:
            self.conflict_detector = ConflictDetector(
                target_subscription_id=target_subscription_id
            )

        logger.info(
            f"ExistingResourceFilter initialized: "
            f"target={target_subscription_id}, async_check={enable_async_check}"
        )

    def filter_resources(self, resources: List[Dict[str, Any]]) -> ExistingResourceFilterResult:
        """Filter resources that already exist in target subscription.

        Args:
            resources: List of resources to filter

        Returns:
            ExistingResourceFilterResult with filtered resources and statistics
        """
        if not self.enable_async_check:
            logger.info("Async check disabled, skipping existing resource filter")
            return ExistingResourceFilterResult(
                resources_before=len(resources),
                resources_after=len(resources),
                filtered_resources=resources,
            )

        if not self.target_subscription_id:
            logger.warning("Target subscription not specified, skipping existing resource filter")
            return ExistingResourceFilterResult(
                resources_before=len(resources),
                resources_after=len(resources),
                filtered_resources=resources,
            )

        # Run async detection
        try:
            existing_resource_ids = self._detect_existing_resources(resources)
        except Exception as e:
            logger.error(f"Error detecting existing resources: {e}")
            logger.warning("Proceeding without existing resource filter")
            return ExistingResourceFilterResult(
                resources_before=len(resources),
                resources_after=len(resources),
                filtered_resources=resources,
            )

        # Filter resources
        filtered_resources = []
        filter_reasons = {}
        resources_before = len(resources)

        for resource in resources:
            resource_id = resource.get("id", "")
            resource_name = resource.get("name", "")

            if resource_id in existing_resource_ids:
                filter_reasons[resource_id] = f"Resource already exists: {resource_name}"
                logger.debug(f"Filtering existing resource: {resource_id}")
            else:
                filtered_resources.append(resource)

        resources_after = len(filtered_resources)

        logger.info(
            f"Existing resource filter: {resources_before} -> {resources_after} "
            f"(filtered {resources_before - resources_after} existing resources)"
        )

        return ExistingResourceFilterResult(
            resources_before=resources_before,
            resources_after=resources_after,
            filtered_resources=filtered_resources,
            existing_resources=existing_resource_ids,
            filter_reasons=filter_reasons,
        )

    def _detect_existing_resources(self, resources: List[Dict[str, Any]]) -> Set[str]:
        """Detect existing resources using ConflictDetector.

        Args:
            resources: List of resources to check

        Returns:
            Set of resource names that already exist (used for matching against resource IDs)
        """
        if not self.conflict_detector:
            return set()

        # Run async detection
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        conflicts = loop.run_until_complete(
            self.conflict_detector.detect_conflicts(resources)
        )

        # Extract existing resource names and build a set of resource IDs to filter
        existing_resource_ids = set()

        for conflict in conflicts:
            if conflict.conflict_type == ConflictType.EXISTING_RESOURCE:
                # Match by resource name and type
                for resource in resources:
                    if (resource.get("name") == conflict.resource_name and
                        resource.get("type") == conflict.resource_type):
                        existing_resource_ids.add(resource.get("id", ""))

        logger.info(f"Detected {len(existing_resource_ids)} existing resources")

        return existing_resource_ids

    def get_filter_summary(self, result: ExistingResourceFilterResult) -> str:
        """Generate human-readable summary of filter results.

        Args:
            result: Filter result to summarize

        Returns:
            Formatted summary string
        """
        summary = [
            "Existing Resource Filter Summary",
            "=" * 50,
            f"Resources before: {result.resources_before}",
            f"Resources after: {result.resources_after}",
            f"Filtered out: {result.filtered_count}",
            "",
        ]

        if result.existing_resources:
            summary.append(f"Existing Resources ({len(result.existing_resources)}):")
            for resource_id in sorted(result.existing_resources):
                reason = result.filter_reasons.get(resource_id, "Already exists")
                summary.append(f"  - {resource_id}")
                summary.append(f"    Reason: {reason}")

        return "\n".join(summary)
