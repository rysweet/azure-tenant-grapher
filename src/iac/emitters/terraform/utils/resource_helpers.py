"""Utility functions for Terraform resource handling.

This module provides helper functions for working with Azure resource IDs,
resource group extraction, and resource metadata operations.
"""

from typing import Optional


def extract_resource_group_from_id(resource_id: Optional[str]) -> Optional[str]:
    """Extract resource group name from Azure resource ID.

    Parses standard Azure resource IDs to extract the resource group name.
    Returns None for subscription-level resources or invalid IDs.

    Args:
        resource_id: Azure resource ID in format:
            /subscriptions/{sub}/resourceGroups/{rg}/providers/{provider}/{type}/{name}

    Returns:
        Resource group name if found, None otherwise

    Examples:
        >>> extract_resource_group_from_id(
        ...     "/subscriptions/12345/resourceGroups/my-rg/providers/Microsoft.Network/virtualNetworks/vnet1"
        ... )
        'my-rg'

        >>> extract_resource_group_from_id("/subscriptions/12345/providers/Microsoft.Resources/deployments/deploy1")
        None

        >>> extract_resource_group_from_id("")
        None
    """
    if not resource_id or not isinstance(resource_id, str):
        return None

    if "/resourceGroups/" not in resource_id:
        return None

    parts = resource_id.split("/")
    try:
        rg_index = parts.index("resourceGroups")
        # Next element after "resourceGroups" is the RG name
        return parts[rg_index + 1]
    except (ValueError, IndexError):
        return None


__all__ = ["extract_resource_group_from_id"]
