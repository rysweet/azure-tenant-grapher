"""
E2E tests for resource_comparator with layer SCAN_SOURCE_NODE support (Issue #570 - TDD)

Test Coverage (10% of testing pyramid - E2E TESTS):
- End-to-end IaC generation workflow with layers
- resource_comparator finding original IDs via SCAN_SOURCE_NODE
- Heuristic cleanup NOT triggered when SCAN_SOURCE_NODE exists
- Full user journey from layer creation to IaC generation

Philosophy:
- All tests should FAIL before fix is implemented
- Tests simulate real user workflows
- Tests verify complete system behavior
- Slower tests (acceptable for E2E)
"""

import pytest

from src.iac.resource_comparator import ResourceComparator, ResourceState
from src.iac.target_scanner import TargetResource, TargetScanResult
from src.utils.session_manager import Neo4jSessionManager

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def neo4j_session_manager(neo4j_container):
    """Create real Neo4j session manager for E2E tests."""
    uri, user, password = neo4j_container
    return Neo4jSessionManager(uri=uri, username=user, password=password)


@pytest.fixture
def resource_comparator(neo4j_session_manager):
    """Create ResourceComparator with real Neo4j connection."""
    return ResourceComparator(session_manager=neo4j_session_manager)


@pytest.fixture
def setup_layer_with_scan_source(neo4j_session_manager):
    """
    Setup a layer with Resources and SCAN_SOURCE_NODE relationships for E2E testing.

    Simulates a real user workflow:
    1. User scans Azure tenant (creates :Original nodes)
    2. System creates abstracted layer (creates :Resource nodes with SCAN_SOURCE_NODE)
    3. User modifies layer (layer operations preserve SCAN_SOURCE_NODE)
    4. User generates IaC (resource_comparator uses SCAN_SOURCE_NODE)
    """

    def _setup(layer_id="iac-test-layer"):
        with neo4j_session_manager.session() as session:
            # Clean up
            session.run(
                """
                MATCH (n)
                WHERE n.layer_id = $layer_id OR n:Original
                DETACH DELETE n
                """,
                {"layer_id": layer_id},
            )

            # Step 1: Create Original nodes (scan results)
            session.run(
                """
                CREATE (orig1:Resource:Original {
                    id: '/subscriptions/test-sub/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1',
                    name: 'vm1',
                    type: 'Microsoft.Compute/virtualMachines',
                    location: 'eastus',
                    tags: ['Environment:Production', 'Owner:TeamA']
                })
                CREATE (orig2:Resource:Original {
                    id: '/subscriptions/test-sub/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1',
                    name: 'vnet1',
                    type: 'Microsoft.Network/virtualNetworks',
                    location: 'eastus',
                    tags: ['Environment:Production']
                })
                """
            )

            # Step 2: Create abstracted Resources in layer
            # These have DIFFERENT IDs from originals (abstraction applied)
            session.run(
                """
                CREATE (r1:Resource {
                    id: '/subscriptions/test-sub/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1_abstracted_abc123',
                    name: 'vm1_abstracted',
                    type: 'Microsoft.Compute/virtualMachines',
                    layer_id: $layer_id,
                    location: 'eastus',
                    tags: ['Environment:Production', 'Owner:TeamA']
                })
                CREATE (r2:Resource {
                    id: '/subscriptions/test-sub/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1_abstracted_def456',
                    name: 'vnet1_abstracted',
                    type: 'Microsoft.Network/virtualNetworks',
                    layer_id: $layer_id,
                    location: 'eastus',
                    tags: ['Environment:Production']
                })
                """,
                {"layer_id": layer_id},
            )

            # Step 3: Create SCAN_SOURCE_NODE relationships (abstracted → original)
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

        return layer_id

    return _setup


