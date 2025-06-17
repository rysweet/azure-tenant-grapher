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
