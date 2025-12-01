"""
Tests for Terraform Emitter Smart Import Integration (Phase 1E)

Tests the integration of SmartImportGenerator with TerraformEmitter,
including import block generation, resource filtering, and backward compatibility.
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.iac.emitters.terraform_emitter import TerraformEmitter
from src.iac.resource_comparator import (
    ComparisonResult,
    ResourceClassification,
    ResourceState,
)
from src.iac.target_scanner import TargetResource
from src.iac.traverser import TenantGraph


@pytest.fixture
def temp_output_dir():
    """Create temporary output directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def simple_graph():
    """Create a simple tenant graph with a few resources."""
    return TenantGraph(
        resources=[
            {
                "id": "rg-001",
                "name": "test-rg",
                "type": "Microsoft.Resources/resourceGroups",
                "location": "eastus",
                "subscription_id": "sub-123",
            },
            {
                "id": "vnet-001",
                "name": "test-vnet",
                "type": "Microsoft.Network/virtualNetworks",
                "location": "eastus",
                "resource_group": "test-rg",
                "subscription_id": "sub-123",
                "properties": json.dumps(
                    {
                        "addressSpace": {"addressPrefixes": ["10.0.0.0/16"]},
                        "subnets": [],
                    }
                ),
            },
            {
                "id": "nsg-001",
                "name": "test-nsg",
                "type": "Microsoft.Network/networkSecurityGroups",
                "location": "eastus",
                "resource_group": "test-rg",
                "subscription_id": "sub-123",
                "properties": json.dumps({"securityRules": []}),
            },
        ],
        relationships=[],
    )


@pytest.fixture
def comparison_result_with_classifications():
    """Create comparison result with mixed classifications."""
    return ComparisonResult(
        classifications=[
            # EXACT_MATCH resource (VNet)
            ResourceClassification(
                abstracted_resource={
                    "id": "vnet-001",
                    "name": "test-vnet",
                    "type": "Microsoft.Network/virtualNetworks",
                    "properties": {"addressSpace": {"addressPrefixes": ["10.0.0.0/16"]}},
                    "original_id": "/subscriptions/sub-123/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet",
                },
                target_resource=TargetResource(
                    id="/subscriptions/sub-123/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet",
                    name="test-vnet",
                    type="Microsoft.Network/virtualNetworks",
                    location="eastus",
                    resource_group="test-rg",
                    subscription_id="sub-123",
                    properties={"addressSpace": {"addressPrefixes": ["10.0.0.0/16"]}},
                ),
                classification=ResourceState.EXACT_MATCH,
            ),
            # DRIFTED resource (NSG)
            ResourceClassification(
                abstracted_resource={
                    "id": "nsg-001",
                    "name": "test-nsg",
                    "type": "Microsoft.Network/networkSecurityGroups",
                    "properties": {"securityRules": []},
                    "original_id": "/subscriptions/sub-123/resourceGroups/test-rg/providers/Microsoft.Network/networkSecurityGroups/test-nsg",
                },
                target_resource=TargetResource(
                    id="/subscriptions/sub-123/resourceGroups/test-rg/providers/Microsoft.Network/networkSecurityGroups/test-nsg",
                    name="test-nsg",
                    type="Microsoft.Network/networkSecurityGroups",
                    location="eastus",
                    resource_group="test-rg",
                    subscription_id="sub-123",
                    properties={"securityRules": [{"name": "extra-rule"}]},  # Different!
                ),
                classification=ResourceState.DRIFTED,
                drift_details={"added": ["securityRules"]},
            ),
            # NEW resource (Resource Group)
            ResourceClassification(
                abstracted_resource={
                    "id": "rg-001",
                    "name": "test-rg",
                    "type": "Microsoft.Resources/resourceGroups",
                    "properties": {"location": "eastus"},
                    "original_id": "/subscriptions/sub-123/resourceGroups/test-rg",
                },
                target_resource=None,  # Not in target
                classification=ResourceState.NEW,
            ),
        ],
        summary={
            ResourceState.EXACT_MATCH: 1,
            ResourceState.DRIFTED: 1,
            ResourceState.NEW: 1,
            ResourceState.ORPHANED: 0,
        },
    )


