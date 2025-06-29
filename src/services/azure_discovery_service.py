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
    ) -> None:
        """
        Initialize the Azure Discovery Service.

        Args:
            config: Configuration object containing Azure settings
            credential: Optional Azure credential (for dependency injection/testing)
            subscription_client_factory: Optional factory for SubscriptionClient (for testing)
            resource_client_factory: Optional factory for ResourceManagementClient (for testing)
        """
        self.config = config
        self.credential = credential or DefaultAzureCredential()
        self.subscription_client_factory = (
            subscription_client_factory or SubscriptionClient
        )
        self.resource_client_factory = (
            resource_client_factory or ResourceManagementClient
        )
        # Maximum retry attempts for transient Azure errors (default 3)
        self._max_retries: int = (
            getattr(getattr(config, "processing", None), "max_retries", 3) or 3
        )
        self._subscriptions: List[Dict[str, Any]] = []

    @property
    def subscriptions(self) -> List[Dict[str, Any]]:
        """Get the cached list of discovered subscriptions."""
        return self._subscriptions.copy()

    async def discover_subscriptions(self) -> List[Dict[str, Any]]:
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
        Discover all resources in a specific subscription.

        Args:
            subscription_id: Azure subscription ID

        Returns:
            List of resource dictionaries with minimal fields including subscription_id and resource_group

        Raises:
            AzureDiscoveryError: If resource discovery fails
        """
        logger.info(f"🔍 Discovering resources in subscription {subscription_id}")

        async def _attempt_discovery() -> List[Dict[str, Any]]:
            try:
                resource_client = self.resource_client_factory(
                    self.credential, subscription_id
                )
                resources: List[Dict[str, Any]] = []
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
                        "subscription_id": parsed_info.get(
                            "subscription_id", subscription_id
                        ),
                        "resource_group": parsed_info.get("resource_group"),
                    }
                    resources.append(resource_dict)
                logger.info(
                    f"✅ Found {len(resources)} resources in subscription {subscription_id}"
                )
                logger.debug(f"Resource IDs: {[r['id'] for r in resources]}")
                return resources
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
            # Default: retry subscription discovery with new credential
            return await self.discover_subscriptions()
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

    def _parse_resource_id(self, resource_id: Optional[str]) -> Dict[str, str]:
        """
        Parse an Azure resource ID to extract subscription_id and resource_group.

        Args:
            resource_id: Azure resource ID in format:
                /subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/{provider}/{type}/{name}

        Returns:
            Dict containing 'subscription_id' and 'resource_group' if found, empty dict otherwise
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


def create_azure_discovery_service(
    config: AzureTenantGrapherConfig,
    credential: Optional[Any] = None,
    subscription_client_factory: Optional[Callable[[Any], Any]] = None,
    resource_client_factory: Optional[Callable[[Any, str], Any]] = None,
) -> AzureDiscoveryService:
    """
    Factory function to create an Azure Discovery Service.

    Args:
        config: Configuration object
        credential: Optional Azure credential for dependency injection
        subscription_client_factory: Optional factory for SubscriptionClient (for testing)
        resource_client_factory: Optional factory for ResourceManagementClient (for testing)

    Returns:
        AzureDiscoveryService: Configured service instance
    """
    return AzureDiscoveryService(
        config,
        credential,
        subscription_client_factory=subscription_client_factory,
        resource_client_factory=resource_client_factory,
    )
