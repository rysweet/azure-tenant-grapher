import datetime
import json
from io import StringIO
from unittest.mock import AsyncMock, MagicMock, patch

import click.testing
import pytest


def _mock_graph():
    from src.iac.traverser import TenantGraph

    g = TenantGraph()
    g.resources = [
        {
            "id": "vm-1",
            "name": "test-vm",
            "type": "Microsoft.Compute/virtualMachines",
            "created": datetime.datetime.now(
                datetime.UTC
            ),  # Use timezone-aware datetime
        }
    ]
    return g


@pytest.mark.asyncio
@patch("src.utils.cli_installer.is_tool_installed", return_value=True)
@patch("src.iac.cli_handler.GraphTraverser")
@patch("src.iac.cli_handler.get_neo4j_driver_from_config")
async def test_dry_run_serialization_fails(
    mock_get_driver, mock_traverser, mock_is_tool
):
    """Test that dry run properly serializes datetime objects to JSON."""
    # Mock traverser to return graph with datetime
    mock_traverser.return_value.traverse = AsyncMock(return_value=_mock_graph())
    mock_get_driver.return_value = MagicMock()

    # Import the handler directly
    from src.iac.cli_handler import generate_iac_command_handler

    # Capture output using click's testing utilities
    runner = click.testing.CliRunner()

    # Run the command handler directly with dry_run=True
    with runner.isolated_filesystem():
        # Capture stdout
        output = StringIO()
        with patch("click.echo") as mock_echo:
            outputs = []

            def capture_output(msg, **kwargs):
                outputs.append(str(msg))

            mock_echo.side_effect = capture_output

            # Run the actual handler
            result = await generate_iac_command_handler(
                tenant_id=None,
                format_type="terraform",
                output_path=None,
                rules_file=None,
                dry_run=True,
                resource_filters=None,
                subset_filter=None,
                node_ids=None,
                dest_rg=None,
                location=None,
                domain_name=None,
            )

            assert result == 0

            # Find the JSON output
            json_output = None
            for output in outputs:
                try:
                    json_output = json.loads(output)
                    break
                except (json.JSONDecodeError, ValueError):
                    continue

            assert json_output is not None, f"No valid JSON found in outputs: {outputs}"
            assert json_output["total_count"] == 1
            assert "created" in json_output["resources"][0]
