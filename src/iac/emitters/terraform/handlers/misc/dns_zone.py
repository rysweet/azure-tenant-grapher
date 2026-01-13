"""DNS Zone handlers for Terraform emission.

Handles: Microsoft.Network/dnsZones, Microsoft.Network/privateDnsZones
Emits: azurerm_dns_zone, azurerm_private_dns_zone
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class DNSZoneHandler(ResourceHandler):
    """Handler for Azure DNS Zones.

    Emits:
        - azurerm_dns_zone
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Network/dnsZones",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_dns_zone",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert DNS Zone to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)

        # DNS zones are global resources - no location field
        config = self.build_base_config(resource, include_location=False)

        logger.debug(f"DNS Zone '{resource_name}' emitted")

        return "azurerm_dns_zone", safe_name, config


@handler
class PrivateDNSZoneHandler(ResourceHandler):
    """Handler for Azure Private DNS Zones.

    Emits:
        - azurerm_private_dns_zone
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Network/privateDnsZones",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_private_dns_zone",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Private DNS Zone to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)

        # Private DNS zones are global resources - no location field
        config = self.build_base_config(resource, include_location=False)

        logger.debug(f"Private DNS Zone '{resource_name}' emitted")

        return "azurerm_private_dns_zone", safe_name, config
