"""Standalone Subnet handler for Terraform emission.

Handles: Microsoft.Network/subnets (standalone)
Emits: azurerm_subnet
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class SubnetHandler(ResourceHandler):
    """Handler for standalone Azure Subnets.

    Note: Most subnets are emitted inline by VirtualNetworkHandler.
    This handler handles standalone subnet resources that appear
    separately in the graph.

    Emits:
        - azurerm_subnet
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Network/subnets",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_subnet",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert standalone Azure Subnet to Terraform configuration.

        Args:
            resource: Azure resource dictionary from graph
            context: Shared emitter context

        Returns:
            Tuple of (terraform_type, resource_name, config) or None if skipped
        """
        resource_name = resource.get("name", "unknown")
        properties = self.parse_properties(resource)

        # Bug #31 Step 3: Use VNet mapping to find terraform name
        subnet_id = resource.get("original_id") or resource.get("id", "")
        vnet_name_safe = None
        vnet_name = "unknown"

        # Try to extract parent VNet ID and look up in mapping
        if "/virtualNetworks/" in subnet_id and "/subnets/" in subnet_id:
            # Extract VNet ID portion: everything up to /subnets/
            vnet_id = subnet_id.split("/subnets/")[0]

            # Look up in mapping (Bug #31 fix for abstracted IDs)
            if vnet_id in context.vnet_id_to_terraform_name:
                vnet_name_safe = context.vnet_id_to_terraform_name[vnet_id]
                vnet_name = self.extract_name_from_id(vnet_id, "virtualNetworks")
                logger.debug(
                    f"Bug #31: Found VNet terraform name via mapping: {vnet_id} -> {vnet_name_safe}"
                )

        # Fallback: Extract VNet name directly from ID
        if not vnet_name_safe:
            vnet_name = self.extract_name_from_id(subnet_id, "virtualNetworks")
            if vnet_name != "unknown":
                vnet_name_safe = self.sanitize_name(vnet_name)

        # Build VNet-scoped resource name
        if vnet_name_safe and "/subnets/" in subnet_id:
            subnet_name_safe = self.sanitize_name(resource_name)
            safe_name = f"{vnet_name_safe}_{subnet_name_safe}"

            config = {
                "name": resource_name,
                "resource_group_name": self.get_resource_group(resource),
                "virtual_network_name": f"${{azurerm_virtual_network.{vnet_name_safe}.name}}",
            }

            logger.debug(
                f"Generated standalone subnet: {safe_name} "
                f"(VNet: {vnet_name}, Subnet: {resource_name})"
            )
        else:
            logger.warning(
                f"Standalone subnet '{resource_name}' has no parent VNet in ID: {subnet_id}. "
                f"Skipping subnet as it cannot be deployed without a VNet."
            )
            return None

        # Handle address prefixes with fallback
        address_prefixes = (
            [properties.get("addressPrefix")]
            if properties.get("addressPrefix")
            else properties.get("addressPrefixes", [])
        )

        if not address_prefixes or not address_prefixes[0]:
            logger.warning(f"Subnet '{resource_name}' has no address prefixes")
            address_prefixes = ["10.0.0.0/24"]

        # Normalize CIDRs
        normalized_prefixes = []
        for cidr in address_prefixes:
            if cidr:
                normalized = self.normalize_cidr_block(cidr, resource_name)
                if normalized:
                    normalized_prefixes.append(normalized)
                else:
                    normalized_prefixes.append(cidr)

        config["address_prefixes"] = (
            normalized_prefixes if normalized_prefixes else address_prefixes
        )

        # Check for NSG association
        nsg_info = properties.get("networkSecurityGroup", {})
        if nsg_info and "id" in nsg_info:
            nsg_name = self.extract_name_from_id(
                nsg_info["id"], "networkSecurityGroups"
            )
            if nsg_name != "unknown":
                nsg_safe = self.sanitize_name(nsg_name)
                context.track_nsg_association(
                    safe_name, nsg_safe, resource_name, nsg_name
                )
                logger.debug(
                    f"Tracked NSG association for standalone subnet: {resource_name} -> {nsg_name}"
                )

        # Optional: Service Endpoints
        service_endpoints = properties.get("serviceEndpoints", [])
        if service_endpoints:
            config["service_endpoints"] = [
                ep["service"] for ep in service_endpoints if "service" in ep
            ]

        # Track in context
        context.available_subnets.add(safe_name)

        return "azurerm_subnet", safe_name, config
