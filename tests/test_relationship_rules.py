from src.relationship_rules import (
    CreatorRule,
    DependsOnRule,
    IdentityRule,
    MonitoringRule,
    NetworkRule,
    RegionRule,
    TagRule,
)
from src.relationship_rules.diagnostic_rule import DiagnosticRule


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


def test_identity_rule_role_assignment_user():
    rule = IdentityRule()
    db = DummyDbOps()
    resource = {
        "id": "ra1",
        "type": "Microsoft.Authorization/roleAssignments",
        "properties": {
            "principalId": "user1",
            "principalType": "User",
            "roleDefinitionId": "roledef1",
        },
    }
    assert rule.applies(resource)
    rule.emit(resource, db)
    # RoleAssignment node
    assert ("upsert", "RoleAssignment", "id", "ra1", {"id": "ra1"}) in db.calls
    # User node
    assert (
        "upsert",
        "User",
        "id",
        "user1",
        {"id": "user1", "principalType": "User"},
    ) in db.calls
    # RoleDefinition node
    assert ("upsert", "RoleDefinition", "id", "roledef1", {"id": "roledef1"}) in [
        c if c[0] == "upsert" and c[1] == "RoleDefinition" else None for c in db.calls
    ]
    # ASSIGNED_TO edge
    assert ("rel", "ra1", "ASSIGNED_TO", "user1", "User", "id") in db.calls
    # HAS_ROLE edge
    assert ("rel", "user1", "HAS_ROLE", "roledef1", "RoleDefinition", "id") in db.calls


def test_identity_rule_role_assignment_service_principal():
    rule = IdentityRule()
    db = DummyDbOps()
    resource = {
        "id": "ra2",
        "type": "Microsoft.Authorization/roleAssignments",
        "properties": {
            "principalId": "sp1",
            "principalType": "ServicePrincipal",
            "roleDefinitionId": "roledef2",
        },
    }
    assert rule.applies(resource)
    rule.emit(resource, db)
    assert (
        "upsert",
        "ServicePrincipal",
        "id",
        "sp1",
        {"id": "sp1", "principalType": "ServicePrincipal"},
    ) in db.calls
    assert ("rel", "ra2", "ASSIGNED_TO", "sp1", "ServicePrincipal", "id") in db.calls
    assert ("rel", "sp1", "HAS_ROLE", "roledef2", "RoleDefinition", "id") in db.calls


def test_identity_rule_role_assignment_managed_identity():
    rule = IdentityRule()
    db = DummyDbOps()
    resource = {
        "id": "ra3",
        "type": "Microsoft.Authorization/roleAssignments",
        "properties": {
            "principalId": "mi1",
            "principalType": "ManagedIdentity",
            "roleDefinitionId": "roledef3",
        },
    }
    assert rule.applies(resource)
    rule.emit(resource, db)
    assert (
        "upsert",
        "ManagedIdentity",
        "id",
        "mi1",
        {"id": "mi1", "principalType": "ManagedIdentity"},
    ) in db.calls
    assert ("rel", "ra3", "ASSIGNED_TO", "mi1", "ManagedIdentity", "id") in db.calls
    assert ("rel", "mi1", "HAS_ROLE", "roledef3", "RoleDefinition", "id") in db.calls


def test_identity_rule_role_assignment_group():
    rule = IdentityRule()
    db = DummyDbOps()
    resource = {
        "id": "ra4",
        "type": "Microsoft.Authorization/roleAssignments",
        "properties": {
            "principalId": "group1",
            "principalType": "Group",
            "roleDefinitionId": "roledef4",
        },
    }
    assert rule.applies(resource)
    rule.emit(resource, db)
    assert (
        "upsert",
        "IdentityGroup",
        "id",
        "group1",
        {"id": "group1", "principalType": "Group"},
    ) in db.calls
    assert ("rel", "ra4", "ASSIGNED_TO", "group1", "IdentityGroup", "id") in db.calls
    assert ("rel", "group1", "HAS_ROLE", "roledef4", "RoleDefinition", "id") in db.calls


def test_identity_rule_role_definition():
    rule = IdentityRule()
    db = DummyDbOps()
    resource = {
        "id": "roledef5",
        "type": "Microsoft.Authorization/roleDefinitions",
        "properties": {"roleName": "Reader", "description": "Can view resources"},
    }
    assert rule.applies(resource)
    rule.emit(resource, db)
    assert (
        "upsert",
        "RoleDefinition",
        "id",
        "roledef5",
        {"id": "roledef5", "roleName": "Reader", "description": "Can view resources"},
    ) in db.calls


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


# To run tests locally:
#   uv run pytest -q
# To run pre-commit checks:
#   pre-commit run --all-files


def test_diagnostic_rule():
    rule = DiagnosticRule()
    db = DummyDbOps()
    resource = {
        "id": "res_diag",
        "type": "Microsoft.Compute/virtualMachines",
        "diagnosticSettings": [
            {
                "id": "diag1",
                "name": "diagsetting1",
                "properties": {"workspaceId": "ws_diag"},
            }
        ],
    }
    assert rule.applies(resource)
    rule.emit(resource, db)
    # Should upsert DiagnosticSetting node
    assert (
        "upsert",
        "DiagnosticSetting",
        "id",
        "diag1",
        {
            "id": "diag1",
            "name": "diagsetting1",
            "type": "Microsoft.Insights/diagnosticSettings",
            "properties": {"workspaceId": "ws_diag"},
        },
    ) in db.calls
    # Should create SENDS_DIAG_TO relationship
    assert (
        "rel",
        "res_diag",
        "SENDS_DIAG_TO",
        "diag1",
        "DiagnosticSetting",
        "id",
    ) in db.calls
    # Should upsert LogAnalyticsWorkspace node
    assert (
        "upsert",
        "LogAnalyticsWorkspace",
        "id",
        "ws_diag",
        {"id": "ws_diag"},
    ) in db.calls
    # Should create LOGS_TO relationship
    assert (
        "rel",
        "diag1",
        "LOGS_TO",
        "ws_diag",
        "LogAnalyticsWorkspace",
        "id",
    ) in db.calls
