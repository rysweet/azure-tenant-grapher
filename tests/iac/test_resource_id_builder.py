"""Tests for Azure Resource ID Builder (Issue #502).

This module tests the strategy pattern-based Azure resource ID construction
for Terraform import blocks. Tests cover all 4 ID patterns implemented in Phase 1:
1. Resource Group Level (standard resources)
2. Child Resources (subnets)
3. Subscription Level (role assignments)
4. Association Resources (NSG associations)
"""

from unittest.mock import Mock

import pytest

from src.iac.resource_id_builder import (
    TERRAFORM_TYPE_TO_ID_PATTERN,
    AzureResourceIdBuilder,
    AzureResourceIdPattern,
)


@pytest.fixture
def mock_emitter():
    """Mock TerraformEmitter with AZURE_TO_TERRAFORM_MAPPING.

    Returns a mock emitter with realistic Azure-to-Terraform type mappings
    that match the production mappings in terraform_emitter.py.
    """
    emitter = Mock()
    emitter.AZURE_TO_TERRAFORM_MAPPING = {
        "Microsoft.Resources/resourceGroups": "azurerm_resource_group",
        "Microsoft.Network/virtualNetworks": "azurerm_virtual_network",
        "Microsoft.Network/subnets": "azurerm_subnet",
        "Microsoft.Network/networkSecurityGroups": "azurerm_network_security_group",
        "Microsoft.Network/networkInterfaces": "azurerm_network_interface",
        "Microsoft.Storage/storageAccounts": "azurerm_storage_account",
        "Microsoft.Compute/virtualMachines": "azurerm_linux_virtual_machine",
        "Microsoft.Authorization/roleAssignments": "azurerm_role_assignment",
        "Microsoft.KeyVault/vaults": "azurerm_key_vault",
    }
    return emitter


@pytest.fixture
def builder(mock_emitter):
    """Create AzureResourceIdBuilder instance.

    Args:
        mock_emitter: Mock TerraformEmitter fixture

    Returns:
        Configured AzureResourceIdBuilder instance
    """
    return AzureResourceIdBuilder(mock_emitter)


class TestResourceGroupLevelPattern:
    """Tests for RESOURCE_GROUP_LEVEL pattern (standard Azure resources).

    This pattern handles most Azure resources that live under resource groups.
    Format: /subscriptions/{sub}/resourceGroups/{rg}/providers/{provider}/{type}/{name}
    """

    def test_standard_resource_id_construction(self, builder):
        """Test standard resource ID construction for storage account."""
        resource_config = {
            "name": "mystorage123",
            "resource_group_name": "my-rg",
            "location": "eastus",
        }
        subscription_id = "11111111-1111-1111-1111-111111111111"

        resource_id = builder.build(
            "azurerm_storage_account", resource_config, subscription_id
        )

        expected = (
            "/subscriptions/11111111-1111-1111-1111-111111111111/"
            "resourceGroups/my-rg/"
            "providers/Microsoft.Storage/storageAccounts/mystorage123"
        )
        assert resource_id == expected

    def test_resource_group_itself(self, builder):
        """Test resource group ID construction (special case - no provider)."""
        resource_config = {
            "name": "my-resource-group",
            "location": "westus",
        }
        subscription_id = "22222222-2222-2222-2222-222222222222"

        resource_id = builder.build(
            "azurerm_resource_group", resource_config, subscription_id
        )

        expected = "/subscriptions/22222222-2222-2222-2222-222222222222/resourceGroups/my-resource-group"
        assert resource_id == expected

    def test_missing_resource_group_name_returns_none(self, builder):
        """Test that missing resource_group_name returns None."""
        resource_config = {
            "name": "my-vnet",
            "location": "eastus",
            # Missing resource_group_name
        }
        subscription_id = "33333333-3333-3333-3333-333333333333"

        resource_id = builder.build(
            "azurerm_virtual_network", resource_config, subscription_id
        )

        assert resource_id is None

    def test_missing_name_returns_none(self, builder):
        """Test that missing name field returns None."""
        resource_config = {
            "resource_group_name": "my-rg",
            "location": "eastus",
            # Missing name
        }
        subscription_id = "44444444-4444-4444-4444-444444444444"

        resource_id = builder.build(
            "azurerm_storage_account", resource_config, subscription_id
        )

        assert resource_id is None

    def test_unknown_terraform_type_returns_none(self, builder):
        """Test that unknown Terraform type returns None."""
        resource_config = {
            "name": "my-resource",
            "resource_group_name": "my-rg",
        }
        subscription_id = "55555555-5555-5555-5555-555555555555"

        resource_id = builder.build(
            "azurerm_unknown_resource_type", resource_config, subscription_id
        )

        assert resource_id is None


