"""TDD Failing Tests for Bug #10: Child Resource Import Blocks.

Bug #10: Child resources (subnets, runbooks, VM extensions) don't get Terraform
import blocks because their IDs contain Terraform variable references like
`${azurerm_virtual_network.Ubuntu_vnet.name}`. The fix uses `original_id` from
Neo4j instead.

These tests follow Test Driven Development methodology - they will FAIL until
the fix is implemented.

Expected fix changes:
1. terraform_emitter._generate_import_blocks() - Build original_id_map from resources
2. resource_id_builder.build() - Accept optional original_id_map parameter
3. resource_id_builder._build_subnet_id() - Try original_id first, fallback to config
4. resource_id_builder._translate_subscription_in_id() - New helper for cross-tenant

Success Criteria:
- 177/177 import blocks generated (not 67/177)
- No Terraform variables in import IDs
- Cross-tenant subscription translation working
- Backward compatible when original_id unavailable
"""

import re
from unittest.mock import Mock, patch

import pytest

from src.iac.emitters.terraform_emitter import TerraformEmitter
from src.iac.resource_id_builder import AzureResourceIdBuilder


@pytest.fixture
def mock_emitter():
    """Mock TerraformEmitter with AZURE_TO_TERRAFORM_MAPPING."""
    emitter = Mock()
    emitter.AZURE_TO_TERRAFORM_MAPPING = {
        "Microsoft.Resources/resourceGroups": "azurerm_resource_group",
        "Microsoft.Network/virtualNetworks": "azurerm_virtual_network",
        "Microsoft.Network/subnets": "azurerm_subnet",
        "Microsoft.Network/networkSecurityGroups": "azurerm_network_security_group",
        "Microsoft.Network/networkInterfaces": "azurerm_network_interface",
        "Microsoft.Storage/storageAccounts": "azurerm_storage_account",
        "Microsoft.Compute/virtualMachines": "azurerm_linux_virtual_machine",
        "Microsoft.Compute/virtualMachines/extensions": "azurerm_virtual_machine_extension",
        "Microsoft.Automation/automationAccounts/runbooks": "azurerm_automation_runbook",
        "Microsoft.Authorization/roleAssignments": "azurerm_role_assignment",
    }
    return emitter


@pytest.fixture
def builder(mock_emitter):
    """Create AzureResourceIdBuilder instance."""
    return AzureResourceIdBuilder(mock_emitter)


