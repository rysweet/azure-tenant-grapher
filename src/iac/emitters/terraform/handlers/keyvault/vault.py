"""Key Vault handler for Terraform emission.

Handles: Microsoft.KeyVault/vaults
Emits: azurerm_key_vault
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class KeyVaultHandler(ResourceHandler):
    """Handler for Azure Key Vaults.

    Emits:
        - azurerm_key_vault
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.KeyVault/vaults",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_key_vault",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Azure Key Vault to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        properties = self.parse_properties(resource)

        # Key Vaults need globally unique names with a suffix
        resource_id = resource.get("id", "")

        # Key Vaults have a 24-character name limit
        # Suffix is 7 characters ("-XXXXXX"), so max base name is 17 chars
        if len(resource_name) > 17:
            truncated_name = resource_name[:17]
            resource_name_with_suffix = self._add_unique_suffix(
                truncated_name, resource_id
            )
            logger.warning(
                f"Truncated Key Vault name '{resource_name}' to '{truncated_name}' "
                f"for suffix, resulting in '{resource_name_with_suffix}'"
            )
        else:
            resource_name_with_suffix = self._add_unique_suffix(
                resource_name, resource_id
            )

        safe_name = self.sanitize_name(resource_name_with_suffix)

        config = self.build_base_config(resource, resource_name_with_suffix)

        # SKU (required)
        sku = properties.get("sku", {})
        sku_name = sku.get("name", "standard") if isinstance(sku, dict) else "standard"
        config["sku_name"] = sku_name.lower()  # Fix #596: Terraform requires lowercase

        # Tenant ID (required)
        tenant_id = properties.get("tenantId") or context.target_tenant_id
        if tenant_id:
            config["tenant_id"] = tenant_id
        else:
            # Use variable reference
            config["tenant_id"] = "${var.tenant_id}"

        # Soft delete settings
        soft_delete_enabled = properties.get("enableSoftDelete", True)
        if soft_delete_enabled:
            config["soft_delete_retention_days"] = properties.get(
                "softDeleteRetentionInDays", 90
            )

        # Purge protection
        purge_protection = properties.get("enablePurgeProtection", False)
        if purge_protection:
            config["purge_protection_enabled"] = True

        logger.debug(
            f"Key Vault '{resource_name}' -> '{resource_name_with_suffix}' emitted"
        )

        return "azurerm_key_vault", safe_name, config

    def _add_unique_suffix(self, name: str, resource_id: str) -> str:
        """Add a unique suffix based on resource ID hash."""
        import hashlib

        if not resource_id:
            return name

        # Generate 6-character hash from resource ID
        hash_val = hashlib.md5(resource_id.encode()).hexdigest()[:6]
        return f"{name}-{hash_val}"
