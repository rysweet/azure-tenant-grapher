"""Service Plan handler for Terraform emission.

Handles: Microsoft.Web/serverFarms
Emits: azurerm_service_plan
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class ServicePlanHandler(ResourceHandler):
    """Handler for Azure App Service Plans.

    Emits:
        - azurerm_service_plan
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Web/serverFarms",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_service_plan",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Azure Service Plan to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        # Fix #601: Pass context to build_base_config for location override
        config = self.build_base_config(resource, context=context)

        # OS type (required)
        kind = properties.get("kind", resource.get("kind", "")).lower()
        os_type = "Linux" if "linux" in kind else "Windows"
        config["os_type"] = os_type

        # SKU name (required)
        sku = properties.get("sku", {})
        sku_name = sku.get("name", "B1") if isinstance(sku, dict) else "B1"
        config["sku_name"] = sku_name

        logger.debug(f"Service Plan '{resource_name}' emitted with os_type={os_type}")

        return "azurerm_service_plan", safe_name, config
