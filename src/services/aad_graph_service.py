import os
from typing import Dict, List, Optional

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

    def get_users(self) -> List[Dict[str, object]]:
        """
        Fetches users from Microsoft Graph API.
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
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json().get("value", [])

    def get_groups(self) -> List[Dict[str, object]]:
        """
        Fetches groups from Microsoft Graph API.
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
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json().get("value", [])
