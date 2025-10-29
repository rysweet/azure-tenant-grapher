"""
Unit tests for SubnetValidator

Tests validate subnet address range validation, overlap detection,
and auto-fix functionality.
"""

from src.iac.validators.subnet_validator import (
    SubnetValidator,
)


class TestSubnetValidator:
    """Test cases for SubnetValidator."""

    def test_valid_subnet_within_vnet_range(self):
        """Test that valid subnets pass validation."""
        validator = SubnetValidator(auto_fix=False)

        subnets = [
            {"name": "subnet1", "address_prefixes": ["10.0.1.0/24"]},
            {"name": "subnet2", "address_prefixes": ["10.0.2.0/24"]},
        ]

        result = validator.validate_vnet_subnets(
            vnet_name="test-vnet",
            vnet_address_space=["10.0.0.0/16"],
            subnets=subnets,
        )

        assert result.valid is True
        assert len(result.issues) == 0
        assert result.auto_fixed is False

    def test_subnet_outside_vnet_range_no_autofix(self):
        """Test detection of subnet outside VNet range without auto-fix."""
        validator = SubnetValidator(auto_fix=False)

        subnets = [
            {"name": "invalid-subnet", "address_prefixes": ["10.10.1.0/24"]},
        ]

        result = validator.validate_vnet_subnets(
            vnet_name="test-vnet",
            vnet_address_space=["10.0.0.0/16"],
            subnets=subnets,
        )

        assert result.valid is False
        assert len(result.issues) == 1
        assert result.issues[0].issue_type == "out_of_range"
        assert result.issues[0].subnet_name == "invalid-subnet"
        assert "outside VNet address space" in result.issues[0].message

    def test_subnet_outside_vnet_range_with_autofix(self):
        """Test auto-fix of subnet outside VNet range."""
        validator = SubnetValidator(auto_fix=True)

        subnets = [
            {"name": "invalid-subnet", "address_prefixes": ["10.10.1.0/24"]},
        ]

        result = validator.validate_vnet_subnets(
            vnet_name="test-vnet",
            vnet_address_space=["10.0.0.0/16"],
            subnets=subnets,
        )

        # Should auto-fix the issue
        assert result.auto_fixed is True
        assert len(result.issues) == 1
        assert result.issues[0].issue_type == "out_of_range"
        assert result.issues[0].auto_fixable is True
        assert result.issues[0].suggested_prefix is not None
        assert result.issues[0].suggested_prefix.startswith("10.0.")

        # Subnet should be updated in-place
        assert subnets[0]["address_prefixes"][0].startswith("10.0.")

    def test_overlapping_subnets(self):
        """Test detection of overlapping subnets."""
        validator = SubnetValidator(auto_fix=False)

        subnets = [
            {"name": "subnet1", "address_prefixes": ["10.0.1.0/24"]},
            {"name": "subnet2", "address_prefixes": ["10.0.1.0/24"]},  # Same range
        ]

        result = validator.validate_vnet_subnets(
            vnet_name="test-vnet",
            vnet_address_space=["10.0.0.0/16"],
            subnets=subnets,
        )

        assert result.valid is False
        overlap_issues = [i for i in result.issues if i.issue_type == "overlap"]
        assert len(overlap_issues) == 1
        assert "overlaps" in overlap_issues[0].message.lower()

    def test_partially_overlapping_subnets(self):
        """Test detection of partially overlapping subnets."""
        validator = SubnetValidator(auto_fix=False)

        subnets = [
            {
                "name": "subnet1",
                "address_prefixes": ["10.0.0.0/23"],
            },  # 10.0.0.0 - 10.0.1.255
            {
                "name": "subnet2",
                "address_prefixes": ["10.0.1.0/24"],
            },  # 10.0.1.0 - 10.0.1.255 (overlaps)
        ]

        result = validator.validate_vnet_subnets(
            vnet_name="test-vnet",
            vnet_address_space=["10.0.0.0/16"],
            subnets=subnets,
        )

        assert result.valid is False
        overlap_issues = [i for i in result.issues if i.issue_type == "overlap"]
        assert len(overlap_issues) == 1

    def test_insufficient_address_space_warning(self):
        """Test warning for insufficient address space."""
        validator = SubnetValidator(auto_fix=False)

        subnets = [
            {
                "name": "tiny-subnet",
                "address_prefixes": ["10.0.1.0/29"],
            },  # Only 8 addresses
        ]

        result = validator.validate_vnet_subnets(
            vnet_name="test-vnet",
            vnet_address_space=["10.0.0.0/16"],
            subnets=subnets,
        )

        # Should pass validation but have a warning
        assert result.valid is True
        insufficient_issues = [
            i for i in result.issues if i.issue_type == "insufficient_space"
        ]
        assert len(insufficient_issues) == 1
        assert "16 addresses" in insufficient_issues[0].message

    def test_missing_address_prefix(self):
        """Test detection of subnet without address prefix."""
        validator = SubnetValidator(auto_fix=False)

        subnets = [
            {"name": "no-prefix-subnet"},  # No address prefix
        ]

        result = validator.validate_vnet_subnets(
            vnet_name="test-vnet",
            vnet_address_space=["10.0.0.0/16"],
            subnets=subnets,
        )

        assert result.valid is False
        missing_issues = [i for i in result.issues if i.issue_type == "missing_prefix"]
        assert len(missing_issues) == 1

    def test_invalid_subnet_prefix(self):
        """Test detection of invalid CIDR prefix."""
        validator = SubnetValidator(auto_fix=False)

        subnets = [
            {"name": "bad-prefix", "address_prefixes": ["not-a-cidr"]},
        ]

        result = validator.validate_vnet_subnets(
            vnet_name="test-vnet",
            vnet_address_space=["10.0.0.0/16"],
            subnets=subnets,
        )

        assert result.valid is False
        invalid_issues = [i for i in result.issues if i.issue_type == "invalid_prefix"]
        assert len(invalid_issues) == 1

    def test_multiple_address_prefixes(self):
        """Test subnet with multiple address prefixes."""
        validator = SubnetValidator(auto_fix=False)

        subnets = [
            {
                "name": "multi-prefix",
                "address_prefixes": ["10.0.1.0/24", "10.0.2.0/24"],
            },
        ]

        result = validator.validate_vnet_subnets(
            vnet_name="test-vnet",
            vnet_address_space=["10.0.0.0/16"],
            subnets=subnets,
        )

        assert result.valid is True
        assert len(result.issues) == 0

    def test_address_prefix_single_format(self):
        """Test subnet with single address_prefix (not array)."""
        validator = SubnetValidator(auto_fix=False)

        subnets = [
            {"name": "single-prefix", "address_prefix": "10.0.1.0/24"},  # Singular form
        ]

        result = validator.validate_vnet_subnets(
            vnet_name="test-vnet",
            vnet_address_space=["10.0.0.0/16"],
            subnets=subnets,
        )

        assert result.valid is True
        assert len(result.issues) == 0

    def test_properties_json_string_format(self):
        """Test subnet with properties as JSON string."""
        validator = SubnetValidator(auto_fix=False)

        import json

        subnets = [
            {
                "name": "json-props",
                "properties": json.dumps({"addressPrefix": "10.0.1.0/24"}),
            },
        ]

        result = validator.validate_vnet_subnets(
            vnet_name="test-vnet",
            vnet_address_space=["10.0.0.0/16"],
            subnets=subnets,
        )

        assert result.valid is True
        assert len(result.issues) == 0

    def test_multiple_vnets(self):
        """Test validation of multiple VNets with different address spaces."""
        validator = SubnetValidator(auto_fix=False)

        result1 = validator.validate_vnet_subnets(
            vnet_name="vnet1",
            vnet_address_space=["10.0.0.0/16"],
            subnets=[{"name": "subnet1", "address_prefixes": ["10.0.1.0/24"]}],
        )

        result2 = validator.validate_vnet_subnets(
            vnet_name="vnet2",
            vnet_address_space=["192.168.0.0/16"],
            subnets=[{"name": "subnet1", "address_prefixes": ["192.168.1.0/24"]}],
        )

        assert result1.valid is True
        assert result2.valid is True

    def test_terraform_resources_validation(self):
        """Test validation of Terraform resource structure."""
        validator = SubnetValidator(auto_fix=False)

        terraform_resources = {
            "azurerm_virtual_network": {
                "test_vnet": {
                    "name": "test-vnet",
                    "address_space": ["10.0.0.0/16"],
                }
            },
            "azurerm_subnet": {
                "subnet1": {
                    "name": "subnet1",
                    "virtual_network_name": "${azurerm_virtual_network.test_vnet.name}",
                    "address_prefixes": ["10.0.1.0/24"],
                },
                "subnet2": {
                    "name": "subnet2",
                    "virtual_network_name": "${azurerm_virtual_network.test_vnet.name}",
                    "address_prefixes": ["10.0.2.0/24"],
                },
            },
        }

        results = validator.validate_terraform_resources(terraform_resources)

        assert len(results) == 1
        assert results[0].vnet_name == "test_vnet"
        assert results[0].valid is True

    def test_terraform_resources_with_invalid_subnets(self):
        """Test Terraform validation with invalid subnets."""
        validator = SubnetValidator(auto_fix=False)

        terraform_resources = {
            "azurerm_virtual_network": {
                "test_vnet": {
                    "name": "test-vnet",
                    "address_space": ["10.0.0.0/16"],
                }
            },
            "azurerm_subnet": {
                "bad_subnet": {
                    "name": "bad-subnet",
                    "virtual_network_name": "test_vnet",
                    "address_prefixes": ["192.168.1.0/24"],  # Wrong range
                },
            },
        }

        results = validator.validate_terraform_resources(terraform_resources)

        assert len(results) == 1
        assert results[0].valid is False
        assert any(i.issue_type == "out_of_range" for i in results[0].issues)

    def test_validation_report_formatting(self):
        """Test validation report formatting."""
        validator = SubnetValidator(auto_fix=False)

        subnets = [
            {"name": "invalid-subnet", "address_prefixes": ["10.10.1.0/24"]},
        ]

        result = validator.validate_vnet_subnets(
            vnet_name="test-vnet",
            vnet_address_space=["10.0.0.0/16"],
            subnets=subnets,
        )

        report = validator.format_validation_report([result])

        assert "Subnet Validation Report" in report
        assert "test-vnet" in report
        assert "invalid-subnet" in report
        assert "Total VNets: 1" in report

    def test_autofix_preserves_prefix_length(self):
        """Test that auto-fix preserves the original prefix length."""
        validator = SubnetValidator(auto_fix=True)

        subnets = [
            {"name": "subnet1", "address_prefixes": ["10.10.1.0/24"]},
        ]

        result = validator.validate_vnet_subnets(
            vnet_name="test-vnet",
            vnet_address_space=["10.0.0.0/16"],
            subnets=subnets,
        )

        assert result.auto_fixed is True
        # Should suggest a /24 prefix within 10.0.0.0/16
        suggested = result.issues[0].suggested_prefix
        assert suggested is not None
        assert suggested.endswith("/24")
        assert suggested.startswith("10.0.")

    def test_complex_scenario_demo_fix(self):
        """Test the exact scenario from the demo (10.10.x.x -> 10.0.x.x)."""
        validator = SubnetValidator(auto_fix=True)

        # Simulate the demo scenario: VNet 10.0.0.0/16 with subnets using 10.10.x.x
        subnets = [
            {"name": "default", "address_prefixes": ["10.10.0.0/24"]},
            {"name": "AzureBastionSubnet", "address_prefixes": ["10.10.1.0/24"]},
        ]

        result = validator.validate_vnet_subnets(
            vnet_name="demo-vnet",
            vnet_address_space=["10.0.0.0/16"],
            subnets=subnets,
        )

        assert result.auto_fixed is True
        assert len(result.issues) == 2  # Both subnets needed fixing

        # Both subnets should now be in 10.0.0.0/16 range
        assert subnets[0]["address_prefixes"][0].startswith("10.0.")
        assert subnets[1]["address_prefixes"][0].startswith("10.0.")

        # No overlaps should exist
        overlap_issues = [i for i in result.issues if i.issue_type == "overlap"]
        assert len(overlap_issues) == 0

    def test_ipv6_support(self):
        """Test that IPv6 addresses are handled correctly."""
        validator = SubnetValidator(auto_fix=False)

        subnets = [
            {"name": "ipv6-subnet", "address_prefixes": ["fd00:db8::/64"]},
        ]

        result = validator.validate_vnet_subnets(
            vnet_name="test-vnet",
            vnet_address_space=["fd00:db8::/48"],
            subnets=subnets,
        )

        assert result.valid is True
        assert len(result.issues) == 0

    def test_invalid_vnet_address_space(self):
        """Test handling of invalid VNet address space."""
        validator = SubnetValidator(auto_fix=False)

        subnets = [
            {"name": "subnet1", "address_prefixes": ["10.0.1.0/24"]},
        ]

        result = validator.validate_vnet_subnets(
            vnet_name="test-vnet",
            vnet_address_space=["not-a-cidr"],
            subnets=subnets,
        )

        assert result.valid is False
        assert any(i.issue_type == "invalid_vnet_space" for i in result.issues)


class TestSubnetValidatorEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_subnet_list(self):
        """Test validation with no subnets."""
        validator = SubnetValidator(auto_fix=False)

        result = validator.validate_vnet_subnets(
            vnet_name="test-vnet",
            vnet_address_space=["10.0.0.0/16"],
            subnets=[],
        )

        assert result.valid is True
        assert len(result.issues) == 0

    def test_multiple_vnet_address_spaces(self):
        """Test VNet with multiple address spaces."""
        validator = SubnetValidator(auto_fix=False)

        subnets = [
            {"name": "subnet1", "address_prefixes": ["10.0.1.0/24"]},
            {"name": "subnet2", "address_prefixes": ["192.168.1.0/24"]},
        ]

        result = validator.validate_vnet_subnets(
            vnet_name="test-vnet",
            vnet_address_space=["10.0.0.0/16", "192.168.0.0/16"],
            subnets=subnets,
        )

        assert result.valid is True
        assert len(result.issues) == 0

    def test_very_large_vnet(self):
        """Test validation with a very large VNet (/8)."""
        validator = SubnetValidator(auto_fix=False)

        subnets = [
            {"name": "subnet1", "address_prefixes": ["10.0.0.0/16"]},
            {"name": "subnet2", "address_prefixes": ["10.1.0.0/16"]},
            {"name": "subnet3", "address_prefixes": ["10.2.0.0/16"]},
        ]

        result = validator.validate_vnet_subnets(
            vnet_name="large-vnet",
            vnet_address_space=["10.0.0.0/8"],
            subnets=subnets,
        )

        assert result.valid is True
        assert len(result.issues) == 0

    def test_minimum_subnet_size(self):
        """Test minimum Azure subnet size (/29)."""
        validator = SubnetValidator(auto_fix=False)

        subnets = [
            {"name": "min-subnet", "address_prefixes": ["10.0.1.0/29"]},
        ]

        result = validator.validate_vnet_subnets(
            vnet_name="test-vnet",
            vnet_address_space=["10.0.0.0/16"],
            subnets=subnets,
        )

        # Should be valid but with a warning
        assert result.valid is True
        warnings = [i for i in result.issues if i.issue_type == "insufficient_space"]
        assert len(warnings) == 1

    def test_terraform_resources_no_subnets(self):
        """Test Terraform validation with VNet but no subnets."""
        validator = SubnetValidator(auto_fix=False)

        terraform_resources = {
            "azurerm_virtual_network": {
                "test_vnet": {
                    "name": "test-vnet",
                    "address_space": ["10.0.0.0/16"],
                }
            },
        }

        results = validator.validate_terraform_resources(terraform_resources)

        assert len(results) == 1
        assert results[0].valid is True
        assert len(results[0].issues) == 0
