"""Recovery Services Vault handler for Terraform emission.

Handles: Microsoft.RecoveryServices/vaults
Emits: azurerm_recovery_services_vault
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class RecoveryServicesVaultHandler(ResourceHandler):
    """Handler for Azure Recovery Services Vaults.

    Emits:
        - azurerm_recovery_services_vault
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.RecoveryServices/vaults",
        "microsoft.recoveryservices/vaults",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_recovery_services_vault",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Recovery Services Vault to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        config = self.build_base_config(resource)

        # SKU
        sku = resource.get("sku", {})
        config["sku"] = (
            sku.get("name", "Standard") if isinstance(sku, dict) else "Standard"
        )

        # Soft delete
        security_settings = properties.get("securitySettings", {})
        soft_delete = security_settings.get("softDeleteSettings", {})
        if soft_delete:
            config["soft_delete_enabled"] = (
                soft_delete.get("softDeleteState", "Enabled") == "Enabled"
            )

        # Cross region restore
        if properties.get("redundancySettings", {}).get("crossRegionRestore"):
            config["cross_region_restore_enabled"] = (
                properties["redundancySettings"]["crossRegionRestore"] == "Enabled"
            )

        # Storage model type
        redundancy_settings = properties.get("redundancySettings", {})
        if redundancy_settings.get("standardTierStorageRedundancy"):
            storage_type = redundancy_settings["standardTierStorageRedundancy"]
            storage_type_map = {
                "LocallyRedundant": "LocallyRedundant",
                "GeoRedundant": "GeoRedundant",
                "ZoneRedundant": "ZoneRedundant",
            }
            config["storage_mode_type"] = storage_type_map.get(
                storage_type, "LocallyRedundant"
            )

        # Public network access
        if properties.get("publicNetworkAccess"):
            config["public_network_access_enabled"] = (
                properties.get("publicNetworkAccess", "Enabled") == "Enabled"
            )

        # Immutability
        immutability = security_settings.get("immutabilitySettings", {})
        if immutability.get("state"):
            config["immutability"] = immutability.get("state", "Disabled")

        # Identity
        identity = resource.get("identity", {})
        if identity.get("type"):
            identity_type = identity.get("type", "").lower()
            if "systemassigned" in identity_type:
                config["identity"] = {"type": "SystemAssigned"}

        # Encryption
        encryption = properties.get("encryption", {})
        if encryption.get("keyVaultProperties"):
            kv_props = encryption["keyVaultProperties"]
            config["encryption"] = {
                "key_id": kv_props.get("keyUri", ""),
                "infrastructure_encryption_enabled": encryption.get(
                    "infrastructureEncryption", "Disabled"
                )
                == "Enabled",
            }

        logger.debug(f"Recovery Services Vault '{resource_name}' emitted")

        return "azurerm_recovery_services_vault", safe_name, config