class TestChildResourcePattern:
    """Tests for CHILD_RESOURCE pattern (nested resources like subnets).

    Child resources are nested under parent resources in Azure's hierarchy.
    Impact: 266 subnets in production.
    """

    def test_valid_subnet_id_with_all_required_fields(self, builder):
        """Test subnet ID construction with all required fields."""
        resource_config = {
            "name": "default",
            "virtual_network_name": "my-vnet",
            "resource_group_name": "network-rg",
            "address_prefixes": ["10.0.1.0/24"],
        }
        subscription_id = "66666666-6666-6666-6666-666666666666"

        resource_id = builder.build("azurerm_subnet", resource_config, subscription_id)

        expected = (
            "/subscriptions/66666666-6666-6666-6666-666666666666/"
            "resourceGroups/network-rg/"
            "providers/Microsoft.Network/virtualNetworks/my-vnet/"
            "subnets/default"
        )
        assert resource_id == expected

    def test_missing_virtual_network_name_returns_none(self, builder):
        """Test that missing virtual_network_name returns None."""
        resource_config = {
            "name": "default",
            "resource_group_name": "network-rg",
            # Missing virtual_network_name
        }
        subscription_id = "77777777-7777-7777-7777-777777777777"

        resource_id = builder.build("azurerm_subnet", resource_config, subscription_id)

        assert resource_id is None

    def test_missing_resource_group_name_returns_none(self, builder):
        """Test that missing resource_group_name returns None."""
        resource_config = {
            "name": "default",
            "virtual_network_name": "my-vnet",
            # Missing resource_group_name
        }
        subscription_id = "88888888-8888-8888-8888-888888888888"

        resource_id = builder.build("azurerm_subnet", resource_config, subscription_id)

        assert resource_id is None

    def test_missing_subnet_name_returns_none(self, builder):
        """Test that missing subnet name returns None."""
        resource_config = {
            "virtual_network_name": "my-vnet",
            "resource_group_name": "network-rg",
            # Missing name
        }
        subscription_id = "99999999-9999-9999-9999-999999999999"

        resource_id = builder.build("azurerm_subnet", resource_config, subscription_id)

        assert resource_id is None


