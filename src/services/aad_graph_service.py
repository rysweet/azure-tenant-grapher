import logging
import os
import time
from typing import Any, Dict, List, Optional

from azure.identity import ClientSecretCredential
from kiota_abstractions.base_request_configuration import RequestConfiguration
from msgraph import GraphServiceClient
from msgraph.generated.groups.groups_request_builder import GroupsRequestBuilder
from msgraph.generated.models.o_data_errors.o_data_error import ODataError
from msgraph.generated.users.users_request_builder import UsersRequestBuilder

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
        credential = ClientSecretCredential(
            tenant_id=tenant_id, client_id=client_id, client_secret=client_secret
        )

        # Initialize Graph client with credential
        scopes = ["https://graph.microsoft.com/.default"]
        self.client = GraphServiceClient(credentials=credential, scopes=scopes)

    async def _retry_with_backoff(self, operation, max_retries: int = 5):
        """Execute operation with exponential backoff retry logic."""
        for attempt in range(max_retries):
            try:
                return await operation()
            except ODataError as e:
                if e.response_status_code == 429:
                    # Rate limited - check for Retry-After header
                    retry_after = e.response.headers.get("Retry-After", "2")
                    sleep_time = int(retry_after)
                    logger.warning(
                        f"Rate limited, retrying after {sleep_time} seconds (attempt {attempt + 1})"
                    )
                    time.sleep(sleep_time)
                    continue
                elif 500 <= e.response_status_code < 600:
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

        return await self._retry_with_backoff(fetch_users)

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

        return await self._retry_with_backoff(fetch_groups)

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

        return await self._retry_with_backoff(fetch_group_members)

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

        # Upsert User nodes
        for user in users:
            user_id = user.get("id")
            if not user_id:
                continue
            props = {
                "id": user_id,
                "displayName": user.get("displayName"),
                "userPrincipalName": user.get("userPrincipalName"),
                "mail": user.get("mail"),
                "type": "User",
            }
            if not dry_run:
                db_ops.upsert_generic("User", "id", user_id, props)

        # Upsert Group nodes
        for group in groups:
            group_id = group.get("id")
            if not group_id:
                continue
            props = {
                "id": group_id,
                "displayName": group.get("displayName"),
                "mail": group.get("mail"),
                "description": group.get("description"),
                "type": "IdentityGroup",
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