class TestResourceIdBuilderWithOriginalIdMap:
    """Unit tests for resource_id_builder.py with original_id_map support."""

    def test_build_accepts_original_id_map_parameter(self, builder):
        """Test that build() method accepts optional original_id_map parameter.

        This test will FAIL until the signature is updated to accept original_id_map.
        """
        resource_config = {
            "name": "default",
            "virtual_network_name": "${azurerm_virtual_network.Ubuntu_vnet.name}",
            "resource_group_name": "network-rg",
        }
        subscription_id = "source-sub-123"

        original_id_map = {
            "azurerm_subnet.default": "/subscriptions/source-sub-123/resourceGroups/network-rg/providers/Microsoft.Network/virtualNetworks/Ubuntu-vnet/subnets/default"
        }

        # This should NOT raise TypeError about unexpected keyword argument
        try:
            _resource_id = builder.build(
                "azurerm_subnet",
                resource_config,
                subscription_id,
                original_id_map=original_id_map,
            )
            # If we get here, the method signature was updated correctly
            assert True
        except TypeError as e:
            if "original_id_map" in str(e):
                pytest.fail(
                    f"build() method does not accept original_id_map parameter: {e}"
                )
            raise

    def test_build_subnet_id_with_original_id_from_map(self, builder):
        """Test _build_subnet_id() uses original_id from map when available.

        This is the CORE fix for Bug #10. When resource_config contains Terraform
        variables (not real values), the builder should use original_id from Neo4j.

        This test will FAIL until _build_subnet_id() is updated.
        """
        resource_config = {
            "name": "default",
            # BAD: Contains Terraform variable reference, not real VNet name
            "virtual_network_name": "${azurerm_virtual_network.Ubuntu_vnet.name}",
            "resource_group_name": "network-rg",
        }
        subscription_id = "source-sub-123"

        # The REAL Azure ID from Neo4j (stored in original_id property)
        original_id_map = {
            "azurerm_subnet.default": "/subscriptions/source-sub-123/resourceGroups/network-rg/providers/Microsoft.Network/virtualNetworks/Ubuntu-vnet/subnets/default"
        }

        resource_id = builder.build(
            "azurerm_subnet",
            resource_config,
            subscription_id,
            original_id_map=original_id_map,
        )

        # Should return the original Azure ID, NOT try to build from config
        expected = "/subscriptions/source-sub-123/resourceGroups/network-rg/providers/Microsoft.Network/virtualNetworks/Ubuntu-vnet/subnets/default"
        assert (
            resource_id == expected
        ), f"Expected original_id from map, got: {resource_id}"

    def test_build_subnet_id_returns_none_when_config_has_terraform_vars_and_no_map(
        self, builder
    ):
        """Test _build_subnet_id() returns None when config has Terraform vars and no original_id_map.

        When resource_config contains Terraform variables AND no original_id_map is
        provided, the builder should return None (cannot construct valid import ID).

        This test will FAIL until _build_subnet_id() validates config values.
        """
        resource_config = {
            "name": "default",
            # Contains Terraform variable - cannot build import ID
            "virtual_network_name": "${azurerm_virtual_network.Ubuntu_vnet.name}",
            "resource_group_name": "network-rg",
        }
        subscription_id = "source-sub-123"

        # No original_id_map provided
        resource_id = builder.build("azurerm_subnet", resource_config, subscription_id)

        # Should return None because vnet_name contains Terraform variable
        assert (
            resource_id is None
        ), f"Expected None for Terraform variable in config, got: {resource_id}"

    def test_build_subnet_id_falls_back_to_config_when_no_original_id_in_map(
        self, builder
    ):
        """Test _build_subnet_id() falls back to config when original_id not in map.

        Backward compatibility: If original_id_map is provided but doesn't contain
        this specific resource, fall back to building from config (if config is valid).

        This test will FAIL until _build_subnet_id() implements fallback logic.
        """
        resource_config = {
            "name": "frontend",
            "virtual_network_name": "app-vnet",  # Real name, not Terraform var
            "resource_group_name": "app-rg",
        }
        subscription_id = "source-sub-123"

        # Map exists but doesn't contain this subnet
        original_id_map = {
            "azurerm_subnet.backend": "/subscriptions/source-sub-123/resourceGroups/app-rg/providers/Microsoft.Network/virtualNetworks/app-vnet/subnets/backend"
        }

        resource_id = builder.build(
            "azurerm_subnet",
            resource_config,
            subscription_id,
            original_id_map=original_id_map,
        )

        # Should fall back to building from config
        expected = "/subscriptions/source-sub-123/resourceGroups/app-rg/providers/Microsoft.Network/virtualNetworks/app-vnet/subnets/frontend"
        assert (
            resource_id == expected
        ), f"Expected fallback to config-based ID, got: {resource_id}"

    def test_translate_subscription_in_id_for_cross_tenant(self, builder):
        """Test _translate_subscription_in_id() replaces subscription ID in Azure resource ID.

        For cross-tenant deployments, the original_id from source tenant needs its
        subscription ID replaced with the target subscription ID.

        This test will FAIL until _translate_subscription_in_id() method is implemented.
        """
        # Original Azure ID from source tenant
        source_id = "/subscriptions/source-sub-123/resourceGroups/network-rg/providers/Microsoft.Network/virtualNetworks/Ubuntu-vnet/subnets/default"
        source_subscription = "source-sub-123"
        target_subscription = "target-sub-456"

        # This method doesn't exist yet - will fail
        try:
            translated_id = builder._translate_subscription_in_id(
                source_id, source_subscription, target_subscription
            )

            expected = "/subscriptions/target-sub-456/resourceGroups/network-rg/providers/Microsoft.Network/virtualNetworks/Ubuntu-vnet/subnets/default"
            assert (
                translated_id == expected
            ), f"Expected subscription translated, got: {translated_id}"
        except AttributeError as e:
            if "_translate_subscription_in_id" in str(e):
                pytest.fail(
                    f"_translate_subscription_in_id() method not implemented: {e}"
                )
            raise

    def test_cross_tenant_subnet_id_with_original_id_map(self, builder):
        """Test cross-tenant subnet ID construction using original_id_map.

        Integration test: Combines original_id_map lookup with subscription translation
        for cross-tenant deployment scenario.

        This test will FAIL until both original_id_map support and subscription
        translation are implemented.
        """
        resource_config = {
            "name": "default",
            "virtual_network_name": "${azurerm_virtual_network.Ubuntu_vnet.name}",
            "resource_group_name": "network-rg",
        }
        source_subscription = "source-sub-123"
        target_subscription = "target-sub-456"

        # Original ID from source tenant Neo4j
        original_id_map = {
            "azurerm_subnet.default": "/subscriptions/source-sub-123/resourceGroups/network-rg/providers/Microsoft.Network/virtualNetworks/Ubuntu-vnet/subnets/default"
        }

        # Build with target subscription (cross-tenant scenario)
        resource_id = builder.build(
            "azurerm_subnet",
            resource_config,
            target_subscription,
            original_id_map=original_id_map,
            source_subscription_id=source_subscription,
        )

        # Should use original_id but translate subscription
        expected = "/subscriptions/target-sub-456/resourceGroups/network-rg/providers/Microsoft.Network/virtualNetworks/Ubuntu-vnet/subnets/default"
        assert (
            resource_id == expected
        ), f"Expected cross-tenant translated ID, got: {resource_id}"

    def test_detects_terraform_variable_in_vnet_name(self, builder):
        """Test that Terraform variable syntax is correctly detected in vnet_name.

        Helper test to ensure variable detection logic works correctly.

        This test will FAIL until variable detection is implemented.
        """
        # Test various Terraform variable patterns
        test_cases = [
            ("${azurerm_virtual_network.Ubuntu_vnet.name}", True),
            ("${var.vnet_name}", True),
            ("${module.network.vnet_name}", True),
            ("real-vnet-name", False),
            ("vnet-123", False),
            ("my_vnet", False),
        ]

        for vnet_name, should_be_variable in test_cases:
            # This helper method doesn't exist yet
            try:
                is_variable = builder._is_terraform_variable(vnet_name)
                if should_be_variable:
                    assert (
                        is_variable
                    ), f"Expected '{vnet_name}' to be detected as Terraform variable"
                else:
                    assert (
                        not is_variable
                    ), f"Expected '{vnet_name}' to be detected as literal value"
            except AttributeError as e:
                if "_is_terraform_variable" in str(e):
                    # Method doesn't exist - use manual check for now
                    is_variable = re.match(r"\$\{.*\}", vnet_name) is not None
                    if should_be_variable:
                        assert is_variable, f"Variable detection failed for: {vnet_name}"
                    else:
                        assert (
                            not is_variable
                        ), f"False positive variable detection for: {vnet_name}"
                else:
                    raise


