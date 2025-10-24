"""
Dual Tenant Configuration Module

This module provides configuration support for dual-tenant operations where
source and target tenants use different service principal credentials.

Module: src/dual_tenant_config.py
Specification: Specs/ServicePrincipalSwitching.md - Module 1
"""

import logging
import os
from dataclasses import dataclass
from typing import Literal, Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class TenantCredentials:
    """
    Credentials for a single tenant.

    Attributes:
        tenant_id: Azure tenant ID
        client_id: Service principal client ID
        client_secret: Service principal client secret
        subscription_id: Optional subscription ID
        role: Expected role (Reader or Contributor) - for documentation/logging
    """

    tenant_id: str
    client_id: str
    client_secret: str
    subscription_id: Optional[str] = None
    role: str = "Reader"

    def __post_init__(self) -> None:
        """Validate credentials after initialization."""
        if not self.tenant_id:
            raise ValueError("Tenant ID is required")
        if not self.client_id:
            raise ValueError("Client ID is required")
        if not self.client_secret:
            raise ValueError("Client secret is required")

    def mask_secret(self) -> str:
        """Return a safe representation for logging."""
        return f"TenantCredentials(tenant_id={self.tenant_id}, client_id={self.client_id}, role={self.role})"


@dataclass
class DualTenantConfig:
    """
    Configuration for dual-tenant operations.

    Attributes:
        source_tenant: Credentials for source tenant (discovery/read operations)
        target_tenant: Credentials for target tenant (deployment/write operations)
        operation_mode: Single or dual tenant mode
        auto_switch: Whether to automatically switch credentials based on operation
    """

    source_tenant: Optional[TenantCredentials] = None
    target_tenant: Optional[TenantCredentials] = None
    operation_mode: Literal["single", "dual"] = "single"
    auto_switch: bool = True

    def is_dual_tenant_mode(self) -> bool:
        """Check if dual-tenant mode is enabled and configured."""
        return (
            self.operation_mode == "dual"
            and self.source_tenant is not None
            and self.target_tenant is not None
        )

    def validate(self) -> None:
        """Validate dual-tenant configuration."""
        if self.operation_mode == "dual":
            if not self.source_tenant:
                raise ValueError(
                    "Source tenant credentials required when dual-tenant mode is enabled"
                )
            if not self.target_tenant:
                raise ValueError(
                    "Target tenant credentials required when dual-tenant mode is enabled"
                )

            # Validate individual credentials
            self.source_tenant.__post_init__()
            self.target_tenant.__post_init__()

            logger.info(
                f"Dual-tenant mode validated: source={self.source_tenant.tenant_id}, "
                f"target={self.target_tenant.tenant_id}"
            )
        elif self.operation_mode == "single":
            logger.debug("Single-tenant mode configured")
        else:
            raise ValueError(
                f"Invalid operation mode: {self.operation_mode}. Must be 'single' or 'dual'"
            )


