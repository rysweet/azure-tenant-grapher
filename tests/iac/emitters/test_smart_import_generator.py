"""
Unit tests for SmartImportGenerator.

Tests all classification rules, edge cases, and error handling.
"""

import pytest

from src.iac.emitters.smart_import_generator import (
    ImportBlock,
    ImportBlockSet,
    SmartImportGenerator,
)
from src.iac.resource_comparator import (
    ComparisonResult,
    ResourceClassification,
    ResourceState,
)
from src.iac.target_scanner import TargetResource


@pytest.fixture
def generator():
    """Fixture providing SmartImportGenerator instance."""
    return SmartImportGenerator()


@pytest.fixture
def sample_abstracted_vnet():
    """Sample abstracted VNet resource."""
    return {
        "id": "vnet-a1b2c3d4",
        "name": "vnet-a1b2c3d4",
        "type": "Microsoft.Network/virtualNetworks",
        "location": "eastus",
        "tags": {"environment": "dev"},
    }


@pytest.fixture
def sample_target_vnet():
    """Sample target VNet resource."""
    return TargetResource(
        id="/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Network/virtualNetworks/my-vnet",
        name="my-vnet",
        type="Microsoft.Network/virtualNetworks",
        location="eastus",
        resource_group="rg-test",
        subscription_id="sub-123",
        tags={"environment": "dev"},
    )


@pytest.fixture
def sample_abstracted_storage():
    """Sample abstracted storage account resource."""
    return {
        "id": "storage-x9y8z7w6",
        "name": "storage-x9y8z7w6",
        "type": "Microsoft.Storage/storageAccounts",
        "location": "westus",
        "tags": {},
    }


@pytest.fixture
def sample_target_storage():
    """Sample target storage account resource."""
    return TargetResource(
        id="/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Storage/storageAccounts/mystorageacct",
        name="mystorageacct",
        type="Microsoft.Storage/storageAccounts",
        location="westus",
        resource_group="rg-test",
        subscription_id="sub-123",
        tags={},
    )


class TestExactMatchClassification:
    """Tests for EXACT_MATCH classification."""

    def test_exact_match_generates_import_only(
        self, generator, sample_abstracted_vnet, sample_target_vnet
    ):
        """EXACT_MATCH should generate import block AND emit resource (Bug #23 fix)."""
        classification = ResourceClassification(
            abstracted_resource=sample_abstracted_vnet,
            target_resource=sample_target_vnet,
            classification=ResourceState.EXACT_MATCH,
        )

        comparison_result = ComparisonResult(
            classifications=[classification],
            summary={
                ResourceState.EXACT_MATCH.value: 1,
                ResourceState.DRIFTED.value: 0,
                ResourceState.NEW.value: 0,
                ResourceState.ORPHANED.value: 0,
            },
        )

        result = generator.generate_import_blocks(comparison_result)

        # Should have import block
        assert len(result.import_blocks) == 1
        assert result.import_blocks[0].to == "azurerm_virtual_network.vnet_a1b2c3d4"
        assert (
            result.import_blocks[0].id
            == "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Network/virtualNetworks/my-vnet"
        )

        # Bug #23: Should ALSO be in emission list to prevent cascading reference errors
        assert len(result.resources_needing_emission) == 1

    def test_exact_match_with_hyphenated_name(self, generator, sample_target_vnet):
        """EXACT_MATCH with hyphenated name should sanitize to underscores."""
        abstracted_resource = {
            "id": "vnet-multi-part-name",
            "name": "vnet-multi-part-name",
            "type": "Microsoft.Network/virtualNetworks",
            "location": "eastus",
            "tags": {},
        }

        classification = ResourceClassification(
            abstracted_resource=abstracted_resource,
            target_resource=sample_target_vnet,
            classification=ResourceState.EXACT_MATCH,
        )

        comparison_result = ComparisonResult(
            classifications=[classification],
            summary={state.value: 0 for state in ResourceState},
        )

        result = generator.generate_import_blocks(comparison_result)

        # Name should be sanitized
        assert len(result.import_blocks) == 1
        assert (
            result.import_blocks[0].to == "azurerm_virtual_network.vnet_multi_part_name"
        )


