from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import pytest
from click.testing import CliRunner
from scripts.cli import cli

from src.iac.cli_handler import (
    generate_iac_command_handler,
    get_neo4j_driver_from_config,
)


def test_get_driver_returns_driver(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_driver = MagicMock()

    class FakeManager:
        def __init__(self, *a: object, **kw: object) -> None:
            self._driver = None

        def connect(self) -> None:
            self._driver = fake_driver

    monkeypatch.setattr(
        "src.iac.cli_handler.create_session_manager",
        lambda cfg: FakeManager(),  # type: ignore[arg-type]
    )
    monkeypatch.setattr(
        "src.iac.cli_handler.create_neo4j_config_from_env", lambda: MagicMock()
    )

    driver = get_neo4j_driver_from_config()
    assert driver is fake_driver


def test_generate_iac_default_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test CLI parsing for generate-iac with default AAD mode (manual)."""
    called = {}

    async def mock_generate_iac_command_handler(
        tenant_id: Optional[str] = None,
        format_type: str = "terraform",
        output_path: Optional[str] = None,
        rules_file: Optional[str] = None,
        dry_run: bool = False,
        resource_filters: Optional[str] = None,
        subset_filter: Optional[str] = None,
        node_ids: Optional[list[str]] = None,
        dest_rg: Optional[str] = None,
        location: Optional[str] = None,
        skip_validation: bool = False,
        skip_subnet_validation: bool = False,
        auto_fix_subnets: bool = False,
        domain_name: Optional[str] = None,
    ) -> int:
        called["tenant_id"] = tenant_id
        return 0

    # Mock at the correct import location in the CLI script
    monkeypatch.setattr(
        "scripts.cli.generate_iac_command_handler",
        mock_generate_iac_command_handler,
    )

    # Also mock the tool check
    monkeypatch.setattr(
        "src.utils.cli_installer.ensure_tool",
        lambda tool, auto_prompt=False: None,
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["generate-iac", "--tenant-id", "dummy-tenant"],
    )
    assert result.exit_code == 0
    assert called["tenant_id"] == "dummy-tenant"


@pytest.mark.asyncio
async def test_node_id_filter_single(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test Cypher query generation with a single node ID."""
    # Mock Neo4j driver and session
    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_result = MagicMock()

    # Create mock records
    mock_record = MagicMock()
    mock_record.get.side_effect = lambda key: {
        "r": {
            "id": "node-1",
            "type": "Microsoft.Compute/virtualMachines",
            "name": "vm-1",
        },
        "rels": [],
    }.get(key)
    mock_result.__iter__.return_value = iter([mock_record])

    mock_session.run.return_value = mock_result
    mock_driver.session.return_value.__enter__.return_value = mock_session

    # Mock the driver creation
    monkeypatch.setattr(
        "src.iac.cli_handler.get_neo4j_driver_from_config", lambda: mock_driver
    )

    # Mock the GraphTraverser
    mock_graph = MagicMock()
    mock_graph.resources = [
        {"id": "node-1", "type": "Microsoft.Compute/virtualMachines"}
    ]

    mock_traverser = MagicMock()
    mock_traverser.traverse = AsyncMock(return_value=mock_graph)

    monkeypatch.setattr(
        "src.iac.cli_handler.GraphTraverser", lambda driver, rules: mock_traverser
    )

    # Mock emitter
    mock_emitter = MagicMock()
    mock_emitter.emit.return_value = [Path("/tmp/test.tf")]

    monkeypatch.setattr(
        "src.iac.cli_handler.get_emitter", lambda fmt: lambda: mock_emitter
    )

    # Mock engine
    mock_engine = MagicMock()
    mock_engine.apply.side_effect = lambda r: r

    monkeypatch.setattr(
        "src.iac.cli_handler.TransformationEngine", lambda *args, **kwargs: mock_engine
    )

    # Mock DeploymentRegistry
    mock_registry = MagicMock()
    mock_registry.register_deployment.return_value = "test-deployment-id"
    monkeypatch.setattr("src.iac.cli_handler.DeploymentRegistry", lambda: mock_registry)

    # Run the handler
    result = await generate_iac_command_handler(
        node_ids=["node-1"], format_type="terraform", dry_run=False
    )

    assert result == 0

    # Verify that traverse was called with a valid Cypher query
    mock_traverser.traverse.assert_called_once()
    filter_cypher = mock_traverser.traverse.call_args[0][0]

    # Verify Cypher query structure
    assert filter_cypher is not None
    assert "MATCH (n)" in filter_cypher
    assert "WHERE n.id IN ['node-1']" in filter_cypher
    assert "OPTIONAL MATCH (n)-[rel]-(connected)" in filter_cypher
    assert "RETURN n AS r, rels" in filter_cypher
    # Ensure no invalid UNION syntax
    assert "UNION" not in filter_cypher
    assert "WITH DISTINCT n AS node" not in filter_cypher


@pytest.mark.asyncio
async def test_node_id_filter_multiple(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test Cypher query generation with multiple node IDs."""
    # Mock Neo4j driver and session
    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_result = MagicMock()

    # Create mock records for multiple nodes
    mock_records = []
    for i in range(1, 4):
        mock_record = MagicMock()
        mock_record.get.side_effect = lambda key, idx=i: {
            "r": {
                "id": f"node-{idx}",
                "type": "Microsoft.Storage/storageAccounts",
                "name": f"storage-{idx}",
            },
            "rels": [],
        }.get(key)
        mock_records.append(mock_record)

    mock_result.__iter__.return_value = iter(mock_records)
    mock_session.run.return_value = mock_result
    mock_driver.session.return_value.__enter__.return_value = mock_session

    # Mock the driver creation
    monkeypatch.setattr(
        "src.iac.cli_handler.get_neo4j_driver_from_config", lambda: mock_driver
    )

    # Mock the GraphTraverser
    mock_graph = MagicMock()
    mock_graph.resources = [
        {"id": f"node-{i}", "type": "Microsoft.Storage/storageAccounts"}
        for i in range(1, 4)
    ]

    mock_traverser = MagicMock()
    mock_traverser.traverse = AsyncMock(return_value=mock_graph)

    monkeypatch.setattr(
        "src.iac.cli_handler.GraphTraverser", lambda driver, rules: mock_traverser
    )

    # Mock emitter
    mock_emitter = MagicMock()
    mock_emitter.emit.return_value = [Path("/tmp/test.tf")]

    monkeypatch.setattr(
        "src.iac.cli_handler.get_emitter", lambda fmt: lambda: mock_emitter
    )

    # Mock engine
    mock_engine = MagicMock()
    mock_engine.apply.side_effect = lambda r: r

    monkeypatch.setattr(
        "src.iac.cli_handler.TransformationEngine", lambda *args, **kwargs: mock_engine
    )

    # Mock DeploymentRegistry
    mock_registry = MagicMock()
    mock_registry.register_deployment.return_value = "test-deployment-id"
    monkeypatch.setattr("src.iac.cli_handler.DeploymentRegistry", lambda: mock_registry)

    # Run the handler with multiple node IDs
    node_ids = ["node-1", "node-2", "node-3"]
    result = await generate_iac_command_handler(
        node_ids=node_ids, format_type="terraform", dry_run=False
    )

    assert result == 0

    # Verify that traverse was called with a valid Cypher query
    mock_traverser.traverse.assert_called_once()
    filter_cypher = mock_traverser.traverse.call_args[0][0]

    # Verify Cypher query structure
    assert filter_cypher is not None
    assert "MATCH (n)" in filter_cypher
    assert "WHERE n.id IN ['node-1', 'node-2', 'node-3']" in filter_cypher
    assert "OPTIONAL MATCH (n)-[rel]-(connected)" in filter_cypher
    assert "collect(DISTINCT" in filter_cypher
    assert "RETURN n AS r, rels" in filter_cypher
    # Ensure no invalid UNION syntax
    assert "UNION" not in filter_cypher


@pytest.mark.asyncio
async def test_node_id_filter_with_relationships(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that node ID filter properly handles relationships."""
    # Mock Neo4j driver and session
    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_result = MagicMock()

    # Create mock record with relationships
    mock_record = MagicMock()
    mock_record.get.side_effect = lambda key: {
        "r": {
            "id": "node-1",
            "type": "Microsoft.Network/virtualNetworks",
            "name": "vnet-1",
        },
        "rels": [
            {"type": "CONTAINS", "target": "subnet-1"},
            {"type": "CONNECTED_TO", "target": "node-2"},
        ],
    }.get(key)
    mock_result.__iter__.return_value = iter([mock_record])

    mock_session.run.return_value = mock_result
    mock_driver.session.return_value.__enter__.return_value = mock_session

    # Mock the driver creation
    monkeypatch.setattr(
        "src.iac.cli_handler.get_neo4j_driver_from_config", lambda: mock_driver
    )

    # Mock the GraphTraverser
    mock_graph = MagicMock()
    mock_graph.resources = [
        {"id": "node-1", "type": "Microsoft.Network/virtualNetworks"}
    ]

    mock_traverser = MagicMock()
    mock_traverser.traverse = AsyncMock(return_value=mock_graph)

    monkeypatch.setattr(
        "src.iac.cli_handler.GraphTraverser", lambda driver, rules: mock_traverser
    )

    # Mock emitter
    mock_emitter = MagicMock()
    mock_emitter.emit.return_value = [Path("/tmp/test.tf")]

    monkeypatch.setattr(
        "src.iac.cli_handler.get_emitter", lambda fmt: lambda: mock_emitter
    )

    # Mock engine
    mock_engine = MagicMock()
    mock_engine.apply.side_effect = lambda r: r

    monkeypatch.setattr(
        "src.iac.cli_handler.TransformationEngine", lambda *args, **kwargs: mock_engine
    )

    # Mock DeploymentRegistry
    mock_registry = MagicMock()
    mock_registry.register_deployment.return_value = "test-deployment-id"
    monkeypatch.setattr("src.iac.cli_handler.DeploymentRegistry", lambda: mock_registry)

    # Run the handler
    result = await generate_iac_command_handler(
        node_ids=["node-1"], format_type="terraform", dry_run=False
    )

    assert result == 0

    # Verify the Cypher query includes relationship handling
    filter_cypher = mock_traverser.traverse.call_args[0][0]
    assert "type: type(rel)" in filter_cypher
    assert "target: connected.id" in filter_cypher
    assert "original_type: rel.original_type" in filter_cypher
    assert "narrative_context: rel.narrative_context" in filter_cypher
