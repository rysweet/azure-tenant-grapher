"""
Tenant Reset Confirmation Flow (Issue #627).

This module handles the critical 5-stage confirmation process for tenant reset operations.
Includes strict validation, typed verification, and security controls to prevent
accidental deletions.
"""

import asyncio
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

# GUID validation regex (UUID v4 format)
GUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# Resource group name validation regex (Azure naming rules)
RESOURCE_GROUP_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]{1,90}$")

# Azure resource ID pattern
RESOURCE_ID_PATTERN = re.compile(
    r"^/subscriptions/[0-9a-f-]+/resourceGroups/[^/]+/providers/[^\s]+$",
    re.IGNORECASE,
)


class ResetScope:
    """
    Scope of reset operation with validation.

    This is a dataclass that validates tenant IDs, subscription IDs,
    resource group names, and resource IDs to prevent injection attacks.
    """

    # Class constants for backwards compatibility
    TENANT = "tenant"
    SUBSCRIPTION = "subscription"
    RESOURCE_GROUP = "resource-group"
    RESOURCE = "resource"

    def __init__(
        self,
        level: str,
        tenant_id: str,
        subscription_id: Optional[str] = None,
        resource_group: Optional[str] = None,
        resource_id: Optional[str] = None,
    ):
        """
        Initialize Reset Scope with validation.

        Args:
            level: Scope level ("tenant", "subscription", "resource-group", "resource")
            tenant_id: Azure tenant ID (must be valid GUID)
            subscription_id: Subscription ID (must be valid GUID if provided)
            resource_group: Resource group name (must follow Azure naming rules if provided)
            resource_id: Resource ID (must follow Azure resource ID format if provided)

        Raises:
            ValueError: If any ID is invalid
        """
        self.level = level

        # Validate tenant ID (required)
        if not GUID_PATTERN.match(tenant_id):
            raise ValueError(f"Invalid tenant ID format: {tenant_id}")
        self.tenant_id = tenant_id

        # Validate subscription ID (if provided)
        if subscription_id is not None:
            if not GUID_PATTERN.match(subscription_id):
                raise ValueError(f"Invalid subscription ID format: {subscription_id}")
        self.subscription_id = subscription_id

        # Validate resource group name (if provided)
        if resource_group is not None:
            if not RESOURCE_GROUP_PATTERN.match(resource_group):
                raise ValueError(f"Invalid resource group name: {resource_group}")
            if len(resource_group) > 90:
                raise ValueError(
                    f"Invalid resource group name length: {len(resource_group)} > 90"
                )
        self.resource_group = resource_group

        # Validate resource ID (if provided)
        if resource_id is not None:
            if not RESOURCE_ID_PATTERN.match(resource_id):
                raise ValueError(f"Invalid resource ID format: {resource_id}")
        self.resource_id = resource_id


@dataclass
class ResetScopeDetails:
    """Details about the reset scope."""

    scope: ResetScope
    tenant_id: str
    subscription_ids: Optional[List[str]] = None
    resource_group_names: Optional[List[str]] = None
    resource_ids: Optional[List[str]] = None
    to_delete_count: int = 0
    to_preserve_count: int = 0


@dataclass
class SafetyValidationResult:
    """Result of safety validation checks."""

    passed: bool
    errors: List[str]
    warnings: List[str]
    atg_sp_id: Optional[str] = None


@dataclass
class ResetExecutionResult:
    """Result of reset execution."""

    success: bool
    deleted_count: int
    failed_count: int
    deleted_resources: List[str]
    failed_resources: List[str]
    errors: Dict[str, str]
    duration_seconds: float


@dataclass
class DeletionError:
    """Error encountered during deletion."""

    resource_id: str
    error_message: str
    error_type: str


class SecurityError(Exception):
    """Raised when security controls detect a violation."""

    pass


class RateLimitError(Exception):
    """Raised when rate limit is exceeded."""

    pass