class TestDriftedClassification:
    """Tests for DRIFTED classification."""

    def test_drifted_generates_import_and_emission(
        self, generator, sample_abstracted_storage, sample_target_storage
    ):
        """DRIFTED should generate import block AND include in emission list."""
        classification = ResourceClassification(
            abstracted_resource=sample_abstracted_storage,
            target_resource=sample_target_storage,
            classification=ResourceState.DRIFTED,
            drift_details={"property_differences": [{"property": "location"}]},
        )

        comparison_result = ComparisonResult(
            classifications=[classification],
            summary={
                ResourceState.EXACT_MATCH.value: 0,
                ResourceState.DRIFTED.value: 1,
                ResourceState.NEW.value: 0,
                ResourceState.ORPHANED.value: 0,
            },
        )

        result = generator.generate_import_blocks(comparison_result)

        # Should have import block
        assert len(result.import_blocks) == 1
        assert result.import_blocks[0].to == "azurerm_storage_account.storage_x9y8z7w6"
        assert (
            result.import_blocks[0].id
            == "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Storage/storageAccounts/mystorageacct"
        )

        # Should be in emission list
        assert len(result.resources_needing_emission) == 1
        assert result.resources_needing_emission[0] == sample_abstracted_storage


class TestNewClassification:
    """Tests for NEW classification."""

    def test_new_resource_emission_only(self, generator, sample_abstracted_vnet):
        """NEW should NOT generate import block but include in emission list."""
        classification = ResourceClassification(
            abstracted_resource=sample_abstracted_vnet,
            target_resource=None,
            classification=ResourceState.NEW,
        )

        comparison_result = ComparisonResult(
            classifications=[classification],
            summary={
                ResourceState.EXACT_MATCH.value: 0,
                ResourceState.DRIFTED.value: 0,
                ResourceState.NEW.value: 1,
                ResourceState.ORPHANED.value: 0,
            },
        )

        result = generator.generate_import_blocks(comparison_result)

        # Should NOT have import block
        assert len(result.import_blocks) == 0

        # Should be in emission list
        assert len(result.resources_needing_emission) == 1
        assert result.resources_needing_emission[0] == sample_abstracted_vnet


class TestOrphanedClassification:
    """Tests for ORPHANED classification."""

    def test_orphaned_resource_no_action(self, generator, sample_target_vnet):
        """ORPHANED should not generate import block or emit resource."""
        pseudo_abstracted = {
            "id": sample_target_vnet.id,
            "name": sample_target_vnet.name,
            "type": sample_target_vnet.type,
            "location": sample_target_vnet.location,
            "tags": sample_target_vnet.tags,
        }

        classification = ResourceClassification(
            abstracted_resource=pseudo_abstracted,
            target_resource=sample_target_vnet,
            classification=ResourceState.ORPHANED,
        )

        comparison_result = ComparisonResult(
            classifications=[classification],
            summary={
                ResourceState.EXACT_MATCH.value: 0,
                ResourceState.DRIFTED.value: 0,
                ResourceState.NEW.value: 0,
                ResourceState.ORPHANED.value: 1,
            },
        )

        result = generator.generate_import_blocks(comparison_result)

        # Should NOT have import block
        assert len(result.import_blocks) == 0

        # Should NOT be in emission list
        assert len(result.resources_needing_emission) == 0

    def test_orphaned_resource_logs_warning(
        self, generator, sample_target_vnet, caplog
    ):
        """ORPHANED should log warning about orphaned resource."""
        pseudo_abstracted = {
            "id": sample_target_vnet.id,
            "name": sample_target_vnet.name,
            "type": sample_target_vnet.type,
            "location": sample_target_vnet.location,
            "tags": sample_target_vnet.tags,
        }

        classification = ResourceClassification(
            abstracted_resource=pseudo_abstracted,
            target_resource=sample_target_vnet,
            classification=ResourceState.ORPHANED,
        )

        comparison_result = ComparisonResult(
            classifications=[classification],
            summary={state.value: 0 for state in ResourceState},
        )

        with caplog.at_level("WARNING"):
            generator.generate_import_blocks(comparison_result)

        # Should log warning
        assert "Orphaned resource detected" in caplog.text


