"""Container Registry handler for Terraform emission.

Handles: Microsoft.ContainerRegistry/registries
Emits: azurerm_container_registry
"""

import hashlib
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

    Note: Phase 5 fix - ID Abstraction Service now generates Azure-compliant names
    in the graph, so no sanitization needed here.
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
        # Phase 5: Names already Azure-compliant from ID Abstraction Service
        abstracted_name = config["name"]

        # Add hash-based suffix for global uniqueness (works in all deployment modes)
        resource_id = resource.get("id", "")
        if resource_id:
            hash_val = hashlib.md5(
                resource_id.encode(), usedforsecurity=False
            ).hexdigest()[:6]
            # Name already sanitized by ID Abstraction Service - just truncate if needed
            if len(abstracted_name) > 44:  # 50 char limit - 6 char hash
                abstracted_name = abstracted_name[:44]
            config["name"] = f"{abstracted_name}{hash_val}"
            logger.info(
                f"Container Registry name made globally unique: {resource_name} → {config['name']}"
            )
        else:
            config["name"] = abstracted_name

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
