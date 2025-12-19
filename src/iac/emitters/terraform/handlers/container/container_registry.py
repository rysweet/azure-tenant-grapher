"""Container Registry handler for Terraform emission.

Handles: Microsoft.ContainerRegistry/registries
Emits: azurerm_container_registry
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class ContainerRegistryHandler(ResourceHandler):
    """Handler for Azure Container Registries.

    Emits:
        - azurerm_container_registry
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.ContainerRegistry/registries",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_container_registry",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Container Registry to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        config = self.build_base_config(resource)

        # Container Registry names must be globally unique (*.azurecr.io)
        # Add tenant suffix for cross-tenant deployments
        if context.target_tenant_id and context.source_tenant_id != context.target_tenant_id:
            tenant_suffix = context.target_tenant_id[-6:].replace("-", "").lower()
            original_name = config["name"].replace("-", "").lower()

            # Truncate to fit (50 - 6 = 44 chars for original)
            if len(original_name) > 44:
                original_name = original_name[:44]

            config["name"] = f"{original_name}{tenant_suffix}"
            logger.info(
                f"Container Registry name updated for cross-tenant deployment: "
                f"{resource_name} -> {config['name']}"
            )

        # SKU (required)
        sku = properties.get("sku", {})
        sku_name = sku.get("name", "Basic") if isinstance(sku, dict) else "Basic"
        config["sku"] = sku_name

        # Admin enabled
        admin_enabled = properties.get("adminUserEnabled", False)
        if admin_enabled:
            config["admin_enabled"] = True

        logger.debug(f"Container Registry '{resource_name}' emitted")

        return "azurerm_container_registry", safe_name, config
