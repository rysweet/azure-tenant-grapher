"""
Resource Existence Validation for Smart Import Blocks

This validator checks if Azure resources actually exist before generating
import blocks. This prevents Terraform import failures due to missing resources.

Issue #422: Smart Import Blocks with Existence Checking
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from azure.core.exceptions import (
    AzureError,
    HttpResponseError,
    ResourceNotFoundError,
    ServiceRequestError,
)
from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient

logger = logging.getLogger(__name__)


@dataclass
class ResourceExistenceResult:
    """Result of resource existence check."""

    resource_id: str
    exists: bool
    error: Optional[str] = None
    cached: bool = False


class ResourceExistenceValidator:
    """
    Validates if Azure resources exist before generating import blocks.

    This validator uses Azure SDK to check if resources actually exist in the
    target subscription, preventing Terraform import failures.

    Features:
    - Checks resource existence using Azure Resource Management API
    - Caches results to minimize API calls
    - Handles transient errors with retry logic
    - Graceful error handling with detailed logging
    """

    def __init__(
        self,
        subscription_id: str,
        credential: Optional[Any] = None,
        tenant_id: Optional[str] = None,  # Fix #608: Tenant for cross-tenant auth
        max_retries: int = 3,
        cache_ttl: int = 300,
    ):
        """
        Initialize the resource existence validator.

        Args:
            subscription_id: Target Azure subscription ID
            credential: Azure credential (defaults to DefaultAzureCredential)
            tenant_id: Target tenant ID for cross-tenant deployments
            max_retries: Maximum retry attempts for transient errors
            cache_ttl: Cache time-to-live in seconds (default 5 minutes)
        """
        self.subscription_id = subscription_id
        self.tenant_id = tenant_id

        # DEBUG: Log what we're initializing with
        logger.info(
            f"🔍 ResourceExistenceValidator init: tenant_id={tenant_id}, subscription={subscription_id}"
        )

        # Fix #608: Use EXPLICIT SP credentials, not DefaultAzureCredential
        # For cross-tenant, we MUST use ClientSecretCredential with explicit SP
        if credential:
            self.credential = credential
            logger.info(
                str(f"   Using provided credential: {type(credential).__name__}")
            )
        elif tenant_id:
            # Use explicit SP from environment (same as deployment uses)
            import os

            from azure.identity import ClientSecretCredential

            client_id = os.getenv("AZURE_TENANT_2_CLIENT_ID") or os.getenv(
                "AZURE_CLIENT_ID"
            )
            client_secret = os.getenv("AZURE_TENANT_2_CLIENT_SECRET") or os.getenv(
                "AZURE_CLIENT_SECRET"
            )
            logger.info(str(f"   Tenant ID provided: {tenant_id}"))
            logger.info(
                f"   Client ID from env: {client_id[:20]}..."
                if client_id
                else "   Client ID: NOT FOUND"
            )
            if client_id and client_secret:
                self.credential = ClientSecretCredential(
                    tenant_id=tenant_id,
                    client_id=client_id,
                    client_secret=client_secret,
                )
                logger.info("   ✅ Created ClientSecretCredential")
            else:
                # Fallback
                logger.warning(
                    "   ⚠️ No SP credentials in env, using DefaultAzureCredential"
                )
                self.credential = DefaultAzureCredential(
                    additionally_allowed_tenants=["*"]
                )
        else:
            logger.info("   No tenant_id, using DefaultAzureCredential")
            self.credential = DefaultAzureCredential()
        self.max_retries = max_retries
        self.cache_ttl = cache_ttl

        # Cache for existence checks: {resource_id: (exists, timestamp)}
        self._cache: Dict[str, tuple[bool, float]] = {}

        # Lazy initialization of resource client
        self._resource_client: Optional[ResourceManagementClient] = None

    @property
    def resource_client(self) -> ResourceManagementClient:
        """Get or create ResourceManagementClient."""
        if self._resource_client is None:
            self._resource_client = ResourceManagementClient(
                credential=self.credential, subscription_id=self.subscription_id
            )
        return self._resource_client

    def check_resource_exists(self, resource_id: str) -> ResourceExistenceResult:
        """
        Check if an Azure resource exists.

        Args:
            resource_id: Full Azure resource ID (e.g., /subscriptions/.../resourceGroups/...)

        Returns:
            ResourceExistenceResult with existence status
        """
        # Check cache first
        cached_result = self._check_cache(resource_id)
        if cached_result is not None:
            logger.debug(str(f"Cache hit for resource: {resource_id}"))
            return ResourceExistenceResult(
                resource_id=resource_id, exists=cached_result, cached=True
            )

        # Perform existence check with retry logic
        for attempt in range(self.max_retries):
            try:
                exists = self._check_resource_exists_internal(resource_id)
                # Cache the result
                self._cache[resource_id] = (exists, time.time())

                logger.debug(
                    f"Resource existence check: {resource_id} -> {'EXISTS' if exists else 'NOT FOUND'}"
                )

                return ResourceExistenceResult(
                    resource_id=resource_id, exists=exists, cached=False
                )

            except (ServiceRequestError, AzureError) as e:
                # Transient errors - retry
                if attempt < self.max_retries - 1:
                    logger.warning(
                        f"Transient error checking resource {resource_id} "
                        f"(attempt {attempt + 1}/{self.max_retries}): {e}"
                    )
                    time.sleep(2**attempt)  # Exponential backoff
                    continue
                else:
                    # Max retries exceeded
                    logger.error(
                        f"Failed to check resource existence after {self.max_retries} attempts: {resource_id}"
                    )
                    return ResourceExistenceResult(
                        resource_id=resource_id,
                        exists=False,
                        error=f"Max retries exceeded: {e!s}",
                    )

            except Exception as e:
                # Unexpected errors
                logger.error(
                    str(f"Unexpected error checking resource {resource_id}: {e}")
                )
                return ResourceExistenceResult(
                    resource_id=resource_id, exists=False, error=str(e)
                )

        # Should not reach here, but handle gracefully
        return ResourceExistenceResult(
            resource_id=resource_id, exists=False, error="Unknown error"
        )

    def _check_resource_exists_internal(self, resource_id: str) -> bool:
        """
        Internal method to check if a resource exists using Azure SDK.

        Args:
            resource_id: Full Azure resource ID

        Returns:
            True if resource exists, False otherwise

        Raises:
            AzureError: For transient errors that should be retried
        """
        try:
            # Use the generic resources API to check existence
            # This works for all resource types
            response = self.resource_client.resources.get_by_id(
                resource_id=resource_id, api_version=self._get_api_version(resource_id)
            )

            # If we get here without exception, resource exists
            return response is not None

        except ResourceNotFoundError:
            # Resource doesn't exist (404) - this is expected, not an error
            return False

        except HttpResponseError as e:
            # Check if it's a 404 (not found)
            if e.status_code == 404:
                return False
            # Other HTTP errors might be transient
            raise

        except Exception:
            # Re-raise to be caught by retry logic
            raise

    def _get_api_version(self, resource_id: str) -> str:
        """
        Get appropriate API version for a resource type.

        Args:
            resource_id: Full Azure resource ID

        Returns:
            API version string
        """
        # Parse resource type from ID
        # Format: /subscriptions/{sub}/resourceGroups/{rg}/providers/{provider}/{type}/{name}
        parts = resource_id.split("/")

        try:
            # Find the provider and resource type
            if "providers" in parts:
                provider_idx = parts.index("providers")
                if provider_idx + 2 < len(parts):
                    provider = parts[provider_idx + 1]
                    resource_type = parts[provider_idx + 2]

                    # Bug #101: Handle provider-specific API versions for ambiguous types
                    # Databricks workspaces need 2024-05-01, OperationalInsights need 2023-09-01
                    if (
                        resource_type == "workspaces"
                        and provider == "Microsoft.Databricks"
                    ):
                        return "2024-05-01"

                    # Use known API versions for common types
                    # Updated 2025-11-28: Added missing resource types to fix validation errors
                    # Bug #97: Added KeyVault API version to fix validation failures
                    api_versions = {
                        "resourceGroups": "2021-04-01",
                        "storageAccounts": "2023-01-01",
                        "virtualMachines": "2023-03-01",
                        "virtualNetworks": "2023-05-01",
                        "subnets": "2023-05-01",
                        "networkInterfaces": "2023-05-01",
                        "vaults": "2023-02-01",  # KeyVault - Bug #97 fix
                        "disks": "2023-04-02",
                        "userAssignedIdentities": "2023-01-31",
                        "publicIPAddresses": "2023-05-01",
                        "networkSecurityGroups": "2023-05-01",
                        # Note: "workspaces" is ambiguous - used by both Databricks and OperationalInsights
                        # This default is for OperationalInsights (most common)
                        "workspaces": "2023-09-01",  # OperationalInsights workspaces
                        "networkWatchers": "2023-05-01",
                        "accounts": "2023-05-01",
                        "loadBalancers": "2023-05-01",
                        "applicationGateways": "2023-05-01",
                        "managedClusters": "2023-10-01",  # AKS
                        "privateDnsZones": "2020-06-01",
                        "privateEndpoints": "2023-05-01",
                        # NEW: Added to fix validation errors
                        "serverFarms": "2024-04-01",  # App Service Plans
                        "namespaces": "2024-01-01",  # Service Bus
                        "registries": "2022-12-01",  # Bug #100: Container Registry (was using fallback 2021-04-01)
                        "databaseAccounts": "2024-08-15",  # Bug #102: CosmosDB (was using fallback 2021-04-01)
                        "managedEnvironments": "2024-03-01",  # Container Apps
                        "dnszones": "2018-05-01",  # DNS Zones (lowercase)
                        "dnsZones": "2018-05-01",  # Bug #103: DNS Zones (camelCase variant)
                        "flexibleServers": "2024-08-01",  # PostgreSQL Flexible Servers
                        "Redis": "2024-03-01",  # Bug #104: Redis Cache
                        "actiongroups": "2023-01-01",  # Bug #105: Action Groups (lowercase variant)
                        "actionGroups": "2023-01-01",  # Bug #105: Action Groups (camelCase variant)
                        "querypacks": "2023-09-01",  # Bug #106: Query Packs (lowercase variant)
                        "queryPacks": "2023-09-01",  # Bug #106: Query Packs (camelCase variant)
                        "accessConnectors": "2024-05-01",  # Databricks Access Connectors
                        "components": "2020-02-02",  # Application Insights
                        "staticSites": "2023-01-01",  # Static Web Apps
                        "labs": "2018-09-15",  # DevTest Labs
                        "galleries": "2023-07-03",  # Compute Galleries
                    }

                    if resource_type in api_versions:
                        return api_versions[resource_type]

        except (ValueError, IndexError):
            pass

        # Default to a stable API version for resource groups
        if "resourceGroups" in resource_id and "/providers/" not in resource_id:
            return "2021-04-01"

        # Generic fallback
        return "2021-04-01"

    def _check_cache(self, resource_id: str) -> Optional[bool]:
        """
        Check if resource existence is cached and still valid.

        Args:
            resource_id: Full Azure resource ID

        Returns:
            Cached existence status or None if not cached/expired
        """
        if resource_id not in self._cache:
            return None

        exists, timestamp = self._cache[resource_id]

        # Check if cache is still valid
        if time.time() - timestamp > self.cache_ttl:
            # Cache expired
            del self._cache[resource_id]
            return None

        return exists

    def clear_cache(self) -> None:
        """Clear the existence check cache."""
        self._cache.clear()
        logger.debug("Cleared resource existence cache")

    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats (total, valid, expired)
        """
        total = len(self._cache)
        valid = sum(
            1
            for _, (_, timestamp) in self._cache.items()
            if time.time() - timestamp <= self.cache_ttl
        )
        expired = total - valid

        return {"total": total, "valid": valid, "expired": expired}

    def batch_check_resources(
        self, resource_ids: list[str]
    ) -> Dict[str, ResourceExistenceResult]:
        """
        Check existence of multiple resources.

        Args:
            resource_ids: List of Azure resource IDs

        Returns:
            Dictionary mapping resource ID to existence result
        """
        results = {}

        for resource_id in resource_ids:
            results[resource_id] = self.check_resource_exists(resource_id)

        cache_stats = self.get_cache_stats()
        logger.info(
            f"Batch checked {len(resource_ids)} resources. "
            f"Cache stats: {cache_stats['valid']} valid, {cache_stats['expired']} expired"
        )

        return results
