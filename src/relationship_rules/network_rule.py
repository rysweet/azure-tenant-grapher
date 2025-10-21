from typing import Any, Dict, List

from .relationship_rule import RelationshipRule

# Node labels
PRIVATE_ENDPOINT = "PrivateEndpoint"
DNS_ZONE = "DNSZone"

# Edge types
CONNECTED_TO_PE = "CONNECTED_TO_PE"
RESOLVES_TO = "RESOLVES_TO"


class NetworkRule(RelationshipRule):
    """
    Emits network-related relationships:
    - (VirtualMachine) -[:USES_SUBNET]-> (Subnet)
    - (NetworkInterface) -[:USES_SUBNET]-> (Subnet)
    - (Subnet) -[:SECURED_BY]-> (NetworkSecurityGroup)
    - (Resource) -[:CONNECTED_TO_PE]- (PrivateEndpoint)
    - (DNSZone) -[:RESOLVES_TO]-> (Resource)
    """

    def applies(self, resource: Dict[str, Any]) -> bool:
        rtype = resource.get("type", "")
        return (
            rtype.endswith("virtualMachines")
            or rtype.endswith("subnets")
            or rtype == "Microsoft.Network/privateEndpoints"
            or rtype == "Microsoft.Network/dnszones"
            or rtype == "Microsoft.Network/networkInterfaces"
        )

    def emit(self, resource: Dict[str, Any], db_ops: Any) -> None:
        rid = resource.get("id")
        rtype = resource.get("type", "")
        props = resource

        # (VirtualMachine) -[:USES_SUBNET]-> (Subnet)
        if rtype.endswith("virtualMachines") and "network_profile" in props:
            nics = props["network_profile"].get("network_interfaces", [])
            for nic in nics:
                ip_cfgs = nic.get("ip_configurations", [])
                for ipcfg in ip_cfgs:
                    subnet = ipcfg.get("subnet")
                    if subnet and isinstance(subnet, dict):
                        subnet_id = subnet.get("id")
                        if subnet_id and rid:
                            db_ops.create_generic_rel(
                                str(rid),
                                "USES_SUBNET",
                                str(subnet_id),
                                "Resource",
                                "id",
                            )

        # (NetworkInterface) -[:USES_SUBNET]-> (Subnet)
        # Handle NICs that may reference subnets in different resource groups
        if rtype == "Microsoft.Network/networkInterfaces":
            # Parse properties if it's a JSON string
            parsed_props = {}
            if isinstance(props.get("properties"), str):
                import json
                try:
                    parsed_props = json.loads(props["properties"])
                except (json.JSONDecodeError, KeyError, TypeError):
                    # If parsing fails, default to empty dict
                    parsed_props = {}
            elif isinstance(props.get("properties"), dict):
                parsed_props = props.get("properties", {})

            # Only proceed if parsed_props is a dict
            if isinstance(parsed_props, dict):
                ip_configs = parsed_props.get("ipConfigurations", [])
                for ip_config in ip_configs:
                    subnet_ref = ip_config.get("subnet")
                    if subnet_ref and isinstance(subnet_ref, dict):
                        subnet_id = subnet_ref.get("id")
                        if subnet_id and rid:
                            db_ops.create_generic_rel(
                                str(rid),
                                "USES_SUBNET",
                                str(subnet_id),
                                "Resource",
                                "id",
                            )

        # (Subnet) -[:SECURED_BY]-> (NetworkSecurityGroup)
        if rtype.endswith("subnets"):
            nsg = props.get("network_security_group")
            if nsg and isinstance(nsg, dict):
                nsg_id = nsg.get("id")
                if nsg_id and rid:
                    db_ops.create_generic_rel(
                        str(rid), "SECURED_BY", str(nsg_id), "Resource", "id"
                    )

        # (PrivateEndpoint) node and CONNECTED_TO_PE edges
        if rtype == "Microsoft.Network/privateEndpoints":
            # Upsert PrivateEndpoint node
            db_ops.upsert_generic(
                PRIVATE_ENDPOINT,
                "id",
                rid,
                {"id": rid, **{k: v for k, v in resource.items() if k != "type"}},
            )
            # Find referenced resource IDs in privateLinkServiceConnections
            connections: List[Dict[str, Any]] = resource.get("properties", {}).get(
                "privateLinkServiceConnections", []
            )
            for conn in connections:
                pe_target_id = conn.get("privateLinkServiceId")
                if pe_target_id:
                    # Edge: Resource <-> PrivateEndpoint (bidirectional)
                    db_ops.create_generic_rel(
                        str(rid), CONNECTED_TO_PE, str(pe_target_id), "Resource", "id"
                    )
                    db_ops.create_generic_rel(
                        str(pe_target_id),
                        CONNECTED_TO_PE,
                        str(rid),
                        PRIVATE_ENDPOINT,
                        "id",
                    )

        # (DNSZone) node and RESOLVES_TO edges
        if rtype == "Microsoft.Network/dnszones":
            # Upsert DNSZone node
            db_ops.upsert_generic(
                DNS_ZONE,
                "id",
                rid,
                {"id": rid, **{k: v for k, v in resource.items() if k != "type"}},
            )
            # This rule does not know all resources, so RESOLVES_TO edges are created elsewhere.
            # But if the resource has a 'resolves_to' property (for testability), emit edges.
            resolves_to = resource.get("resolves_to", [])
            for res_id in resolves_to:
                db_ops.create_generic_rel(
                    str(rid), RESOLVES_TO, str(res_id), "Resource", "id"
                )

        # (Resource) with dnsZoneId property: create RESOLVES_TO edge from DNSZone
        dns_zone_id = resource.get("dnsZoneId")
        if dns_zone_id and rid:
            db_ops.create_generic_rel(
                str(dns_zone_id), RESOLVES_TO, str(rid), "Resource", "id"
            )
