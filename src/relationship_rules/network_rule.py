"""
DEPRECATED: This file is deprecated in favor of network_rule_optimized.py.

The optimized version provides 100-400x performance improvement through batched
relationship creation. This file is kept for reference only.

Use NetworkRuleOptimized instead.
"""

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
    - (Subnet) -[:SECURED_BY]-> (NetworkSecurityGroup)
    - (Resource) -[:CONNECTED_TO_PE]- (PrivateEndpoint)
    - (DNSZone) -[:RESOLVES_TO]-> (Resource)

    Supports dual-graph architecture - creates relationships in both original and abstracted graphs.
    """

    def applies(self, resource: Dict[str, Any]) -> bool:
        rtype = resource.get("type", "")
        return (
            rtype.endswith("virtualMachines")
            or rtype.endswith("subnets")
            or rtype == "Microsoft.Network/privateEndpoints"
            or rtype == "Microsoft.Network/dnszones"
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
                            # Use dual-graph helper with immediate_flush for critical relationship
                            # This ensures USES_SUBNET relationships are created when both nodes exist
                            self.create_dual_graph_relationship(
                                db_ops,
                                str(rid),
                                "USES_SUBNET",
                                str(subnet_id),
                                immediate_flush=True,
                            )

        # (Subnet) -[:SECURED_BY]-> (NetworkSecurityGroup)
        if rtype.endswith("subnets"):
            nsg = props.get("network_security_group")
            if nsg and isinstance(nsg, dict):
                nsg_id = nsg.get("id")
                if nsg_id and rid:
                    # Use dual-graph helper instead of direct db_ops call
                    self.create_dual_graph_relationship(
                        db_ops,
                        str(rid),
                        "SECURED_BY",
                        str(nsg_id),
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
                    # Edge: PrivateEndpoint -> Resource (use dual-graph)
                    self.create_dual_graph_relationship(
                        db_ops,
                        str(rid),
                        CONNECTED_TO_PE,
                        str(pe_target_id),
                    )
                    # Edge: Resource -> PrivateEndpoint (reverse direction)
                    # Note: PrivateEndpoint is not a Resource node, so we use generic rel
                    # This creates from both original and abstracted Resource nodes
                    self.create_dual_graph_generic_rel(
                        db_ops,
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
                # DNSZone -> Resource (use generic rel since DNSZone is source)
                self.create_dual_graph_generic_rel(
                    db_ops,
                    str(rid),
                    RESOLVES_TO,
                    str(res_id),
                    "Resource",
                    "id",
                )

        # (Resource) with dnsZoneId property: create RESOLVES_TO edge from DNSZone
        dns_zone_id = resource.get("dnsZoneId")
        if dns_zone_id and rid:
            # DNSZone -> Resource relationship
            self.create_dual_graph_generic_rel(
                db_ops,
                str(dns_zone_id),
                RESOLVES_TO,
                str(rid),
                "Resource",
                "id",
            )
