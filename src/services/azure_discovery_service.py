"""
Azure Discovery Service

This service handles all Azure subscription and resource discovery operations,
providing a focused interface for interacting with Azure APIs while following
proper error handling and dependency injection patterns.
"""

import logging
import subprocess
from typing import Any, Dict, List, Optional

from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.resource.subscriptions import SubscriptionClient

from ..config_manager import AzureTenantGrapherConfig
from ..exceptions import (
    AzureAuthenticationError,
    wrap_azure_exception,
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
        credential: Optional[DefaultAzureCredential] = None,
    ) -> None:
        """
        Initialize the Azure Discovery Service.

        Args:
            config: Configuration object containing Azure settings
            credential: Optional Azure credential (for dependency injection/testing)
        """
        self.config = config
        self.credential = credential or DefaultAzureCredential()
        self._subscriptions: List[Dict[str, Any]] = []

    @property
    def subscriptions(self) -> List[Dict[str, Any]]:
        """Get the cached list of discovered subscriptions."""
        return self._subscriptions.copy()

    async def discover_subscriptions(self) -> List[Dict[str, Any]]:
        """
        Discover all subscriptions in the tenant.

        Returns:
            List of subscription dictionaries with id, display_name, state, and tenant_id

        Raises:
            AzureSubscriptionError: If subscription discovery fails
            AzureAuthenticationError: If authentication fails
        """
        logger.info(f"🔍 Discovering subscriptions in tenant {self.config.tenant_id}")

        try:
            subscription_client = SubscriptionClient(self.credential)
            subscriptions: List[Dict[str, Any]] = []

            for subscription in subscription_client.subscriptions.list():
                # Explicitly cast subscription to Any to avoid type errors
                sub: Any = subscription
                subscription_dict: Dict[str, Any] = {
                    "id": getattr(sub, "subscription_id", None),
                    "display_name": getattr(sub, "display_name", None),
                    "state": getattr(sub, "state", None),
                    "tenant_id": getattr(sub, "tenant_id", None),
                }
                subscriptions.append(subscription_dict)
                logger.info(
                    f"📋 Found subscription: {getattr(sub, 'display_name', 'unknown')} "
                    f"({getattr(sub, 'subscription_id', 'unknown')})"
                )

            self._subscriptions = subscriptions
            logger.info(f"✅ Discovered {len(subscriptions)} subscriptions total")
            return subscriptions

        except Exception as exc:
            logger.error(f"❌ Error discovering subscriptions: {exc}")
            return await self._handle_authentication_fallback(exc)

    async def _handle_authentication_fallback(
        self, original_exception: Exception
    ) -> List[Dict[str, Any]]:
        """
        Handle authentication failures with Azure CLI fallback.

        Args:
            original_exception: The original exception that triggered fallback

        Returns:
            List of subscription dictionaries if fallback succeeds

        Raises:
            AzureAuthenticationError: If authentication and fallback both fail
            AzureSubscriptionError: If the original error is not authentication-related
        """
        error_str = str(original_exception).lower()
        auth_keywords = ["defaultazurecredential", "authentication", "token", "login"]

        if not any(keyword in error_str for keyword in auth_keywords):
            # Not an authentication error, wrap and re-raise
            context = {"tenant_id": self.config.tenant_id}
            raise wrap_azure_exception(
                original_exception, context
            ) from original_exception

        logger.info("🔄 Attempting to authenticate with Azure CLI fallback...")

        try:
            if not self.config.tenant_id:
                raise AzureAuthenticationError(
                    "Tenant ID is required for Azure CLI fallback authentication",
                    tenant_id=self.config.tenant_id,
                    cause=original_exception,
                )

            # Execute Azure CLI login
            cmd = ["az", "login", "--tenant", self.config.tenant_id]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            if result.returncode != 0:
                raise AzureAuthenticationError(
                    f"Azure CLI login failed: {result.stderr}",
                    tenant_id=self.config.tenant_id,
                    cause=original_exception,
                )

            logger.info("✅ Successfully authenticated with Azure CLI")
            logger.info("🔄 Retrying subscription discovery...")

            # Recreate credential and retry discovery
            self.credential = DefaultAzureCredential()
            return await self._retry_subscription_discovery()

        except subprocess.TimeoutExpired as timeout_exc:
            raise AzureAuthenticationError(
                "Azure CLI login timed out after 120 seconds",
                tenant_id=self.config.tenant_id,
                cause=timeout_exc,
                recovery_suggestion="Try running 'az login' manually or check network connectivity",
            ) from timeout_exc

        except FileNotFoundError as file_exc:
            raise AzureAuthenticationError(
                "Azure CLI not found. Please install Azure CLI",
                tenant_id=self.config.tenant_id,
                cause=file_exc,
                recovery_suggestion="Install Azure CLI from https://docs.microsoft.com/en-us/cli/azure/install-azure-cli",
            ) from file_exc

        except Exception as fallback_exc:
            raise AzureAuthenticationError(
                f"Azure CLI fallback authentication failed: {fallback_exc}",
                tenant_id=self.config.tenant_id,
                cause=original_exception,
            ) from fallback_exc

    async def _retry_subscription_discovery(self) -> List[Dict[str, Any]]:
        """
        Retry subscription discovery after successful authentication.

        Returns:
            List of subscription dictionaries

        Raises:
            AzureSubscriptionError: If retry fails
        """
        try:
            subscription_client = SubscriptionClient(self.credential)
            subscriptions: List[Dict[str, Any]] = []

            for subscription in subscription_client.subscriptions.list():
                sub: Any = subscription
                subscription_dict: Dict[str, Any] = {
                    "id": getattr(sub, "subscription_id", None),
                    "display_name": getattr(sub, "display_name", None),
                    "state": getattr(sub, "state", None),
                    "tenant_id": getattr(sub, "tenant_id", None),
                }
                subscriptions.append(subscription_dict)
                logger.info(
                    f"📋 Found subscription: {getattr(sub, 'display_name', 'unknown')} "
                    f"({getattr(sub, 'subscription_id', 'unknown')})"
                )

            self._subscriptions = subscriptions
            logger.info(f"✅ Discovered {len(subscriptions)} subscriptions total")
            return subscriptions

        except Exception as exc:
            context = {"tenant_id": self.config.tenant_id, "retry_attempt": True}
            raise wrap_azure_exception(exc, context) from exc

    async def discover_resources_in_subscription(
        self, subscription_id: str
    ) -> List[Dict[str, Any]]:
        """
        Discover all resources in a specific subscription.

        Args:
            subscription_id: Azure subscription ID

        Returns:
            List of resource dictionaries with comprehensive metadata

        Raises:
            AzureResourceDiscoveryError: If resource discovery fails
        """
        logger.info(f"🔍 Discovering resources in subscription {subscription_id}")

        try:
            resource_client = ResourceManagementClient(self.credential, subscription_id)
            resources: List[Dict[str, Any]] = []

            for resource in resource_client.resources.list():
                res: Any = resource
                res_id: Optional[str] = getattr(res, "id", None)

                # Extract resource group from resource ID
                resource_group = None
                if res_id and len(res_id.split("/")) > 4:
                    resource_group = res_id.split("/")[4]

                resource_dict: Dict[str, Any] = {
                    "id": res_id,
                    "name": getattr(res, "name", None),
                    "type": getattr(res, "type", None),
                    "location": getattr(res, "location", None),
                    "resource_group": resource_group,
                    "subscription_id": subscription_id,
                    "tags": dict(getattr(res, "tags", {}) or {}),
                    "kind": getattr(res, "kind", None),
                    "sku": getattr(res, "sku", None),
                }
                resources.append(resource_dict)

            logger.info(
                f"✅ Found {len(resources)} resources in subscription {subscription_id}"
            )
            logger.debug(f"Resource IDs: {[r['id'] for r in resources]}")
            return resources

        except Exception as exc:
            logger.error(
                f"❌ Error discovering resources in subscription {subscription_id}: {exc}"
            )
            context = {
                "subscription_id": subscription_id,
                "tenant_id": self.config.tenant_id,
            }
            raise wrap_azure_exception(exc, context) from exc

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
            # Simple check - attempt to get token
            self.credential.get_token("https://management.azure.com/.default")
            return True
        except Exception:
            return False


def create_azure_discovery_service(
    config: AzureTenantGrapherConfig,
    credential: Optional[DefaultAzureCredential] = None,
) -> AzureDiscoveryService:
    """
    Factory function to create an Azure Discovery Service.

    Args:
        config: Configuration object
        credential: Optional Azure credential for dependency injection

    Returns:
        AzureDiscoveryService: Configured service instance
    """
    return AzureDiscoveryService(config, credential)
