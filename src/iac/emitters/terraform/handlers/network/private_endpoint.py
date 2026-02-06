"""Private Endpoint handler for Terraform emission.

Handles: Microsoft.Network/privateEndpoints
Emits: azurerm_private_endpoint
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class PrivateEndpointHandler(ResourceHandler):
    """Handler for Azure Private Endpoints.

    Emits:
        - azurerm_private_endpoint
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Network/privateEndpoints",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_private_endpoint",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Azure Private Endpoint to Terraform configuration.

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
        config = self.build_base_config(resource, context=context)

        # Extract subnet reference
        subnet_info = properties.get("subnet", {})
        subnet_id = subnet_info.get("id", "")

        # Extract VNet and subnet names for scoped reference
        vnet_name = self.extract_name_from_id(subnet_id, "virtualNetworks")
        subnet_name = self.extract_name_from_id(subnet_id, "subnets")

        # Build VNet-scoped subnet reference
        subnet_reference = "${azurerm_subnet.unknown_subnet.id}"
        if vnet_name != "unknown" and subnet_name != "unknown":
            vnet_name_safe = self.sanitize_name(vnet_name)
            subnet_name_safe = self.sanitize_name(subnet_name)
            scoped_subnet_name = f"{vnet_name_safe}_{subnet_name_safe}"

            # Validate subnet exists
            if not self.validate_resource_reference(
                "azurerm_subnet", scoped_subnet_name, context
            ):
                logger.warning(
                    f"Private Endpoint '{resource_name}' references subnet that doesn't exist:\n"
                    f"  Subnet Terraform name: {scoped_subnet_name}\n"
                    f"  Subnet Azure name: {subnet_name}\n"
                    f"  VNet Azure name: {vnet_name}\n"
                    f"  Azure ID: {subnet_id}"
                )
                context.track_missing_reference(
                    resource_name,
                    "subnet",
                    subnet_name,
                    subnet_id,
                )

            subnet_reference = f"${{azurerm_subnet.{scoped_subnet_name}.id}}"
            logger.debug(
                f"Resolved subnet for Private Endpoint '{resource_name}': "
                f"VNet='{vnet_name}', Subnet='{subnet_name}' -> {scoped_subnet_name}"
            )
        else:
            logger.warning(
                f"Private Endpoint '{resource_name}' has invalid subnet reference: {subnet_id}"
            )

        config["subnet_id"] = subnet_reference

        # Extract private link service connections
        private_link_connections = properties.get("privateLinkServiceConnections", [])
        if not private_link_connections:
            logger.warning(
                f"Private Endpoint '{resource_name}' has no private link service connections. "
                "Generated Terraform may be invalid."
            )
            return None

        connection_configs = []
        for conn in private_link_connections:
            conn_props = conn.get("properties", {})
            conn_config = {
                "name": conn.get("name", f"{resource_name}-connection"),
                "is_manual_connection": False,
            }

            # Add target resource ID
            target_resource_id = conn_props.get("privateLinkServiceId")
            if target_resource_id:
                conn_config["private_connection_resource_id"] = target_resource_id

            # Add subresource names (group IDs)
            group_ids = conn_props.get("groupIds", [])
            if group_ids:
                conn_config["subresource_names"] = group_ids

            connection_configs.append(conn_config)

        if connection_configs:
            config["private_service_connection"] = connection_configs

        logger.debug(f"Private Endpoint '{resource_name}' emitted")

        return "azurerm_private_endpoint", safe_name, config
