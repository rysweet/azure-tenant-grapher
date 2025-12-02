"""Private Endpoint and Private DNS Zone emitter utilities.

This module provides helper functions for emitting Private Endpoint and
Private DNS Zone resources in Terraform format.
"""

import json
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from ..translators.private_endpoint_translator import PrivateEndpointTranslator

logger = logging.getLogger(__name__)


def parse_properties(resource: Dict[str, Any]) -> Dict[str, Any]:
    """Parse properties JSON from resource.

    Args:
        resource: Azure resource with properties field

    Returns:
        Parsed properties dict (empty dict if parsing fails)
    """
    properties_str = resource.get("properties", "{}")
    if isinstance(properties_str, str):
        try:
            return json.loads(properties_str)
        except json.JSONDecodeError:
            logger.warning(
                f"Failed to parse properties for resource '{resource.get('name')}'"
            )
            return {}
    return properties_str if isinstance(properties_str, dict) else {}


def extract_resource_name_from_id(resource_id: str, resource_type: str) -> str:
    """Extract resource name from Azure resource ID path.

    Args:
        resource_id: Full Azure resource ID
        resource_type: Azure resource type segment (e.g., "subnets", "virtualNetworks")

    Returns:
        Extracted resource name or "unknown"
    """
    if not resource_id:
        return "unknown"

    path_segment = f"/{resource_type}/"
    if path_segment in resource_id:
        return resource_id.split(path_segment)[-1].split("/")[0]
    return "unknown"


def sanitize_terraform_name(name: str) -> str:
    """Sanitize resource name for Terraform compatibility.

    Args:
        name: Original resource name

    Returns:
        Sanitized name safe for Terraform
    """
    import re

    # Replace invalid characters with underscores
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", name)

    # Ensure it starts with a letter or underscore
    if sanitized and sanitized[0].isdigit():
        sanitized = f"resource_{sanitized}"

    return sanitized or "unnamed_resource"