class TestResourceNameSanitization:
    """Tests for resource name sanitization."""

    def test_sanitize_hyphenated_name(self, generator):
        """Hyphens should be replaced with underscores."""
        sanitized = generator._sanitize_resource_name("vnet-test-name")
        assert sanitized == "vnet_test_name"

    def test_sanitize_special_characters(self, generator):
        """Special characters should be removed."""
        sanitized = generator._sanitize_resource_name("vnet@test#name!")
        assert sanitized == "vnettestname"

    def test_sanitize_starts_with_number(self, generator):
        """Names starting with numbers should be prefixed."""
        sanitized = generator._sanitize_resource_name("123-vnet")
        assert sanitized == "r_123_vnet"

    def test_sanitize_empty_name(self, generator):
        """Empty names should default to 'unnamed_resource'."""
        sanitized = generator._sanitize_resource_name("")
        assert sanitized == "unnamed_resource"

    def test_sanitize_none_name(self, generator):
        """None names should default to 'unnamed_resource'."""
        sanitized = generator._sanitize_resource_name(None)
        assert sanitized == "unnamed_resource"

    def test_sanitize_only_special_chars(self, generator):
        """Names with only special characters should default."""
        sanitized = generator._sanitize_resource_name("@#$%")
        assert sanitized == "unnamed_resource"

    def test_sanitize_valid_name_unchanged(self, generator):
        """Valid names should remain unchanged."""
        sanitized = generator._sanitize_resource_name("valid_name_123")
        assert sanitized == "valid_name_123"


class TestUnknownResourceTypes:
    """Tests for unknown Azure resource types."""

    def test_unknown_type_skips_import(self, generator, sample_target_vnet):
        """Unknown Azure type should skip import block but emit resource (Bug #23)."""
        abstracted_resource = {
            "id": "unknown-resource-123",
            "name": "unknown-resource-123",
            "type": "Microsoft.Unknown/unknownType",
            "location": "eastus",
            "tags": {},
        }

        classification = ResourceClassification(
            abstracted_resource=abstracted_resource,
            target_resource=sample_target_vnet,
            classification=ResourceState.EXACT_MATCH,
        )

        comparison_result = ComparisonResult(
            classifications=[classification],
            summary={state.value: 0 for state in ResourceState},
        )

        result = generator.generate_import_blocks(comparison_result)

        # Should NOT have import block (unknown type has no Terraform mapping)
        assert len(result.import_blocks) == 0

        # Bug #23: Should STILL be in emission list to prevent cascading reference errors
        assert len(result.resources_needing_emission) == 1

    def test_unknown_type_logs_warning(self, generator, sample_target_vnet, caplog):
        """Unknown Azure type should log warning."""
        abstracted_resource = {
            "id": "unknown-resource-123",
            "name": "unknown-resource-123",
            "type": "Microsoft.Unknown/unknownType",
            "location": "eastus",
            "tags": {},
        }

        classification = ResourceClassification(
            abstracted_resource=abstracted_resource,
            target_resource=sample_target_vnet,
            classification=ResourceState.EXACT_MATCH,
        )

        comparison_result = ComparisonResult(
            classifications=[classification],
            summary={state.value: 0 for state in ResourceState},
        )

        with caplog.at_level("WARNING"):
            generator.generate_import_blocks(comparison_result)

        assert "Unknown Azure resource type" in caplog.text


