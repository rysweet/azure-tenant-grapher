"""PostgreSQL Flexible Server handler for Terraform emission.

Handles: Microsoft.DBforPostgreSQL/flexibleServers
Emits: azurerm_postgresql_flexible_server
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class PostgreSQLFlexibleServerHandler(ResourceHandler):
    """Handler for Azure PostgreSQL Flexible Servers.

    Emits:
        - azurerm_postgresql_flexible_server
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.DBforPostgreSQL/flexibleServers",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_postgresql_flexible_server",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert PostgreSQL Flexible Server to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        config = self.build_base_config(resource)

        # SKU
        sku = properties.get("sku", {})
        if sku and "name" in sku:
            config["sku_name"] = sku["name"]

        # Version
        version = properties.get("version")
        if version:
            config["version"] = version

        # Storage
        storage = properties.get("storage", {})
        if storage and "storageSizeGB" in storage:
            config["storage_mb"] = storage["storageSizeGB"] * 1024

        # Optional: public_network_access_enabled (security - HIGH for network isolation)
        # Maps to Azure property: publicNetworkAccess
        public_network_access = properties.get("publicNetworkAccess")
        if public_network_access is not None:
            if public_network_access == "Enabled":
                config["public_network_access_enabled"] = True
            elif public_network_access == "Disabled":
                config["public_network_access_enabled"] = False
            else:
                logger.warning(
                    f"PostgreSQL Server '{resource_name}': publicNetworkAccess "
                    f"unexpected value '{public_network_access}', expected 'Enabled' or 'Disabled'"
                )

        # Optional: geo_redundant_backup_enabled (security/reliability - MEDIUM)
        # Maps to Azure property: backup.geoRedundantBackup
        backup_config = properties.get("backup", {})
        if isinstance(backup_config, dict):
            geo_redundant = backup_config.get("geoRedundantBackup")
            if geo_redundant == "Enabled":
                config["geo_redundant_backup_enabled"] = True
            elif geo_redundant == "Disabled":
                config["geo_redundant_backup_enabled"] = False

        # Optional: authentication configuration (security - HIGH)
        # Maps to Azure property: authConfig
        auth_config = properties.get("authConfig", {})
        if isinstance(auth_config, dict):
            active_directory_auth = auth_config.get("activeDirectoryAuth")
            password_auth = auth_config.get("passwordAuth")

            if active_directory_auth:
                config["authentication"] = {
                    "active_directory_auth_enabled": active_directory_auth == "Enabled",
                    "password_auth_enabled": password_auth
                    == "Enabled"  # pragma: allowlist secret
                    if password_auth
                    else True,
                }

        logger.debug(f"PostgreSQL Flexible Server '{resource_name}' emitted")

        return "azurerm_postgresql_flexible_server", safe_name, config
