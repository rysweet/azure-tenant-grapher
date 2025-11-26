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

        logger.debug(f"PostgreSQL Flexible Server '{resource_name}' emitted")

        return "azurerm_postgresql_flexible_server", safe_name, config
