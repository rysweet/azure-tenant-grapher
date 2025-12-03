"""
Unit tests for LayerExportOperations (Issue #570 - TDD Approach)

Test Coverage (60% of testing pyramid - UNIT TESTS):
- copy_layer preserves SCAN_SOURCE_NODE relationships
- archive_layer includes SCAN_SOURCE_NODE in JSON
- restore_layer recreates SCAN_SOURCE_NODE relationships
- Layer isolation is maintained (no cross-layer contamination)

Philosophy:
- All tests should FAIL before fix is implemented
- Fast tests (<100ms per test)
- Isolated tests (no test dependencies)
- Clear test names describe what is verified
"""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.services.layer.export import LayerExportOperations
from src.services.layer.models import LayerMetadata, LayerType
from src.utils.session_manager import Neo4jSessionManager


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_session_manager():
    """Mock Neo4j session manager for unit tests."""
    mock_manager = Mock(spec=Neo4jSessionManager)
    mock_session = MagicMock()

    # Mock the context manager behavior
    mock_manager.session.return_value.__enter__.return_value = mock_session
    mock_manager.session.return_value.__exit__.return_value = None

    return mock_manager, mock_session


@pytest.fixture
def mock_crud_operations():
    """Mock CRUD operations for layer metadata."""
    mock_crud = AsyncMock()

    # Default layer metadata
    source_layer = LayerMetadata(
        layer_id="source-layer",
        name="Source Layer",
        description="Test source layer",
        created_at=datetime.utcnow(),
        tenant_id="test-tenant",
        layer_type=LayerType.BASELINE,
    )

    mock_crud.get_layer.return_value = source_layer
    mock_crud.create_layer.return_value = None

    return mock_crud


@pytest.fixture
def mock_stats_operations():
    """Mock stats operations for layer statistics."""
    mock_stats = AsyncMock()
    mock_stats.refresh_layer_stats.return_value = None
    return mock_stats


@pytest.fixture
def export_operations(mock_session_manager, mock_crud_operations, mock_stats_operations):
    """Create LayerExportOperations instance with mocked dependencies."""
    session_manager, _ = mock_session_manager
    return LayerExportOperations(
        session_manager=session_manager,
        crud_operations=mock_crud_operations,
        stats_operations=mock_stats_operations,
    )


@pytest.fixture
def sample_nodes():
    """Sample Resource nodes for testing."""
    return [
        {
            "id": "/subscriptions/test-sub/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "layer_id": "source-layer",
        },
        {
            "id": "/subscriptions/test-sub/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1",
            "name": "vnet1",
            "type": "Microsoft.Network/virtualNetworks",
            "layer_id": "source-layer",
        },
    ]


@pytest.fixture
def sample_original_nodes():
    """Sample Original nodes (scan results) for testing."""
    return [
        {
            "id": "/subscriptions/test-sub/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1_original",
            "name": "vm1_original",
            "type": "Microsoft.Compute/virtualMachines",
        },
        {
            "id": "/subscriptions/test-sub/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1_original",
            "name": "vnet1_original",
            "type": "Microsoft.Network/virtualNetworks",
        },
    ]


# =============================================================================
# Unit Tests - copy_layer (EXPECTED TO FAIL)
# =============================================================================


