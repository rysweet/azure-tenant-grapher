"""
Azure Discovery Service

This service handles all Azure subscription and resource discovery operations,
providing a focused interface for interacting with Azure APIs while following
proper error handling and dependency injection patterns.
"""

import asyncio
import logging
import os
from typing import Any, Awaitable, Callable, Dict, List, Optional

from azure.core.credentials import AccessToken  # type: ignore[import-untyped]
from azure.core.exceptions import AzureError  # type: ignore[import-untyped]
from azure.identity import (  # type: ignore[import-untyped]
    AzureCliCredential,
    CredentialUnavailableError,
    DefaultAzureCredential,
)
from azure.mgmt.authorization import (
    AuthorizationManagementClient,  # type: ignore[import-untyped]
)
from azure.mgmt.monitor import MonitorManagementClient  # type: ignore[import-untyped]
from azure.mgmt.resource import ResourceManagementClient  # type: ignore[import-untyped]
from azure.mgmt.subscription import SubscriptionClient  # type: ignore[import-untyped]

from ..config_manager import AzureTenantGrapherConfig
from ..exceptions import (
    AzureAuthenticationError,
    AzureDiscoveryError,
)
from ..models.filter_config import FilterConfig

logger = logging.getLogger(__name__)


class StaticTokenCredential:
    """
    Custom credential that uses a static access token.
    Used for SPA-provided authentication tokens.

    SECURITY: This credential does NOT log the token value.
    """

    def __init__(self, access_token: str):
        """
        Initialize with a static access token.

        Args:
            access_token: Azure access token from device code flow

        Raises:
            ValueError: If token is invalid (empty or too short)
        """
        if not access_token or not access_token.strip():
            raise ValueError("Invalid access token: Token cannot be empty")

        if len(access_token) < 50:
            raise ValueError("Token too short: Token appears to be invalid")

        self._token = access_token
        # NOTE: We do NOT log the token value (security requirement)
        logger.info("Using static token credential (token value not logged)")

    def get_token(self, *scopes: str, **kwargs: Any) -> AccessToken:
        """
        Get the static access token.

        Args:
            *scopes: Token scopes (ignored for static token)
            **kwargs: Additional arguments (ignored)

        Returns:
            AccessToken with the static token (expires in 1 hour as placeholder)
        """
        # Return token with a far-future expiry (we don't know actual expiry)
        # The token will be validated by Azure API calls
        import time

        expiry = int(time.time()) + 3600  # 1 hour from now
        return AccessToken(self._token, expiry)


