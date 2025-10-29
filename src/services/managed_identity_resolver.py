"""Service for resolving managed identity details from Azure."""

import logging
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ManagedIdentityResolver:
    """Resolves managed identity details for both system and user-assigned identities."""

    def __init__(self, azure_service: Optional[Any] = None):
        """
        Initialize the managed identity resolver.

        Args:
            azure_service: Optional AzureDataService instance for querying Azure resources
        """
        self.azure_service = azure_service
        logger.debug("ManagedIdentityResolver initialized")

    def resolve_identities(
        self, identity_refs: Set[str], all_resources: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Resolve managed identities to their full details.

        Args:
            identity_refs: Set of identity IDs or resource IDs to resolve
            all_resources: List of all Azure resources to search through

        Returns:
            Dictionary mapping identity ID to identity details
        """
        resolved = {}

        for resource in all_resources:
            resource_type = resource.get("type", "")
            resource_id = resource.get("id", "")

            # Check if this is a user-assigned managed identity resource
            if resource_type == "Microsoft.ManagedIdentity/userAssignedIdentities":
                # The resource ID itself might be in our identity_refs
                if resource_id in identity_refs:
                    resolved[resource_id] = {
                        "id": resource_id,
                        "type": "UserAssignedManagedIdentity",
                        "name": resource.get("name"),
                        "location": resource.get("location"),
                        "principalId": resource.get("properties", {}).get(
                            "principalId"
                        ),
                        "clientId": resource.get("properties", {}).get("clientId"),
                        "tenantId": resource.get("properties", {}).get("tenantId"),
                    }
                    logger.debug(f"Resolved user-assigned identity: {resource_id}")

                # Also check if the principal ID is in our refs
                principal_id = resource.get("properties", {}).get("principalId")
                if principal_id and principal_id in identity_refs:
                    resolved[principal_id] = {
                        "id": principal_id,
                        "resourceId": resource_id,
                        "type": "UserAssignedManagedIdentity",
                        "name": resource.get("name"),
                        "location": resource.get("location"),
                        "principalId": principal_id,
                        "clientId": resource.get("properties", {}).get("clientId"),
                        "tenantId": resource.get("properties", {}).get("tenantId"),
                    }
                    logger.debug(
                        f"Resolved user-assigned identity by principal ID: {principal_id}"
                    )

            # Check for system-assigned identities
            identity = resource.get("identity")
            if identity and isinstance(identity, dict):
                identity_type = identity.get("type", "")

                # System-assigned identity
                if "SystemAssigned" in identity_type:
                    principal_id = identity.get("principalId")
                    if principal_id and principal_id in identity_refs:
                        resolved[principal_id] = {
                            "id": principal_id,
                            "type": "SystemAssignedManagedIdentity",
                            "resourceId": resource_id,
                            "resourceType": resource_type,
                            "resourceName": resource.get("name"),
                            "principalId": principal_id,
                            "tenantId": identity.get("tenantId"),
                        }
                        logger.debug(
                            f"Resolved system-assigned identity {principal_id} "
                            f"from resource {resource_id}"
                        )

        logger.info(
            f"Resolved {len(resolved)} managed identities out of {len(identity_refs)} references"
        )
        return resolved

    def extract_additional_references(
        self, resolved_identities: Dict[str, Dict[str, Any]]
    ) -> Set[str]:
        """
        Extract additional identity references from resolved identities.

        Some resolved identities might reference other identities that also need to be included.

        Args:
            resolved_identities: Dictionary of resolved identity details

        Returns:
            Set of additional identity IDs to fetch
        """
        additional_refs = set()

        # Currently, managed identities don't typically reference other identities directly
        # But this method is here for future extensibility if needed

        return additional_refs

    def get_identity_summary(
        self, resolved_identities: Dict[str, Dict[str, Any]]
    ) -> str:
        """
        Get a human-readable summary of resolved identities.

        Args:
            resolved_identities: Dictionary of resolved identity details

        Returns:
            String summary of identities
        """
        if not resolved_identities:
            return "No managed identities resolved"

        system_assigned = 0
        user_assigned = 0

        for identity in resolved_identities.values():
            if identity.get("type") == "SystemAssignedManagedIdentity":
                system_assigned += 1
            elif identity.get("type") == "UserAssignedManagedIdentity":
                user_assigned += 1

        parts = []
        if system_assigned:
            parts.append(f"{system_assigned} system-assigned")
        if user_assigned:
            parts.append(f"{user_assigned} user-assigned")

        return f"Resolved {len(resolved_identities)} managed identities: {', '.join(parts)}"
