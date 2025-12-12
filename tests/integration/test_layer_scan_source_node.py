"""
Integration tests for SCAN_SOURCE_NODE preservation in layer operations (Issue #570 - TDD)

Test Coverage (30% of testing pyramid - INTEGRATION TESTS):
- Full copy/archive/restore workflow with real Neo4j session
- Multiple components working together
- SCAN_SOURCE_NODE relationships across full workflow

Philosophy:
- All tests should FAIL before fix is implemented
- Tests use real Neo4j transactions (with rollback)
- Tests verify end-to-end workflows
- Clear assertions on expected behavior
"""

import json

import pytest

from src.services.layer.export import LayerExportOperations
from src.utils.session_manager import Neo4jSessionManager

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def neo4j_session_manager(neo4j_container):
    """Create real Neo4j session manager for integration tests."""
    uri, user, password = neo4j_container
    return Neo4jSessionManager(uri=uri, username=user, password=password)


@pytest.fixture
def export_operations(neo4j_session_manager):
    """Create LayerExportOperations with real Neo4j connection."""
    return LayerExportOperations(session_manager=neo4j_session_manager)


@pytest.fixture
def setup_test_layer(neo4j_session_manager):
    """
    Setup a test layer with Resources and SCAN_SOURCE_NODE relationships.

    Creates:
    - 2 :Original nodes (scan results)
    - 2 :Resource nodes in test-layer
    - 2 SCAN_SOURCE_NODE relationships (Resource → Original)
    - 1 CONTAINS relationship (Resource → Resource)
    """

    def _setup(layer_id="test-layer"):
        with neo4j_session_manager.session() as session:
            # Clean up any existing test data
            session.run(
                """
                MATCH (n)
                WHERE n.layer_id = $layer_id OR n:Original
                DETACH DELETE n
                """,
                {"layer_id": layer_id},
            )

            # Create Original nodes (scan results)
            session.run(
                """
                CREATE (orig1:Resource:Original {
                    id: '/subscriptions/test-sub/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1',
                    name: 'vm1',
                    type: 'Microsoft.Compute/virtualMachines',
                    location: 'eastus'
                })
                CREATE (orig2:Resource:Original {
                    id: '/subscriptions/test-sub/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1',
                    name: 'vnet1',
                    type: 'Microsoft.Network/virtualNetworks',
                    location: 'eastus'
                })
                """
            )

            # Create Resource nodes in layer
            session.run(
                """
                CREATE (r1:Resource {
                    id: '/subscriptions/test-sub/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1_abstracted',
                    name: 'vm1_abstracted',
                    type: 'Microsoft.Compute/virtualMachines',
                    layer_id: $layer_id,
                    location: 'eastus'
                })
                CREATE (r2:Resource {
                    id: '/subscriptions/test-sub/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1_abstracted',
                    name: 'vnet1_abstracted',
                    type: 'Microsoft.Network/virtualNetworks',
                    layer_id: $layer_id,
                    location: 'eastus'
                })
                """,
                {"layer_id": layer_id},
            )

            # Create SCAN_SOURCE_NODE relationships (abstracted → original)
            session.run(
                """
                MATCH (r1:Resource {name: 'vm1_abstracted', layer_id: $layer_id})
                MATCH (orig1:Resource:Original {name: 'vm1'})
                CREATE (r1)-[:SCAN_SOURCE_NODE]->(orig1)

                MATCH (r2:Resource {name: 'vnet1_abstracted', layer_id: $layer_id})
                MATCH (orig2:Resource:Original {name: 'vnet1'})
                CREATE (r2)-[:SCAN_SOURCE_NODE]->(orig2)
                """,
                {"layer_id": layer_id},
            )

            # Create CONTAINS relationship (Resource → Resource)
            session.run(
                """
                MATCH (r1:Resource {name: 'vm1_abstracted', layer_id: $layer_id})
                MATCH (r2:Resource {name: 'vnet1_abstracted', layer_id: $layer_id})
                CREATE (r1)-[:CONTAINS]->(r2)
                """,
                {"layer_id": layer_id},
            )

            # Verify setup
            result = session.run(
                """
                MATCH (r:Resource)
                WHERE r.layer_id = $layer_id
                RETURN count(r) as resource_count
                """,
                {"layer_id": layer_id},
            )
            resource_count = result.single()["resource_count"]

            result = session.run(
                """
                MATCH (r:Resource)-[:SCAN_SOURCE_NODE]->(orig:Original)
                WHERE r.layer_id = $layer_id
                RETURN count(r) as scan_source_count
                """,
                {"layer_id": layer_id},
            )
            scan_source_count = result.single()["scan_source_count"]

            return {
                "layer_id": layer_id,
                "resource_count": resource_count,
                "scan_source_count": scan_source_count,
            }

    return _setup