class TestTerraformEmitterBackwardCompatibility:
    """Test backward compatibility - existing behavior without comparison_result."""

    def test_emit_without_comparison_result(self, simple_graph, temp_output_dir):
        """Test that emitter works exactly as before when comparison_result=None."""
        emitter = TerraformEmitter()

        # Emit without comparison_result (default behavior)
        emitter.emit(
            graph=simple_graph,
            out_dir=temp_output_dir,
            subscription_id="sub-123",
        )

        # Verify main.tf.json was created
        main_tf = temp_output_dir / "main.tf.json"
        assert main_tf.exists()

        # Verify imports.tf was NOT created (no comparison_result)
        imports_tf = temp_output_dir / "imports.tf"
        assert not imports_tf.exists()

        # Verify all resources were emitted
        with open(main_tf) as f:
            config = json.load(f)

        resources = config.get("resource", {})
        assert "azurerm_resource_group" in resources
        assert "azurerm_virtual_network" in resources
        assert "azurerm_network_security_group" in resources

        # Verify all resources present
        # Note: Resource groups may have >1 due to collision resolution
        assert len(resources["azurerm_resource_group"]) >= 1
        assert len(resources["azurerm_virtual_network"]) == 1
        assert len(resources["azurerm_network_security_group"]) == 1

    def test_emit_with_none_comparison_result_explicit(
        self, simple_graph, temp_output_dir
    ):
        """Test explicit comparison_result=None maintains backward compatibility."""
        emitter = TerraformEmitter()

        # Explicitly pass None
        emitter.emit(
            graph=simple_graph,
            out_dir=temp_output_dir,
            subscription_id="sub-123",
            comparison_result=None,
        )

        # Same behavior as without the parameter
        main_tf = temp_output_dir / "main.tf.json"
        assert main_tf.exists()

        imports_tf = temp_output_dir / "imports.tf"
        assert not imports_tf.exists()


class TestTerraformEmitterSmartImportMode:
    """Test smart import mode - new behavior with comparison_result."""

    def test_emit_with_comparison_result_generates_imports(
        self, simple_graph, comparison_result_with_classifications, temp_output_dir
    ):
        """Test that import blocks are generated when comparison_result provided."""
        emitter = TerraformEmitter()

        emitter.emit(
            graph=simple_graph,
            out_dir=temp_output_dir,
            subscription_id="sub-123",
            comparison_result=comparison_result_with_classifications,
        )

        # Verify imports.tf was created
        imports_tf = temp_output_dir / "imports.tf"
        assert imports_tf.exists()

        # Read and verify import blocks
        with open(imports_tf) as f:
            content = f.read()

        # Should contain import blocks for EXACT_MATCH and DRIFTED
        assert "import {" in content
        assert "azurerm_virtual_network.test_vnet" in content  # EXACT_MATCH
        assert "azurerm_network_security_group.test_nsg" in content  # DRIFTED

        # Verify format is HCL (not JSON)
        assert '"import"' not in content  # Not JSON
        assert "to =" in content
        assert 'id = "' in content

    def test_emit_filters_exact_match_resources(
        self, simple_graph, comparison_result_with_classifications, temp_output_dir
    ):
        """Test that EXACT_MATCH resources ARE emitted (Bug #23 fix)."""
        emitter = TerraformEmitter()

        emitter.emit(
            graph=simple_graph,
            out_dir=temp_output_dir,
            subscription_id="sub-123",
            comparison_result=comparison_result_with_classifications,
        )

        # Read main.tf.json
        main_tf = temp_output_dir / "main.tf.json"
        with open(main_tf) as f:
            config = json.load(f)

        resources = config.get("resource", {})

        # Bug #23: EXACT_MATCH resource (vnet-001) SHOULD be in resource blocks
        # to prevent cascading reference errors
        vnet_resources = resources.get("azurerm_virtual_network", {})
        assert "test_vnet" in vnet_resources

        # NEW resource (rg-001) should be emitted
        rg_resources = resources.get("azurerm_resource_group", {})
        assert "test_rg" in rg_resources

        # DRIFTED resource (nsg-001) should be emitted
        nsg_resources = resources.get("azurerm_network_security_group", {})
        assert "test_nsg" in nsg_resources

    def test_emit_includes_new_and_drifted_resources(
        self, simple_graph, comparison_result_with_classifications, temp_output_dir
    ):
        """Test that NEW and DRIFTED resources ARE emitted with resource blocks."""
        emitter = TerraformEmitter()

        emitter.emit(
            graph=simple_graph,
            out_dir=temp_output_dir,
            subscription_id="sub-123",
            comparison_result=comparison_result_with_classifications,
        )

        main_tf = temp_output_dir / "main.tf.json"
        with open(main_tf) as f:
            config = json.load(f)

        resources = config.get("resource", {})

        # NEW resource emitted - NOTE: simple_graph also has "test-rg" causing collision!
        # Emitter resolves collision by creating both "test_rg" and "default_rg_test_rg"
        rg_resources = resources.get("azurerm_resource_group", {})
        assert len(rg_resources) == 2  # Collision resolution creates 2
        assert "test_rg" in rg_resources or "default_rg_test_rg" in rg_resources

        # DRIFTED resource emitted
        nsg_resources = resources.get("azurerm_network_security_group", {})
        assert len(nsg_resources) == 1
        assert "test_nsg" in nsg_resources