def create_dual_tenant_config_from_env() -> DualTenantConfig:
    """
    Create DualTenantConfig from environment variables.

    This function supports both single-tenant and dual-tenant configurations:

    Single-tenant mode (backward compatible):
    - Uses AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET
    - operation_mode = "single"

    Dual-tenant mode:
    - Requires AZTG_DUAL_TENANT_MODE=true
    - Source tenant: AZURE_SOURCE_TENANT_ID, AZURE_SOURCE_TENANT_CLIENT_ID, etc.
    - Target tenant: AZURE_TARGET_TENANT_ID, AZURE_TARGET_TENANT_CLIENT_ID, etc.
    - operation_mode = "dual"

    Returns:
        DualTenantConfig: Configured instance

    Raises:
        ValueError: If dual mode enabled but credentials missing
    """
    # Check if dual-tenant mode is explicitly enabled
    dual_mode_enabled = os.getenv("AZTG_DUAL_TENANT_MODE", "false").lower() == "true"
    auto_switch = os.getenv("AZTG_AUTO_SWITCH", "true").lower() == "true"

    # Try to load source tenant credentials
    source_tenant_id = os.getenv("AZURE_SOURCE_TENANT_ID")
    source_client_id = os.getenv("AZURE_SOURCE_TENANT_CLIENT_ID")
    source_client_secret = os.getenv("AZURE_SOURCE_TENANT_CLIENT_SECRET")
    source_subscription_id = os.getenv("AZURE_SOURCE_TENANT_SUBSCRIPTION_ID")

    # Try to load target tenant credentials
    target_tenant_id = os.getenv("AZURE_TARGET_TENANT_ID")
    target_client_id = os.getenv("AZURE_TARGET_TENANT_CLIENT_ID")
    target_client_secret = os.getenv("AZURE_TARGET_TENANT_CLIENT_SECRET")
    target_subscription_id = os.getenv("AZURE_TARGET_TENANT_SUBSCRIPTION_ID")

    # Determine operation mode
    has_source = all([source_tenant_id, source_client_id, source_client_secret])
    has_target = all([target_tenant_id, target_client_id, target_client_secret])

    if dual_mode_enabled and has_source and has_target:
        # Dual-tenant mode
        source_tenant = TenantCredentials(
            tenant_id=source_tenant_id,  # type: ignore
            client_id=source_client_id,  # type: ignore
            client_secret=source_client_secret,  # type: ignore
            subscription_id=source_subscription_id,
            role="Reader",
        )

        target_tenant = TenantCredentials(
            tenant_id=target_tenant_id,  # type: ignore
            client_id=target_client_id,  # type: ignore
            client_secret=target_client_secret,  # type: ignore
            subscription_id=target_subscription_id,
            role="Contributor",
        )

        config = DualTenantConfig(
            source_tenant=source_tenant,
            target_tenant=target_tenant,
            operation_mode="dual",
            auto_switch=auto_switch,
        )

        logger.info(
            f"Dual-tenant configuration loaded: source={source_tenant_id}, target={target_tenant_id}"
        )

        return config

    elif dual_mode_enabled:
        # Dual mode requested but credentials incomplete
        raise ValueError(
            "AZTG_DUAL_TENANT_MODE is enabled but source/target credentials are incomplete. "
            "Required: AZURE_SOURCE_TENANT_ID, AZURE_SOURCE_TENANT_CLIENT_ID, "
            "AZURE_SOURCE_TENANT_CLIENT_SECRET, AZURE_TARGET_TENANT_ID, "
            "AZURE_TARGET_TENANT_CLIENT_ID, AZURE_TARGET_TENANT_CLIENT_SECRET"
        )

    else:
        # Single-tenant mode (backward compatible)
        # Check if we have single-tenant credentials for fallback
        single_tenant_id = os.getenv("AZURE_TENANT_ID")
        single_client_id = os.getenv("AZURE_CLIENT_ID")
        single_client_secret = os.getenv("AZURE_CLIENT_SECRET")

        if single_tenant_id and single_client_id and single_client_secret:
            # Create a single-tenant config using the standard env vars
            # This is stored as source_tenant for consistency
            source_tenant = TenantCredentials(
                tenant_id=single_tenant_id,
                client_id=single_client_id,
                client_secret=single_client_secret,
                subscription_id=os.getenv("AZURE_SUBSCRIPTION_ID"),
                role="Reader",  # Default role
            )

            config = DualTenantConfig(
                source_tenant=source_tenant,
                target_tenant=None,
                operation_mode="single",
                auto_switch=False,  # No auto-switching in single mode
            )

            logger.debug(
                f"Single-tenant configuration loaded: tenant={single_tenant_id}"
            )
            return config

        # No credentials available at all
        logger.warning(
            "No Azure credentials found in environment. "
            "Set AZURE_TENANT_ID/AZURE_CLIENT_ID/AZURE_CLIENT_SECRET or enable dual-tenant mode."
        )

        return DualTenantConfig(
            source_tenant=None,
            target_tenant=None,
            operation_mode="single",
            auto_switch=False,
        )