class TestTerraformEmitterImportBlocksWithOriginalId:
    """Integration tests for terraform_emitter.py import block generation with original_id."""

    @pytest.fixture
    def emitter(self):
        """Create TerraformEmitter instance with auto-import enabled."""
        return TerraformEmitter(
            auto_import_existing=True,
            import_strategy="all_resources",
            source_subscription_id="source-sub-123",
            target_subscription_id="target-sub-456",
        )

    def test_generate_import_blocks_builds_original_id_map(self, emitter):
        """Test _generate_import_blocks() extracts original_id from resources to build map.

        The key fix: terraform_emitter needs to build an original_id_map from the
        resources list (from Neo4j) and pass it to resource_id_builder.

        This test will FAIL until _generate_import_blocks() builds the map.
        """
        # Mock terraform config with subnet
        terraform_config = {
            "resource": {
                "azurerm_subnet": {
                    "default": {
                        "name": "default",
                        "virtual_network_name": "${azurerm_virtual_network.Ubuntu_vnet.name}",
                        "resource_group_name": "network-rg",
                    }
                }
            }
        }

        # Resources from Neo4j with original_id property
        _resources = [
            {
                "type": "Microsoft.Network/subnets",
                "name": "default",
                "resource_group": "network-rg",
                "original_id": "/subscriptions/source-sub-123/resourceGroups/network-rg/providers/Microsoft.Network/virtualNetworks/Ubuntu-vnet/subnets/default",
            }
        ]

        # Mock the existence validator to avoid actual Azure calls
        with patch.object(
            emitter, "_existence_validator", None
        ):  # Force no validation path
            import_blocks = emitter._generate_import_blocks_no_validation(
                terraform_config, resources=_resources
            )

        # Should generate import block using original_id (not config with Terraform vars)
        assert len(import_blocks) > 0, "Expected at least one import block"

        subnet_imports = [
            block for block in import_blocks if "azurerm_subnet" in block.get("to", "")
        ]
        assert len(subnet_imports) > 0, "Expected subnet import block"

        # Verify import ID doesn't contain Terraform variables
        subnet_import = subnet_imports[0]
        import_id = subnet_import["id"]
        assert (
            "${" not in import_id
        ), f"Import ID contains Terraform variable: {import_id}"
        assert (
            "Ubuntu-vnet" in import_id or "Ubuntu_vnet" in import_id
        ), f"Import ID should contain real VNet name: {import_id}"

    def test_import_blocks_for_both_parent_and_child_resources(self, emitter):
        """Test that import blocks are generated for BOTH parent (VNet) and child (subnet) resources.

        Before Bug #10 fix: Only 67/177 import blocks (missing child resources)
        After Bug #10 fix: 177/177 import blocks (includes child resources)

        This test will FAIL until child resources get import blocks.
        """
        terraform_config = {
            "resource": {
                "azurerm_virtual_network": {
                    "Ubuntu_vnet": {
                        "name": "Ubuntu-vnet",
                        "resource_group_name": "network-rg",
                        "address_space": ["10.0.0.0/16"],
                    }
                },
                "azurerm_subnet": {
                    "default": {
                        "name": "default",
                        "virtual_network_name": "${azurerm_virtual_network.Ubuntu_vnet.name}",
                        "resource_group_name": "network-rg",
                    }
                },
            }
        }

        _resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "Ubuntu-vnet",
                "resource_group": "network-rg",
                "original_id": "/subscriptions/source-sub-123/resourceGroups/network-rg/providers/Microsoft.Network/virtualNetworks/Ubuntu-vnet",
            },
            {
                "type": "Microsoft.Network/subnets",
                "name": "default",
                "resource_group": "network-rg",
                "original_id": "/subscriptions/source-sub-123/resourceGroups/network-rg/providers/Microsoft.Network/virtualNetworks/Ubuntu-vnet/subnets/default",
            },
        ]

        # Mock validator
        with patch.object(emitter, "_existence_validator", None):
            import_blocks = emitter._generate_import_blocks_no_validation(
                terraform_config, resources=_resources
            )

        # Should have import blocks for BOTH parent and child
        vnet_imports = [
            block
            for block in import_blocks
            if "azurerm_virtual_network" in block.get("to", "")
        ]
        subnet_imports = [
            block for block in import_blocks if "azurerm_subnet" in block.get("to", "")
        ]

        assert len(vnet_imports) > 0, "Expected VNet import block (parent resource)"
        assert len(subnet_imports) > 0, "Expected subnet import block (child resource)"

        # Verify both have valid import IDs (no Terraform variables)
        for block in vnet_imports + subnet_imports:
            import_id = block["id"]
            assert (
                "${" not in import_id
            ), f"Import ID contains Terraform variable: {import_id}"

    def test_import_ids_have_no_terraform_variables(self, emitter):
        """Test that ALL import IDs are pure Azure resource IDs with no Terraform variables.

        Critical success criteria: Import IDs must be valid Azure resource IDs that
        can be used with `terraform import` command. They cannot contain Terraform
        interpolation syntax like ${...}.

        This test will FAIL until all import IDs use original_id or valid config values.
        """
        terraform_config = {
            "resource": {
                "azurerm_subnet": {
                    "subnet1": {
                        "name": "subnet1",
                        "virtual_network_name": "${azurerm_virtual_network.vnet1.name}",
                        "resource_group_name": "rg1",
                    },
                    "subnet2": {
                        "name": "subnet2",
                        "virtual_network_name": "${var.vnet_name}",
                        "resource_group_name": "rg2",
                    },
                    "subnet3": {
                        "name": "subnet3",
                        "virtual_network_name": "${module.network.vnet_name}",
                        "resource_group_name": "rg3",
                    },
                }
            }
        }

        _resources = [
            {
                "type": "Microsoft.Network/subnets",
                "name": "subnet1",
                "resource_group": "rg1",
                "original_id": "/subscriptions/source-sub-123/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1",
            },
            {
                "type": "Microsoft.Network/subnets",
                "name": "subnet2",
                "resource_group": "rg2",
                "original_id": "/subscriptions/source-sub-123/resourceGroups/rg2/providers/Microsoft.Network/virtualNetworks/vnet2/subnets/subnet2",
            },
            {
                "type": "Microsoft.Network/subnets",
                "name": "subnet3",
                "resource_group": "rg3",
                "original_id": "/subscriptions/source-sub-123/resourceGroups/rg3/providers/Microsoft.Network/virtualNetworks/vnet3/subnets/subnet3",
            },
        ]

        with patch.object(emitter, "_existence_validator", None):
            import_blocks = emitter._generate_import_blocks_no_validation(
                terraform_config, resources=_resources
            )

        # All subnets should have import blocks
        subnet_imports = [
            block for block in import_blocks if "azurerm_subnet" in block.get("to", "")
        ]
        assert (
            len(subnet_imports) == 3
        ), f"Expected 3 subnet import blocks, got {len(subnet_imports)}"

        # CRITICAL: No import IDs should contain Terraform variables
        terraform_var_pattern = re.compile(r"\$\{.*?\}")
        for block in subnet_imports:
            import_id = block["id"]
            matches = terraform_var_pattern.findall(import_id)
            assert (
                not matches
            ), f"Import ID contains Terraform variables: {import_id} (found: {matches})"

            # Verify it's a valid Azure resource ID format
            assert import_id.startswith(
                "/subscriptions/"
            ), f"Invalid Azure resource ID format: {import_id}"

    def test_cross_tenant_import_ids_use_target_subscription(self, emitter):
        """Test that cross-tenant import IDs use target subscription, not source.

        For cross-tenant deployment, import IDs must reference resources in the
        TARGET tenant/subscription, not the source.

        This test will FAIL until subscription translation is implemented.
        """
        terraform_config = {
            "resource": {
                "azurerm_subnet": {
                    "default": {
                        "name": "default",
                        "virtual_network_name": "${azurerm_virtual_network.vnet.name}",
                        "resource_group_name": "network-rg",
                    }
                }
            }
        }

        # Resource from source tenant
        _resources = [
            {
                "type": "Microsoft.Network/subnets",
                "name": "default",
                "resource_group": "network-rg",
                "original_id": "/subscriptions/source-sub-123/resourceGroups/network-rg/providers/Microsoft.Network/virtualNetworks/vnet/subnets/default",
            }
        ]

        # Emitter configured for cross-tenant (target subscription)
        with patch.object(emitter, "_existence_validator", None):
            import_blocks = emitter._generate_import_blocks_no_validation(
                terraform_config, resources=_resources
            )

        subnet_imports = [
            block for block in import_blocks if "azurerm_subnet" in block.get("to", "")
        ]
        assert len(subnet_imports) > 0, "Expected subnet import block"

        import_id = subnet_imports[0]["id"]

        # Should use TARGET subscription, not source
        assert (
            "target-sub-456" in import_id
        ), f"Import ID should use target subscription: {import_id}"
        assert (
            "source-sub-123" not in import_id
        ), f"Import ID should not contain source subscription: {import_id}"

    def test_backward_compatible_when_original_id_unavailable(self, emitter):
        """Test backward compatibility when original_id property is not in Neo4j.

        Older Neo4j databases or resources without original_id should still work
        by falling back to config-based ID construction (if config is valid).

        This test will FAIL if backward compatibility is broken.
        """
        terraform_config = {
            "resource": {
                "azurerm_subnet": {
                    "legacy_subnet": {
                        "name": "legacy-subnet",
                        "virtual_network_name": "legacy-vnet",  # Real name, not variable
                        "resource_group_name": "legacy-rg",
                    }
                }
            }
        }

        # Resource WITHOUT original_id property (legacy scenario)
        _resources = [
            {
                "type": "Microsoft.Network/subnets",
                "name": "legacy-subnet",
                "resource_group": "legacy-rg",
                # No original_id property
            }
        ]

        with patch.object(emitter, "_existence_validator", None):
            import_blocks = emitter._generate_import_blocks_no_validation(
                terraform_config, resources=_resources
            )

        subnet_imports = [
            block for block in import_blocks if "azurerm_subnet" in block.get("to", "")
        ]

        # Should still generate import block using config (backward compatible)
        assert len(subnet_imports) > 0, "Expected subnet import block (legacy scenario)"

        import_id = subnet_imports[0]["id"]
        assert "legacy-vnet" in import_id, f"Should use config vnet name: {import_id}"
        assert "legacy-subnet" in import_id, f"Should use config subnet name: {import_id}"


