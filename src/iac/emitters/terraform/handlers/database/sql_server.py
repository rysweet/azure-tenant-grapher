"""SQL Server handler for Terraform emission.

Handles: Microsoft.Sql/servers
Emits: azurerm_mssql_server, random_password
"""

import hashlib
import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from src.services.azure_name_sanitizer import AzureNameSanitizer

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

    def __init__(self):
        """Initialize handler with Azure name sanitizer."""
        super().__init__()
        self.sanitizer = AzureNameSanitizer()

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

        # SQL Server names must be globally unique (servername.database.windows.net)
        # Sanitize using centralized Azure naming rules
        abstracted_name = config["name"]
        sanitized_name = self.sanitizer.sanitize(
            abstracted_name, "Microsoft.Sql/servers"
        )

        # Add hash-based suffix for global uniqueness (works in all deployment modes)
        resource_id = resource.get("id", "")
        if resource_id:
            hash_val = hashlib.md5(
                resource_id.encode(), usedforsecurity=False
            ).hexdigest()[:6]
            base_name = sanitized_name.replace("-", "").lower()
            if len(base_name) > 57:  # 63 char limit - 6 char hash
                base_name = base_name[:57]
            config["name"] = f"{base_name}{hash_val}"
            logger.info(
                f"SQL Server name made globally unique: {resource_name} → {config['name']}"
            )
        else:
            config["name"] = sanitized_name

        config.update(
            {
                "version": resource.get("version", "12.0"),
                "administrator_login": resource.get("administrator_login", "sqladmin"),
                "administrator_login_password": f"${{random_password.{password_resource_name}.result}}",
            }
        )

        logger.debug(f"SQL Server '{resource_name}' emitted")

        return "azurerm_mssql_server", safe_name, config
