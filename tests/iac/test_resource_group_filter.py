"""Integration tests for resource group filtering in IaC generation."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.iac.cli_handler import generate_iac_command_handler


@pytest.mark.asyncio
async def test_resource_group_regex_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that resource group regex filtering generates correct Cypher and filters resources."""
    # Mock Neo4j driver and session
    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_result = MagicMock()

    # Create mock records with different resource groups
    mock_records = []
    test_resources = [
        {
            "id": "vm-1",
            "type": "Microsoft.Compute/virtualMachines",
            "name": "vm-1",
            "resourceGroup": "simuland",
        },
        {
            "id": "vm-2",
            "type": "Microsoft.Compute/virtualMachines",
            "name": "vm-2",
            "resourceGroup": "simuland_api",
        },
        {
            "id": "vm-3",
            "type": "Microsoft.Compute/virtualMachines",
            "name": "vm-3",
            "resourceGroup": "production",
        },
    ]

    for resource in test_resources:
        mock_record = MagicMock()
        mock_record.get.side_effect = lambda key, r=resource: {
            "r": r,
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
    mock_graph.resources = test_resources

    mock_traverser = MagicMock()
    mock_traverser.traverse = AsyncMock(return_value=mock_graph)

    monkeypatch.setattr(
        "src.iac.cli_handler.GraphTraverser", lambda driver, rules: mock_traverser
    )

    # Mock emitter
    mock_emitter = MagicMock()
    mock_emitter.emit.return_value = [Path("/tmp/test.tf")]
    mock_emitter.get_import_blocks_count.return_value = 0
    mock_emitter.get_resource_count.return_value = 0
    mock_emitter.get_files_created_count.return_value = 1
    mock_emitter.get_translation_stats.return_value = {}

    monkeypatch.setattr(
        "src.iac.cli_handler.get_emitter", lambda fmt: lambda **kwargs: mock_emitter
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

    # Run the handler with resource group regex filter (case-insensitive simuland pattern)
    result = await generate_iac_command_handler(
        resource_filters="resourceGroup=~'(?i).*(simuland|SimuLand).*'",
        format_type="terraform",
        dry_run=False,
        skip_name_validation=True,  # Skip name validation for this test
    )

    assert result == 0

    # Verify that traverse was called with a valid Cypher query
    mock_traverser.traverse.assert_called_once()
    filter_cypher = mock_traverser.traverse.call_args[0][0]

    # Verify Cypher query structure
    assert filter_cypher is not None
    assert "MATCH (r:Resource)" in filter_cypher
    # Verify the regex filter is applied to both field name variations
    assert "r.resource_group =~ '(?i).*(simuland|SimuLand).*'" in filter_cypher
    assert "r.resourceGroup =~ '(?i).*(simuland|SimuLand).*'" in filter_cypher
    assert "OR" in filter_cypher  # Ensures both field names are checked


@pytest.mark.asyncio
async def test_resource_group_exact_match_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that exact resource group name filtering works correctly."""
    # Mock Neo4j driver and session
    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_result = MagicMock()

    # Create mock record
    mock_record = MagicMock()
    mock_record.get.side_effect = lambda key: {
        "r": {
            "id": "vm-1",
            "type": "Microsoft.Compute/virtualMachines",
            "name": "vm-1",
            "resourceGroup": "simuland",
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
        {
            "id": "vm-1",
            "type": "Microsoft.Compute/virtualMachines",
            "resourceGroup": "simuland",
        }
    ]

    mock_traverser = MagicMock()
    mock_traverser.traverse = AsyncMock(return_value=mock_graph)

    monkeypatch.setattr(
        "src.iac.cli_handler.GraphTraverser", lambda driver, rules: mock_traverser
    )

    # Mock emitter
    mock_emitter = MagicMock()
    mock_emitter.emit.return_value = [Path("/tmp/test.tf")]
    mock_emitter.get_import_blocks_count.return_value = 0
    mock_emitter.get_resource_count.return_value = 0
    mock_emitter.get_files_created_count.return_value = 1
    mock_emitter.get_translation_stats.return_value = {}

    monkeypatch.setattr(
        "src.iac.cli_handler.get_emitter", lambda fmt: lambda **kwargs: mock_emitter
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

    # Run the handler with exact resource group name filter
    result = await generate_iac_command_handler(
        resource_filters="resourceGroup='simuland'",
        format_type="terraform",
        dry_run=False,
        skip_name_validation=True,  # Skip name validation for this test
    )

    assert result == 0

    # Verify that traverse was called with a valid Cypher query
    mock_traverser.traverse.assert_called_once()
    filter_cypher = mock_traverser.traverse.call_args[0][0]

    # Verify Cypher query structure
    assert filter_cypher is not None
    assert "MATCH (r:Resource)" in filter_cypher
    # Verify exact match filter is applied to both field name variations
    assert "r.resource_group = 'simuland'" in filter_cypher
    assert "r.resourceGroup = 'simuland'" in filter_cypher
    assert "OR" in filter_cypher


@pytest.mark.asyncio
async def test_mixed_type_and_resource_group_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that type and resource group filters can be combined."""
    # Mock Neo4j driver and session
    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_result = MagicMock()

    # Create mock record
    mock_record = MagicMock()
    mock_record.get.side_effect = lambda key: {
        "r": {
            "id": "vnet-1",
            "type": "Microsoft.Network/virtualNetworks",
            "name": "vnet-1",
            "resourceGroup": "simuland",
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
        {
            "id": "vnet-1",
            "type": "Microsoft.Network/virtualNetworks",
            "resourceGroup": "simuland",
        }
    ]

    mock_traverser = MagicMock()
    mock_traverser.traverse = AsyncMock(return_value=mock_graph)

    monkeypatch.setattr(
        "src.iac.cli_handler.GraphTraverser", lambda driver, rules: mock_traverser
    )

    # Mock emitter
    mock_emitter = MagicMock()
    mock_emitter.emit.return_value = [Path("/tmp/test.tf")]
    mock_emitter.get_import_blocks_count.return_value = 0
    mock_emitter.get_resource_count.return_value = 0
    mock_emitter.get_files_created_count.return_value = 1
    mock_emitter.get_translation_stats.return_value = {}

    monkeypatch.setattr(
        "src.iac.cli_handler.get_emitter", lambda fmt: lambda **kwargs: mock_emitter
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

    # Run the handler with mixed filters (type AND resource group)
    result = await generate_iac_command_handler(
        resource_filters="Microsoft.Network/virtualNetworks,resourceGroup=~'(?i).*simuland.*'",
        format_type="terraform",
        dry_run=False,
        skip_name_validation=True,  # Skip name validation for this test
    )

    assert result == 0

    # Verify that traverse was called with a valid Cypher query
    mock_traverser.traverse.assert_called_once()
    filter_cypher = mock_traverser.traverse.call_args[0][0]

    # Verify Cypher query structure includes both filters connected with OR
    assert filter_cypher is not None
    assert "MATCH (r:Resource)" in filter_cypher
    assert "r.type = 'Microsoft.Network/virtualNetworks'" in filter_cypher
    assert "r.resource_group =~ '(?i).*simuland.*'" in filter_cypher
    assert "r.resourceGroup =~ '(?i).*simuland.*'" in filter_cypher
    assert "OR" in filter_cypher  # Multiple OR conditions for different filters
