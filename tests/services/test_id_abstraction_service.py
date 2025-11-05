"""Tests for ID Abstraction Service - Dual Graph Architecture (Issue #420).

This test suite validates the ID abstraction service that creates deterministic,
type-prefixed hashed IDs for Azure resources.

Test Categories:
- Hash generation (deterministic, reproducible)
- Type-prefixed format (vm-{hash}, storage-{hash}, etc.)
- Full resource ID translation
- Subscription ID abstraction
- Resource group name abstraction
- Seed-based reproducibility
- All Azure resource types handling
"""

import re
from typing import Dict

import pytest

from src.services.id_abstraction_service import IDAbstractionService

# Pytest marker for dual-graph feature tests
pytestmark = pytest.mark.dual_graph


class TestIDAbstractionService:
    """Test suite for ID Abstraction Service."""

    @pytest.fixture
    def tenant_seed(self) -> str:
        """Provide a consistent tenant seed for testing."""
        return "test-tenant-seed-12345"

    @pytest.fixture
    def sample_resource_ids(self) -> Dict[str, str]:
        """Provide sample Azure resource IDs for testing."""
        return {
            "vm": "/subscriptions/abc123/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm-001",
            "storage": "/subscriptions/abc123/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/teststorage001",
            "vnet": "/subscriptions/abc123/resourceGroups/network-rg/providers/Microsoft.Network/virtualNetworks/vnet-prod",
            "subnet": "/subscriptions/abc123/resourceGroups/network-rg/providers/Microsoft.Network/virtualNetworks/vnet-prod/subnets/subnet-web",
            "nsg": "/subscriptions/abc123/resourceGroups/network-rg/providers/Microsoft.Network/networkSecurityGroups/nsg-web",
            "keyvault": "/subscriptions/abc123/resourceGroups/security-rg/providers/Microsoft.KeyVault/vaults/kv-prod-001",
        }

    def test_service_initialization(self, tenant_seed):
        """Test IDAbstractionService can be initialized with a tenant seed."""
        service = IDAbstractionService(tenant_seed)
        assert service.tenant_seed == tenant_seed
        assert service.hash_length == 16  # Default

    def test_service_initialization_custom_hash_length(self, tenant_seed):
        """Test IDAbstractionService can be initialized with custom hash length."""
        service = IDAbstractionService(tenant_seed, hash_length=8)
        assert service.tenant_seed == tenant_seed
        assert service.hash_length == 8

    def test_service_initialization_invalid_seed(self):
        """Test that initialization fails with invalid seed."""
        with pytest.raises(ValueError, match="tenant_seed must be a non-empty string"):
            IDAbstractionService("")

        with pytest.raises(ValueError, match="tenant_seed must be a non-empty string"):
            IDAbstractionService(None)  # type: ignore

    def test_service_initialization_invalid_hash_length(self, tenant_seed):
        """Test that initialization fails with invalid hash length."""
        with pytest.raises(ValueError, match="hash_length must be between 8 and 64"):
            IDAbstractionService(tenant_seed, hash_length=4)

        with pytest.raises(ValueError, match="hash_length must be between 8 and 64"):
            IDAbstractionService(tenant_seed, hash_length=100)

    def test_deterministic_hash_generation(self, tenant_seed):
        """Test that same input produces same hash output (deterministic)."""
        service = IDAbstractionService(tenant_seed)

        resource_name = "test-vm-001"
        hash1 = service._hash(resource_name)
        hash2 = service._hash(resource_name)

        assert hash1 == hash2
        assert len(hash1) == 16  # Default hash length

    def test_type_prefixed_format_vm(self, tenant_seed, sample_resource_ids):
        """Test VM resource gets 'vm-' prefix."""
        service = IDAbstractionService(tenant_seed)

        abstracted_id = service.abstract_resource_id(sample_resource_ids["vm"])
        assert abstracted_id.startswith("vm-")
        # vm-{16-char-hash}
        parts = abstracted_id.split("-", 1)
        assert len(parts) == 2
        assert len(parts[1]) == 16

    def test_type_prefixed_format_storage(self, tenant_seed, sample_resource_ids):
        """Test storage account gets 'storage-' prefix."""
        service = IDAbstractionService(tenant_seed)

        abstracted_id = service.abstract_resource_id(sample_resource_ids["storage"])
        assert abstracted_id.startswith("storage-")

    def test_type_prefixed_format_vnet(self, tenant_seed, sample_resource_ids):
        """Test virtual network gets 'vnet-' prefix."""
        service = IDAbstractionService(tenant_seed)

        abstracted_id = service.abstract_resource_id(sample_resource_ids["vnet"])
        assert abstracted_id.startswith("vnet-")

    def test_type_prefixed_format_subnet(self, tenant_seed, sample_resource_ids):
        """Test subnet gets 'subnet-' prefix."""
        service = IDAbstractionService(tenant_seed)

        abstracted_id = service.abstract_resource_id(sample_resource_ids["subnet"])
        assert abstracted_id.startswith("subnet-")

    def test_full_resource_id_translation(self, tenant_seed, sample_resource_ids):
        """Test that full Azure resource ID is translated to abstracted format."""
        service = IDAbstractionService(tenant_seed)

        original_id = sample_resource_ids["vm"]
        abstracted_id = service.abstract_resource_id(original_id)

        # Should not contain any original identifiers
        assert "abc123" not in abstracted_id  # No subscription ID
        assert "test-rg" not in abstracted_id  # No resource group name
        assert "test-vm-001" not in abstracted_id  # No resource name

        # Should be in format: vm-{hash}
        assert abstracted_id.startswith("vm-")

    def test_subscription_id_abstraction(self, tenant_seed):
        """Test that subscription IDs are abstracted consistently."""
        service = IDAbstractionService(tenant_seed)

        subscription_id = "abc123-def456-ghi789"
        abstracted_sub = service.abstract_subscription_id(subscription_id)

        # Should be in format: sub-{hash}
        assert abstracted_sub.startswith("sub-")
        assert subscription_id not in abstracted_sub

    def test_resource_group_name_abstraction(self, tenant_seed):
        """Test that resource group names are abstracted consistently."""
        service = IDAbstractionService(tenant_seed)

        rg_name = "production-rg-eastus"
        abstracted_rg = service.abstract_resource_group_name(rg_name)

        # Should be in format: rg-{hash}
        assert abstracted_rg.startswith("rg-")
        assert "production" not in abstracted_rg

    def test_seed_based_reproducibility_same_seed(self, sample_resource_ids):
        """Test that same seed produces same abstractions."""
        seed = "shared-seed-123"
        service1 = IDAbstractionService(seed)
        service2 = IDAbstractionService(seed)

        resource_id = sample_resource_ids["vm"]
        abstracted1 = service1.abstract_resource_id(resource_id)
        abstracted2 = service2.abstract_resource_id(resource_id)

        assert abstracted1 == abstracted2

    def test_seed_based_reproducibility_different_seeds(self, sample_resource_ids):
        """Test that different seeds produce different abstractions."""
        service1 = IDAbstractionService("seed-alpha")
        service2 = IDAbstractionService("seed-beta")

        resource_id = sample_resource_ids["vm"]
        abstracted1 = service1.abstract_resource_id(resource_id)
        abstracted2 = service2.abstract_resource_id(resource_id)

        assert abstracted1 != abstracted2

    def test_handle_compute_resource_types(self, tenant_seed):
        """Test handling of various compute resource types."""
        service = IDAbstractionService(tenant_seed)

        compute_resources = {
            "Microsoft.Compute/virtualMachines": "vm-",
            "Microsoft.Compute/disks": "disk-",
            "Microsoft.Compute/availabilitySets": "avset-",
            "Microsoft.Compute/virtualMachineScaleSets": "vmss-",
        }

        for resource_type, expected_prefix in compute_resources.items():
            resource_id = f"/subscriptions/sub1/resourceGroups/rg1/providers/{resource_type}/resource1"
            abstracted = service.abstract_resource_id(resource_id)
            assert abstracted.startswith(expected_prefix), (
                f"Expected {expected_prefix} for {resource_type}, got {abstracted}"
            )

    def test_handle_network_resource_types(self, tenant_seed):
        """Test handling of various network resource types."""
        service = IDAbstractionService(tenant_seed)

        network_resources = {
            "Microsoft.Network/virtualNetworks": "vnet-",
            "Microsoft.Network/networkSecurityGroups": "nsg-",
            "Microsoft.Network/publicIPAddresses": "pip-",
            "Microsoft.Network/networkInterfaces": "nic-",
            "Microsoft.Network/loadBalancers": "lb-",
        }

        for resource_type, expected_prefix in network_resources.items():
            resource_id = f"/subscriptions/sub1/resourceGroups/rg1/providers/{resource_type}/resource1"
            abstracted = service.abstract_resource_id(resource_id)
            assert abstracted.startswith(expected_prefix), (
                f"Expected {expected_prefix} for {resource_type}, got {abstracted}"
            )

    def test_handle_storage_resource_types(self, tenant_seed):
        """Test handling of various storage resource types."""
        service = IDAbstractionService(tenant_seed)

        storage_resources = {
            "Microsoft.Storage/storageAccounts": "storage-",
        }

        for resource_type, expected_prefix in storage_resources.items():
            resource_id = f"/subscriptions/sub1/resourceGroups/rg1/providers/{resource_type}/resource1"
            abstracted = service.abstract_resource_id(resource_id)
            assert abstracted.startswith(expected_prefix), (
                f"Expected {expected_prefix} for {resource_type}, got {abstracted}"
            )

    def test_handle_identity_resource_types(self, tenant_seed):
        """Test handling of identity and security resource types."""
        service = IDAbstractionService(tenant_seed)

        identity_resources = {
            "Microsoft.KeyVault/vaults": "kv-",
            "Microsoft.ManagedIdentity/userAssignedIdentities": "identity-",
        }

        for resource_type, expected_prefix in identity_resources.items():
            resource_id = f"/subscriptions/sub1/resourceGroups/rg1/providers/{resource_type}/resource1"
            abstracted = service.abstract_resource_id(resource_id)
            assert abstracted.startswith(expected_prefix), (
                f"Expected {expected_prefix} for {resource_type}, got {abstracted}"
            )

    def test_handle_complex_resource_id_with_child_resources(self, tenant_seed):
        """Test handling of complex resource IDs with child resources (e.g., subnets)."""
        service = IDAbstractionService(tenant_seed)

        subnet_id = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1"
        abstracted = service.abstract_resource_id(subnet_id)

        assert abstracted.startswith("subnet-")
        assert "vnet1" not in abstracted
        assert "subnet1" not in abstracted

    def test_abstraction_preserves_resource_type_distinction(self, tenant_seed):
        """Test that different resource types get different prefixes even with same name."""
        service = IDAbstractionService(tenant_seed)

        # Two resources with same name but different types
        vm_id = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/resource1"
        storage_id = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/resource1"

        abstracted_vm = service.abstract_resource_id(vm_id)
        abstracted_storage = service.abstract_resource_id(storage_id)

        assert abstracted_vm.startswith("vm-")
        assert abstracted_storage.startswith("storage-")
        # Different prefixes, but same resource name should still produce same hash part
        # So they should differ in prefix but have same hash
        assert abstracted_vm != abstracted_storage

    def test_hash_collision_resistance(self, tenant_seed):
        """Test that similar resource IDs produce different hashes."""
        service = IDAbstractionService(tenant_seed)

        # Similar but different resource names
        id1 = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm-001"
        id2 = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm-002"

        abstracted1 = service.abstract_resource_id(id1)
        abstracted2 = service.abstract_resource_id(id2)

        assert abstracted1 != abstracted2

    def test_abstracted_id_format_validation(self, tenant_seed, sample_resource_ids):
        """Test that abstracted IDs follow the expected format pattern."""
        service = IDAbstractionService(tenant_seed)

        for resource_id in sample_resource_ids.values():
            abstracted = service.abstract_resource_id(resource_id)

            # Format should be: {type}-{16-char-hash} (with default hash_length=16)
            pattern = r"^[a-z0-9]+-[a-f0-9]{16}$"
            assert re.match(pattern, abstracted), f"Invalid format: {abstracted}"

    def test_abstracted_id_format_validation_custom_length(
        self, tenant_seed, sample_resource_ids
    ):
        """Test that abstracted IDs respect custom hash length."""
        service = IDAbstractionService(tenant_seed, hash_length=8)

        for resource_id in sample_resource_ids.values():
            abstracted = service.abstract_resource_id(resource_id)

            # Format should be: {type}-{8-char-hash}
            pattern = r"^[a-z0-9]+-[a-f0-9]{8}$"
            assert re.match(pattern, abstracted), f"Invalid format: {abstracted}"

    def test_reverse_lookup_not_possible(self, tenant_seed, sample_resource_ids):
        """Test that reverse lookup from abstracted ID to original ID is not easily possible.

        This is a security feature - abstracted IDs should not reveal original information.
        """
        service = IDAbstractionService(tenant_seed)

        original_id = sample_resource_ids["vm"]
        abstracted_id = service.abstract_resource_id(original_id)

        # Should not contain any substring of original ID (except common words like 'providers')
        original_parts = original_id.split("/")
        for part in original_parts:
            if part and part not in ["subscriptions", "resourceGroups", "providers"]:
                # Check that specific identifiers are not present
                assert part.lower() not in abstracted_id.lower(), (
                    f"Original part '{part}' found in abstracted ID '{abstracted_id}'"
                )

    def test_caching_through_determinism(self, tenant_seed, sample_resource_ids):
        """Test that repeated abstractions produce identical results (deterministic = cached behavior)."""
        service = IDAbstractionService(tenant_seed)
        resource_id = sample_resource_ids["vm"]

        # Multiple calls should produce same result
        result1 = service.abstract_resource_id(resource_id)
        result2 = service.abstract_resource_id(resource_id)
        result3 = service.abstract_resource_id(resource_id)

        assert result1 == result2 == result3

    def test_bulk_abstraction(self, tenant_seed, sample_resource_ids):
        """Test bulk abstraction of multiple resource IDs."""
        service = IDAbstractionService(tenant_seed)

        resource_ids = list(sample_resource_ids.values())
        abstracted_ids = service.abstract_resource_ids_bulk(resource_ids)

        assert len(abstracted_ids) == len(resource_ids)
        for abstracted in abstracted_ids:
            assert "-" in abstracted  # Should have type-hash format

        # Verify each matches individual abstraction
        for original, abstracted in zip(resource_ids, abstracted_ids):
            individual = service.abstract_resource_id(original)
            assert abstracted == individual

    def test_extract_type_prefix_known_types(self, tenant_seed):
        """Test type prefix extraction for known Azure resource types."""
        service = IDAbstractionService(tenant_seed)

        known_mappings = {
            "Microsoft.Compute/virtualMachines": "vm",
            "Microsoft.Storage/storageAccounts": "storage",
            "Microsoft.Network/virtualNetworks": "vnet",
            "Microsoft.KeyVault/vaults": "kv",
        }

        for resource_type, expected_prefix in known_mappings.items():
            actual_prefix = service._extract_type_prefix(resource_type)
            assert actual_prefix == expected_prefix

    def test_extract_type_prefix_unknown_types(self, tenant_seed):
        """Test type prefix extraction for unknown Azure resource types (fallback)."""
        service = IDAbstractionService(tenant_seed)

        # Unknown type should extract last segment
        unknown_type = "Microsoft.CustomProvider/customResources"
        prefix = service._extract_type_prefix(unknown_type)

        assert prefix == "customresources"  # Sanitized, lowercase, alphanumeric

    def test_parse_azure_resource_id_simple(self, tenant_seed):
        """Test parsing of simple Azure resource ID."""
        service = IDAbstractionService(tenant_seed)

        resource_id = "/subscriptions/abc123/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm"
        parsed = service._parse_azure_resource_id(resource_id)

        assert parsed["subscription_id"] == "abc123"
        assert parsed["resource_group"] == "test-rg"
        assert parsed["resource_type"] == "Microsoft.Compute/virtualMachines"
        assert parsed["resource_name"] == "test-vm"
        assert parsed["is_child_resource"] is False

    def test_parse_azure_resource_id_child_resource(self, tenant_seed):
        """Test parsing of child resource ID (e.g., subnet)."""
        service = IDAbstractionService(tenant_seed)

        subnet_id = "/subscriptions/abc123/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1"
        parsed = service._parse_azure_resource_id(subnet_id)

        assert parsed["subscription_id"] == "abc123"
        assert parsed["resource_group"] == "rg1"
        assert parsed["resource_type"] == "Microsoft.Network/virtualNetworks/subnets"
        assert parsed["resource_name"] == "subnet1"
        assert parsed["is_child_resource"] is True

    def test_abstract_resource_name_directly(self, tenant_seed):
        """Test direct resource name abstraction with type."""
        service = IDAbstractionService(tenant_seed)

        abstracted = service.abstract_resource_name(
            "my-vm", "Microsoft.Compute/virtualMachines"
        )

        assert abstracted.startswith("vm-")
        assert "my-vm" not in abstracted

        # Same name, different type should give different prefix
        abstracted2 = service.abstract_resource_name(
            "my-vm", "Microsoft.Storage/storageAccounts"
        )
        assert abstracted2.startswith("storage-")
        assert abstracted != abstracted2

    def test_empty_inputs_raise_errors(self, tenant_seed):
        """Test that empty inputs raise appropriate errors."""
        service = IDAbstractionService(tenant_seed)

        with pytest.raises(ValueError, match="cannot be empty"):
            service.abstract_resource_id("")

        with pytest.raises(ValueError, match="cannot be empty"):
            service.abstract_subscription_id("")

        with pytest.raises(ValueError, match="cannot be empty"):
            service.abstract_resource_group_name("")

        with pytest.raises(ValueError, match="cannot be empty"):
            service.abstract_resource_name("", "Microsoft.Compute/virtualMachines")

        with pytest.raises(ValueError, match="cannot be empty"):
            service.abstract_resource_name("name", "")

    def test_hash_length_respected(self, tenant_seed):
        """Test that hash length parameter is respected."""
        service8 = IDAbstractionService(tenant_seed, hash_length=8)
        service16 = IDAbstractionService(tenant_seed, hash_length=16)
        service32 = IDAbstractionService(tenant_seed, hash_length=32)

        resource_name = "test-resource"

        hash8 = service8._hash(resource_name)
        hash16 = service16._hash(resource_name)
        hash32 = service32._hash(resource_name)

        assert len(hash8) == 8
        assert len(hash16) == 16
        assert len(hash32) == 32

        # All should be prefixes of each other (same hash, different lengths)
        assert hash32.startswith(hash16)
        assert hash16.startswith(hash8)