def emit_private_endpoint(
    resource: Dict[str, Any],
    sanitize_name_fn: Optional[callable] = None,
    extract_name_fn: Optional[callable] = None,
    available_subnets: Optional[set] = None,
    missing_references: Optional[List[Dict[str, str]]] = None,
    translator: Optional["PrivateEndpointTranslator"] = None,
) -> Dict[str, Any]:
    """Generate azurerm_private_endpoint resource configuration.

    Args:
        resource: Private endpoint resource data from Neo4j
        sanitize_name_fn: Function to sanitize resource names (optional)
        extract_name_fn: Function to extract names from resource IDs (optional)
        available_subnets: Set of available VNet-scoped subnet names for validation
        missing_references: List to append missing reference information to
        translator: Optional translator for cross-subscription resource IDs

    Returns:
        Terraform resource configuration dictionary
    """
    sanitize = sanitize_name_fn or sanitize_terraform_name
    extract = extract_name_fn or extract_resource_name_from_id

    resource_name = resource.get("name", "unknown")
    properties = parse_properties(resource)

    # Extract subnet reference
    subnet_info = properties.get("subnet", {})
    subnet_id = subnet_info.get("id", "")

    # Extract VNet and subnet names for scoped reference
    vnet_name = extract(subnet_id, "virtualNetworks")
    subnet_name = extract(subnet_id, "subnets")

    # Build VNet-scoped subnet reference
    subnet_reference = "${azurerm_subnet.unknown_subnet.id}"
    if vnet_name != "unknown" and subnet_name != "unknown":
        vnet_name_safe = sanitize(vnet_name)
        subnet_name_safe = sanitize(subnet_name)
        scoped_subnet_name = f"{vnet_name_safe}_{subnet_name_safe}"

        # Validate subnet exists if validation set provided
        if (
            available_subnets is not None
            and scoped_subnet_name not in available_subnets
        ):
            logger.error(
                f"Private Endpoint '{resource_name}' references subnet that doesn't exist:\n"
                f"  Subnet Terraform name: {scoped_subnet_name}\n"
                f"  Subnet Azure name: {subnet_name}\n"
                f"  VNet Azure name: {vnet_name}\n"
                f"  Azure ID: {subnet_id}"
            )
            if missing_references is not None:
                missing_references.append(
                    {
                        "resource_name": resource_name,
                        "resource_type": "subnet",
                        "missing_resource_name": subnet_name,
                        "missing_resource_id": subnet_id,
                        "missing_vnet_name": vnet_name,
                        "expected_terraform_name": scoped_subnet_name,
                    }
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

    # Build base configuration
    config = {
        "name": resource_name,
        "location": resource.get("location", "eastus"),
        "resource_group_name": resource.get("resource_group", "default-rg"),
        "subnet_id": subnet_reference,
    }

    # Extract private link service connections
    private_link_connections = properties.get("privateLinkServiceConnections", [])
    if private_link_connections:
        connection_configs = []
        for conn in private_link_connections:
            conn_props = conn.get("properties", {})
            conn_config = {
                "name": conn.get("name", f"{resource_name}-connection"),
                "is_manual_connection": False,
            }

            # Add target resource ID with optional translation
            target_resource_id = conn_props.get("privateLinkServiceId")
            if target_resource_id:
                # Apply translation if translator is provided and translation is needed
                if translator and translator.should_translate(target_resource_id):
                    result = translator.translate_resource_id(
                        target_resource_id, resource_name
                    )
                    conn_config["private_connection_resource_id"] = result.translated_id
                    # Log any warnings from translation
                    for warning in result.warnings:
                        logger.warning(warning)
                else:
                    # No translation needed or no translator provided
                    conn_config["private_connection_resource_id"] = target_resource_id

            # Add subresource names (group IDs)
            group_ids = conn_props.get("groupIds", [])
            if group_ids:
                conn_config["subresource_names"] = group_ids

            connection_configs.append(conn_config)

        if connection_configs:
            config["private_service_connection"] = connection_configs
    else:
        logger.warning(
            f"Private Endpoint '{resource_name}' has no private link service connections"
        )

    # Add tags if present
    tags = resource.get("tags")
    if tags:
        if isinstance(tags, str):
            try:
                parsed_tags = json.loads(tags)
                if isinstance(parsed_tags, dict) and parsed_tags:
                    config["tags"] = parsed_tags
            except json.JSONDecodeError:
                pass
        elif isinstance(tags, dict) and tags:
            config["tags"] = tags

    return config


def emit_private_dns_zone(resource: Dict[str, Any]) -> Dict[str, Any]:
    """Generate azurerm_private_dns_zone resource configuration.

    Args:
        resource: Private DNS zone resource data from Neo4j

    Returns:
        Terraform resource configuration dictionary
    """
    resource_name = resource.get("name", "unknown")

    # Extract RG from original_id (abstracted resources have hash IDs)
    resource_group = resource.get("resource_group")
    if not resource_group:
        # Parse from original_id: /subscriptions/.../resourceGroups/RG_NAME/...
        original_id = resource.get("original_id") or resource.get("id", "")
        if "/resourceGroups/" in original_id:
            rg_part = original_id.split("/resourceGroups/")[1]
            resource_group = rg_part.split("/")[0] if "/" in rg_part else rg_part
        else:
            resource_group = "default-rg"

    config = {
        "name": resource_name,
        "resource_group_name": resource_group,
    }

    # Add tags if present
    tags = resource.get("tags")
    if tags:
        if isinstance(tags, str):
            try:
                parsed_tags = json.loads(tags)
                if isinstance(parsed_tags, dict) and parsed_tags:
                    config["tags"] = parsed_tags
            except json.JSONDecodeError:
                pass
        elif isinstance(tags, dict) and tags:
            config["tags"] = tags

    return config


def emit_private_dns_zone_vnet_link(
    resource: Dict[str, Any],
    sanitize_name_fn: Optional[callable] = None,
    extract_name_fn: Optional[callable] = None,
    available_vnets: Optional[set] = None,
    available_dns_zones: Optional[set] = None,
    missing_references: Optional[List[Dict[str, str]]] = None,
) -> Optional[Dict[str, Any]]:
    """Generate azurerm_private_dns_zone_virtual_network_link resource configuration.

    Args:
        resource: Virtual network link resource data from Neo4j
        sanitize_name_fn: Function to sanitize resource names (optional)
        extract_name_fn: Function to extract names from resource IDs (optional)
        available_vnets: Set of available VNet names for validation
        available_dns_zones: Set of available Private DNS Zone names for validation
        missing_references: List to append missing reference information to

    Returns:
        Terraform resource configuration dictionary or None if invalid
    """
    sanitize = sanitize_name_fn or sanitize_terraform_name
    extract = extract_name_fn or extract_resource_name_from_id

    resource_name = resource.get("name", "unknown")
    properties = parse_properties(resource)

    # Extract DNS zone name from resource name (format: "zone-name/link-name")
    if "/" in resource_name:
        dns_zone_name = resource_name.split("/")[0]
    else:
        logger.error(
            f"Virtual Network Link '{resource_name}' has invalid name format (expected 'zone/link')"
        )
        return None

    # Extract VNet reference
    vnet_info = properties.get("virtualNetwork", {})
    vnet_id = vnet_info.get("id", "")
    vnet_name = extract(vnet_id, "virtualNetworks")

    if vnet_name == "unknown":
        logger.warning(
            f"Virtual Network Link '{resource_name}' has invalid VNet reference: {vnet_id}"
        )
        return None

    vnet_name_safe = sanitize(vnet_name)

    # Validate VNet exists if validation set provided
    if available_vnets is not None and vnet_name_safe not in available_vnets:
        logger.error(
            f"Virtual Network Link '{resource_name}' references VNet that doesn't exist:\n"
            f"  VNet Terraform name: {vnet_name_safe}\n"
            f"  VNet Azure name: {vnet_name}\n"
            f"  Azure ID: {vnet_id}"
        )
        if missing_references is not None:
            missing_references.append(
                {
                    "resource_name": resource_name,
                    "resource_type": "virtual_network",
                    "missing_resource_name": vnet_name,
                    "missing_resource_id": vnet_id,
                    "expected_terraform_name": vnet_name_safe,
                }
            )

    dns_zone_name_safe = sanitize(dns_zone_name)

    # Validate DNS Zone exists if validation set provided
    if (
        available_dns_zones is not None
        and dns_zone_name_safe not in available_dns_zones
    ):
        logger.error(
            f"Virtual Network Link '{resource_name}' references Private DNS Zone that doesn't exist:\n"
            f"  DNS Zone Terraform name: {dns_zone_name_safe}\n"
            f"  DNS Zone Azure name: {dns_zone_name}\n"
            f"  This DNS Zone must be emitted before the VNet Link can reference it."
        )
        if missing_references is not None:
            missing_references.append(
                {
                    "resource_name": resource_name,
                    "resource_type": "private_dns_zone",
                    "missing_resource_name": dns_zone_name,
                    "expected_terraform_name": dns_zone_name_safe,
                }
            )
        # Return None to skip this VNet Link (cannot deploy without parent DNS Zone)
        return None

    # Build link name from zone and VNet
    link_name = f"{dns_zone_name_safe}_{vnet_name_safe}_link"

    config = {
        "name": link_name,
        "resource_group_name": resource.get("resource_group", "default-rg"),
        "private_dns_zone_name": f"${{azurerm_private_dns_zone.{dns_zone_name_safe}.name}}",
        "virtual_network_id": f"${{azurerm_virtual_network.{vnet_name_safe}.id}}",
    }

    # Add registration enabled flag
    registration_enabled = properties.get("registrationEnabled", False)
    if registration_enabled:
        config["registration_enabled"] = True

    # Add tags if present
    tags = resource.get("tags")
    if tags:
        if isinstance(tags, str):
            try:
                parsed_tags = json.loads(tags)
                if isinstance(parsed_tags, dict) and parsed_tags:
                    config["tags"] = parsed_tags
            except json.JSONDecodeError:
                pass
        elif isinstance(tags, dict) and tags:
            config["tags"] = tags

    return config
