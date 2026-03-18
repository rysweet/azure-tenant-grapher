"""PostgreSQL Flexible Server handler for Terraform emission.

Handles: Microsoft.DBforPostgreSQL/flexibleServers
Emits: azurerm_postgresql_flexible_server
"""

import hashlib
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
        # PostgreSQL Flexible Server names are globally unique — add hash suffix
        sub_id = context.target_subscription_id or resource.get("subscription_id", "")
        name_suffix = hashlib.md5(sub_id.encode()).hexdigest()[:8]  # nosec B324
        unique_name = f"{resource_name}-{name_suffix}"[:63]  # max 63 chars
        safe_name = self.sanitize_name(unique_name)
        properties = self.parse_properties(resource)

        config = self.build_base_config(resource, resource_name_with_suffix=unique_name)

        # SKU — required by Terraform when create_mode=Default; fall back to a common SKU
        sku = properties.get("sku", {})
        config["sku_name"] = sku.get("name", "B_Standard_B1ms") if sku else "B_Standard_B1ms"

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
                password_auth_enabled = (
                    password_auth == "Enabled"  # pragma: allowlist secret
                    if password_auth
                    else True
                )
                config["authentication"] = {
                    "active_directory_auth_enabled": active_directory_auth == "Enabled",
                    "password_auth_enabled": password_auth_enabled,
                }
                # administrator_login + administrator_password are required when
                # create_mode=Default and password_auth_enabled=True (Azure API requirement)
                if password_auth_enabled:
                    if "administrator_login" not in config:
                        config["administrator_login"] = "psqladmin"  # pragma: allowlist secret
                    if "administrator_password" not in config:
                        resource_id = resource.get("id", resource.get("name", ""))
                        # Deterministic password meeting Azure complexity (upper+lower+digit+special)
                        pw_hash = hashlib.md5(resource_id.encode()).hexdigest()[:12]  # nosec B324
                        config["administrator_password"] = f"Psql@{pw_hash}1A"  # pragma: allowlist secret

        logger.debug(f"PostgreSQL Flexible Server '{resource_name}' emitted")

        return "azurerm_postgresql_flexible_server", safe_name, config