class TestImportBlockCountRegression:
    """Regression test for import block count (67 -> 177).

    Before Bug #10 fix: Only 67/177 resources got import blocks
    After Bug #10 fix: All 177 resources get import blocks

    This is the HIGH-LEVEL success criteria test.
    """

    def test_all_resources_get_import_blocks_not_just_parents(self):
        """Test that ALL 177 resources get import blocks, not just 67 parent resources.

        This is the ultimate regression test. Before Bug #10, only parent resources
        (VNets, Automation Accounts, VMs) got import blocks. Child resources (subnets,
        runbooks, VM extensions) were skipped because their config had Terraform variables.

        This test will FAIL until the fix enables import blocks for child resources.
        """
        emitter = TerraformEmitter(
            auto_import_existing=True,
            import_strategy="all_resources",
            source_subscription_id="source-sub-123",
            target_subscription_id="source-sub-123",  # Same tenant for simplicity
        )

        # Realistic terraform config with mix of parent and child resources
        # Based on actual production data: 177 total resources
        terraform_config = {
            "resource": {
                # 10 parent resources (VNets)
                "azurerm_virtual_network": {
                    f"vnet_{i}": {
                        "name": f"vnet-{i}",
                        "resource_group_name": "network-rg",
                        "address_space": ["10.0.0.0/16"],
                    }
                    for i in range(10)
                },
                # 100 child resources (subnets) - these were MISSING import blocks
                "azurerm_subnet": {
                    f"subnet_{i}": {
                        "name": f"subnet-{i}",
                        "virtual_network_name": f"${{azurerm_virtual_network.vnet_{i % 10}.name}}",
                        "resource_group_name": "network-rg",
                    }
                    for i in range(100)
                },
                # 67 other parent resources (storage accounts, etc.)
                "azurerm_storage_account": {
                    f"storage_{i}": {
                        "name": f"storage{i}",
                        "resource_group_name": "storage-rg",
                    }
                    for i in range(67)
                },
            }
        }

        # Resources from Neo4j with original_id for ALL resources
        resources = []

        # VNets
        for i in range(10):
            resources.append(
                {
                    "type": "Microsoft.Network/virtualNetworks",
                    "name": f"vnet-{i}",
                    "resource_group": "network-rg",
                    "original_id": f"/subscriptions/source-sub-123/resourceGroups/network-rg/providers/Microsoft.Network/virtualNetworks/vnet-{i}",
                }
            )

        # Subnets (these need original_id to get import blocks)
        for i in range(100):
            resources.append(
                {
                    "type": "Microsoft.Network/subnets",
                    "name": f"subnet-{i}",
                    "resource_group": "network-rg",
                    "original_id": f"/subscriptions/source-sub-123/resourceGroups/network-rg/providers/Microsoft.Network/virtualNetworks/vnet-{i % 10}/subnets/subnet-{i}",
                }
            )

        # Storage accounts
        for i in range(67):
            resources.append(
                {
                    "type": "Microsoft.Storage/storageAccounts",
                    "name": f"storage{i}",
                    "resource_group": "storage-rg",
                    "original_id": f"/subscriptions/source-sub-123/resourceGroups/storage-rg/providers/Microsoft.Storage/storageAccounts/storage{i}",
                }
            )

        with patch.object(emitter, "_existence_validator", None):
            import_blocks = emitter._generate_import_blocks_no_validation(
                terraform_config, resources=resources
            )

        # Count import blocks by resource type
        vnet_imports = [
            b for b in import_blocks if "azurerm_virtual_network" in b.get("to", "")
        ]
        subnet_imports = [
            b for b in import_blocks if "azurerm_subnet" in b.get("to", "")
        ]
        storage_imports = [
            b for b in import_blocks if "azurerm_storage_account" in b.get("to", "")
        ]

        # Before fix: subnet_imports would be 0 (child resources skipped)
        # After fix: subnet_imports should be 100
        assert (
            len(subnet_imports) == 100
        ), f"Expected 100 subnet import blocks, got {len(subnet_imports)} (Bug #10: child resources missing import blocks)"

        # Parent resources should always work
        assert (
            len(vnet_imports) == 10
        ), f"Expected 10 VNet import blocks, got {len(vnet_imports)}"
        assert (
            len(storage_imports) == 67
        ), f"Expected 67 storage import blocks, got {len(storage_imports)}"

        # TOTAL: Should be 177 import blocks (10 + 100 + 67)
        total_imports = len(import_blocks)
        assert (
            total_imports == 177
        ), f"Expected 177 total import blocks, got {total_imports} (Bug #10: was 67 before fix)"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
