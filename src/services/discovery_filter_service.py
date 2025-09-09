"""Service for filtering Azure resources during discovery."""

import logging
from typing import Any, Dict, List, Optional

from src.config_manager import FilterConfig

logger = logging.getLogger(__name__)


class DiscoveryFilterService:
    """Service to filter subscriptions and resources based on configured criteria."""

    def __init__(self, config: Optional[FilterConfig] = None):
        """
        Initialize the discovery filter service.

        Args:
            config: FilterConfig with optional subscription IDs and resource group filter
        """
        self.config = config or FilterConfig()
        
        if self.config.has_filters():
            logger.info(
                f"Discovery filters configured - "
                f"Subscriptions: {len(self.config.subscription_ids) if self.config.subscription_ids else 'all'}, "
                f"Resource group filter: {self.config.resource_group_filter or 'none'}"
            )

    def is_subscription_included(self, subscription_id: str) -> bool:
        """
        Check if a subscription should be included based on filter config.
        
        Args:
            subscription_id: The subscription ID to check
            
        Returns:
            True if subscription should be included, False otherwise
        """
        # If subscription_ids is set, subscription must be in it
        if self.config.subscription_ids:
            return subscription_id in self.config.subscription_ids
            
        # No filters = include everything
        return True
    
    def is_resource_included(self, resource: Dict[str, Any]) -> bool:
        """
        Check if a resource should be included based on filter config.
        
        Args:
            resource: Resource dictionary with 'resource_group' field
            
        Returns:
            True if resource should be included, False otherwise
        """
        resource_group = resource.get("resource_group")
        if not resource_group:
            # If resource has no resource group, include it by default
            return True
            
        # If resource_group_filter is set, use regex
        if self.config.resource_group_filter:
            import re
            pattern = re.compile(self.config.resource_group_filter)
            return bool(pattern.match(resource_group))
            
        # No filters = include everything
        return True

    def filter_subscriptions(self, subscriptions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter subscriptions based on configured subscription IDs.

        Args:
            subscriptions: List of subscription dictionaries with 'id' field

        Returns:
            Filtered list of subscriptions
        """
        # If no filter configured, return all subscriptions
        if not self.config.subscription_ids:
            logger.debug("No subscription filter configured, returning all subscriptions")
            return subscriptions

        # Filter subscriptions by ID
        filtered = []
        for sub in subscriptions:
            sub_id = sub.get("id")
            if sub_id in self.config.subscription_ids:
                filtered.append(sub)
                logger.debug(f"Including subscription: {sub_id}")
            else:
                logger.debug(f"Excluding subscription: {sub_id}")

        logger.info(
            f"Filtered subscriptions: {len(filtered)}/{len(subscriptions)} "
            f"subscriptions match filter criteria"
        )
        return filtered

    def should_include_resource(self, resource: Dict[str, Any]) -> bool:
        """
        Check if a resource should be included based on resource group filter.

        Args:
            resource: Resource dictionary with 'resource_group' field

        Returns:
            True if resource should be included, False otherwise
        """
        # If no resource group filter configured, include all resources
        if not self.config.resource_group_filter:
            return True

        # Get resource group from resource (case-insensitive comparison)
        resource_group = resource.get("resource_group", "")
        if not resource_group:
            logger.debug(f"Resource {resource.get('id', 'unknown')} has no resource group, excluding")
            return False

        # Check if resource group matches filter (case-insensitive)
        filter_lower = self.config.resource_group_filter.lower()
        rg_lower = resource_group.lower()
        
        # Support partial matching with wildcards
        if "*" in filter_lower:
            # Simple wildcard matching: * matches any characters
            import fnmatch
            matches = fnmatch.fnmatch(rg_lower, filter_lower)
        else:
            # Exact match (case-insensitive)
            matches = rg_lower == filter_lower
        
        if not matches:
            logger.debug(f"Resource group '{resource_group}' does not match filter '{self.config.resource_group_filter}'")
        
        return matches

    def filter_resources(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter resources based on resource group filter.

        Args:
            resources: List of resource dictionaries

        Returns:
            Filtered list of resources
        """
        # If no resource group filter configured, return all resources
        if not self.config.resource_group_filter:
            logger.debug("No resource group filter configured, returning all resources")
            return resources

        # Filter resources by resource group
        filtered = [r for r in resources if self.should_include_resource(r)]
        
        logger.info(
            f"Filtered resources: {len(filtered)}/{len(resources)} "
            f"resources match resource group filter '{self.config.resource_group_filter}'"
        )
        return filtered

    def get_filter_summary(self) -> str:
        """
        Get a human-readable summary of configured filters.

        Returns:
            String describing the active filters
        """
        if not self.config.has_filters():
            return "No filters configured - discovering all resources"

        parts = []
        if self.config.subscription_ids:
            parts.append(f"Subscriptions: {', '.join(self.config.subscription_ids)}")
        if self.config.resource_group_filter:
            parts.append(f"Resource group filter: {self.config.resource_group_filter}")
        
        return f"Discovery filters: {' | '.join(parts)}"