@pytest.fixture
def target_scan_result():
    """Create sample target scan result (simulates Azure tenant scan)."""
    return TargetScanResult(
        resources=[
            TargetResource(
                id="/subscriptions/test-sub/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
                name="vm1",
                type="Microsoft.Compute/virtualMachines",
                location="eastus",
                tags={"Environment": "Production", "Owner": "TeamA"},
            ),
            TargetResource(
                id="/subscriptions/test-sub/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1",
                name="vnet1",
                type="Microsoft.Network/virtualNetworks",
                location="eastus",
                tags={"Environment": "Production"},
            ),
        ]
    )


# =============================================================================
# E2E Tests - Full User Workflow (EXPECTED TO FAIL)
# =============================================================================


@pytest.mark.e2e
def test_resource_comparator_finds_scan_source_node_in_layers(
    resource_comparator,
    neo4j_session_manager,
    setup_layer_with_scan_source,
    target_scan_result,
):
    """
    E2E: Test resource_comparator finds original IDs via SCAN_SOURCE_NODE.

    THIS TEST SHOULD FAIL because:
    - If SCAN_SOURCE_NODE not preserved during layer operations (copy/archive/restore),
      then resource_comparator won't find original IDs
    - Heuristic cleanup will be triggered as fallback
    - Classification may be wrong (NEW instead of EXACT_MATCH)

    Expected behavior after fix:
    - resource_comparator queries SCAN_SOURCE_NODE to find original Azure IDs
    - Resources correctly classified as EXACT_MATCH (not NEW)
    - No heuristic cleanup warnings in logs
    """
    # Setup layer with SCAN_SOURCE_NODE
    layer_id = setup_layer_with_scan_source()

    # Get abstracted resources from layer
    with neo4j_session_manager.session() as session:
        result = session.run(
            """
            MATCH (r:Resource)
            WHERE r.layer_id = $layer_id
            RETURN r
            """,
            {"layer_id": layer_id},
        )
        abstracted_resources = [dict(record["r"]) for record in result]

    assert len(abstracted_resources) == 2, "Should have 2 abstracted resources"

    # Compare with target scan
    comparison_result = resource_comparator.compare_resources(
        abstracted_resources=abstracted_resources,
        target_scan=target_scan_result,
    )

    # Verify classifications
    summary = comparison_result.summary

    # THIS ASSERTION SHOULD FAIL if SCAN_SOURCE_NODE not preserved
    # Expected: 2 EXACT_MATCH (comparator found original IDs via SCAN_SOURCE_NODE)
    # Actual: 2 NEW (comparator couldn't find original IDs, used heuristic fallback)
    assert summary[ResourceState.EXACT_MATCH.value] == 2, (
        f"EXPECTED FAILURE: Should have 2 EXACT_MATCH resources, "
        f"but got {summary[ResourceState.EXACT_MATCH.value]}. "
        f"resource_comparator couldn't find SCAN_SOURCE_NODE relationships."
    )

    assert summary[ResourceState.NEW.value] == 0, (
        f"Should have 0 NEW resources (all should match), "
        f"but got {summary[ResourceState.NEW.value]}"
    )


