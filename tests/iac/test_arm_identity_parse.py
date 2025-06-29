import json
import re
from pathlib import Path

from src.relationship_rules.identity_rule import IdentityRule
from src.resource_processor import extract_identity_fields


class MockDbOps:
    def __init__(self):
        self.upserts = []
        self.rels = []

    def upsert_generic(self, label, key_prop, key_value, properties):
        self.upserts.append((label, key_prop, key_value, dict(properties)))

    def create_generic_rel(
        self, src_id, rel_type, tgt_key_value, tgt_label, tgt_key_prop
    ):
        self.rels.append((src_id, rel_type, tgt_key_value, tgt_label, tgt_key_prop))


def test_arm_identity_rbac_graph_emission():
    fixture_path = Path(__file__).parent / "fixtures" / "arm_identity_rbac.json"
    with open(fixture_path) as f:
        arm = json.load(f)
    resources = arm["resources"]
    # Add "id" field to each resource for test realism
    for res in resources:
        if "id" not in res:
            res["id"] = (
                f"/subscriptions/xxx/resourceGroups/yyy/providers/{res['type']}/{res['name']}"
            )
    db_ops = MockDbOps()
    rule = IdentityRule()
    for res in resources:
        rule.emit(res, db_ops)

    # Check ManagedIdentity nodes
    managed_identities = [u for u in db_ops.upserts if u[0] == "ManagedIdentity"]
    assert any(
        "SystemAssigned" in u[3].get("identityType", "") for u in managed_identities
    )
    assert any(
        "UserAssigned" in u[3].get("identityType", "") for u in managed_identities
    )
    # Check RoleAssignment node
    assert any(u[0] == "RoleAssignment" for u in db_ops.upserts)
    # Check USES_IDENTITY edge
    assert any(r[1] == "USES_IDENTITY" for r in db_ops.rels)
    # Check RoleAssignment has correct fields
    ra = next(u for u in db_ops.upserts if u[0] == "RoleAssignment")
    assert "principalId" in ra[3]
    assert "principalType" in ra[3]
    assert "roleDefinitionId" in ra[3]
    assert "scope" in ra[3]


def is_guid(val):
    return bool(
        re.match(
            r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
            val,
        )
    )


def test_identity_block_extracted():
    resource = {
        "id": "/subscriptions/xxx/resourceGroups/yyy/providers/Microsoft.Compute/virtualMachines/vm1",
        "name": "vm1",
        "identity": {
            "type": "SystemAssigned",
            "principalId": "11111111-2222-3333-4444-555555555555",
        },
    }
    extract_identity_fields(resource)
    assert "identity" in resource
    assert resource["identity"]["type"] == "SystemAssigned"


def test_principal_id_valid_guid():
    resource = {"name": "sp1", "principalId": "12345678-1234-1234-1234-123456789abc"}
    extract_identity_fields(resource)
    assert "principal_id" in resource
    assert is_guid(resource["principal_id"])


def test_both_identity_and_principal_id():
    resource = {
        "name": "webapp1",
        "identity": {"type": "UserAssigned"},
        "principalId": "abcdefab-1234-5678-9abc-def012345678",
    }
    extract_identity_fields(resource)
    assert "identity" in resource
    assert "principal_id" in resource
    assert is_guid(resource["principal_id"])


def test_invalid_principal_id_not_extracted():
    resource = {"name": "badsp", "principalId": "not-a-guid"}
    extract_identity_fields(resource)
    assert "principal_id" not in resource


def test_neither_identity_nor_principal_id():
    resource = {"name": "storage1"}
    extract_identity_fields(resource)
    assert "identity" not in resource
    assert "principal_id" not in resource
