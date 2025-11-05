"""Automatic identity mapping between Azure tenants for cross-tenant IaC generation.

This module provides the AutoIdentityMapper class that automatically matches identities
(users, groups, service principals) between source and target tenants to enable
seamless cross-tenant IaC generation without manual configuration.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from azure.identity import ClientSecretCredential
from msgraph.graph_service_client import GraphServiceClient

logger = logging.getLogger(__name__)


class AADGraphService:
    """Lightweight wrapper around Microsoft Graph API for fetching identities from a specific tenant."""

    def __init__(
        self,
        tenant_id: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ):
        """Initialize Graph service for a specific tenant.

        Args:
            tenant_id: Azure AD tenant ID
            client_id: Optional client ID (defaults to AZURE_CLIENT_ID env var)
            client_secret: Optional client secret (defaults to AZURE_CLIENT_SECRET env var)
        """
        self.tenant_id = tenant_id

        # Get credentials from parameters or environment
        self.client_id = client_id or os.environ.get("AZURE_CLIENT_ID")
        self.client_secret = client_secret or os.environ.get("AZURE_CLIENT_SECRET")

        if not self.client_id or not self.client_secret:
            raise ValueError(
                "Missing Azure credentials. Provide client_id and client_secret or set "
                "AZURE_CLIENT_ID and AZURE_CLIENT_SECRET environment variables."
            )

        # Validate tenant ID format (basic check)
        if not tenant_id or len(tenant_id) < 10:
            raise ValueError(f"Invalid tenant ID: {tenant_id}")

        # Initialize Graph client
        credential = ClientSecretCredential(
            tenant_id=self.tenant_id,
            client_id=self.client_id,
            client_secret=self.client_secret,
        )
        self.client = GraphServiceClient(
            credentials=credential, scopes=["https://graph.microsoft.com/.default"]
        )

    async def get_users(self) -> List[Dict[str, Any]]:
        """Fetch all users from the tenant."""
        users = []

        try:
            users_page = await self.client.users.get()

            if users_page and users_page.value:
                for user in users_page.value:
                    users.append(
                        {
                            "id": user.id,
                            "displayName": user.display_name,
                            "userPrincipalName": user.user_principal_name,
                            "mail": user.mail,
                        }
                    )

            # Handle pagination
            while users_page and users_page.odata_next_link:
                users_page = await self.client.users.with_url(
                    users_page.odata_next_link
                ).get()

                if users_page and users_page.value:
                    for user in users_page.value:
                        users.append(
                            {
                                "id": user.id,
                                "displayName": user.display_name,
                                "userPrincipalName": user.user_principal_name,
                                "mail": user.mail,
                            }
                        )

            logger.info(
                f"Fetched {len(users)} users from tenant {self.tenant_id[:8]}..."
            )
            return users

        except Exception as e:
            logger.error(f"Failed to fetch users from tenant {self.tenant_id}: {e}")
            raise

    async def get_groups(self) -> List[Dict[str, Any]]:
        """Fetch all groups from the tenant."""
        groups = []

        try:
            groups_page = await self.client.groups.get()

            if groups_page and groups_page.value:
                for group in groups_page.value:
                    groups.append(
                        {
                            "id": group.id,
                            "displayName": group.display_name,
                            "mail": group.mail,
                            "description": group.description,
                        }
                    )

            # Handle pagination
            while groups_page and groups_page.odata_next_link:
                groups_page = await self.client.groups.with_url(
                    groups_page.odata_next_link
                ).get()

                if groups_page and groups_page.value:
                    for group in groups_page.value:
                        groups.append(
                            {
                                "id": group.id,
                                "displayName": group.display_name,
                                "mail": group.mail,
                                "description": group.description,
                            }
                        )

            logger.info(
                f"Fetched {len(groups)} groups from tenant {self.tenant_id[:8]}..."
            )
            return groups

        except Exception as e:
            logger.error(f"Failed to fetch groups from tenant {self.tenant_id}: {e}")
            raise

    async def get_service_principals(self) -> List[Dict[str, Any]]:
        """Fetch all service principals from the tenant."""
        service_principals = []

        try:
            sp_page = await self.client.service_principals.get()

            if sp_page and sp_page.value:
                for sp in sp_page.value:
                    service_principals.append(
                        {
                            "id": sp.id,
                            "displayName": sp.display_name,
                            "appId": sp.app_id,
                            "servicePrincipalType": sp.service_principal_type,
                        }
                    )

            # Handle pagination
            while sp_page and sp_page.odata_next_link:
                sp_page = await self.client.service_principals.with_url(
                    sp_page.odata_next_link
                ).get()

                if sp_page and sp_page.value:
                    for sp in sp_page.value:
                        service_principals.append(
                            {
                                "id": sp.id,
                                "displayName": sp.display_name,
                                "appId": sp.app_id,
                                "servicePrincipalType": sp.service_principal_type,
                            }
                        )

            logger.info(
                f"Fetched {len(service_principals)} service principals from tenant {self.tenant_id[:8]}..."
            )
            return service_principals

        except Exception as e:
            logger.error(
                f"Failed to fetch service principals from tenant {self.tenant_id}: {e}"
            )
            raise


class AutoIdentityMapper:
    """Automatically maps identities between source and target tenants.

    This class discovers identities in both tenants and creates mappings based on
    matching attributes with different confidence levels:
    - Very high: Service Principal appId match (globally unique)
    - High: User email or UPN match
    - Medium: Display name match (requires manual verification)
    """

    def __init__(self):
        """Initialize the auto identity mapper."""
        pass

    async def create_mapping(
        self,
        source_tenant_id: str,
        target_tenant_id: str,
        manual_mapping_file: Optional[Path] = None,
        neo4j_driver: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Create identity mappings between source and target tenants.

        Args:
            source_tenant_id: Source Azure AD tenant ID
            target_tenant_id: Target Azure AD tenant ID
            manual_mapping_file: Optional path to manual mapping file (takes precedence)
            neo4j_driver: Optional Neo4j driver for discovering referenced identities

        Returns:
            Mapping dictionary with flat structure:
            {
                "users": {
                    "source_id": {
                        "target_object_id": "target_id",
                        "source_upn": "...",
                        "target_upn": "...",
                        "match_method": "email|upn|displayName",
                        "match_confidence": "very_high|high|medium|low|none|manual",
                        "notes": "..."
                    }
                },
                "groups": {...},
                "service_principals": {...}
            }

            Note: When saved to file via save_mapping(), it's wrapped in proper format
            with tenant_mapping and identity_mappings sections.
        """
        logger.info(
            f"Creating automatic identity mapping: {source_tenant_id[:8]}... -> {target_tenant_id[:8]}..."
        )

        # Store tenant IDs for later use
        self._source_tenant_id = source_tenant_id
        self._target_tenant_id = target_tenant_id

        # Load manual mappings first (if provided)
        manual_mappings = self._load_manual_mappings(manual_mapping_file)

        # Initialize Graph services for both tenants
        source_service = AADGraphService(tenant_id=source_tenant_id)
        target_service = AADGraphService(tenant_id=target_tenant_id)

        # Fetch identities from both tenants
        import asyncio

        logger.info("Fetching identities from source and target tenants...")
        (
            source_users,
            target_users,
            source_groups,
            target_groups,
            source_sps,
            target_sps,
        ) = await asyncio.gather(
            source_service.get_users(),
            target_service.get_users(),
            source_service.get_groups(),
            target_service.get_groups(),
            source_service.get_service_principals(),
            target_service.get_service_principals(),
        )

        # Create mappings
        user_mappings = self._map_users(source_users, target_users, manual_mappings)
        group_mappings = self._map_groups(source_groups, target_groups, manual_mappings)
        sp_mappings = self._map_service_principals(
            source_sps, target_sps, manual_mappings
        )

        # Build result with nested structure (matches file format)
        result = {
            "tenant_mapping": {
                "source_tenant_id": source_tenant_id,
                "target_tenant_id": target_tenant_id,
            },
            "identity_mappings": {
                "users": user_mappings,
                "groups": group_mappings,
                "service_principals": sp_mappings,
            },
        }

        # Also add flat accessors for backward compatibility
        result["users"] = user_mappings
        result["groups"] = group_mappings
        result["service_principals"] = sp_mappings

        # Log summary
        logger.info(
            f"Created mappings: {len(user_mappings)} users, {len(group_mappings)} groups, "
            f"{len(sp_mappings)} service principals"
        )

        return result

    def _load_manual_mappings(
        self, manual_mapping_file: Optional[Path]
    ) -> Dict[str, Any]:
        """Load manual mappings from file if provided."""
        if not manual_mapping_file or not Path(manual_mapping_file).exists():
            return {"users": {}, "groups": {}, "service_principals": {}}

        try:
            with open(manual_mapping_file) as f:
                data = json.load(f)
                return data.get("identity_mappings", {})
        except Exception as e:
            logger.warning(f"Failed to load manual mapping file: {e}")
            return {"users": {}, "groups": {}, "service_principals": {}}

    def _map_users(
        self,
        source_users: List[Dict[str, Any]],
        target_users: List[Dict[str, Any]],
        manual_mappings: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        """Map users between tenants with priority: email > UPN > displayName."""
        mappings = {}
        manual_user_mappings = manual_mappings.get("users", {})

        # Build target lookup indexes
        target_by_email = {
            u["mail"]: u for u in target_users if u.get("mail") is not None
        }
        {
            u["userPrincipalName"]: u
            for u in target_users
            if u.get("userPrincipalName") is not None
        }
        target_by_upn_username = {}
        for u in target_users:
            upn = u.get("userPrincipalName")
            if upn and "@" in upn:
                username = upn.split("@")[0]
                target_by_upn_username[username] = u

        target_by_display_name = {
            u["displayName"]: u
            for u in target_users
            if u.get("displayName") is not None
        }

        for source_user in source_users:
            source_id = source_user["id"]

            # Check manual override first
            if source_id in manual_user_mappings:
                mappings[source_id] = manual_user_mappings[source_id]
                continue

            # Try matching by email (high confidence)
            email = source_user.get("mail")
            if email and email in target_by_email:
                target_user = target_by_email[email]
                mappings[source_id] = {
                    "target_object_id": target_user["id"],
                    "source_upn": source_user.get("userPrincipalName"),
                    "target_upn": target_user.get("userPrincipalName"),
                    "match_method": "email",
                    "match_confidence": "high",
                    "notes": f"Matched by email: {email}",
                }
                continue

            # Try matching by UPN username (high confidence - but only if email didn't work)
            # Skip UPN matching if user has no email (email takes priority)
            upn = source_user.get("userPrincipalName")
            if upn and "@" in upn and email:  # Only try UPN if email exists
                username = upn.split("@")[0]
                if username in target_by_upn_username:
                    target_user = target_by_upn_username[username]
                    mappings[source_id] = {
                        "target_object_id": target_user["id"],
                        "source_upn": source_user.get("userPrincipalName"),
                        "target_upn": target_user.get("userPrincipalName"),
                        "match_method": "upn",
                        "match_confidence": "high",
                        "notes": f"Matched by UPN username: {username}",
                    }
                    continue

            # Try matching by display name (lower confidence)
            display_name = source_user.get("displayName")
            if display_name and display_name in target_by_display_name:
                target_user = target_by_display_name[display_name]
                mappings[source_id] = {
                    "target_object_id": target_user["id"],
                    "source_upn": source_user.get("userPrincipalName"),
                    "target_upn": target_user.get("userPrincipalName"),
                    "match_method": "displayName",
                    "match_confidence": "medium",
                    "notes": f"Matched by display name (verify manually): {display_name}",
                }
                continue

            # No match found
            logger.warning(
                f"No match found for user: {source_user.get('displayName')} "
                f"({source_user.get('userPrincipalName')})"
            )
            mappings[source_id] = {
                "target_object_id": "MANUAL_INPUT_REQUIRED",
                "source_upn": source_user.get("userPrincipalName"),
                "target_upn": None,
                "match_method": "none",
                "match_confidence": "none",
                "notes": "No match found - manual mapping required",
            }

        return mappings

    def _map_groups(
        self,
        source_groups: List[Dict[str, Any]],
        target_groups: List[Dict[str, Any]],
        manual_mappings: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        """Map groups between tenants."""
        mappings = {}
        manual_group_mappings = manual_mappings.get("groups", {})

        # Build target lookup indexes
        target_by_display_name = {
            g["displayName"]: g
            for g in target_groups
            if g.get("displayName") is not None
        }
        target_by_mail = {
            g["mail"]: g for g in target_groups if g.get("mail") is not None
        }

        for source_group in source_groups:
            source_id = source_group["id"]

            # Check manual override first
            if source_id in manual_group_mappings:
                mappings[source_id] = manual_group_mappings[source_id]
                continue

            # Try matching by mail
            mail = source_group.get("mail")
            if mail and mail in target_by_mail:
                target_group = target_by_mail[mail]
                mappings[source_id] = {
                    "target_object_id": target_group["id"],
                    "source_display_name": source_group.get("displayName"),
                    "target_display_name": target_group.get("displayName"),
                    "match_method": "mail",
                    "match_confidence": "high",
                    "notes": f"Matched by mail: {mail}",
                }
                continue

            # Try matching by display name
            display_name = source_group.get("displayName")
            if display_name and display_name in target_by_display_name:
                target_group = target_by_display_name[display_name]
                mappings[source_id] = {
                    "target_object_id": target_group["id"],
                    "source_display_name": source_group.get("displayName"),
                    "target_display_name": target_group.get("displayName"),
                    "match_method": "displayName",
                    "match_confidence": "medium",
                    "notes": f"Matched by display name (verify manually): {display_name}",
                }
                continue

            # No match found
            logger.warning(
                f"No match found for group: {source_group.get('displayName')}"
            )
            mappings[source_id] = {
                "target_object_id": "MANUAL_INPUT_REQUIRED",
                "source_display_name": source_group.get("displayName"),
                "target_display_name": None,
                "match_method": "none",
                "match_confidence": "none",
                "notes": "No match found - manual mapping required",
            }

        return mappings

    def _map_service_principals(
        self,
        source_sps: List[Dict[str, Any]],
        target_sps: List[Dict[str, Any]],
        manual_mappings: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        """Map service principals between tenants (appId is globally unique)."""
        mappings = {}
        manual_sp_mappings = manual_mappings.get("service_principals", {})

        # Build target lookup by appId (globally unique identifier)
        target_by_app_id = {
            sp["appId"]: sp for sp in target_sps if sp.get("appId") is not None
        }
        target_by_display_name = {
            sp["displayName"]: sp
            for sp in target_sps
            if sp.get("displayName") is not None
        }

        for source_sp in source_sps:
            source_id = source_sp["id"]

            # Check manual override first
            if source_id in manual_sp_mappings:
                mappings[source_id] = manual_sp_mappings[source_id]
                continue

            # Try matching by appId (very high confidence - globally unique)
            app_id = source_sp.get("appId")
            if app_id and app_id in target_by_app_id:
                target_sp = target_by_app_id[app_id]
                mappings[source_id] = {
                    "target_object_id": target_sp["id"],
                    "source_app_id": app_id,
                    "target_app_id": app_id,
                    "match_method": "appId",
                    "match_confidence": "very_high",
                    "notes": f"Matched by appId: {app_id}",
                }
                continue

            # Try matching by display name (fallback)
            display_name = source_sp.get("displayName")
            if display_name and display_name in target_by_display_name:
                target_sp = target_by_display_name[display_name]
                mappings[source_id] = {
                    "target_object_id": target_sp["id"],
                    "source_app_id": source_sp.get("appId"),
                    "target_app_id": target_sp.get("appId"),
                    "match_method": "displayName",
                    "match_confidence": "low",
                    "notes": f"Matched by display name (verify manually): {display_name}",
                }
                continue

            # No match found
            logger.warning(
                f"No match found for service principal: {source_sp.get('displayName')} "
                f"(appId: {source_sp.get('appId')})"
            )
            mappings[source_id] = {
                "target_object_id": "MANUAL_INPUT_REQUIRED",
                "source_app_id": source_sp.get("appId"),
                "target_app_id": None,
                "match_method": "none",
                "match_confidence": "none",
                "notes": "No match found - manual mapping required",
            }

        return mappings

    def save_mapping(self, mapping: Dict[str, Any], output_file: Path) -> None:
        """Save mapping to JSON file in EntraIdTranslator format.

        Args:
            mapping: Mapping dictionary from create_mapping()
            output_file: Path to output JSON file
        """
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Remove flat accessors before saving (keep only nested structure)
        file_format = {
            "tenant_mapping": mapping.get("tenant_mapping", {}),
            "identity_mappings": mapping.get("identity_mappings", {}),
        }

        with open(output_file, "w") as f:
            json.dump(file_format, f, indent=2)

        logger.info(f"Saved identity mapping to {output_file}")