class TestMissingResourceFields:
    """Tests for missing or invalid resource fields."""

    def test_missing_resource_type(self, generator, sample_target_vnet, caplog):
        """Missing resource type should skip import block."""
        abstracted_resource = {
            "id": "resource-123",
            "name": "resource-123",
            # Missing 'type'
            "location": "eastus",
            "tags": {},
        }

        classification = ResourceClassification(
            abstracted_resource=abstracted_resource,
            target_resource=sample_target_vnet,
            classification=ResourceState.EXACT_MATCH,
        )

        comparison_result = ComparisonResult(
            classifications=[classification],
            summary={state.value: 0 for state in ResourceState},
        )

        with caplog.at_level("WARNING"):
            result = generator.generate_import_blocks(comparison_result)

        # Should NOT have import block
        assert len(result.import_blocks) == 0
        assert "missing resource type" in caplog.text

    def test_missing_resource_name(self, generator, sample_target_vnet, caplog):
        """Missing resource name should skip import block."""
        abstracted_resource = {
            "id": "resource-123",
            # Missing 'name'
            "type": "Microsoft.Network/virtualNetworks",
            "location": "eastus",
            "tags": {},
        }

        classification = ResourceClassification(
            abstracted_resource=abstracted_resource,
            target_resource=sample_target_vnet,
            classification=ResourceState.EXACT_MATCH,
        )

        comparison_result = ComparisonResult(
            classifications=[classification],
            summary={state.value: 0 for state in ResourceState},
        )

        with caplog.at_level("WARNING"):
            result = generator.generate_import_blocks(comparison_result)

        # Should NOT have import block
        assert len(result.import_blocks) == 0
        assert "missing resource name" in caplog.text

    def test_missing_target_resource_id(self, generator, caplog):
        """Missing target resource ID should skip import block."""
        abstracted_resource = {
            "id": "resource-123",
            "name": "resource-123",
            "type": "Microsoft.Network/virtualNetworks",
            "location": "eastus",
            "tags": {},
        }

        # Target resource with no ID (shouldn't happen but test defensive code)
        target_resource = TargetResource(
            id="",  # Empty ID
            name="my-vnet",
            type="Microsoft.Network/virtualNetworks",
            location="eastus",
            resource_group="rg-test",
            subscription_id="sub-123",
            tags={},
        )

        classification = ResourceClassification(
            abstracted_resource=abstracted_resource,
            target_resource=target_resource,
            classification=ResourceState.DRIFTED,
        )

        comparison_result = ComparisonResult(
            classifications=[classification],
            summary={state.value: 0 for state in ResourceState},
        )

        with caplog.at_level("WARNING"):
            result = generator.generate_import_blocks(comparison_result)

        # Should NOT have import block
        assert len(result.import_blocks) == 0

        # Should still be in emission list (DRIFTED)
        assert len(result.resources_needing_emission) == 1
        assert "missing target resource ID" in caplog.text


class TestEmptyComparisonResult:
    """Tests for empty comparison results."""

    def test_empty_classifications(self, generator):
        """Empty comparison result should return empty import block set."""
        comparison_result = ComparisonResult(
            classifications=[],
            summary={state.value: 0 for state in ResourceState},
        )

        result = generator.generate_import_blocks(comparison_result)

        assert len(result.import_blocks) == 0
        assert len(result.resources_needing_emission) == 0


