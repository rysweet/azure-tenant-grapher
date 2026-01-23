"""Service for collecting referenced resources during filtered imports.

When filtering by subscription or resource group, this service automatically includes
resources that are referenced by the filtered resources but fall outside the filter scope.

Referenced resources include:
- User-assigned managed identities in different resource groups
- System-assigned managed identity details
- RBAC principals (users, groups, service principals)

Issue #228: Subscription and Resource Group Filtering with Referenced Resources
"""

import logging
import re
from typing import Any, Dict, List, Optional, Set

from src.models.filter_config import FilterConfig

logger = logging.getLogger(__name__)


class ReferencedResourceCollector:
    """Collects referenced resources for filtered imports.

    This service ensures complete and accurate graph representation when using
    subscription or resource group filtering by automatically including resources
    that are referenced by filtered resources but fall outside the filter scope.
    """

    def __init__(
        self,
        discovery_service: Any,
        identity_resolver: Any,
        aad_graph_service: Optional[Any] = None,
    ):
        """
        Initialize the referenced resource collector.

        Args:
            discovery_service: AzureDiscoveryService for fetching resources
            identity_resolver: ManagedIdentityResolver for resolving identity details
            aad_graph_service: Optional AADGraphService for fetching RBAC principals
        """
        self.discovery_service = discovery_service
        self.identity_resolver = identity_resolver
        self.aad_graph_service = aad_graph_service
        logger.debug("ReferencedResourceCollector initialized")

    async def collect_referenced_resources(
        self, filtered_resources: List[Dict[str, Any]], filter_config: FilterConfig
    ) -> List[Dict[str, Any]]:
        """
        Collect all referenced resources that should be included with filtered resources.

        Args:
            filtered_resources: List of resources that passed the filter
            filter_config: Filter configuration used for filtering

        Returns:
            List of referenced resources to add to the filtered set
        """
        # Early return if reference inclusion is disabled
        if not filter_config.include_referenced_resources:
            logger.info("Referenced resource inclusion disabled by filter config")
            return []

        # Early return if no filters are active (unfiltered build)
        if not filter_config.has_filters():
            logger.debug("No filters active, skipping referenced resource collection")
            return []

        logger.info("=" * 70)
        logger.info("Collecting referenced resources for filtered import...")
        logger.info("=" * 70)

        referenced_resources = []

        # 1. Extract identity references from filtered resources
        identity_refs = self._extract_identity_references(filtered_resources)
        logger.info(
            f"Extracted {len(identity_refs)} identity references from filtered resources"
        )

        # 2. Fetch user-assigned managed identities
        if identity_refs:
            user_assigned_identities = await self._fetch_user_assigned_identities(
                identity_refs, filter_config
            )
            referenced_resources.extend(user_assigned_identities)
            logger.info(
                f"Fetched {len(user_assigned_identities)} user-assigned managed identities"
            )

        # 3. Extract RBAC principal IDs
        principal_ids = self._extract_rbac_principal_ids(filtered_resources)
        total_principals = sum(len(ids) for ids in principal_ids.values())
        logger.info(
            f"Extracted {total_principals} RBAC principal IDs from filtered resources"
        )

        # 4. Fetch RBAC principals from AAD
        if total_principals > 0 and self.aad_graph_service:
            rbac_principals = await self._fetch_rbac_principals(principal_ids)
            referenced_resources.extend(rbac_principals)
            logger.info(f"Fetched {len(rbac_principals)} RBAC principals from AAD")
        elif total_principals > 0:
            logger.warning(
                "RBAC principals found but AAD Graph Service not available - principals will not be included"
            )

        logger.info("=" * 70)
        logger.info(
            f"Referenced resource collection complete: {len(referenced_resources)} resources added"
        )
        logger.info("=" * 70)

        return referenced_resources

    def _extract_identity_references(self, resources: List[Dict[str, Any]]) -> Set[str]:
        """
        Extract identity references from resources.

        Extracts both system-assigned identity principal IDs and user-assigned
        identity resource IDs.

        Args:
            resources: List of resources to extract identities from

        Returns:
            Set of identity IDs (principal IDs or resource IDs)
        """
        identity_refs: Set[str] = set()

        for resource in resources:
            identity = resource.get("identity")
            if not identity or not isinstance(identity, dict):
                continue

            identity_type = identity.get("type", "")

            # Extract system-assigned identity principal ID
            if "SystemAssigned" in identity_type:
                principal_id = identity.get("principalId")
                if principal_id:
                    identity_refs.add(principal_id)
                    logger.debug(f"Found system-assigned identity: {principal_id}")

            # Extract user-assigned identity resource IDs
            if "UserAssigned" in identity_type:
                user_assigned_identities = identity.get("userAssignedIdentities", {})
                if isinstance(user_assigned_identities, dict):
                    for identity_resource_id in user_assigned_identities.keys():
                        identity_refs.add(identity_resource_id)
                        logger.debug(
                            f"Found user-assigned identity: {identity_resource_id}"
                        )

        return identity_refs

    def _extract_rbac_principal_ids(
        self, resources: List[Dict[str, Any]]
    ) -> Dict[str, Set[str]]:
        """
        Extract RBAC principal IDs from resources.

        Handles multiple RBAC formats:
        - roleAssignments array (common format)
        - accessPolicies array (KeyVault format)

        Args:
            resources: List of resources to extract RBAC principals from

        Returns:
            Dictionary with keys 'users', 'groups', 'service_principals'
            and sets of principal IDs as values
        """
        principal_ids: Dict[str, Set[str]] = {
            "users": set(),
            "groups": set(),
            "service_principals": set(),
        }

        for resource in resources:
            properties = resource.get("properties", {})
            if not isinstance(properties, dict):
                continue

            # Format 1: roleAssignments (most common)
            role_assignments = properties.get("roleAssignments", [])
            if isinstance(role_assignments, list):
                for assignment in role_assignments:
                    if not isinstance(assignment, dict):
                        continue

                    principal_id = assignment.get("principalId")
                    principal_type = assignment.get("principalType", "").lower()

                    if principal_id:
                        if "user" in principal_type:
                            principal_ids["users"].add(principal_id)
                        elif "group" in principal_type:
                            principal_ids["groups"].add(principal_id)
                        elif "serviceprincipal" in principal_type:
                            principal_ids["service_principals"].add(principal_id)

            # Format 2: accessPolicies (KeyVault format)
            access_policies = properties.get("accessPolicies", [])
            if isinstance(access_policies, list):
                for policy in access_policies:
                    if not isinstance(policy, dict):
                        continue

                    object_id = policy.get("objectId")
                    object_type = policy.get("objectType", "").lower()

                    if object_id:
                        if "user" in object_type:
                            principal_ids["users"].add(object_id)
                        elif "group" in object_type:
                            principal_ids["groups"].add(object_id)
                        elif "serviceprincipal" in object_type:
                            principal_ids["service_principals"].add(object_id)

        return principal_ids

    async def _fetch_user_assigned_identities(
        self, identity_resource_ids: Set[str], filter_config: FilterConfig
    ) -> List[Dict[str, Any]]:
        """
        Fetch user-assigned managed identities by resource ID.

        User-assigned identities may be in resource groups or subscriptions outside
        the filter scope. This method fetches them regardless of filter.

        Args:
            identity_resource_ids: Set of user-assigned identity resource IDs
            filter_config: Filter configuration (for subscription context)

        Returns:
            List of user-assigned identity resources
        """
        # Filter to only user-assigned identity resource IDs
        ua_identity_ids = {
            rid
            for rid in identity_resource_ids
            if "/providers/Microsoft.ManagedIdentity/userAssignedIdentities/" in rid
        }

        if not ua_identity_ids:
            return []

        fetched_identities: List[Dict[str, Any]] = []

        # Extract subscription IDs from identity resource IDs
        subscriptions_to_query = set()
        for identity_id in ua_identity_ids:
            # Parse subscription ID from resource ID
            # Format: /subscriptions/{sub-id}/resourceGroups/{rg}/providers/...
            match = re.match(r"/subscriptions/([^/]+)/", identity_id)
            if match:
                subscriptions_to_query.add(match.group(1))

        # Fetch identities from each subscription
        for sub_id in subscriptions_to_query:
            try:
                # Query for user-assigned identity resources
                # Note: We bypass the filter here intentionally - these are referenced resources
                identity_resources = await self.discovery_service.discover_resources_in_subscription(
                    subscription_id=sub_id,
                    resource_type_filter="Microsoft.ManagedIdentity/userAssignedIdentities",
                )

                # Filter to only the identities we're looking for
                for identity_resource in identity_resources:
                    resource_id = identity_resource.get("id")
                    if resource_id in ua_identity_ids:
                        fetched_identities.append(identity_resource)
                        logger.debug(f"Fetched user-assigned identity: {resource_id}")

            except Exception as e:
                logger.warning(
                    f"Failed to fetch user-assigned identities from subscription {sub_id}: {e}"
                )
                continue

        # Check for identities that couldn't be fetched
        fetched_ids = {r.get("id") for r in fetched_identities}
        missing_ids = ua_identity_ids - fetched_ids
        if missing_ids:
            logger.warning(
                f"Could not fetch {len(missing_ids)} user-assigned identities (may be inaccessible or deleted)"
            )
            for missing_id in missing_ids:
                logger.debug(f"Missing identity: {missing_id}")

        return fetched_identities

    async def _fetch_rbac_principals(
        self, principal_ids: Dict[str, Set[str]]
    ) -> List[Dict[str, Any]]:
        """
        Fetch RBAC principals (users, groups, service principals) from AAD.

        Args:
            principal_ids: Dictionary with 'users', 'groups', 'service_principals' keys

        Returns:
            List of principal resources in graph format
        """
        if not self.aad_graph_service:
            logger.warning(
                "AAD Graph Service not available - cannot fetch RBAC principals"
            )
            return []

        rbac_resources: List[Dict[str, Any]] = []

        try:
            # Fetch users
            if principal_ids["users"]:
                logger.info(f"Fetching {len(principal_ids['users'])} users from AAD...")
                users = await self.aad_graph_service.get_users_by_ids(
                    principal_ids["users"]
                )
                for user in users:
                    rbac_resources.append(
                        {
                            "id": f"/users/{user['id']}",
                            "name": user.get("displayName", user["id"]),
                            "type": "Microsoft.Graph/users",
                            "location": "global",
                            "properties": user,
                            "subscription_id": None,  # AAD resources are tenant-level
                            "resource_group": None,
                            "tags": {},
                        }
                    )
                logger.info(f"Fetched {len(users)} users")

            # Fetch groups
            if principal_ids["groups"]:
                logger.info(
                    f"Fetching {len(principal_ids['groups'])} groups from AAD..."
                )
                groups = await self.aad_graph_service.get_groups_by_ids(
                    principal_ids["groups"]
                )
                for group in groups:
                    rbac_resources.append(
                        {
                            "id": f"/groups/{group['id']}",
                            "name": group.get("displayName", group["id"]),
                            "type": "Microsoft.Graph/groups",
                            "location": "global",
                            "properties": group,
                            "subscription_id": None,
                            "resource_group": None,
                            "tags": {},
                        }
                    )
                logger.info(f"Fetched {len(groups)} groups")

            # Fetch service principals
            if principal_ids["service_principals"]:
                logger.info(
                    f"Fetching {len(principal_ids['service_principals'])} service principals from AAD..."
                )
                sps = await self.aad_graph_service.get_service_principals_by_ids(
                    principal_ids["service_principals"]
                )
                for sp in sps:
                    rbac_resources.append(
                        {
                            "id": f"/servicePrincipals/{sp['id']}",
                            "name": sp.get("displayName", sp["id"]),
                            "type": "Microsoft.Graph/servicePrincipals",
                            "location": "global",
                            "properties": sp,
                            "subscription_id": None,
                            "resource_group": None,
                            "tags": {},
                        }
                    )
                logger.info(f"Fetched {len(sps)} service principals")

        except Exception as e:
            logger.error(f"Error fetching RBAC principals from AAD: {e}")
            # Continue with partial results rather than failing completely

        return rbac_resources
