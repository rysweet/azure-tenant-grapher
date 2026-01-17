"""Storage Account handler for Terraform emission.

Handles: Microsoft.Storage/storageAccounts
Emits: azurerm_storage_account
"""

import hashlib
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

    Note: Phase 5 fix - ID Abstraction Service now generates Azure-compliant names
    in the graph, so no sanitization needed here.
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
        # Phase 5: Names already Azure-compliant from ID Abstraction Service (no hyphens, lowercase)
        abstracted_name = config["name"]

        # Add hash-based suffix for global uniqueness (works in all deployment modes)
        if resource_id:
            hash_val = hashlib.md5(
                resource_id.encode(), usedforsecurity=False
            ).hexdigest()[:6]
            # Name already sanitized by ID Abstraction Service - just truncate if needed
            if len(abstracted_name) > 18:
                abstracted_name = abstracted_name[:18]
            config["name"] = f"{abstracted_name}{hash_val}"
            logger.info(
                f"Storage account name made globally unique: {resource_name} → {config['name']}"
            )
        else:
            config["name"] = abstracted_name

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

        # Optional: allow_nested_items_to_be_public (security)
        # Maps to Azure property: allowBlobPublicAccess
        # Note: Parameter renamed in azurerm v3.0+ (was allow_blob_public_access in v2.x)
        allow_blob_public_access = properties.get("allowBlobPublicAccess")
        if allow_blob_public_access is not None:
            if not isinstance(allow_blob_public_access, bool):
                logger.warning(
                    f"Storage account '{resource_name}': allowBlobPublicAccess "
                    f"expected bool, got {type(allow_blob_public_access).__name__}"
                )
            else:
                config["allow_nested_items_to_be_public"] = allow_blob_public_access

        # Optional: default_to_oauth_authentication (security)
        default_to_oauth = properties.get("defaultToOAuthAuthentication")
        if default_to_oauth is not None:
            if not isinstance(default_to_oauth, bool):
                logger.warning(
                    f"Storage account '{resource_name}': defaultToOAuthAuthentication "
                    f"expected bool, got {type(default_to_oauth).__name__}"
                )
            else:
                config["default_to_oauth_authentication"] = default_to_oauth

        # Optional: shared_access_key_enabled (security - CRITICAL for zero-trust)
        # Maps to Azure property: allowSharedKeyAccess
        # Note: Disabling shared key access forces OAuth/Entra ID authentication
        shared_key_access = properties.get("allowSharedKeyAccess")
        if shared_key_access is not None:
            if not isinstance(shared_key_access, bool):
                logger.warning(
                    f"Storage account '{resource_name}': allowSharedKeyAccess "
                    f"expected bool, got {type(shared_key_access).__name__}"
                )
            else:
                config["shared_access_key_enabled"] = shared_key_access

        # Optional: public_network_access_enabled (security - HIGH for network isolation)
        # Maps to Azure property: publicNetworkAccess
        # Note: Azure uses "Enabled"/"Disabled" strings, Terraform uses boolean
        public_network_access = properties.get("publicNetworkAccess")
        if public_network_access is not None:
            if public_network_access == "Enabled":
                config["public_network_access_enabled"] = True
            elif public_network_access == "Disabled":
                config["public_network_access_enabled"] = False
            else:
                logger.warning(
                    f"Storage account '{resource_name}': publicNetworkAccess "
                    f"unexpected value '{public_network_access}', expected 'Enabled' or 'Disabled'"
                )

        logger.debug(
            f"Storage Account '{resource_name}' emitted with "
            f"tier={account_tier}, replication={account_replication_type}"
        )

        return "azurerm_storage_account", safe_name, config
