"""Static Web App handler for Terraform emission.

Handles: Microsoft.Web/staticSites
Emits: azurerm_static_web_app
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class StaticWebAppHandler(ResourceHandler):
    """Handler for Azure Static Web Apps.

    Emits:
        - azurerm_static_web_app
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Web/staticSites",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_static_web_app",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Azure Static Web App to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        config = self.build_base_config(resource)

        # SKU
        sku = properties.get("sku", {})
        if sku and "name" in sku:
            config["sku_tier"] = sku.get("tier", "Free")
            config["sku_size"] = sku.get("name", "Free")

        logger.debug(f"Static Web App '{resource_name}' emitted")

        return "azurerm_static_web_app", safe_name, config