@pytest.mark.asyncio
async def test_copy_layer_preserves_scan_source_node(
    export_operations,
    mock_session_manager,
    sample_nodes,
    sample_original_nodes,
):
    """
    Test that copy_layer preserves SCAN_SOURCE_NODE relationships.

    THIS TEST SHOULD FAIL before fix is implemented because:
    - Line 166 in export.py explicitly excludes SCAN_SOURCE_NODE: `AND type(rel) <> 'SCAN_SOURCE_NODE'`
    - The current implementation does not copy SCAN_SOURCE_NODE relationships

    Expected behavior after fix:
    - SCAN_SOURCE_NODE relationships should be copied to target layer
    - Target layer Resources should link to ORIGINAL nodes (not copied)
    """
    _, mock_session = mock_session_manager

    # Mock node count query
    mock_session.run.return_value.single.return_value = {"total": 2}

    # Track queries executed
    queries_executed = []

    def track_query(query, params):
        queries_executed.append((query, params))
        # Return appropriate mock responses
        if "count(r)" in query:
            result = Mock()
            result.single.return_value = {"total": 2}
            return result
        elif "CREATE (new:Resource)" in query:
            return Mock()
        elif "SCAN_SOURCE_NODE" in query or "apoc.create.relationship" in query:
            result = Mock()
            result.single.return_value = {"count": 2}
            return result
        return Mock()

    mock_session.run.side_effect = track_query

    # Execute copy
    result = await export_operations.copy_layer(
        source_layer_id="source-layer",
        target_layer_id="target-layer",
        name="Target Layer",
        description="Copy of source layer",
    )

    # Verify SCAN_SOURCE_NODE relationships were copied
    # THIS ASSERTION SHOULD FAIL
    scan_source_queries = [
        query for query, params in queries_executed
        if "SCAN_SOURCE_NODE" in query and "CREATE" in query.upper()
    ]

    assert len(scan_source_queries) > 0, (
        "EXPECTED FAILURE: copy_layer should copy SCAN_SOURCE_NODE relationships, "
        "but currently excludes them (line 166 in export.py)"
    )


@pytest.mark.asyncio
async def test_copy_layer_links_to_original_nodes_not_copies(
    export_operations,
    mock_session_manager,
):
    """
    Test that copied Resources link to ORIGINAL nodes, not copied Resources.

    THIS TEST SHOULD FAIL because:
    - Current implementation doesn't copy SCAN_SOURCE_NODE at all
    - Even if it did, it might incorrectly create new Original nodes

    Expected behavior after fix:
    - Target layer Resources should have SCAN_SOURCE_NODE → existing :Original nodes
    - Should NOT create duplicate :Original nodes
    """
    _, mock_session = mock_session_manager

    # Mock responses
    mock_session.run.return_value.single.return_value = {"total": 1}

    queries_executed = []

    def track_query(query, params):
        queries_executed.append((query, params))
        return Mock(single=Mock(return_value={"count": 1}))

    mock_session.run.side_effect = track_query

    await export_operations.copy_layer(
        source_layer_id="source-layer",
        target_layer_id="target-layer",
        name="Target Layer",
        description="Test",
    )

    # Verify SCAN_SOURCE_NODE points to :Original nodes
    # THIS ASSERTION SHOULD FAIL
    scan_source_to_original = [
        query for query, params in queries_executed
        if "SCAN_SOURCE_NODE" in query and ":Original" in query
    ]

    assert len(scan_source_to_original) > 0, (
        "EXPECTED FAILURE: Target layer should link to :Original nodes via SCAN_SOURCE_NODE, "
        "but current implementation doesn't copy these relationships"
    )


# =============================================================================
# Unit Tests - archive_layer (EXPECTED TO FAIL)
# =============================================================================


@pytest.mark.asyncio
async def test_archive_layer_includes_scan_source_node(
    export_operations,
    mock_session_manager,
    tmp_path,
):
    """
    Test that archive_layer includes SCAN_SOURCE_NODE in JSON export.

    THIS TEST SHOULD FAIL because:
    - Line 255 in export.py explicitly excludes SCAN_SOURCE_NODE: `AND type(rel) <> 'SCAN_SOURCE_NODE'`

    Expected behavior after fix:
    - JSON archive should include SCAN_SOURCE_NODE relationships
    - Archive should have version metadata (version: "2.0", includes_scan_source_node: True)
    """
    _, mock_session = mock_session_manager

    # Mock node query
    mock_node_result = Mock()
    mock_node_result.__iter__ = Mock(return_value=iter([
        {"r": {"id": "vm1", "name": "vm1", "layer_id": "test-layer"}},
    ]))

    # Mock relationship query (currently excludes SCAN_SOURCE_NODE)
    mock_rel_result = Mock()
    mock_rel_result.__iter__ = Mock(return_value=iter([]))

    mock_session.run.side_effect = [mock_node_result, mock_rel_result]

    # Archive to temporary file
    output_path = tmp_path / "archive.json"
    await export_operations.archive_layer(
        layer_id="test-layer",
        output_path=str(output_path),
    )

    # Load archive and verify SCAN_SOURCE_NODE relationships
    with open(output_path) as f:
        archive_data = json.load(f)

    relationships = archive_data.get("relationships", [])
    scan_source_rels = [
        rel for rel in relationships
        if rel.get("type") == "SCAN_SOURCE_NODE"
    ]

    # THIS ASSERTION SHOULD FAIL
    assert len(scan_source_rels) > 0, (
        "EXPECTED FAILURE: archive should include SCAN_SOURCE_NODE relationships, "
        "but line 255 in export.py excludes them"
    )


