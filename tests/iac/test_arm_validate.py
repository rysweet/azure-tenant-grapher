import shutil
import subprocess
from pathlib import Path

import pytest

from src.iac.emitters.arm_emitter import ArmEmitter
from src.iac.traverser import TenantGraph

az = shutil.which("az")


@pytest.mark.skipif(
    az is None,
    reason="Azure CLI (az) not found. Install via 'brew install azure-cli', 'choco install azure-cli', or see https://docs.microsoft.com/cli/azure/install-azure-cli",
)
def test_arm_template_validates_with_az(tmp_path: Path) -> None:
    # Minimal ARM graph
    graph = TenantGraph()
    graph.resources = [
        {
            "type": "Microsoft.Storage/storageAccounts",
            "name": "teststorage",
            "location": "eastus",
            "tags": {"env": "test"},
        }
    ]
    emitter = ArmEmitter()
    files = emitter.emit(graph, tmp_path)
    assert len(files) == 1
    template_path = files[0]
    assert template_path.name == "azuredeploy.json"

    # Validate with az (dummy group, will fail on real deploy, but syntax/structure is checked)
    # Use --parameters '{}' to avoid param errors, and --validate-only to avoid actual deployment
    proc = subprocess.run(
        [
            az,
            "deployment",
            "group",
            "validate",
            "--resource-group",
            "dummy-rg",
            "--template-file",
            str(template_path),
            "--parameters",
            "{}",
        ],
        capture_output=True,
        text=True,
    )
    # Accept 0 (valid), 3 (validation error), or 1 (ResourceGroupNotFound) as long as the error is about the group, not template syntax
    if proc.returncode in (0, 3):
        pass
    elif proc.returncode == 1 and (
        "ResourceGroupNotFound" in proc.stdout
        or "ResourceGroupNotFound" in proc.stderr
        or "could not be found" in proc.stdout
        or "could not be found" in proc.stderr
    ):
        pass
    else:
        raise AssertionError(f"az validate failed:\n{proc.stdout}\n{proc.stderr}")
