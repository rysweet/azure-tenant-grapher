"""
Subnet Extraction Rule

Extracts embedded subnets from VNet properties and creates standalone subnet nodes.
This enables proper Terraform IaC generation where NICs can reference subnets as
independent resources.
"""

import json
import logging
from typing import Any, Dict

from .relationship_rule import RelationshipRule

logger = logging.getLogger(__name__)


class SubnetExtractionRule(RelationshipRule):
    """
    Extracts embedded subnets from VNet properties and creates standalone subnet nodes.

    When a VNet resource is processed, this rule:
    1. Extracts subnets from properties.subnets[] array
    2. Creates standalone Resource nodes (type: Microsoft.Network/subnets)
    3. Creates CONTAINS relationships: (VNet)-[:CONTAINS]->(Subnet)

    This enables IaC generators to reference subnets as independent resources.
    """

    def applies(self, resource: Dict[str, Any]) -> bool:
        """
        Check if this rule applies to the resource.

        Args:
            resource: Resource dictionary

        Returns:
            True if resource is a VNet with required fields
        """
        rtype = resource.get("type", "")
        if rtype != "Microsoft.Network/virtualNetworks":
            return False

        # Ensure VNet has required fields
        if not resource.get("id"):
            logger.warning("VNet resource missing ID, skipping subnet extraction")
            return False

        return True

    def emit(self, resource: Dict[str, Any], db_ops: Any) -> None:
        """
        Extract subnets from VNet and create standalone nodes.

        Args:
            resource: VNet resource dictionary
            db_ops: Database operations object
        """
        vnet_id = resource.get("id")
        if not vnet_id:
            return

        # Parse VNet properties
        properties = self._parse_properties(resource)
        subnets = properties.get("subnets", [])

        if not subnets:
            logger.debug(f"VNet {vnet_id} has no subnets to extract")
            return

        logger.info(f"Extracting {len(subnets)} subnets from VNet {vnet_id}")

        # Process each subnet
        for subnet in subnets:
            try:
                subnet_resource = self._build_subnet_resource(resource, subnet)
                if subnet_resource:
                    # Create standalone subnet node
                    db_ops.upsert_resource(
                        subnet_resource,
                        processing_status="completed"
                    )

                    # Create VNet -> Subnet relationship
                    db_ops.create_generic_rel(
                        str(vnet_id),
                        "CONTAINS",
                        str(subnet_resource["id"]),
                        "Resource",
                        "id"
                    )

                    logger.debug(
                        f"Created subnet node: {subnet_resource['id']}"
                    )
            except Exception as e:
                subnet_name = subnet.get("name", "unknown")
                logger.error(
                    f"Failed to create subnet {subnet_name} in VNet {vnet_id}: {e}"
                )

    def _parse_properties(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse properties field which may be a JSON string or dict.

        Args:
            resource: Resource dictionary

        Returns:
            Properties dictionary
        """
        properties = resource.get("properties", "{}")

        if isinstance(properties, str):
            try:
                return json.loads(properties)
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Failed to parse properties for {resource.get('id')}: {e}"
                )
                return {}

        return properties if isinstance(properties, dict) else {}

    def _build_subnet_resource(
        self, vnet_resource: Dict[str, Any], subnet: Dict[str, Any]
    ) -> Dict[str, Any] | None:
        """
        Build a standalone subnet resource from VNet and subnet data.

        Args:
            vnet_resource: Parent VNet resource
            subnet: Subnet data from VNet properties

        Returns:
            Subnet resource dictionary or None if invalid
        """
        vnet_id = vnet_resource.get("id")
        subnet_name = subnet.get("name")

        if not subnet_name:
            logger.warning(
                f"Subnet in VNet {vnet_id} missing name, skipping"
            )
            return None

        # Construct subnet ID following Azure ARM format
        subnet_id = f"{vnet_id}/subnets/{subnet_name}"

        # Extract subnet properties
        subnet_props = self._extract_subnet_properties(subnet)

        # Validate required fields
        if not subnet_props.get("addressPrefix") and not subnet_props.get("addressPrefixes"):
            logger.warning(
                f"Subnet {subnet_name} in VNet {vnet_id} has no address prefix, skipping"
            )
            return None

        # Build subnet resource
        subnet_resource = {
            "id": subnet_id,
            "name": subnet_name,
            "type": "Microsoft.Network/subnets",
            "location": vnet_resource.get("location"),
            "resource_group": vnet_resource.get("resource_group"),
            "subscription_id": vnet_resource.get("subscription_id"),
            "parent_id": vnet_id,
            "properties": self._serialize_value(subnet_props),
        }

        return subnet_resource

    def _extract_subnet_properties(self, subnet: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract relevant properties from subnet data.

        Args:
            subnet: Subnet data from VNet

        Returns:
            Dictionary of subnet properties
        """
        subnet_props = subnet.get("properties", {})

        # Build properties dictionary with all relevant fields
        extracted = {}

        # Address prefixes (required)
        if "addressPrefixes" in subnet_props:
            extracted["addressPrefixes"] = subnet_props["addressPrefixes"]
        elif "addressPrefix" in subnet_props:
            extracted["addressPrefix"] = subnet_props["addressPrefix"]

        # Optional properties
        optional_props = [
            "networkSecurityGroup",
            "routeTable",
            "serviceEndpoints",
            "delegations",
            "privateEndpointNetworkPolicies",
            "privateLinkServiceNetworkPolicies",
            "ipConfigurations",
            "serviceEndpointPolicies",
            "natGateway",
        ]

        for prop in optional_props:
            if prop in subnet_props:
                extracted[prop] = subnet_props[prop]

        return extracted

    def _serialize_value(self, value: Any) -> str:
        """
        Serialize a value to JSON string for Neo4j storage.

        Args:
            value: Value to serialize

        Returns:
            JSON string
        """
        if isinstance(value, str):
            return value

        try:
            return json.dumps(value)
        except (TypeError, ValueError):
            return str(value)
