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
        safe_name = self.sanitize_name(resource_name)

        config = {
            "name": resource_name,
            "location": self.get_location(resource),
            "tags": self.parse_tags(resource, resource_name),
        }

        logger.debug(f"Resource Group '{resource_name}' emitted")

        return "azurerm_resource_group", safe_name, config
