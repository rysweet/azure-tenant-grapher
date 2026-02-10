"""
Network Interface Relationship Rule

Creates relationships for Network Interfaces:
- (NetworkInterface) -[:CONNECTED_TO]-> (Subnet)
- (NetworkInterface) -[:SECURED_BY]-> (NetworkSecurityGroup)
"""

import json
from typing import Any, Dict, Set

import structlog  # type: ignore[import-untyped]

from .relationship_rule import RelationshipRule

logger = structlog.get_logger(__name__)


class NICRelationshipRule(RelationshipRule):
    """
    Creates relationships for Network Interfaces.

    Relationships created:
    - (NetworkInterface) -[:CONNECTED_TO]-> (Subnet)
    - (NetworkInterface) -[:SECURED_BY]-> (NetworkSecurityGroup) if NSG attached
    """

    def applies(self, resource: Dict[str, Any]) -> bool:
        """Apply to network interfaces only."""
        rtype = resource.get("type", "")
        return rtype == "Microsoft.Network/networkInterfaces"

    def emit(self, resource: Dict[str, Any], db_ops: Any) -> None:
        """Extract subnet and NSG relationships from NIC."""
        rid = resource.get("id")

        # Parse properties JSON
        props_dict = {}
        if "properties" in resource:
            props_str = resource["properties"]
            if isinstance(props_str, str):
                try:
                    props_dict = json.loads(props_str)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse properties for NIC {rid}: {e}")
                    return  # Exit early - can't extract relationships without properties
            elif isinstance(props_str, dict):
                props_dict = props_str

        # Get IP configurations
        ip_configs = props_dict.get("ipConfigurations", [])

        for ip_config in ip_configs:
            # Subnet is nested in ipConfiguration.properties.subnet
            if isinstance(ip_config, dict) and "properties" in ip_config:
                ip_props = ip_config["properties"]

                # (NIC) -[:CONNECTED_TO]-> (Subnet)
                if "subnet" in ip_props:
                    subnet = ip_props["subnet"]
                    if isinstance(subnet, dict):
                        subnet_id = subnet.get("id")
                        if subnet_id and rid:
                            self.queue_dual_graph_relationship(
                                str(rid),
                                "CONNECTED_TO",
                                str(subnet_id),
                            )
                            logger.debug(
                                f"🔗 Queued CONNECTED_TO: {rid.split('/')[-1]} -> {subnet_id.split('/')[-1]}"
                            )
                            self.auto_flush_if_needed(db_ops)

        # (NIC) -[:SECURED_BY]-> (NSG) if NSG is attached
        nsg = props_dict.get("networkSecurityGroup")
        if nsg and isinstance(nsg, dict):
            nsg_id = nsg.get("id")
            if nsg_id and rid:
                self.queue_dual_graph_relationship(
                    str(rid),
                    "SECURED_BY",
                    str(nsg_id),
                )
                logger.debug(
                    f"🔗 Queued SECURED_BY: {rid.split('/')[-1]} -> {nsg_id.split('/')[-1]}"
                )
                self.auto_flush_if_needed(db_ops)

    def extract_target_ids(self, resource: Dict[str, Any]) -> Set[str]:
        """Extract subnet and NSG IDs that this NIC references."""
        target_ids: Set[str] = set()

        # Parse properties
        props_dict = {}
        if "properties" in resource:
            props_str = resource["properties"]
            if isinstance(props_str, str):
                try:
                    props_dict = json.loads(props_str)
                except json.JSONDecodeError:
                    return target_ids
            elif isinstance(props_str, dict):
                props_dict = props_str

        # Extract subnet IDs from ipConfigurations
        ip_configs = props_dict.get("ipConfigurations", [])
        for ip_config in ip_configs:
            if isinstance(ip_config, dict) and "properties" in ip_config:
                ip_props = ip_config["properties"]
                if "subnet" in ip_props and isinstance(ip_props["subnet"], dict):
                    subnet_id = ip_props["subnet"].get("id")
                    if subnet_id:
                        target_ids.add(str(subnet_id))

        # Extract NSG ID if attached
        nsg = props_dict.get("networkSecurityGroup")
        if nsg and isinstance(nsg, dict):
            nsg_id = nsg.get("id")
            if nsg_id:
                target_ids.add(str(nsg_id))

        return target_ids
