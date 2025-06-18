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
