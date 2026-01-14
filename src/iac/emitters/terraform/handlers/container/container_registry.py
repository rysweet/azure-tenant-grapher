"""Container Registry handler for Terraform emission.

Handles: Microsoft.ContainerRegistry/registries
Emits: azurerm_container_registry
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from src.services.azure_name_sanitizer import AzureNameSanitizer

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

    def __init__(self):
        """Initialize handler with Azure name sanitizer."""
        super().__init__()
        self.sanitizer = AzureNameSanitizer()

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
        # Sanitize using centralized Azure naming rules
        abstracted_name = config["name"]
        sanitized_name = self.sanitizer.sanitize(
            abstracted_name, "Microsoft.ContainerRegistry/registries"
        )

        # Add hash-based suffix for global uniqueness (works in all deployment modes)
        resource_id = resource.get("id", "")
        if resource_id:
            import hashlib

            hash_val = hashlib.md5(resource_id.encode()).hexdigest()[:6]
            base_name = sanitized_name.replace("-", "").lower()
            if len(base_name) > 44:  # 50 char limit - 6 char hash
                base_name = base_name[:44]
            config["name"] = f"{base_name}{hash_val}"
            logger.info(
                f"Container Registry name made globally unique: {resource_name} → {config['name']}"
            )
        else:
            config["name"] = sanitized_name

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
