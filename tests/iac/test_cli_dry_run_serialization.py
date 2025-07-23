import datetime
import json
import subprocess
from unittest.mock import AsyncMock, MagicMock, patch


def _mock_graph():
    from src.iac.traverser import TenantGraph

    g = TenantGraph()
    g.resources = [
        {
            "id": "vm-1",
            "name": "test-vm",
            "type": "Microsoft.Compute/virtualMachines",
            "created": datetime.datetime.utcnow(),
        }
    ]
    return g


@patch("src.utils.cli_installer.is_tool_installed", return_value=True)
@patch("src.iac.cli_handler.GraphTraverser")
@patch("src.iac.cli_handler.get_neo4j_driver_from_config")
def test_dry_run_serialization_fails(mock_get_driver, mock_traverser, mock_is_tool):
    # mock traverser to return graph with datetime
    mock_traverser.return_value.traverse = AsyncMock(return_value=_mock_graph())
    mock_get_driver.return_value = MagicMock()

    result = subprocess.run(
        ["uv", "run", "scripts/cli.py", "generate-iac", "--dry-run"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["total_count"] == 1
    assert "created" in data["resources"][0]
