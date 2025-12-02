"""Action Group handler for Terraform emission.

Handles: Microsoft.Insights/actionGroups
Emits: azurerm_monitor_action_group
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class ActionGroupHandler(ResourceHandler):
    """Handler for Monitor Action Groups.

    Emits:
        - azurerm_monitor_action_group
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "microsoft.insights/actiongroups",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_monitor_action_group",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Action Group to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        config = self.build_base_config(resource)

        # short_name is required (max 12 characters)
        short_name = (
            properties.get("groupShortName")
            or properties.get("short_name")
            or resource_name[:12]
        )
        config["short_name"] = short_name

        logger.debug(
            f"Action Group '{resource_name}' emitted with short_name '{short_name}'"
        )

        return "azurerm_monitor_action_group", safe_name, config
