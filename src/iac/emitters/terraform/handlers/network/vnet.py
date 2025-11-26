"""Virtual Network handler for Terraform emission.

Handles: Microsoft.Network/virtualNetworks
Emits: azurerm_virtual_network, azurerm_subnet (inline)
"""

import json
import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class VirtualNetworkHandler(ResourceHandler):
    """Handler for Azure Virtual Networks.

    Also emits inline subnets and tracks NSG associations for
    deferred emission.

    Emits:
        - azurerm_virtual_network
        - azurerm_subnet (inline subnets from VNet properties)
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Network/virtualNetworks",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_virtual_network",
        "azurerm_subnet",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Azure VNet to Terraform configuration.

        Args:
            resource: Azure resource dictionary from graph
            context: Shared emitter context

        Returns:
            Tuple of (terraform_type, resource_name, config) or None if skipped
        """
        resource_name = resource.get("name", "unknown")
        properties = self.parse_properties(resource)
        safe_name = self.sanitize_name(resource_name)
        location = self.get_location(resource)

        # Skip VNets with missing resource group
        rg_name = self.get_resource_group(resource)
        if not rg_name:
            logger.warning(
                f"Skipping VNet '{resource_name}': No resource group found. "
                f"VNets require a valid resource group for deployment."
            )
            return None

        # Extract address space
        address_prefixes = self._get_address_space(resource, properties, resource_name)

        # Normalize all VNet CIDRs
        normalized_prefixes = []
        for cidr in address_prefixes:
            normalized = self.normalize_cidr_block(cidr, resource_name)
            if normalized:
                normalized_prefixes.append(normalized)
            else:
                # Keep original if normalization fails
                normalized_prefixes.append(cidr)

        # Build VNet config
        config = {
            "name": resource_name,
            "location": location,
            "resource_group_name": rg_name,
            "address_space": normalized_prefixes,
        }

        # Add tags
        tags = resource.get("tags")
        if tags:
            parsed_tags = self.parse_tags(tags, resource_name)
            if parsed_tags:
                config["tags"] = parsed_tags

        # Bug #31 Step 2: Populate VNet ID -> Terraform name mapping
        vnet_id = resource.get("id", "")
        vnet_original_id = resource.get("original_id", "")

        if vnet_id and safe_name:
            context.vnet_id_to_terraform_name[vnet_id] = safe_name
            logger.debug(f"Bug #31: Mapped VNet ID {vnet_id} -> {safe_name}")

        if vnet_original_id and vnet_original_id != vnet_id and safe_name:
            context.vnet_id_to_terraform_name[vnet_original_id] = safe_name
            logger.debug(
                f"Bug #31: Mapped VNet original_id {vnet_original_id} -> {safe_name}"
            )

        # Extract and emit inline subnets
        self._emit_inline_subnets(resource, properties, safe_name, rg_name, context)

        logger.debug(
            f"VNet '{resource_name}' emitted with {len(normalized_prefixes)} address spaces"
        )

        return "azurerm_virtual_network", safe_name, config

    def _get_address_space(
        self,
        resource: Dict[str, Any],
        properties: Dict[str, Any],
        resource_name: str,
    ) -> list:
        """Extract address space from VNet.

        Args:
            resource: Azure resource dict
            properties: Parsed properties dict
            resource_name: Resource name for logging

        Returns:
            List of address prefixes
        """
        # Try properties.addressSpace.addressPrefixes
        address_space_obj = properties.get("addressSpace", {})
        prefixes = address_space_obj.get("addressPrefixes", [])

        # Fallback 1: Try top-level addressSpace property
        if not prefixes and resource.get("addressSpace"):
            try:
                addr_space = resource.get("addressSpace")
                if isinstance(addr_space, str):
                    prefixes = json.loads(addr_space)
                    logger.debug(
                        f"VNet '{resource_name}' using top-level addressSpace: {prefixes}"
                    )
                elif isinstance(addr_space, list):
                    prefixes = addr_space
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(
                    f"Failed to parse top-level addressSpace for VNet '{resource_name}': {e}"
                )

        # Fallback 2: Use default
        if not prefixes:
            prefixes = ["10.0.0.0/16"]
            logger.warning(
                f"VNet '{resource_name}' has no addressSpace, using fallback: {prefixes}"
            )

        return prefixes

    def _emit_inline_subnets(
        self,
        resource: Dict[str, Any],
        properties: Dict[str, Any],
        vnet_safe_name: str,
        rg_name: str,
        context: EmitterContext,
    ) -> None:
        """Emit subnets defined inline in VNet properties.

        Args:
            resource: Azure resource dict
            properties: Parsed properties dict
            vnet_safe_name: Sanitized VNet terraform name
            rg_name: Resource group name
            context: Emitter context
        """
        resource_name = resource.get("name", "unknown")
        subnets = properties.get("subnets", [])

        for subnet in subnets:
            subnet_name = subnet.get("name")
            if not subnet_name:
                continue

            subnet_props = subnet.get("properties", {})

            # Handle both addressPrefix (singular) and addressPrefixes (array)
            address_prefixes = (
                [subnet_props.get("addressPrefix")]
                if subnet_props.get("addressPrefix")
                else subnet_props.get("addressPrefixes", [])
            )

            if not address_prefixes or not address_prefixes[0]:
                logger.warning(
                    f"Subnet '{subnet_name}' in vnet '{resource_name}' has no addressPrefix, skipping"
                )
                continue

            address_prefix = address_prefixes[0]

            # Normalize subnet CIDR
            normalized_cidr = self.normalize_cidr_block(
                address_prefix, f"{resource_name}/{subnet_name}"
            )
            if not normalized_cidr:
                logger.warning(
                    f"Subnet '{subnet_name}' has invalid CIDR '{address_prefix}', skipping"
                )
                continue

            # Build VNet-scoped subnet resource name
            subnet_safe_name = self.sanitize_name(subnet_name)
            scoped_subnet_name = f"{vnet_safe_name}_{subnet_safe_name}"

            # Build subnet resource config
            subnet_config = {
                "name": subnet_name,
                "resource_group_name": rg_name,
                "virtual_network_name": f"${{azurerm_virtual_network.{vnet_safe_name}.name}}",
                "address_prefixes": [normalized_cidr],
            }

            # Check for NSG association
            nsg_info = subnet_props.get("networkSecurityGroup", {})
            if nsg_info and "id" in nsg_info:
                nsg_name = self.extract_name_from_id(
                    nsg_info["id"], "networkSecurityGroups"
                )
                if nsg_name != "unknown":
                    nsg_safe = self.sanitize_name(nsg_name)
                    context.track_nsg_association(
                        scoped_subnet_name, nsg_safe, subnet_name, nsg_name
                    )
                    logger.debug(
                        f"Tracked NSG association for inline subnet: {subnet_name} -> {nsg_name}"
                    )

            # Add to terraform config
            context.add_helper_resource(
                "azurerm_subnet", scoped_subnet_name, subnet_config
            )
            context.available_subnets.add(scoped_subnet_name)
            context.add_resource("azurerm_subnet", scoped_subnet_name)

            logger.debug(
                f"Emitted inline subnet: {scoped_subnet_name} "
                f"(VNet: {resource_name}, Subnet: {subnet_name})"
            )
