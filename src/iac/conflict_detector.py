"""Pre-deployment conflict detection for Azure resources.

This module provides conflict detection before IaC generation to prevent
deployment failures from existing resources, soft-deleted Key Vaults,
and locked resource groups.

Design Goals:
- Detect conflicts BEFORE IaC generation
- Provide actionable remediation options
- Integration with existing cleanup infrastructure
- Zero false positives
- Graceful error handling with warnings
- Cross-tenant support with proper credential routing
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from azure.core.exceptions import AzureError, ResourceNotFoundError
from azure.identity import ClientSecretCredential, DefaultAzureCredential
from azure.mgmt.keyvault import KeyVaultManagementClient
from azure.mgmt.resource import ManagementLockClient, ResourceManagementClient

logger = logging.getLogger(__name__)


def _get_tenant_credential_from_env(tenant_num: int) -> Optional[ClientSecretCredential]:
    """Create Azure credential from tenant-specific environment variables.

    Args:
        tenant_num: Tenant number (1 or 2)

    Returns:
        ClientSecretCredential if all required env vars exist, None otherwise
    """
    tenant_id = os.environ.get(f"AZURE_TENANT_{tenant_num}_ID")
    client_id = os.environ.get(f"AZURE_TENANT_{tenant_num}_CLIENT_ID")
    client_secret = os.environ.get(f"AZURE_TENANT_{tenant_num}_CLIENT_SECRET")

    if tenant_id and client_id and client_secret:
        logger.debug(f"Creating credential for Tenant {tenant_num} (tenant_id: {tenant_id[:8]}...)")
        return ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
    return None


def _build_subscription_to_credential_map() -> Dict[str, ClientSecretCredential]:
    """Build mapping from subscription IDs to appropriate tenant credentials.

    Reads AZURE_TENANT_1_SUBSCRIPTION_ID and AZURE_TENANT_2_SUBSCRIPTION_ID
    from environment and maps them to their respective credentials.

    Returns:
        Dictionary mapping subscription_id -> ClientSecretCredential
    """
    mapping = {}

    # Try Tenant 1
    tenant1_sub = os.environ.get("AZURE_TENANT_1_SUBSCRIPTION_ID")
    tenant1_cred = _get_tenant_credential_from_env(1)
    if tenant1_sub and tenant1_cred:
        mapping[tenant1_sub] = tenant1_cred
        logger.debug(f"Mapped subscription {tenant1_sub[:8]}... to Tenant 1 credentials")

    # Try Tenant 2
    tenant2_sub = os.environ.get("AZURE_TENANT_2_SUBSCRIPTION_ID")
    tenant2_cred = _get_tenant_credential_from_env(2)
    if tenant2_sub and tenant2_cred:
        mapping[tenant2_sub] = tenant2_cred
        logger.debug(f"Mapped subscription {tenant2_sub[:8]}... to Tenant 2 credentials")

    if not mapping:
        logger.warning(
            "No subscription-to-tenant mappings found. "
            "Set AZURE_TENANT_1_SUBSCRIPTION_ID and AZURE_TENANT_2_SUBSCRIPTION_ID "
            "to enable cross-tenant conflict detection."
        )

    return mapping


class ConflictType(Enum):
    """Types of deployment conflicts."""

    EXISTING_RESOURCE = "existing_resource"
    SOFT_DELETED_KEYVAULT = "soft_deleted_keyvault"
    LOCKED_RESOURCE_GROUP = "locked_resource_group"


@dataclass
class ResourceConflict:
    """Represents a single resource conflict."""

    conflict_type: ConflictType
    resource_name: str
    resource_type: str
    resource_group: Optional[str] = None
    location: Optional[str] = None

    # Conflict-specific details
    lock_type: Optional[str] = None  # For LOCKED_RESOURCE_GROUP
    deletion_date: Optional[str] = None  # For SOFT_DELETED_KEYVAULT
    scheduled_purge_date: Optional[str] = None  # For SOFT_DELETED_KEYVAULT

    # Remediation suggestions
    remediation_actions: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        """Human-readable conflict description."""
        if self.conflict_type == ConflictType.EXISTING_RESOURCE:
            return (
                f"Resource '{self.resource_name}' ({self.resource_type}) "
                f"already exists in RG '{self.resource_group}'"
            )
        elif self.conflict_type == ConflictType.SOFT_DELETED_KEYVAULT:
            return (
                f"Key Vault '{self.resource_name}' is soft-deleted "
                f"(purge scheduled: {self.scheduled_purge_date})"
            )
        elif self.conflict_type == ConflictType.LOCKED_RESOURCE_GROUP:
            return f"Resource Group '{self.resource_name}' has {self.lock_type} lock"
        return f"Unknown conflict: {self.resource_name}"


@dataclass
class ConflictReport:
    """Aggregated conflict detection results."""

    subscription_id: str
    conflicts: List[ResourceConflict] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # Statistics
    total_resources_checked: int = 0
    existing_resources_found: int = 0
    soft_deleted_vaults_found: int = 0
    locked_rgs_found: int = 0

    @property
    def has_conflicts(self) -> bool:
        """Check if any conflicts were detected."""
        return len(self.conflicts) > 0

    @property
    def conflict_summary(self) -> Dict[ConflictType, int]:
        """Count conflicts by type."""
        summary = dict.fromkeys(ConflictType, 0)
        for conflict in self.conflicts:
            summary[conflict.conflict_type] += 1
        return summary

    def format_report(self) -> str:
        """Generate human-readable conflict report."""
        lines = [
            "=" * 60,
            "Pre-Deployment Conflict Report",
            f"Subscription: {self.subscription_id}",
            "=" * 60,
            "",
            f"Resources Checked: {self.total_resources_checked}",
            f"Conflicts Found: {len(self.conflicts)}",
            "",
        ]

        if not self.has_conflicts:
            lines.append("No conflicts detected. Deployment should succeed.")
            return "\n".join(lines)

        # Group by conflict type
        for conflict_type in ConflictType:
            type_conflicts = [
                c for c in self.conflicts if c.conflict_type == conflict_type
            ]
            if type_conflicts:
                lines.append(
                    f"\n{conflict_type.value.upper().replace('_', ' ')} ({len(type_conflicts)}):"
                )
                lines.append("-" * 60)
                for conflict in type_conflicts:
                    lines.append(f"  {conflict}")
                    for action in conflict.remediation_actions:
                        lines.append(f"    -> {action}")

        if self.warnings:
            lines.append("\nWARNINGS:")
            for warning in self.warnings:
                lines.append(f"  {warning}")

        return "\n".join(lines)


class ConflictDetector:
    """Detects deployment conflicts in target Azure subscription.

    Supports cross-tenant conflict detection by automatically selecting
    the appropriate credential based on subscription-to-tenant mapping.
    """

    def __init__(
        self,
        subscription_id: str,
        credential: Optional[DefaultAzureCredential] = None,
        timeout: int = 300,
    ):
        """Initialize conflict detector.

        Args:
            subscription_id: Target Azure subscription ID
            credential: Optional Azure credential. If not provided, attempts to
                       select credential based on subscription-to-tenant mapping
                       from environment variables (AZURE_TENANT_1_SUBSCRIPTION_ID, etc.)
            timeout: Timeout in seconds for Azure API operations
        """
        self.subscription_id = subscription_id

        # Select credential: explicit > mapped > default
        if credential is not None:
            self.credential = credential
            logger.debug(f"Using explicitly provided credential for subscription {subscription_id[:8]}...")
        else:
            # Try to get tenant-specific credential from mapping
            sub_to_cred_map = _build_subscription_to_credential_map()
            if subscription_id in sub_to_cred_map:
                self.credential = sub_to_cred_map[subscription_id]
                logger.info(
                    f"Using tenant-specific credential for subscription {subscription_id[:8]}... "
                    f"(cross-tenant mode enabled)"
                )
            else:
                self.credential = DefaultAzureCredential()
                logger.warning(
                    f"Subscription {subscription_id[:8]}... not in tenant mapping, "
                    f"falling back to DefaultAzureCredential. "
                    f"This may cause LinkedAuthorizationFailed errors in cross-tenant scenarios."
                )

        self.timeout = timeout

        # Lazy-initialized clients
        self._resource_client: Optional[ResourceManagementClient] = None
        self._keyvault_client: Optional[KeyVaultManagementClient] = None
        self._lock_client: Optional[ManagementLockClient] = None

    @property
    def resource_client(self) -> ResourceManagementClient:
        """Lazy-initialized resource management client."""
        if self._resource_client is None:
            self._resource_client = ResourceManagementClient(
                self.credential, self.subscription_id
            )
        return self._resource_client

    @property
    def keyvault_client(self) -> KeyVaultManagementClient:
        """Lazy-initialized Key Vault management client."""
        if self._keyvault_client is None:
            self._keyvault_client = KeyVaultManagementClient(
                self.credential, self.subscription_id
            )
        return self._keyvault_client

    @property
    def lock_client(self) -> ManagementLockClient:
        """Lazy-initialized management lock client."""
        if self._lock_client is None:
            self._lock_client = ManagementLockClient(
                self.credential, self.subscription_id
            )
        return self._lock_client

    async def detect_conflicts(
        self,
        planned_resources: List[Dict[str, Any]],
        check_existing: bool = True,
        check_soft_deleted: bool = True,
        check_locks: bool = True,
    ) -> ConflictReport:
        """Detect all conflicts for planned resource deployment.

        Args:
            planned_resources: List of resources to be deployed (from TenantGraph)
            check_existing: Check for existing resources (default: True)
            check_soft_deleted: Check for soft-deleted Key Vaults (default: True)
            check_locks: Check for locked resource groups (default: True)

        Returns:
            ConflictReport with detected conflicts and remediation suggestions
        """
        report = ConflictReport(subscription_id=self.subscription_id)
        report.total_resources_checked = len(planned_resources)

        # Extract resource groups and Key Vaults from planned resources
        planned_rgs = self._extract_resource_groups(planned_resources)
        planned_vaults = self._extract_key_vaults(planned_resources)

        # Run detection tasks concurrently
        tasks = []

        if check_existing:
            tasks.append(self._check_existing_resources(planned_resources, report))

        if check_soft_deleted and planned_vaults:
            tasks.append(self._check_soft_deleted_vaults(planned_vaults, report))

        if check_locks and planned_rgs:
            tasks.append(self._check_locked_resource_groups(planned_rgs, report))

        # Execute all checks (capture exceptions to prevent one failure from blocking others)
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            # Log any unexpected exceptions
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Conflict detection task failed: {result}")

        # Generate remediation suggestions
        self._add_remediation_suggestions(report)

        return report

    async def _check_existing_resources(
        self,
        planned_resources: List[Dict[str, Any]],
        report: ConflictReport,
    ) -> None:
        """Check for existing resources with same names.

        Strategy:
        1. List all resources in subscription
        2. Build name+type index
        3. Check planned resources against index
        """
        logger.info("Checking for existing resource conflicts...")

        try:
            # Build index of existing resources
            existing_index: Dict[str, Set[str]] = {}  # {type: {name1, name2, ...}}

            for resource in self.resource_client.resources.list():
                rtype = resource.type
                rname = resource.name

                if rtype not in existing_index:
                    existing_index[rtype] = set()
                existing_index[rtype].add(rname)

            # Check planned resources
            for planned in planned_resources:
                ptype = planned.get("type")
                pname = planned.get("name")
                prg = planned.get("resource_group")
                plocation = planned.get("location")

                if not ptype or not pname:
                    continue

                if ptype in existing_index and pname in existing_index[ptype]:
                    conflict = ResourceConflict(
                        conflict_type=ConflictType.EXISTING_RESOURCE,
                        resource_name=pname,
                        resource_type=ptype,
                        resource_group=prg,
                        location=plocation,
                        remediation_actions=[
                            "Delete existing resource manually",
                            "Run cleanup script: ./scripts/cleanup_target_subscription.sh",
                            "Use --name-suffix to rename resources",
                        ],
                    )
                    report.conflicts.append(conflict)
                    report.existing_resources_found += 1

            logger.info(
                f"Found {report.existing_resources_found} existing resource conflicts"
            )

        except Exception as e:
            logger.error(f"Error checking existing resources: {e}")
            report.warnings.append(f"Failed to check existing resources: {e!s}")

    async def _check_soft_deleted_vaults(
        self,
        planned_vaults: List[str],
        report: ConflictReport,
    ) -> None:
        """Check for soft-deleted Key Vaults.

        Uses KeyVaultManagementClient to list deleted vaults.
        """
        logger.info(
            f"Checking for soft-deleted Key Vaults ({len(planned_vaults)} planned)..."
        )

        try:
            # List all soft-deleted vaults in subscription
            deleted_vaults = {}  # {name: vault_info}

            for vault in self.keyvault_client.vaults.list_deleted():
                deleted_vaults[vault.name] = vault

            # Check planned vaults
            for vault_name in planned_vaults:
                if vault_name in deleted_vaults:
                    vault_info = deleted_vaults[vault_name]
                    conflict = ResourceConflict(
                        conflict_type=ConflictType.SOFT_DELETED_KEYVAULT,
                        resource_name=vault_name,
                        resource_type="Microsoft.KeyVault/vaults",
                        location=(
                            vault_info.properties.location
                            if vault_info.properties
                            else None
                        ),
                        deletion_date=(
                            str(vault_info.properties.deletion_date)
                            if vault_info.properties
                            else None
                        ),
                        scheduled_purge_date=(
                            str(vault_info.properties.scheduled_purge_date)
                            if vault_info.properties
                            else None
                        ),
                        remediation_actions=[
                            f"Purge vault: az keyvault purge --name {vault_name}",
                            "Use --auto-purge-soft-deleted flag",
                            "Use --name-suffix to rename vault",
                        ],
                    )
                    report.conflicts.append(conflict)
                    report.soft_deleted_vaults_found += 1

            logger.info(
                f"Found {report.soft_deleted_vaults_found} soft-deleted vault conflicts"
            )

        except Exception as e:
            logger.error(f"Error checking soft-deleted vaults: {e}")
            report.warnings.append(f"Failed to check soft-deleted vaults: {e!s}")

    async def _check_locked_resource_groups(
        self,
        planned_rgs: Set[str],
        report: ConflictReport,
    ) -> None:
        """Check for locked resource groups.

        Uses ManagementLockClient to detect RG locks.
        """
        logger.info(
            f"Checking for locked resource groups ({len(planned_rgs)} planned)..."
        )

        try:
            for rg_name in planned_rgs:
                try:
                    # List locks on resource group
                    locks = list(
                        self.lock_client.management_locks.list_at_resource_group_level(
                            rg_name
                        )
                    )

                    if locks:
                        # RG has locks - this will block deployment
                        lock_types = [lock.level for lock in locks]
                        conflict = ResourceConflict(
                            conflict_type=ConflictType.LOCKED_RESOURCE_GROUP,
                            resource_name=rg_name,
                            resource_type="Microsoft.Resources/resourceGroups",
                            lock_type=", ".join(lock_types),
                            remediation_actions=[
                                f"Remove locks: az lock delete --resource-group {rg_name}",
                                "Cleanup script will skip locked RGs automatically",
                                "Use different target RG with --dest-rg",
                            ],
                        )
                        report.conflicts.append(conflict)
                        report.locked_rgs_found += 1

                except ResourceNotFoundError:
                    # RG doesn't exist yet (not a conflict)
                    logger.debug(f"RG {rg_name} not found (will be created)")
                except AzureError as e:
                    # Other Azure errors - log but continue
                    logger.debug(f"Could not check locks for RG {rg_name}: {e}")

            logger.info(
                f"Found {report.locked_rgs_found} locked resource group conflicts"
            )

        except Exception as e:
            logger.error(f"Error checking resource group locks: {e}")
            report.warnings.append(f"Failed to check RG locks: {e!s}")

    def _extract_resource_groups(
        self, resources: List[Dict[str, Any]]
    ) -> Set[str]:
        """Extract unique resource group names from planned resources."""
        rgs = set()
        for resource in resources:
            if resource.get("resource_group"):
                rgs.add(resource["resource_group"])
            # Also parse from resource ID if present
            elif "id" in resource:
                rid = resource["id"]
                if "/resourceGroups/" in rid:
                    rg = rid.split("/resourceGroups/")[1].split("/")[0]
                    rgs.add(rg)
        return rgs

    def _extract_key_vaults(self, resources: List[Dict[str, Any]]) -> List[str]:
        """Extract Key Vault names from planned resources."""
        vaults = []
        for resource in resources:
            if resource.get("type") == "Microsoft.KeyVault/vaults":
                if "name" in resource:
                    vaults.append(resource["name"])
        return vaults

    def _add_remediation_suggestions(self, report: ConflictReport) -> None:
        """Add global remediation suggestions based on conflict patterns."""
        if not report.has_conflicts:
            return

        # Add cleanup script suggestion if multiple conflicts
        if len(report.conflicts) >= 3:
            report.warnings.append(
                "Multiple conflicts detected. Consider running cleanup script: "
                "./scripts/cleanup_target_subscription.sh --dry-run"
            )

        # Add name suffix suggestion if name conflicts
        if report.existing_resources_found > 0 or report.soft_deleted_vaults_found > 0:
            report.warnings.append(
                "Use --name-suffix flag to automatically rename conflicting resources"
            )
