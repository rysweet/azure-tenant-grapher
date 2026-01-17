"""SQL Server handler for Terraform emission.

Handles: Microsoft.Sql/servers
Emits: azurerm_mssql_server, random_password
"""

import hashlib
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

    Note: Phase 5 fix - ID Abstraction Service now generates Azure-compliant names
    in the graph, so no sanitization needed here.
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

        # SQL Server names must be globally unique (servername.database.windows.net)
        # Phase 5: Names already Azure-compliant from ID Abstraction Service
        abstracted_name = config["name"]

        # Add hash-based suffix for global uniqueness (works in all deployment modes)
        resource_id = resource.get("id", "")
        if resource_id:
            hash_val = hashlib.md5(
                resource_id.encode(), usedforsecurity=False
            ).hexdigest()[:6]
            # Name already sanitized by ID Abstraction Service - just truncate if needed
            if len(abstracted_name) > 57:  # 63 char limit - 6 char hash
                abstracted_name = abstracted_name[:57]
            config["name"] = f"{abstracted_name}{hash_val}"
            logger.info(
                f"SQL Server name made globally unique: {resource_name} → {config['name']}"
            )
        else:
            config["name"] = abstracted_name

        config.update(
            {
                "version": resource.get("version", "12.0"),
                "administrator_login": resource.get("administrator_login", "sqladmin"),
                "administrator_login_password": f"${{random_password.{password_resource_name}.result}}",
            }
        )

        # Extract properties for security settings
        properties = resource.get("properties", {})

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
                    f"SQL Server '{resource_name}': publicNetworkAccess "
                    f"unexpected value '{public_network_access}', expected 'Enabled' or 'Disabled'"
                )

        # Optional: minimum_tls_version (security - MEDIUM for protocol enforcement)
        # Maps to Azure property: minimalTlsVersion
        min_tls_version = properties.get("minimalTlsVersion")
        if min_tls_version:
            config["minimum_tls_version"] = min_tls_version

        # Optional: azuread_authentication_only (security - HIGH for auth enforcement)
        # Maps to Azure property in administrators object
        administrators = properties.get("administrators", {})
        if isinstance(administrators, dict):
            azuread_only = administrators.get("azureADOnlyAuthentication")
            if azuread_only is not None:
                if not isinstance(azuread_only, bool):
                    logger.warning(
                        f"SQL Server '{resource_name}': azureADOnlyAuthentication "
                        f"expected bool, got {type(azuread_only).__name__}"
                    )
                else:
                    config["azuread_administrator"] = {
                        "azuread_authentication_only": azuread_only
                    }

        logger.debug(f"SQL Server '{resource_name}' emitted")

        return "azurerm_mssql_server", safe_name, config
