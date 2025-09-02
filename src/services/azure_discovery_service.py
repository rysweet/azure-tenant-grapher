"""
Azure Discovery Service

This service handles all Azure subscription and resource discovery operations,
providing a focused interface for interacting with Azure APIs while following
proper error handling and dependency injection patterns.
"""

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional

from azure.core.exceptions import AzureError
from azure.identity import (
    AzureCliCredential,
    CredentialUnavailableError,
    DefaultAzureCredential,
)
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.subscription import SubscriptionClient

from ..config_manager import AzureTenantGrapherConfig
from ..exceptions import (
    AzureAuthenticationError,
    AzureDiscoveryError,
)

logger = logging.getLogger(__name__)


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
        change_feed_ingestion_service: Optional[Any] = None,
    ) -> None:
        """
        Initialize the Azure Discovery Service.

        Args:
            config: Configuration object containing Azure settings
            credential: Optional Azure credential (for dependency injection/testing)
            subscription_client_factory: Optional factory for SubscriptionClient (for testing)
            resource_client_factory: Optional factory for ResourceManagementClient (for testing)
            change_feed_ingestion_service: Optional ChangeFeedIngestionService for delta ingestion (for testing)
        """
        self.config = config
        self.credential = credential or DefaultAzureCredential()
        self.subscription_client_factory = (
            subscription_client_factory or SubscriptionClient
        )
        self.resource_client_factory = (
            resource_client_factory or ResourceManagementClient
        )
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
        self, _skip_fallback: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Discover all subscriptions in the tenant.

        Returns:
            List of subscription dictionaries with id and display_name

        Raises:
            AzureDiscoveryError: If subscription discovery fails
            AzureAuthenticationError: If authentication fails
        """
        logger.info(f"🔍 Discovering subscriptions in tenant {self.config.tenant_id}")

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
                self._subscriptions = subscriptions
                logger.info(f"✅ Discovered {len(subscriptions)} subscriptions total")

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
                        logger.warning(f"Azure CLI fallback failed: {fallback_exc}")
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
        from azure.core.exceptions import ClientAuthenticationError

        for attempt in range(1, max_attempts + 1):
            try:
                return await _attempt_discovery()
            except AzureError as exc:
                logger.warning(f"Attempt {attempt} failed: {exc}")
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
        self, subscription_id: str
    ) -> List[Dict[str, Any]]:
        """
        Discover all resources in a specific subscription with optional parallel property fetching.

        Args:
            subscription_id: Azure subscription ID

        Returns:
            List of resource dictionaries with full properties if max_build_threads > 0

        Raises:
            AzureDiscoveryError: If resource discovery fails
        """
        logger.info(f"🔍 Discovering resources in subscription {subscription_id}")

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
                    resource_basics.append(resource_dict)

                logger.info(
                    f"✅ Found {len(resource_basics)} resources in subscription {subscription_id}"
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
        from azure.core.exceptions import ClientAuthenticationError

        for attempt in range(1, max_attempts + 1):
            try:
                return await _attempt_discovery()
            except AzureError as exc:
                logger.warning(f"Attempt {attempt} failed: {exc}")
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
        self, subscription_ids: List[str], concurrency: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Discover resources for many subscriptions concurrently while ensuring that
        no more than *concurrency* discovery operations are in-flight at once.

        Args:
            subscription_ids: List of Azure subscription IDs.
            concurrency: Maximum number of concurrent discovery tasks (``>=1``).

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
                return await self.discover_resources_in_subscription(sub_id)

        # Kick off the tasks concurrently and wait for them to finish.
        results_nested: List[List[Dict[str, Any]]] = await asyncio.gather(
            *[_bounded_discover(sid) for sid in subscription_ids]
        )

        # Flatten [[...], [...]] → [...]
        flattened: List[Dict[str, Any]] = [
            item for sublist in results_nested for item in sublist
        ]
        return flattened

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
                        logger.debug(f"API version for {cache_key}: {api_version}")
                        return api_version
        except Exception as e:
            logger.warning(f"Failed to get API version for {cache_key}: {e}")

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
                    logger.warning(f"Rate limited for {resource_id}, SDK will retry")
                else:
                    logger.error(f"Failed to fetch {resource_id}: {error_msg[:200]}")

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

            logger.info(f"Processing batch {batch_num}/{total_batches}")

            try:
                # Execute batch with timeout
                results = await asyncio.wait_for(
                    asyncio.gather(*batch, return_exceptions=True),
                    timeout=300,  # 5 minute timeout per batch
                )

                # Process results
                for result in results:
                    if isinstance(result, Exception):
                        logger.warning(f"Task failed with exception: {result}")
                        # Still include the resource with empty properties
                        all_resources.append({"properties": {}})
                    elif result:
                        all_resources.append(result)

            except asyncio.TimeoutError:
                logger.error(f"Batch {batch_num} timed out after 5 minutes")
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
    change_feed_ingestion_service: Optional[Any] = None,
) -> AzureDiscoveryService:
    """
    Factory function to create an Azure Discovery Service.

    Args:
        config: Configuration object
        credential: Optional Azure credential for dependency injection
        subscription_client_factory: Optional factory for SubscriptionClient (for testing)
        resource_client_factory: Optional factory for ResourceManagementClient (for testing)
        change_feed_ingestion_service: Optional ChangeFeedIngestionService for delta ingestion (for testing)

    Returns:
        AzureDiscoveryService: Configured service instance
    """
    return AzureDiscoveryService(
        config,
        credential,
        subscription_client_factory=subscription_client_factory,
        resource_client_factory=resource_client_factory,
        change_feed_ingestion_service=change_feed_ingestion_service,
    )
