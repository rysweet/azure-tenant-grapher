import os

import pytest

from src.services.aad_graph_service import AADGraphService


def test_get_users_mock():
    service = AADGraphService(use_mock=True)
    users = service.get_users()
    assert isinstance(users, list)
    assert users
    for user in users:
        assert "id" in user
        assert "displayName" in user


def test_get_groups_mock():
    service = AADGraphService(use_mock=True)
    groups = service.get_groups()
    assert isinstance(groups, list)
    assert groups
    for group in groups:
        assert "id" in group
        assert "displayName" in group


@pytest.mark.skipif(
    not all(
        [
            os.environ.get("AZURE_CLIENT_ID"),
            os.environ.get("AZURE_CLIENT_SECRET"),
            os.environ.get("AZURE_TENANT_ID"),
        ]
    ),
    reason="Azure AD credentials not set in environment",
)
def test_get_users_real():
    service = AADGraphService()
    users = service.get_users()
    assert isinstance(users, list)
    # If there are no users, that's fine, but the call should succeed


@pytest.mark.skipif(
    not all(
        [
            os.environ.get("AZURE_CLIENT_ID"),
            os.environ.get("AZURE_CLIENT_SECRET"),
            os.environ.get("AZURE_TENANT_ID"),
        ]
    ),
    reason="Azure AD credentials not set in environment",
)
def test_get_groups_real():
    service = AADGraphService()
    groups = service.get_groups()
    assert isinstance(groups, list)
    # If there are no groups, that's fine, but the call should succeed
