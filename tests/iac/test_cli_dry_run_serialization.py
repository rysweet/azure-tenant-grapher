import datetime
import json
from click.testing import CliRunner
from unittest.mock import MagicMock, patch, AsyncMock
from scripts.cli import cli

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

@patch("src.iac.cli_handler.GraphTraverser")
@patch("src.iac.cli_handler.get_neo4j_driver_from_config")
def test_dry_run_serialization_fails(mock_get_driver, mock_traverser):
    # mock traverser to return graph with datetime
    mock_traverser.return_value.traverse = AsyncMock(return_value=_mock_graph())
    mock_get_driver.return_value = MagicMock()

    runner = CliRunner()
    result = runner.invoke(cli, ["generate-iac", "--dry-run"])
    # should not raise TypeError after fix
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["total_count"] == 1
    assert "created" in data["resources"][0]