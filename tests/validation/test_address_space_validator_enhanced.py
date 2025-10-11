"""Enhanced tests for address space validator (Issue #334).

This module tests the enhanced warning messages and conflict report
generation features added for VNet overlap detection.
"""

import logging

from src.validation.address_space_validator import (
    AddressSpaceConflict,
    AddressSpaceValidator,
    ValidationResult,
)


# Test data helpers
def create_vnet_resource(
    name: str, address_space: str, rg: str = "test-rg"
) -> dict[str, any]:
    """Helper to create VNet resource for testing."""
    return {
        "id": f"/subscriptions/test-sub/resourceGroups/{rg}/providers/Microsoft.Network/virtualNetworks/{name}",
        "type": "Microsoft.Network/virtualNetworks",
        "name": name,
        "address_space": [address_space],
        "resourceGroup": rg,
        "location": "eastus",
        "tags": {},
    }


# Unit Tests: Message Formatting (UF-01 to UF-05)
class TestEnhancedWarningMessages:
    """Test rich warning message formatting."""

    def test_format_conflict_warning_exact_duplicate(self):
        """UF-01: Format warning for exact duplicate address spaces."""
        validator = AddressSpaceValidator()
        conflict = AddressSpaceConflict(
            vnet_names=["vnet1", "vnet2"], address_space="10.0.0.0/16"
        )
        warning = validator.format_conflict_warning(conflict)

        assert "VNet Address Space Conflict Detected" in warning
        assert "vnet1" in warning and "vnet2" in warning
        assert "10.0.0.0/16" in warning
        assert "peering will FAIL" in warning
        assert "Remediation" in warning

    def test_format_conflict_warning_partial_overlap(self):
        """UF-02: Format warning for partial overlap."""
        validator = AddressSpaceValidator()
        conflict = AddressSpaceConflict(
            vnet_names=["large_hub", "small_spoke"],
            address_space="10.0.0.0/16 overlaps 10.0.128.0/17",
        )
        warning = validator.format_conflict_warning(conflict)

        assert "large_hub" in warning
        assert "small_spoke" in warning
        assert "overlaps" in warning
        assert "10.0.0.0/16" in warning
        assert "10.0.128.0/17" in warning

    def test_suggest_alternative_range_finds_available(self):
        """UF-03: Suggest alternative address range."""
        validator = AddressSpaceValidator()
        # Simulate used ranges
        validator._used_ranges = {"10.0.0.0/16", "10.1.0.0/16"}

        conflict = AddressSpaceConflict(
            vnet_names=["vnet1", "vnet2"], address_space="10.0.0.0/16"
        )
        suggestion = validator._suggest_alternative_range(conflict)

        assert suggestion is not None
        assert suggestion == "10.2.0.0/16"

    def test_format_includes_azure_docs_link(self):
        """UF-04: Warning includes Azure documentation link."""
        validator = AddressSpaceValidator()
        conflict = AddressSpaceConflict(
            vnet_names=["vnet1", "vnet2"], address_space="10.0.0.0/16"
        )
        warning = validator.format_conflict_warning(conflict)

        assert "learn.microsoft.com" in warning
        assert "virtual-network" in warning

    def test_format_includes_auto_renumber_hint(self):
        """UF-05: Warning mentions auto-renumber flag."""
        validator = AddressSpaceValidator()
        conflict = AddressSpaceConflict(
            vnet_names=["vnet1", "vnet2"], address_space="10.0.0.0/16"
        )
        warning = validator.format_conflict_warning(conflict)

        assert "--auto-renumber-conflicts" in warning


# Unit Tests: Report Generation (RG-01 to RG-04)
class TestConflictReportGeneration:
    """Test markdown conflict report generation."""

    def test_generate_report_no_conflicts(self, tmp_path):
        """RG-01: Generate report when no conflicts detected."""
        validator = AddressSpaceValidator()
        result = ValidationResult(is_valid=True, vnets_checked=5, conflicts=[])

        report = validator.generate_conflict_report(result)

        assert "No Conflicts Detected" in report
        assert "Total VNets" in report
        assert "5" in report

    def test_generate_report_with_conflicts(self, tmp_path):
        """RG-02: Generate report with multiple conflicts."""
        validator = AddressSpaceValidator()
        conflicts = [
            AddressSpaceConflict(["vnet1", "vnet2"], "10.0.0.0/16"),
            AddressSpaceConflict(["vnet3", "vnet4"], "10.1.0.0/16"),
        ]
        result = ValidationResult(is_valid=False, conflicts=conflicts, vnets_checked=4)

        report = validator.generate_conflict_report(result)

        assert "Conflict 1:" in report
        assert "Conflict 2:" in report
        assert "vnet1" in report
        assert "vnet3" in report

    def test_report_markdown_format(self):
        """RG-03: Report is valid markdown."""
        validator = AddressSpaceValidator()
        conflict = AddressSpaceConflict(["vnet1", "vnet2"], "10.0.0.0/16")
        result = ValidationResult(is_valid=False, conflicts=[conflict], vnets_checked=2)

        report = validator.generate_conflict_report(result)

        # Check markdown structure
        assert "# VNet Address Space Conflict Report" in report
        assert "## Summary" in report
        assert "## Conflicts" in report
        assert "###" in report  # Conflict subsection
        assert "**" in report  # Bold text
        assert "- " in report  # List items
        assert "`" in report  # Code formatting

    def test_report_written_to_file(self, tmp_path):
        """RG-04: Report is written to specified file."""
        validator = AddressSpaceValidator()
        conflict = AddressSpaceConflict(["vnet1", "vnet2"], "10.0.0.0/16")
        result = ValidationResult(is_valid=False, conflicts=[conflict], vnets_checked=2)

        report_path = tmp_path / "report.md"
        report = validator.generate_conflict_report(result, report_path)

        assert report_path.exists()
        content = report_path.read_text()
        assert content == report
        assert "Conflict 1:" in content


