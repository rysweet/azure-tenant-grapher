"""Cross-tenant resource filter for IaC generation.

This module filters out resources that reference the source subscription
when deploying to a different target subscription. This prevents
LinkedAuthorizationFailed errors (130 errors).

Key Concepts:
- Source Subscription: Where resources were discovered (tenant graph)
- Target Subscription: Where resources will be deployed (IaC generation)
- Cross-tenant references: Resources that reference source subscription IDs
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class FilterResult:
    """Result of filtering operation."""

    resources_before: int
    resources_after: int
    filtered_resources: List[Dict[str, Any]] = field(default_factory=list)
    filter_reasons: Dict[str, str] = field(default_factory=dict)

    @property
    def filtered_count(self) -> int:
        """Number of resources filtered out."""
        return self.resources_before - self.resources_after


class CrossTenantResourceFilter:
    """Filter resources that reference source subscription when deploying to target.

    Prevents LinkedAuthorizationFailed errors by removing:
    1. Role assignments referencing source subscription scope
    2. Policy assignments referencing source subscription
    3. Resources with explicit source subscription dependencies
    4. Diagnostic settings pointing to source subscription
    """

    # Resource types that commonly have cross-tenant references
    CROSS_TENANT_TYPES = {
        "Microsoft.Authorization/roleAssignments",
        "Microsoft.Authorization/policyAssignments",
        "Microsoft.Insights/diagnosticSettings",
        "Microsoft.Security/pricings",
    }

    def __init__(
        self,
        source_subscription_id: Optional[str] = None,
        target_subscription_id: Optional[str] = None,
    ) -> None:
        """Initialize cross-tenant filter.

        Args:
            source_subscription_id: Source subscription ID (where resources were discovered)
            target_subscription_id: Target subscription ID (where resources will be deployed)
        """
        self.source_subscription_id = source_subscription_id
        self.target_subscription_id = target_subscription_id

        # Normalize subscription IDs (remove /subscriptions/ prefix if present)
        if self.source_subscription_id:
            self.source_subscription_id = self._normalize_subscription_id(
                self.source_subscription_id
            )
        if self.target_subscription_id:
            self.target_subscription_id = self._normalize_subscription_id(
                self.target_subscription_id
            )

        logger.info(
            f"CrossTenantResourceFilter initialized: "
            f"source={self.source_subscription_id}, target={self.target_subscription_id}"
        )

    def filter_resources(self, resources: List[Dict[str, Any]]) -> FilterResult:
        """Filter resources that reference source subscription.

        Args:
            resources: List of resources to filter

        Returns:
            FilterResult with filtered resources and statistics
        """
        if not self.source_subscription_id or not self.target_subscription_id:
            logger.warning(
                "Source or target subscription not specified, skipping cross-tenant filter"
            )
            return FilterResult(
                resources_before=len(resources),
                resources_after=len(resources),
                filtered_resources=resources,
            )

        # Same subscription = no filtering needed
        if self.source_subscription_id == self.target_subscription_id:
            logger.info("Source and target subscriptions are the same, no filtering needed")
            return FilterResult(
                resources_before=len(resources),
                resources_after=len(resources),
                filtered_resources=resources,
            )

        filtered_resources = []
        filter_reasons = {}
        resources_before = len(resources)

        for resource in resources:
            should_filter, reason = self._should_filter_resource(resource)

            if should_filter:
                resource_id = resource.get("id", "unknown")
                filter_reasons[resource_id] = reason
                logger.debug(f"Filtering resource {resource_id}: {reason}")
            else:
                filtered_resources.append(resource)

        resources_after = len(filtered_resources)

        logger.info(
            f"Cross-tenant filter: {resources_before} -> {resources_after} "
            f"(filtered {resources_before - resources_after} resources)"
        )

        return FilterResult(
            resources_before=resources_before,
            resources_after=resources_after,
            filtered_resources=filtered_resources,
            filter_reasons=filter_reasons,
        )

    def _should_filter_resource(self, resource: Dict[str, Any]) -> tuple[bool, str]:
        """Check if resource should be filtered.

        Args:
            resource: Resource to check

        Returns:
            Tuple of (should_filter, reason)
        """
        resource_type = resource.get("type", "")
        resource_id = resource.get("id", "")

        # Check if resource type commonly has cross-tenant references
        if resource_type in self.CROSS_TENANT_TYPES:
            # Check role assignments
            if resource_type == "Microsoft.Authorization/roleAssignments":
                return self._check_role_assignment(resource)

            # Check policy assignments
            if resource_type == "Microsoft.Authorization/policyAssignments":
                return self._check_policy_assignment(resource)

            # Check diagnostic settings
            if resource_type == "Microsoft.Insights/diagnosticSettings":
                return self._check_diagnostic_settings(resource)

            # Filter security center pricings (subscription-level)
            if resource_type == "Microsoft.Security/pricings":
                return True, "Security Center pricing is subscription-scoped"

        # Check if resource ID contains source subscription
        if self._contains_source_subscription(resource_id):
            return True, "Resource ID references source subscription"

        # Check properties for source subscription references
        properties = resource.get("properties", {})
        if isinstance(properties, dict):
            properties_str = str(properties)
            if self.source_subscription_id in properties_str:
                return True, "Properties reference source subscription"

        return False, ""

    def _check_role_assignment(self, resource: Dict[str, Any]) -> tuple[bool, str]:
        """Check if role assignment should be filtered.

        Args:
            resource: Role assignment resource

        Returns:
            Tuple of (should_filter, reason)
        """
        resource_id = resource.get("id", "")
        properties = resource.get("properties", {})

        # Filter if scope references source subscription
        scope = properties.get("scope", "")
        if self._contains_source_subscription(scope):
            return True, f"Role assignment scope references source subscription: {scope}"

        # Filter if roleDefinitionId references source subscription
        role_def_id = properties.get("roleDefinitionId", "")
        if self._contains_source_subscription(role_def_id):
            return (
                True,
                f"Role definition references source subscription: {role_def_id}",
            )

        return False, ""

    def _check_policy_assignment(self, resource: Dict[str, Any]) -> tuple[bool, str]:
        """Check if policy assignment should be filtered.

        Args:
            resource: Policy assignment resource

        Returns:
            Tuple of (should_filter, reason)
        """
        properties = resource.get("properties", {})

        # Filter if policyDefinitionId references source subscription
        policy_def_id = properties.get("policyDefinitionId", "")
        if self._contains_source_subscription(policy_def_id):
            return (
                True,
                f"Policy definition references source subscription: {policy_def_id}",
            )

        return False, ""

    def _check_diagnostic_settings(self, resource: Dict[str, Any]) -> tuple[bool, str]:
        """Check if diagnostic settings should be filtered.

        Args:
            resource: Diagnostic settings resource

        Returns:
            Tuple of (should_filter, reason)
        """
        properties = resource.get("properties", {})

        # Filter if workspaceId references source subscription
        workspace_id = properties.get("workspaceId", "")
        if self._contains_source_subscription(workspace_id):
            return (
                True,
                f"Diagnostic settings workspace references source subscription: {workspace_id}",
            )

        # Filter if storageAccountId references source subscription
        storage_id = properties.get("storageAccountId", "")
        if self._contains_source_subscription(storage_id):
            return (
                True,
                f"Diagnostic settings storage references source subscription: {storage_id}",
            )

        # Filter if eventHubAuthorizationRuleId references source subscription
        event_hub_id = properties.get("eventHubAuthorizationRuleId", "")
        if self._contains_source_subscription(event_hub_id):
            return (
                True,
                f"Diagnostic settings event hub references source subscription: {event_hub_id}",
            )

        return False, ""

    def _contains_source_subscription(self, value: str) -> bool:
        """Check if value contains source subscription ID.

        Args:
            value: String value to check

        Returns:
            True if value contains source subscription ID
        """
        if not value or not self.source_subscription_id:
            return False

        # Normalize value
        normalized_value = self._normalize_subscription_id(value)

        # Check for exact match
        if self.source_subscription_id in normalized_value:
            return True

        # Check for subscription ID in resource ID format
        # e.g., /subscriptions/{source-sub-id}/...
        pattern = rf"/subscriptions/{re.escape(self.source_subscription_id)}(/|$)"
        if re.search(pattern, value, re.IGNORECASE):
            return True

        return False

    def _normalize_subscription_id(self, value: str) -> str:
        """Normalize subscription ID by removing common prefixes.

        Args:
            value: Subscription ID or resource ID

        Returns:
            Normalized subscription ID
        """
        # Remove /subscriptions/ prefix if present
        if "/subscriptions/" in value.lower():
            # Extract subscription ID from resource ID
            match = re.search(
                r"/subscriptions/([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})",
                value,
                re.IGNORECASE,
            )
            if match:
                return match.group(1).lower()

        return value.lower()

    def get_filter_summary(self, result: FilterResult) -> str:
        """Generate human-readable summary of filter results.

        Args:
            result: Filter result to summarize

        Returns:
            Formatted summary string
        """
        summary = [
            "Cross-Tenant Resource Filter Summary",
            "=" * 50,
            f"Resources before: {result.resources_before}",
            f"Resources after: {result.resources_after}",
            f"Filtered out: {result.filtered_count}",
            "",
        ]

        if result.filter_reasons:
            summary.append("Filtered Resources:")
            for resource_id, reason in result.filter_reasons.items():
                summary.append(f"  - {resource_id}")
                summary.append(f"    Reason: {reason}")

        return "\n".join(summary)
