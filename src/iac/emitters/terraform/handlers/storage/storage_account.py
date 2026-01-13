"""Storage Account handler for Terraform emission.

Handles: Microsoft.Storage/storageAccounts
Emits: azurerm_storage_account
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class StorageAccountHandler(ResourceHandler):
    """Handler for Azure Storage Accounts.

    Emits:
        - azurerm_storage_account
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Storage/storageAccounts",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_storage_account",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Azure Storage Account to Terraform configuration.

        Args:
            resource: Azure resource dictionary from graph
            context: Shared emitter context

        Returns:
            Tuple of (terraform_type, resource_name, config) or None if skipped
        """
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)

        # Skip Databricks-managed storage accounts (have deny assignments)
        resource_id = resource.get("id", "")
        resource_group_name = resource.get("resource_group_name", "")
        # Check both ID and resource_group_name field
        if (
            "databricks-rg" in resource_id.lower()
            or "databricks-rg" in resource_group_name.lower()
        ):
            logger.info(
                f"Skipping Databricks-managed storage account '{resource_name}' in RG '{resource_group_name}' "
                "(has Azure deny assignments)"
            )
            return None

        # Also skip by name pattern (dbstorage* are Databricks-managed)
        if resource_name.startswith("dbstorage"):
            logger.info(
                f"Skipping Databricks storage account by name pattern: '{resource_name}'"
            )
            return None

        # Build base configuration
        config = self.build_base_config(resource)

        # Storage account names must be globally unique (*.core.windows.net)
        # Add tenant-specific suffix for cross-tenant deployments
        # Constraints: lowercase alphanumeric only, max 24 chars
        original_name = config["name"]
        if (
            context.target_tenant_id
            and context.source_tenant_id != context.target_tenant_id
        ):
            # Add target tenant suffix (last 6 chars of tenant ID, alphanumeric only)
            tenant_suffix = context.target_tenant_id[-6:].replace("-", "").lower()
            # Remove hyphens and convert to lowercase for storage account name
            original_name = original_name.replace("-", "").lower()

            # Truncate to fit (24 - 6 = 18 chars for original)
            if len(original_name) > 18:
                original_name = original_name[:18]

            config["name"] = f"{original_name}{tenant_suffix}"
            logger.info(
                f"Storage account name made globally unique: {resource_name} → {config['name']}"
            )

        # Storage account specific properties
        properties = self.parse_properties(resource)

        # Account tier and replication type are required
        account_tier = resource.get("account_tier") or properties.get(
            "accountTier", "Standard"
        )
        account_replication_type = resource.get(
            "account_replication_type"
        ) or properties.get("replicationType", "LRS")

        # Handle SKU extraction from properties
        sku = properties.get("sku", {})
        if sku and isinstance(sku, dict):
            sku_name = sku.get("name", "Standard_LRS")
            # Parse SKU name (e.g., "Standard_LRS" -> tier="Standard", replication="LRS")
            if "_" in sku_name:
                parts = sku_name.split("_")
                account_tier = parts[0]
                account_replication_type = "_".join(parts[1:])

        config.update(
            {
                "account_tier": account_tier,
                "account_replication_type": account_replication_type,
            }
        )

        # Optional: account_kind (default is StorageV2)
        kind = properties.get("kind") or resource.get("kind")
        if kind:
            config["account_kind"] = kind

        # Optional: access_tier (for BlobStorage and StorageV2)
        access_tier = properties.get("accessTier") or resource.get("access_tier")
        if access_tier:
            config["access_tier"] = access_tier

        # Optional: HTTPS traffic only - Fix #596: Property renamed in provider v4+
        https_only = properties.get("supportsHttpsTrafficOnly")
        if https_only is not None:
            config["https_traffic_only_enabled"] = https_only

        # Optional: min_tls_version
        tls_version = properties.get("minimumTlsVersion")
        if tls_version:
            config["min_tls_version"] = tls_version

        logger.debug(
            f"Storage Account '{resource_name}' emitted with "
            f"tier={account_tier}, replication={account_replication_type}"
        )

        return "azurerm_storage_account", safe_name, config
