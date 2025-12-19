"""Route Table handler for Terraform emission.

Handles: Microsoft.Network/routeTables
Emits: azurerm_route_table
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class RouteTableHandler(ResourceHandler):
    """Handler for Azure Route Tables.

    Emits:
        - azurerm_route_table
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Network/routeTables",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_route_table",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Azure Route Table to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        config = self.build_base_config(resource)

        # BGP route propagation
        # Updated for azurerm provider v4+: renamed from disable_bgp_route_propagation to bgp_route_propagation_enabled
        disable_bgp = properties.get("disableBgpRoutePropagation")
        if disable_bgp is not None:
            # Invert the logic: disableBgpRoutePropagation=true means bgp_route_propagation_enabled=false
            config["bgp_route_propagation_enabled"] = not disable_bgp

        logger.debug(f"Route Table '{resource_name}' emitted")

        return "azurerm_route_table", safe_name, config