@pytest.mark.asyncio
async def test_archive_layer_has_version_metadata(
    export_operations,
    mock_session_manager,
    tmp_path,
):
    """
    Test that archive includes version metadata.

    THIS TEST SHOULD FAIL because:
    - Current implementation doesn't add version metadata

    Expected behavior after fix:
    - Archive should have: {"version": "2.0", "includes_scan_source_node": True}
    """
    _, mock_session = mock_session_manager

    mock_session.run.return_value.__iter__ = Mock(return_value=iter([]))

    output_path = tmp_path / "archive.json"
    await export_operations.archive_layer(
        layer_id="test-layer",
        output_path=str(output_path),
    )

    with open(output_path) as f:
        archive_data = json.load(f)

    # THIS ASSERTION SHOULD FAIL
    assert "version" in archive_data, (
        "EXPECTED FAILURE: archive should include version metadata"
    )
    assert archive_data.get("version") == "2.0", (
        "EXPECTED FAILURE: archive version should be 2.0 (with SCAN_SOURCE_NODE support)"
    )
    assert archive_data.get("includes_scan_source_node") is True, (
        "EXPECTED FAILURE: archive should indicate SCAN_SOURCE_NODE is included"
    )


# =============================================================================
# Unit Tests - restore_layer (EXPECTED TO FAIL)
# =============================================================================


@pytest.mark.asyncio
async def test_restore_layer_recreates_scan_source_node(
    export_operations,
    mock_session_manager,
    tmp_path,
):
    """
    Test that restore_layer recreates SCAN_SOURCE_NODE relationships.

    THIS TEST SHOULD FAIL because:
    - Archive doesn't include SCAN_SOURCE_NODE (test above fails)
    - Even if archive had them, restore might not recreate correctly

    Expected behavior after fix:
    - Restored layer should have SCAN_SOURCE_NODE relationships
    - Relationships should point to :Original nodes (not create new ones)
    """
    _, mock_session = mock_session_manager

    # Create archive with SCAN_SOURCE_NODE (simulating fixed archive format)
    archive_data = {
        "metadata": {
            "layer_id": "restored-layer",
            "name": "Restored Layer",
            "description": "Test restore",
            "created_at": datetime.utcnow().isoformat(),
            "layer_type": "experimental",
            "tenant_id": "test-tenant",
        },
        "nodes": [
            {"id": "vm1", "name": "vm1", "layer_id": "restored-layer"},
        ],
        "relationships": [
            {
                "source": "vm1",
                "target": "vm1_original",
                "type": "SCAN_SOURCE_NODE",
                "properties": {},
            },
        ],
        "version": "2.0",
        "includes_scan_source_node": True,
    }

    archive_path = tmp_path / "archive.json"
    with open(archive_path, "w") as f:
        json.dump(archive_data, f)

    # Track queries
    queries_executed = []

    def track_query(query, params):
        queries_executed.append((query, params))
        return Mock()

    mock_session.run.side_effect = track_query

    # Restore layer
    await export_operations.restore_layer(
        archive_path=str(archive_path),
    )

    # Verify SCAN_SOURCE_NODE was restored
    # THIS ASSERTION SHOULD FAIL
    scan_source_queries = [
        query for query, params in queries_executed
        if "SCAN_SOURCE_NODE" in query
    ]

    assert len(scan_source_queries) > 0, (
        "EXPECTED FAILURE: restore_layer should recreate SCAN_SOURCE_NODE relationships "
        "from archive, but current implementation may not handle them"
    )


# =============================================================================
# Unit Tests - Layer Isolation (SHOULD PASS - Regression Test)
# =============================================================================


