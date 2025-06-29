import tempfile
from pathlib import Path

from src.iac.emitters.bicep_emitter import BicepEmitter
from src.iac.traverser import TenantGraph


def test_bicep_emitter_creates_valid_template():
    emitter = BicepEmitter()
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
        file_names = [f.name for f in files]
        assert "main.bicep" in file_names
        assert files[0].name == "main.bicep"
        with open(files[0]) as f:
            content = f.read()
        # Check Bicep template structure
        assert (
            "resource teststorage_res 'Microsoft.Storage/storageAccounts@2023-01-01'"
            in content
        )
        # Accept any API version for the VM resource
        assert "resource testvm_res 'Microsoft.Compute/virtualMachines@" in content
        assert "location: 'eastus'" in content
        assert "location: 'eastus2'" in content
        assert "tags: { env: 'test' }" in content


def test_bicep_emitter_identities_and_rbac():
    import tempfile
    from pathlib import Path

    from src.iac.emitters.bicep_emitter import BicepEmitter
    from src.iac.traverser import TenantGraph

    emitter = BicepEmitter()
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
        main_bicep = next(f for f in files if f.name == "main.bicep")
        with open(main_bicep) as f:
            content = f.read()
        # Managed identity present
        assert (
            "resource myuami_identity 'Microsoft.ManagedIdentity/userAssignedIdentities@"
            in content
        )
        # System-assigned identity block present
        assert "resource vmwithsysid_res 'Microsoft.Compute/virtualMachines@" in content
        assert "identity: { type: 'SystemAssigned' }" in content
        # User-assigned identity block present
        assert "resource webappwithuami_res 'Microsoft.Web/sites@" in content
        assert "identity: {" in content and "type: 'UserAssigned'" in content
        # Role assignment present
        assert "resource myra_ra 'Microsoft.Authorization/roleAssignments@" in content
        # Custom role definition present
        assert (
            "resource mycustomrole_rd 'Microsoft.Authorization/roleDefinitions@"
            in content
        )
        # Custom role definition has correct properties
        assert "roleType: 'Custom'" in content
