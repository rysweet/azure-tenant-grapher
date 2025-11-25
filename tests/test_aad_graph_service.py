import json
import os

import pytest

from src.services.aad_graph_service import AADGraphService

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "aad")


def load_fixture(name):
    with open(os.path.join(FIXTURES, name)) as f:
        return json.load(f)


class MockDBOps:
    def __init__(self):
        self.upserts = []
        self.rels = []

    def upsert_generic(self, label, key_prop, key_value, properties):
        # Mock the real upsert_generic behavior: filter out None values
        # This simulates what the actual DatabaseOperations.upsert_generic does
        filtered_props = {k: v for k, v in properties.items() if v is not None}
        self.upserts.append((label, key_prop, key_value, filtered_props))

    def create_generic_rel(
        self, src_id, rel_type, tgt_key_value, tgt_label, tgt_key_prop
    ):
        self.rels.append((src_id, rel_type, tgt_key_value, tgt_label, tgt_key_prop))


@pytest.mark.asyncio
async def test_get_users_mock():
    service = AADGraphService(use_mock=True)
    users = await service.get_users()
    assert isinstance(users, list)
    assert users
    for user in users:
        assert "id" in user
        assert "displayName" in user


@pytest.mark.asyncio
async def test_get_groups_mock():
    service = AADGraphService(use_mock=True)
    groups = await service.get_groups()
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
@pytest.mark.asyncio
async def test_get_users_real():
    service = AADGraphService()
    users = await service.get_users()
    assert isinstance(users, list)


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
@pytest.mark.asyncio
async def test_get_groups_real():
    service = AADGraphService()
    groups = await service.get_groups()
    assert isinstance(groups, list)


@pytest.mark.asyncio
async def test_ingest_into_graph_with_fixtures(monkeypatch):
    # Patch AADGraphService to use fixture data
    users = load_fixture("users.json")["value"]
    groups = load_fixture("groups.json")["value"]
    group_members = load_fixture("group_members_group-1.json")["value"]

    class FixtureAADGraphService(AADGraphService):
        def __init__(self):
            # Skip the parent __init__ to avoid graph client initialization
            self.use_mock = True
            self.client = None

        async def get_users(self):
            return users

        async def get_groups(self):
            return groups

        async def get_group_memberships(self, group_id):
            if group_id == "group-1":
                return group_members
            return []

    db_ops = MockDBOps()
    service = FixtureAADGraphService()
    await service.ingest_into_graph(db_ops)

    # Check User nodes
    user_ids = {u["id"] for u in users}
    upserted_users = {kv for (label, _, kv, props) in db_ops.upserts if label == "User"}
    assert user_ids == upserted_users

    # Check Group nodes
    group_ids = {g["id"] for g in groups}
    upserted_groups = {
        kv for (label, _, kv, props) in db_ops.upserts if label == "IdentityGroup"
    }
    assert group_ids == upserted_groups

    # Check MEMBER_OF edges for group-1
    member_ids = {m["id"] for m in group_members}
    member_of_edges = {
        (src, tgt)
        for (src, rel, tgt, label, key) in db_ops.rels
        if rel == "MEMBER_OF" and label == "IdentityGroup"
    }
    for mid in member_ids:
        assert (mid, "group-1") in member_of_edges


@pytest.mark.asyncio
async def test_ingest_into_graph_dry_run(monkeypatch):
    # Patch AADGraphService to use fixture data
    users = load_fixture("users.json")["value"]
    groups = load_fixture("groups.json")["value"]
    group_members = load_fixture("group_members_group-1.json")["value"]

    class FixtureAADGraphService(AADGraphService):
        def __init__(self):
            # Skip the parent __init__ to avoid graph client initialization
            self.use_mock = True
            self.client = None

        async def get_users(self):
            return users

        async def get_groups(self):
            return groups

        async def get_group_memberships(self, group_id):
            if group_id == "group-1":
                return group_members
            return []

    db_ops = MockDBOps()
    service = FixtureAADGraphService()
    await service.ingest_into_graph(db_ops, dry_run=True)

    # No upserts or rels should be recorded in dry_run
    assert not db_ops.upserts
    assert not db_ops.rels


@pytest.mark.asyncio
async def test_ingest_users_with_none_values():
    """Test that User nodes with None values for mail/userPrincipalName are handled correctly."""
    # Create test users with None values (common in real Azure AD)
    users_with_none = [
        {
            "id": "user-1",
            "displayName": "User With Mail",
            "userPrincipalName": "user1@example.com",
            "mail": "user1@example.com",
        },
        {
            "id": "user-2",
            "displayName": "User Without Mail",
            "userPrincipalName": "user2@example.com",
            "mail": None,  # This was causing CypherTypeError
        },
        {
            "id": "user-3",
            "displayName": "Guest User",
            "userPrincipalName": None,  # Guest users may have None
            "mail": None,
        },
    ]

    class FixtureAADGraphService(AADGraphService):
        def __init__(self):
            self.use_mock = True
            self.client = None

        async def get_users(self):
            return users_with_none

        async def get_groups(self):
            return []

        async def get_group_memberships(self, group_id):
            return []

    db_ops = MockDBOps()
    service = FixtureAADGraphService()
    await service.ingest_into_graph(db_ops)

    # Verify all users were upserted
    user_upserts = [
        (label, kv, props)
        for (label, _, kv, props) in db_ops.upserts
        if label == "User"
    ]
    assert len(user_upserts) == 3

    # Verify None values were filtered out in properties
    for _label, _key_value, props in user_upserts:
        # None values should not be present in the properties dict
        for prop_key, prop_value in props.items():
            assert prop_value is not None, (
                f"Property {prop_key} should not be None in upserted data"
            )

        # Required fields should always be present
        assert "id" in props
        assert "display_name" in props
        assert "type" in props
