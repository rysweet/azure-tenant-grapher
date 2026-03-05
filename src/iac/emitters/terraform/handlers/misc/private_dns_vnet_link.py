"""Private DNS Zone Virtual Network Link handler for Terraform emission.

Handles: Microsoft.Network/privateDnsZones/virtualNetworkLinks
Emits: azurerm_private_dns_zone_virtual_network_link

This handler supports standalone VNet Links that are selected directly
(e.g., as orphaned resources) without their parent Private DNS Zone.
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class PrivateDNSVNetLinkHandler(ResourceHandler):
    """Handler for standalone Private DNS Zone Virtual Network Links.

    This handler complements PrivateDNSZoneHandler by handling VNet Links
    that are selected directly as resources, rather than being discovered
    as children of a Private DNS Zone.

    Emits:
        - azurerm_private_dns_zone_virtual_network_link
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Network/privateDnsZones/virtualNetworkLinks",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_private_dns_zone_virtual_network_link",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert standalone Private DNS Zone VNet Link to Terraform configuration.

        Args:
            resource: VNet Link resource dictionary from Neo4j
            context: Emitter context

        Returns:
            Tuple of (terraform_type, resource_name, config) or None if validation fails
        """
        resource_id = resource.get("id", "")
        link_name = resource.get("name", "unknown")
        link_props = resource.get("properties", {})

        # Extract zone name from resource ID
        # Format: .../privateDnsZones/{zone_name}/virtualNetworkLinks/{link_name}
        zone_name = self._extract_zone_name_from_id(resource_id)
        if not zone_name:
            logger.warning(
                f"Cannot extract DNS zone name from VNet Link ID '{resource_id}' - skipping"
            )
            return None

        # Get VNet ID from properties
        # virtualNetwork can be either a dict with "id" key or a string ID directly
        vnet_ref = link_props.get("virtualNetwork")
        if not vnet_ref:
            logger.warning(
                f"VNet Link '{link_name}' has no VNet reference in properties - skipping"
            )
            return None

        # Handle both dict format {"id": "..."} and direct string format
        if isinstance(vnet_ref, dict):
            vnet_id = vnet_ref.get("id")
        elif isinstance(vnet_ref, str):
            vnet_id = vnet_ref
        else:
            logger.warning(
                f"VNet Link '{link_name}' has unexpected virtualNetwork format: {type(vnet_ref)} - skipping"
            )
            return None

        if not vnet_id:
            logger.warning(
                f"VNet Link '{link_name}' has no VNet ID - skipping"
            )
            return None

        # Build terraform config
        safe_name = self.sanitize_name(link_name)

        # Check if we have the VNet in our terraform config
        vnet_tf_name = context.vnet_id_to_terraform_name.get(vnet_id.lower())

        if not vnet_tf_name:
            # VNet not in our config - this is expected for orphaned links
            # We'll create a data source reference instead
            logger.info(
                f"VNet Link '{link_name}' references external VNet '{vnet_id}' "
                f"- using data source"
            )

            # Create a data source for the referenced VNet
            vnet_data_name = self.sanitize_name(f"vnet_{vnet_id.split('/')[-1]}")
            self._add_vnet_data_source(context, vnet_id, vnet_data_name)

            vnet_id_reference = f"${{data.azurerm_virtual_network.{vnet_data_name}.id}}"
        else:
            # VNet is in our config - reference it directly
            vnet_id_reference = f"${{azurerm_virtual_network.{vnet_tf_name}.id}}"

        # Check if the parent DNS zone exists in our config
        zone_tf_name = self._find_zone_terraform_name(context, zone_name)

        if not zone_tf_name:
            # DNS zone not in our config - create data source
            logger.info(
                f"VNet Link '{link_name}' references external DNS zone '{zone_name}' "
                f"- using data source"
            )
            zone_data_name = self.sanitize_name(f"pdnsz_{zone_name}")
            self._add_dns_zone_data_source(
                context, zone_name, resource.get("resource_group"), zone_data_name
            )
            zone_name_reference = f"${{data.azurerm_private_dns_zone.{zone_data_name}.name}}"
        else:
            # DNS zone is in our config - reference it directly
            zone_name_reference = f"${{azurerm_private_dns_zone.{zone_tf_name}.name}}"

        # Build link config
        config = {
            "name": link_name,
            "private_dns_zone_name": zone_name_reference,
            "resource_group_name": resource.get("resource_group"),
            "virtual_network_id": vnet_id_reference,
        }

        # Optional properties
        if link_props.get("registrationEnabled"):
            config["registration_enabled"] = True

        logger.debug(
            f"Emitted standalone Private DNS VNet Link: {zone_name} -> {link_name}"
        )

        return "azurerm_private_dns_zone_virtual_network_link", safe_name, config

    def _extract_zone_name_from_id(self, resource_id: str) -> Optional[str]:
        """Extract DNS zone name from VNet Link resource ID.

        Args:
            resource_id: Full Azure resource ID

        Returns:
            DNS zone name or None if extraction fails
        """
        try:
            # Format: .../privateDnsZones/{zone_name}/virtualNetworkLinks/{link_name}
            parts = resource_id.split("/privateDnsZones/")
            if len(parts) < 2:
                return None

            zone_and_rest = parts[1]
            zone_name = zone_and_rest.split("/virtualNetworkLinks/")[0]
            return zone_name
        except Exception as e:
            logger.warning(f"Failed to extract zone name from ID '{resource_id}': {e}")
            return None

    def _find_zone_terraform_name(
        self, context: EmitterContext, zone_name: str
    ) -> Optional[str]:
        """Find Terraform name for a Private DNS Zone if it exists in config.

        Args:
            context: Emitter context
            zone_name: Azure DNS zone name

        Returns:
            Terraform resource name or None if not found
        """
        zones = context.terraform_config.get("resource", {}).get(
            "azurerm_private_dns_zone", {}
        )

        for tf_name, config in zones.items():
            if config.get("name") == zone_name:
                return tf_name

        return None

    def _add_vnet_data_source(
        self, context: EmitterContext, vnet_id: str, data_name: str
    ) -> None:
        """Add a data source for an external Virtual Network.

        Args:
            context: Emitter context
            vnet_id: Full Azure VNet resource ID
            data_name: Terraform data source name
        """
        # Extract VNet name and resource group from ID
        # Format: /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Network/virtualNetworks/{name}
        parts = vnet_id.split("/")
        if len(parts) < 9:
            logger.warning(f"Cannot parse VNet ID '{vnet_id}' - invalid format")
            return

        try:
            rg_index = parts.index("resourceGroups")
            vnet_name = parts[-1]
            resource_group = parts[rg_index + 1]

            context.add_data_source(
                "azurerm_virtual_network",
                data_name,
                {
                    "name": vnet_name,
                    "resource_group_name": resource_group,
                },
            )
            logger.debug(f"Added VNet data source: {data_name} -> {vnet_name}")
        except (ValueError, IndexError) as e:
            logger.warning(f"Failed to parse VNet ID '{vnet_id}': {e}")

    def _add_dns_zone_data_source(
        self,
        context: EmitterContext,
        zone_name: str,
        resource_group: Optional[str],
        data_name: str,
    ) -> None:
        """Add a data source for an external Private DNS Zone.

        Args:
            context: Emitter context
            zone_name: DNS zone name
            resource_group: Resource group name
            data_name: Terraform data source name
        """
        if not resource_group:
            logger.warning(
                f"Cannot create data source for DNS zone '{zone_name}' - "
                f"no resource group"
            )
            return

        context.add_data_source(
            "azurerm_private_dns_zone",
            data_name,
            {
                "name": zone_name,
                "resource_group_name": resource_group,
            },
        )
        logger.debug(f"Added Private DNS Zone data source: {data_name} -> {zone_name}")
