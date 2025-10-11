"""Tests for VNet address space validator (GAP-012).

This module tests the address space validation functionality that detects
overlapping VNet address spaces and optionally auto-renumbers conflicts.
"""


from src.validation.address_space_validator import (
    AddressSpaceConflict,
    AddressSpaceValidator,
    ValidationResult,
    validate_address_spaces,
)


class TestAddressSpaceValidator:
    """Test suite for AddressSpaceValidator."""

    def test_no_vnets_returns_valid(self):
        """Test that validation passes with no VNets."""
        validator = AddressSpaceValidator()
        resources = [
            {"type": "Microsoft.Storage/storageAccounts", "name": "storage1"},
        ]
        result = validator.validate_resources(resources)

        assert result.is_valid
        assert result.vnets_checked == 0
        assert len(result.conflicts) == 0
        assert len(result.warnings) == 1
        assert "No VNet resources found" in result.warnings[0]

    def test_single_vnet_returns_valid(self):
        """Test that validation passes with a single VNet."""
        validator = AddressSpaceValidator()
        resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet1",
                "address_space": ["10.0.0.0/16"],
            },
        ]
        result = validator.validate_resources(resources)

        assert result.is_valid
        assert result.vnets_checked == 1
        assert len(result.conflicts) == 0
        assert len(result.warnings) == 0

    def test_duplicate_address_spaces_detected(self):
        """Test that duplicate address spaces are detected."""
        validator = AddressSpaceValidator()
        resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet1",
                "address_space": ["10.0.0.0/16"],
            },
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet2",
                "address_space": ["10.0.0.0/16"],
            },
        ]
        result = validator.validate_resources(resources)

        assert not result.is_valid
        assert result.vnets_checked == 2
        assert len(result.conflicts) == 1
        assert "vnet1" in result.conflicts[0].vnet_names
        assert "vnet2" in result.conflicts[0].vnet_names
        assert "10.0.0.0/16" in result.conflicts[0].address_space

    def test_multiple_duplicate_address_spaces(self):
        """Test detection of multiple VNets with same address space."""
        validator = AddressSpaceValidator()
        resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet1",
                "address_space": ["10.0.0.0/16"],
            },
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet2",
                "address_space": ["10.0.0.0/16"],
            },
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet3",
                "address_space": ["10.0.0.0/16"],
            },
        ]
        result = validator.validate_resources(resources)

        assert not result.is_valid
        assert result.vnets_checked == 3
        assert len(result.conflicts) == 1
        assert len(result.conflicts[0].vnet_names) == 3

    def test_overlapping_but_different_ranges_detected(self):
        """Test that overlapping (but not identical) address spaces are detected."""
        validator = AddressSpaceValidator()
        resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet1",
                "address_space": ["10.0.0.0/16"],
            },
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet2",
                "address_space": ["10.0.1.0/24"],  # Overlaps with vnet1
            },
        ]
        result = validator.validate_resources(resources)

        assert not result.is_valid
        assert len(result.conflicts) == 1
        assert "overlap" in result.conflicts[0].message.lower()

    def test_non_overlapping_ranges_valid(self):
        """Test that non-overlapping address spaces pass validation."""
        validator = AddressSpaceValidator()
        resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet1",
                "address_space": ["10.0.0.0/16"],
            },
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet2",
                "address_space": ["10.1.0.0/16"],
            },
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet3",
                "address_space": ["172.16.0.0/16"],
            },
        ]
        result = validator.validate_resources(resources)

        assert result.is_valid
        assert result.vnets_checked == 3
        assert len(result.conflicts) == 0

    def test_reserved_range_warning(self):
        """Test that reserved address ranges generate warnings."""
        validator = AddressSpaceValidator()
        resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet1",
                "address_space": ["169.254.0.0/16"],  # Azure link-local
            },
        ]
        result = validator.validate_resources(resources)

        assert result.is_valid  # No conflicts, but warnings
        assert len(result.warnings) == 1
        assert "reserved" in result.warnings[0].lower()

    def test_auto_renumber_disabled_by_default(self):
        """Test that auto-renumbering is disabled by default."""
        validator = AddressSpaceValidator(auto_renumber=False)
        resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet1",
                "address_space": ["10.0.0.0/16"],
            },
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet2",
                "address_space": ["10.0.0.0/16"],
            },
        ]
        result = validator.validate_resources(resources, modify_in_place=False)

        assert not result.is_valid
        assert len(result.auto_renumbered) == 0
        # Original address spaces unchanged
        assert resources[0]["address_space"] == ["10.0.0.0/16"]
        assert resources[1]["address_space"] == ["10.0.0.0/16"]

    def test_auto_renumber_conflicts(self):
        """Test that auto-renumbering resolves conflicts."""
        validator = AddressSpaceValidator(auto_renumber=True)
        resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet1",
                "address_space": ["10.0.0.0/16"],
            },
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet2",
                "address_space": ["10.0.0.0/16"],
            },
        ]
        result = validator.validate_resources(resources, modify_in_place=True)

        # Conflicts should be detected initially
        assert not result.is_valid
        assert len(result.conflicts) > 0

        # But vnet2 should be renumbered
        assert len(result.auto_renumbered) == 1
        assert "vnet2" in result.auto_renumbered

        # vnet1 should keep original address space
        assert resources[0]["address_space"] == ["10.0.0.0/16"]

        # vnet2 should have new address space
        assert resources[1]["address_space"] != ["10.0.0.0/16"]
        assert resources[1]["address_space"][0].startswith("10.")

    def test_auto_renumber_multiple_conflicts(self):
        """Test auto-renumbering with multiple conflicting VNets."""
        validator = AddressSpaceValidator(auto_renumber=True)
        resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet1",
                "address_space": ["10.0.0.0/16"],
            },
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet2",
                "address_space": ["10.0.0.0/16"],
            },
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet3",
                "address_space": ["10.0.0.0/16"],
            },
        ]
        result = validator.validate_resources(resources, modify_in_place=True)

        assert len(result.auto_renumbered) == 2
        assert "vnet2" in result.auto_renumbered
        assert "vnet3" in result.auto_renumbered

        # All VNets should have different address spaces
        assert resources[0]["address_space"][0] != resources[1]["address_space"][0]
        assert resources[0]["address_space"][0] != resources[2]["address_space"][0]
        assert resources[1]["address_space"][0] != resources[2]["address_space"][0]

    def test_auto_renumber_finds_available_ranges(self):
        """Test that auto-renumbering finds available private ranges."""
        validator = AddressSpaceValidator(auto_renumber=True)
        resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet1",
                "address_space": ["10.0.0.0/16"],
            },
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet2",
                "address_space": ["10.0.0.0/16"],
            },
        ]
        _ = validator.validate_resources(resources, modify_in_place=True)

        # Should find 10.1.0.0/16 as next available
        assert resources[1]["address_space"] == ["10.1.0.0/16"]

    def test_missing_address_space_uses_default(self):
        """Test that VNets without address_space get default."""
        validator = AddressSpaceValidator()
        resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet1",
                # No address_space field
            },
        ]
        result = validator.validate_resources(resources)

        assert result.is_valid
        assert result.vnets_checked == 1

    def test_invalid_address_space_handled(self):
        """Test that invalid CIDR notation is handled gracefully."""
        validator = AddressSpaceValidator()
        resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet1",
                "address_space": ["invalid-cidr"],
            },
        ]
        # Should not crash
        result = validator.validate_resources(resources)
        assert result.is_valid  # Invalid ranges ignored

    def test_convenience_function(self):
        """Test the convenience function validate_address_spaces."""
        resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet1",
                "address_space": ["10.0.0.0/16"],
            },
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet2",
                "address_space": ["10.0.0.0/16"],
            },
        ]
        result = validate_address_spaces(resources, auto_renumber=False)

        assert isinstance(result, ValidationResult)
        assert not result.is_valid
        assert len(result.conflicts) > 0

    def test_mixed_resource_types(self):
        """Test validation with mixed resource types."""
        validator = AddressSpaceValidator()
        resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet1",
                "address_space": ["10.0.0.0/16"],
            },
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "storage1",
            },
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet2",
                "address_space": ["10.1.0.0/16"],
            },
            {
                "type": "Microsoft.Compute/virtualMachines",
                "name": "vm1",
            },
        ]
        result = validator.validate_resources(resources)

        assert result.is_valid
        assert result.vnets_checked == 2

    def test_address_space_conflict_dataclass(self):
        """Test AddressSpaceConflict dataclass."""
        conflict = AddressSpaceConflict(
            vnet_names=["vnet1", "vnet2"],
            address_space="10.0.0.0/16",
            severity="warning",
        )

        assert conflict.vnet_names == ["vnet1", "vnet2"]
        assert conflict.address_space == "10.0.0.0/16"
        assert conflict.severity == "warning"
        assert "vnet1" in conflict.message
        assert "vnet2" in conflict.message
        assert "10.0.0.0/16" in conflict.message

    def test_validation_result_dataclass(self):
        """Test ValidationResult dataclass."""
        result = ValidationResult(
            is_valid=False,
            conflicts=[
                AddressSpaceConflict(
                    vnet_names=["vnet1", "vnet2"], address_space="10.0.0.0/16"
                )
            ],
            warnings=["Warning 1"],
            vnets_checked=2,
            auto_renumbered=["vnet2"],
        )

        assert not result.is_valid
        assert len(result.conflicts) == 1
        assert len(result.warnings) == 1
        assert result.vnets_checked == 2
        assert len(result.auto_renumbered) == 1

    def test_string_address_space_converted_to_list(self):
        """Test that string address_space is converted to list."""
        validator = AddressSpaceValidator()
        resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet1",
                "address_space": "10.0.0.0/16",  # String instead of list
            },
        ]
        result = validator.validate_resources(resources)

        assert result.is_valid
        assert result.vnets_checked == 1

    def test_multiple_address_spaces_per_vnet(self):
        """Test VNets with multiple address spaces."""
        validator = AddressSpaceValidator()
        resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet1",
                "address_space": ["10.0.0.0/16", "10.1.0.0/16"],
            },
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet2",
                "address_space": ["10.2.0.0/16"],
            },
        ]
        result = validator.validate_resources(resources)

        assert result.is_valid
        assert result.vnets_checked == 2

    def test_conflict_between_multiple_address_spaces(self):
        """Test conflict detection with multiple address spaces per VNet."""
        validator = AddressSpaceValidator()
        resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet1",
                "address_space": ["10.0.0.0/16", "10.1.0.0/16"],
            },
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet2",
                "address_space": ["10.1.0.0/16", "10.2.0.0/16"],  # Overlaps on 10.1.0.0/16
            },
        ]
        result = validator.validate_resources(resources)

        assert not result.is_valid
        assert len(result.conflicts) > 0


