from src.relationship_rules import (
    CreatorRule,
    DependsOnRule,
    IdentityRule,
    MonitoringRule,
    NetworkRule,
    RegionRule,
    TagRule,
)


class DummyDbOps:
    def __init__(self):
        self.calls = []

    def create_generic_rel(self, src, rel, tgt, tgt_label, tgt_key):
        self.calls.append(("rel", src, rel, tgt, tgt_label, tgt_key))

    def upsert_generic(self, label, key, value, props):
        self.calls.append(("upsert", label, key, value, props))


def test_network_rule_vm():
    rule = NetworkRule()
    db = DummyDbOps()
    resource = {
        "id": "vm1",
        "type": "Microsoft.Compute/virtualMachines",
        "network_profile": {
            "network_interfaces": [
                {"ip_configurations": [{"subnet": {"id": "subnet1"}}]}
            ]
        },
    }
    assert rule.applies(resource)
    rule.emit(resource, db)
    assert ("rel", "vm1", "USES_SUBNET", "subnet1", "Resource", "id") in db.calls


def test_identity_rule_managed_identity():
    rule = IdentityRule()
    db = DummyDbOps()
    resource = {
        "id": "res1",
        "type": "Microsoft.Web/sites",
        "identity": {"principalId": "pid1"},
    }
    assert rule.applies(resource)
    rule.emit(resource, db)
    assert ("rel", "res1", "USES_IDENTITY", "pid1", "ManagedIdentity", "id") in db.calls


def test_tag_rule():
    rule = TagRule()
    db = DummyDbOps()
    resource = {
        "id": "res2",
        "type": "Microsoft.Storage/storageAccounts",
        "tags": {"env": "prod"},
    }
    assert rule.applies(resource)
    rule.emit(resource, db)
    assert (
        "upsert",
        "Tag",
        "id",
        "env:prod",
        {"key": "env", "value": "prod"},
    ) in db.calls
    assert ("rel", "res2", "TAGGED_WITH", "env:prod", "Tag", "id") in db.calls


def test_region_rule():
    rule = RegionRule()
    db = DummyDbOps()
    resource = {"id": "res3", "location": "eastus"}
    assert rule.applies(resource)
    rule.emit(resource, db)
    assert ("upsert", "Region", "code", "eastus", {"name": "eastus"}) in db.calls
    assert ("rel", "res3", "LOCATED_IN", "eastus", "Region", "code") in db.calls


def test_creator_rule():
    rule = CreatorRule()
    db = DummyDbOps()
    resource = {"id": "res4", "systemData": {"createdBy": "user1"}}
    assert rule.applies(resource)
    rule.emit(resource, db)
    assert ("upsert", "User", "id", "user1", {"id": "user1"}) in db.calls
    assert ("rel", "res4", "CREATED_BY", "user1", "User", "id") in db.calls


def test_monitoring_rule():
    rule = MonitoringRule()
    db = DummyDbOps()
    resource = {"id": "res5", "diagnosticSettings": [{"workspaceId": "ws1"}]}
    assert rule.applies(resource)
    rule.emit(resource, db)
    assert ("rel", "res5", "LOGS_TO", "ws1", "Resource", "id") in db.calls


def test_depends_on_rule():
    rule = DependsOnRule()
    db = DummyDbOps()
    resource = {"id": "res6", "dependsOn": ["res7"]}
    assert rule.applies(resource)
    rule.emit(resource, db)
    assert ("rel", "res6", "DEPENDS_ON", "res7", "Resource", "id") in db.calls