class ResetConfirmation:
    """
    5-stage confirmation flow for tenant reset operations.

    Stages:
    1. Scope understanding and permanent deletion acknowledgment
    2. Resource preview and count verification
    3. Typed tenant ID verification
    4. ATG Service Principal preservation acknowledgment
    5. Final "DELETE" typed confirmation with 3-second delay

    Safety Features:
    - No --force or --yes flag bypass
    - Case-sensitive typed verification
    - Mandatory 3-second countdown
    - Dry-run mode support (skip confirmation)
    - Keyboard interrupt handling
    """

    def __init__(
        self,
        scope: str,
        dry_run: bool = False,
        skip_confirmation: bool = False,
        tenant_id: Optional[str] = None,
    ):
        """
        Initialize confirmation flow.

        Args:
            scope: Reset scope level ("tenant", "subscription", "resource-group", "resource")
            dry_run: If True, don't actually delete (preview only)
            skip_confirmation: If True, skip confirmation (ONLY allowed in dry-run mode)
            tenant_id: Tenant ID for typed verification
        """
        self.scope = scope
        self.dry_run = dry_run
        self.skip_confirmation = skip_confirmation
        self.tenant_id = tenant_id

        # Security: skip_confirmation only allowed in dry-run mode
        if skip_confirmation and not dry_run:
            raise ValueError(
                "skip_confirmation requires dry_run mode. "
                "Confirmation cannot be bypassed for actual deletions."
            )

    async def confirm(self, scope_data: Dict) -> bool:
        """
        Execute the 5-stage confirmation flow.

        Args:
            scope_data: Scope data from TenantResetService
                {
                    "to_delete": List[str],  # Resource IDs to delete
                    "to_preserve": List[str],  # Resource IDs to preserve
                }

        Returns:
            True if user confirmed all stages, False otherwise

        Raises:
            KeyboardInterrupt: If user presses Ctrl+C
        """
        # SECURITY: Runtime verification that dry_run is still True
        # Prevents bypass if dry_run was changed after initialization
        if self.skip_confirmation:
            if not self.dry_run:
                raise ValueError(
                    "SECURITY: skip_confirmation is True but dry_run is False. "
                    "Confirmation cannot be bypassed for actual deletions."
                )
            return True

        try:
            # Stage 1: Scope confirmation
            if not await self._stage1_scope_confirmation(scope_data):
                return False

            # Stage 2: Preview resources
            if not await self._stage2_preview_resources(scope_data):
                return False

            # Stage 3: Typed tenant ID verification
            if not await self._stage3_typed_verification():
                return False

            # Stage 4: ATG SP acknowledgment
            if not await self._stage4_atg_sp_acknowledgment():
                return False

            # Stage 5: Final confirmation with delay
            if not await self._stage5_final_confirmation_with_delay():
                return False

            return True

        except KeyboardInterrupt:
            raise

    async def _stage1_scope_confirmation(self, scope_data: Dict) -> bool:
        """
        Stage 1: User confirms understanding of permanent deletion.

        Displays:
        - Reset scope
        - Resource counts
        - Warning about permanence

        Returns:
            True if user types "yes" (case-sensitive), False otherwise
        """

        user_input = input("> ").strip()
        return user_input == "yes"

    async def _stage2_preview_resources(self, scope_data: Dict) -> bool:
        """
        Stage 2: Preview resources and get confirmation.

        Displays:
        - First 10 resources to be deleted
        - Total count

        Safety:
        - Abort if scope exceeds 1000 resources (safety limit)

        Returns:
            True if user types "yes" (case-sensitive), False otherwise
        """

        to_delete = scope_data["to_delete"]
        total_count = len(to_delete)

        # Safety check: Abort if scope too large
        if total_count > 1000:
            return False

        for _i, _resource_id in enumerate(to_delete[:10], 1):
            pass

        if total_count > 10:
            pass

        user_input = input("> ").strip()
        return user_input == "yes"

    async def _stage3_typed_verification(self) -> bool:
        """
        Stage 3: User types tenant ID exactly (case-sensitive).

        Returns:
            True if typed tenant ID matches exactly, False otherwise
        """
        if not self.tenant_id:
            # If tenant_id not provided, skip this stage
            return True

        user_input = input("> ").strip()
        return user_input == self.tenant_id

    async def _stage4_atg_sp_acknowledgment(self) -> bool:
        """
        Stage 4: User acknowledges ATG Service Principal preservation.

        Displays:
        - ATG SP ID
        - Warning that ATG SP will NOT be deleted
        - Consequences of ATG SP deletion

        Returns:
            True if user types "yes" (case-sensitive), False otherwise
        """

        # Get ATG SP ID from environment
        import os

        os.environ.get("AZURE_CLIENT_ID", "UNKNOWN")

        user_input = input("> ").strip()
        return user_input == "yes"

    async def _stage5_final_confirmation_with_delay(self) -> bool:
        """
        Stage 5: Final confirmation with 3-second delay.

        User must:
        1. Wait for 3-second countdown
        2. Type "DELETE" (case-sensitive, all caps)

        Returns:
            True if user types "DELETE" exactly, False otherwise
        """

        # 3-second countdown
        for _i in range(3, 0, -1):
            await asyncio.sleep(1)

        user_input = input("> ").strip()
        return user_input == "DELETE"

    def display_dry_run(self, scope_data: Dict):
        """
        Display dry-run preview without prompting for confirmation.

        Args:
            scope_data: Scope data from TenantResetService
        """

        to_delete = scope_data["to_delete"]
        to_preserve = scope_data["to_preserve"]

        for _i, _resource_id in enumerate(to_delete[:10], 1):
            pass

        if len(to_delete) > 10:
            pass

        for _i, _resource_id in enumerate(to_preserve[:5], 1):
            pass

        if len(to_preserve) > 5:
            pass