@pytest.mark.asyncio
async def test_layer_isolation_maintained(
    export_operations,
    mock_session_manager,
):
    """
    Test that layer isolation is maintained (no cross-layer contamination).

    THIS TEST SHOULD PASS even before fix (regression test).

    Verifies:
    - Layer A's SCAN_SOURCE_NODE doesn't reference Layer B's Resources
    - layer_id scoping works correctly
    """
    _, mock_session = mock_session_manager

    # Mock two separate layers
    mock_session.run.return_value.single.return_value = {"total": 1}

    queries_executed = []

    def track_query(query, params):
        queries_executed.append((query, params))
        return Mock(single=Mock(return_value={"count": 1}))

    mock_session.run.side_effect = track_query

    # Copy Layer A
    await export_operations.copy_layer(
        source_layer_id="layer-a",
        target_layer_id="layer-a-copy",
        name="Layer A Copy",
        description="Test",
    )

    # Verify all queries include layer_id filtering
    for query, params in queries_executed:
        if "MATCH" in query and "Resource" in query:
            # Should have layer_id filter
            assert "layer_id" in query or "layer_id" in str(params), (
                f"Query should filter by layer_id to maintain isolation: {query}"
            )


# =============================================================================
# Unit Tests - Edge Cases
# =============================================================================


@pytest.mark.asyncio
async def test_copy_layer_empty_source(
    export_operations,
    mock_session_manager,
):
    """Test copying a layer with no Resources."""
    _, mock_session = mock_session_manager

    # Mock empty layer
    mock_session.run.return_value.single.return_value = {"total": 0}

    result = await export_operations.copy_layer(
        source_layer_id="empty-layer",
        target_layer_id="empty-copy",
        name="Empty Copy",
        description="Copy of empty layer",
    )

    assert result is not None


@pytest.mark.asyncio
async def test_archive_layer_with_no_relationships(
    export_operations,
    mock_session_manager,
    tmp_path,
):
    """Test archiving a layer with nodes but no relationships."""
    _, mock_session = mock_session_manager

    # Mock nodes but no relationships
    mock_node_result = Mock()
    mock_node_result.__iter__ = Mock(return_value=iter([
        {"r": {"id": "vm1", "name": "vm1"}},
    ]))

    mock_rel_result = Mock()
    mock_rel_result.__iter__ = Mock(return_value=iter([]))

    mock_session.run.side_effect = [mock_node_result, mock_rel_result]

    output_path = tmp_path / "archive.json"
    result = await export_operations.archive_layer(
        layer_id="test-layer",
        output_path=str(output_path),
    )

    assert result == str(output_path)
    assert output_path.exists()


@pytest.mark.asyncio
async def test_restore_layer_backward_compatibility_v1_archives(
    export_operations,
    mock_session_manager,
    tmp_path,
):
    """
    Test that v1.0 archives (without SCAN_SOURCE_NODE) still work.

    THIS TEST SHOULD PASS - Backward compatibility requirement.
    """
    _, mock_session = mock_session_manager

    # Create v1.0 archive (no version metadata, no SCAN_SOURCE_NODE)
    archive_data = {
        "metadata": {
            "layer_id": "restored-layer",
            "name": "Restored Layer",
            "description": "Test restore",
            "created_at": datetime.utcnow().isoformat(),
            "layer_type": "experimental",
            "tenant_id": "test-tenant",
        },
        "nodes": [
            {"id": "vm1", "name": "vm1", "layer_id": "restored-layer"},
        ],
        "relationships": [
            {
                "source": "vm1",
                "target": "vm2",
                "type": "CONTAINS",
                "properties": {},
            },
        ],
    }

    archive_path = tmp_path / "v1_archive.json"
    with open(archive_path, "w") as f:
        json.dump(archive_data, f)

    mock_session.run.return_value = Mock()

    # Should not raise exception
    result = await export_operations.restore_layer(
        archive_path=str(archive_path),
    )

    assert result is not None


__all__ = [
    "test_copy_layer_preserves_scan_source_node",
    "test_copy_layer_links_to_original_nodes_not_copies",
    "test_archive_layer_includes_scan_source_node",
    "test_archive_layer_has_version_metadata",
    "test_restore_layer_recreates_scan_source_node",
    "test_layer_isolation_maintained",
    "test_copy_layer_empty_source",
    "test_archive_layer_with_no_relationships",
    "test_restore_layer_backward_compatibility_v1_archives",
]