class TestSubscriptionLevelPattern:
    """Tests for SUBSCRIPTION_LEVEL pattern (role assignments).

    Subscription-level resources are not scoped to resource groups.
    Impact: 1,017 role assignments in production.
    """

    def test_role_assignment_with_explicit_scope(self, builder):
        """Test role assignment with explicit scope field."""
        resource_config = {
            "name": "12345678-1234-1234-1234-123456789012",
            "scope": "/subscriptions/aaaa-bbbb-cccc-dddd/resourceGroups/my-rg",
            "role_definition_name": "Contributor",
        }
        subscription_id = "aaaa-bbbb-cccc-dddd"

        resource_id = builder.build(
            "azurerm_role_assignment", resource_config, subscription_id
        )

        expected = (
            "/subscriptions/aaaa-bbbb-cccc-dddd/resourceGroups/my-rg/"
            "providers/Microsoft.Authorization/roleAssignments/"
            "12345678-1234-1234-1234-123456789012"
        )
        assert resource_id == expected

    def test_role_assignment_with_resource_group_name(self, builder):
        """Test role assignment with resource_group_name (inferred RG scope)."""
        resource_config = {
            "name": "87654321-4321-4321-4321-210987654321",
            "resource_group_name": "my-rg",
            "role_definition_name": "Reader",
        }
        subscription_id = "bbbb-cccc-dddd-eeee"

        resource_id = builder.build(
            "azurerm_role_assignment", resource_config, subscription_id
        )

        expected = (
            "/subscriptions/bbbb-cccc-dddd-eeee/"
            "resourceGroups/my-rg/"
            "providers/Microsoft.Authorization/roleAssignments/"
            "87654321-4321-4321-4321-210987654321"
        )
        assert resource_id == expected

    def test_role_assignment_with_neither_scope_nor_rg(self, builder):
        """Test role assignment with neither scope nor RG (subscription scope)."""
        resource_config = {
            "name": "ffffffff-ffff-ffff-ffff-ffffffffffff",
            "role_definition_name": "Owner",
        }
        subscription_id = "cccc-dddd-eeee-ffff"

        resource_id = builder.build(
            "azurerm_role_assignment", resource_config, subscription_id
        )

        expected = (
            "/subscriptions/cccc-dddd-eeee-ffff/"
            "providers/Microsoft.Authorization/roleAssignments/"
            "ffffffff-ffff-ffff-ffff-ffffffffffff"
        )
        assert resource_id == expected

    def test_missing_name_returns_none(self, builder):
        """Test that missing name returns None."""
        resource_config = {
            "scope": "/subscriptions/test-sub/resourceGroups/test-rg",
            "role_definition_name": "Contributor",
            # Missing name
        }
        subscription_id = "dddd-eeee-ffff-0000"

        resource_id = builder.build(
            "azurerm_role_assignment", resource_config, subscription_id
        )

        assert resource_id is None

    def test_empty_scope_defaults_to_subscription(self, builder):
        """Test that empty scope string defaults to subscription scope."""
        resource_config = {
            "name": "00000000-0000-0000-0000-000000000000",
            "scope": "",  # Empty scope
            "role_definition_name": "Reader",
        }
        subscription_id = "eeee-ffff-0000-1111"

        resource_id = builder.build(
            "azurerm_role_assignment", resource_config, subscription_id
        )

        # Should default to subscription scope
        expected = (
            "/subscriptions/eeee-ffff-0000-1111/"
            "providers/Microsoft.Authorization/roleAssignments/"
            "00000000-0000-0000-0000-000000000000"
        )
        assert resource_id == expected

    def test_whitespace_only_scope_defaults_to_subscription(self, builder):
        """Test that whitespace-only scope string defaults to subscription scope."""
        resource_config = {
            "name": "11111111-1111-1111-1111-111111111111",
            "scope": "   ",  # Whitespace only - should be trimmed to empty
            "role_definition_name": "Contributor",
        }
        subscription_id = "ffff-0000-1111-2222"

        resource_id = builder.build(
            "azurerm_role_assignment", resource_config, subscription_id
        )

        # Should default to subscription scope after trimming whitespace
        expected = (
            "/subscriptions/ffff-0000-1111-2222/"
            "providers/Microsoft.Authorization/roleAssignments/"
            "11111111-1111-1111-1111-111111111111"
        )
        assert resource_id == expected

    def test_invalid_scope_format_returns_none(self, builder):
        """Test that scope without leading slash is rejected."""
        resource_config = {
            "name": "22222222-2222-2222-2222-222222222222",
            "scope": "subscriptions/invalid/format",  # Missing leading /
            "role_definition_name": "Owner",
        }
        subscription_id = "0000-1111-2222-3333"

        resource_id = builder.build(
            "azurerm_role_assignment", resource_config, subscription_id
        )

        # Should return None due to invalid scope format
        assert resource_id is None

    def test_scope_with_leading_slash_is_valid(self, builder):
        """Test that scope with proper leading slash is accepted."""
        resource_config = {
            "name": "33333333-3333-3333-3333-333333333333",
            "scope": "/subscriptions/aaaa-bbbb-cccc-dddd/providers/Microsoft.Authorization/roleDefinitions/custom",
            "role_definition_name": "CustomRole",
        }
        subscription_id = "eeee-ffff-0000-1111"

        resource_id = builder.build(
            "azurerm_role_assignment", resource_config, subscription_id
        )

        # Should use the explicit scope
        expected = (
            "/subscriptions/aaaa-bbbb-cccc-dddd/providers/Microsoft.Authorization/roleDefinitions/custom/"
            "providers/Microsoft.Authorization/roleAssignments/"
            "33333333-3333-3333-3333-333333333333"
        )
        assert resource_id == expected


