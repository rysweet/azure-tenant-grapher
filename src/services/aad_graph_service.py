import os
import time
from typing import Any, Dict, List, Optional

import requests


class AADGraphService:
    """
    Service for fetching Azure AD users and groups from Microsoft Graph API.
    Reads credentials from environment variables:
      - AZURE_CLIENT_ID
      - AZURE_CLIENT_SECRET
      - AZURE_TENANT_ID
    """

    def __init__(self, use_mock: bool = False):
        self.use_mock = use_mock
        self.token: Optional[str] = None

    def _get_token(self) -> str:
        if self.use_mock:
            return "mock-token"
        tenant_id = os.environ.get("AZURE_TENANT_ID")
        client_id = os.environ.get("AZURE_CLIENT_ID")
        client_secret = os.environ.get("AZURE_CLIENT_SECRET")
        if not all([tenant_id, client_id, client_secret]):
            raise RuntimeError(
                "Missing one or more required Azure AD credentials in environment variables."
            )
        url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "https://graph.microsoft.com/.default",
        }
        resp = requests.post(url, data=data)
        resp.raise_for_status()
        return resp.json()["access_token"]

    def _ensure_token(self):
        if self.token is None:
            self.token = self._get_token()

    def _paged_get(
        self, url: str, headers: dict[str, str], params: Optional[dict[str, Any]] = None
    ) -> list[dict[str, Any]]:
        """Fetch all pages from a Graph API endpoint."""
        results: list[dict[str, Any]] = []
        params = params or {}
        while url:
            for attempt in range(5):
                try:
                    resp = requests.get(url, headers=headers, params=params)
                    if resp.status_code == 429:
                        # Throttled, wait and retry
                        retry_after = int(resp.headers.get("Retry-After", "2"))
                        time.sleep(retry_after)
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    results.extend(data.get("value", []))
                    url = data.get("@odata.nextLink")
                    params = None  # Only use params on first request
                    break
                except requests.RequestException:
                    if attempt == 4:
                        raise
                    time.sleep(2**attempt)
        return results

    def get_users(self) -> List[Dict[str, object]]:
        """
        Fetches users from Microsoft Graph API, handling pagination and throttling.
        Returns a list of user dicts.
        """
        if self.use_mock:
            return [
                {"id": "mock-user-1", "displayName": "Mock User One"},
                {"id": "mock-user-2", "displayName": "Mock User Two"},
            ]
        self._ensure_token()
        url = "https://graph.microsoft.com/v1.0/users"
        headers = {"Authorization": f"Bearer {self.token}"}
        return self._paged_get(url, headers)

    def get_groups(self) -> List[Dict[str, object]]:
        """
        Fetches groups from Microsoft Graph API, handling pagination and throttling.
        Returns a list of group dicts.
        """
        if self.use_mock:
            return [
                {"id": "mock-group-1", "displayName": "Mock Group One"},
                {"id": "mock-group-2", "displayName": "Mock Group Two"},
            ]
        self._ensure_token()
        url = "https://graph.microsoft.com/v1.0/groups"
        headers = {"Authorization": f"Bearer {self.token}"}
        return self._paged_get(url, headers)

    def get_group_memberships(self, group_id: str) -> List[Dict[str, Any]]:
        """
        Fetches members of a group (users and groups) from Microsoft Graph API.
        Returns a list of member dicts.
        """
        if self.use_mock:
            # Return mock memberships
            if group_id == "mock-group-1":
                return [{"id": "mock-user-1", "@odata.type": "#microsoft.graph.user"}]
            if group_id == "mock-group-2":
                return [{"id": "mock-user-2", "@odata.type": "#microsoft.graph.user"}]
            return []
        self._ensure_token()
        url = f"https://graph.microsoft.com/v1.0/groups/{group_id}/members"
        headers = {"Authorization": f"Bearer {self.token}"}
        return self._paged_get(url, headers)

    def ingest_into_graph(self, db_ops: Any, dry_run: bool = False) -> None:
        """
        Ingests AAD users and groups into the graph.
        - Upserts User and IdentityGroup nodes.
        - Upserts MEMBER_OF edges for group memberships.
        - db_ops: DatabaseOperations instance (from resource_processor).
        - dry_run: If True, skips DB operations (for tests).
        """
        users = self.get_users()
        groups = self.get_groups()

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
            members = self.get_group_memberships(str(group_id))
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
