"""NAT Gateway handler for Terraform emission.

Handles: Microsoft.Network/natGateways
Emits: azurerm_nat_gateway
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class NATGatewayHandler(ResourceHandler):
    """Handler for Azure NAT Gateways.

    Emits:
        - azurerm_nat_gateway
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Network/natGateways",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_nat_gateway",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Azure NAT Gateway to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        config = self.build_base_config(resource)

        # SKU
        sku = properties.get("sku", {})
        if sku and "name" in sku:
            config["sku_name"] = sku["name"]

        # Idle timeout
        idle_timeout = properties.get("idleTimeoutInMinutes")
        if idle_timeout:
            config["idle_timeout_in_minutes"] = idle_timeout

        # Zones
        zones = resource.get("zones") or properties.get("zones")
        if zones:
            config["zones"] = zones

        logger.debug(f"NAT Gateway '{resource_name}' emitted")

        return "azurerm_nat_gateway", safe_name, config