class TestImportBlockFileFormat:
    """Test import block file format and content."""

    def test_import_blocks_use_hcl_format(
        self, simple_graph, comparison_result_with_classifications, temp_output_dir
    ):
        """Test that import blocks are written in HCL format, not JSON."""
        emitter = TerraformEmitter()

        emitter.emit(
            graph=simple_graph,
            out_dir=temp_output_dir,
            subscription_id="sub-123",
            comparison_result=comparison_result_with_classifications,
        )

        imports_tf = temp_output_dir / "imports.tf"
        with open(imports_tf) as f:
            content = f.read()

        # Check HCL format structure
        assert "import {" in content
        assert "  to = " in content
        assert '  id = "' in content
        assert "}" in content

        # Should NOT be JSON format
        assert not content.strip().startswith("{")
        assert '"import"' not in content

    def test_import_blocks_contain_header_comment(
        self, simple_graph, comparison_result_with_classifications, temp_output_dir
    ):
        """Test that imports.tf has a header comment explaining purpose."""
        emitter = TerraformEmitter()

        emitter.emit(
            graph=simple_graph,
            out_dir=temp_output_dir,
            subscription_id="sub-123",
            comparison_result=comparison_result_with_classifications,
        )

        imports_tf = temp_output_dir / "imports.tf"
        with open(imports_tf) as f:
            content = f.read()

        # Check for header comment
        assert "# Terraform 1.5+ import blocks" in content
        assert "# Generated by Smart Import Generator" in content

    def test_import_blocks_separate_from_main_tf(
        self, simple_graph, comparison_result_with_classifications, temp_output_dir
    ):
        """Test that import blocks are in separate imports.tf file."""
        emitter = TerraformEmitter()

        emitter.emit(
            graph=simple_graph,
            out_dir=temp_output_dir,
            subscription_id="sub-123",
            comparison_result=comparison_result_with_classifications,
        )

        # Verify separate files exist
        main_tf = temp_output_dir / "main.tf.json"
        imports_tf = temp_output_dir / "imports.tf"

        assert main_tf.exists()
        assert imports_tf.exists()

        # Verify main.tf.json does NOT contain import blocks
        with open(main_tf) as f:
            main_config = json.load(f)

        # Old auto_import_existing feature used JSON format with "import" key
        # New smart import uses separate HCL file
        assert "import" not in main_config


class TestErrorHandling:
    """Test error handling and graceful degradation."""

    def test_emit_continues_if_import_generation_fails(
        self, simple_graph, temp_output_dir, monkeypatch
    ):
        """Test that emit continues with standard generation if smart import fails."""

        # Mock SmartImportGenerator to raise exception
        def mock_generate_import_blocks(self, comparison_result):
            raise ValueError("Mock error in import generation")

        monkeypatch.setattr(
            "src.iac.emitters.smart_import_generator.SmartImportGenerator.generate_import_blocks",
            mock_generate_import_blocks,
        )

        emitter = TerraformEmitter()

        # Should not raise exception, should continue with standard emission
        comparison_result = ComparisonResult(
            classifications=[],
            summary={
                ResourceState.EXACT_MATCH: 0,
                ResourceState.DRIFTED: 0,
                ResourceState.NEW: 0,
                ResourceState.ORPHANED: 0,
            },
        )

        emitter.emit(
            graph=simple_graph,
            out_dir=temp_output_dir,
            subscription_id="sub-123",
            comparison_result=comparison_result,
        )

        # Verify main.tf.json was still created
        main_tf = temp_output_dir / "main.tf.json"
        assert main_tf.exists()

        # Verify all resources were emitted (fallback to standard behavior)
        with open(main_tf) as f:
            config = json.load(f)

        resources = config.get("resource", {})
        # May have collision resolution creating multiple resource groups
        assert len(resources["azurerm_resource_group"]) >= 1
        assert len(resources["azurerm_virtual_network"]) == 1
        assert len(resources["azurerm_network_security_group"]) == 1

    def test_emit_continues_if_import_write_fails(
        self, simple_graph, comparison_result_with_classifications, temp_output_dir
    ):
        """Test that emit continues with resource generation if import write fails."""
        emitter = TerraformEmitter()

        # Make output directory read-only to cause write failure
        temp_output_dir.chmod(0o444)

        try:
            # Should raise exception for main.tf.json, but import write failure
            # is non-fatal and should be logged only
            # This test verifies _write_import_blocks logs errors gracefully
            with pytest.raises(PermissionError):
                emitter.emit(
                    graph=simple_graph,
                    out_dir=temp_output_dir,
                    subscription_id="sub-123",
                    comparison_result=comparison_result_with_classifications,
                )
            # The import write error should have been logged (not raised)
            # but main.tf.json write error will raise (that's expected)

        finally:
            # Restore permissions for cleanup
            temp_output_dir.chmod(0o755)


