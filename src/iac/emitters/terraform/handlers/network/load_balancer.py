"""Load Balancer handler for Terraform emission.

Handles: Microsoft.Network/loadBalancers
Emits: azurerm_lb
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class LoadBalancerHandler(ResourceHandler):
    """Handler for Azure Load Balancers.

    Emits:
        - azurerm_lb

    Note: This is a basic implementation that emits minimal Load Balancer
    configuration. Enhanced implementation with frontend IPs, backend pools,
    probes, and rules can be added when needed.
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Network/loadBalancers",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_lb",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Azure Load Balancer to Terraform configuration.

        Args:
            resource: Azure resource dictionary from graph
            context: Shared emitter context

        Returns:
            Tuple of (terraform_type, resource_name, config) or None if skipped
        """
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        # Build base config (name, location, resource_group_name, tags)
        config = self.build_base_config(resource)

        # Extract SKU (Standard, Basic, Gateway)
        sku = properties.get("sku", {})
        if isinstance(sku, dict):
            sku_name = sku.get("name", "Standard")
        else:
            sku_name = "Standard"
        config["sku"] = sku_name

        # TODO: Future enhancement - Extract and emit:
        # - frontend_ip_configuration blocks
        # - backend_address_pool blocks (separate resource)
        # - probe blocks (separate resource)
        # - lb_rule blocks (separate resource)
        # For now, just emit the basic LB resource

        logger.debug(f"Load Balancer '{resource_name}' emitted with SKU: {sku_name}")

        return "azurerm_lb", safe_name, config
