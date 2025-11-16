"""
Target Tenant Scanner Service

This service scans target tenants to discover existing resources (ephemeral, no persistence).
It provides a thin wrapper over AzureDiscoveryService for one-time resource comparisons.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..services.azure_discovery_service import AzureDiscoveryService

logger = logging.getLogger(__name__)


@dataclass
class TargetResource:
    """Represents a resource discovered in target tenant."""

    id: str  # Full Azure resource ID
    type: str  # Azure resource type (e.g., Microsoft.Compute/virtualMachines)
    name: str
    location: str
    resource_group: str
    subscription_id: str
    properties: Dict[str, Any] = field(
        default_factory=dict
    )  # Full properties from Azure API
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class TargetScanResult:
    """Result of scanning target tenant."""

    tenant_id: str
    subscription_id: Optional[str]
    resources: List[TargetResource]
    scan_timestamp: str  # ISO8601
    error: Optional[str] = None  # If scan failed partially


class TargetScannerService:
    """Scans target tenant to discover existing resources (ephemeral)."""

    def __init__(self, azure_discovery_service: AzureDiscoveryService):
        """
        Initialize with existing Azure discovery service.

        Args:
            azure_discovery_service: Configured AzureDiscoveryService instance
        """
        self.discovery_service = azure_discovery_service

    async def scan_target_tenant(
        self,
        tenant_id: str,
        subscription_id: Optional[str] = None,
        credential: Any = None,
    ) -> TargetScanResult:
        """
        Scan target tenant to discover existing resources.

        This method performs an ephemeral scan of the target tenant without persisting
        results to Neo4j. It's suitable for one-time comparisons or conflict detection.

        Args:
            tenant_id: Target tenant ID
            subscription_id: Optional subscription ID (if None, scan all accessible subscriptions)
            credential: Azure credential (if None, use discovery service's default)

        Returns:
            TargetScanResult with discovered resources and metadata

        Note:
            No exceptions are raised - all errors are captured in TargetScanResult.error field.
            Partial scan success is acceptable and will return available resources.
        """
        scan_timestamp = datetime.now(timezone.utc).isoformat()
        error_message: Optional[str] = None
        all_resources: List[TargetResource] = []

        logger.info(
            f"🔍 Starting target tenant scan: tenant_id={tenant_id}, "
            f"subscription_id={subscription_id or 'all'}"
        )

        try:
            # Update credential if provided
            original_credential = None
            if credential:
                original_credential = self.discovery_service.credential
                self.discovery_service.credential = credential
                logger.debug("Using provided credential for target tenant scan")

            # Discover subscriptions
            try:
                if subscription_id:
                    # Scan specific subscription
                    subscriptions = [
                        {"id": subscription_id, "display_name": subscription_id}
                    ]
                    logger.info(f"Scanning single subscription: {subscription_id}")
                else:
                    # Discover all subscriptions in target tenant
                    subscriptions = (
                        await self.discovery_service.discover_subscriptions()
                    )
                    logger.info(
                        f"Discovered {len(subscriptions)} subscriptions in target tenant"
                    )

                    if not subscriptions:
                        error_message = (
                            f"No subscriptions found in target tenant {tenant_id}. "
                            "This may indicate insufficient permissions or empty tenant."
                        )
                        logger.warning(error_message)

            except Exception as sub_error:
                error_message = f"Failed to discover subscriptions: {sub_error}"
                logger.error(error_message, exc_info=True)
                subscriptions = []

            # Discover resources in each subscription
            for sub in subscriptions:
                sub_id = sub.get("id")
                sub_name = sub.get("display_name", sub_id)

                if not sub_id:
                    logger.warning(f"Skipping subscription without ID: {sub}")
                    continue

                try:
                    logger.info(f"🔍 Scanning subscription: {sub_name} ({sub_id})")
                    resources = (
                        await self.discovery_service.discover_resources_in_subscription(
                            sub_id
                        )
                    )

                    # Convert to TargetResource format
                    for resource in resources:
                        try:
                            target_resource = self._convert_to_target_resource(resource)
                            all_resources.append(target_resource)
                        except Exception as convert_error:
                            logger.warning(
                                f"Failed to convert resource {resource.get('id', 'unknown')}: {convert_error}"
                            )
                            # Continue with other resources

                    logger.info(
                        f"✅ Found {len(resources)} resources in subscription {sub_name}"
                    )

                except Exception as resource_error:
                    partial_error = f"Failed to scan subscription {sub_name} ({sub_id}): {resource_error}"
                    logger.error(partial_error, exc_info=True)

                    # Accumulate partial errors
                    if error_message:
                        error_message += f"\n{partial_error}"
                    else:
                        error_message = partial_error

                    # Continue with other subscriptions (graceful degradation)

            # Restore original credential if we changed it
            if credential and original_credential is not None:
                self.discovery_service.credential = original_credential

        except Exception as outer_error:
            # Catch-all for unexpected errors
            error_message = f"Unexpected error during target tenant scan: {outer_error}"
            logger.error(error_message, exc_info=True)

        # Create result with all discovered resources and any accumulated errors
        result = TargetScanResult(
            tenant_id=tenant_id,
            subscription_id=subscription_id,
            resources=all_resources,
            scan_timestamp=scan_timestamp,
            error=error_message,
        )

        logger.info(
            f"✅ Target tenant scan complete: {len(all_resources)} resources discovered, "
            f"errors={'yes' if error_message else 'no'}"
        )

        return result

    def _convert_to_target_resource(self, resource: Dict[str, Any]) -> TargetResource:
        """
        Convert Azure API resource format to TargetResource.

        Args:
            resource: Resource dictionary from Azure API

        Returns:
            TargetResource with populated fields

        Raises:
            ValueError: If required fields are missing
        """
        # Extract required fields
        resource_id = resource.get("id")
        resource_type = resource.get("type")
        resource_name = resource.get("name")
        location = resource.get("location", "")
        resource_group = resource.get("resource_group", "")
        subscription_id = resource.get("subscription_id", "")

        # Validate required fields
        if not resource_id:
            raise ValueError("Resource missing 'id' field")
        if not resource_type:
            raise ValueError(f"Resource {resource_id} missing 'type' field")
        if not resource_name:
            raise ValueError(f"Resource {resource_id} missing 'name' field")

        # Extract optional fields
        properties = resource.get("properties", {})
        if not isinstance(properties, dict):
            logger.warning(
                f"Resource {resource_id} has non-dict properties, converting to empty dict"
            )
            properties = {}

        tags = resource.get("tags", {})
        if not isinstance(tags, dict):
            logger.warning(
                f"Resource {resource_id} has non-dict tags, converting to empty dict"
            )
            tags = {}

        return TargetResource(
            id=resource_id,
            type=resource_type,
            name=resource_name,
            location=location,
            resource_group=resource_group,
            subscription_id=subscription_id,
            properties=properties,
            tags=tags,
        )