class TestAssociationPattern:
    """Tests for ASSOCIATION pattern (NSG associations).

    Association resources are synthetic Terraform constructs that cannot be imported.
    They contain Terraform interpolations, not Azure resource IDs.
    Impact: 86 associations in production - all return None (no import blocks).
    """

    def test_subnet_nsg_association_returns_none(self, builder):
        """Test subnet-NSG association returns None (not importable)."""
        resource_config = {
            "subnet_id": "${azurerm_subnet.subnet_1.id}",
            "network_security_group_id": "${azurerm_network_security_group.nsg_1.id}",
        }
        subscription_id = "sub1"

        resource_id = builder.build(
            "azurerm_subnet_network_security_group_association",
            resource_config,
            subscription_id,
        )

        # Association resources cannot be imported - they're Terraform constructs
        assert resource_id is None

    def test_nic_nsg_association_returns_none(self, builder):
        """Test NIC-NSG association returns None (not importable)."""
        resource_config = {
            "network_interface_id": "${azurerm_network_interface.nic_1.id}",
            "network_security_group_id": "${azurerm_network_security_group.nsg_2.id}",
        }
        subscription_id = "sub2"

        resource_id = builder.build(
            "azurerm_network_interface_security_group_association",
            resource_config,
            subscription_id,
        )

        # Association resources cannot be imported - they're Terraform constructs
        assert resource_id is None

    def test_missing_subnet_id_returns_none(self, builder):
        """Test that missing subnet_id returns None."""
        resource_config = {
            "network_security_group_id": "/subscriptions/sub3/resourceGroups/rg3/providers/Microsoft.Network/networkSecurityGroups/nsg3",
            # Missing subnet_id
        }
        subscription_id = "sub3"

        resource_id = builder.build(
            "azurerm_subnet_network_security_group_association",
            resource_config,
            subscription_id,
        )

        assert resource_id is None

    def test_missing_nsg_id_returns_none(self, builder):
        """Test that missing nsg_id returns None."""
        resource_config = {
            "subnet_id": "/subscriptions/sub4/resourceGroups/rg4/providers/Microsoft.Network/virtualNetworks/vnet4/subnets/subnet4",
            # Missing network_security_group_id
        }
        subscription_id = "sub4"

        resource_id = builder.build(
            "azurerm_subnet_network_security_group_association",
            resource_config,
            subscription_id,
        )

        assert resource_id is None

    def test_missing_nic_id_returns_none(self, builder):
        """Test that missing NIC ID returns None."""
        resource_config = {
            "network_security_group_id": "/subscriptions/sub5/resourceGroups/rg5/providers/Microsoft.Network/networkSecurityGroups/nsg5",
            # Missing network_interface_id
        }
        subscription_id = "sub5"

        resource_id = builder.build(
            "azurerm_network_interface_security_group_association",
            resource_config,
            subscription_id,
        )

        assert resource_id is None

    def test_empty_subnet_id_returns_none(self, builder):
        """Test that empty subnet_id string returns None."""
        resource_config = {
            "subnet_id": "",  # Empty string
            "network_security_group_id": "/subscriptions/sub6/resourceGroups/rg6/providers/Microsoft.Network/networkSecurityGroups/nsg6",
        }
        subscription_id = "sub6"

        resource_id = builder.build(
            "azurerm_subnet_network_security_group_association",
            resource_config,
            subscription_id,
        )

        assert resource_id is None


class TestPatternDetection:
    """Tests for pattern detection and dispatching."""

    def test_unknown_type_defaults_to_resource_group_pattern(self, builder):
        """Test that unknown types default to RESOURCE_GROUP_LEVEL pattern."""
        # This type is not in TERRAFORM_TYPE_TO_ID_PATTERN, so should default
        assert "azurerm_key_vault" not in TERRAFORM_TYPE_TO_ID_PATTERN, (
            "Test assumption: azurerm_key_vault should not have explicit pattern mapping"
        )

        resource_config = {
            "name": "my-keyvault",
            "resource_group_name": "security-rg",
            "location": "eastus",
        }
        subscription_id = "ffff-0000-1111-2222"

        resource_id = builder.build(
            "azurerm_key_vault", resource_config, subscription_id
        )

        # Should use resource group level pattern
        expected = (
            "/subscriptions/ffff-0000-1111-2222/"
            "resourceGroups/security-rg/"
            "providers/Microsoft.KeyVault/vaults/my-keyvault"
        )
        assert resource_id == expected

    def test_known_types_dispatch_to_correct_pattern(self, builder):
        """Test that known types dispatch to their specific patterns."""
        # Verify pattern mappings exist
        assert (
            TERRAFORM_TYPE_TO_ID_PATTERN["azurerm_subnet"]
            == AzureResourceIdPattern.CHILD_RESOURCE
        )
        assert (
            TERRAFORM_TYPE_TO_ID_PATTERN["azurerm_role_assignment"]
            == AzureResourceIdPattern.SUBSCRIPTION_LEVEL
        )
        assert (
            TERRAFORM_TYPE_TO_ID_PATTERN[
                "azurerm_subnet_network_security_group_association"
            ]
            == AzureResourceIdPattern.ASSOCIATION
        )