# Unit Tests: Edge Cases (EC-01 to EC-10)
class TestEdgeCases:
    """Test edge cases in validation."""

    def test_single_vnet_no_warnings(self):
        """EC-01: Single VNet produces no warnings."""
        validator = AddressSpaceValidator()
        resources = [create_vnet_resource("solo", "10.0.0.0/16")]
        result = validator.validate_resources(resources)

        assert result.is_valid
        assert len(result.conflicts) == 0

    def test_no_vnets_no_warnings(self):
        """EC-02: No VNets produces no warnings."""
        validator = AddressSpaceValidator()
        resources = []
        result = validator.validate_resources(resources)

        assert result.is_valid
        assert "No VNet resources found" in result.warnings

    def test_three_vnets_all_overlapping(self):
        """EC-03: Three VNets all using same address space."""
        validator = AddressSpaceValidator()
        resources = [
            create_vnet_resource("vnet1", "10.0.0.0/16"),
            create_vnet_resource("vnet2", "10.0.0.0/16"),
            create_vnet_resource("vnet3", "10.0.0.0/16"),
        ]
        result = validator.validate_resources(resources)

        assert not result.is_valid
        # Collect all VNet names mentioned in conflicts
        all_names = set()
        for conflict in result.conflicts:
            all_names.update(conflict.vnet_names)
        assert "vnet1" in all_names
        assert "vnet2" in all_names
        assert "vnet3" in all_names

    def test_complex_partial_overlaps(self):
        """EC-04: Complex nested overlaps (10.0.0.0/8 contains 10.1.0.0/16)."""
        validator = AddressSpaceValidator()
        resources = [
            create_vnet_resource("super_vnet", "10.0.0.0/8"),
            create_vnet_resource("large_vnet", "10.1.0.0/16"),
            create_vnet_resource("medium_vnet", "10.1.1.0/24"),
        ]
        result = validator.validate_resources(resources)

        assert not result.is_valid
        assert len(result.conflicts) > 0

    def test_non_overlapping_in_different_ranges(self):
        """EC-05: Non-overlapping VNets in different private ranges."""
        validator = AddressSpaceValidator()
        resources = [
            create_vnet_resource("vnet_10", "10.0.0.0/16"),
            create_vnet_resource("vnet_172", "172.16.0.0/16"),
            create_vnet_resource("vnet_192", "192.168.0.0/16"),
        ]
        result = validator.validate_resources(resources)

        assert result.is_valid
        assert len(result.conflicts) == 0

    def test_multiple_address_spaces_per_vnet(self):
        """EC-06: VNet with multiple address spaces, one overlaps."""
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
                "address_space": ["10.1.0.0/16"],
            },
        ]
        result = validator.validate_resources(resources)

        assert not result.is_valid
        # Check that 10.1.0.0/16 conflict is detected
        conflict_found = any("10.1.0.0/16" in c.address_space for c in result.conflicts)
        assert conflict_found

    def test_invalid_cidr_notation_handled(self, caplog):
        """EC-07: Invalid CIDR notation handled gracefully."""
        validator = AddressSpaceValidator()
        resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "bad_vnet",
                "address_space": ["not-a-valid-cidr"],
            }
        ]

        with caplog.at_level(logging.WARNING):
            validator.validate_resources(resources)

        # Should not crash, should log warning
        warning_messages = [r.message for r in caplog.records]
        assert any("Invalid address space" in msg for msg in warning_messages)

    def test_empty_address_space_uses_default(self, caplog):
        """EC-08: Empty address_space uses default 10.0.0.0/16."""
        validator = AddressSpaceValidator()
        resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "empty_vnet",
                "address_space": [],
            }
        ]

        with caplog.at_level(logging.WARNING):
            validator.validate_resources(resources)

        # Should use default
        warning_messages = [r.message for r in caplog.records]
        assert any("defaulting to" in msg for msg in warning_messages)

    def test_ipv6_addresses_supported(self):
        """EC-09: IPv6 addresses are supported."""
        validator = AddressSpaceValidator()
        resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "ipv6_vnet",
                "address_space": ["fd00:db8::/64"],
            }
        ]

        # Should not crash
        result = validator.validate_resources(resources)
        assert result.is_valid

    def test_adjacent_non_overlapping_ranges(self):
        """EC-10: Adjacent but non-overlapping ranges are valid."""
        validator = AddressSpaceValidator()
        resources = [
            create_vnet_resource("vnet1", "10.0.0.0/16"),
            create_vnet_resource("vnet2", "10.1.0.0/16"),
        ]
        result = validator.validate_resources(resources)

        assert result.is_valid
        assert len(result.conflicts) == 0


