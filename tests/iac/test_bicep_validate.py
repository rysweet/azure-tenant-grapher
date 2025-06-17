import shutil
import subprocess
from pathlib import Path

import pytest

from src.iac.emitters.bicep_emitter import BicepEmitter
from src.iac.traverser import TenantGraph

bicep = shutil.which("bicep")


@pytest.mark.skipif(
    bicep is None,
    reason="Bicep CLI not found. Install via 'brew install bicep', 'choco install bicep', or see https://docs.microsoft.com/azure/azure-resource-manager/bicep/install",
)
def test_bicep_template_builds(tmp_path: Path) -> None:
    # Minimal Bicep graph
    graph = TenantGraph()
    graph.resources = [
        {
            "type": "Microsoft.Storage/storageAccounts",
            "name": "teststorage",
            "location": "eastus",
            "tags": {"env": "test"},
        }
    ]
    emitter = BicepEmitter()
    files = emitter.emit(graph, tmp_path)
    assert len(files) == 1
    bicep_path = files[0]
    assert bicep_path.name == "main.bicep"

    # Run bicep build
    proc = subprocess.run(
        [bicep, "build", str(bicep_path)], capture_output=True, text=True
    )
    assert proc.returncode == 0, f"bicep build failed:\n{proc.stdout}\n{proc.stderr}"
