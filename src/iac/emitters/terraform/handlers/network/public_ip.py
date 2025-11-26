"""Public IP Address handler for Terraform emission.

Handles: Microsoft.Network/publicIPAddresses
Emits: azurerm_public_ip
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class PublicIPHandler(ResourceHandler):
    """Handler for Azure Public IP Addresses.

    Emits:
        - azurerm_public_ip
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Network/publicIPAddresses",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_public_ip",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Azure Public IP to Terraform configuration.

        Args:
            resource: Azure resource dictionary from graph
            context: Shared emitter context

        Returns:
            Tuple of (terraform_type, resource_name, config) or None if skipped
        """
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)

        # Build base configuration
        config = self.build_base_config(resource)

        # Public IP specific properties
        properties = self.parse_properties(resource)

        # Allocation method (required)
        allocation_method = resource.get("allocation_method") or properties.get(
            "publicIPAllocationMethod", "Static"
        )
        config["allocation_method"] = allocation_method

        # SKU
        sku = properties.get("sku", {})
        if sku and "name" in sku:
            config["sku"] = sku["name"]

        # IP version
        ip_version = properties.get("publicIPAddressVersion")
        if ip_version:
            config["ip_version"] = ip_version

        # Domain name label
        dns_settings = properties.get("dnsSettings", {})
        if dns_settings and "domainNameLabel" in dns_settings:
            config["domain_name_label"] = dns_settings["domainNameLabel"]

        logger.debug(
            f"Public IP '{resource_name}' emitted with allocation_method={allocation_method}"
        )

        return "azurerm_public_ip", safe_name, config
