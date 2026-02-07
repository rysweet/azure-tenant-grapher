"""DNS Zone handlers for Terraform emission.

Handles: Microsoft.Network/dnsZones, Microsoft.Network/privateDnsZones
Emits: azurerm_dns_zone, azurerm_private_dns_zone
"""

import logging
from typing import Any, ClassVar, Dict, List, Optional, Set, Tuple

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
        - azurerm_private_dns_zone_virtual_network_link (via post_emit)
        - azurerm_private_dns_a_record (via post_emit)
        - azurerm_private_dns_aaaa_record (via post_emit)
        - azurerm_private_dns_cname_record (via post_emit)
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Network/privateDnsZones",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_private_dns_zone",
        "azurerm_private_dns_zone_virtual_network_link",
        "azurerm_private_dns_a_record",
        "azurerm_private_dns_aaaa_record",
        "azurerm_private_dns_cname_record",
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

    def post_emit(self, context: EmitterContext) -> None:
        """Emit VNet Links and DNS Record Sets for all Private DNS Zones.

        This method:
        1. Queries Neo4j for all Private DNS Zones
        2. For each zone, finds VNet Links (child resources)
        3. For each zone, finds DNS Record Sets (A, AAAA, CNAME records)
        4. Emits appropriate Terraform resources for each

        Args:
            context: Emitter context with graph access
        """
        if not context.graph:
            logger.warning("No graph available - skipping Private DNS Zone child resources")
            return

        # Get all emitted Private DNS Zones
        emitted_zones = context.terraform_config.get("resource", {}).get(
            "azurerm_private_dns_zone", {}
        )

        if not emitted_zones:
            logger.debug("No Private DNS Zones emitted - skipping child resources")
            return

        vnet_link_count = 0
        record_count = 0

        for zone_tf_name, zone_config in emitted_zones.items():
            zone_name = zone_config.get("name")
            if not zone_name:
                logger.warning(f"Private DNS Zone '{zone_tf_name}' has no name - skipping")
                continue

            # Query for VNet Links
            vnet_links = self._query_vnet_links(context, zone_name)
            for link in vnet_links:
                if self._emit_vnet_link(context, zone_tf_name, zone_name, link):
                    vnet_link_count += 1

            # Query for DNS Record Sets
            record_sets = self._query_record_sets(context, zone_name)
            for record in record_sets:
                if self._emit_record_set(context, zone_tf_name, zone_name, record):
                    record_count += 1

        logger.info(
            f"Emitted {vnet_link_count} Private DNS VNet Links and "
            f"{record_count} DNS Record Sets"
        )

    def _query_vnet_links(
        self, context: EmitterContext, zone_name: str
    ) -> List[Dict[str, Any]]:
        """Query Neo4j for VNet Links belonging to a Private DNS Zone.

        Args:
            context: Emitter context with graph access
            zone_name: Private DNS Zone name

        Returns:
            List of VNet Link resource dictionaries
        """
        query = """
        MATCH (zone:Resource {name: $zone_name, type: "Microsoft.Network/privateDnsZones"})
        MATCH (link:Resource {type: "Microsoft.Network/privateDnsZones/virtualNetworkLinks"})
        WHERE link.id STARTS WITH zone.id + "/virtualNetworkLinks/"
        RETURN link
        """

        try:
            result = context.graph.run(query, zone_name=zone_name)
            links = [record["link"] for record in result]
            logger.debug(f"Found {len(links)} VNet Links for zone '{zone_name}'")
            return links
        except Exception as e:
            logger.warning(f"Failed to query VNet Links for zone '{zone_name}': {e}")
            return []

    def _query_record_sets(
        self, context: EmitterContext, zone_name: str
    ) -> List[Dict[str, Any]]:
        """Query Neo4j for DNS Record Sets in a Private DNS Zone.

        Queries for A, AAAA, and CNAME record types.

        Args:
            context: Emitter context with graph access
            zone_name: Private DNS Zone name

        Returns:
            List of DNS Record Set resource dictionaries
        """
        query = """
        MATCH (zone:Resource {name: $zone_name, type: "Microsoft.Network/privateDnsZones"})
        MATCH (record:Resource)
        WHERE record.id STARTS WITH zone.id + "/"
        AND record.type IN [
            "Microsoft.Network/privateDnsZones/A",
            "Microsoft.Network/privateDnsZones/AAAA",
            "Microsoft.Network/privateDnsZones/CNAME"
        ]
        RETURN record
        """

        try:
            result = context.graph.run(query, zone_name=zone_name)
            records = [record["record"] for record in result]
            logger.debug(f"Found {len(records)} DNS Record Sets for zone '{zone_name}'")
            return records
        except Exception as e:
            logger.warning(f"Failed to query DNS Record Sets for zone '{zone_name}': {e}")
            return []

    def _emit_vnet_link(
        self,
        context: EmitterContext,
        zone_tf_name: str,
        zone_name: str,
        link: Dict[str, Any],
    ) -> bool:
        """Emit a Private DNS Zone VNet Link resource.

        Args:
            context: Emitter context
            zone_tf_name: Terraform name of the Private DNS Zone
            zone_name: Azure name of the Private DNS Zone
            link: VNet Link resource dictionary from Neo4j

        Returns:
            True if emitted successfully, False otherwise
        """
        link_name = link.get("name", "unknown")
        link_props = link.get("properties", {})

        # Get VNet ID from properties
        vnet_id = link_props.get("virtualNetwork", {}).get("id")
        if not vnet_id:
            logger.warning(
                f"VNet Link '{link_name}' has no VNet ID - skipping"
            )
            return False

        # Get VNet terraform name from context mapping
        vnet_tf_name = context.vnet_id_to_terraform_name.get(vnet_id.lower())
        if not vnet_tf_name:
            logger.warning(
                f"VNet Link '{link_name}' references unknown VNet '{vnet_id}' - skipping"
            )
            context.track_missing_reference(
                resource_name=f"private-dns-vnet-link-{link_name}",
                resource_type="azurerm_virtual_network",
                missing_resource_name=vnet_id,
                missing_resource_id=vnet_id,
            )
            return False

        # Build link resource name
        safe_link_name = self.sanitize_name(link_name)
        link_tf_name = f"{zone_tf_name}_{safe_link_name}"

        # Build link config
        config = {
            "name": link_name,
            "private_dns_zone_name": f"${{azurerm_private_dns_zone.{zone_tf_name}.name}}",
            "resource_group_name": link.get("resource_group"),
            "virtual_network_id": f"${{azurerm_virtual_network.{vnet_tf_name}.id}}",
        }

        # Optional properties
        if link_props.get("registrationEnabled"):
            config["registration_enabled"] = True

        # Add to terraform config
        context.add_helper_resource(
            "azurerm_private_dns_zone_virtual_network_link",
            link_tf_name,
            config,
        )

        logger.debug(f"Emitted Private DNS VNet Link: {zone_name} -> {link_name}")
        return True

    def _emit_record_set(
        self,
        context: EmitterContext,
        zone_tf_name: str,
        zone_name: str,
        record: Dict[str, Any],
    ) -> bool:
        """Emit a DNS Record Set resource.

        Args:
            context: Emitter context
            zone_tf_name: Terraform name of the Private DNS Zone
            zone_name: Azure name of the Private DNS Zone
            record: DNS Record Set resource dictionary from Neo4j

        Returns:
            True if emitted successfully, False otherwise
        """
        record_name = record.get("name", "unknown")
        record_type = record.get("type", "").split("/")[-1]  # A, AAAA, or CNAME
        record_props = record.get("properties", {})

        # Map Azure record type to Terraform resource type
        terraform_type_map = {
            "A": "azurerm_private_dns_a_record",
            "AAAA": "azurerm_private_dns_aaaa_record",
            "CNAME": "azurerm_private_dns_cname_record",
        }

        terraform_type = terraform_type_map.get(record_type)
        if not terraform_type:
            logger.warning(f"Unsupported DNS record type '{record_type}' - skipping")
            return False

        # Build record resource name
        safe_record_name = self.sanitize_name(record_name)
        record_tf_name = f"{zone_tf_name}_{safe_record_name}"

        # Build base config
        config = {
            "name": record_name,
            "zone_name": f"${{azurerm_private_dns_zone.{zone_tf_name}.name}}",
            "resource_group_name": record.get("resource_group"),
            "ttl": record_props.get("ttl", 3600),
        }

        # Add type-specific properties
        if record_type == "A":
            records = record_props.get("aRecords", [])
            config["records"] = [r.get("ipv4Address") for r in records if r.get("ipv4Address")]
        elif record_type == "AAAA":
            records = record_props.get("aaaaRecords", [])
            config["records"] = [r.get("ipv6Address") for r in records if r.get("ipv6Address")]
        elif record_type == "CNAME":
            cname_record = record_props.get("cnameRecord", {})
            cname = cname_record.get("cname")
            if cname:
                config["record"] = cname
            else:
                logger.warning(f"CNAME record '{record_name}' has no target - skipping")
                return False

        # Skip if no records
        if record_type in ["A", "AAAA"] and not config.get("records"):
            logger.warning(f"{record_type} record '{record_name}' has no addresses - skipping")
            return False

        # Add to terraform config
        context.add_helper_resource(terraform_type, record_tf_name, config)

        logger.debug(f"Emitted Private DNS {record_type} Record: {zone_name} -> {record_name}")
        return True
