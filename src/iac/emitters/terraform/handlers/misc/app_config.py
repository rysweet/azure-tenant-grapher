"""App Configuration handler for Terraform emission.

Handles: Microsoft.AppConfiguration/configurationStores
Emits: azurerm_app_configuration
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class AppConfigurationHandler(ResourceHandler):
    """Handler for Azure App Configuration.

    Emits:
        - azurerm_app_configuration
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.AppConfiguration/configurationStores",
        "microsoft.appconfiguration/configurationstores",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_app_configuration",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert App Configuration to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        config = self.build_base_config(resource)

        # SKU
        sku = resource.get("sku", {})
        config["sku"] = sku.get("name", "free") if isinstance(sku, dict) else "free"

        # Public network access
        if properties.get("publicNetworkAccess"):
            config["public_network_access"] = properties.get("publicNetworkAccess")

        # Soft delete retention
        if properties.get("softDeleteRetentionInDays"):
            config["soft_delete_retention_days"] = properties.get(
                "softDeleteRetentionInDays"
            )

        # Purge protection
        if properties.get("enablePurgeProtection") is not None:
            config["purge_protection_enabled"] = properties.get("enablePurgeProtection")

        # Local auth
        if properties.get("disableLocalAuth") is not None:
            config["local_auth_enabled"] = not properties.get("disableLocalAuth")

        # Identity
        identity = resource.get("identity", {})
        if identity.get("type"):
            identity_type = identity.get("type", "").lower()
            if "systemassigned" in identity_type:
                config["identity"] = {"type": "SystemAssigned"}
            elif "userassigned" in identity_type:
                user_ids = list(identity.get("userAssignedIdentities", {}).keys())
                if user_ids:
                    config["identity"] = {
                        "type": "UserAssigned",
                        "identity_ids": user_ids,
                    }

        # Encryption
        encryption = properties.get("encryption", {})
        if encryption.get("keyVaultProperties"):
            kv_props = encryption["keyVaultProperties"]
            config["encryption"] = {
                "key_vault_key_identifier": kv_props.get("keyIdentifier", ""),
            }
            if kv_props.get("identityClientId"):
                config["encryption"]["identity_client_id"] = kv_props.get(
                    "identityClientId"
                )

        logger.debug(f"App Configuration '{resource_name}' emitted")

        return "azurerm_app_configuration", safe_name, config
