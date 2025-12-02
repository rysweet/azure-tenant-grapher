"""Security tests for CLI handler - Issue #524 Cypher injection prevention.

This test module validates that the CLI handler properly prevents Cypher injection
attacks through input validation and parameterized queries.
"""

import os
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.iac.cli_handler import generate_iac_command_handler


@pytest.fixture(autouse=True)
def setup_azure_env():
    """Set up minimal Azure environment variables for all tests."""
    os.environ["AZURE_CLIENT_ID"] = "test-client-id"
    os.environ["AZURE_CLIENT_SECRET"] = "test-secret"
    os.environ["AZURE_TENANT_ID"] = "test-tenant-id"
    os.environ["AZURE_SUBSCRIPTION_ID"] = "test-subscription-id"
    yield
    # Cleanup
    for key in ["AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "AZURE_TENANT_ID", "AZURE_SUBSCRIPTION_ID"]:
        os.environ.pop(key, None)


@pytest.fixture
def mock_azure_credential(monkeypatch: pytest.MonkeyPatch):
    """Mock Azure credential for all tests."""
    mock_credential = MagicMock()
    # Mock at azure.identity level since it's imported inside the function
    monkeypatch.setattr(
        "azure.identity.ClientSecretCredential", lambda *args, **kwargs: mock_credential
    )
    return mock_credential


@pytest.mark.asyncio
async def test_node_ids_injection_prevented(
    monkeypatch: pytest.MonkeyPatch, mock_azure_credential: MagicMock
) -> None:
    """Test that malicious node IDs cannot inject Cypher commands."""
    # Mock Neo4j driver
    mock_driver = MagicMock()
    monkeypatch.setattr(
        "src.iac.cli_handler.get_neo4j_driver_from_config", lambda: mock_driver
    )

    # Mock GraphTraverser to capture query and parameters
    captured_query = None
    captured_params = None

    async def mock_traverse(query, parameters=None):
        nonlocal captured_query, captured_params
        captured_query = query
        captured_params = parameters
        mock_graph = MagicMock()
        mock_graph.resources = []
        return mock_graph

    mock_traverser = MagicMock()
    mock_traverser.traverse = mock_traverse

    monkeypatch.setattr(
        "src.iac.cli_handler.GraphTraverser", lambda driver, rules: mock_traverser
    )

    # Mock emitter and other components
    mock_emitter_instance = MagicMock()
    mock_emitter_instance.emit.return_value = [Path("/tmp/test.tf")]

    class MockEmitterClass:
        def __init__(self, *args, **kwargs):
            pass

        def emit(self, *args, **kwargs):
            return mock_emitter_instance.emit(*args, **kwargs)

    monkeypatch.setattr(
        "src.iac.cli_handler.get_emitter", lambda fmt: MockEmitterClass
    )

    mock_engine = MagicMock()
    mock_engine.apply.side_effect = lambda r: r
    monkeypatch.setattr(
        "src.iac.cli_handler.TransformationEngine", lambda *args, **kwargs: mock_engine
    )

    mock_registry = MagicMock()
    mock_registry.register_deployment.return_value = "test-deployment-id"
    monkeypatch.setattr("src.iac.cli_handler.DeploymentRegistry", lambda: mock_registry)

    # Test with malicious node IDs attempting injection
    malicious_node_ids = [
        "node-1",
        "node-2' OR 1=1 --",  # SQL injection style
    ]

    result = await generate_iac_command_handler(
        node_ids=malicious_node_ids,
        format_type="terraform",
        dry_run=False,
    )

    assert result == 0

    # Verify parameterized query was used
    assert captured_query is not None
    assert "$node_ids" in captured_query
    assert "WHERE n.id IN $node_ids" in captured_query

    # Verify NO direct string interpolation in query
    assert "node-1" not in captured_query
    assert "node-2" not in captured_query
    assert "OR 1=1" not in captured_query

    # Verify parameters contain the values
    assert captured_params is not None
    assert "node_ids" in captured_params
    assert malicious_node_ids[0] in captured_params["node_ids"]
    assert malicious_node_ids[1] in captured_params["node_ids"]


@pytest.mark.asyncio
async def test_property_name_whitelist_enforcement(
    monkeypatch: pytest.MonkeyPatch, mock_azure_credential: MagicMock
) -> None:
    """Test that only whitelisted property names are allowed in filters."""
    # Mock Neo4j driver
    mock_driver = MagicMock()
    monkeypatch.setattr(
        "src.iac.cli_handler.get_neo4j_driver_from_config", lambda: mock_driver
    )

    # Mock GraphTraverser
    mock_graph = MagicMock()
    mock_graph.resources = []
    mock_traverser = MagicMock()
    mock_traverser.traverse = AsyncMock(return_value=mock_graph)

    monkeypatch.setattr(
        "src.iac.cli_handler.GraphTraverser", lambda driver, rules: mock_traverser
    )

    # Test with invalid property name (not in whitelist)
    result = await generate_iac_command_handler(
        resource_filters="malicious_property='value'",
        format_type="terraform",
        dry_run=False,
    )
    assert result == 1  # Should fail with error code

    # Test with SQL injection attempt in property name
    result = await generate_iac_command_handler(
        resource_filters="type; DROP TABLE users--='value'",
        format_type="terraform",
        dry_run=False,
    )
    assert result == 1  # Should fail with error code


@pytest.mark.asyncio
async def test_pattern_quote_validation(monkeypatch: pytest.MonkeyPatch, mock_azure_credential: MagicMock) -> None:
    """Test that patterns must be properly quoted."""
    # Mock Neo4j driver
    mock_driver = MagicMock()
    monkeypatch.setattr(
        "src.iac.cli_handler.get_neo4j_driver_from_config", lambda: mock_driver
    )

    # Mock GraphTraverser
    mock_graph = MagicMock()
    mock_graph.resources = []
    mock_traverser = MagicMock()
    mock_traverser.traverse = AsyncMock(return_value=mock_graph)

    monkeypatch.setattr(
        "src.iac.cli_handler.GraphTraverser", lambda driver, rules: mock_traverser
    )

    # Test with unquoted pattern (security risk)
    result = await generate_iac_command_handler(
        resource_filters="resourceGroup=myRG",  # Missing quotes
        format_type="terraform",
        dry_run=False,
    )
    assert result == 1  # Should fail with error code

    # Test with malicious unquoted pattern
    result = await generate_iac_command_handler(
        resource_filters="resourceGroup=value' OR '1'='1",  # SQL injection attempt
        format_type="terraform",
        dry_run=False,
    )
    assert result == 1  # Should fail with error code


@pytest.mark.asyncio
async def test_type_filter_character_validation(monkeypatch: pytest.MonkeyPatch, mock_azure_credential: MagicMock) -> None:
    """Test that type filters reject suspicious characters."""
    # Mock Neo4j driver
    mock_driver = MagicMock()
    monkeypatch.setattr(
        "src.iac.cli_handler.get_neo4j_driver_from_config", lambda: mock_driver
    )

    # Mock GraphTraverser
    mock_graph = MagicMock()
    mock_graph.resources = []
    mock_traverser = MagicMock()
    mock_traverser.traverse = AsyncMock(return_value=mock_graph)

    monkeypatch.setattr(
        "src.iac.cli_handler.GraphTraverser", lambda driver, rules: mock_traverser
    )

    # Test type filters with suspicious characters
    suspicious_filters = [
        "Microsoft.Network'; DROP TABLE resources--",
        'Microsoft.Network"; DELETE FROM resources--',
        "Microsoft.Network`; MATCH (n) DELETE n--",
        "Microsoft.Network/* comment */",
    ]

    for suspicious_filter in suspicious_filters:
        result = await generate_iac_command_handler(
            resource_filters=suspicious_filter,
            format_type="terraform",
            dry_run=False,
        )
        assert result == 1  # Should fail with error code


@pytest.mark.asyncio
async def test_parameterized_property_filter(monkeypatch: pytest.MonkeyPatch, mock_azure_credential: MagicMock) -> None:
    """Test that property filters use parameterized queries."""
    # Mock Neo4j driver
    mock_driver = MagicMock()
    monkeypatch.setattr(
        "src.iac.cli_handler.get_neo4j_driver_from_config", lambda: mock_driver
    )

    # Mock GraphTraverser to capture query and parameters
    captured_query = None
    captured_params = None

    async def mock_traverse(query, parameters=None):
        nonlocal captured_query, captured_params
        captured_query = query
        captured_params = parameters
        mock_graph = MagicMock()
        mock_graph.resources = []
        return mock_graph

    mock_traverser = MagicMock()
    mock_traverser.traverse = mock_traverse

    monkeypatch.setattr(
        "src.iac.cli_handler.GraphTraverser", lambda driver, rules: mock_traverser
    )

    # Mock emitter and other components
    mock_emitter_instance = MagicMock()
    mock_emitter_instance.emit.return_value = [Path("/tmp/test.tf")]

    class MockEmitterClass:
        def __init__(self, *args, **kwargs):
            pass

        def emit(self, *args, **kwargs):
            return mock_emitter_instance.emit(*args, **kwargs)

    monkeypatch.setattr(
        "src.iac.cli_handler.get_emitter", lambda fmt: MockEmitterClass
    )

    mock_engine = MagicMock()
    mock_engine.apply.side_effect = lambda r: r
    monkeypatch.setattr(
        "src.iac.cli_handler.TransformationEngine", lambda *args, **kwargs: mock_engine
    )

    mock_registry = MagicMock()
    mock_registry.register_deployment.return_value = "test-deployment-id"
    monkeypatch.setattr("src.iac.cli_handler.DeploymentRegistry", lambda: mock_registry)

    # Test with property filter
    result = await generate_iac_command_handler(
        resource_filters="resourceGroup='myRG'",
        format_type="terraform",
        dry_run=False,
    )

    assert result == 0

    # Verify parameterized query was used
    assert captured_query is not None
    assert "$filter_value_0" in captured_query
    assert "r.resource_group = $filter_value_0" in captured_query

    # Verify NO direct value interpolation
    assert "'myRG'" not in captured_query

    # Verify parameters contain the unquoted value
    assert captured_params is not None
    assert "filter_value_0" in captured_params
    assert captured_params["filter_value_0"] == "myRG"


@pytest.mark.asyncio
async def test_regex_filter_parameterization(monkeypatch: pytest.MonkeyPatch, mock_azure_credential: MagicMock) -> None:
    """Test that regex filters are properly parameterized."""
    # Mock Neo4j driver
    mock_driver = MagicMock()
    monkeypatch.setattr(
        "src.iac.cli_handler.get_neo4j_driver_from_config", lambda: mock_driver
    )

    # Mock GraphTraverser to capture query and parameters
    captured_query = None
    captured_params = None

    async def mock_traverse(query, parameters=None):
        nonlocal captured_query, captured_params
        captured_query = query
        captured_params = parameters
        mock_graph = MagicMock()
        mock_graph.resources = []
        return mock_graph

    mock_traverser = MagicMock()
    mock_traverser.traverse = mock_traverse

    monkeypatch.setattr(
        "src.iac.cli_handler.GraphTraverser", lambda driver, rules: mock_traverser
    )

    # Mock emitter and other components
    mock_emitter_instance = MagicMock()
    mock_emitter_instance.emit.return_value = [Path("/tmp/test.tf")]

    class MockEmitterClass:
        def __init__(self, *args, **kwargs):
            pass

        def emit(self, *args, **kwargs):
            return mock_emitter_instance.emit(*args, **kwargs)

    monkeypatch.setattr(
        "src.iac.cli_handler.get_emitter", lambda fmt: MockEmitterClass
    )

    mock_engine = MagicMock()
    mock_engine.apply.side_effect = lambda r: r
    monkeypatch.setattr(
        "src.iac.cli_handler.TransformationEngine", lambda *args, **kwargs: mock_engine
    )

    mock_registry = MagicMock()
    mock_registry.register_deployment.return_value = "test-deployment-id"
    monkeypatch.setattr("src.iac.cli_handler.DeploymentRegistry", lambda: mock_registry)

    # Test with regex filter
    regex_pattern = "(?i).*(simuland|SimuLand).*"
    result = await generate_iac_command_handler(
        resource_filters=f"resourceGroup=~'{regex_pattern}'",
        format_type="terraform",
        dry_run=False,
    )

    assert result == 0

    # Verify parameterized query with regex operator
    assert captured_query is not None
    assert "$filter_value_0" in captured_query
    assert "r.resource_group =~ $filter_value_0" in captured_query

    # Verify pattern is NOT embedded in query
    assert "simuland" not in captured_query.lower()

    # Verify parameters contain the pattern
    assert captured_params is not None
    assert "filter_value_0" in captured_params
    assert captured_params["filter_value_0"] == regex_pattern


@pytest.mark.asyncio
async def test_empty_node_id_rejected(monkeypatch: pytest.MonkeyPatch, mock_azure_credential: MagicMock) -> None:
    """Test that empty or whitespace-only node IDs are rejected."""
    # Mock Neo4j driver
    mock_driver = MagicMock()
    monkeypatch.setattr(
        "src.iac.cli_handler.get_neo4j_driver_from_config", lambda: mock_driver
    )

    # Mock GraphTraverser
    mock_graph = MagicMock()
    mock_graph.resources = []
    mock_traverser = MagicMock()
    mock_traverser.traverse = AsyncMock(return_value=mock_graph)

    monkeypatch.setattr(
        "src.iac.cli_handler.GraphTraverser", lambda driver, rules: mock_traverser
    )

    # Test with empty node ID
    result = await generate_iac_command_handler(
        node_ids=["node-1", "", "node-2"],
        format_type="terraform",
        dry_run=False,
    )
    assert result == 1  # Should fail with error code

    # Test with whitespace-only node ID
    result = await generate_iac_command_handler(
        node_ids=["node-1", "   ", "node-2"],
        format_type="terraform",
        dry_run=False,
    )
    assert result == 1  # Should fail with error code


@pytest.mark.asyncio
async def test_multiple_filters_all_parameterized(
    monkeypatch: pytest.MonkeyPatch, mock_azure_credential: MagicMock
) -> None:
    """Test that multiple filters are all parameterized correctly."""
    # Mock Neo4j driver
    mock_driver = MagicMock()
    monkeypatch.setattr(
        "src.iac.cli_handler.get_neo4j_driver_from_config", lambda: mock_driver
    )

    # Mock GraphTraverser to capture query and parameters
    captured_query = None
    captured_params = None

    async def mock_traverse(query, parameters=None):
        nonlocal captured_query, captured_params
        captured_query = query
        captured_params = parameters
        mock_graph = MagicMock()
        mock_graph.resources = []
        return mock_graph

    mock_traverser = MagicMock()
    mock_traverser.traverse = mock_traverse

    monkeypatch.setattr(
        "src.iac.cli_handler.GraphTraverser", lambda driver, rules: mock_traverser
    )

    # Mock emitter and other components
    mock_emitter_instance = MagicMock()
    mock_emitter_instance.emit.return_value = [Path("/tmp/test.tf")]

    class MockEmitterClass:
        def __init__(self, *args, **kwargs):
            pass

        def emit(self, *args, **kwargs):
            return mock_emitter_instance.emit(*args, **kwargs)

    monkeypatch.setattr(
        "src.iac.cli_handler.get_emitter", lambda fmt: MockEmitterClass
    )

    mock_engine = MagicMock()
    mock_engine.apply.side_effect = lambda r: r
    monkeypatch.setattr(
        "src.iac.cli_handler.TransformationEngine", lambda *args, **kwargs: mock_engine
    )

    mock_registry = MagicMock()
    mock_registry.register_deployment.return_value = "test-deployment-id"
    monkeypatch.setattr("src.iac.cli_handler.DeploymentRegistry", lambda: mock_registry)

    # Test with multiple filters (property + type)
    result = await generate_iac_command_handler(
        resource_filters="resourceGroup='myRG',Microsoft.Network/virtualNetworks",
        format_type="terraform",
        dry_run=False,
    )

    assert result == 0

    # Verify both filters are parameterized
    assert captured_query is not None
    assert "$filter_value_0" in captured_query  # Property filter
    assert "$filter_type_1" in captured_query  # Type filter

    # Verify NO direct values in query
    assert "'myRG'" not in captured_query
    assert "virtualNetworks" not in captured_query

    # Verify parameters contain both values
    assert captured_params is not None
    assert "filter_value_0" in captured_params
    assert "filter_type_1" in captured_params
    assert captured_params["filter_value_0"] == "myRG"
    assert captured_params["filter_type_1"] == "Microsoft.Network/virtualNetworks"
