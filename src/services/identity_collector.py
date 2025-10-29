"""Service for collecting identity references from Azure resources."""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class IdentityReference:
    """Reference to an identity found in Azure resources."""

    id: str
    type: str  # "User", "ServicePrincipal", "ManagedIdentity", "Group"
    source_resource_id: Optional[str] = None


@dataclass
class IdentityReferences:
    """Collection of identity references grouped by type."""

    users: Set[str] = field(default_factory=set)
    service_principals: Set[str] = field(default_factory=set)
    managed_identities: Set[str] = field(default_factory=set)
    groups: Set[str] = field(default_factory=set)

    def has_identities(self) -> bool:
        """Check if any identities have been collected."""
        return bool(
            self.users
            or self.service_principals
            or self.managed_identities
            or self.groups
        )

    def total_count(self) -> int:
        """Get total count of unique identities."""
        return (
            len(self.users)
            + len(self.service_principals)
            + len(self.managed_identities)
            + len(self.groups)
        )


class IdentityCollector:
    """Collects identity references from Azure resources."""

    def __init__(self):
        """Initialize the identity collector."""
        logger.debug("IdentityCollector initialized")

    def collect_identity_references(
        self, resources: List[Dict[str, Any]]
    ) -> IdentityReferences:
        """
        Extract all identity references from resources.

        Args:
            resources: List of Azure resource dictionaries

        Returns:
            IdentityReferences containing all discovered identities
        """
        references = IdentityReferences()

        for resource in resources:
            try:
                # Extract managed identities
                identity_refs = self.extract_managed_identities(resource)
                for ref in identity_refs:
                    if ref.type == "ManagedIdentity":
                        references.managed_identities.add(ref.id)

                # Extract role assignment principals
                principal_refs = self.extract_role_assignment_principals(resource)
                for ref in principal_refs:
                    if ref.type == "User":
                        references.users.add(ref.id)
                    elif ref.type == "ServicePrincipal":
                        references.service_principals.add(ref.id)
                    elif ref.type == "Group":
                        references.groups.add(ref.id)
                    elif ref.type == "ManagedIdentity":
                        references.managed_identities.add(ref.id)

            except Exception as e:
                logger.warning(
                    f"Error extracting identities from resource {resource.get('id', 'unknown')}: {e}"
                )

        logger.info(
            f"Collected identities - Users: {len(references.users)}, "
            f"Service Principals: {len(references.service_principals)}, "
            f"Managed Identities: {len(references.managed_identities)}, "
            f"Groups: {len(references.groups)}"
        )

        return references

    def extract_managed_identities(
        self, resource: Dict[str, Any]
    ) -> List[IdentityReference]:
        """
        Extract managed identity references from a single resource.

        Args:
            resource: Azure resource dictionary

        Returns:
            List of IdentityReference objects for managed identities
        """
        identities = []
        resource_id = resource.get("id")

        # Check for identity block in resource
        identity = resource.get("identity")
        if not identity or not isinstance(identity, dict):
            return identities

        identity_type = identity.get("type", "")

        # Handle system-assigned managed identity
        if identity_type in ["SystemAssigned", "SystemAssigned,UserAssigned"]:
            principal_id = identity.get("principalId")
            if principal_id:
                identities.append(
                    IdentityReference(
                        id=principal_id,
                        type="ManagedIdentity",
                        source_resource_id=resource_id,
                    )
                )
                logger.debug(
                    f"Found system-assigned identity {principal_id} in resource {resource_id}"
                )

        # Handle user-assigned managed identities
        if identity_type in ["UserAssigned", "SystemAssigned,UserAssigned"]:
            user_identities = identity.get("userAssignedIdentities", {})
            if isinstance(user_identities, dict):
                for identity_resource_id, identity_details in user_identities.items():
                    # The key is the resource ID of the user-assigned identity
                    identities.append(
                        IdentityReference(
                            id=identity_resource_id,
                            type="ManagedIdentity",
                            source_resource_id=resource_id,
                        )
                    )

                    # Some resources also include the principal ID in the details
                    if isinstance(identity_details, dict):
                        principal_id = identity_details.get("principalId")
                        if principal_id:
                            identities.append(
                                IdentityReference(
                                    id=principal_id,
                                    type="ManagedIdentity",
                                    source_resource_id=resource_id,
                                )
                            )

                    logger.debug(
                        f"Found user-assigned identity {identity_resource_id} in resource {resource_id}"
                    )

        return identities

    def extract_role_assignment_principals(
        self, resource: Dict[str, Any]
    ) -> List[IdentityReference]:
        """
        Extract principal IDs from role assignments.

        Args:
            resource: Azure resource dictionary

        Returns:
            List of IdentityReference objects for principals in role assignments
        """
        identities = []
        resource_id = resource.get("id")
        resource_type = resource.get("type", "")

        # Check if this is a role assignment
        if not resource_type.endswith("roleAssignments"):
            return identities

        # Get properties (could be in properties or at root level)
        props = resource.get("properties", resource)

        principal_id = props.get("principalId")
        principal_type = props.get("principalType", "Unknown")

        if principal_id:
            # Map Azure principal types to our types
            type_mapping = {
                "User": "User",
                "Group": "Group",
                "ServicePrincipal": "ServicePrincipal",
                "ManagedIdentity": "ManagedIdentity",
                "Application": "ServicePrincipal",  # Applications are service principals
                "ForeignGroup": "Group",
                "Unknown": "ServicePrincipal",  # Default to service principal for unknown
            }

            identity_type = type_mapping.get(principal_type, "ServicePrincipal")

            identities.append(
                IdentityReference(
                    id=principal_id, type=identity_type, source_resource_id=resource_id
                )
            )

            logger.debug(
                f"Found {identity_type} principal {principal_id} in role assignment {resource_id}"
            )

        return identities

    def get_summary(self, references: IdentityReferences) -> str:
        """
        Get a human-readable summary of collected identities.

        Args:
            references: IdentityReferences to summarize

        Returns:
            String summary of identities
        """
        if not references.has_identities():
            return "No identities found"

        parts = []
        if references.users:
            parts.append(f"{len(references.users)} users")
        if references.service_principals:
            parts.append(f"{len(references.service_principals)} service principals")
        if references.managed_identities:
            parts.append(f"{len(references.managed_identities)} managed identities")
        if references.groups:
            parts.append(f"{len(references.groups)} groups")

        return f"Found {references.total_count()} identities: {', '.join(parts)}"