class TestIntegration:
    """Integration tests with real-world scenarios."""

    def test_with_real_terraform_emitter_instance(self, mock_emitter):
        """Test with realistic emitter instance."""
        builder = AzureResourceIdBuilder(mock_emitter)

        # Test multiple resource types
        test_cases = [
            # (tf_type, config, subscription_id, expected_substring)
            (
                "azurerm_virtual_network",
                {"name": "vnet1", "resource_group_name": "network-rg"},
                "sub1",
                "Microsoft.Network/virtualNetworks/vnet1",
            ),
            (
                "azurerm_subnet",
                {
                    "name": "subnet1",
                    "virtual_network_name": "vnet1",
                    "resource_group_name": "network-rg",
                },
                "sub1",
                "virtualNetworks/vnet1/subnets/subnet1",
            ),
            (
                "azurerm_role_assignment",
                {"name": "role1"},
                "sub1",
                "Microsoft.Authorization/roleAssignments/role1",
            ),
        ]

        for tf_type, config, sub_id, expected_substr in test_cases:
            resource_id = builder.build(tf_type, config, sub_id)
            assert resource_id is not None, f"Failed to build ID for {tf_type}"
            assert expected_substr in resource_id, (
                f"Expected substring not found in {resource_id}"
            )

    def test_reverse_mapping_correctness(self, builder):
        """Test that reverse mapping from AZURE_TO_TERRAFORM_MAPPING works."""
        # Build a storage account ID
        resource_config = {
            "name": "storage123",
            "resource_group_name": "data-rg",
        }
        subscription_id = "test-sub"

        resource_id = builder.build(
            "azurerm_storage_account", resource_config, subscription_id
        )

        # Verify reverse mapping worked (should contain Microsoft.Storage/storageAccounts)
        assert "Microsoft.Storage/storageAccounts" in resource_id

    def test_exception_handling_in_builder(self, builder):
        """Test that exceptions are caught and logged."""
        # Malformed config that could cause exceptions
        resource_config = {"name": None}  # None name could cause issues
        subscription_id = "test-sub"

        # Should not raise exception, should return None
        resource_id = builder.build(
            "azurerm_storage_account", resource_config, subscription_id
        )
        assert resource_id is None

    def test_cross_tenant_subscription_ids(self, builder):
        """Test that subscription IDs are correctly used in cross-tenant scenarios."""
        source_subscription = "source-sub-123"
        target_subscription = "target-sub-456"

        resource_config = {
            "name": "my-vnet",
            "resource_group_name": "network-rg",
        }

        # Build with target subscription
        resource_id = builder.build(
            "azurerm_virtual_network", resource_config, target_subscription
        )

        # Should use target subscription
        assert target_subscription in resource_id
        assert source_subscription not in resource_id


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_special_characters_in_names(self, builder):
        """Test handling of special characters in resource names."""
        resource_config = {
            "name": "my-resource_name.v2",
            "resource_group_name": "my-rg-123",
        }
        subscription_id = "edge-case-sub"

        resource_id = builder.build(
            "azurerm_storage_account", resource_config, subscription_id
        )

        # Should preserve special characters
        assert "my-resource_name.v2" in resource_id
        assert "my-rg-123" in resource_id

    def test_very_long_resource_names(self, builder):
        """Test handling of very long resource names."""
        long_name = "a" * 200  # Very long name
        resource_config = {
            "name": long_name,
            "resource_group_name": "rg",
        }
        subscription_id = "long-name-sub"

        resource_id = builder.build(
            "azurerm_storage_account", resource_config, subscription_id
        )

        # Should handle long names
        assert long_name in resource_id

    def test_unicode_characters_in_names(self, builder):
        """Test handling of unicode characters in resource names."""
        resource_config = {
            "name": "my-resource-ñ-test",
            "resource_group_name": "rg-ñ",
        }
        subscription_id = "unicode-sub"

        resource_id = builder.build(
            "azurerm_storage_account", resource_config, subscription_id
        )

        # Should handle unicode
        assert "my-resource-ñ-test" in resource_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
