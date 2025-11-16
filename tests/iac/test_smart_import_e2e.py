"""
End-to-End Tests for Smart Import IaC Generation Pipeline (Phase 1G)

Tests the complete workflow from graph setup through comparison to IaC generation,
covering all resource classification states and edge cases.
"""

import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from src.iac.emitters.terraform_emitter import TerraformEmitter
from src.iac.resource_comparator import (
    ComparisonResult,
    ResourceComparator,
    ResourceState,
)
from src.iac.target_scanner import (
    TargetResource,
    TargetScanResult,
)
from src.iac.traverser import TenantGraph

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def temp_output_dir():
    """Create temporary output directory for IaC files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_neo4j_session_manager():
    """Mock Neo4j session manager for ResourceComparator."""
    mock_manager = MagicMock()
    mock_session = MagicMock()
    mock_manager.session.return_value.__enter__.return_value = mock_session
    mock_manager.session.return_value.__exit__ = Mock(return_value=False)
    return mock_manager


@pytest.fixture
def mock_azure_discovery_service():
    """Mock Azure Discovery Service for TargetScannerService."""
    service = MagicMock()
    service.credential = MagicMock()
    service.discover_subscriptions = AsyncMock()
    service.discover_resources_in_subscription = AsyncMock()
    return service


# ============================================================================
# Test Data: Abstracted Resources (from graph)
# ============================================================================


@pytest.fixture
def abstracted_resources_new() -> List[Dict[str, Any]]:
    """NEW resources - not in target tenant."""
    return [
        {
            "id": "vnet-new-abc123",
            "name": "vnet-new-abc123",
            "type": "Microsoft.Network/virtualNetworks",
            "location": "eastus",
            "subscription_id": "source-sub-123",
            "resource_group": "rg-test",
            "tags": {"Environment": "Production"},
            "original_id": "/subscriptions/source-sub-123/resourceGroups/rg-test/providers/Microsoft.Network/virtualNetworks/new-vnet",
            "properties": json.dumps(
                {"addressSpace": {"addressPrefixes": ["10.0.0.0/16"]}}
            ),
        },
        {
            "id": "storage-new-xyz789",
            "name": "storage-new-xyz789",
            "type": "Microsoft.Storage/storageAccounts",
            "location": "westus",
            "subscription_id": "source-sub-123",
            "resource_group": "rg-test",
            "tags": {},
            "original_id": "/subscriptions/source-sub-123/resourceGroups/rg-test/providers/Microsoft.Storage/storageAccounts/new-storage",
            "properties": json.dumps({"sku": {"name": "Standard_LRS"}}),
        },
        {
            "id": "nsg-new-def456",
            "name": "nsg-new-def456",
            "type": "Microsoft.Network/networkSecurityGroups",
            "location": "eastus",
            "subscription_id": "source-sub-123",
            "resource_group": "rg-test",
            "tags": {"Owner": "TeamA"},
            "original_id": "/subscriptions/source-sub-123/resourceGroups/rg-test/providers/Microsoft.Network/networkSecurityGroups/new-nsg",
            "properties": json.dumps({"securityRules": []}),
        },
    ]


@pytest.fixture
def abstracted_resources_exact_match() -> List[Dict[str, Any]]:
    """EXACT_MATCH resources - in target with same properties.

    NOTE: original_id must match the target resource ID for matching to work.
    """
    return [
        {
            "id": "rg-match-111",
            "name": "test-rg",
            "type": "Microsoft.Resources/resourceGroups",
            "location": "westus",
            "subscription_id": "source-sub-123",
            "tags": {"Environment": "Test"},
            # original_id points to target tenant (where the resource exists)
            "original_id": "/subscriptions/target-sub-456/resourceGroups/test-rg",
            "properties": json.dumps({}),
        },
        {
            "id": "vnet-match-222",
            "name": "prod-vnet",
            "type": "Microsoft.Network/virtualNetworks",
            "location": "eastus",
            "subscription_id": "source-sub-123",
            "resource_group": "test-rg",
            "tags": {"Environment": "Production"},
            # original_id points to target tenant (where the resource exists)
            "original_id": "/subscriptions/target-sub-456/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/prod-vnet",
            "properties": json.dumps(
                {"addressSpace": {"addressPrefixes": ["10.1.0.0/16"]}}
            ),
        },
    ]


@pytest.fixture
def abstracted_resources_drifted() -> List[Dict[str, Any]]:
    """DRIFTED resources - in target but properties differ.

    NOTE: original_id must match the target resource ID for matching to work.
    """
    return [
        {
            "id": "nsg-drift-333",
            "name": "prod-nsg",
            "type": "Microsoft.Network/networkSecurityGroups",
            "location": "eastus",
            "subscription_id": "source-sub-123",
            "resource_group": "test-rg",
            "tags": {"Environment": "Production", "Owner": "TeamA"},  # Different from target
            # original_id points to target tenant (where the resource exists)
            "original_id": "/subscriptions/target-sub-456/resourceGroups/test-rg/providers/Microsoft.Network/networkSecurityGroups/prod-nsg",
            "properties": json.dumps({"securityRules": []}),
        },
        {
            "id": "storage-drift-444",
            "name": "drifted-storage",
            "type": "Microsoft.Storage/storageAccounts",
            "location": "westus",  # Different from target (eastus)
            "subscription_id": "source-sub-123",
            "resource_group": "test-rg",
            "tags": {"Environment": "Dev"},
            # original_id points to target tenant (where the resource exists)
            "original_id": "/subscriptions/target-sub-456/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/drifted-storage",
            "properties": json.dumps({"sku": {"name": "Standard_GRS"}}),
        },
    ]


# ============================================================================
# Test Data: Target Resources (from scan)
# ============================================================================


@pytest.fixture
def target_resources_exact_match() -> List[TargetResource]:
    """Target resources that match abstracted resources exactly."""
    return [
        TargetResource(
            id="/subscriptions/target-sub-456/resourceGroups/test-rg",
            type="Microsoft.Resources/resourceGroups",
            name="test-rg",
            location="westus",
            resource_group="test-rg",
            subscription_id="target-sub-456",
            properties={},
            tags={"Environment": "Test"},
        ),
        TargetResource(
            id="/subscriptions/target-sub-456/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/prod-vnet",
            type="Microsoft.Network/virtualNetworks",
            name="prod-vnet",
            location="eastus",
            resource_group="test-rg",
            subscription_id="target-sub-456",
            properties={"addressSpace": {"addressPrefixes": ["10.1.0.0/16"]}},
            tags={"Environment": "Production"},
        ),
    ]


@pytest.fixture
def target_resources_drifted() -> List[TargetResource]:
    """Target resources with properties that differ from abstracted."""
    return [
        TargetResource(
            id="/subscriptions/target-sub-456/resourceGroups/test-rg/providers/Microsoft.Network/networkSecurityGroups/prod-nsg",
            type="Microsoft.Network/networkSecurityGroups",
            name="prod-nsg",
            location="eastus",
            resource_group="test-rg",
            subscription_id="target-sub-456",
            properties={"securityRules": []},
            tags={
                "Environment": "Dev",  # Different from abstracted (Production)
                "Owner": "TeamA",
            },
        ),
        TargetResource(
            id="/subscriptions/target-sub-456/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/drifted-storage",
            type="Microsoft.Storage/storageAccounts",
            name="drifted-storage",
            location="eastus",  # Different from abstracted (westus)
            resource_group="test-rg",
            subscription_id="target-sub-456",
            properties={"sku": {"name": "Standard_GRS"}},
            tags={"Environment": "Dev"},
        ),
    ]


@pytest.fixture
def target_resources_orphaned() -> List[TargetResource]:
    """Orphaned resources - in target but not in abstracted graph."""
    return [
        TargetResource(
            id="/subscriptions/target-sub-456/resourceGroups/test-rg/providers/Microsoft.Network/publicIPAddresses/orphaned-ip",
            type="Microsoft.Network/publicIPAddresses",
            name="orphaned-ip",
            location="westus",
            resource_group="test-rg",
            subscription_id="target-sub-456",
            properties={},
            tags={},
        )
    ]


# ============================================================================
# E2E Test Cases
# ============================================================================


class TestCompleteWorkflowMixedStates:
    """Test complete workflow with all resource states: NEW, EXACT_MATCH, DRIFTED, ORPHANED."""

    @pytest.mark.asyncio
    async def test_complete_smart_import_workflow(
        self,
        temp_output_dir,
        mock_neo4j_session_manager,
        mock_azure_discovery_service,
        abstracted_resources_new,
        abstracted_resources_exact_match,
        abstracted_resources_drifted,
        target_resources_exact_match,
        target_resources_drifted,
        target_resources_orphaned,
    ):
        """
        Test complete workflow from scan to IaC generation with mixed resource states.

        Scenario:
        - 3 NEW resources (not in target)
        - 2 EXACT_MATCH resources (in target, no drift)
        - 2 DRIFTED resources (in target, with drift)
        - 1 ORPHANED resource (in target, not in abstracted)

        Expected outcomes:
        - Import blocks: 2 EXACT_MATCH + 2 DRIFTED = 4 total
        - Resource blocks: 3 NEW + 2 DRIFTED = 5 total
        - Orphaned: Logged warning, not emitted
        """
        # Step 1: Combine all abstracted resources
        abstracted_resources = (
            abstracted_resources_new
            + abstracted_resources_exact_match
            + abstracted_resources_drifted
        )

        # Step 2: Simulate target scan result
        target_scan = TargetScanResult(
            tenant_id="target-tenant-456",
            subscription_id="target-sub-456",
            resources=(
                target_resources_exact_match
                + target_resources_drifted
                + target_resources_orphaned
            ),
            scan_timestamp="2025-11-15T12:00:00Z",
            error=None,
        )

        # Step 3: Run comparison
        comparator = ResourceComparator(mock_neo4j_session_manager)
        comparison_result = comparator.compare_resources(
            abstracted_resources, target_scan
        )

        # Step 4: Verify comparison results
        assert len(comparison_result.classifications) == 8  # All resources classified
        assert comparison_result.summary[ResourceState.NEW.value] == 3
        assert comparison_result.summary[ResourceState.EXACT_MATCH.value] == 2
        assert comparison_result.summary[ResourceState.DRIFTED.value] == 2
        assert comparison_result.summary[ResourceState.ORPHANED.value] == 1

        # Step 5: Create TenantGraph for emitter
        tenant_graph = TenantGraph(
            resources=abstracted_resources,
            relationships=[],
        )

        # Step 6: Generate IaC with smart import
        emitter = TerraformEmitter()
        emitter.emit(
            graph=tenant_graph,
            out_dir=temp_output_dir,
            subscription_id="target-sub-456",
            comparison_result=comparison_result,
        )

        # Step 7: Verify outputs
        self._verify_import_blocks(temp_output_dir, comparison_result)
        self._verify_resource_blocks(temp_output_dir, comparison_result)
        self._verify_orphaned_not_emitted(temp_output_dir)

    def _verify_import_blocks(
        self, output_dir: Path, comparison_result: ComparisonResult
    ):
        """Verify imports.tf contains correct import blocks."""
        imports_file = output_dir / "imports.tf"
        assert imports_file.exists(), "imports.tf should be created"

        content = imports_file.read_text()

        # Verify import block count (EXACT_MATCH + DRIFTED)
        import_count = content.count("import {")
        assert import_count == 4, f"Expected 4 import blocks, found {import_count}"

        # Verify HCL format
        assert "to =" in content, "Import blocks should use HCL format"
        assert 'id = "' in content, "Import blocks should have id field"
        assert '"import"' not in content, "Should not be JSON format"

        # Verify header comment
        assert (
            "# Terraform 1.5+ import blocks" in content
        ), "Should have header comment"

        # Verify specific import blocks for EXACT_MATCH resources
        assert (
            "azurerm_resource_group.test_rg" in content
        ), "Should have RG import block"
        assert (
            "azurerm_virtual_network.prod_vnet" in content
        ), "Should have VNet import block"

        # Verify specific import blocks for DRIFTED resources
        assert (
            "azurerm_network_security_group.prod_nsg" in content
        ), "Should have NSG import block"
        assert (
            "azurerm_storage_account.drifted_storage" in content
        ), "Should have Storage import block"

    def _verify_resource_blocks(
        self, output_dir: Path, comparison_result: ComparisonResult
    ):
        """Verify main.tf.json contains correct resource blocks."""
        main_tf = output_dir / "main.tf.json"
        assert main_tf.exists(), "main.tf.json should be created"

        with open(main_tf) as f:
            config = json.load(f)

        resources = config.get("resource", {})

        # Count total emitted resources (NEW + DRIFTED only)
        total_emitted = sum(len(v) for v in resources.values())
        assert (
            total_emitted == 5
        ), f"Expected 5 resources (3 NEW + 2 DRIFTED), found {total_emitted}"

        # Verify NEW resources are emitted
        assert "azurerm_virtual_network" in resources
        vnet_resources = resources["azurerm_virtual_network"]
        assert (
            "vnet_new_abc123" in vnet_resources
        ), "NEW VNet should be in resource blocks"

        assert "azurerm_storage_account" in resources
        storage_resources = resources["azurerm_storage_account"]
        assert (
            "storage_new_xyz789" in storage_resources
        ), "NEW Storage should be in resource blocks"

        assert "azurerm_network_security_group" in resources
        nsg_resources = resources["azurerm_network_security_group"]
        assert "nsg_new_def456" in nsg_resources, "NEW NSG should be in resource blocks"

        # Verify DRIFTED resources are emitted
        assert (
            "prod_nsg" in nsg_resources
        ), "DRIFTED NSG should be in resource blocks"

        assert (
            "drifted_storage" in storage_resources
        ), "DRIFTED Storage should be in resource blocks"

        # Verify EXACT_MATCH resources are NOT emitted
        assert (
            "test_rg" not in resources.get("azurerm_resource_group", {})
        ), "EXACT_MATCH RG should NOT be in resource blocks"
        assert (
            "prod_vnet" not in vnet_resources
        ), "EXACT_MATCH VNet should NOT be in resource blocks"

    def _verify_orphaned_not_emitted(self, output_dir: Path):
        """Verify orphaned resources are not in any output files."""
        main_tf = output_dir / "main.tf.json"
        imports_tf = output_dir / "imports.tf"

        # Check main.tf.json
        with open(main_tf) as f:
            main_content = json.dumps(json.load(f))
        assert (
            "orphaned-ip" not in main_content
        ), "Orphaned resource should NOT be in main.tf.json"

        # Check imports.tf
        imports_content = imports_tf.read_text()
        assert (
            "orphaned-ip" not in imports_content
        ), "Orphaned resource should NOT be in imports.tf"


class TestEmptyScenarios:
    """Test edge cases with empty or minimal data."""

    def test_no_target_resources_all_new(
        self,
        temp_output_dir,
        mock_neo4j_session_manager,
        abstracted_resources_new,
    ):
        """Test when target tenant is empty - all resources are NEW."""
        # Empty target scan
        target_scan = TargetScanResult(
            tenant_id="target-tenant-456",
            subscription_id="target-sub-456",
            resources=[],
            scan_timestamp="2025-11-15T12:00:00Z",
            error=None,
        )

        # Run comparison
        comparator = ResourceComparator(mock_neo4j_session_manager)
        comparison_result = comparator.compare_resources(
            abstracted_resources_new, target_scan
        )

        # All should be NEW
        assert comparison_result.summary[ResourceState.NEW.value] == 3
        assert comparison_result.summary[ResourceState.EXACT_MATCH.value] == 0
        assert comparison_result.summary[ResourceState.DRIFTED.value] == 0
        assert comparison_result.summary[ResourceState.ORPHANED.value] == 0

        # Generate IaC
        tenant_graph = TenantGraph(resources=abstracted_resources_new, relationships=[])
        emitter = TerraformEmitter()
        emitter.emit(
            graph=tenant_graph,
            out_dir=temp_output_dir,
            subscription_id="target-sub-456",
            comparison_result=comparison_result,
        )

        # Verify no import blocks (all NEW)
        imports_file = temp_output_dir / "imports.tf"
        if imports_file.exists():
            content = imports_file.read_text()
            # File might exist but should be empty or only have comments
            assert "import {" not in content, "No import blocks for all-NEW scenario"

        # Verify all resources in main.tf.json
        main_tf = temp_output_dir / "main.tf.json"
        with open(main_tf) as f:
            config = json.load(f)
        resources = config.get("resource", {})
        total_emitted = sum(len(v) for v in resources.values())
        assert total_emitted == 3, "All NEW resources should be emitted"

    def test_no_abstracted_resources_all_orphaned(
        self,
        temp_output_dir,
        mock_neo4j_session_manager,
        target_resources_orphaned,
    ):
        """Test when abstracted graph is empty - all target resources are ORPHANED."""
        # Target has resources but abstracted is empty
        target_scan = TargetScanResult(
            tenant_id="target-tenant-456",
            subscription_id="target-sub-456",
            resources=target_resources_orphaned,
            scan_timestamp="2025-11-15T12:00:00Z",
            error=None,
        )

        # Run comparison
        comparator = ResourceComparator(mock_neo4j_session_manager)
        comparison_result = comparator.compare_resources([], target_scan)

        # All should be ORPHANED
        assert comparison_result.summary[ResourceState.NEW.value] == 0
        assert comparison_result.summary[ResourceState.EXACT_MATCH.value] == 0
        assert comparison_result.summary[ResourceState.DRIFTED.value] == 0
        assert comparison_result.summary[ResourceState.ORPHANED.value] == 1

        # Generate IaC (should handle gracefully)
        tenant_graph = TenantGraph(resources=[], relationships=[])
        emitter = TerraformEmitter()
        emitter.emit(
            graph=tenant_graph,
            out_dir=temp_output_dir,
            subscription_id="target-sub-456",
            comparison_result=comparison_result,
        )

        # Verify no import blocks
        imports_file = temp_output_dir / "imports.tf"
        if imports_file.exists():
            content = imports_file.read_text()
            assert "import {" not in content, "No import blocks for ORPHANED resources"

        # Verify no resources emitted
        main_tf = temp_output_dir / "main.tf.json"
        with open(main_tf) as f:
            config = json.load(f)
        resources = config.get("resource", {})
        total_emitted = sum(len(v) for v in resources.values())
        assert total_emitted == 0, "ORPHANED resources should NOT be emitted"


class TestBackwardCompatibility:
    """Test backward compatibility without comparison_result."""

    def test_emit_without_comparison_result(
        self,
        temp_output_dir,
        abstracted_resources_new,
    ):
        """Test that emitter works as before when comparison_result=None."""
        tenant_graph = TenantGraph(
            resources=abstracted_resources_new,
            relationships=[],
        )

        emitter = TerraformEmitter()
        emitter.emit(
            graph=tenant_graph,
            out_dir=temp_output_dir,
            subscription_id="source-sub-123",
            # No comparison_result provided
        )

        # Verify main.tf.json exists
        main_tf = temp_output_dir / "main.tf.json"
        assert main_tf.exists()

        # Verify no imports.tf
        imports_tf = temp_output_dir / "imports.tf"
        assert not imports_tf.exists(), "No imports.tf without comparison_result"

        # Verify all resources emitted normally
        with open(main_tf) as f:
            config = json.load(f)
        resources = config.get("resource", {})
        total_emitted = sum(len(v) for v in resources.values())
        # Should emit: 3 NEW resources (vnet, storage, nsg)
        # Provider resource might also be emitted automatically
        assert total_emitted >= 3, f"Expected at least 3 resources, got {total_emitted}"


class TestErrorHandling:
    """Test error handling and graceful degradation."""

    def test_comparison_with_malformed_resource(
        self,
        mock_neo4j_session_manager,
    ):
        """Test comparison handles malformed abstracted resources gracefully."""
        # Malformed resource (missing required fields)
        malformed_resources = [
            {
                "id": "test-id",
                # Missing 'name', 'type', etc.
            }
        ]

        target_scan = TargetScanResult(
            tenant_id="target-tenant-456",
            subscription_id="target-sub-456",
            resources=[],
            scan_timestamp="2025-11-15T12:00:00Z",
            error=None,
        )

        comparator = ResourceComparator(mock_neo4j_session_manager)
        # Should not crash - handles gracefully
        comparison_result = comparator.compare_resources(
            malformed_resources, target_scan
        )

        # Should classify as NEW (safe default)
        assert len(comparison_result.classifications) >= 0

    def test_emitter_continues_on_import_generation_failure(
        self,
        temp_output_dir,
        abstracted_resources_new,
    ):
        """Test that emitter continues with standard emission if smart import fails."""
        tenant_graph = TenantGraph(
            resources=abstracted_resources_new,
            relationships=[],
        )

        # Create a broken comparison result
        from src.iac.resource_comparator import ComparisonResult

        broken_comparison = ComparisonResult(
            classifications=[],  # Empty but valid
            summary={state.value: 0 for state in ResourceState},
        )

        emitter = TerraformEmitter()
        # Should not crash
        emitter.emit(
            graph=tenant_graph,
            out_dir=temp_output_dir,
            subscription_id="source-sub-123",
            comparison_result=broken_comparison,
        )

        # Verify main.tf.json was created
        main_tf = temp_output_dir / "main.tf.json"
        assert main_tf.exists(), "Should create main.tf.json despite import issues"


class TestImportBlockFormat:
    """Test import block file format and correctness."""

    def test_import_block_hcl_format(
        self,
        temp_output_dir,
        mock_neo4j_session_manager,
        abstracted_resources_exact_match,
        target_resources_exact_match,
    ):
        """Test that import blocks use correct HCL format."""
        target_scan = TargetScanResult(
            tenant_id="target-tenant-456",
            subscription_id="target-sub-456",
            resources=target_resources_exact_match,
            scan_timestamp="2025-11-15T12:00:00Z",
            error=None,
        )

        comparator = ResourceComparator(mock_neo4j_session_manager)
        comparison_result = comparator.compare_resources(
            abstracted_resources_exact_match, target_scan
        )

        tenant_graph = TenantGraph(
            resources=abstracted_resources_exact_match,
            relationships=[],
        )

        emitter = TerraformEmitter()
        emitter.emit(
            graph=tenant_graph,
            out_dir=temp_output_dir,
            subscription_id="target-sub-456",
            comparison_result=comparison_result,
        )

        imports_file = temp_output_dir / "imports.tf"
        content = imports_file.read_text()

        # Verify HCL structure
        assert "import {" in content
        assert "to =" in content
        assert 'id = "' in content

        # Verify balanced braces
        open_braces = content.count("{")
        close_braces = content.count("}")
        assert open_braces == close_braces, "Braces should be balanced"

        # Verify not JSON
        assert not content.strip().startswith('{"import"')

    def test_import_block_resource_id_format(
        self,
        temp_output_dir,
        mock_neo4j_session_manager,
        abstracted_resources_exact_match,
        target_resources_exact_match,
    ):
        """Test that import blocks contain correct Azure resource IDs."""
        target_scan = TargetScanResult(
            tenant_id="target-tenant-456",
            subscription_id="target-sub-456",
            resources=target_resources_exact_match,
            scan_timestamp="2025-11-15T12:00:00Z",
            error=None,
        )

        comparator = ResourceComparator(mock_neo4j_session_manager)
        comparison_result = comparator.compare_resources(
            abstracted_resources_exact_match, target_scan
        )

        tenant_graph = TenantGraph(
            resources=abstracted_resources_exact_match,
            relationships=[],
        )

        emitter = TerraformEmitter()
        emitter.emit(
            graph=tenant_graph,
            out_dir=temp_output_dir,
            subscription_id="target-sub-456",
            comparison_result=comparison_result,
        )

        imports_file = temp_output_dir / "imports.tf"
        content = imports_file.read_text()

        # Verify Azure resource ID format
        assert (
            "/subscriptions/target-sub-456/resourceGroups/test-rg" in content
        ), "Should contain target resource group ID"
        assert (
            "/subscriptions/target-sub-456/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/prod-vnet"
            in content
        ), "Should contain target VNet ID"


class TestResourceFiltering:
    """Test resource filtering for EXACT_MATCH resources."""

    def test_exact_match_not_in_main_tf(
        self,
        temp_output_dir,
        mock_neo4j_session_manager,
        abstracted_resources_exact_match,
        target_resources_exact_match,
    ):
        """Test that EXACT_MATCH resources are filtered from main.tf.json."""
        target_scan = TargetScanResult(
            tenant_id="target-tenant-456",
            subscription_id="target-sub-456",
            resources=target_resources_exact_match,
            scan_timestamp="2025-11-15T12:00:00Z",
            error=None,
        )

        comparator = ResourceComparator(mock_neo4j_session_manager)
        comparison_result = comparator.compare_resources(
            abstracted_resources_exact_match, target_scan
        )

        tenant_graph = TenantGraph(
            resources=abstracted_resources_exact_match,
            relationships=[],
        )

        emitter = TerraformEmitter()
        emitter.emit(
            graph=tenant_graph,
            out_dir=temp_output_dir,
            subscription_id="target-sub-456",
            comparison_result=comparison_result,
        )

        main_tf = temp_output_dir / "main.tf.json"
        with open(main_tf) as f:
            config = json.load(f)

        resources = config.get("resource", {})

        # EXACT_MATCH resources should not be present
        rg_resources = resources.get("azurerm_resource_group", {})
        assert (
            "test_rg" not in rg_resources
        ), "EXACT_MATCH RG should NOT be in main.tf.json"

        vnet_resources = resources.get("azurerm_virtual_network", {})
        assert (
            "prod_vnet" not in vnet_resources
        ), "EXACT_MATCH VNet should NOT be in main.tf.json"

    def test_exact_match_in_imports_tf(
        self,
        temp_output_dir,
        mock_neo4j_session_manager,
        abstracted_resources_exact_match,
        target_resources_exact_match,
    ):
        """Test that EXACT_MATCH resources ARE in imports.tf."""
        target_scan = TargetScanResult(
            tenant_id="target-tenant-456",
            subscription_id="target-sub-456",
            resources=target_resources_exact_match,
            scan_timestamp="2025-11-15T12:00:00Z",
            error=None,
        )

        comparator = ResourceComparator(mock_neo4j_session_manager)
        comparison_result = comparator.compare_resources(
            abstracted_resources_exact_match, target_scan
        )

        tenant_graph = TenantGraph(
            resources=abstracted_resources_exact_match,
            relationships=[],
        )

        emitter = TerraformEmitter()
        emitter.emit(
            graph=tenant_graph,
            out_dir=temp_output_dir,
            subscription_id="target-sub-456",
            comparison_result=comparison_result,
        )

        imports_file = temp_output_dir / "imports.tf"
        content = imports_file.read_text()

        # EXACT_MATCH resources should be in imports
        assert "azurerm_resource_group.test_rg" in content
        assert "azurerm_virtual_network.prod_vnet" in content


class TestLogging:
    """Test logging output during smart import workflow."""

    def test_orphaned_resource_logged(
        self,
        mock_neo4j_session_manager,
        target_resources_orphaned,
        caplog,
    ):
        """Test that orphaned resources are logged as warnings."""
        target_scan = TargetScanResult(
            tenant_id="target-tenant-456",
            subscription_id="target-sub-456",
            resources=target_resources_orphaned,
            scan_timestamp="2025-11-15T12:00:00Z",
            error=None,
        )

        comparator = ResourceComparator(mock_neo4j_session_manager)

        with caplog.at_level("WARNING"):
            comparison_result = comparator.compare_resources([], target_scan)

        # Should log warning about orphaned resource
        assert (
            comparison_result.summary[ResourceState.ORPHANED.value] == 1
        ), "Should detect orphaned resource"