# =============================================================================
# Integration Tests - Full Workflow (EXPECTED TO FAIL)
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_copy_workflow_preserves_scan_source_node(
    export_operations,
    neo4j_session_manager,
    setup_test_layer,
):
    """
    Test full copy workflow with real Neo4j preserves SCAN_SOURCE_NODE.

    THIS TEST SHOULD FAIL because:
    - export.py line 166 excludes SCAN_SOURCE_NODE from copy
    - Copied layer will not have these relationships

    Expected behavior after fix:
    - Target layer should have same SCAN_SOURCE_NODE count as source
    - SCAN_SOURCE_NODE should point to same :Original nodes (not copied)
    """
    # Setup source layer
    setup_info = setup_test_layer(layer_id="source-layer")
    assert setup_info["scan_source_count"] == 2, (
        "Setup should create 2 SCAN_SOURCE_NODE relationships"
    )

    # Copy layer
    await export_operations.copy_layer(
        source_layer_id="source-layer",
        target_layer_id="target-layer",
        name="Target Layer",
        description="Copy of source layer",
        copy_metadata=True,
    )

    # Verify target layer has SCAN_SOURCE_NODE relationships
    with neo4j_session_manager.session() as session:
        result = session.run(
            """
            MATCH (r:Resource)-[:SCAN_SOURCE_NODE]->(orig:Original)
            WHERE r.layer_id = $target_layer_id
            RETURN count(r) as scan_source_count
            """,
            {"target_layer_id": "target-layer"},
        )
        target_scan_source_count = result.single()["scan_source_count"]

    # THIS ASSERTION SHOULD FAIL
    assert target_scan_source_count == 2, (
        f"EXPECTED FAILURE: Target layer should have 2 SCAN_SOURCE_NODE relationships, "
        f"but got {target_scan_source_count}. Current implementation excludes SCAN_SOURCE_NODE (line 166)."
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_archive_restore_workflow_preserves_scan_source_node(
    export_operations,
    neo4j_session_manager,
    setup_test_layer,
    tmp_path,
):
    """
    Test full archive → restore workflow preserves SCAN_SOURCE_NODE.

    THIS TEST SHOULD FAIL because:
    - archive_layer excludes SCAN_SOURCE_NODE (line 255)
    - Archive will not contain these relationships
    - restore_layer cannot recreate what's not in archive

    Expected behavior after fix:
    - Archive should include SCAN_SOURCE_NODE relationships
    - Restored layer should recreate SCAN_SOURCE_NODE links to :Original nodes
    """
    # Setup source layer
    setup_info = setup_test_layer(layer_id="archive-source")
    assert setup_info["scan_source_count"] == 2

    # Archive layer
    archive_path = tmp_path / "layer_archive.json"
    await export_operations.archive_layer(
        layer_id="archive-source",
        output_path=str(archive_path),
    )

    # Verify archive contains SCAN_SOURCE_NODE
    with open(archive_path) as f:
        archive_data = json.load(f)

    scan_source_rels = [
        rel
        for rel in archive_data.get("relationships", [])
        if rel.get("type") == "SCAN_SOURCE_NODE"
    ]

    # THIS ASSERTION SHOULD FAIL
    assert len(scan_source_rels) == 2, (
        f"EXPECTED FAILURE: Archive should contain 2 SCAN_SOURCE_NODE relationships, "
        f"but got {len(scan_source_rels)}. Current implementation excludes them (line 255)."
    )

    # Clean up original layer
    with neo4j_session_manager.session() as session:
        session.run(
            """
            MATCH (n:Resource)
            WHERE n.layer_id = 'archive-source'
            DETACH DELETE n
            """
        )

    # Restore layer (will fail if archive doesn't have SCAN_SOURCE_NODE)
    await export_operations.restore_layer(
        archive_path=str(archive_path),
        target_layer_id="restored-layer",
    )

    # Verify restored layer has SCAN_SOURCE_NODE
    with neo4j_session_manager.session() as session:
        result = session.run(
            """
            MATCH (r:Resource)-[:SCAN_SOURCE_NODE]->(orig:Original)
            WHERE r.layer_id = 'restored-layer'
            RETURN count(r) as scan_source_count
            """,
        )
        restored_scan_source_count = result.single()["scan_source_count"]

    # THIS ASSERTION SHOULD FAIL
    assert restored_scan_source_count == 2, (
        f"EXPECTED FAILURE: Restored layer should have 2 SCAN_SOURCE_NODE relationships, "
        f"but got {restored_scan_source_count}. Archive doesn't contain them."
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_copy_preserves_scan_source_to_same_originals(
    export_operations,
    neo4j_session_manager,
    setup_test_layer,
):
    """
    Test that copied layer links to SAME Original nodes (not duplicates).

    THIS TEST SHOULD FAIL because:
    - SCAN_SOURCE_NODE not copied at all currently

    Expected behavior after fix:
    - Source and target layers should share same :Original nodes
    - No duplicate :Original nodes created
    """
    # Setup source layer
    setup_test_layer(layer_id="source-layer")

    # Count original nodes before copy
    with neo4j_session_manager.session() as session:
        result = session.run("MATCH (orig:Original) RETURN count(orig) as count")
        original_count_before = result.single()["count"]

    # Copy layer
    await export_operations.copy_layer(
        source_layer_id="source-layer",
        target_layer_id="target-layer",
        name="Target Layer",
        description="Test",
    )

    # Count original nodes after copy (should be same)
    with neo4j_session_manager.session() as session:
        result = session.run("MATCH (orig:Original) RETURN count(orig) as count")
        original_count_after = result.single()["count"]

    assert original_count_before == original_count_after, (
        f"Should not create duplicate :Original nodes, "
        f"but count changed from {original_count_before} to {original_count_after}"
    )

    # Verify both layers link to SAME original nodes
    with neo4j_session_manager.session() as session:
        result = session.run(
            """
            MATCH (r1:Resource)-[:SCAN_SOURCE_NODE]->(orig:Original)<-[:SCAN_SOURCE_NODE]-(r2:Resource)
            WHERE r1.layer_id = 'source-layer' AND r2.layer_id = 'target-layer'
            RETURN count(DISTINCT orig) as shared_originals
            """
        )
        shared_originals = result.single()["shared_originals"]

    # THIS ASSERTION SHOULD FAIL
    assert shared_originals == 2, (
        f"EXPECTED FAILURE: Both layers should share 2 :Original nodes, "
        f"but got {shared_originals}. SCAN_SOURCE_NODE not copied."
    )


# =============================================================================
# Integration Tests - Layer Isolation (SHOULD PASS)
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_layer_isolation_with_real_neo4j(
    export_operations,
    neo4j_session_manager,
    setup_test_layer,
):
    """
    Test that layer isolation is maintained with real Neo4j.

    THIS TEST SHOULD PASS even before fix (regression test).

    Verifies:
    - Layer A doesn't see Layer B's Resources
    - SCAN_SOURCE_NODE scoped to correct layer
    """
    # Setup two separate layers
    setup_test_layer(layer_id="layer-a")
    setup_test_layer(layer_id="layer-b")

    # Verify layer A only sees its own resources
    with neo4j_session_manager.session() as session:
        result = session.run(
            """
            MATCH (r:Resource)
            WHERE r.layer_id = 'layer-a'
            RETURN count(r) as count
            """
        )
        layer_a_count = result.single()["count"]

        result = session.run(
            """
            MATCH (r:Resource)
            WHERE r.layer_id = 'layer-b'
            RETURN count(r) as count
            """
        )
        layer_b_count = result.single()["count"]

    assert layer_a_count == 2, "Layer A should have 2 resources"
    assert layer_b_count == 2, "Layer B should have 2 resources"

    # Verify no cross-layer SCAN_SOURCE_NODE contamination
    with neo4j_session_manager.session() as session:
        result = session.run(
            """
            MATCH (r:Resource)-[:SCAN_SOURCE_NODE]->(orig:Original)
            WHERE r.layer_id = 'layer-a'
            RETURN count(r) as layer_a_scan_source
            """
        )
        layer_a_scan_source = result.single()["layer_a_scan_source"]

    assert layer_a_scan_source == 2, (
        "Layer A should have 2 SCAN_SOURCE_NODE relationships"
    )


# =============================================================================
# Integration Tests - Edge Cases
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_copy_layer_with_multiple_scan_source_per_resource(
    export_operations,
    neo4j_session_manager,
):
    """
    Test copying when a Resource has multiple SCAN_SOURCE_NODE relationships.

    THIS TEST SHOULD FAIL because SCAN_SOURCE_NODE not copied.

    Expected behavior after fix:
    - All SCAN_SOURCE_NODE relationships should be copied
    """
    # Setup layer with multiple SCAN_SOURCE_NODE per resource
    with neo4j_session_manager.session() as session:
        session.run(
            """
            MATCH (n) WHERE n.layer_id = 'multi-source' OR n:Original DETACH DELETE n
            """
        )

        # Create 2 Original nodes
        session.run(
            """
            CREATE (orig1:Resource:Original {id: 'orig1', name: 'orig1'})
            CREATE (orig2:Resource:Original {id: 'orig2', name: 'orig2'})
            """
        )

        # Create 1 Resource with 2 SCAN_SOURCE_NODE relationships
        session.run(
            """
            CREATE (r:Resource {
                id: 'resource1',
                name: 'resource1',
                layer_id: 'multi-source'
            })
            WITH r
            MATCH (orig1:Original {id: 'orig1'})
            MATCH (orig2:Original {id: 'orig2'})
            CREATE (r)-[:SCAN_SOURCE_NODE]->(orig1)
            CREATE (r)-[:SCAN_SOURCE_NODE]->(orig2)
            """
        )

    # Copy layer
    await export_operations.copy_layer(
        source_layer_id="multi-source",
        target_layer_id="multi-source-copy",
        name="Multi Source Copy",
        description="Test",
    )

    # Verify target has same number of SCAN_SOURCE_NODE
    with neo4j_session_manager.session() as session:
        result = session.run(
            """
            MATCH (r:Resource)-[:SCAN_SOURCE_NODE]->(orig:Original)
            WHERE r.layer_id = 'multi-source-copy'
            RETURN count(*) as scan_source_count
            """
        )
        scan_source_count = result.single()["scan_source_count"]

    # THIS ASSERTION SHOULD FAIL
    assert scan_source_count == 2, (
        f"EXPECTED FAILURE: Should have 2 SCAN_SOURCE_NODE relationships, "
        f"but got {scan_source_count}"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_archive_restore_with_orphaned_scan_source_node(
    export_operations,
    neo4j_session_manager,
    tmp_path,
):
    """
    Test archive/restore when SCAN_SOURCE_NODE points to deleted Original.

    THIS TEST SHOULD FAIL because archive doesn't include SCAN_SOURCE_NODE.

    Expected behavior after fix:
    - Archive should gracefully handle missing Original nodes
    - Restore should either skip or warn about orphaned references
    """
    # Setup layer with SCAN_SOURCE_NODE
    with neo4j_session_manager.session() as session:
        session.run("MATCH (n) WHERE n.layer_id = 'orphan-test' DETACH DELETE n")

        # Create Resource with SCAN_SOURCE_NODE to non-existent Original
        session.run(
            """
            CREATE (r:Resource {
                id: 'resource1',
                name: 'resource1',
                layer_id: 'orphan-test'
            })
            CREATE (orig:Resource:Original {id: 'orig1', name: 'orig1'})
            CREATE (r)-[:SCAN_SOURCE_NODE]->(orig)
            """
        )

        # Delete the Original node (orphan the SCAN_SOURCE_NODE)
        session.run("MATCH (orig:Original {id: 'orig1'}) DETACH DELETE orig")

    # Archive should handle gracefully
    archive_path = tmp_path / "orphan_archive.json"
    await export_operations.archive_layer(
        layer_id="orphan-test",
        output_path=str(archive_path),
    )

    # Verify archive doesn't break (should skip orphaned SCAN_SOURCE_NODE)
    with open(archive_path) as f:
        archive_data = json.load(f)

    # Archive should have nodes but no SCAN_SOURCE_NODE (Original deleted)
    assert len(archive_data["nodes"]) == 1
    # This assertion will fail regardless, but documents expected behavior
    scan_source_rels = [
        rel
        for rel in archive_data.get("relationships", [])
        if rel.get("type") == "SCAN_SOURCE_NODE"
    ]
    # After fix: Should be 0 (orphaned reference skipped) or include warning
    assert len(scan_source_rels) == 0, "Orphaned SCAN_SOURCE_NODE should be skipped"


# =============================================================================
# Test Configuration
# =============================================================================


def pytest_configure(config):
    """Register integration marker."""
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test (requires Neo4j)",
    )


__all__ = [
    "test_archive_restore_with_orphaned_scan_source_node",
    "test_copy_layer_with_multiple_scan_source_per_resource",
    "test_copy_preserves_scan_source_to_same_originals",
    "test_full_archive_restore_workflow_preserves_scan_source_node",
    "test_full_copy_workflow_preserves_scan_source_node",
    "test_layer_isolation_with_real_neo4j",
]
