import shutil
import subprocess
from pathlib import Path

import pytest

from src.iac.emitters.terraform_emitter import TerraformEmitter
from src.iac.traverser import TenantGraph

terraform = shutil.which("terraform")


@pytest.mark.skipif(
    terraform is None,
    reason="Terraform CLI not found. Install via 'brew install terraform' "
    "or download from https://developer.hashicorp.com/terraform",
)
def test_terraform_validate_passes(tmp_path: Path) -> None:
    # minimal graph with mapped resource types only
    graph = TenantGraph()
    graph.resources = [
        {
            "type": "Microsoft.Storage/storageAccounts",
            "name": "teststorage",
            "location": "East US",
            "resourceGroup": "rg1",
            "tags": {"env": "test"},
        }
    ]
    emitter = TerraformEmitter()
    emitter.emit(graph, tmp_path)

    # init & validate
    assert terraform is not None  # Type guard for mypy
    subprocess.run(
        [
            terraform,
            f"-chdir={tmp_path!s}",
            "init",
            "-backend=false",
            "-input=false",
            "-no-color",
        ],
        check=True,
    )
    proc = subprocess.run(
        [terraform, f"-chdir={tmp_path!s}", "validate", "-no-color"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"terraform validate failed:\n{proc.stdout}\n{proc.stderr}"
    )
