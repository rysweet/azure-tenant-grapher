"""SQL Database handler for Terraform emission.

Handles: Microsoft.Sql/servers/databases
Emits: azurerm_mssql_database
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class SQLDatabaseHandler(ResourceHandler):
    """Handler for Azure SQL Databases.

    Emits:
        - azurerm_mssql_database
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Sql/servers/databases",
        "microsoft.sql/servers/databases",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_mssql_database",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Azure SQL Database to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        # Extract parent server name from database ID
        db_id = resource.get("id", "") or resource.get("original_id", "")
        server_name = self.extract_name_from_id(db_id, "servers")

        if server_name == "unknown":
            logger.warning(
                f"SQL Database '{resource_name}' has no parent server in ID: {db_id}. "
                f"Skipping."
            )
            return None

        server_safe = self.sanitize_name(server_name)

        # SQL Database only needs server_id, not location/resource_group_name
        config = {
            "name": resource_name,
            "server_id": f"${{azurerm_mssql_server.{server_safe}.id}}",
        }

        # SKU
        sku = properties.get("sku", {})
        if sku and "name" in sku:
            config["sku_name"] = sku["name"]

        # Max size
        max_size = properties.get("maxSizeBytes")
        if max_size:
            config["max_size_gb"] = max_size // (1024 * 1024 * 1024)

        logger.debug(
            f"SQL Database '{resource_name}' emitted for server '{server_name}'"
        )

        return "azurerm_mssql_database", safe_name, config