# Test data scenarios from TEST_SPECIFICATION_TABLE.md
DEMO_OVERLAP_SCENARIO = [
    {
        "type": "Microsoft.Network/virtualNetworks",
        "name": "dtlatevet12_attack_vnet",
        "address_space": ["10.0.0.0/16"],
        "resourceGroup": "atevet12-Working",
        "location": "eastus",
    },
    {
        "type": "Microsoft.Network/virtualNetworks",
        "name": "dtlatevet12_infra_vnet",
        "address_space": ["10.0.0.0/16"],
        "resourceGroup": "atevet12-Working",
        "location": "eastus",
    },
]


class TestRealWorldScenarios:
    """Test with realistic scenarios from demo data."""

    def test_demo_overlap_scenario(self):
        """Test the demo scenario from issue #334."""
        validator = AddressSpaceValidator()
        result = validator.validate_resources(DEMO_OVERLAP_SCENARIO)

        assert not result.is_valid
        assert len(result.conflicts) == 1
        conflict = result.conflicts[0]
        assert "dtlatevet12_attack_vnet" in conflict.vnet_names
        assert "dtlatevet12_infra_vnet" in conflict.vnet_names
        assert "10.0.0.0/16" in conflict.address_space

    def test_demo_scenario_with_rich_warning(self):
        """Test rich warning generation for demo scenario."""
        validator = AddressSpaceValidator()
        result = validator.validate_resources(DEMO_OVERLAP_SCENARIO)

        conflict = result.conflicts[0]
        warning = validator.format_conflict_warning(conflict)

        # Should contain both VNet names
        assert "dtlatevet12_attack_vnet" in warning
        assert "dtlatevet12_infra_vnet" in warning
        # Should have remediation guidance
        assert "Remediation" in warning
        assert "--auto-renumber-conflicts" in warning
        # Should suggest alternative
        assert "10." in warning  # Should suggest some 10.x range

    def test_demo_scenario_conflict_report(self, tmp_path):
        """Test conflict report for demo scenario."""
        validator = AddressSpaceValidator()
        result = validator.validate_resources(DEMO_OVERLAP_SCENARIO)

        report_path = tmp_path / "demo_conflict_report.md"
        report = validator.generate_conflict_report(result, report_path)

        assert report_path.exists()
        assert "dtlatevet12_attack_vnet" in report
        assert "dtlatevet12_infra_vnet" in report
        assert "Conflicts Detected**: 1" in report


class TestAutoRenumbering:
    """Test auto-renumbering with enhanced messages."""

    def test_auto_renumber_updates_resources(self):
        """Test auto-renumber modifies resources in place."""
        validator = AddressSpaceValidator(auto_renumber=True)
        resources = [
            create_vnet_resource("vnet1", "10.0.0.0/16"),
            create_vnet_resource("vnet2", "10.0.0.0/16"),
        ]

        result = validator.validate_resources(resources, modify_in_place=True)

        # Should have renumbered vnet2
        assert len(result.auto_renumbered) == 1
        assert "vnet2" in result.auto_renumbered

        # Check that vnet2 was actually changed
        vnet2 = next(r for r in resources if r["name"] == "vnet2")
        assert vnet2["address_space"] != ["10.0.0.0/16"]

    def test_report_includes_auto_renumbered_section(self, tmp_path):
        """Test report includes auto-renumbered VNets section."""
        validator = AddressSpaceValidator(auto_renumber=True)
        resources = [
            create_vnet_resource("vnet1", "10.0.0.0/16"),
            create_vnet_resource("vnet2", "10.0.0.0/16"),
        ]

        result = validator.validate_resources(resources, modify_in_place=True)
        report = validator.generate_conflict_report(result)

        assert "Auto-Renumbered VNets" in report
        assert "`vnet2`" in report
