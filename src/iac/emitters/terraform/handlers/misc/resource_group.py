"""Resource Group handler for Terraform emission.

Handles: Microsoft.Resources/resourceGroups
Emits: azurerm_resource_group
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class ResourceGroupHandler(ResourceHandler):
    """Handler for Azure Resource Groups.

    Emits:
        - azurerm_resource_group
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "microsoft.resources/resourcegroups",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_resource_group",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Resource Group to Terraform configuration."""
        resource_name = resource.get("name", "unknown")

        # Skip Azure-managed resource groups (cannot be created via Terraform)
        # These are automatically created by Azure services (AKS, App Insights, etc.)
        if "_managed" in resource_name or resource_name.startswith("NetworkWatcherRG"):
            logger.debug(f"Skipping Azure-managed resource group: {resource_name}")
            return None

        safe_name = self.sanitize_name(resource_name)

        config = {
            "name": resource_name,
            "location": self.get_location(resource),
        }

        # Add tags if present (matching legacy behavior)
        tags = resource.get("tags")
        if tags:
            parsed_tags = self.parse_tags(tags, resource_name)
            if parsed_tags:
                config["tags"] = parsed_tags

        logger.debug(f"Resource Group '{resource_name}' emitted")

        return "azurerm_resource_group", safe_name, config