class TestMixedClassifications:
    """Tests for mixed classifications in single comparison."""

    def test_mixed_classifications(
        self,
        generator,
        sample_abstracted_vnet,
        sample_target_vnet,
        sample_abstracted_storage,
        sample_target_storage,
    ):
        """Mixed classifications should be handled correctly."""
        # EXACT_MATCH VNet
        exact_match = ResourceClassification(
            abstracted_resource=sample_abstracted_vnet,
            target_resource=sample_target_vnet,
            classification=ResourceState.EXACT_MATCH,
        )

        # DRIFTED Storage
        drifted = ResourceClassification(
            abstracted_resource=sample_abstracted_storage,
            target_resource=sample_target_storage,
            classification=ResourceState.DRIFTED,
            drift_details={"property_differences": []},
        )

        # NEW Resource Group
        new_rg = {
            "id": "rg-new123",
            "name": "rg-new123",
            "type": "Microsoft.Resources/resourceGroups",
            "location": "eastus",
            "tags": {},
        }
        new = ResourceClassification(
            abstracted_resource=new_rg,
            target_resource=None,
            classification=ResourceState.NEW,
        )

        # ORPHANED VM
        orphaned_vm = {
            "id": "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/vm-orphan",
            "name": "vm-orphan",
            "type": "Microsoft.Compute/virtualMachines",
            "location": "westus",
            "tags": {},
        }
        orphaned = ResourceClassification(
            abstracted_resource=orphaned_vm,
            target_resource=TargetResource(
                id=orphaned_vm["id"],
                name=orphaned_vm["name"],
                type=orphaned_vm["type"],
                location=orphaned_vm["location"],
                resource_group="rg-test",
                subscription_id="sub-123",
                tags=orphaned_vm["tags"],
            ),
            classification=ResourceState.ORPHANED,
        )

        comparison_result = ComparisonResult(
            classifications=[exact_match, drifted, new, orphaned],
            summary={
                ResourceState.EXACT_MATCH.value: 1,
                ResourceState.DRIFTED.value: 1,
                ResourceState.NEW.value: 1,
                ResourceState.ORPHANED.value: 1,
            },
        )

        result = generator.generate_import_blocks(comparison_result)

        # Should have 2 import blocks (EXACT_MATCH + DRIFTED)
        assert len(result.import_blocks) == 2

        # Should have 2 resources needing emission (DRIFTED + NEW)
        assert len(result.resources_needing_emission) == 2

        # Verify import blocks
        import_addresses = [block.to for block in result.import_blocks]
        assert "azurerm_virtual_network.vnet_a1b2c3d4" in import_addresses
        assert "azurerm_storage_account.storage_x9y8z7w6" in import_addresses

        # Verify emission list
        emission_ids = [res["id"] for res in result.resources_needing_emission]
        assert "storage-x9y8z7w6" in emission_ids
        assert "rg-new123" in emission_ids


class TestAzureToTerraformTypeMapping:
    """Tests for Azure to Terraform type mapping."""

    def test_common_resource_types_mapped(self, generator):
        """Common Azure resource types should map correctly."""
        mappings = {
            "Microsoft.Network/virtualNetworks": "azurerm_virtual_network",
            "Microsoft.Network/networkSecurityGroups": "azurerm_network_security_group",
            "Microsoft.Compute/virtualMachines": "azurerm_virtual_machine",
            "Microsoft.Storage/storageAccounts": "azurerm_storage_account",
            "Microsoft.Resources/resourceGroups": "azurerm_resource_group",
            "Microsoft.KeyVault/vaults": "azurerm_key_vault",
        }

        for azure_type, expected_tf_type in mappings.items():
            tf_type = generator._map_azure_to_terraform_type(azure_type)
            assert tf_type == expected_tf_type

    def test_unknown_type_returns_none(self, generator):
        """Unknown Azure type should return None."""
        tf_type = generator._map_azure_to_terraform_type("Microsoft.Unknown/type")
        assert tf_type is None


class TestImportBlockDataStructure:
    """Tests for ImportBlock data structure."""

    def test_import_block_creation(self):
        """ImportBlock should be created with to and id."""
        block = ImportBlock(
            to="azurerm_virtual_network.vnet_test",
            id="/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Network/virtualNetworks/vnet",
        )

        assert block.to == "azurerm_virtual_network.vnet_test"
        assert (
            block.id
            == "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Network/virtualNetworks/vnet"
        )


class TestImportBlockSetDataStructure:
    """Tests for ImportBlockSet data structure."""

    def test_import_block_set_creation(self):
        """ImportBlockSet should be created with blocks and resources."""
        block = ImportBlock(
            to="azurerm_virtual_network.vnet_test",
            id="/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Network/virtualNetworks/vnet",
        )

        resource = {
            "id": "vnet-test",
            "name": "vnet-test",
            "type": "Microsoft.Network/virtualNetworks",
        }

        block_set = ImportBlockSet(
            import_blocks=[block],
            resources_needing_emission=[resource],
        )

        assert len(block_set.import_blocks) == 1
        assert len(block_set.resources_needing_emission) == 1
        assert block_set.import_blocks[0] == block
        assert block_set.resources_needing_emission[0] == resource