class AzureDiscoveryService:
    """
    Service for discovering Azure subscriptions and resources.

    This service encapsulates all Azure API interactions for resource discovery,
    providing proper error handling, authentication fallback, and clear interfaces
    for testing and dependency injection.
    """

    def __init__(
        self,
        config: AzureTenantGrapherConfig,
        credential: Optional[Any] = None,
        subscription_client_factory: Optional[Callable[[Any], Any]] = None,
        resource_client_factory: Optional[Callable[[Any, str], Any]] = None,
        authorization_client_factory: Optional[Callable[[Any, str], Any]] = None,
        monitor_client_factory: Optional[Callable[[Any, str], Any]] = None,
        change_feed_ingestion_service: Optional[Any] = None,
    ) -> None:
        """
        Initialize the Azure Discovery Service.

        Args:
            config: Configuration object containing Azure settings
            credential: Optional Azure credential (for dependency injection/testing)
            subscription_client_factory: Optional factory for SubscriptionClient (for testing)
            resource_client_factory: Optional factory for ResourceManagementClient (for testing)
            authorization_client_factory: Optional factory for AuthorizationManagementClient (for testing)
            monitor_client_factory: Optional factory for MonitorManagementClient (for testing)
            change_feed_ingestion_service: Optional ChangeFeedIngestionService for delta ingestion (for testing)
        """
        self.config = config

        # Check for environment token (from SPA device code flow)
        # SECURITY: Token is cleared from environment after use
        access_token = os.environ.get("AZURE_ACCESS_TOKEN")
        if access_token and not credential:
            # Use static token credential with environment token
            logger.info("Using access token from environment (AZURE_ACCESS_TOKEN)")
            self.credential = StaticTokenCredential(access_token)

            # SECURITY CRITICAL: Clear token from environment immediately
            # This prevents token leakage through logs, child processes, etc.
            del os.environ["AZURE_ACCESS_TOKEN"]
            logger.info("Token cleared from environment for security")
        else:
            # Fall back to provided credential or DefaultAzureCredential
            self.credential = credential or DefaultAzureCredential()

        self.subscription_client_factory = (
            subscription_client_factory or SubscriptionClient
        )
        self.resource_client_factory = (
            resource_client_factory or ResourceManagementClient
        )
        self.authorization_client_factory = (
            authorization_client_factory or AuthorizationManagementClient
        )
        self.monitor_client_factory = monitor_client_factory or MonitorManagementClient
        self.change_feed_ingestion_service = change_feed_ingestion_service
        # Maximum retry attempts for transient Azure errors (default 3)
        self._max_retries: int = (
            getattr(getattr(config, "processing", None), "max_retries", 3) or 3
        )
        # Maximum concurrent threads for fetching resource details
        self._max_build_threads: int = (
            getattr(getattr(config, "processing", None), "max_build_threads", 20) or 20
        )
        # Cache for resource provider API versions
        self._api_version_cache: Dict[str, str] = {}
        self._subscriptions: List[Dict[str, Any]] = []

    @property
    def subscriptions(self) -> List[Dict[str, Any]]:
        """Get the cached list of discovered subscriptions."""
        return self._subscriptions.copy()

    async def discover_subscriptions(
        self, _skip_fallback: bool = False, filter_config: Optional[FilterConfig] = None
    ) -> List[Dict[str, Any]]:
        """
        Discover all subscriptions in the tenant.

        Args:
            _skip_fallback: Skip fallback authentication (internal use)
            filter_config: Optional FilterConfig to filter subscriptions

        Returns:
            List of subscription dictionaries with id and display_name

        Raises:
            AzureDiscoveryError: If subscription discovery fails
            AzureAuthenticationError: If authentication fails
        """
        logger.info(
            str(f"🔍 Discovering subscriptions in tenant {self.config.tenant_id}")
        )

        async def _attempt_discovery() -> List[Dict[str, Any]]:
            try:
                subscription_client = self.subscription_client_factory(self.credential)
                subscriptions: List[Dict[str, Any]] = []
                for subscription in subscription_client.subscriptions.list():
                    sub: Any = subscription
                    subscription_dict: Dict[str, Any] = {
                        "id": getattr(sub, "subscription_id", None),
                        "display_name": getattr(sub, "display_name", None),
                    }
                    subscriptions.append(subscription_dict)
                    logger.info(
                        f"📋 Found subscription: {subscription_dict['display_name']} ({subscription_dict['id']})"
                    )
                # Apply filter if provided
                if filter_config:
                    filtered_subscriptions = []
                    for sub in subscriptions:
                        if filter_config.should_include_subscription(sub["id"]):
                            filtered_subscriptions.append(sub)
                        else:
                            logger.info(
                                f"🚫 Filtering out subscription: {sub['display_name']} ({sub['id']})"
                            )
                    subscriptions = filtered_subscriptions
                    logger.info(
                        f"✅ After filtering: {len(subscriptions)} subscriptions included"
                    )

                self._subscriptions = subscriptions
                logger.info(
                    str(f"✅ Discovered {len(subscriptions)} subscriptions total")
                )

                # If we get 0 subscriptions but no error, it might be a permissions issue
                # Try Azure CLI credential as a fallback (only if not already in fallback mode)
                if len(subscriptions) == 0 and not _skip_fallback:
                    logger.warning(
                        "🔄 Got 0 subscriptions with current credential, attempting Azure CLI fallback..."
                    )
                    try:
                        fallback_subs = await self._handle_auth_fallback()
                        if len(fallback_subs) > 0:
                            logger.info(
                                f"✅ Azure CLI fallback succeeded, found {len(fallback_subs)} subscriptions"
                            )
                            self._subscriptions = fallback_subs
                            return fallback_subs
                    except Exception as fallback_exc:
                        logger.warning(
                            str(f"Azure CLI fallback failed: {fallback_exc}")
                        )
                        # Continue with original empty result

                return subscriptions
            except AzureError:
                # Log and propagate so outer retry loop can handle
                logger.exception("AzureError during subscription discovery")
                raise
            except Exception as exc:
                logger.exception("Non-AzureError during subscription discovery")
                raise AzureDiscoveryError(
                    f"Non-Azure error during subscription discovery: {exc}",
                    context={"tenant_id": self.config.tenant_id},
                ) from exc

        # Retry logic with exponential backoff for AzureError
        max_attempts = self._max_retries
        delay = 1
        from azure.core.exceptions import (
            ClientAuthenticationError,  # type: ignore[import-untyped]
        )

        for attempt in range(1, max_attempts + 1):
            try:
                return await _attempt_discovery()
            except AzureError as exc:
                logger.warning(str(f"Attempt {attempt} failed: {exc}"))
                # If authentication/credential error, attempt fallback immediately
                if (
                    isinstance(
                        exc, (ClientAuthenticationError, CredentialUnavailableError)
                    )
                    or "authentication" in str(exc).lower()
                    or "credential" in str(exc).lower()
                ):
                    try:
                        return await self._handle_auth_fallback(_attempt_discovery)
                    except AzureAuthenticationError as auth_exc:
                        logger.exception("Authentication fallback failed")
                        raise AzureAuthenticationError(
                            f"Authentication fallback failed: {auth_exc}",
                            tenant_id=self.config.tenant_id,
                        ) from auth_exc
                # Otherwise, retry
                if attempt < max_attempts:
                    await asyncio.sleep(delay)
                    delay *= 2
                else:
                    logger.exception(
                        "Max attempts reached for subscription discovery, raising AzureDiscoveryError."
                    )
                    raise AzureDiscoveryError(
                        f"Azure error during subscription discovery: {exc}",
                        context={"tenant_id": self.config.tenant_id},
                    ) from exc
        return []

    async def discover_resources_in_subscription(
        self,
        subscription_id: str,
        filter_config: Optional[FilterConfig] = None,
        resource_limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Discover all resources in a specific subscription with optional parallel property fetching.

        Args:
            subscription_id: Azure subscription ID
            filter_config: Optional FilterConfig to filter resources
            resource_limit: Optional limit on number of resources to discover per subscription

        Returns:
            List of resource dictionaries with full properties if max_build_threads > 0

        Raises:
            AzureDiscoveryError: If resource discovery fails
        """
        logger.info(str(f"🔍 Discovering resources in subscription {subscription_id}"))

        async def _attempt_discovery() -> List[Dict[str, Any]]:
            try:
                resource_client = self.resource_client_factory(
                    self.credential, subscription_id
                )

                # Phase 1: List all resources (lightweight)
                logger.info("📋 Phase 1: Listing all resource IDs...")
                resource_basics: List[Dict[str, Any]] = []
                pager = resource_client.resources.list()
                for resource in pager:
                    res: Any = resource
                    res_id: Optional[str] = getattr(res, "id", None)

                    # Parse resource ID to extract subscription_id and resource_group
                    parsed_info = self._parse_resource_id(res_id) if res_id else {}

                    resource_dict: Dict[str, Any] = {
                        "id": res_id,
                        "name": getattr(res, "name", None),
                        "type": getattr(res, "type", None),
                        "location": getattr(res, "location", None),
                        "tags": dict(getattr(res, "tags", {}) or {}),
                        # Start with existing properties if available (usually None from list),
                        # will be populated by parallel fetching if enabled
                        "properties": getattr(res, "properties", {}) or {},
                        "subscription_id": parsed_info.get(
                            "subscription_id", subscription_id
                        ),
                        "resource_group": parsed_info.get("resource_group"),
                    }
                    # Apply resource filter if provided
                    if filter_config:
                        if filter_config.should_include_resource(resource_dict):
                            resource_basics.append(resource_dict)
                        else:
                            logger.debug(
                                f"🚫 Filtering out resource: {resource_dict.get('name')} in RG {resource_dict.get('resource_group')}"
                            )
                    else:
                        resource_basics.append(resource_dict)

                logger.info(
                    f"✅ Found {len(resource_basics)} resources in subscription {subscription_id} after filtering"
                )

                # Phase 1.5: Discover role assignments in subscription
                # This is done separately because role assignments are not returned by
                # resources.list() - they require a separate API call to the
                # Authorization Management Client
                logger.info("🔐 Phase 1.5: Discovering role assignments...")
                all_role_assignments = []
                try:
                    # Get subscription name from cached subscriptions
                    subscription_name = subscription_id
                    for sub in self._subscriptions:
                        if sub.get("id") == subscription_id:
                            subscription_name = sub.get("display_name", subscription_id)
                            break

                    # Discover subscription-level role assignments
                    role_assignments = (
                        await self.discover_role_assignments_in_subscription(
                            subscription_id, subscription_name
                        )
                    )
                    all_role_assignments.extend(role_assignments)

                    # Discover resource-scoped role assignments (Phase 3)
                    # These are scoped to individual resources, not subscription-wide
                    logger.info(
                        "🔐 Phase 1.5.1: Discovering resource-scoped role assignments..."
                    )
                    resource_scoped = (
                        await self.discover_resource_scoped_role_assignments(
                            subscription_id, resource_basics
                        )
                    )
                    all_role_assignments.extend(resource_scoped)

                    logger.info(
                        f"✅ Total role assignments discovered: {len(all_role_assignments)} "
                        f"({len(role_assignments)} subscription-level + {len(resource_scoped)} resource-scoped)"
                    )

                    # Apply filter to role assignments if provided
                    if filter_config and all_role_assignments:
                        filtered_assignments = []
                        for assignment in all_role_assignments:
                            if filter_config.should_include_resource(assignment):
                                filtered_assignments.append(assignment)
                            else:
                                logger.debug(
                                    f"🚫 Filtering out role assignment: {assignment.get('id')}"
                                )
                        all_role_assignments = filtered_assignments
                        logger.info(
                            f"✅ After filtering: {len(all_role_assignments)} role assignments included"
                        )

                    # Merge role assignments with resources
                    resource_basics.extend(all_role_assignments)
                    logger.info(
                        f"✅ Total resources including role assignments: {len(resource_basics)}"
                    )
                except Exception as role_error:
                    # Log but don't fail - role assignments are supplementary
                    logger.warning(
                        f"Failed to discover role assignments (continuing with other resources): {role_error}"
                    )

                # Apply resource_limit BEFORE child discovery to reduce API calls
                if resource_limit and len(resource_basics) > resource_limit:
                    logger.info(
                        f"🔢 Applying per-subscription resource_limit before child discovery: "
                        f"{resource_limit} (before: {len(resource_basics)})"
                    )
                    resource_basics = resource_basics[:resource_limit]
                    logger.info(
                        f"🔢 Resource list truncated to {len(resource_basics)} items "
                        f"(child resources will only be discovered for these {len(resource_basics)} resources)"
                    )

                # Phase 1.6: Discover child resources (Bug #520 fix)
                # Child resources (subnets, runbooks, etc.) are not returned by resources.list()
                # They require explicit API calls to parent resource endpoints
                logger.info("🔍 Phase 1.6: Discovering child resources...")
                child_resources = []
                try:
                    discovered_children = await self.discover_child_resources(
                        subscription_id, resource_basics
                    )

                    if discovered_children:
                        # Apply filter to child resources if provided
                        if filter_config:
                            filtered_children = []
                            for child in discovered_children:
                                if filter_config.should_include_resource(child):
                                    filtered_children.append(child)
                                else:
                                    logger.debug(
                                        f"🚫 Filtering out child resource: {child.get('id')}"
                                    )
                            child_resources = filtered_children
                            logger.info(
                                f"✅ After filtering: {len(child_resources)} child resources included"
                            )
                        else:
                            child_resources = discovered_children

                        # Merge child resources with main resource list
                        resource_basics.extend(child_resources)
                        logger.info(
                            f"✅ Total resources including children: {len(resource_basics)}"
                        )
                except Exception as child_error:
                    # Log but don't fail - child resources are supplementary
                    logger.warning(
                        f"Failed to discover child resources (continuing): {child_error}"
                    )

                # Phase 1.7: Discover diagnostic settings
                # Diagnostic settings are not returned by resources.list()
                # They require Monitor Management Client API calls
                logger.info("📊 Phase 1.7: Discovering diagnostic settings...")
                try:
                    diagnostic_settings = await self.discover_diagnostic_settings(
                        subscription_id, resource_basics
                    )

                    if diagnostic_settings:
                        # Apply filter to diagnostic settings if provided
                        if filter_config:
                            filtered_diagnostics = []
                            for diagnostic in diagnostic_settings:
                                if filter_config.should_include_resource(diagnostic):
                                    filtered_diagnostics.append(diagnostic)
                                else:
                                    logger.debug(
                                        f"🚫 Filtering out diagnostic setting: {diagnostic.get('id')}"
                                    )
                            diagnostic_settings = filtered_diagnostics
                            logger.info(
                                f"✅ After filtering: {len(diagnostic_settings)} diagnostic settings included"
                            )

                        # Merge diagnostic settings with main resource list
                        child_resources.extend(diagnostic_settings)
                        resource_basics.extend(diagnostic_settings)
                        logger.info(
                            f"✅ Total resources including diagnostic settings: {len(resource_basics)}"
                        )
                except Exception as diagnostic_error:
                    # Log but don't fail - diagnostic settings are supplementary
                    logger.warning(
                        f"Failed to discover diagnostic settings (continuing): {diagnostic_error}"
                    )

                # Phase 2: Fetch full properties in parallel if enabled
                if self._max_build_threads > 0 and resource_basics:
                    logger.info(
                        f"🔄 Phase 2: Fetching full properties for {len(resource_basics)} resources "
                        f"(max {self._max_build_threads} concurrent threads)..."
                    )
                    enriched_resources = await self._fetch_resources_with_properties(
                        resource_basics, resource_client, subscription_id
                    )
                    return enriched_resources
                else:
                    logger.info(
                        "Skipping property enrichment (disabled or no resources)"
                    )
                    return resource_basics
            except AzureError:
                # Log and propagate so outer retry loop can handle
                logger.exception("AzureError during resource discovery")
                raise
            except Exception as exc:
                logger.exception("Non-AzureError during resource discovery")
                raise AzureDiscoveryError(
                    f"Non-Azure error during resource discovery: {exc}",
                    context={
                        "subscription_id": subscription_id,
                        "tenant_id": self.config.tenant_id,
                    },
                ) from exc

        # Retry logic with exponential backoff for AzureError
        max_attempts = self._max_retries
        delay = 1
        from azure.core.exceptions import (
            ClientAuthenticationError,  # type: ignore[import-untyped]
        )

        for attempt in range(1, max_attempts + 1):
            try:
                return await _attempt_discovery()
            except AzureError as exc:
                logger.warning(str(f"Attempt {attempt} failed: {exc}"))
                # If authentication/credential error, attempt fallback immediately
                if (
                    isinstance(
                        exc, (ClientAuthenticationError, CredentialUnavailableError)
                    )
                    or "authentication" in str(exc).lower()
                    or "credential" in str(exc).lower()
                ):
                    try:
                        return await self._handle_auth_fallback(_attempt_discovery)
                    except AzureAuthenticationError as auth_exc:
                        logger.exception(
                            "Authentication fallback failed during resource discovery"
                        )
                        raise AzureDiscoveryError(
                            f"Authentication fallback failed during resource discovery: {auth_exc}",
                            context={
                                "subscription_id": subscription_id,
                                "tenant_id": self.config.tenant_id,
                            },
                        ) from auth_exc
                    raise AzureDiscoveryError(
                        f"Failed to discover resources after fallback: {exc}",
                        context={
                            "subscription_id": subscription_id,
                            "tenant_id": self.config.tenant_id,
                        },
                    ) from exc
                # Otherwise, retry
                if attempt < max_attempts:
                    await asyncio.sleep(delay)
                    delay *= 2
                else:
                    logger.exception(
                        "Max attempts reached for resource discovery, raising AzureDiscoveryError."
                    )
                    raise AzureDiscoveryError(
                        f"Azure error during resource discovery: {exc}",
                        context={
                            "subscription_id": subscription_id,
                            "tenant_id": self.config.tenant_id,
                        },
                    ) from exc
        return []

    async def discover_resources_across_subscriptions(
        self,
        subscription_ids: List[str],
        concurrency: int = 5,
        filter_config: Optional[FilterConfig] = None,
    ) -> List[Dict[str, Any]]:
        """
        Discover resources for many subscriptions concurrently while ensuring that
        no more than *concurrency* discovery operations are in-flight at once.

        Args:
            subscription_ids: List of Azure subscription IDs.
            concurrency: Maximum number of concurrent discovery tasks (``>=1``).
            filter_config: Optional FilterConfig to filter resources

        Returns
        -------
        List[Dict[str, Any]]
            Flattened list containing all discovered resources from every
            subscription.
        """
        # Guard against invalid values
        if concurrency <= 0:
            concurrency = 1

        semaphore = asyncio.Semaphore(concurrency)

        async def _bounded_discover(sub_id: str) -> List[Dict[str, Any]]:
            # Ensure no more than `concurrency` coroutines execute concurrently.
            async with semaphore:
                return await self.discover_resources_in_subscription(
                    sub_id, filter_config
                )

        # Kick off the tasks concurrently and wait for them to finish.
        results_nested: List[List[Dict[str, Any]]] = await asyncio.gather(
            *[_bounded_discover(sid) for sid in subscription_ids]
        )

        # Flatten [[...], [...]] → [...]
        flattened: List[Dict[str, Any]] = [
            item for sublist in results_nested for item in sublist
        ]
        return flattened

    async def discover_role_assignments_in_subscription(
        self, subscription_id: str, subscription_name: str
    ) -> List[Dict[str, Any]]:
        """
        Discover role assignments in a specific subscription.

        Role assignments link identities (users, service principals, managed identities)
        to roles at specific scopes. This method fetches all role assignments for a
        subscription and converts them to the resource format expected by the processor.

        **Phase 3 Enhancement**: Now discovers both subscription-level and resource-scoped
        role assignments using list_for_subscription() and list_for_resource() APIs.

        Args:
            subscription_id: Azure subscription ID
            subscription_name: Display name of the subscription

        Returns:
            List of role assignment dictionaries in resource format

        Raises:
            AzureDiscoveryError: If role assignment discovery fails critically
        """
        logger.info(
            f"🔍 Discovering role assignments in subscription {subscription_id}"
        )

        try:
            # Create authorization client for this subscription
            authorization_client = self.authorization_client_factory(
                self.credential, subscription_id
            )

            role_assignments: List[Dict[str, Any]] = []

            # List all role assignments in the subscription
            # This requires Reader + User Access Administrator roles or equivalent
            try:
                pager = authorization_client.role_assignments.list_for_subscription()

                for assignment in pager:
                    # Extract role assignment properties
                    assignment_id: Optional[str] = getattr(assignment, "id", None)
                    if not assignment_id:
                        logger.debug("Skipping role assignment without ID")
                        continue

                    # Get assignment properties
                    principal_id: Optional[str] = getattr(
                        assignment, "principal_id", None
                    )
                    principal_type: Optional[str] = getattr(
                        assignment, "principal_type", None
                    )
                    role_definition_id: Optional[str] = getattr(
                        assignment, "role_definition_id", None
                    )
                    scope: Optional[str] = getattr(assignment, "scope", None)

                    # Convert to resource format expected by processor
                    # Format matches what ResourceManagementClient.resources.list() returns
                    role_assignment_dict: Dict[str, Any] = {
                        "id": assignment_id,
                        "name": assignment_id.split("/")[-1]
                        if assignment_id
                        else "unknown",
                        "type": "Microsoft.Authorization/roleAssignments",
                        "location": None,  # Role assignments are not location-specific
                        "tags": {},
                        "properties": {
                            "principalId": principal_id,
                            "principalType": principal_type,
                            "roleDefinitionId": role_definition_id,
                            "scope": scope,
                        },
                        "subscription_id": subscription_id,
                        # Extract resource group from scope if present
                        "resource_group": self._extract_resource_group_from_scope(
                            scope
                        ),
                    }

                    role_assignments.append(role_assignment_dict)

                    logger.debug(
                        f"Found role assignment: {principal_type} -> "
                        f"{role_definition_id.split('/')[-1] if role_definition_id else 'unknown'} "
                        f"at scope {scope}"
                    )

                logger.info(
                    f"✅ Discovered {len(role_assignments)} subscription-level role assignments in subscription {subscription_id}"
                )

            except Exception as perm_error:
                # Permission errors are common - handle gracefully
                error_msg = str(perm_error).lower()
                if any(
                    keyword in error_msg
                    for keyword in [
                        "authorization",
                        "forbidden",
                        "access denied",
                        "insufficient privileges",
                        "does not have authorization",
                    ]
                ):
                    logger.warning(
                        f"⚠️  Insufficient permissions to list role assignments in subscription {subscription_id}. "
                        "This requires Reader + User Access Administrator roles or Owner role. "
                        "Role assignment relationships will not be created for this subscription."
                    )
                    # Return empty list - not a fatal error
                    return []
                else:
                    # Unknown error - log but don't fail the entire discovery
                    logger.warning(
                        f"Failed to list role assignments in subscription {subscription_id}: {perm_error}"
                    )
                    return []

            return role_assignments

        except Exception:
            # Catch-all for unexpected errors
            logger.exception(
                f"Unexpected error discovering role assignments in subscription {subscription_id}"
            )
            # Don't raise - role assignments are supplementary, not critical
            logger.warning(
                f"Continuing discovery without role assignments for subscription {subscription_id}"
            )
            return []

    async def discover_resource_scoped_role_assignments(
        self,
        subscription_id: str,
        resources: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Discover resource-scoped role assignments for specific resources.

        Resource-scoped role assignments grant permissions directly on individual
        resources (e.g., Key Vault data plane roles, Storage blob access). These
        are NOT returned by list_for_subscription() and require explicit calls
        to list_for_resource() for each resource.

        Args:
            subscription_id: Azure subscription ID
            resources: List of resources to check for resource-scoped role assignments

        Returns:
            List of resource-scoped role assignment dictionaries

        Raises:
            No exceptions - handles permission errors gracefully
        """
        logger.info(
            f"🔐 Discovering resource-scoped role assignments for {len(resources)} resources..."
        )

        resource_scoped_assignments = []

        try:
            # Create authorization client for this subscription
            authorization_client = self.authorization_client_factory(
                self.credential, subscription_id
            )

            # Resource types that commonly have resource-scoped role assignments
            # Focus on resources with data plane permissions
            target_types = {
                "Microsoft.KeyVault/vaults",
                "Microsoft.Storage/storageAccounts",
                "Microsoft.ContainerRegistry/registries",
                "Microsoft.Sql/servers",
                "Microsoft.DBforPostgreSQL/servers",
                "Microsoft.DBforPostgreSQL/flexibleServers",
                "Microsoft.Web/sites",
                "Microsoft.EventHub/namespaces",
                "Microsoft.ServiceBus/namespaces",
            }

            # Filter resources to those likely to have resource-scoped assignments
            candidate_resources = [
                r for r in resources if r.get("type") in target_types
            ]

            logger.info(
                f"Checking {len(candidate_resources)} resources for resource-scoped role assignments"
            )

            for resource in candidate_resources:
                try:
                    resource_id = resource.get("id")
                    if not resource_id:
                        continue

                    # Fetch role assignments scoped to this specific resource
                    # Azure API: GET {resourceId}/providers/Microsoft.Authorization/roleAssignments
                    pager = authorization_client.role_assignments.list_for_resource(
                        resource_group_name=resource.get("resource_group", ""),
                        resource_provider_namespace=self._extract_provider(
                            resource.get("type", "")
                        ),
                        parent_resource_path="",
                        resource_type=self._extract_resource_type(
                            resource.get("type", "")
                        ),
                        resource_name=resource.get("name", ""),
                    )

                    for assignment in pager:
                        assignment_id = getattr(assignment, "id", None)
                        if not assignment_id:
                            continue

                        # Skip subscription-level assignments (already captured)
                        scope = getattr(assignment, "scope", "")
                        if not scope or scope == f"/subscriptions/{subscription_id}":
                            continue

                        # Only include if scoped exactly to this resource
                        if scope != resource_id:
                            continue

                        # Extract assignment properties
                        principal_id = getattr(assignment, "principal_id", None)
                        principal_type = getattr(assignment, "principal_type", None)
                        role_definition_id = getattr(
                            assignment, "role_definition_id", None
                        )

                        # Convert to resource format
                        assignment_dict = {
                            "id": assignment_id,
                            "name": assignment_id.split("/")[-1]
                            if assignment_id
                            else "unknown",
                            "type": "Microsoft.Authorization/roleAssignments",
                            "location": None,
                            "tags": {},
                            "properties": {
                                "principalId": principal_id,
                                "principalType": principal_type,
                                "roleDefinitionId": role_definition_id,
                                "scope": scope,
                            },
                            "subscription_id": subscription_id,
                            "resource_group": resource.get("resource_group"),
                            # Preserve scan metadata for relationships
                            "scan_id": resource.get("scan_id"),
                            "tenant_id": resource.get("tenant_id"),
                        }

                        resource_scoped_assignments.append(assignment_dict)

                except Exception as e:
                    # Handle permission errors and unsupported resources gracefully
                    error_msg = str(e).lower()

                    if any(
                        keyword in error_msg
                        for keyword in [
                            "forbidden",
                            "authorization",
                            "access denied",
                            "insufficient privileges",
                        ]
                    ):
                        logger.debug(
                            f"Insufficient permissions to read role assignments for {resource.get('id')}"
                        )
                    elif "not found" in error_msg or "does not exist" in error_msg:
                        logger.debug(
                            f"Resource {resource.get('id')} not found or has no role assignments"
                        )
                    else:
                        # Unknown error - log but continue
                        logger.warning(
                            f"Failed to fetch resource-scoped role assignments for {resource.get('id')}: {e}"
                        )

            logger.info(
                f"✅ Discovered {len(resource_scoped_assignments)} resource-scoped role assignments"
            )

        except Exception:
            # Catch-all for unexpected errors
            logger.exception(
                f"Unexpected error discovering resource-scoped role assignments in subscription {subscription_id}"
            )
            logger.warning(
                "Continuing discovery without resource-scoped role assignments for this subscription"
            )

        return resource_scoped_assignments

    def _extract_provider(self, resource_type: str) -> str:
        """
        Extract provider namespace from resource type.

        Args:
            resource_type: Full resource type (e.g., "Microsoft.KeyVault/vaults")

        Returns:
            Provider namespace (e.g., "Microsoft.KeyVault")
        """
        if not resource_type or "/" not in resource_type:
            return ""
        return resource_type.split("/")[0]

    def _extract_resource_type(self, resource_type: str) -> str:
        """
        Extract resource type name from full resource type.

        Args:
            resource_type: Full resource type (e.g., "Microsoft.KeyVault/vaults")

        Returns:
            Resource type name (e.g., "vaults")
        """
        if not resource_type or "/" not in resource_type:
            return ""
        return resource_type.split("/")[1]

    async def discover_child_resources(
        self,
        subscription_id: str,
        parent_resources: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Discover child resources that resources.list() doesn't return.

        Child resources (subnets, runbooks, etc.) are nested under parent resources
        and require explicit API calls to parent resource endpoints.

        Args:
            subscription_id: Azure subscription ID
            parent_resources: List of parent resources from main discovery

        Returns:
            List of child resource dictionaries

        Bug #520 fix: Target scanner coverage gaps for child resources
        """
        from azure.mgmt.automation import (
            AutomationClient,  # type: ignore[import-untyped]
        )
        from azure.mgmt.network import (
            NetworkManagementClient,  # type: ignore[import-untyped]
        )

        child_resources = []

        # Group parents by type for efficient processing
        vnets = [
            r
            for r in parent_resources
            if r.get("type") == "Microsoft.Network/virtualNetworks"
        ]
        automation_accounts = [
            r
            for r in parent_resources
            if r.get("type") == "Microsoft.Automation/automationAccounts"
        ]

        # Discover subnets
        if vnets:
            logger.info(str(f"🔍 Discovering subnets for {len(vnets)} VNets..."))
            try:
                network_client = NetworkManagementClient(
                    self.credential, subscription_id
                )

                for vnet in vnets:
                    try:
                        rg = vnet.get("resource_group")
                        vnet_name = vnet.get("name")

                        if not rg or not vnet_name:
                            continue

                        # Fetch subnets for this VNet
                        subnets_pager = network_client.subnets.list(rg, vnet_name)

                        for subnet in subnets_pager:
                            # FIX Issue #563: Include scan_id and tenant_id to ensure SCAN_SOURCE_NODE relationships are created
                            subnet_dict = {
                                "id": getattr(subnet, "id", None),
                                "name": getattr(subnet, "name", None),
                                "type": "Microsoft.Network/subnets",
                                "location": vnet.get("location"),  # Inherit from parent
                                "properties": {},
                                "subscription_id": subscription_id,
                                "resource_group": rg,
                                "scan_id": vnet.get(
                                    "scan_id"
                                ),  # Required for SCAN_SOURCE_NODE relationship
                                "tenant_id": vnet.get(
                                    "tenant_id"
                                ),  # Required for SCAN_SOURCE_NODE relationship
                            }
                            child_resources.append(subnet_dict)

                    except Exception as e:
                        logger.warning(
                            str(f"Failed to fetch subnets for {vnet_name}: {e}")
                        )

                subnet_count = len(
                    [
                        r
                        for r in child_resources
                        if r["type"] == "Microsoft.Network/subnets"
                    ]
                )
                logger.info(str(f"✅ Found {subnet_count} subnets"))

            except Exception as e:
                logger.warning(str(f"Failed to create network client: {e}"))

        # Discover automation runbooks
        if automation_accounts:
            logger.info(
                f"🔍 Discovering runbooks for {len(automation_accounts)} Automation Accounts..."
            )
            try:
                automation_client = AutomationClient(self.credential, subscription_id)

                for account in automation_accounts:
                    try:
                        rg = account.get("resource_group")
                        account_name = account.get("name")

                        if not rg or not account_name:
                            continue

                        # Fetch runbooks for this account
                        runbooks_pager = (
                            automation_client.runbook.list_by_automation_account(
                                rg, account_name
                            )
                        )

                        for runbook in runbooks_pager:
                            # FIX Issue #563: Include scan_id and tenant_id to ensure SCAN_SOURCE_NODE relationships are created
                            runbook_dict = {
                                "id": getattr(runbook, "id", None),
                                "name": getattr(runbook, "name", None),
                                "type": "Microsoft.Automation/automationAccounts/runbooks",
                                "location": account.get("location"),
                                "properties": {},
                                "subscription_id": subscription_id,
                                "resource_group": rg,
                                "scan_id": account.get(
                                    "scan_id"
                                ),  # Required for SCAN_SOURCE_NODE relationship
                                "tenant_id": account.get(
                                    "tenant_id"
                                ),  # Required for SCAN_SOURCE_NODE relationship
                            }
                            child_resources.append(runbook_dict)

                    except Exception as e:
                        logger.warning(
                            f"Failed to fetch runbooks for {account_name}: {e}"
                        )

                runbook_count = len(
                    [r for r in child_resources if "runbooks" in r["type"]]
                )
                logger.info(str(f"✅ Found {runbook_count} runbooks"))

            except Exception as e:
                logger.warning(str(f"Failed to create automation client: {e}"))

        # Discover DNS zone virtual network links (21 errors)
        dns_zones = [
            r
            for r in parent_resources
            if r.get("type") == "Microsoft.Network/privateDnsZones"
        ]
        if dns_zones:
            logger.info(
                f"🔍 Discovering virtual network links for {len(dns_zones)} DNS zones..."
            )
            try:
                network_client = NetworkManagementClient(
                    self.credential, subscription_id
                )

                for dns_zone in dns_zones:
                    try:
                        rg = dns_zone.get("resource_group")
                        zone_name = dns_zone.get("name")

                        if not rg or not zone_name:
                            continue

                        # Fetch virtual network links for this DNS zone
                        links_pager = network_client.virtual_network_links.list(
                            rg, zone_name
                        )

                        for link in links_pager:
                            # FIX Issue #563: Include scan_id and tenant_id to ensure SCAN_SOURCE_NODE relationships are created
                            link_dict = {
                                "id": getattr(link, "id", None),
                                "name": getattr(link, "name", None),
                                "type": "Microsoft.Network/privateDnsZones/virtualNetworkLinks",
                                "location": dns_zone.get("location"),
                                "properties": {},
                                "subscription_id": subscription_id,
                                "resource_group": rg,
                                "scan_id": dns_zone.get(
                                    "scan_id"
                                ),  # Required for SCAN_SOURCE_NODE relationship
                                "tenant_id": dns_zone.get(
                                    "tenant_id"
                                ),  # Required for SCAN_SOURCE_NODE relationship
                            }
                            child_resources.append(link_dict)

                    except Exception as e:
                        logger.warning(
                            str(f"Failed to fetch DNS links for {zone_name}: {e}")
                        )

                link_count = len(
                    [r for r in child_resources if "virtualNetworkLinks" in r["type"]]
                )
                logger.info(str(f"✅ Found {link_count} DNS zone links"))

            except Exception as e:
                logger.warning(str(f"Failed to discover DNS zone links: {e}"))

        # Discover VM extensions (123 resources in source)
        vms = [
            r
            for r in parent_resources
            if r.get("type") == "Microsoft.Compute/virtualMachines"
        ]
        if vms:
            logger.info(str(f"🔍 Discovering VM extensions for {len(vms)} VMs..."))
            try:
                from azure.mgmt.compute import (
                    ComputeManagementClient,  # type: ignore[import-untyped]
                )

                compute_client = ComputeManagementClient(
                    self.credential, subscription_id
                )

                for vm in vms:
                    try:
                        rg = vm.get("resource_group")
                        vm_name = vm.get("name")

                        if not rg or not vm_name:
                            continue

                        # Fetch extensions for this VM
                        extensions_pager = (
                            compute_client.virtual_machine_extensions.list(rg, vm_name)
                        )

                        for ext in extensions_pager:
                            # FIX Issue #563: Include scan_id and tenant_id to ensure SCAN_SOURCE_NODE relationships are created
                            ext_dict = {
                                "id": getattr(ext, "id", None),
                                "name": getattr(ext, "name", None),
                                "type": "Microsoft.Compute/virtualMachines/extensions",
                                "location": vm.get("location"),
                                "properties": {},
                                "subscription_id": subscription_id,
                                "resource_group": rg,
                                "scan_id": vm.get(
                                    "scan_id"
                                ),  # Required for SCAN_SOURCE_NODE relationship
                                "tenant_id": vm.get(
                                    "tenant_id"
                                ),  # Required for SCAN_SOURCE_NODE relationship
                            }
                            child_resources.append(ext_dict)

                    except Exception as e:
                        logger.warning(
                            f"Failed to fetch VM extensions for {vm_name}: {e}"
                        )

                ext_count = len(
                    [
                        r
                        for r in child_resources
                        if r["type"] == "Microsoft.Compute/virtualMachines/extensions"
                    ]
                )
                logger.info(str(f"✅ Found {ext_count} VM extensions"))

            except Exception as e:
                logger.warning(str(f"Failed to discover VM extensions: {e}"))

        # Discover SQL databases (child of SQL servers)
        sql_servers = [
            r for r in parent_resources if r.get("type") == "Microsoft.Sql/servers"
        ]
        if sql_servers:
            logger.info(
                f"🔍 Discovering databases for {len(sql_servers)} SQL servers..."
            )
            try:
                from azure.mgmt.sql import (
                    SqlManagementClient,  # type: ignore[import-untyped]
                )

                sql_client = SqlManagementClient(self.credential, subscription_id)

                for server in sql_servers:
                    try:
                        rg = server.get("resource_group")
                        server_name = server.get("name")

                        if not rg or not server_name:
                            continue

                        # Fetch databases for this server
                        databases_pager = sql_client.databases.list_by_server(
                            rg, server_name
                        )

                        for db in databases_pager:
                            # FIX Issue #563: Include scan_id and tenant_id to ensure SCAN_SOURCE_NODE relationships are created
                            db_dict = {
                                "id": getattr(db, "id", None),
                                "name": getattr(db, "name", None),
                                "type": "Microsoft.Sql/servers/databases",
                                "location": server.get("location"),
                                "properties": {},
                                "subscription_id": subscription_id,
                                "resource_group": rg,
                                "scan_id": server.get(
                                    "scan_id"
                                ),  # Required for SCAN_SOURCE_NODE relationship
                                "tenant_id": server.get(
                                    "tenant_id"
                                ),  # Required for SCAN_SOURCE_NODE relationship
                            }
                            child_resources.append(db_dict)

                    except Exception as e:
                        logger.warning(
                            f"Failed to fetch databases for {server_name}: {e}"
                        )

                db_count = len(
                    [
                        r
                        for r in child_resources
                        if r["type"] == "Microsoft.Sql/servers/databases"
                    ]
                )
                logger.info(str(f"✅ Found {db_count} SQL databases"))

            except Exception as e:
                logger.warning(str(f"Failed to discover SQL databases: {e}"))

        # Discover PostgreSQL configurations
        pg_servers = [
            r
            for r in parent_resources
            if r.get("type")
            in [
                "Microsoft.DBforPostgreSQL/servers",
                "Microsoft.DBforPostgreSQL/flexibleServers",
            ]
        ]
        if pg_servers:
            logger.info(
                f"🔍 Discovering configurations for {len(pg_servers)} PostgreSQL servers..."
            )
            try:
                from azure.mgmt.rdbms.postgresql import (
                    PostgreSQLManagementClient,  # type: ignore[import-untyped]
                )

                pg_client = PostgreSQLManagementClient(self.credential, subscription_id)

                for server in pg_servers:
                    try:
                        rg = server.get("resource_group")
                        server_name = server.get("name")

                        if not rg or not server_name:
                            continue

                        # Fetch configurations for this server
                        try:
                            configs_pager = pg_client.configurations.list_by_server(
                                rg, server_name
                            )

                            for config in configs_pager:
                                # FIX Issue #563: Include scan_id and tenant_id to ensure SCAN_SOURCE_NODE relationships are created
                                config_dict = {
                                    "id": getattr(config, "id", None),
                                    "name": getattr(config, "name", None),
                                    "type": "Microsoft.DBforPostgreSQL/servers/configurations",
                                    "location": server.get("location"),
                                    "properties": {},
                                    "subscription_id": subscription_id,
                                    "resource_group": rg,
                                    "scan_id": server.get(
                                        "scan_id"
                                    ),  # Required for SCAN_SOURCE_NODE relationship
                                    "tenant_id": server.get(
                                        "tenant_id"
                                    ),  # Required for SCAN_SOURCE_NODE relationship
                                }
                                child_resources.append(config_dict)
                        except Exception:
                            # Might be flexibleServers which use different API
                            pass

                    except Exception as e:
                        logger.warning(
                            f"Failed to fetch PostgreSQL configs for {server_name}: {e}"
                        )

                config_count = len(
                    [
                        r
                        for r in child_resources
                        if "configurations" in r.get("type", "")
                    ]
                )
                logger.info(str(f"✅ Found {config_count} PostgreSQL configurations"))

            except Exception as e:
                logger.warning(
                    str(f"Failed to discover PostgreSQL configurations: {e}")
                )

        # Discover Container Registry webhooks
        registries = [
            r
            for r in parent_resources
            if r.get("type") == "Microsoft.ContainerRegistry/registries"
        ]
        if registries:
            logger.info(
                f"🔍 Discovering webhooks for {len(registries)} container registries..."
            )
            try:
                from azure.mgmt.containerregistry import (  # type: ignore[import-untyped]
                    ContainerRegistryManagementClient,
                )

                acr_client = ContainerRegistryManagementClient(
                    self.credential, subscription_id
                )

                for registry in registries:
                    try:
                        rg = registry.get("resource_group")
                        registry_name = registry.get("name")

                        if not rg or not registry_name:
                            continue

                        webhooks_pager = acr_client.webhooks.list(rg, registry_name)

                        for webhook in webhooks_pager:
                            # FIX Issue #563: Include scan_id and tenant_id to ensure SCAN_SOURCE_NODE relationships are created
                            webhook_dict = {
                                "id": getattr(webhook, "id", None),
                                "name": getattr(webhook, "name", None),
                                "type": "Microsoft.ContainerRegistry/registries/webhooks",
                                "location": registry.get("location"),
                                "properties": {},
                                "subscription_id": subscription_id,
                                "resource_group": rg,
                                "scan_id": registry.get(
                                    "scan_id"
                                ),  # Required for SCAN_SOURCE_NODE relationship
                                "tenant_id": registry.get(
                                    "tenant_id"
                                ),  # Required for SCAN_SOURCE_NODE relationship
                            }
                            child_resources.append(webhook_dict)

                    except Exception as e:
                        logger.warning(
                            f"Failed to fetch webhooks for {registry_name}: {e}"
                        )

                webhook_count = len(
                    [r for r in child_resources if "webhooks" in r.get("type", "")]
                )
                logger.info(
                    str(f"✅ Found {webhook_count} container registry webhooks")
                )

            except Exception as e:
                logger.warning(
                    str(f"Failed to discover container registry webhooks: {e}")
                )

        # Discover DevTest Lab child resources (GAP-020: Issue #315)
        devtest_labs = [
            r for r in parent_resources if r.get("type") == "Microsoft.DevTestLab/labs"
        ]
        if devtest_labs:
            logger.info(
                f"🔍 Discovering child resources for {len(devtest_labs)} DevTest Labs..."
            )
            try:
                from azure.mgmt.devtestlabs import (  # type: ignore[import-untyped]
                    DevTestLabsClient,
                )

                devtest_client = DevTestLabsClient(self.credential, subscription_id)

                for lab in devtest_labs:
                    try:
                        rg = lab.get("resource_group")
                        lab_name = lab.get("name")

                        if not rg or not lab_name:
                            continue

                        # Discover Virtual Machines
                        try:
                            vms_pager = devtest_client.virtual_machines.list(
                                rg, lab_name
                            )

                            for vm in vms_pager:
                                # FIX Issue #563: Include scan_id and tenant_id
                                vm_dict = {
                                    "id": getattr(vm, "id", None),
                                    "name": getattr(vm, "name", None),
                                    "type": "Microsoft.DevTestLab/labs/virtualMachines",
                                    "location": lab.get("location"),
                                    "properties": {},
                                    "subscription_id": subscription_id,
                                    "resource_group": rg,
                                    "scan_id": lab.get("scan_id"),
                                    "tenant_id": lab.get("tenant_id"),
                                }
                                child_resources.append(vm_dict)
                        except Exception as e:
                            logger.warning(
                                f"Failed to fetch VMs for lab {lab_name}: {e}"
                            )

                        # Discover Policies
                        try:
                            policies_pager = devtest_client.policies.list(
                                rg, lab_name, "default"
                            )

                            for policy in policies_pager:
                                # FIX Issue #563: Include scan_id and tenant_id
                                policy_dict = {
                                    "id": getattr(policy, "id", None),
                                    "name": getattr(policy, "name", None),
                                    "type": "Microsoft.DevTestLab/labs/policysets/policies",
                                    "location": lab.get("location"),
                                    "properties": {},
                                    "subscription_id": subscription_id,
                                    "resource_group": rg,
                                    "scan_id": lab.get("scan_id"),
                                    "tenant_id": lab.get("tenant_id"),
                                }
                                child_resources.append(policy_dict)
                        except Exception as e:
                            logger.warning(
                                f"Failed to fetch policies for lab {lab_name}: {e}"
                            )

                        # Discover Schedules
                        try:
                            schedules_pager = devtest_client.schedules.list(
                                rg, lab_name
                            )

                            for schedule in schedules_pager:
                                # FIX Issue #563: Include scan_id and tenant_id
                                schedule_dict = {
                                    "id": getattr(schedule, "id", None),
                                    "name": getattr(schedule, "name", None),
                                    "type": "Microsoft.DevTestLab/schedules",
                                    "location": lab.get("location"),
                                    "properties": {},
                                    "subscription_id": subscription_id,
                                    "resource_group": rg,
                                    "scan_id": lab.get("scan_id"),
                                    "tenant_id": lab.get("tenant_id"),
                                }
                                child_resources.append(schedule_dict)
                        except Exception as e:
                            logger.warning(
                                f"Failed to fetch schedules for lab {lab_name}: {e}"
                            )

                        # Discover Virtual Networks
                        try:
                            vnets_pager = devtest_client.virtual_networks.list(
                                rg, lab_name
                            )

                            for vnet in vnets_pager:
                                # FIX Issue #563: Include scan_id and tenant_id
                                vnet_dict = {
                                    "id": getattr(vnet, "id", None),
                                    "name": getattr(vnet, "name", None),
                                    "type": "Microsoft.DevTestLab/labs/virtualnetworks",
                                    "location": lab.get("location"),
                                    "properties": {},
                                    "subscription_id": subscription_id,
                                    "resource_group": rg,
                                    "scan_id": lab.get("scan_id"),
                                    "tenant_id": lab.get("tenant_id"),
                                }
                                child_resources.append(vnet_dict)
                        except Exception as e:
                            logger.warning(
                                f"Failed to fetch virtual networks for lab {lab_name}: {e}"
                            )

                    except Exception as e:
                        logger.warning(f"Failed to process DevTest Lab {lab_name}: {e}")

                # Log counts for each DevTest Lab child resource type
                devtest_vm_count = len(
                    [
                        r
                        for r in child_resources
                        if r["type"] == "Microsoft.DevTestLab/labs/virtualMachines"
                    ]
                )
                devtest_policy_count = len(
                    [
                        r
                        for r in child_resources
                        if r["type"] == "Microsoft.DevTestLab/labs/policysets/policies"
                    ]
                )
                devtest_schedule_count = len(
                    [
                        r
                        for r in child_resources
                        if r["type"] == "Microsoft.DevTestLab/schedules"
                    ]
                )
                devtest_vnet_count = len(
                    [
                        r
                        for r in child_resources
                        if r["type"] == "Microsoft.DevTestLab/labs/virtualnetworks"
                    ]
                )
                logger.info(
                    f"✅ Found {devtest_vm_count} DevTest Lab VMs, "
                    f"{devtest_policy_count} policies, "
                    f"{devtest_schedule_count} schedules, "
                    f"{devtest_vnet_count} virtual networks"
                )

            except Exception as e:
                logger.warning(f"Failed to discover DevTest Lab child resources: {e}")

        # Log final Phase 1.6 summary
        child_type_counts = {}
        for child in child_resources:
            child_type = child.get("type", "unknown")
            child_type_counts[child_type] = child_type_counts.get(child_type, 0) + 1

        logger.info(
            f"✅ Phase 1.6 complete: {len(child_resources)} child resources discovered across {len(child_type_counts)} types"
        )
        logger.debug(str(f"Child resource breakdown: {child_type_counts}"))

        return child_resources

    async def discover_diagnostic_settings(
        self,
        subscription_id: str,
        parent_resources: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Discover diagnostic settings for resources that support them.

        Diagnostic settings send resource logs and metrics to destinations like
        Log Analytics workspaces, Storage Accounts, and Event Hubs. Not all
        resource types support diagnostic settings, so we handle unsupported
        resources gracefully.

        Args:
            subscription_id: Azure subscription ID
            parent_resources: List of resources to check for diagnostic settings

        Returns:
            List of diagnostic setting dictionaries in resource format

        Raises:
            No exceptions - handles permission and unsupported resource errors gracefully
        """
        logger.info(
            f"📊 Discovering diagnostic settings for {len(parent_resources)} resources..."
        )

        diagnostic_settings = []

        try:
            # Create monitor client for diagnostic settings API
            monitor_client = self.monitor_client_factory(
                self.credential, subscription_id
            )

            # Resource types that commonly support diagnostic settings
            # This is not exhaustive - Azure adds support for new types regularly
            supported_types = {
                "Microsoft.KeyVault/vaults",
                "Microsoft.Storage/storageAccounts",
                "Microsoft.Network/networkSecurityGroups",
                "Microsoft.Network/applicationGateways",
                "Microsoft.Network/loadBalancers",
                "Microsoft.Network/virtualNetworkGateways",
                "Microsoft.Network/publicIPAddresses",
                "Microsoft.Sql/servers/databases",
                "Microsoft.DBforPostgreSQL/servers",
                "Microsoft.DBforPostgreSQL/flexibleServers",
                "Microsoft.DBforMySQL/servers",
                "Microsoft.DBforMariaDB/servers",
                "Microsoft.Compute/virtualMachines",
                "Microsoft.Web/sites",
                "Microsoft.Logic/workflows",
                "Microsoft.EventHub/namespaces",
                "Microsoft.ServiceBus/namespaces",
                "Microsoft.Automation/automationAccounts",
                "Microsoft.ContainerRegistry/registries",
                "Microsoft.Network/virtualNetworks",
            }

            # Filter to resources that likely support diagnostic settings
            candidate_resources = [
                r for r in parent_resources if r.get("type") in supported_types
            ]

            logger.info(
                f"Found {len(candidate_resources)} resources with potential diagnostic settings support"
            )

            for resource in candidate_resources:
                try:
                    resource_id = resource.get("id")
                    if not resource_id:
                        continue

                    # Fetch diagnostic settings for this resource
                    # Azure API: GET /subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/{resourceProviderNamespace}/{resourceType}/{resourceName}/providers/microsoft.insights/diagnosticSettings
                    settings_pager = monitor_client.diagnostic_settings.list(
                        resource_uri=resource_id
                    )

                    for setting in settings_pager:
                        # Extract diagnostic setting properties
                        setting_id = getattr(setting, "id", None)
                        setting_name = getattr(setting, "name", None)

                        if not setting_id or not setting_name:
                            continue

                        # Get diagnostic setting configuration
                        logs = getattr(setting, "logs", []) or []
                        metrics = getattr(setting, "metrics", []) or []
                        workspace_id = getattr(setting, "workspace_id", None)
                        storage_account_id = getattr(
                            setting, "storage_account_id", None
                        )
                        event_hub_authorization_rule_id = getattr(
                            setting, "event_hub_authorization_rule_id", None
                        )
                        event_hub_name = getattr(setting, "event_hub_name", None)

                        # Convert to resource format
                        diagnostic_dict = {
                            "id": setting_id,
                            "name": setting_name,
                            "type": "Microsoft.Insights/diagnosticSettings",
                            "location": None,  # Diagnostic settings are not location-specific
                            "tags": {},
                            "properties": {
                                "logs": [
                                    {
                                        "category": getattr(log, "category", None),
                                        "enabled": getattr(log, "enabled", False),
                                    }
                                    for log in logs
                                ],
                                "metrics": [
                                    {
                                        "category": getattr(metric, "category", None),
                                        "enabled": getattr(metric, "enabled", False),
                                    }
                                    for metric in metrics
                                ],
                                "workspaceId": workspace_id,
                                "storageAccountId": storage_account_id,
                                "eventHubAuthorizationRuleId": event_hub_authorization_rule_id,
                                "eventHubName": event_hub_name,
                            },
                            "subscription_id": subscription_id,
                            "resource_group": resource.get("resource_group"),
                            # Preserve scan metadata for relationships
                            "scan_id": resource.get("scan_id"),
                            "tenant_id": resource.get("tenant_id"),
                        }

                        diagnostic_settings.append(diagnostic_dict)

                except Exception as e:
                    # Handle unsupported resources and permission errors gracefully
                    error_msg = str(e).lower()

                    # Common error patterns
                    if any(
                        keyword in error_msg
                        for keyword in [
                            "does not support diagnostic settings",
                            "not supported",
                            "invalid resource type",
                            "resource type is not supported",
                        ]
                    ):
                        logger.debug(
                            f"Resource {resource.get('type')} does not support diagnostic settings"
                        )
                    elif any(
                        keyword in error_msg
                        for keyword in [
                            "forbidden",
                            "authorization",
                            "access denied",
                            "insufficient privileges",
                        ]
                    ):
                        logger.warning(
                            f"Insufficient permissions to read diagnostic settings for {resource.get('id')}"
                        )
                    elif "not found" in error_msg or "does not exist" in error_msg:
                        logger.debug(
                            f"Resource {resource.get('id')} not found or has no diagnostic settings"
                        )
                    else:
                        # Unknown error - log but continue
                        logger.warning(
                            f"Failed to fetch diagnostic settings for {resource.get('id')}: {e}"
                        )

            logger.info(f"✅ Discovered {len(diagnostic_settings)} diagnostic settings")

        except Exception:
            # Catch-all for unexpected errors
            logger.exception(
                f"Unexpected error discovering diagnostic settings in subscription {subscription_id}"
            )
            logger.warning(
                "Continuing discovery without diagnostic settings for this subscription"
            )

        return diagnostic_settings

    def _extract_resource_group_from_scope(self, scope: Optional[str]) -> Optional[str]:
        """
        Extract resource group name from a role assignment scope.

        Args:
            scope: Role assignment scope (e.g., /subscriptions/{sub}/resourceGroups/{rg})

        Returns:
            Resource group name if present in scope, None otherwise
        """
        if not scope:
            return None

        try:
            # Scope format: /subscriptions/{sub}/resourceGroups/{rg}/...
            segments = scope.strip("/").split("/")
            try:
                rg_index = segments.index("resourceGroups")
                if rg_index + 1 < len(segments):
                    return segments[rg_index + 1]
            except (ValueError, IndexError):
                # No resourceGroups in scope (subscription or management group level)
                return None
        except Exception:
            logger.debug(str(f"Could not extract resource group from scope: {scope}"))
            return None

    async def _handle_auth_fallback(
        self,
        discovery_func: Optional[Callable[..., Awaitable[List[Dict[str, Any]]]]] = None,
        *args: Any,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """
        Handle authentication failures by switching to AzureCliCredential.

        Args:
            discovery_func: Optional function to call with the new credential (for resources)
            *args, **kwargs: Arguments to pass to discovery_func

        Returns:
            List of discovered items if fallback succeeds

        Raises:
            AzureAuthenticationError: If both primary and fallback fail
        """
        logger.info("🔄 Attempting to authenticate with AzureCliCredential fallback...")
        try:
            cli_credential = AzureCliCredential()
            # Test the credential
            cli_credential.get_token("https://management.azure.com/.default")
            self.credential = cli_credential
            logger.info("✅ Successfully authenticated with AzureCliCredential")
            if discovery_func:
                return await discovery_func(self.credential, *args, **kwargs)
            # Default: retry subscription discovery with new credential (skip fallback to avoid recursion)
            return await self.discover_subscriptions(_skip_fallback=True)
        except CredentialUnavailableError as exc:
            logger.exception("AzureCliCredential unavailable")
            raise AzureAuthenticationError(
                "Azure CLI credential unavailable. Please ensure you are logged in with 'az login'.",
                tenant_id=self.config.tenant_id,
            ) from exc
        except Exception as exc:
            logger.exception("Azure CLI fallback authentication failed")
            raise AzureAuthenticationError(
                f"Azure CLI fallback authentication failed: {exc}",
                tenant_id=self.config.tenant_id,
            ) from exc

    async def _get_api_version_for_resource(
        self, resource_id: str, resource_client: Any
    ) -> str:
        """
        Get the appropriate API version for a resource type.

        Args:
            resource_id: Azure resource ID
            resource_client: ResourceManagementClient instance

        Returns:
            API version string
        """
        # Special handling for role assignments - they use Microsoft.Authorization API versions
        # regardless of their parent resource
        if "/providers/Microsoft.Authorization/roleAssignments/" in resource_id:
            return "2022-04-01"  # Stable API version for role assignments

        # Parse resource ID to extract provider and resource type
        parsed = self._parse_resource_id(resource_id)
        if not parsed.get("provider") or not parsed.get("resource_type"):
            # Default fallback API version
            return "2021-04-01"

        provider = parsed["provider"]
        resource_type = parsed["resource_type"]
        cache_key = f"{provider}/{resource_type}"

        # Check cache first
        if cache_key in self._api_version_cache:
            return self._api_version_cache[cache_key]

        try:
            # Query provider for available API versions
            provider_info = await asyncio.to_thread(
                resource_client.providers.get, provider
            )

            # Find the resource type in the provider
            for rt in provider_info.resource_types:
                if rt.resource_type.lower() == resource_type.lower():
                    if rt.api_versions:
                        # Use the latest stable version (first in list)
                        api_version = rt.api_versions[0]
                        self._api_version_cache[cache_key] = api_version
                        logger.debug(str(f"API version for {cache_key}: {api_version}"))
                        return api_version
        except Exception as e:
            logger.warning(str(f"Failed to get API version for {cache_key}: {e}"))

        # Default fallback
        default_version = "2021-04-01"
        self._api_version_cache[cache_key] = default_version
        return default_version

    async def _fetch_single_resource_with_properties(
        self,
        resource: Dict[str, Any],
        resource_client: Any,
        semaphore: asyncio.Semaphore,
    ) -> Dict[str, Any]:
        """
        Fetch full properties for a single resource.

        Args:
            resource: Basic resource dictionary
            resource_client: ResourceManagementClient instance
            semaphore: Semaphore for concurrency control

        Returns:
            Resource dictionary with full properties
        """
        resource_id = resource.get("id")
        if not resource_id:
            return resource

        # Bug #95: Skip Phase 2 for role assignments - they already have full properties from Phase 1.5
        # Role assignments use AuthorizationManagementClient, not ResourceManagementClient
        resource_type = resource.get("type", "")
        if resource_type == "Microsoft.Authorization/roleAssignments":
            logger.debug(
                f"Skipping Phase 2 property fetch for role assignment {resource_id} "
                "(already has full properties from Phase 1.5)"
            )
            return resource

        async with semaphore:
            try:
                # Get appropriate API version
                api_version = await self._get_api_version_for_resource(
                    resource_id, resource_client
                )

                # Fetch full resource details
                # Note: Azure SDK handles retries automatically with exponential backoff
                full_resource = await asyncio.to_thread(
                    resource_client.resources.get_by_id, resource_id, api_version
                )

                # Update resource with full properties
                props = getattr(full_resource, "properties", {})

                # Convert properties if it's an SDK object
                # Note: props might be an Azure SDK object, not a dict
                if props and not isinstance(props, dict) and hasattr(props, "as_dict"):
                    try:
                        resource["properties"] = props.as_dict()  # type: ignore
                    except Exception as e:
                        logger.debug(
                            f"Failed to convert properties to dict for {resource_id}: {e}"
                        )
                        resource["properties"] = {}
                else:
                    resource["properties"] = props if isinstance(props, dict) else {}

                logger.debug(
                    f"Successfully fetched properties for {resource.get('name')}"
                )
                return resource

            except Exception as e:
                # Log the specific error for debugging
                error_msg = str(e)
                if "InvalidApiVersionParameter" in error_msg:
                    logger.error(
                        f"Invalid API version for {resource_id}: {error_msg[:200]}"
                    )
                elif "AuthenticationFailed" in error_msg:
                    logger.error(
                        f"Authentication failed for {resource_id}: {error_msg[:200]}"
                    )
                elif "TooManyRequests" in error_msg:
                    logger.warning(
                        str(f"Rate limited for {resource_id}, SDK will retry")
                    )
                else:
                    logger.error(
                        str(f"Failed to fetch {resource_id}: {error_msg[:200]}")
                    )

                # Return resource with empty properties on failure
                return resource

    async def _fetch_resources_with_properties(
        self,
        resources: List[Dict[str, Any]],
        resource_client: Any,
        subscription_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Fetch full properties for all resources in parallel.

        Args:
            resources: List of basic resource dictionaries
            resource_client: ResourceManagementClient instance
            subscription_id: Azure subscription ID

        Returns:
            List of resources with full properties
        """
        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(self._max_build_threads)

        # Create tasks for all resources
        tasks = [
            self._fetch_single_resource_with_properties(
                resource, resource_client, semaphore
            )
            for resource in resources
        ]

        # Process in batches to manage memory for large subscriptions
        batch_size = 100
        all_resources = []

        for i in range(0, len(tasks), batch_size):
            batch = tasks[i : i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(tasks) + batch_size - 1) // batch_size

            logger.info(str(f"Processing batch {batch_num}/{total_batches}"))

            try:
                # Execute batch with timeout
                results = await asyncio.wait_for(
                    asyncio.gather(*batch, return_exceptions=True),
                    timeout=300,  # 5 minute timeout per batch
                )

                # Process results
                for result in results:
                    if isinstance(result, Exception):
                        logger.warning(str(f"Task failed with exception: {result}"))
                        # Still include the resource with empty properties
                        all_resources.append({"properties": {}})
                    elif result:
                        all_resources.append(result)

            except asyncio.TimeoutError:
                logger.error(str(f"Batch {batch_num} timed out after 5 minutes"))
                # Add resources from timed-out batch with empty properties
                for _ in batch:
                    all_resources.append({"properties": {}})

        success_count = len([r for r in all_resources if r.get("properties")])
        logger.info(
            f"✅ Successfully fetched properties for {success_count} "
            f"out of {len(all_resources)} resources"
        )

        return all_resources

    def _parse_resource_id(self, resource_id: Optional[str]) -> Dict[str, str]:
        """
        Parse an Azure resource ID to extract subscription_id, resource_group, provider, and resource_type.

        Args:
            resource_id: Azure resource ID in format:
                /subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/{provider}/{type}/{name}

        Returns:
            Dict containing parsed components if found, empty dict otherwise
        """
        if not resource_id:
            return {}

        try:
            # Split the resource ID into segments
            segments = resource_id.strip("/").split("/")

            result = {}

            # Find subscription ID (should be after 'subscriptions')
            try:
                subscription_index = segments.index("subscriptions")
                if subscription_index + 1 < len(segments):
                    result["subscription_id"] = segments[subscription_index + 1]
            except (ValueError, IndexError):
                logger.debug(
                    f"Could not parse subscription_id from resource ID: {resource_id}"
                )

            # Find resource group (should be after 'resourceGroups')
            try:
                rg_index = segments.index("resourceGroups")
                if rg_index + 1 < len(segments):
                    result["resource_group"] = segments[rg_index + 1]
            except (ValueError, IndexError):
                logger.debug(
                    f"Could not parse resource_group from resource ID: {resource_id}"
                )

            # Find provider and resource type (should be after 'providers')
            try:
                provider_index = segments.index("providers")
                if provider_index + 2 < len(segments):
                    result["provider"] = segments[provider_index + 1]
                    result["resource_type"] = segments[provider_index + 2]
            except (ValueError, IndexError):
                logger.debug(
                    f"Could not parse provider/resource_type from resource ID: {resource_id}"
                )

            return result
        except Exception:
            logger.exception(f"Error parsing resource ID: {resource_id}")
            return {}

    def get_cached_subscriptions(self) -> List[Dict[str, Any]]:
        """
        Get cached subscriptions without making API calls.

        Returns:
            List of cached subscription dictionaries
        """
        return self.subscriptions

    def clear_cache(self) -> None:
        """Clear cached subscription data."""
        self._subscriptions = []
        logger.debug("🗑️ Cleared subscription cache")

    def is_authenticated(self) -> bool:
        """
        Check if the service has valid Azure credentials.

        Returns:
            True if credentials appear to be valid
        """
        try:
            self.credential.get_token("https://management.azure.com/.default")
            return True
        except Exception:
            return False

    async def fetch_resource_by_id(self, resource_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a single resource by its full Azure resource ID.

        This method is used by RelationshipDependencyCollector to fetch
        cross-RG dependencies that weren't included in the initial filtered scan.

        Args:
            resource_id: Full Azure resource ID (e.g., /subscriptions/.../resourceGroups/.../providers/...)

        Returns:
            Resource dictionary with full properties, or None if fetch fails

        Example:
            >>> resource_id = "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic1"
            >>> resource = await service.fetch_resource_by_id(resource_id)
            >>> print(resource["name"])  # "nic1"
        """
        try:
            # Parse resource ID to extract subscription and resource group
            parsed = self._parse_resource_id(resource_id)
            subscription_id = parsed.get("subscription_id")
            resource_group = parsed.get("resource_group")

            if not subscription_id or not resource_group:
                logger.warning(
                    f"Could not parse subscription/RG from resource ID: {resource_id}"
                )
                return None

            # Create resource client for this subscription
            resource_client = self.resource_client_factory(
                self.credential, subscription_id
            )

            # Get API version for this resource type
            api_version = self._get_api_version_for_resource_id(
                resource_client, resource_id
            )

            if not api_version:
                logger.warning(
                    f"Could not determine API version for resource: {resource_id}"
                )
                return None

            # Fetch the resource using generic GET
            resource = resource_client.resources.get_by_id(
                resource_id, api_version=api_version
            )

            # Convert to dictionary format consistent with discovery
            resource_dict: Dict[str, Any] = {
                "id": resource_id,
                "name": getattr(resource, "name", None),
                "type": getattr(resource, "type", None),
                "location": getattr(resource, "location", None),
                "tags": dict(getattr(resource, "tags", {}) or {}),
                "properties": getattr(resource, "properties", {}) or {},
                "subscription_id": subscription_id,
                "resource_group": resource_group,
            }

            logger.debug(f"Successfully fetched resource: {resource_id}")
            return resource_dict

        except Exception as e:
            logger.warning(f"Failed to fetch resource by ID {resource_id}: {e}")
            return None

    def _get_api_version_for_resource_id(
        self, resource_client: Any, resource_id: str
    ) -> Optional[str]:
        """
        Get the appropriate API version for a resource ID.

        Uses caching to avoid repeated provider API calls.

        Args:
            resource_client: ResourceManagementClient instance
            resource_id: Full Azure resource ID

        Returns:
            API version string, or None if not found
        """
        # Parse resource type from ID
        # Format: /subscriptions/.../providers/{provider}/{resourceType}/...
        parts = resource_id.split("/")
        try:
            provider_index = parts.index("providers")
            if provider_index + 2 < len(parts):
                provider_namespace = parts[provider_index + 1]
                resource_type = parts[provider_index + 2]
                full_type = f"{provider_namespace}/{resource_type}"

                # Check cache first
                if full_type in self._api_version_cache:
                    return self._api_version_cache[full_type]

                # Fetch from Azure Resource Provider
                try:
                    provider = resource_client.providers.get(provider_namespace)
                    for resource_type_info in provider.resource_types:
                        if resource_type_info.resource_type == resource_type:
                            # Get latest non-preview API version
                            api_versions = [
                                v
                                for v in resource_type_info.api_versions
                                if "preview" not in v.lower()
                            ]
                            if api_versions:
                                api_version = api_versions[0]
                                self._api_version_cache[full_type] = api_version
                                return api_version
                            # Fall back to first API version (even if preview)
                            if resource_type_info.api_versions:
                                api_version = resource_type_info.api_versions[0]
                                self._api_version_cache[full_type] = api_version
                                return api_version
                except Exception as e:
                    logger.debug(
                        f"Failed to get API version for {full_type} from provider: {e}"
                    )

        except (ValueError, IndexError) as e:
            logger.debug(f"Failed to parse resource type from ID {resource_id}: {e}")

        return None

    async def ingest_delta_for_subscription(
        self, subscription_id: str, since_timestamp: Optional[str] = None
    ):
        """
        Trigger delta ingestion for a subscription using the ChangeFeedIngestionService.

        Args:
            subscription_id: Azure subscription ID.
            since_timestamp: Optional ISO8601 timestamp string.

        Returns:
            List of upserted or marked resources, or None if not configured.
        """
        if not self.change_feed_ingestion_service:
            raise RuntimeError("ChangeFeedIngestionService is not configured.")
        return await self.change_feed_ingestion_service.ingest_changes_for_subscription(
            subscription_id, since_timestamp=since_timestamp
        )


def create_azure_discovery_service(
    config: AzureTenantGrapherConfig,
    credential: Optional[Any] = None,
    subscription_client_factory: Optional[Callable[[Any], Any]] = None,
    resource_client_factory: Optional[Callable[[Any, str], Any]] = None,
    authorization_client_factory: Optional[Callable[[Any, str], Any]] = None,
    monitor_client_factory: Optional[Callable[[Any, str], Any]] = None,
    change_feed_ingestion_service: Optional[Any] = None,
) -> AzureDiscoveryService:
    """
    Factory function to create an Azure Discovery Service.

    Args:
        config: Configuration object
        credential: Optional Azure credential for dependency injection
        subscription_client_factory: Optional factory for SubscriptionClient (for testing)
        resource_client_factory: Optional factory for ResourceManagementClient (for testing)
        authorization_client_factory: Optional factory for AuthorizationManagementClient (for testing)
        monitor_client_factory: Optional factory for MonitorManagementClient (for testing)
        change_feed_ingestion_service: Optional ChangeFeedIngestionService for delta ingestion (for testing)

    Returns:
        AzureDiscoveryService: Configured service instance
    """
    return AzureDiscoveryService(
        config,
        credential,
        subscription_client_factory=subscription_client_factory,
        resource_client_factory=resource_client_factory,
        authorization_client_factory=authorization_client_factory,
        monitor_client_factory=monitor_client_factory,
        change_feed_ingestion_service=change_feed_ingestion_service,
    )
