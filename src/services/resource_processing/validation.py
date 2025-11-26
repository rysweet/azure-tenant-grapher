"""
Resource Validation Module

This module provides validation for resource data before processing.
"""

import re
from typing import Any, Dict, List

from src.exceptions import ResourceDataValidationError

# Global resource types that don't require location/resource_group
GLOBAL_RESOURCE_TYPES = {
    "Microsoft.Authorization/roleAssignments",
    "Microsoft.Authorization/policyAssignments",
    "Microsoft.Authorization/roleDefinitions",
}


def get_required_fields(resource_type: str) -> List[str]:
    """
    Get required fields for a resource type.

    Args:
        resource_type: Azure resource type string

    Returns:
        List of required field names
    """
    if resource_type in GLOBAL_RESOURCE_TYPES:
        return ["id", "name", "type", "subscription_id"]
    else:
        return [
            "id",
            "name",
            "type",
            "location",
            "resource_group",
            "subscription_id",
        ]


def validate_resource_data(resource: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate resource data before processing.

    Args:
        resource: Resource dictionary to validate

    Returns:
        Validated resource dict (may be modified)

    Raises:
        ResourceDataValidationError: If required fields are missing/null
    """
    resource_type = resource.get("type", "")
    required_fields = get_required_fields(resource_type)

    # Accept id from resource_id if present
    if not resource.get("id") and resource.get("resource_id"):
        resource["id"] = resource["resource_id"]

    missing_or_null = [f for f in required_fields if resource.get(f) in (None, "")]
    if missing_or_null:
        raise ResourceDataValidationError(missing_fields=missing_or_null)

    return resource


def extract_identity_fields(resource: Dict[str, Any]) -> None:
    """
    Extracts 'identity' and 'principalId' from a resource dict if present.

    - Adds resource['identity'] if an 'identity' block is present.
    - Adds resource['principal_id'] if 'principalId' is present and looks like a GUID.

    Args:
        resource: Resource dictionary (modified in place)
    """
    # Extract 'identity' block if present
    identity = resource.get("identity")
    if identity is not None:
        resource["identity"] = identity

    # Extract 'principalId' if present and looks like a GUID
    principal_id = resource.get("principalId") or resource.get("principal_id")
    if principal_id and isinstance(principal_id, str):
        # Minimal GUID validation: 8-4-4-4-12 hex digits
        if re.match(
            r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
            principal_id,
        ):
            resource["principal_id"] = principal_id
