"""Network Security Group handler for Terraform emission.

Handles: Microsoft.Network/networkSecurityGroups
Emits: azurerm_network_security_group
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class NetworkSecurityGroupHandler(ResourceHandler):
    """Handler for Azure Network Security Groups.

    Emits:
        - azurerm_network_security_group
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Network/networkSecurityGroups",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_network_security_group",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Azure NSG to Terraform configuration.

        Args:
            resource: Azure resource dictionary from graph
            context: Shared emitter context

        Returns:
            Tuple of (terraform_type, resource_name, config) or None if skipped
        """
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)

        # Build base configuration - NSGs only need name, location, resource_group_name
        config = self.build_base_config(resource)

        logger.debug(f"NSG '{resource_name}' emitted")

        return "azurerm_network_security_group", safe_name, config
