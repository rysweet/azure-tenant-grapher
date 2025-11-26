"""Bastion Host handler for Terraform emission.

Handles: Microsoft.Network/bastionHosts
Emits: azurerm_bastion_host
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class BastionHostHandler(ResourceHandler):
    """Handler for Azure Bastion Hosts.

    Emits:
        - azurerm_bastion_host
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Network/bastionHosts",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_bastion_host",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Azure Bastion Host to Terraform configuration.

        Args:
            resource: Azure resource dictionary from graph
            context: Shared emitter context

        Returns:
            Tuple of (terraform_type, resource_name, config) or None if skipped
        """
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        # Build base configuration
        config = self.build_base_config(resource)

        ip_configurations = properties.get("ipConfigurations", [])
        if not ip_configurations:
            logger.warning(
                f"Bastion Host '{resource_name}' has no IP configurations in properties. "
                "Generated Terraform may be invalid."
            )
            return None

        # Use first IP configuration
        ip_config = ip_configurations[0]
        ip_config_name = ip_config.get("name", "IpConf")
        ip_props = ip_config.get("properties", {})

        # Extract subnet reference
        subnet_info = ip_props.get("subnet", {})
        subnet_id = subnet_info.get("id", "")
        subnet_reference = self._resolve_subnet_reference(
            subnet_id, resource_name, context
        )

        # Extract public IP reference (REQUIRED for Bastion Host)
        public_ip_info = ip_props.get("publicIPAddress", {})
        public_ip_id = public_ip_info.get("id", "")
        public_ip_name = self.extract_name_from_id(public_ip_id, "publicIPAddresses")

        if public_ip_name == "unknown":
            logger.error(
                f"Bastion Host '{resource_name}' has no publicIPAddress. "
                f"Bastion Hosts require a public IP. Skipping."
            )
            return None

        public_ip_safe = self.sanitize_name(public_ip_name)

        # Build IP configuration block
        ip_config_block = {
            "name": ip_config_name,
            "subnet_id": subnet_reference or "${azurerm_subnet.unknown_subnet.id}",
            "public_ip_address_id": f"${{azurerm_public_ip.{public_ip_safe}.id}}",
        }

        config["ip_configuration"] = ip_config_block

        # Validate public IP exists
        if not self.validate_resource_reference(
            "azurerm_public_ip", public_ip_safe, context
        ):
            logger.warning(
                f"Bastion Host '{resource_name}' references public IP '{public_ip_name}' "
                f"that may not exist in the graph. Azure ID: {public_ip_id}"
            )
            context.track_missing_reference(
                resource_name,
                "public_ip",
                public_ip_name,
                public_ip_id,
            )

        # Validate subnet reference
        if subnet_reference and "unknown" in subnet_reference:
            logger.warning(
                f"Bastion Host '{resource_name}' has invalid subnet reference. "
                f"Generated Terraform may be invalid."
            )

        # Add SKU if present
        sku = properties.get("sku", {})
        if sku and "name" in sku:
            config["sku"] = sku["name"]

        logger.debug(f"Bastion Host '{resource_name}' emitted")

        return "azurerm_bastion_host", safe_name, config

    def _resolve_subnet_reference(
        self,
        subnet_id: str,
        resource_name: str,
        context: EmitterContext,
    ) -> Optional[str]:
        """Resolve a subnet ID to a Terraform reference."""
        if not subnet_id:
            return None

        vnet_name = self.extract_name_from_id(subnet_id, "virtualNetworks")
        subnet_name = self.extract_name_from_id(subnet_id, "subnets")

        if vnet_name == "unknown" or subnet_name == "unknown":
            return None

        vnet_safe = self.sanitize_name(vnet_name)
        subnet_safe = self.sanitize_name(subnet_name)
        scoped_name = f"{vnet_safe}_{subnet_safe}"

        return f"${{azurerm_subnet.{scoped_name}.id}}"
