from typing import Any, Dict

from .relationship_rule import RelationshipRule


class NetworkRule(RelationshipRule):
    """
    Emits network-related relationships:
    - (VirtualMachine) -[:USES_SUBNET]-> (Subnet)
    - (Subnet) -[:SECURED_BY]-> (NetworkSecurityGroup)
    """

    def applies(self, resource: Dict[str, Any]) -> bool:
        rtype = resource.get("type", "")
        return rtype.endswith("virtualMachines") or rtype.endswith("subnets")

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

        # (Subnet) -[:SECURED_BY]-> (NetworkSecurityGroup)
        if rtype.endswith("subnets"):
            nsg = props.get("network_security_group")
            if nsg and isinstance(nsg, dict):
                nsg_id = nsg.get("id")
                if nsg_id and rid:
                    db_ops.create_generic_rel(
                        str(rid), "SECURED_BY", str(nsg_id), "Resource", "id"
                    )
