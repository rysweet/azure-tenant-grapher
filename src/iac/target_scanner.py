"""
Target Tenant Scanner Service

This service scans target tenants to discover existing resources (ephemeral, no persistence).
It provides a thin wrapper over AzureDiscoveryService for one-time resource comparisons.

Features:
- Resource existence validation (Issue #555 fix)
- Filters out soft-deleted and stale resources
- Prevents false positive import blocks
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
from azure.mgmt.resource import ResourceManagementClient

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
        validate_existence: bool = True,
    ) -> TargetScanResult:
        """
        Scan target tenant to discover existing resources.

        This method performs an ephemeral scan of the target tenant without persisting
        results to Neo4j. It's suitable for one-time comparisons or conflict detection.

        Args:
            tenant_id: Target tenant ID
            subscription_id: Optional subscription ID (if None, scan all accessible subscriptions)
            credential: Azure credential (if None, use discovery service's default)
            validate_existence: Validate resource existence with Azure GET API (default: True, Issue #555 fix)

        Returns:
            TargetScanResult with discovered resources and metadata

        Note:
            No exceptions are raised - all errors are captured in TargetScanResult.error field.
            Partial scan success is acceptable and will return available resources.
            When validate_existence=True, resources that fail validation are excluded (safe default).
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
                    logger.info(str(f"Scanning single subscription: {subscription_id}"))
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
                    logger.warning(str(f"Skipping subscription without ID: {sub}"))
                    continue

                try:
                    logger.info(str(f"🔍 Scanning subscription: {sub_name} ({sub_id})"))

                    # Discover regular resources
                    resources = (
                        await self.discovery_service.discover_resources_in_subscription(
                            sub_id
                        )
                    )

                    # Convert regular resources to TargetResource format
                    for resource in resources:
                        try:
                            target_resource = self._convert_to_target_resource(resource)

                            # Issue #555 fix: Validate resource existence before adding
                            if validate_existence:
                                resource_exists = await self._validate_resource_exists(
                                    target_resource.id
                                )
                                if not resource_exists:
                                    logger.debug(
                                        f"Resource validation failed (not found or inaccessible): {target_resource.id}"
                                    )
                                    continue  # Skip non-existent resources

                            all_resources.append(target_resource)
                        except Exception as convert_error:
                            logger.warning(
                                f"Failed to convert resource {resource.get('id', 'unknown')}: {convert_error}"
                            )
                            # Continue with other resources

                    logger.info(
                        f"✅ Found {len(resources)} resources in subscription {sub_name}"
                    )

                    # Issue #752 fix: Discover role assignments (separate Authorization API call)
                    try:
                        role_assignments = await self.discovery_service.discover_role_assignments_in_subscription(
                            sub_id, sub_name
                        )

                        # Convert role assignments to TargetResource format
                        for role_assignment in role_assignments:
                            try:
                                target_resource = self._convert_to_target_resource(
                                    role_assignment
                                )

                                # Issue #555 fix: Validate role assignment existence before adding
                                if validate_existence:
                                    resource_exists = (
                                        await self._validate_resource_exists(
                                            target_resource.id
                                        )
                                    )
                                    if not resource_exists:
                                        logger.debug(
                                            f"Role assignment validation failed (not found or inaccessible): {target_resource.id}"
                                        )
                                        continue  # Skip non-existent role assignments

                                all_resources.append(target_resource)
                            except Exception as convert_error:
                                logger.warning(
                                    f"Failed to convert role assignment {role_assignment.get('id', 'unknown')}: {convert_error}"
                                )
                                # Continue with other role assignments

                        logger.info(
                            f"✅ Found {len(role_assignments)} role assignments in subscription {sub_name}"
                        )

                    except Exception as role_error:
                        # Handle role assignment discovery errors gracefully
                        role_partial_error = f"Failed to discover role assignments in subscription {sub_name} ({sub_id}): {role_error}"
                        logger.warning(role_partial_error)

                        # Accumulate role assignment errors but don't fail the entire scan
                        if error_message:
                            error_message += f"\n{role_partial_error}"
                        else:
                            error_message = role_partial_error

                        # Continue with other subscriptions even if role assignments fail

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

    async def _validate_resource_exists(self, resource_id: str) -> bool:
        """
        Validate that a resource actually exists in Azure (Issue #555 fix).

        This method makes a direct Azure GET API call to verify the resource exists
        and is accessible. Resources that return 404 Not Found, 410 Gone, or other
        errors are considered non-existent (safe default).

        Args:
            resource_id: Full Azure resource ID to validate

        Returns:
            True if resource exists and is accessible, False otherwise

        Error Handling:
            - 404 Not Found: Resource doesn't exist → False
            - 410 Gone: Resource soft-deleted → False
            - 403 Forbidden: Permission denied → False (safe default)
            - 500 Server Error: Azure API error → False (safe default)
            - Network errors: Connection issues → False (safe default)
            - All errors logged but don't raise exceptions (graceful degradation)

        Note:
            This validation prevents false positive import blocks for non-existent resources.
        """
        try:
            # Create ResourceManagementClient with discovery service credential
            client = ResourceManagementClient(
                credential=self.discovery_service.credential,
                subscription_id=self._extract_subscription_id_from_resource_id(
                    resource_id
                ),
            )

            # Make Azure GET API call to verify resource exists
            # Use generic resources.get_by_id() to handle all resource types
            client.resources.get_by_id(
                resource_id=resource_id,
                api_version="2021-04-01",  # Generic API version for resource existence check
            )

            # If GET succeeds (200 OK), resource exists
            logger.debug(f"Resource validation successful: {resource_id}")
            return True

        except ResourceNotFoundError:
            # Resource doesn't exist (404 Not Found)
            logger.debug(f"Resource not found (404): {resource_id}")
            return False

        except HttpResponseError as http_error:
            # Handle specific HTTP error codes
            status_code = getattr(http_error, "status_code", None)

            if status_code == 410:
                # Resource soft-deleted (410 Gone)
                logger.debug(f"Resource soft-deleted (410 Gone): {resource_id}")
                return False
            elif status_code == 403:
                # Permission denied (403 Forbidden) - safe default: exclude
                logger.warning(
                    f"Resource validation failed (403 Forbidden): {resource_id}. "
                    "Check service principal permissions."
                )
                return False
            elif status_code in (500, 502, 503, 504):
                # Server errors (5xx) - safe default: exclude
                logger.warning(
                    f"Resource validation failed (Azure server error {status_code}): {resource_id}"
                )
                return False
            else:
                # Other HTTP errors - safe default: exclude
                logger.warning(
                    f"Resource validation failed (HTTP {status_code}): {resource_id} - {http_error}"
                )
                return False

        except Exception as error:
            # Catch-all for unexpected errors (network timeouts, etc.)
            logger.warning(
                f"Resource validation failed (unexpected error): {resource_id} - {error}"
            )
            return False

    def _extract_subscription_id_from_resource_id(self, resource_id: str) -> str:
        """
        Extract subscription ID from full Azure resource ID.

        Args:
            resource_id: Full Azure resource ID (e.g., /subscriptions/abc-123/resourceGroups/...)

        Returns:
            Subscription ID extracted from resource ID

        Raises:
            ValueError: If resource ID format is invalid
        """
        parts = resource_id.split("/")

        # Find 'subscriptions' in path and get next element
        try:
            subscriptions_index = parts.index("subscriptions")
            subscription_id = parts[subscriptions_index + 1]

            if not subscription_id:
                raise ValueError(
                    f"Invalid resource ID format (empty subscription ID): {resource_id}"
                )

            return subscription_id

        except (ValueError, IndexError) as error:
            # 'subscriptions' not found or no element after it
            raise ValueError(
                f"Invalid resource ID format (missing subscriptions segment): {resource_id}"
            ) from error
