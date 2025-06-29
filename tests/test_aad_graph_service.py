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
        self.upserts.append((label, key_prop, key_value, dict(properties)))

    def create_generic_rel(
        self, src_id, rel_type, tgt_key_value, tgt_label, tgt_key_prop
    ):
        self.rels.append((src_id, rel_type, tgt_key_value, tgt_label, tgt_key_prop))


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


def test_ingest_into_graph_with_fixtures(monkeypatch):
    # Patch AADGraphService to use fixture data
    users = load_fixture("users.json")["value"]
    groups = load_fixture("groups.json")["value"]
    group_members = load_fixture("group_members_group-1.json")["value"]

    class FixtureAADGraphService(AADGraphService):
        def get_users(self):
            return users

        def get_groups(self):
            return groups

        def get_group_memberships(self, group_id):
            if group_id == "group-1":
                return group_members
            return []

    db_ops = MockDBOps()
    service = FixtureAADGraphService()
    service.ingest_into_graph(db_ops)

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


def test_ingest_into_graph_dry_run(monkeypatch):
    # Patch AADGraphService to use fixture data
    users = load_fixture("users.json")["value"]
    groups = load_fixture("groups.json")["value"]
    group_members = load_fixture("group_members_group-1.json")["value"]

    class FixtureAADGraphService(AADGraphService):
        def get_users(self):
            return users

        def get_groups(self):
            return groups

        def get_group_memberships(self, group_id):
            if group_id == "group-1":
                return group_members
            return []

    db_ops = MockDBOps()
    service = FixtureAADGraphService()
    service.ingest_into_graph(db_ops, dry_run=True)

    # No upserts or rels should be recorded in dry_run
    assert not db_ops.upserts
    assert not db_ops.rels