class TestIntegrationScenarios:
    """Integration tests for real-world scenarios."""

    def test_demo_scenario_duplicate_10_0_0_0(self):
        """Test the actual demo scenario from GAP-012."""
        validator = AddressSpaceValidator()
        resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "dtlatevet12-infra-vnet",
                "address_space": ["10.0.0.0/16"],
                "resourceGroup": "atevet12-Working",
            },
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "dtlatevet12-attack-vnet",
                "address_space": ["10.0.0.0/16"],  # Same as infra-vnet
                "resourceGroup": "atevet12-Working",
            },
        ]
        result = validator.validate_resources(resources)

        assert not result.is_valid
        assert len(result.conflicts) == 1
        assert "dtlatevet12-infra-vnet" in result.conflicts[0].vnet_names
        assert "dtlatevet12-attack-vnet" in result.conflicts[0].vnet_names

    def test_demo_scenario_with_auto_renumber(self):
        """Test demo scenario with auto-renumbering enabled."""
        validator = AddressSpaceValidator(auto_renumber=True)
        resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "dtlatevet12-infra-vnet",
                "address_space": ["10.0.0.0/16"],
                "resourceGroup": "atevet12-Working",
            },
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "dtlatevet12-attack-vnet",
                "address_space": ["10.0.0.0/16"],
                "resourceGroup": "atevet12-Working",
            },
        ]
        result = validator.validate_resources(resources, modify_in_place=True)

        # Conflicts detected but fixed
        assert len(result.auto_renumbered) == 1
        assert "dtlatevet12-attack-vnet" in result.auto_renumbered

        # First VNet keeps original
        assert resources[0]["address_space"] == ["10.0.0.0/16"]

        # Second VNet gets renumbered
        assert resources[1]["address_space"] == ["10.1.0.0/16"]

    def test_large_deployment_with_many_vnets(self):
        """Test validation with many VNets."""
        validator = AddressSpaceValidator()
        resources = []
        for i in range(10):
            resources.append(
                {
                    "type": "Microsoft.Network/virtualNetworks",
                    "name": f"vnet{i}",
                    "address_space": [f"10.{i}.0.0/16"],
                }
            )
        result = validator.validate_resources(resources)

        assert result.is_valid
        assert result.vnets_checked == 10
        assert len(result.conflicts) == 0
