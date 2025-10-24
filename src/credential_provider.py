"""
Credential Provider Module

This module provides centralized credential selection based on operation context,
enabling automatic switching between source and target tenant credentials.

Module: src/credential_provider.py
Specification: Specs/ServicePrincipalSwitching.md - Module 2
"""

import logging
from enum import Enum
from typing import Dict, Optional, Tuple

from azure.identity import ClientSecretCredential

from .dual_tenant_config import DualTenantConfig, TenantCredentials

logger = logging.getLogger(__name__)


class OperationType(Enum):
    """
    Types of operations requiring credentials.

    DISCOVERY: Read operations on source tenant (requires Reader role)
    DEPLOYMENT: Write operations on target tenant (requires Contributor role)
    VALIDATION: Validation operations (typically uses source tenant)
    """

    DISCOVERY = "discovery"
    DEPLOYMENT = "deployment"
    VALIDATION = "validation"


class TenantCredentialProvider:
    """
    Provides credentials based on operation context.

    This class selects the appropriate tenant credentials based on the operation
    type, supporting both single-tenant (backward compatible) and dual-tenant modes.

    Attributes:
        config: DualTenantConfig instance
        _credential_cache: Cache of credentials per tenant ID
        _current_tenant_id: Track current tenant for logging
    """

    def __init__(self, config: DualTenantConfig) -> None:
        """
        Initialize credential provider.

        Args:
            config: DualTenantConfig instance with source/target credentials

        Raises:
            ValueError: If config is invalid
        """
        self.config = config
        self._credential_cache: Dict[str, ClientSecretCredential] = {}
        self._current_tenant_id: Optional[str] = None

        # Validate config
        self.config.validate()

    def get_credential(
        self, operation: OperationType
    ) -> Tuple[ClientSecretCredential, str]:
        """
        Get credential for the specified operation type.

        Args:
            operation: Type of operation requiring credentials

        Returns:
            Tuple of (credential, tenant_id)

        Raises:
            ValueError: If required credentials not configured
        """
        # Select appropriate tenant credentials
        tenant_creds = self._select_tenant_credentials(operation)

        # Create and cache credential
        credential = self._get_or_create_credential(tenant_creds)

        # Log tenant switch if changed
        if self._current_tenant_id != tenant_creds.tenant_id:
            self._log_tenant_switch(tenant_creds, operation)
            self._current_tenant_id = tenant_creds.tenant_id

        return credential, tenant_creds.tenant_id

    def get_tenant_id(self, operation: OperationType) -> str:
        """
        Get tenant ID for the specified operation type.

        Args:
            operation: Type of operation

        Returns:
            Tenant ID string

        Raises:
            ValueError: If required credentials not configured
        """
        tenant_creds = self._select_tenant_credentials(operation)
        return tenant_creds.tenant_id

    def get_subscription_id(self, operation: OperationType) -> Optional[str]:
        """
        Get subscription ID for the specified operation type.

        Args:
            operation: Type of operation

        Returns:
            Subscription ID string or None if not configured

        Raises:
            ValueError: If required credentials not configured
        """
        tenant_creds = self._select_tenant_credentials(operation)
        return tenant_creds.subscription_id

    def _select_tenant_credentials(
        self, operation: OperationType
    ) -> TenantCredentials:
        """
        Select credentials based on operation and mode.

        Args:
            operation: Type of operation

        Returns:
            TenantCredentials for the operation

        Raises:
            ValueError: If required credentials not configured or operation unknown
        """
        # Single-tenant mode: use same credentials for everything
        if not self.config.is_dual_tenant_mode():
            if not self.config.source_tenant:
                raise ValueError(
                    "No credentials configured. Set AZURE_TENANT_ID, AZURE_CLIENT_ID, "
                    "AZURE_CLIENT_SECRET or enable dual-tenant mode."
                )
            return self.config.source_tenant

        # Dual-tenant mode: switch based on operation
        if operation == OperationType.DISCOVERY:
            if not self.config.source_tenant:
                raise ValueError(
                    "Source tenant credentials required for DISCOVERY operations"
                )
            return self.config.source_tenant

        elif operation == OperationType.DEPLOYMENT:
            if not self.config.target_tenant:
                raise ValueError(
                    "Target tenant credentials required for DEPLOYMENT operations"
                )
            return self.config.target_tenant

        elif operation == OperationType.VALIDATION:
            # Validation uses source tenant (read-only)
            if not self.config.source_tenant:
                raise ValueError(
                    "Source tenant credentials required for VALIDATION operations"
                )
            return self.config.source_tenant

        else:
            raise ValueError(f"Unknown operation type: {operation}")

    def _get_or_create_credential(
        self, tenant_creds: TenantCredentials
    ) -> ClientSecretCredential:
        """
        Get cached credential or create new one.

        Args:
            tenant_creds: Tenant credentials to use

        Returns:
            Azure ClientSecretCredential
        """
        tenant_id = tenant_creds.tenant_id

        if tenant_id not in self._credential_cache:
            logger.debug(
                f"Creating new credential for tenant {tenant_id} ({tenant_creds.role} role)"
            )

            credential = ClientSecretCredential(
                tenant_id=tenant_creds.tenant_id,
                client_id=tenant_creds.client_id,
                client_secret=tenant_creds.client_secret,
            )

            self._credential_cache[tenant_id] = credential

        return self._credential_cache[tenant_id]

    def _log_tenant_switch(
        self, tenant_creds: TenantCredentials, operation: OperationType
    ) -> None:
        """
        Log tenant context switch.

        Args:
            tenant_creds: Credentials being switched to
            operation: Operation type triggering the switch
        """
        # Determine tenant type for logging
        if self.config.is_dual_tenant_mode():
            if (
                self.config.source_tenant
                and tenant_creds.tenant_id == self.config.source_tenant.tenant_id
            ):
                tenant_type = "source"
            elif (
                self.config.target_tenant
                and tenant_creds.tenant_id == self.config.target_tenant.tenant_id
            ):
                tenant_type = "target"
            else:
                tenant_type = "unknown"
        else:
            tenant_type = "single"

        # Mask tenant ID for security (show first 8 chars)
        masked_tenant_id = tenant_creds.tenant_id[:8] + "..." if len(tenant_creds.tenant_id) > 8 else tenant_creds.tenant_id

        logger.info(
            f"Switching to {tenant_type} tenant ({masked_tenant_id}) for {operation.value.upper()} operation [{tenant_creds.role} role]"
        )

    def clear_cache(self) -> None:
        """Clear credential cache. Useful for testing or credential refresh."""
        logger.debug("Clearing credential cache")
        self._credential_cache.clear()
        self._current_tenant_id = None

    def get_current_tenant_id(self) -> Optional[str]:
        """Get the currently active tenant ID."""
        return self._current_tenant_id

    def is_dual_mode(self) -> bool:
        """Check if operating in dual-tenant mode."""
        return self.config.is_dual_tenant_mode()