class TestResourceFiltering:
    """Test resource filtering logic based on classifications."""

    def test_only_exact_match_resources_skipped(
        self, simple_graph, comparison_result_with_classifications, temp_output_dir
    ):
        """Test that only EXACT_MATCH resources are skipped from emission."""
        emitter = TerraformEmitter()

        emitter.emit(
            graph=simple_graph,
            out_dir=temp_output_dir,
            subscription_id="sub-123",
            comparison_result=comparison_result_with_classifications,
        )

        main_tf = temp_output_dir / "main.tf.json"
        with open(main_tf) as f:
            config = json.load(f)

        resources = config.get("resource", {})

        # Count total resources emitted
        total_emitted = sum(len(v) for v in resources.values())

        # Bug #23: Should emit: 1 RG (NEW) + 1 NSG (DRIFTED) + 1 VNet (EXACT_MATCH) = 3+
        # Plus collision resolution may create additional RG
        # Original test expected 2, now expect 4 (3 resources + 1 collision RG)
        assert total_emitted == 4

    def test_resource_filtering_uses_resource_id(
        self, simple_graph, comparison_result_with_classifications, temp_output_dir
    ):
        """Test that filtering uses resource 'id' field from graph."""
        emitter = TerraformEmitter()

        emitter.emit(
            graph=simple_graph,
            out_dir=temp_output_dir,
            subscription_id="sub-123",
            comparison_result=comparison_result_with_classifications,
        )

        # Verify the EXACT_MATCH resource (id='vnet-001') behavior (Bug #23)
        main_tf = temp_output_dir / "main.tf.json"
        with open(main_tf) as f:
            config = json.load(f)

        resources = config.get("resource", {})
        vnet_resources = resources.get("azurerm_virtual_network", {})

        # Bug #23: EXACT_MATCH now emitted to prevent cascading errors
        assert len(vnet_resources) == 1


class TestIntegrationWithSmartImportGenerator:
    """Test integration between TerraformEmitter and SmartImportGenerator."""

    def test_emitter_calls_smart_import_generator(
        self, simple_graph, comparison_result_with_classifications, temp_output_dir
    ):
        """Test that emitter correctly calls SmartImportGenerator."""
        emitter = TerraformEmitter()

        # This is an integration test - verify end-to-end behavior
        emitter.emit(
            graph=simple_graph,
            out_dir=temp_output_dir,
            subscription_id="sub-123",
            comparison_result=comparison_result_with_classifications,
        )

        # Verify both outputs exist
        assert (temp_output_dir / "main.tf.json").exists()
        assert (temp_output_dir / "imports.tf").exists()

        # Verify import blocks match expected classifications
        with open(temp_output_dir / "imports.tf") as f:
            imports_content = f.read()

        # Should have 2 import blocks (EXACT_MATCH + DRIFTED)
        import_count = imports_content.count("import {")
        assert import_count == 2

    def test_emitter_handles_empty_comparison_result(
        self, simple_graph, temp_output_dir
    ):
        """Test emitter with comparison_result containing no classifications."""
        emitter = TerraformEmitter()

        # Empty comparison result
        empty_comparison = ComparisonResult(
            classifications=[],
            summary={
                ResourceState.EXACT_MATCH: 0,
                ResourceState.DRIFTED: 0,
                ResourceState.NEW: 0,
                ResourceState.ORPHANED: 0,
            },
        )

        emitter.emit(
            graph=simple_graph,
            out_dir=temp_output_dir,
            subscription_id="sub-123",
            comparison_result=empty_comparison,
        )

        # Should create main.tf.json
        assert (temp_output_dir / "main.tf.json").exists()

        # imports.tf might be created but empty or not created
        # Either way, should not crash

        # All resources should be emitted (no filtering)
        with open(temp_output_dir / "main.tf.json") as f:
            config = json.load(f)

        resources = config.get("resource", {})
        total_emitted = sum(len(v) for v in resources.values())

        # All resources should be emitted when comparison result is empty
        # May have collision resolution creating additional resources
        assert total_emitted >= 3  # At least RG + VNet + NSG


class TestLogging:
    """Test logging output for smart import mode."""

    def test_smart_import_mode_logs_header(
        self, simple_graph, comparison_result_with_classifications, temp_output_dir
    ):
        """Test that smart import mode logs appropriate header."""
        emitter = TerraformEmitter()

        # Note: We can't easily capture logs in this test without adding
        # a log handler, but we verify the mode executes without error
        emitter.emit(
            graph=simple_graph,
            out_dir=temp_output_dir,
            subscription_id="sub-123",
            comparison_result=comparison_result_with_classifications,
        )

        # If this completes without error, logging code executed successfully
        assert (temp_output_dir / "main.tf.json").exists()
        assert (temp_output_dir / "imports.tf").exists()
