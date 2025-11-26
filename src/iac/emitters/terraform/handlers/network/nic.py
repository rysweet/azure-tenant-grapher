"""Network Interface handler for Terraform emission.

Handles: Microsoft.Network/networkInterfaces
Emits: azurerm_network_interface
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class NetworkInterfaceHandler(ResourceHandler):
    """Handler for Azure Network Interfaces.

    Also tracks NIC-NSG associations for deferred emission.

    Emits:
        - azurerm_network_interface
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Network/networkInterfaces",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_network_interface",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Azure NIC to Terraform configuration.

        Args:
            resource: Azure resource dictionary from graph
            context: Shared emitter context

        Returns:
            Tuple of (terraform_type, resource_name, config) or None if skipped
        """
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        ip_configurations = properties.get("ipConfigurations", [])
        if not ip_configurations:
            logger.error(
                f"NIC '{resource_name}' has no ip_configurations in properties. "
                "Skipping this NIC as it cannot be deployed without ip_configuration block."
            )
            return None

        # Use first IP configuration
        ip_config = ip_configurations[0]
        ip_props = ip_config.get("properties", {})
        subnet_info = ip_props.get("subnet", {})
        subnet_id = subnet_info.get("id", "")

        # Resolve VNet-scoped subnet reference
        subnet_reference = self._resolve_subnet_reference(
            subnet_id, resource_name, context
        )

        # Bug #29: Skip NIC if subnet doesn't exist in graph
        if subnet_reference is None:
            logger.error(
                f"Skipping NIC '{resource_name}' - subnet missing from graph. "
                "NIC cannot be deployed without valid subnet reference."
            )
            return None

        private_ip = ip_props.get("privateIPAddress", "")
        allocation_method = ip_props.get("privateIPAllocationMethod", "Dynamic")

        ip_config_block = {
            "name": ip_config.get("name", "internal"),
            "subnet_id": subnet_reference,
            "private_ip_address_allocation": allocation_method,
        }

        # Add private IP if static allocation
        if allocation_method == "Static" and private_ip:
            ip_config_block["private_ip_address"] = private_ip

        # Build base config
        config = self.build_base_config(resource)
        config["ip_configuration"] = ip_config_block

        # Track NSG association if present
        # NOTE: network_security_group_id field is deprecated
        # Must use azurerm_network_interface_security_group_association resource
        nsg_info = properties.get("networkSecurityGroup", {})
        if nsg_info and "id" in nsg_info:
            nsg_id = nsg_info["id"]
            nsg_name = self.extract_name_from_id(nsg_id, "networkSecurityGroups")
            if nsg_name != "unknown":
                nsg_safe = self.sanitize_name(nsg_name)
                context.track_nic_nsg_association(
                    safe_name, nsg_safe, resource_name, nsg_name
                )
                logger.debug(
                    f"NIC '{resource_name}' will get NSG association: {nsg_name}"
                )

        # Validate reference (warn if placeholder)
        if "unknown" in subnet_reference:
            logger.warning(
                f"NIC '{resource_name}' has invalid subnet reference. "
                f"Generated Terraform may be invalid."
            )

        logger.debug(f"NIC '{resource_name}' emitted")

        return "azurerm_network_interface", safe_name, config

    def _resolve_subnet_reference(
        self,
        subnet_id: str,
        resource_name: str,
        context: EmitterContext,
    ) -> Optional[str]:
        """Resolve a subnet ID to a Terraform reference.

        Args:
            subnet_id: Azure subnet ID
            resource_name: Parent resource name for logging
            context: Emitter context with VNet mappings

        Returns:
            Terraform reference string or None if subnet not found
        """
        if not subnet_id:
            return None

        # Extract VNet and subnet names
        vnet_name = self.extract_name_from_id(subnet_id, "virtualNetworks")
        subnet_name = self.extract_name_from_id(subnet_id, "subnets")

        if vnet_name == "unknown" or subnet_name == "unknown":
            logger.warning(
                f"Resource '{resource_name}' has invalid subnet ID: {subnet_id}"
            )
            return None

        vnet_safe = self.sanitize_name(vnet_name)
        subnet_safe = self.sanitize_name(subnet_name)
        scoped_name = f"{vnet_safe}_{subnet_safe}"

        # Check if subnet exists in context
        if scoped_name in context.available_subnets:
            return f"${{azurerm_subnet.{scoped_name}.id}}"

        # Also try VNet ID mapping (Bug #31)
        if "/virtualNetworks/" in subnet_id and "/subnets/" in subnet_id:
            vnet_id = subnet_id.split("/subnets/")[0]
            if vnet_id in context.vnet_id_to_terraform_name:
                vnet_tf_name = context.vnet_id_to_terraform_name[vnet_id]
                mapped_scoped_name = f"{vnet_tf_name}_{subnet_safe}"
                if mapped_scoped_name in context.available_subnets:
                    return f"${{azurerm_subnet.{mapped_scoped_name}.id}}"

        # Subnet not found - return None to trigger skip
        logger.warning(
            f"Resource '{resource_name}' references subnet not in graph: "
            f"VNet={vnet_name}, Subnet={subnet_name}"
        )
        return None
