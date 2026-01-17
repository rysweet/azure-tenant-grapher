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

        # Bug #43: Strip parent prefix from child resource names
        # Azure format: "server_name/database_name", Terraform needs: "database_name"
        database_name = (
            resource_name.split("/")[-1] if "/" in resource_name else resource_name
        )

        # SQL Database only needs server_id, not location/resource_group_name
        config = {
            "name": database_name,
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

        # Optional: transparent_data_encryption (security - HIGH for encryption at rest)
        # Maps to Azure property: transparentDataEncryption (nested property)
        # Note: This may be in a separate resource, check if properties contain TDE settings
        tde_config = properties.get("transparentDataEncryption")
        if tde_config and isinstance(tde_config, dict):
            tde_status = tde_config.get("status")
            if tde_status == "Enabled":
                # Note: TDE is typically enabled by default in newer Azure SQL versions
                # We'll add a note that TDE is expected to be enabled
                logger.info(f"SQL Database '{resource_name}': Transparent Data Encryption enabled")

        # Optional: ledger_enabled (security - MEDIUM for immutable audit log)
        # Maps to Azure property: isLedgerDatabase
        is_ledger = properties.get("isLedgerDatabase")
        if is_ledger is not None:
            if not isinstance(is_ledger, bool):
                logger.warning(
                    f"SQL Database '{resource_name}': isLedgerDatabase "
                    f"expected bool, got {type(is_ledger).__name__}"
                )
            else:
                config["ledger_enabled"] = is_ledger

        # Optional: zone_redundant (reliability/security - MEDIUM)
        # Maps to Azure property: zoneRedundant
        zone_redundant = properties.get("zoneRedundant")
        if zone_redundant is not None:
            if not isinstance(zone_redundant, bool):
                logger.warning(
                    f"SQL Database '{resource_name}': zoneRedundant "
                    f"expected bool, got {type(zone_redundant).__name__}"
                )
            else:
                config["zone_redundant"] = zone_redundant

        logger.debug(
            f"SQL Database '{resource_name}' emitted for server '{server_name}'"
        )

        return "azurerm_mssql_database", safe_name, config
