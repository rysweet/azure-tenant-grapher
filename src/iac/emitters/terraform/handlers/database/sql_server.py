"""SQL Server handler for Terraform emission.

Handles: Microsoft.Sql/servers
Emits: azurerm_mssql_server, random_password
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class SQLServerHandler(ResourceHandler):
    """Handler for Azure SQL Servers.

    Emits:
        - azurerm_mssql_server
        - random_password (helper resource)
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Sql/servers",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_mssql_server",
        "random_password",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Azure SQL Server to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)

        # Generate a unique password for each SQL server
        password_resource_name = f"{safe_name}_password"

        # Add random_password resource
        context.add_helper_resource(
            "random_password",
            password_resource_name,
            {
                "length": 20,
                "special": True,
                "override_special": "!@#$%&*()-_=+[]{}<>:?",
                "min_lower": 1,
                "min_upper": 1,
                "min_numeric": 1,
                "min_special": 1,
            },
        )

        config = self.build_base_config(resource)

        config.update(
            {
                "version": resource.get("version", "12.0"),
                "administrator_login": resource.get("administrator_login", "sqladmin"),
                "administrator_login_password": f"${{random_password.{password_resource_name}.result}}",
            }
        )

        logger.debug(f"SQL Server '{resource_name}' emitted")

        return "azurerm_mssql_server", safe_name, config
