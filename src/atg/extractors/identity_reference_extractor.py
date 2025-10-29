"""Extracts managed identity references from Azure resources."""

import logging
from typing import Any, Dict, List, Set

logger = logging.getLogger(__name__)


class IdentityReferenceExtractor:
    """Extracts managed identity references from Azure resources."""

    def __init__(self):
        """Initialize the identity reference extractor."""
        self.identity_references: Set[str] = set()
        self.user_assigned_identity_resource_ids: Set[str] = set()

    def extract_from_resources(
        self, resources: List[Dict[str, Any]]
    ) -> Dict[str, Set[str]]:
        """
        Extract all managed identity references from a list of resources.

        Args:
            resources: List of Azure resource dictionaries

        Returns:
            Dictionary containing:
                - 'object_ids': Set of identity object IDs to fetch
                - 'user_assigned_resource_ids': Set of user-assigned identity resource IDs
        """
        self.identity_references.clear()
        self.user_assigned_identity_resource_ids.clear()

        for resource in resources:
            self._extract_from_resource(resource)

        logger.info(f"Extracted {len(self.identity_references)} identity object IDs")
        logger.info(
            f"Found {len(self.user_assigned_identity_resource_ids)} user-assigned identity resource IDs"
        )

        return {
            "object_ids": self.identity_references.copy(),
            "user_assigned_resource_ids": self.user_assigned_identity_resource_ids.copy(),
        }

    def _extract_from_resource(self, resource: Dict[str, Any]) -> None:
        """
        Extract identity references from a single resource.

        Args:
            resource: Azure resource dictionary
        """
        # Extract from identity property (common pattern)
        identity = resource.get("identity")
        if identity:
            self._extract_from_identity_property(identity)

        # Extract from properties.identity (some resources use this)
        properties = resource.get("properties", {})
        if properties and isinstance(properties, dict):
            properties_identity = properties.get("identity")
            if properties_identity:
                self._extract_from_identity_property(properties_identity)

            # Check for service principal references in properties
            self._extract_service_principal_references(properties)

        # Check for specific resource types that have unique patterns
        resource_type = resource.get("type", "").lower()
        self._extract_by_resource_type(resource, resource_type)

    def _extract_from_identity_property(self, identity: Dict[str, Any]) -> None:
        """
        Extract identity references from an identity property.

        Args:
            identity: Identity property dictionary
        """
        if not isinstance(identity, dict):
            return

        # System-assigned identity
        principal_id = identity.get("principalId")
        if principal_id and principal_id != "00000000-0000-0000-0000-000000000000":
            self.identity_references.add(principal_id)
            logger.debug(f"Found system-assigned identity: {principal_id}")

        # User-assigned identities
        user_assigned_identities = identity.get("userAssignedIdentities")
        if user_assigned_identities and isinstance(user_assigned_identities, dict):
            for resource_id, identity_info in user_assigned_identities.items():
                # Add the resource ID for later resolution
                self.user_assigned_identity_resource_ids.add(resource_id)

                # Extract the principal ID if available
                if isinstance(identity_info, dict):
                    user_principal_id = identity_info.get("principalId")
                    if (
                        user_principal_id
                        and user_principal_id != "00000000-0000-0000-0000-000000000000"
                    ):
                        self.identity_references.add(user_principal_id)
                        logger.debug(
                            f"Found user-assigned identity: {user_principal_id} from {resource_id}"
                        )

    def _extract_service_principal_references(self, properties: Dict[str, Any]) -> None:
        """
        Extract service principal references from resource properties.

        Args:
            properties: Resource properties dictionary
        """
        # Common property names that might contain service principal IDs
        sp_properties = [
            "servicePrincipalId",
            "objectId",
            "principalId",
            "clientId",
            "applicationId",
        ]

        for prop in sp_properties:
            value = properties.get(prop)
            if value and isinstance(value, str) and self._is_valid_guid(value):
                self.identity_references.add(value)
                logger.debug(f"Found service principal reference in {prop}: {value}")

        # Check nested properties for Key Vault access policies
        access_policies = properties.get("accessPolicies", [])
        if isinstance(access_policies, list):
            for policy in access_policies:
                if isinstance(policy, dict):
                    object_id = policy.get("objectId")
                    if object_id and self._is_valid_guid(object_id):
                        self.identity_references.add(object_id)
                        logger.debug(f"Found identity in access policy: {object_id}")

    def _extract_by_resource_type(
        self, resource: Dict[str, Any], resource_type: str
    ) -> None:
        """
        Extract identity references based on specific resource types.

        Args:
            resource: Azure resource dictionary
            resource_type: Lowercase resource type string
        """
        # Logic Apps
        if "microsoft.logic/workflows" in resource_type:
            self._extract_from_logic_app(resource)
        # Function Apps / Web Apps
        elif "microsoft.web/sites" in resource_type:
            self._extract_from_web_app(resource)
        # Data Factory
        elif "microsoft.datafactory/factories" in resource_type:
            self._extract_from_data_factory(resource)
        # Synapse Workspace
        elif "microsoft.synapse/workspaces" in resource_type:
            self._extract_from_synapse(resource)

    def _extract_from_logic_app(self, resource: Dict[str, Any]) -> None:
        """Extract identity references from Logic Apps."""
        properties = resource.get("properties", {})
        if not isinstance(properties, dict):
            return

        # Check workflow parameters for managed identity connections
        parameters = properties.get("parameters", {})
        if isinstance(parameters, dict):
            for param_name, param_value in parameters.items():
                if (
                    isinstance(param_value, dict)
                    and param_value.get("type") == "ManagedServiceIdentity"
                ):
                    # This indicates the workflow uses managed identity
                    identity = resource.get("identity")
                    if identity:
                        self._extract_from_identity_property(identity)

    def _extract_from_web_app(self, resource: Dict[str, Any]) -> None:
        """Extract identity references from Web Apps/Function Apps."""
        properties = resource.get("properties", {})
        if not isinstance(properties, dict):
            return

        # Check site config for managed identity settings
        site_config = properties.get("siteConfig", {})
        if isinstance(site_config, dict):
            # Check if managed identity authentication is enabled
            managed_identity_enabled = site_config.get("managedServiceIdentityId")
            if managed_identity_enabled:
                # Extract from the identity property
                identity = resource.get("identity")
                if identity:
                    self._extract_from_identity_property(identity)

    def _extract_from_data_factory(self, resource: Dict[str, Any]) -> None:
        """Extract identity references from Data Factory."""
        properties = resource.get("properties", {})
        if not isinstance(properties, dict):
            return

        # Data Factory uses 'identity' at the properties level sometimes
        identity = properties.get("identity")
        if identity:
            self._extract_from_identity_property(identity)

    def _extract_from_synapse(self, resource: Dict[str, Any]) -> None:
        """Extract identity references from Synapse Workspaces."""
        properties = resource.get("properties", {})
        if not isinstance(properties, dict):
            return

        # Synapse managed identity
        managed_identity = properties.get("managedResourceGroupName")
        if managed_identity:
            # Extract from the identity property
            identity = resource.get("identity")
            if identity:
                self._extract_from_identity_property(identity)

    def _is_valid_guid(self, value: str) -> bool:
        """
        Check if a string is a valid GUID format.

        Args:
            value: String to check

        Returns:
            True if valid GUID format, False otherwise
        """
        if not value or not isinstance(value, str):
            return False

        # Basic GUID format check (8-4-4-4-12)
        parts = value.split("-")
        if len(parts) != 5:
            return False

        expected_lengths = [8, 4, 4, 4, 12]
        for part, expected_length in zip(parts, expected_lengths):
            if len(part) != expected_length:
                return False
            try:
                int(part, 16)  # Check if valid hexadecimal
            except ValueError:
                return False

        # Don't include empty GUIDs
        if value == "00000000-0000-0000-0000-000000000000":
            return False

        return True
