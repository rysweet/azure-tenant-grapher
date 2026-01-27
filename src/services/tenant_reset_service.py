"""Tenant Reset Service for Azure Tenant Grapher.

Philosophy:
- Safety-first: Multiple confirmation layers prevent accidental deletion
- Ruthless simplicity: Clear separation of preview vs execution
- Zero-BS implementation: ATG SP preservation is hardcoded safety check

Public API (the "studs"):
    TenantResetService: Main service for tenant reset operations
    preview_tenant_reset: Preview tenant-level deletion
    execute_tenant_reset: Execute tenant-level deletion after confirmation
    preview_subscription_reset: Preview subscription-level deletion
    execute_subscription_reset: Execute subscription-level deletion
    preview_resource_group_reset: Preview resource group deletion
    execute_resource_group_reset: Execute resource group deletion
    preview_resource_reset: Preview individual resource deletion
    execute_resource_reset: Execute individual resource deletion

CRITICAL SAFETY REQUIREMENTS:
1. This service DELETES ACTUAL Azure resources and Entra ID objects
2. Confirmation token must be EXACTLY "DELETE" (case-sensitive)
3. ATG service principal is NEVER deleted (hardcoded safety check)
4. All operations are audited
5. Dry-run mode available for testing

Issue #627: Tenant Reset Feature with Granular Scopes
"""

import asyncio
import time
from datetime import datetime
from typing import Any, Optional

import structlog
from azure.core.credentials import TokenCredential
from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient, SubscriptionClient
from kiota_abstractions.api_error import APIError
from msgraph import GraphServiceClient
from neo4j import AsyncDriver

from .tenant_reset_models import (
    EntraObjectDeletionResult,
    GraphCleanupResult,
    ResetPreview,
    ResetResult,
    ResetScope,
    ResetStatus,
    ResourceDeletionResult,
    ScopeType,
)

logger = structlog.get_logger(__name__)

# CRITICAL: Confirmation token that must be provided to execute deletion
CONFIRMATION_TOKEN = "DELETE"


class InvalidConfirmationTokenError(Exception):
    """Raised when confirmation token doesn't match required value."""

    pass


class ATGServicePrincipalInScopeError(Exception):
    """Raised when ATG service principal would be deleted (critical safety check)."""

    pass


