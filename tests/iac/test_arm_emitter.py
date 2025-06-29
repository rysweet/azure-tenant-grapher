import json
import tempfile
from pathlib import Path

from src.iac.emitters.arm_emitter import ArmEmitter
from src.iac.traverser import TenantGraph


def test_arm_emitter_creates_valid_template():
    emitter = ArmEmitter()
    graph = TenantGraph()
    graph.resources = [
        {
            "type": "Microsoft.Storage/storageAccounts",
            "name": "teststorage",
            "location": "eastus",
            "tags": {"env": "test"},
        },
        {
            "type": "Microsoft.Compute/virtualMachines",
            "name": "testvm",
            "location": "eastus2",
        },
    ]
    with tempfile.TemporaryDirectory() as temp_dir:
        out_dir = Path(temp_dir)
        files = emitter.emit(graph, out_dir)
        assert len(files) == 1
        assert files[0].name == "azuredeploy.json"
        with open(files[0]) as f:
            template = json.load(f)
        # Check ARM template structure
        assert "$schema" in template
        assert "resources" in template
        assert isinstance(template["resources"], list)
        assert len(template["resources"]) == 2
        # Check resource types
        types = {r["type"] for r in template["resources"]}
        assert "Microsoft.Storage/storageAccounts" in types
        assert "Microsoft.Compute/virtualMachines" in types


def test_arm_emitter_identities_and_rbac():
    import json
    import tempfile
    from pathlib import Path

    from src.iac.emitters.arm_emitter import ArmEmitter
    from src.iac.traverser import TenantGraph

    emitter = ArmEmitter()
    graph = TenantGraph()
    graph.resources = [
        # User-assigned managed identity
        {
            "type": "Microsoft.ManagedIdentity/userAssignedIdentities",
            "name": "myuami",
            "location": "westus2",
        },
        # System-assigned identity on VM
        {
            "type": "Microsoft.Compute/virtualMachines",
            "name": "vmwithsysid",
            "location": "eastus",
            "systemAssignedIdentity": True,
        },
        # Resource referencing user-assigned identity
        {
            "type": "Microsoft.Web/sites",
            "name": "webappwithuami",
            "location": "eastus2",
            "identity": {
                "type": "UserAssigned",
                "userAssignedIdentities": {
                    "/subscriptions/xxx/resourceGroups/yyy/providers/Microsoft.ManagedIdentity/userAssignedIdentities/myuami": {}
                },
            },
        },
        # Role assignment
        {
            "type": "Microsoft.Authorization/roleAssignments",
            "name": "myra",
            "properties": {
                "roleDefinitionId": "/subscriptions/xxx/providers/Microsoft.Authorization/roleDefinitions/abc",
                "principalId": "11111111-2222-3333-4444-555555555555",
                "principalType": "ServicePrincipal",
                "scope": "/subscriptions/xxx/resourceGroups/yyy",
            },
        },
        # Custom role definition
        {
            "type": "Microsoft.Authorization/roleDefinitions",
            "name": "mycustomrole",
            "properties": {
                "roleName": "My Custom Role",
                "description": "Custom role for testing",
                "permissions": [{"actions": ["*"], "notActions": []}],
                "assignableScopes": ["/subscriptions/xxx"],
                "roleType": "Custom",
            },
        },
    ]
    with tempfile.TemporaryDirectory() as temp_dir:
        out_dir = Path(temp_dir)
        files = emitter.emit(graph, out_dir)
        assert len(files) == 1
        with open(files[0]) as f:
            template = json.load(f)
        types = {r["type"] for r in template["resources"]}
        # Managed identity present
        assert "Microsoft.ManagedIdentity/userAssignedIdentities" in types
        # System-assigned identity block present
        vm = next(r for r in template["resources"] if r["name"] == "vmwithsysid")
        assert "identity" in vm and vm["identity"]["type"] == "SystemAssigned"
        # User-assigned identity block present
        webapp = next(r for r in template["resources"] if r["name"] == "webappwithuami")
        assert "identity" in webapp and webapp["identity"]["type"] == "UserAssigned"
        # Role assignment present
        assert "Microsoft.Authorization/roleAssignments" in types
        # Custom role definition present
        assert "Microsoft.Authorization/roleDefinitions" in types
        # Custom role definition has correct properties
        customrole = next(
            r
            for r in template["resources"]
            if r["type"] == "Microsoft.Authorization/roleDefinitions"
        )
        assert customrole["properties"]["roleType"] == "Custom"
