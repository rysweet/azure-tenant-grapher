import logging
import os
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set

from azure.identity import ClientSecretCredential
from kiota_abstractions.base_request_configuration import RequestConfiguration
from msgraph.generated.groups.groups_request_builder import GroupsRequestBuilder
from msgraph.generated.models.o_data_errors.o_data_error import ODataError
from msgraph.generated.service_principals.service_principals_request_builder import (
    ServicePrincipalsRequestBuilder,
)
from msgraph.generated.users.users_request_builder import UsersRequestBuilder
from msgraph.graph_service_client import GraphServiceClient

logger = logging.getLogger(__name__)


class AADGraphService:
    """
    Service for fetching Azure AD users and groups from Microsoft Graph API.
    Uses Microsoft Graph SDK with MSAL authentication.
    Reads credentials from environment variables:
      - AZURE_CLIENT_ID
      - AZURE_CLIENT_SECRET
      - AZURE_TENANT_ID
    """

    def __init__(self, use_mock: bool = False):
        self.use_mock = use_mock
        self.client: Optional[GraphServiceClient] = None

        if not use_mock:
            self._initialize_graph_client()

    def _initialize_graph_client(self) -> None:
        """Initialize Microsoft Graph client with MSAL authentication."""
        tenant_id = os.environ.get("AZURE_TENANT_ID")
        client_id = os.environ.get("AZURE_CLIENT_ID")
        client_secret = os.environ.get("AZURE_CLIENT_SECRET")

        if not all([tenant_id, client_id, client_secret]):
            raise RuntimeError(
                "Missing one or more required Azure AD credentials in environment variables: "
                "AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET"
            )

        # Create credential using MSAL
        if tenant_id is None or client_id is None or client_secret is None:
            raise RuntimeError(
                "Missing one or more required Azure AD credentials in environment variables: "
                "AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET"
            )
        credential = ClientSecretCredential(
            tenant_id=tenant_id, client_id=client_id, client_secret=client_secret
        )

        # Initialize Graph client with credential
        scopes = ["https://graph.microsoft.com/.default"]
        self.client = GraphServiceClient(credentials=credential, scopes=scopes)

    async def _retry_with_backoff(
        self, operation: Callable[[], Awaitable[Any]], max_retries: int = 5
    ) -> Any:
        """Execute operation with exponential backoff retry logic."""
        for attempt in range(max_retries):
            try:
                return await operation()
            except ODataError as e:
                status_code = getattr(e, "response_status_code", None)
                if status_code == 429:
                    # Rate limited - use fixed retry time
                    sleep_time = 2
                    logger.warning(
                        f"Rate limited, retrying after {sleep_time} seconds (attempt {attempt + 1})"
                    )
                    time.sleep(sleep_time)
                    continue
                elif status_code is not None and 500 <= status_code < 600:
                    # Server error - exponential backoff
                    sleep_time = 2**attempt
                    logger.warning(
                        f"Server error {e.response_status_code}, retrying after {sleep_time} seconds (attempt {attempt + 1})"
                    )
                    time.sleep(sleep_time)
                    continue
                else:
                    # Other error - don't retry
                    logger.error(f"Non-retryable error: {e}")
                    raise
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Operation failed after {max_retries} attempts: {e}")
                    raise
                sleep_time = 2**attempt
                logger.warning(
                    f"Unexpected error, retrying after {sleep_time} seconds (attempt {attempt + 1}): {e}"
                )
                time.sleep(sleep_time)

    async def get_users(self) -> List[Dict[str, Any]]:
        """
        Fetches users from Microsoft Graph API using SDK, handling pagination and throttling.
        Returns a list of user dictionaries.
        """
        if self.use_mock:
            return [
                {"id": "mock-user-1", "displayName": "Mock User One"},
                {"id": "mock-user-2", "displayName": "Mock User Two"},
            ]

        if not self.client:
            raise RuntimeError("Graph client not initialized")

        async def fetch_users():
            users = []

            # Configure request to get all pages
            query_params = UsersRequestBuilder.UsersRequestBuilderGetQueryParameters(
                select=["id", "displayName", "userPrincipalName", "mail"]
            )
            request_config = RequestConfiguration(query_parameters=query_params)

            # Get first page
            if not self.client:
                raise RuntimeError("Graph client not initialized")
            users_page = await self.client.users.get(
                request_configuration=request_config
            )

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
                logger.info(
                    f"Fetching next page of users (current count: {len(users)})"
                )
                if not self.client:
                    raise RuntimeError("Graph client not initialized")
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

            logger.info(f"Fetched {len(users)} users from Microsoft Graph")
            return users

        result = await self._retry_with_backoff(fetch_users)
        return result if result is not None else []

    async def get_users_by_ids(self, user_ids: Set[str]) -> List[Dict[str, Any]]:
        """
        Fetches specific users by their IDs from Microsoft Graph API.
        
        Args:
            user_ids: Set of user IDs to fetch
            
        Returns:
            List of user dictionaries for the specified IDs
        """
        if not user_ids:
            return []
            
        if self.use_mock:
            # Return mock users matching the requested IDs
            mock_users = [
                {"id": "mock-user-1", "displayName": "Mock User One"},
                {"id": "mock-user-2", "displayName": "Mock User Two"},
            ]
            return [u for u in mock_users if u["id"] in user_ids]
            
        if not self.client:
            raise RuntimeError("Graph client not initialized")
            
        users = []
        
        # Fetch each user individually (batch requests could be optimized later)
        for user_id in user_ids:
            try:
                async def fetch_user():
                    if not self.client:
                        raise RuntimeError("Graph client not initialized")
                    user = await self.client.users.by_user_id(user_id).get()
                    if user:
                        return {
                            "id": user.id,
                            "displayName": user.display_name,
                            "userPrincipalName": user.user_principal_name,
                            "mail": user.mail,
                        }
                    return None
                    
                user_data = await self._retry_with_backoff(fetch_user)
                if user_data:
                    users.append(user_data)
            except ODataError as e:
                # User not found or no permissions - log and continue
                logger.warning(f"Could not fetch user {user_id}: {e}")
                continue
                
        logger.info(f"Fetched {len(users)} users out of {len(user_ids)} requested")
        return users

    async def get_groups(self) -> List[Dict[str, Any]]:
        """
        Fetches groups from Microsoft Graph API using SDK, handling pagination and throttling.
        Returns a list of group dictionaries.
        """
        if self.use_mock:
            return [
                {"id": "mock-group-1", "displayName": "Mock Group One"},
                {"id": "mock-group-2", "displayName": "Mock Group Two"},
            ]

        if not self.client:
            raise RuntimeError("Graph client not initialized")

        async def fetch_groups():
            groups = []

            # Configure request to get all pages
            query_params = GroupsRequestBuilder.GroupsRequestBuilderGetQueryParameters(
                select=["id", "displayName", "mail", "description"]
            )
            request_config = RequestConfiguration(query_parameters=query_params)

            # Get first page
            if not self.client:
                raise RuntimeError("Graph client not initialized")
            groups_page = await self.client.groups.get(
                request_configuration=request_config
            )

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
                logger.info(
                    f"Fetching next page of groups (current count: {len(groups)})"
                )
                if not self.client:
                    raise RuntimeError("Graph client not initialized")
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

            logger.info(f"Fetched {len(groups)} groups from Microsoft Graph")
            return groups

        result = await self._retry_with_backoff(fetch_groups)
        return result if result is not None else []

    async def get_groups_by_ids(self, group_ids: Set[str]) -> List[Dict[str, Any]]:
        """
        Fetches specific groups by their IDs from Microsoft Graph API.
        
        Args:
            group_ids: Set of group IDs to fetch
            
        Returns:
            List of group dictionaries for the specified IDs
        """
        if not group_ids:
            return []
            
        if self.use_mock:
            # Return mock groups matching the requested IDs
            mock_groups = [
                {"id": "mock-group-1", "displayName": "Mock Group One"},
                {"id": "mock-group-2", "displayName": "Mock Group Two"},
            ]
            return [g for g in mock_groups if g["id"] in group_ids]
            
        if not self.client:
            raise RuntimeError("Graph client not initialized")
            
        groups = []
        
        # Fetch each group individually
        for group_id in group_ids:
            try:
                async def fetch_group():
                    if not self.client:
                        raise RuntimeError("Graph client not initialized")
                    group = await self.client.groups.by_group_id(group_id).get()
                    if group:
                        return {
                            "id": group.id,
                            "displayName": group.display_name,
                            "mail": group.mail,
                            "description": group.description,
                        }
                    return None
                    
                group_data = await self._retry_with_backoff(fetch_group)
                if group_data:
                    groups.append(group_data)
            except ODataError as e:
                # Group not found or no permissions - log and continue
                logger.warning(f"Could not fetch group {group_id}: {e}")
                continue
                
        logger.info(f"Fetched {len(groups)} groups out of {len(group_ids)} requested")
        return groups

    async def get_service_principals(self) -> List[Dict[str, Any]]:
        """
        Fetches all service principals from Microsoft Graph API.
        Returns a list of service principal dictionaries.
        """
        if self.use_mock:
            return [
                {"id": "mock-sp-1", "displayName": "Mock Service Principal One"},
                {"id": "mock-sp-2", "displayName": "Mock Service Principal Two"},
            ]
            
        if not self.client:
            raise RuntimeError("Graph client not initialized")
            
        async def fetch_service_principals():
            service_principals = []
            
            # Configure request
            query_params = ServicePrincipalsRequestBuilder.ServicePrincipalsRequestBuilderGetQueryParameters(
                select=["id", "displayName", "appId", "servicePrincipalType"]
            )
            request_config = RequestConfiguration(query_parameters=query_params)
            
            # Get first page
            if not self.client:
                raise RuntimeError("Graph client not initialized")
            sp_page = await self.client.service_principals.get(
                request_configuration=request_config
            )
            
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
                logger.info(
                    f"Fetching next page of service principals (current count: {len(service_principals)})"
                )
                if not self.client:
                    raise RuntimeError("Graph client not initialized")
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
            
            logger.info(f"Fetched {len(service_principals)} service principals from Microsoft Graph")
            return service_principals
            
        result = await self._retry_with_backoff(fetch_service_principals)
        return result if result is not None else []

    async def get_service_principals_by_ids(self, principal_ids: Set[str]) -> List[Dict[str, Any]]:
        """
        Fetches specific service principals by their IDs from Microsoft Graph API.
        
        Args:
            principal_ids: Set of service principal IDs to fetch
            
        Returns:
            List of service principal dictionaries for the specified IDs
        """
        if not principal_ids:
            return []
            
        if self.use_mock:
            # Return mock service principals matching the requested IDs
            mock_sps = [
                {"id": "mock-sp-1", "displayName": "Mock Service Principal One"},
                {"id": "mock-sp-2", "displayName": "Mock Service Principal Two"},
            ]
            return [sp for sp in mock_sps if sp["id"] in principal_ids]
            
        if not self.client:
            raise RuntimeError("Graph client not initialized")
            
        service_principals = []
        
        # Fetch each service principal individually
        for sp_id in principal_ids:
            try:
                async def fetch_sp():
                    if not self.client:
                        raise RuntimeError("Graph client not initialized")
                    sp = await self.client.service_principals.by_service_principal_id(sp_id).get()
                    if sp:
                        return {
                            "id": sp.id,
                            "displayName": sp.display_name,
                            "appId": sp.app_id,
                            "servicePrincipalType": sp.service_principal_type,
                        }
                    return None
                    
                sp_data = await self._retry_with_backoff(fetch_sp)
                if sp_data:
                    service_principals.append(sp_data)
            except ODataError as e:
                # Service principal not found or no permissions - log and continue
                logger.warning(f"Could not fetch service principal {sp_id}: {e}")
                continue
                
        logger.info(f"Fetched {len(service_principals)} service principals out of {len(principal_ids)} requested")
        return service_principals

    async def get_group_memberships(self, group_id: str) -> List[Dict[str, Any]]:
        """
        Fetches members of a group (users and groups) from Microsoft Graph API using SDK.
        Returns a list of member dictionaries with @odata.type information.
        """
        if self.use_mock:
            # Return mock memberships
            if group_id == "mock-group-1":
                return [{"id": "mock-user-1", "@odata.type": "#microsoft.graph.user"}]
            if group_id == "mock-group-2":
                return [{"id": "mock-user-2", "@odata.type": "#microsoft.graph.user"}]
            return []

        if not self.client:
            raise RuntimeError("Graph client not initialized")

        async def fetch_group_members():
            members = []

            # Get first page of group members
            if not self.client:
                raise RuntimeError("Graph client not initialized")
            members_page = await self.client.groups.by_group_id(group_id).members.get()

            if members_page and members_page.value:
                for member in members_page.value:
                    member_dict = {
                        "id": member.id,
                        "displayName": getattr(member, "display_name", None),
                        "@odata.type": member.odata_type,
                    }
                    members.append(member_dict)

            # Handle pagination
            while members_page and members_page.odata_next_link:
                logger.info(
                    f"Fetching next page of group members for group {group_id} (current count: {len(members)})"
                )
                if not self.client:
                    raise RuntimeError("Graph client not initialized")
                members_page = (
                    await self.client.groups.by_group_id(group_id)
                    .members.with_url(members_page.odata_next_link)
                    .get()
                )

                if members_page and members_page.value:
                    for member in members_page.value:
                        member_dict = {
                            "id": member.id,
                            "displayName": getattr(member, "display_name", None),
                            "@odata.type": member.odata_type,
                        }
                        members.append(member_dict)

            logger.info(f"Fetched {len(members)} members for group {group_id}")
            return members

        result = await self._retry_with_backoff(fetch_group_members)
        return result if result is not None else []

    async def ingest_into_graph(self, db_ops: Any, dry_run: bool = False) -> None:
        """
        Ingests AAD users and groups into the graph.
        - Upserts User and IdentityGroup nodes.
        - Upserts MEMBER_OF edges for group memberships.
        - db_ops: DatabaseOperations instance (from resource_processor).
        - dry_run: If True, skips DB operations (for tests).
        """
        logger.info("Starting AAD graph ingestion")

        # Fetch users and groups concurrently if not using mock
        if self.use_mock:
            users = await self.get_users()
            groups = await self.get_groups()
        else:
            import asyncio

            users, groups = await asyncio.gather(self.get_users(), self.get_groups())

        logger.info(f"Ingesting {len(users)} users and {len(groups)} groups")

        # Upsert User nodes with IaC-standard properties
        for user in users:
            user_id = user.get("id")
            if not user_id:
                continue
            display_name = user.get("displayName", user_id)
            props = {
                "id": user_id,
                "display_name": display_name,
                "user_principal_name": user.get("userPrincipalName"),
                "mail": user.get("mail"),
                "type": "Microsoft.Graph/users",
                "name": display_name,
                "displayName": display_name,
                "location": "global",
                "resourceGroup": "identity-resources",
            }
            if not dry_run:
                db_ops.upsert_generic("User", "id", user_id, props)

        # Upsert Group nodes with IaC-standard properties
        for group in groups:
            group_id = group.get("id")
            if not group_id:
                continue
            display_name = group.get("displayName", group_id)
            props = {
                "id": group_id,
                "display_name": display_name,
                "mail": group.get("mail"),
                "description": group.get("description"),
                "type": "Microsoft.Graph/groups",
                "name": display_name,
                "displayName": display_name,
                "location": "global",
                "resourceGroup": "identity-resources",
            }
            if not dry_run:
                db_ops.upsert_generic("IdentityGroup", "id", group_id, props)

        # Upsert group memberships (MEMBER_OF edges)
        for group in groups:
            group_id = group.get("id")
            if not group_id:
                continue

            logger.info(
                f"Fetching memberships for group {group_id} ({group.get('displayName', 'Unknown')})"
            )
            members = await self.get_group_memberships(str(group_id))

            for member in members:
                member_id = member.get("id")
                if not member_id:
                    continue
                # Only create edge if member is a User or Group
                odata_type = member.get("@odata.type", "")
                if odata_type.endswith("user") or odata_type.endswith("group"):
                    # MEMBER_OF: (User|IdentityGroup)-[:MEMBER_OF]->(IdentityGroup)
                    if not dry_run:
                        db_ops.create_generic_rel(
                            src_id=member_id,
                            rel_type="MEMBER_OF",
                            tgt_key_value=group_id,
                            tgt_label="IdentityGroup",
                            tgt_key_prop="id",
                        )

        logger.info("Completed AAD graph ingestion")

    async def ingest_filtered_identities(
        self,
        user_ids: Set[str],
        group_ids: Set[str],
        service_principal_ids: Set[str],
        db_ops: Any,
        dry_run: bool = False
    ) -> None:
        """
        Ingests only specific AAD identities into the graph.
        Used when filtering resources to include only referenced identities.
        
        Args:
            user_ids: Set of user IDs to ingest
            group_ids: Set of group IDs to ingest
            service_principal_ids: Set of service principal IDs to ingest
            db_ops: DatabaseOperations instance
            dry_run: If True, skips DB operations (for tests)
        """
        logger.info(
            f"Starting filtered AAD graph ingestion - "
            f"Users: {len(user_ids)}, Groups: {len(group_ids)}, "
            f"Service Principals: {len(service_principal_ids)}"
        )
        
        # Fetch identities concurrently
        import asyncio
        
        users, groups, service_principals = await asyncio.gather(
            self.get_users_by_ids(user_ids),
            self.get_groups_by_ids(group_ids),
            self.get_service_principals_by_ids(service_principal_ids)
        )
        
        logger.info(
            f"Fetched {len(users)} users, {len(groups)} groups, "
            f"{len(service_principals)} service principals"
        )
        
        # Upsert User nodes with IaC-standard properties
        for user in users:
            user_id = user.get("id")
            if not user_id:
                continue
            display_name = user.get("displayName", user_id)
            props = {
                "id": user_id,
                "display_name": display_name,
                "user_principal_name": user.get("userPrincipalName"),
                "mail": user.get("mail"),
                "type": "Microsoft.Graph/users",
                "name": display_name,
                "displayName": display_name,
                "location": "global",
                "resourceGroup": "identity-resources",
            }
            if not dry_run:
                db_ops.upsert_generic("User", "id", user_id, props)
        
        # Upsert Group nodes with IaC-standard properties
        for group in groups:
            group_id = group.get("id")
            if not group_id:
                continue
            display_name = group.get("displayName", group_id)
            props = {
                "id": group_id,
                "display_name": display_name,
                "mail": group.get("mail"),
                "description": group.get("description"),
                "type": "Microsoft.Graph/groups",
                "name": display_name,
                "displayName": display_name,
                "location": "global",
                "resourceGroup": "identity-resources",
            }
            if not dry_run:
                db_ops.upsert_generic("IdentityGroup", "id", group_id, props)
        
        # Upsert ServicePrincipal nodes with IaC-standard properties
        for sp in service_principals:
            sp_id = sp.get("id")
            if not sp_id:
                continue
            display_name = sp.get("displayName", sp_id)
            props = {
                "id": sp_id,
                "display_name": display_name,
                "app_id": sp.get("appId"),
                "service_principal_type": sp.get("servicePrincipalType"),
                "type": "Microsoft.Graph/servicePrincipals",
                "name": display_name,
                "displayName": display_name,
                "location": "global",
                "resourceGroup": "identity-resources",
            }
            if not dry_run:
                db_ops.upsert_generic("ServicePrincipal", "id", sp_id, props)
        
        # Fetch and create group memberships only for the filtered groups
        for group in groups:
            group_id = group.get("id")
            if not group_id:
                continue
            
            logger.info(
                f"Fetching memberships for group {group_id} ({group.get('displayName', 'Unknown')})"
            )
            members = await self.get_group_memberships(str(group_id))
            
            for member in members:
                member_id = member.get("id")
                if not member_id:
                    continue
                    
                # Only create edge if member is in our filtered sets
                odata_type = member.get("@odata.type", "")
                if odata_type.endswith("user") and member_id in user_ids:
                    # MEMBER_OF: User-[:MEMBER_OF]->IdentityGroup
                    if not dry_run:
                        db_ops.create_generic_rel(
                            src_id=member_id,
                            rel_type="MEMBER_OF",
                            tgt_key_value=group_id,
                            tgt_label="IdentityGroup",
                            tgt_key_prop="id",
                        )
                elif odata_type.endswith("group") and member_id in group_ids:
                    # MEMBER_OF: IdentityGroup-[:MEMBER_OF]->IdentityGroup
                    if not dry_run:
                        db_ops.create_generic_rel(
                            src_id=member_id,
                            rel_type="MEMBER_OF",
                            tgt_key_value=group_id,
                            tgt_label="IdentityGroup",
                            tgt_key_prop="id",
                        )
                elif odata_type.endswith("servicePrincipal") and member_id in service_principal_ids:
                    # MEMBER_OF: ServicePrincipal-[:MEMBER_OF]->IdentityGroup
                    if not dry_run:
                        db_ops.create_generic_rel(
                            src_id=member_id,
                            rel_type="MEMBER_OF",
                            tgt_key_value=group_id,
                            tgt_label="IdentityGroup",
                            tgt_key_prop="id",
                        )
        
        logger.info("Completed filtered AAD graph ingestion")