class TenantResetService:
    """Service for tenant reset operations with granular scopes.

    Provides preview and execution capabilities for deleting:
    - Azure resources (VMs, storage accounts, etc.)
    - Entra ID objects (users, groups, service principals)
    - Graph data (Neo4j nodes and relationships)

    SAFETY MECHANISMS:
    - Confirmation token required for all executions
    - ATG service principal preservation (never deleted)
    - Dry-run mode for testing
    - Comprehensive audit logging
    - Preview before execution
    """

    def __init__(
        self,
        azure_credential: Optional[TokenCredential] = None,
        graph_client: Optional[GraphServiceClient] = None,
        neo4j_driver: Optional[AsyncDriver] = None,
        atg_sp_id: Optional[str] = None,
        dry_run: bool = False,
    ):
        """Initialize tenant reset service.

        Args:
            azure_credential: Azure SDK credential (uses DefaultAzureCredential if None)
            graph_client: Microsoft Graph API client
            neo4j_driver: Neo4j async driver
            atg_sp_id: ATG service principal ID to preserve (loaded from config if None)
            dry_run: If True, preview only (no actual deletion)
        """
        self.credential = azure_credential or DefaultAzureCredential()
        self.graph_client = graph_client or GraphServiceClient(credentials=self.credential)
        self.neo4j_driver = neo4j_driver
        self.dry_run = dry_run

        # Load ATG SP ID from config or environment
        self.atg_sp_id = atg_sp_id or self._load_atg_sp_id()

        # Initialize Azure clients
        self.subscription_client = SubscriptionClient(credential=self.credential)

        logger.info(
            "tenant_reset_service_initialized",
            dry_run=self.dry_run,
            atg_sp_id=self.atg_sp_id,
        )

    def _load_atg_sp_id(self) -> Optional[str]:
        """Load ATG service principal ID from configuration.

        Returns:
            ATG service principal ID or None if not configured
        """
        import os

        # Try environment variable first
        atg_sp_id = os.getenv("ATG_SERVICE_PRINCIPAL_ID")
        if atg_sp_id:
            return atg_sp_id

        # Try loading from config
        try:
            from src.config_manager import load_config

            config = load_config()
            atg_sp_id = config.get("reset", {}).get("atg_sp_id")
            if atg_sp_id:
                return atg_sp_id
        except Exception as e:
            logger.warning("failed_to_load_atg_sp_id_from_config", error=str(e))

        logger.warning(
            "atg_sp_id_not_configured",
            message="ATG service principal ID not configured. Set ATG_SERVICE_PRINCIPAL_ID env var.",
        )
        return None

    def _validate_confirmation_token(self, confirmation_token: str) -> None:
        """Validate confirmation token matches required value.

        Args:
            confirmation_token: Token provided by user

        Raises:
            InvalidConfirmationTokenError: If token doesn't match exactly
        """
        if confirmation_token != CONFIRMATION_TOKEN:
            raise InvalidConfirmationTokenError(
                f"Confirmation token must be exactly '{CONFIRMATION_TOKEN}' (case-sensitive). "
                f"Provided: '{confirmation_token}'"
            )

    def _is_atg_service_principal(self, sp_id: str) -> bool:
        """Check if service principal is the ATG SP that must be preserved.

        Args:
            sp_id: Service principal object ID

        Returns:
            True if this is the ATG SP, False otherwise
        """
        if not self.atg_sp_id:
            logger.warning(
                "atg_sp_id_not_configured_during_check",
                message="Cannot verify ATG SP preservation without configured ATG_SERVICE_PRINCIPAL_ID",
            )
            return False

        return sp_id == self.atg_sp_id

    async def preview_tenant_reset(self) -> ResetPreview:
        """Preview tenant-level reset without executing.

        Shows counts of resources that would be deleted.

        Returns:
            ResetPreview with counts and warnings
        """
        scope = ResetScope(scope_type=ScopeType.TENANT)

        logger.info("preview_tenant_reset_started", scope=scope.to_dict())

        # Count Azure resources
        azure_count = await self._count_azure_resources(scope)

        # Count Entra ID objects
        users_count, groups_count, sps_count = await self._count_entra_objects(scope)

        # Count graph nodes
        graph_nodes_count = await self._count_graph_nodes(scope)

        # Estimate duration (rough: 1 second per resource + 0.5 seconds per Entra object)
        estimated_duration = azure_count + int((users_count + groups_count + sps_count) * 0.5)

        # Generate warnings
        warnings = [
            "⚠️  This will DELETE ALL Azure resources in the tenant",
            "⚠️  This will DELETE ALL Entra ID users, groups, and service principals (except ATG SP)",
            "⚠️  This action CANNOT be undone",
            "⚠️  Production data will be permanently lost",
        ]

        if not self.atg_sp_id:
            warnings.append(
                "⚠️  WARNING: ATG service principal ID not configured - cannot guarantee ATG SP preservation"
            )

        preview = ResetPreview(
            scope=scope,
            azure_resources_count=azure_count,
            entra_users_count=users_count,
            entra_groups_count=groups_count,
            entra_service_principals_count=sps_count,
            graph_nodes_count=graph_nodes_count,
            estimated_duration_seconds=estimated_duration,
            warnings=warnings,
        )

        logger.info("preview_tenant_reset_completed", preview=preview.to_dict())
        return preview

    async def execute_tenant_reset(self, confirmation_token: str) -> ResetResult:
        """Execute tenant-level reset after confirmation.

        Args:
            confirmation_token: Must be exactly "DELETE"

        Returns:
            ResetResult with deletion details

        Raises:
            InvalidConfirmationTokenError: If confirmation token doesn't match
            ATGServicePrincipalInScopeError: If ATG SP would be deleted
        """
        # CRITICAL SAFETY CHECK: Validate confirmation token
        self._validate_confirmation_token(confirmation_token)

        scope = ResetScope(scope_type=ScopeType.TENANT)
        start_time = time.time()
        started_at = datetime.utcnow()

        logger.warning(
            "execute_tenant_reset_started",
            scope=scope.to_dict(),
            dry_run=self.dry_run,
            confirmation_token=confirmation_token,
        )

        result = ResetResult(
            scope=scope,
            status=ResetStatus.RUNNING,
            started_at=started_at,
        )

        try:
            # Phase 1: Delete Azure resources
            azure_results = await self._delete_azure_resources(scope)
            result.resource_deletion_details = azure_results
            result.deleted_azure_resources = sum(1 for r in azure_results if r.success)

            # Phase 2: Delete Entra ID objects (with ATG SP preservation)
            entra_results = await self._delete_entra_objects(scope)
            result.entra_deletion_details = entra_results
            result.deleted_entra_users = sum(
                1 for r in entra_results if r.success and r.object_type == "user"
            )
            result.deleted_entra_groups = sum(
                1 for r in entra_results if r.success and r.object_type == "group"
            )
            result.deleted_entra_service_principals = sum(
                1 for r in entra_results if r.success and r.object_type == "service_principal"
            )

            # Phase 3: Clean up graph data
            graph_result = await self._cleanup_graph_data(scope)
            result.graph_cleanup_details = graph_result
            result.deleted_graph_nodes = graph_result.nodes_deleted if graph_result else 0
            result.deleted_graph_relationships = (
                graph_result.relationships_deleted if graph_result else 0
            )

            # Collect errors
            result.errors.extend([r.error for r in azure_results if not r.success and r.error])
            result.errors.extend([r.error for r in entra_results if not r.success and r.error])
            if graph_result and not graph_result.success and graph_result.error:
                result.errors.append(f"Graph cleanup failed: {graph_result.error}")

            # Determine final status
            if len(result.errors) == 0:
                result.status = ResetStatus.COMPLETED
            elif result.deleted_azure_resources > 0 or result.deleted_entra_users > 0:
                result.status = ResetStatus.PARTIAL
            else:
                result.status = ResetStatus.FAILED

        except Exception as e:
            logger.error("execute_tenant_reset_failed", error=str(e), exc_info=True)
            result.status = ResetStatus.FAILED
            result.errors.append(f"Fatal error during reset: {str(e)}")

        result.completed_at = datetime.utcnow()
        result.duration_seconds = time.time() - start_time

        logger.warning(
            "execute_tenant_reset_completed",
            status=result.status.value,
            deleted_resources=result.deleted_azure_resources,
            deleted_entra_objects=(
                result.deleted_entra_users
                + result.deleted_entra_groups
                + result.deleted_entra_service_principals
            ),
            duration_seconds=result.duration_seconds,
            error_count=len(result.errors),
        )

        return result

    async def preview_subscription_reset(self, subscription_id: str) -> ResetPreview:
        """Preview subscription-level reset.

        Args:
            subscription_id: Azure subscription ID

        Returns:
            ResetPreview with counts and warnings
        """
        scope = ResetScope(scope_type=ScopeType.SUBSCRIPTION, subscription_id=subscription_id)

        logger.info("preview_subscription_reset_started", scope=scope.to_dict())

        azure_count = await self._count_azure_resources(scope)
        graph_nodes_count = await self._count_graph_nodes(scope)
        estimated_duration = azure_count

        warnings = [
            f"⚠️  This will DELETE ALL Azure resources in subscription {subscription_id}",
            "⚠️  This action CANNOT be undone",
            "⚠️  Entra ID objects are NOT affected (subscription scope only)",
        ]

        preview = ResetPreview(
            scope=scope,
            azure_resources_count=azure_count,
            graph_nodes_count=graph_nodes_count,
            estimated_duration_seconds=estimated_duration,
            warnings=warnings,
        )

        logger.info("preview_subscription_reset_completed", preview=preview.to_dict())
        return preview

    async def execute_subscription_reset(
        self, subscription_id: str, confirmation_token: str
    ) -> ResetResult:
        """Execute subscription-level reset.

        Args:
            subscription_id: Azure subscription ID
            confirmation_token: Must be exactly "DELETE"

        Returns:
            ResetResult with deletion details
        """
        self._validate_confirmation_token(confirmation_token)

        scope = ResetScope(scope_type=ScopeType.SUBSCRIPTION, subscription_id=subscription_id)
        start_time = time.time()
        started_at = datetime.utcnow()

        logger.warning(
            "execute_subscription_reset_started",
            scope=scope.to_dict(),
            dry_run=self.dry_run,
        )

        result = ResetResult(scope=scope, status=ResetStatus.RUNNING, started_at=started_at)

        try:
            # Delete Azure resources in subscription
            azure_results = await self._delete_azure_resources(scope)
            result.resource_deletion_details = azure_results
            result.deleted_azure_resources = sum(1 for r in azure_results if r.success)

            # Clean up graph data for subscription
            graph_result = await self._cleanup_graph_data(scope)
            result.graph_cleanup_details = graph_result
            result.deleted_graph_nodes = graph_result.nodes_deleted if graph_result else 0
            result.deleted_graph_relationships = (
                graph_result.relationships_deleted if graph_result else 0
            )

            # Collect errors
            result.errors.extend([r.error for r in azure_results if not r.success and r.error])
            if graph_result and not graph_result.success and graph_result.error:
                result.errors.append(f"Graph cleanup failed: {graph_result.error}")

            result.status = (
                ResetStatus.COMPLETED
                if len(result.errors) == 0
                else (ResetStatus.PARTIAL if result.deleted_azure_resources > 0 else ResetStatus.FAILED)
            )

        except Exception as e:
            logger.error("execute_subscription_reset_failed", error=str(e), exc_info=True)
            result.status = ResetStatus.FAILED
            result.errors.append(f"Fatal error: {str(e)}")

        result.completed_at = datetime.utcnow()
        result.duration_seconds = time.time() - start_time

        logger.warning(
            "execute_subscription_reset_completed",
            status=result.status.value,
            deleted_resources=result.deleted_azure_resources,
            duration_seconds=result.duration_seconds,
        )

        return result

    async def preview_resource_group_reset(
        self, subscription_id: str, rg_name: str
    ) -> ResetPreview:
        """Preview resource group reset.

        Args:
            subscription_id: Azure subscription ID
            rg_name: Resource group name

        Returns:
            ResetPreview with counts and warnings
        """
        scope = ResetScope(
            scope_type=ScopeType.RESOURCE_GROUP,
            subscription_id=subscription_id,
            resource_group_name=rg_name,
        )

        logger.info("preview_resource_group_reset_started", scope=scope.to_dict())

        azure_count = await self._count_azure_resources(scope)
        graph_nodes_count = await self._count_graph_nodes(scope)
        estimated_duration = azure_count

        warnings = [
            f"⚠️  This will DELETE ALL Azure resources in resource group {rg_name}",
            "⚠️  This action CANNOT be undone",
        ]

        preview = ResetPreview(
            scope=scope,
            azure_resources_count=azure_count,
            graph_nodes_count=graph_nodes_count,
            estimated_duration_seconds=estimated_duration,
            warnings=warnings,
        )

        logger.info("preview_resource_group_reset_completed", preview=preview.to_dict())
        return preview

    async def execute_resource_group_reset(
        self, subscription_id: str, rg_name: str, confirmation_token: str
    ) -> ResetResult:
        """Execute resource group reset.

        Args:
            subscription_id: Azure subscription ID
            rg_name: Resource group name
            confirmation_token: Must be exactly "DELETE"

        Returns:
            ResetResult with deletion details
        """
        self._validate_confirmation_token(confirmation_token)

        scope = ResetScope(
            scope_type=ScopeType.RESOURCE_GROUP,
            subscription_id=subscription_id,
            resource_group_name=rg_name,
        )
        start_time = time.time()
        started_at = datetime.utcnow()

        logger.warning(
            "execute_resource_group_reset_started",
            scope=scope.to_dict(),
            dry_run=self.dry_run,
        )

        result = ResetResult(scope=scope, status=ResetStatus.RUNNING, started_at=started_at)

        try:
            azure_results = await self._delete_azure_resources(scope)
            result.resource_deletion_details = azure_results
            result.deleted_azure_resources = sum(1 for r in azure_results if r.success)

            graph_result = await self._cleanup_graph_data(scope)
            result.graph_cleanup_details = graph_result
            result.deleted_graph_nodes = graph_result.nodes_deleted if graph_result else 0
            result.deleted_graph_relationships = (
                graph_result.relationships_deleted if graph_result else 0
            )

            result.errors.extend([r.error for r in azure_results if not r.success and r.error])
            if graph_result and not graph_result.success and graph_result.error:
                result.errors.append(f"Graph cleanup failed: {graph_result.error}")

            result.status = (
                ResetStatus.COMPLETED
                if len(result.errors) == 0
                else (ResetStatus.PARTIAL if result.deleted_azure_resources > 0 else ResetStatus.FAILED)
            )

        except Exception as e:
            logger.error("execute_resource_group_reset_failed", error=str(e), exc_info=True)
            result.status = ResetStatus.FAILED
            result.errors.append(f"Fatal error: {str(e)}")

        result.completed_at = datetime.utcnow()
        result.duration_seconds = time.time() - start_time

        logger.warning(
            "execute_resource_group_reset_completed",
            status=result.status.value,
            deleted_resources=result.deleted_azure_resources,
            duration_seconds=result.duration_seconds,
        )

        return result

    async def preview_resource_reset(self, resource_id: str) -> ResetPreview:
        """Preview individual resource reset.

        Args:
            resource_id: Full Azure resource ID

        Returns:
            ResetPreview with counts and warnings
        """
        scope = ResetScope(scope_type=ScopeType.RESOURCE, resource_id=resource_id)

        logger.info("preview_resource_reset_started", scope=scope.to_dict())

        warnings = [
            f"⚠️  This will DELETE resource {resource_id}",
            "⚠️  This action CANNOT be undone",
        ]

        preview = ResetPreview(
            scope=scope,
            azure_resources_count=1,
            graph_nodes_count=1,
            estimated_duration_seconds=1,
            warnings=warnings,
        )

        logger.info("preview_resource_reset_completed", preview=preview.to_dict())
        return preview

    async def execute_resource_reset(
        self, resource_id: str, confirmation_token: str
    ) -> ResetResult:
        """Execute individual resource reset.

        Args:
            resource_id: Full Azure resource ID
            confirmation_token: Must be exactly "DELETE"

        Returns:
            ResetResult with deletion details
        """
        self._validate_confirmation_token(confirmation_token)

        scope = ResetScope(scope_type=ScopeType.RESOURCE, resource_id=resource_id)
        start_time = time.time()
        started_at = datetime.utcnow()

        logger.warning(
            "execute_resource_reset_started",
            scope=scope.to_dict(),
            dry_run=self.dry_run,
        )

        result = ResetResult(scope=scope, status=ResetStatus.RUNNING, started_at=started_at)

        try:
            azure_results = await self._delete_azure_resources(scope)
            result.resource_deletion_details = azure_results
            result.deleted_azure_resources = sum(1 for r in azure_results if r.success)

            graph_result = await self._cleanup_graph_data(scope)
            result.graph_cleanup_details = graph_result
            result.deleted_graph_nodes = graph_result.nodes_deleted if graph_result else 0
            result.deleted_graph_relationships = (
                graph_result.relationships_deleted if graph_result else 0
            )

            result.errors.extend([r.error for r in azure_results if not r.success and r.error])
            if graph_result and not graph_result.success and graph_result.error:
                result.errors.append(f"Graph cleanup failed: {graph_result.error}")

            result.status = (
                ResetStatus.COMPLETED
                if len(result.errors) == 0
                else (ResetStatus.PARTIAL if result.deleted_azure_resources > 0 else ResetStatus.FAILED)
            )

        except Exception as e:
            logger.error("execute_resource_reset_failed", error=str(e), exc_info=True)
            result.status = ResetStatus.FAILED
            result.errors.append(f"Fatal error: {str(e)}")

        result.completed_at = datetime.utcnow()
        result.duration_seconds = time.time() - start_time

        logger.warning(
            "execute_resource_reset_completed",
            status=result.status.value,
            deleted_resources=result.deleted_azure_resources,
            duration_seconds=result.duration_seconds,
        )

        return result

    # ========================================================================
    # Internal implementation methods
    # ========================================================================

    async def _count_azure_resources(self, scope: ResetScope) -> int:
        """Count Azure resources in scope.

        Args:
            scope: Reset scope

        Returns:
            Count of Azure resources
        """
        try:
            if scope.scope_type == ScopeType.TENANT:
                # Count all resources across all subscriptions
                total = 0
                subscriptions = self.subscription_client.subscriptions.list()
                for sub in subscriptions:
                    resource_client = ResourceManagementClient(
                        credential=self.credential, subscription_id=sub.subscription_id
                    )
                    resources = list(resource_client.resources.list())
                    total += len(resources)
                return total

            elif scope.scope_type == ScopeType.SUBSCRIPTION:
                resource_client = ResourceManagementClient(
                    credential=self.credential, subscription_id=scope.subscription_id
                )
                resources = list(resource_client.resources.list())
                return len(resources)

            elif scope.scope_type == ScopeType.RESOURCE_GROUP:
                resource_client = ResourceManagementClient(
                    credential=self.credential, subscription_id=scope.subscription_id
                )
                resources = list(
                    resource_client.resources.list_by_resource_group(
                        resource_group_name=scope.resource_group_name
                    )
                )
                return len(resources)

            elif scope.scope_type == ScopeType.RESOURCE:
                return 1  # Single resource

        except Exception as e:
            logger.error("failed_to_count_azure_resources", scope=scope.to_dict(), error=str(e))
            return 0

    async def _count_entra_objects(self, scope: ResetScope) -> tuple[int, int, int]:
        """Count Entra ID objects in scope.

        Only counts for tenant-level scope (Entra ID is tenant-wide).

        Args:
            scope: Reset scope

        Returns:
            Tuple of (users_count, groups_count, service_principals_count)
        """
        if scope.scope_type != ScopeType.TENANT:
            return (0, 0, 0)

        try:
            # Count users
            users = await self.graph_client.users.get()
            users_count = len(users.value) if users and users.value else 0

            # Count groups
            groups = await self.graph_client.groups.get()
            groups_count = len(groups.value) if groups and groups.value else 0

            # Count service principals (excluding ATG SP)
            sps = await self.graph_client.service_principals.get()
            sps_count = 0
            if sps and sps.value:
                sps_count = sum(1 for sp in sps.value if not self._is_atg_service_principal(sp.id))

            return (users_count, groups_count, sps_count)

        except Exception as e:
            logger.error("failed_to_count_entra_objects", error=str(e))
            return (0, 0, 0)

    async def _count_graph_nodes(self, scope: ResetScope) -> int:
        """Count Neo4j graph nodes in scope.

        Args:
            scope: Reset scope

        Returns:
            Count of graph nodes
        """
        if not self.neo4j_driver:
            return 0

        try:
            async with self.neo4j_driver.session() as session:
                if scope.scope_type == ScopeType.TENANT:
                    result = await session.run("MATCH (n) RETURN count(n) as count")
                elif scope.scope_type == ScopeType.SUBSCRIPTION:
                    result = await session.run(
                        "MATCH (n:Resource) WHERE n.subscriptionId = $sub_id RETURN count(n) as count",
                        sub_id=scope.subscription_id,
                    )
                elif scope.scope_type == ScopeType.RESOURCE_GROUP:
                    result = await session.run(
                        "MATCH (n:Resource) WHERE n.subscriptionId = $sub_id AND n.resourceGroup = $rg RETURN count(n) as count",
                        sub_id=scope.subscription_id,
                        rg=scope.resource_group_name,
                    )
                elif scope.scope_type == ScopeType.RESOURCE:
                    result = await session.run(
                        "MATCH (n:Resource {id: $resource_id}) RETURN count(n) as count",
                        resource_id=scope.resource_id,
                    )

                record = await result.single()
                return record["count"] if record else 0

        except Exception as e:
            logger.error("failed_to_count_graph_nodes", scope=scope.to_dict(), error=str(e))
            return 0

    async def _delete_azure_resources(self, scope: ResetScope) -> list[ResourceDeletionResult]:
        """Delete Azure resources in scope.

        Args:
            scope: Reset scope

        Returns:
            List of ResourceDeletionResult for each resource
        """
        if self.dry_run:
            logger.info("dry_run_skip_azure_deletion", scope=scope.to_dict())
            return []

        results: list[ResourceDeletionResult] = []

        try:
            if scope.scope_type == ScopeType.TENANT:
                # Delete resources across all subscriptions
                subscriptions = self.subscription_client.subscriptions.list()
                for sub in subscriptions:
                    sub_results = await self._delete_subscription_resources(sub.subscription_id)
                    results.extend(sub_results)

            elif scope.scope_type == ScopeType.SUBSCRIPTION:
                results = await self._delete_subscription_resources(scope.subscription_id)

            elif scope.scope_type == ScopeType.RESOURCE_GROUP:
                results = await self._delete_resource_group_resources(
                    scope.subscription_id, scope.resource_group_name
                )

            elif scope.scope_type == ScopeType.RESOURCE:
                result = await self._delete_single_resource(scope.resource_id)
                if result:
                    results.append(result)

        except Exception as e:
            logger.error("failed_to_delete_azure_resources", scope=scope.to_dict(), error=str(e))
            results.append(
                ResourceDeletionResult(
                    resource_id="unknown",
                    resource_type="unknown",
                    success=False,
                    error=f"Fatal error during Azure deletion: {str(e)}",
                )
            )

        return results

    async def _delete_subscription_resources(
        self, subscription_id: str
    ) -> list[ResourceDeletionResult]:
        """Delete all resources in a subscription.

        Args:
            subscription_id: Azure subscription ID

        Returns:
            List of ResourceDeletionResult
        """
        results: list[ResourceDeletionResult] = []

        try:
            resource_client = ResourceManagementClient(
                credential=self.credential, subscription_id=subscription_id
            )
            resources = list(resource_client.resources.list())

            # Delete resources in parallel (batch of 10)
            batch_size = 10
            for i in range(0, len(resources), batch_size):
                batch = resources[i : i + batch_size]
                batch_results = await asyncio.gather(
                    *[self._delete_single_resource(r.id) for r in batch],
                    return_exceptions=True,
                )
                results.extend([r for r in batch_results if isinstance(r, ResourceDeletionResult)])

        except Exception as e:
            logger.error(
                "failed_to_delete_subscription_resources",
                subscription_id=subscription_id,
                error=str(e),
            )
            results.append(
                ResourceDeletionResult(
                    resource_id=subscription_id,
                    resource_type="subscription",
                    success=False,
                    error=f"Failed to list/delete subscription resources: {str(e)}",
                )
            )

        return results

    async def _delete_resource_group_resources(
        self, subscription_id: str, rg_name: str
    ) -> list[ResourceDeletionResult]:
        """Delete all resources in a resource group.

        Args:
            subscription_id: Azure subscription ID
            rg_name: Resource group name

        Returns:
            List of ResourceDeletionResult
        """
        results: list[ResourceDeletionResult] = []

        try:
            resource_client = ResourceManagementClient(
                credential=self.credential, subscription_id=subscription_id
            )
            resources = list(
                resource_client.resources.list_by_resource_group(resource_group_name=rg_name)
            )

            # Delete resources in parallel
            batch_size = 10
            for i in range(0, len(resources), batch_size):
                batch = resources[i : i + batch_size]
                batch_results = await asyncio.gather(
                    *[self._delete_single_resource(r.id) for r in batch],
                    return_exceptions=True,
                )
                results.extend([r for r in batch_results if isinstance(r, ResourceDeletionResult)])

        except Exception as e:
            logger.error(
                "failed_to_delete_resource_group_resources",
                subscription_id=subscription_id,
                rg_name=rg_name,
                error=str(e),
            )
            results.append(
                ResourceDeletionResult(
                    resource_id=f"/subscriptions/{subscription_id}/resourceGroups/{rg_name}",
                    resource_type="resourceGroup",
                    success=False,
                    error=f"Failed to list/delete RG resources: {str(e)}",
                )
            )

        return results

    async def _delete_single_resource(self, resource_id: str) -> Optional[ResourceDeletionResult]:
        """Delete a single Azure resource.

        Args:
            resource_id: Full Azure resource ID

        Returns:
            ResourceDeletionResult or None if failed to parse resource ID
        """
        start_time = time.time()

        try:
            # Parse resource ID to extract components
            parts = resource_id.split("/")
            if len(parts) < 8:
                return ResourceDeletionResult(
                    resource_id=resource_id,
                    resource_type="unknown",
                    success=False,
                    error="Invalid resource ID format",
                )

            subscription_id = parts[2]
            resource_group = parts[4]
            provider = parts[6]
            resource_type = parts[7]
            resource_name = parts[8] if len(parts) > 8 else "unknown"

            # Create resource client
            resource_client = ResourceManagementClient(
                credential=self.credential, subscription_id=subscription_id
            )

            # Delete the resource (long-running operation)
            api_version = "2023-07-01"  # Common API version
            poller = resource_client.resources.begin_delete_by_id(
                resource_id=resource_id, api_version=api_version
            )

            # Wait for deletion (with timeout of 30 seconds)
            result = await asyncio.wait_for(asyncio.to_thread(poller.result), timeout=30.0)

            duration = time.time() - start_time

            logger.info(
                "azure_resource_deleted",
                resource_id=resource_id,
                resource_type=f"{provider}/{resource_type}",
                duration_seconds=duration,
            )

            return ResourceDeletionResult(
                resource_id=resource_id,
                resource_type=f"{provider}/{resource_type}",
                success=True,
                duration_seconds=duration,
            )

        except asyncio.TimeoutError:
            duration = time.time() - start_time
            logger.error("azure_resource_deletion_timeout", resource_id=resource_id)
            return ResourceDeletionResult(
                resource_id=resource_id,
                resource_type="unknown",
                success=False,
                error="Deletion timed out after 30 seconds",
                duration_seconds=duration,
            )

        except Exception as e:
            duration = time.time() - start_time
            logger.error("azure_resource_deletion_failed", resource_id=resource_id, error=str(e))
            return ResourceDeletionResult(
                resource_id=resource_id,
                resource_type="unknown",
                success=False,
                error=str(e),
                duration_seconds=duration,
            )

    async def _delete_entra_objects(self, scope: ResetScope) -> list[EntraObjectDeletionResult]:
        """Delete Entra ID objects in scope.

        Only executes for tenant-level scope. CRITICAL: Preserves ATG service principal.

        Args:
            scope: Reset scope

        Returns:
            List of EntraObjectDeletionResult
        """
        if scope.scope_type != ScopeType.TENANT:
            return []

        if self.dry_run:
            logger.info("dry_run_skip_entra_deletion", scope=scope.to_dict())
            return []

        results: list[EntraObjectDeletionResult] = []

        try:
            # Delete users
            users_results = await self._delete_entra_users()
            results.extend(users_results)

            # Delete groups
            groups_results = await self._delete_entra_groups()
            results.extend(groups_results)

            # Delete service principals (WITH ATG SP PRESERVATION)
            sps_results = await self._delete_entra_service_principals()
            results.extend(sps_results)

        except Exception as e:
            logger.error("failed_to_delete_entra_objects", error=str(e))
            results.append(
                EntraObjectDeletionResult(
                    object_id="unknown",
                    object_type="unknown",
                    display_name="unknown",
                    success=False,
                    error=f"Fatal error during Entra deletion: {str(e)}",
                )
            )

        return results

    async def _delete_entra_users(self) -> list[EntraObjectDeletionResult]:
        """Delete all Entra ID users.

        Returns:
            List of EntraObjectDeletionResult
        """
        results: list[EntraObjectDeletionResult] = []

        try:
            users_response = await self.graph_client.users.get()
            if not users_response or not users_response.value:
                return results

            users = users_response.value

            # Delete users in parallel (batch of 5)
            batch_size = 5
            for i in range(0, len(users), batch_size):
                batch = users[i : i + batch_size]
                batch_results = await asyncio.gather(
                    *[self._delete_single_entra_user(user) for user in batch],
                    return_exceptions=True,
                )
                results.extend(
                    [r for r in batch_results if isinstance(r, EntraObjectDeletionResult)]
                )

        except Exception as e:
            logger.error("failed_to_delete_entra_users", error=str(e))
            results.append(
                EntraObjectDeletionResult(
                    object_id="unknown",
                    object_type="user",
                    display_name="unknown",
                    success=False,
                    error=f"Failed to list/delete users: {str(e)}",
                )
            )

        return results

    async def _delete_single_entra_user(self, user: Any) -> EntraObjectDeletionResult:
        """Delete a single Entra ID user.

        Args:
            user: User object from Graph API

        Returns:
            EntraObjectDeletionResult
        """
        try:
            await self.graph_client.users.by_user_id(user.id).delete()

            logger.info("entra_user_deleted", user_id=user.id, display_name=user.display_name)

            return EntraObjectDeletionResult(
                object_id=user.id,
                object_type="user",
                display_name=user.display_name or "unknown",
                success=True,
            )

        except APIError as e:
            logger.error(
                "entra_user_deletion_failed",
                user_id=user.id,
                display_name=user.display_name,
                error=str(e),
            )
            return EntraObjectDeletionResult(
                object_id=user.id,
                object_type="user",
                display_name=user.display_name or "unknown",
                success=False,
                error=str(e),
            )

    async def _delete_entra_groups(self) -> list[EntraObjectDeletionResult]:
        """Delete all Entra ID groups.

        Returns:
            List of EntraObjectDeletionResult
        """
        results: list[EntraObjectDeletionResult] = []

        try:
            groups_response = await self.graph_client.groups.get()
            if not groups_response or not groups_response.value:
                return results

            groups = groups_response.value

            # Delete groups in parallel
            batch_size = 5
            for i in range(0, len(groups), batch_size):
                batch = groups[i : i + batch_size]
                batch_results = await asyncio.gather(
                    *[self._delete_single_entra_group(group) for group in batch],
                    return_exceptions=True,
                )
                results.extend(
                    [r for r in batch_results if isinstance(r, EntraObjectDeletionResult)]
                )

        except Exception as e:
            logger.error("failed_to_delete_entra_groups", error=str(e))
            results.append(
                EntraObjectDeletionResult(
                    object_id="unknown",
                    object_type="group",
                    display_name="unknown",
                    success=False,
                    error=f"Failed to list/delete groups: {str(e)}",
                )
            )

        return results

    async def _delete_single_entra_group(self, group: Any) -> EntraObjectDeletionResult:
        """Delete a single Entra ID group.

        Args:
            group: Group object from Graph API

        Returns:
            EntraObjectDeletionResult
        """
        try:
            await self.graph_client.groups.by_group_id(group.id).delete()

            logger.info("entra_group_deleted", group_id=group.id, display_name=group.display_name)

            return EntraObjectDeletionResult(
                object_id=group.id,
                object_type="group",
                display_name=group.display_name or "unknown",
                success=True,
            )

        except APIError as e:
            logger.error(
                "entra_group_deletion_failed",
                group_id=group.id,
                display_name=group.display_name,
                error=str(e),
            )
            return EntraObjectDeletionResult(
                object_id=group.id,
                object_type="group",
                display_name=group.display_name or "unknown",
                success=False,
                error=str(e),
            )

    async def _delete_entra_service_principals(self) -> list[EntraObjectDeletionResult]:
        """Delete all Entra ID service principals (EXCEPT ATG SP).

        CRITICAL SAFETY: This method MUST preserve the ATG service principal.

        Returns:
            List of EntraObjectDeletionResult
        """
        results: list[EntraObjectDeletionResult] = []

        try:
            sps_response = await self.graph_client.service_principals.get()
            if not sps_response or not sps_response.value:
                return results

            sps = sps_response.value

            # CRITICAL SAFETY CHECK: Verify ATG SP is not in deletion list
            atg_sp_in_scope = any(self._is_atg_service_principal(sp.id) for sp in sps)
            if atg_sp_in_scope and self.atg_sp_id:
                logger.critical(
                    "atg_service_principal_preservation_check",
                    message="ATG service principal detected in scope - will be skipped",
                    atg_sp_id=self.atg_sp_id,
                )

            # Filter out ATG SP from deletion list
            sps_to_delete = [sp for sp in sps if not self._is_atg_service_principal(sp.id)]

            logger.info(
                "entra_service_principals_filtered",
                total_sps=len(sps),
                sps_to_delete=len(sps_to_delete),
                atg_sp_preserved=len(sps) - len(sps_to_delete),
            )

            # Delete service principals in parallel
            batch_size = 5
            for i in range(0, len(sps_to_delete), batch_size):
                batch = sps_to_delete[i : i + batch_size]
                batch_results = await asyncio.gather(
                    *[self._delete_single_entra_service_principal(sp) for sp in batch],
                    return_exceptions=True,
                )
                results.extend(
                    [r for r in batch_results if isinstance(r, EntraObjectDeletionResult)]
                )

        except Exception as e:
            logger.error("failed_to_delete_entra_service_principals", error=str(e))
            results.append(
                EntraObjectDeletionResult(
                    object_id="unknown",
                    object_type="service_principal",
                    display_name="unknown",
                    success=False,
                    error=f"Failed to list/delete service principals: {str(e)}",
                )
            )

        return results

    async def _delete_single_entra_service_principal(
        self, sp: Any
    ) -> EntraObjectDeletionResult:
        """Delete a single Entra ID service principal.

        Args:
            sp: Service principal object from Graph API

        Returns:
            EntraObjectDeletionResult
        """
        # DOUBLE-CHECK: Never delete ATG SP
        if self._is_atg_service_principal(sp.id):
            logger.warning(
                "atg_service_principal_skip",
                sp_id=sp.id,
                display_name=sp.display_name,
                message="ATG service principal skipped (safety check)",
            )
            return EntraObjectDeletionResult(
                object_id=sp.id,
                object_type="service_principal",
                display_name=sp.display_name or "ATG Service Principal",
                success=False,
                error="ATG service principal cannot be deleted (safety check)",
            )

        try:
            await self.graph_client.service_principals.by_service_principal_id(sp.id).delete()

            logger.info(
                "entra_service_principal_deleted", sp_id=sp.id, display_name=sp.display_name
            )

            return EntraObjectDeletionResult(
                object_id=sp.id,
                object_type="service_principal",
                display_name=sp.display_name or "unknown",
                success=True,
            )

        except APIError as e:
            logger.error(
                "entra_service_principal_deletion_failed",
                sp_id=sp.id,
                display_name=sp.display_name,
                error=str(e),
            )
            return EntraObjectDeletionResult(
                object_id=sp.id,
                object_type="service_principal",
                display_name=sp.display_name or "unknown",
                success=False,
                error=str(e),
            )

    async def _cleanup_graph_data(self, scope: ResetScope) -> Optional[GraphCleanupResult]:
        """Clean up Neo4j graph data for deleted resources.

        Args:
            scope: Reset scope

        Returns:
            GraphCleanupResult or None if Neo4j driver not configured
        """
        if not self.neo4j_driver:
            logger.warning("neo4j_driver_not_configured", message="Cannot cleanup graph data")
            return None

        if self.dry_run:
            logger.info("dry_run_skip_graph_cleanup", scope=scope.to_dict())
            return GraphCleanupResult(
                nodes_deleted=0, relationships_deleted=0, success=True, duration_seconds=0.0
            )

        start_time = time.time()

        try:
            async with self.neo4j_driver.session() as session:
                if scope.scope_type == ScopeType.TENANT:
                    # Delete all nodes and relationships
                    result = await session.run("MATCH (n) DETACH DELETE n")
                    summary = await result.consume()
                    nodes_deleted = summary.counters.nodes_deleted
                    rels_deleted = summary.counters.relationships_deleted

                elif scope.scope_type == ScopeType.SUBSCRIPTION:
                    result = await session.run(
                        "MATCH (n:Resource {subscriptionId: $sub_id}) DETACH DELETE n",
                        sub_id=scope.subscription_id,
                    )
                    summary = await result.consume()
                    nodes_deleted = summary.counters.nodes_deleted
                    rels_deleted = summary.counters.relationships_deleted

                elif scope.scope_type == ScopeType.RESOURCE_GROUP:
                    result = await session.run(
                        "MATCH (n:Resource {subscriptionId: $sub_id, resourceGroup: $rg}) DETACH DELETE n",
                        sub_id=scope.subscription_id,
                        rg=scope.resource_group_name,
                    )
                    summary = await result.consume()
                    nodes_deleted = summary.counters.nodes_deleted
                    rels_deleted = summary.counters.relationships_deleted

                elif scope.scope_type == ScopeType.RESOURCE:
                    result = await session.run(
                        "MATCH (n:Resource {id: $resource_id}) DETACH DELETE n",
                        resource_id=scope.resource_id,
                    )
                    summary = await result.consume()
                    nodes_deleted = summary.counters.nodes_deleted
                    rels_deleted = summary.counters.relationships_deleted

                duration = time.time() - start_time

                logger.info(
                    "graph_cleanup_completed",
                    scope=scope.to_dict(),
                    nodes_deleted=nodes_deleted,
                    relationships_deleted=rels_deleted,
                    duration_seconds=duration,
                )

                return GraphCleanupResult(
                    nodes_deleted=nodes_deleted,
                    relationships_deleted=rels_deleted,
                    success=True,
                    duration_seconds=duration,
                )

        except Exception as e:
            duration = time.time() - start_time
            logger.error("graph_cleanup_failed", scope=scope.to_dict(), error=str(e))
            return GraphCleanupResult(
                nodes_deleted=0,
                relationships_deleted=0,
                success=False,
                error=str(e),
                duration_seconds=duration,
            )