@pytest.mark.e2e
def test_heuristic_cleanup_not_triggered_with_scan_source_node(
    resource_comparator,
    neo4j_session_manager,
    setup_layer_with_scan_source,
    target_scan_result,
    caplog,
):
    """
    E2E: Test that heuristic cleanup is NOT triggered when SCAN_SOURCE_NODE exists.

    THIS TEST SHOULD FAIL because:
    - Without SCAN_SOURCE_NODE, resource_comparator falls back to heuristic cleanup
    - Warning logs will appear: "No SCAN_SOURCE_NODE found, using heuristic-cleaned abstracted ID"

    Expected behavior after fix:
    - No heuristic cleanup warnings in logs
    - resource_comparator uses SCAN_SOURCE_NODE path (preferred)
    """
    import logging

    caplog.set_level(logging.WARNING)

    # Setup layer
    layer_id = setup_layer_with_scan_source()

    # Get abstracted resources
    with neo4j_session_manager.session() as session:
        result = session.run(
            """
            MATCH (r:Resource)
            WHERE r.layer_id = $layer_id
            RETURN r
            """,
            {"layer_id": layer_id},
        )
        abstracted_resources = [dict(record["r"]) for record in result]

    # Compare
    resource_comparator.compare_resources(
        abstracted_resources=abstracted_resources,
        target_scan=target_scan_result,
    )

    # Check for heuristic cleanup warnings
    heuristic_warnings = [
        record for record in caplog.records if "heuristic" in record.message.lower()
    ]

    # THIS ASSERTION SHOULD FAIL
    assert len(heuristic_warnings) == 0, (
        f"EXPECTED FAILURE: Should not trigger heuristic cleanup when SCAN_SOURCE_NODE exists, "
        f"but found {len(heuristic_warnings)} warnings: {[r.message for r in heuristic_warnings]}"
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_iac_generation_after_layer_copy(
    resource_comparator,
    neo4j_session_manager,
    setup_layer_with_scan_source,
    target_scan_result,
):
    """
    E2E: Test IaC generation after layer copy operation.

    THIS TEST SHOULD FAIL because:
    - copy_layer doesn't preserve SCAN_SOURCE_NODE (line 166 in export.py)
    - Copied layer won't have original ID mappings
    - resource_comparator will misclassify resources

    Expected behavior after fix:
    - After copy, SCAN_SOURCE_NODE preserved in target layer
    - IaC generation works correctly with copied layer
    """
    from src.services.layer.export import LayerExportOperations

    # Setup source layer
    source_layer_id = setup_layer_with_scan_source(layer_id="source-layer")

    # Copy layer (THIS IS WHERE BUG OCCURS)
    export_ops = LayerExportOperations(session_manager=neo4j_session_manager)
    await export_ops.copy_layer(
        source_layer_id=source_layer_id,
        target_layer_id="copied-layer",
        name="Copied Layer",
        description="Copy for IaC generation",
    )

    # Get resources from COPIED layer
    with neo4j_session_manager.session() as session:
        result = session.run(
            """
            MATCH (r:Resource)
            WHERE r.layer_id = 'copied-layer'
            RETURN r
            """
        )
        copied_resources = [dict(record["r"]) for record in result]

    assert len(copied_resources) == 2, "Copied layer should have 2 resources"

    # Compare copied layer with target scan
    comparison_result = resource_comparator.compare_resources(
        abstracted_resources=copied_resources,
        target_scan=target_scan_result,
    )

    summary = comparison_result.summary

    # THIS ASSERTION SHOULD FAIL
    assert summary[ResourceState.EXACT_MATCH.value] == 2, (
        f"EXPECTED FAILURE: Copied layer should classify resources correctly, "
        f"but got {summary[ResourceState.EXACT_MATCH.value]} EXACT_MATCH. "
        f"SCAN_SOURCE_NODE not preserved during copy."
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_iac_generation_after_archive_restore(
    resource_comparator,
    neo4j_session_manager,
    setup_layer_with_scan_source,
    target_scan_result,
    tmp_path,
):
    """
    E2E: Test IaC generation after archive → restore workflow.

    THIS TEST SHOULD FAIL because:
    - archive_layer excludes SCAN_SOURCE_NODE (line 255 in export.py)
    - Restored layer won't have SCAN_SOURCE_NODE relationships
    - IaC generation will fail to find original IDs

    Expected behavior after fix:
    - Archive includes SCAN_SOURCE_NODE
    - Restore recreates SCAN_SOURCE_NODE
    - IaC generation works correctly with restored layer
    """
    from src.services.layer.export import LayerExportOperations

    # Setup source layer
    source_layer_id = setup_layer_with_scan_source(layer_id="archive-source")

    # Archive layer (THIS IS WHERE BUG OCCURS)
    export_ops = LayerExportOperations(session_manager=neo4j_session_manager)
    archive_path = tmp_path / "layer.json"
    await export_ops.archive_layer(
        layer_id=source_layer_id,
        output_path=str(archive_path),
    )

    # Delete source layer
    with neo4j_session_manager.session() as session:
        session.run(
            """
            MATCH (n:Resource)
            WHERE n.layer_id = 'archive-source'
            DETACH DELETE n
            """
        )

    # Restore layer
    await export_ops.restore_layer(
        archive_path=str(archive_path),
        target_layer_id="restored-layer",
    )

    # Get resources from RESTORED layer
    with neo4j_session_manager.session() as session:
        result = session.run(
            """
            MATCH (r:Resource)
            WHERE r.layer_id = 'restored-layer'
            RETURN r
            """
        )
        restored_resources = [dict(record["r"]) for record in result]

    assert len(restored_resources) == 2, "Restored layer should have 2 resources"

    # Compare restored layer with target scan
    comparison_result = resource_comparator.compare_resources(
        abstracted_resources=restored_resources,
        target_scan=target_scan_result,
    )

    summary = comparison_result.summary

    # THIS ASSERTION SHOULD FAIL
    assert summary[ResourceState.EXACT_MATCH.value] == 2, (
        f"EXPECTED FAILURE: Restored layer should classify resources correctly, "
        f"but got {summary[ResourceState.EXACT_MATCH.value]} EXACT_MATCH. "
        f"SCAN_SOURCE_NODE not included in archive/restore."
    )


# =============================================================================
# E2E Tests - Cross-Tenant IaC Generation (SHOULD WORK)
# =============================================================================


@pytest.mark.e2e
def test_cross_tenant_iac_generation_with_scan_source_node(
    neo4j_session_manager,
    setup_layer_with_scan_source,
):
    """
    E2E: Test cross-tenant IaC generation with SCAN_SOURCE_NODE.

    THIS TEST SHOULD FAIL because SCAN_SOURCE_NODE not preserved.

    Expected behavior after fix:
    - resource_comparator uses SCAN_SOURCE_NODE to get source subscription ID
    - Normalizes ID for target subscription
    - Correctly matches resources across tenants
    """
    # Setup source layer (subscription: test-sub)
    layer_id = setup_layer_with_scan_source()

    # Create resource comparator with cross-tenant config
    comparator = ResourceComparator(
        session_manager=neo4j_session_manager,
        source_subscription_id="test-sub",
        target_subscription_id="target-sub",
    )

    # Get abstracted resources
    with neo4j_session_manager.session() as session:
        result = session.run(
            """
            MATCH (r:Resource)
            WHERE r.layer_id = $layer_id
            RETURN r
            """,
            {"layer_id": layer_id},
        )
        abstracted_resources = [dict(record["r"]) for record in result]

    # Target scan with DIFFERENT subscription
    target_scan = TargetScanResult(
        resources=[
            TargetResource(
                id="/subscriptions/target-sub/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
                name="vm1",
                type="Microsoft.Compute/virtualMachines",
                location="eastus",
                tags={"Environment": "Production", "Owner": "TeamA"},
            ),
        ]
    )

    # Compare
    comparison_result = comparator.compare_resources(
        abstracted_resources=abstracted_resources,
        target_scan=target_scan,
    )

    summary = comparison_result.summary

    # THIS ASSERTION SHOULD FAIL
    assert summary[ResourceState.EXACT_MATCH.value] == 1, (
        f"EXPECTED FAILURE: Cross-tenant comparison should work with SCAN_SOURCE_NODE, "
        f"but got {summary[ResourceState.EXACT_MATCH.value]} matches. "
        f"SCAN_SOURCE_NODE not preserved in layer."
    )


# =============================================================================
# Test Configuration
# =============================================================================


def pytest_configure(config):
    """Register e2e marker."""
    config.addinivalue_line(
        "markers",
        "e2e: mark test as end-to-end test (requires Neo4j, slower)",
    )


__all__ = [
    "test_cross_tenant_iac_generation_with_scan_source_node",
    "test_heuristic_cleanup_not_triggered_with_scan_source_node",
    "test_iac_generation_after_archive_restore",
    "test_iac_generation_after_layer_copy",
    "test_resource_comparator_finds_scan_source_node_in_layers",
]
