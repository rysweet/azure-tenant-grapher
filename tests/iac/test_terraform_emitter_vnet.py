"""Tests for VNet address space extraction in TerraformEmitter.

This test module covers the VNet addressSpace parsing bug where properties
weren't parsed before extraction, causing hardcoded defaults to be used.

Bug Context: VNet address space was using hardcoded default ["10.0.0.0/16"]
because properties.addressSpace.addressPrefixes wasn't parsed correctly.

Fix: Lines 512-528 in terraform_emitter.py now parse properties first,
then extract addressSpace.addressPrefixes correctly.
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.iac.emitters.terraform_emitter import TerraformEmitter
from src.iac.traverser import TenantGraph


class TestVNetAddressSpaceExtraction:
    """Unit tests for VNet address space extraction."""

    def test_vnet_with_valid_address_space(self) -> None:
        """Test VNet with valid addressSpace in properties.

        This is the primary test case - VNet with proper addressSpace should
        extract the correct address prefixes without falling back to defaults.
        No warning should be logged.
        """
        emitter = TerraformEmitter()
        graph = TenantGraph()

        # Mock VNet resource with addressSpace in properties JSON
        vnet_properties = {
            "addressSpace": {
                "addressPrefixes": ["10.8.0.0/16"]
            },
            "subnets": []
        }

        graph.resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "test-vnet",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "properties": json.dumps(vnet_properties),  # Stored as JSON string
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)

            # Read generated Terraform config
            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            # Extract VNet resource
            vnet_resource = terraform_config["resource"]["azurerm_virtual_network"][
                "test_vnet"
            ]

            # Verify address space was extracted correctly
            assert "address_space" in vnet_resource, "VNet should have address_space field"
            assert isinstance(vnet_resource["address_space"], list), (
                "address_space should be a list"
            )
            assert vnet_resource["address_space"] == ["10.8.0.0/16"], (
                "address_space should match properties.addressSpace.addressPrefixes"
            )

    def test_vnet_with_missing_address_space(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test VNet with properties but missing addressSpace.

        When addressSpace is completely missing from properties, emitter should:
        1. Fall back to default ["10.0.0.0/16"]
        2. Log a WARNING message
        """
        emitter = TerraformEmitter()
        graph = TenantGraph()

        # Mock VNet resource with properties but NO addressSpace
        vnet_properties = {
            "subnets": []
            # No addressSpace field
        }

        graph.resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet-no-address",
                "location": "westus",
                "resourceGroup": "test-rg",
                "properties": json.dumps(vnet_properties),
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)

            # Clear captured logs before emit
            caplog.clear()

            written_files = emitter.emit(graph, out_dir)

            # Read generated Terraform config
            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            vnet_resource = terraform_config["resource"]["azurerm_virtual_network"][
                "vnet_no_address"
            ]

            # Verify fallback to default address space
            assert vnet_resource["address_space"] == ["10.0.0.0/16"], (
                "Should fall back to default when addressSpace is missing"
            )

            # Verify warning was logged
            warning_logs = [
                record for record in caplog.records
                if record.levelname == "WARNING" and "vnet-no-address" in record.message
            ]
            assert len(warning_logs) > 0, "Should log WARNING when addressSpace is missing"
            assert "no addressSpace in properties" in warning_logs[0].message, (
                "Warning should mention missing addressSpace"
            )
            assert "fallback" in warning_logs[0].message.lower(), (
                "Warning should mention fallback"
            )

    def test_vnet_with_empty_address_prefixes(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test VNet with addressSpace but empty addressPrefixes array.

        When addressPrefixes exists but is empty [], emitter should:
        1. Fall back to default ["10.0.0.0/16"]
        2. Log a WARNING message
        """
        emitter = TerraformEmitter()
        graph = TenantGraph()

        # Mock VNet with addressSpace but empty prefixes
        vnet_properties = {
            "addressSpace": {
                "addressPrefixes": []  # Empty array
            },
            "subnets": []
        }

        graph.resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet-empty-prefixes",
                "location": "centralus",
                "resourceGroup": "test-rg",
                "properties": json.dumps(vnet_properties),
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)

            caplog.clear()

            written_files = emitter.emit(graph, out_dir)

            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            vnet_resource = terraform_config["resource"]["azurerm_virtual_network"][
                "vnet_empty_prefixes"
            ]

            # Verify fallback
            assert vnet_resource["address_space"] == ["10.0.0.0/16"], (
                "Should fall back to default when addressPrefixes is empty"
            )

            # Verify warning
            warning_logs = [
                record for record in caplog.records
                if record.levelname == "WARNING" and "vnet-empty-prefixes" in record.message
            ]
            assert len(warning_logs) > 0, "Should log WARNING when addressPrefixes is empty"

    def test_vnet_with_multiple_address_prefixes(self) -> None:
        """Test VNet with multiple address prefixes.

        VNets can have multiple address spaces (e.g., ["10.0.0.0/16", "10.1.0.0/16"]).
        All prefixes should be preserved in the emitted Terraform.
        """
        emitter = TerraformEmitter()
        graph = TenantGraph()

        # Mock VNet with multiple address spaces
        vnet_properties = {
            "addressSpace": {
                "addressPrefixes": ["10.0.0.0/16", "10.1.0.0/16"]
            },
            "subnets": []
        }

        graph.resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "multi-address-vnet",
                "location": "eastus2",
                "resourceGroup": "test-rg",
                "properties": json.dumps(vnet_properties),
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)

            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            vnet_resource = terraform_config["resource"]["azurerm_virtual_network"][
                "multi_address_vnet"
            ]

            # Verify ALL address prefixes are preserved
            assert vnet_resource["address_space"] == ["10.0.0.0/16", "10.1.0.0/16"], (
                "All address prefixes should be preserved"
            )

    def test_vnet_with_properties_as_dict(self) -> None:
        """Test VNet with properties already as dict (not JSON string).

        The _parse_properties method handles both JSON strings and dicts.
        This tests the dict path.
        """
        emitter = TerraformEmitter()
        graph = TenantGraph()

        # Properties as dict instead of JSON string
        vnet_properties = {
            "addressSpace": {
                "addressPrefixes": ["192.168.0.0/16"]
            },
            "subnets": []
        }

        graph.resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet-dict-props",
                "location": "westus2",
                "resourceGroup": "test-rg",
                "properties": vnet_properties,  # Dict, not JSON string
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)

            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            vnet_resource = terraform_config["resource"]["azurerm_virtual_network"][
                "vnet_dict_props"
            ]

            # Should handle dict properties correctly
            assert vnet_resource["address_space"] == ["192.168.0.0/16"], (
                "Should parse addressSpace from dict properties"
            )

    def test_vnet_with_malformed_properties_json(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test VNet with malformed properties JSON.

        When properties JSON is invalid, _parse_properties returns empty dict,
        triggering the fallback path.
        """
        emitter = TerraformEmitter()
        graph = TenantGraph()

        graph.resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet-bad-json",
                "location": "northeurope",
                "resourceGroup": "test-rg",
                "properties": "{invalid json}",  # Malformed JSON
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)

            caplog.clear()

            written_files = emitter.emit(graph, out_dir)

            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            vnet_resource = terraform_config["resource"]["azurerm_virtual_network"][
                "vnet_bad_json"
            ]

            # Should fall back to default
            assert vnet_resource["address_space"] == ["10.0.0.0/16"], (
                "Should fall back when properties JSON is malformed"
            )

            # Should log warning about missing addressSpace (result of empty parsed properties)
            warning_logs = [
                record for record in caplog.records
                if record.levelname == "WARNING" and "vnet-bad-json" in record.message
            ]
            assert len(warning_logs) > 0, "Should log WARNING for malformed properties"

    def test_vnet_with_no_properties_field(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test VNet with no properties field at all.

        When properties field is missing entirely, _parse_properties returns empty dict.
        """
        emitter = TerraformEmitter()
        graph = TenantGraph()

        graph.resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet-no-props",
                "location": "southcentralus",
                "resourceGroup": "test-rg",
                # No properties field
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)

            caplog.clear()

            written_files = emitter.emit(graph, out_dir)

            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            vnet_resource = terraform_config["resource"]["azurerm_virtual_network"][
                "vnet_no_props"
            ]

            # Should fall back to default
            assert vnet_resource["address_space"] == ["10.0.0.0/16"], (
                "Should fall back when properties field is missing"
            )

            # Should log warning
            warning_logs = [
                record for record in caplog.records
                if record.levelname == "WARNING" and "vnet-no-props" in record.message
            ]
            assert len(warning_logs) > 0, "Should log WARNING when properties is missing"


class TestVNetAddressSpaceEdgeCases:
    """Edge case tests for VNet address space extraction."""

    def test_vnet_with_ipv6_address_space(self) -> None:
        """Test VNet with IPv6 address space.

        Azure supports IPv6 address spaces. These should be preserved.
        """
        emitter = TerraformEmitter()
        graph = TenantGraph()

        vnet_properties = {
            "addressSpace": {
                "addressPrefixes": ["10.0.0.0/16", "fd00:db8:deca::/48"]
            },
            "subnets": []
        }

        graph.resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet-ipv6",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "properties": json.dumps(vnet_properties),
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)

            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            vnet_resource = terraform_config["resource"]["azurerm_virtual_network"][
                "vnet_ipv6"
            ]

            # Both IPv4 and IPv6 should be preserved
            assert len(vnet_resource["address_space"]) == 2
            assert "10.0.0.0/16" in vnet_resource["address_space"]
            assert "fd00:db8:deca::/48" in vnet_resource["address_space"]

    def test_vnet_with_large_cidr_block(self) -> None:
        """Test VNet with large CIDR block (e.g., /8).

        Azure allows /8 to /29 for IPv4. Verify large blocks work.
        """
        emitter = TerraformEmitter()
        graph = TenantGraph()

        vnet_properties = {
            "addressSpace": {
                "addressPrefixes": ["10.0.0.0/8"]
            },
            "subnets": []
        }

        graph.resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet-large-cidr",
                "location": "westus",
                "resourceGroup": "test-rg",
                "properties": json.dumps(vnet_properties),
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)

            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            vnet_resource = terraform_config["resource"]["azurerm_virtual_network"][
                "vnet_large_cidr"
            ]

            assert vnet_resource["address_space"] == ["10.0.0.0/8"]

    def test_vnet_with_small_cidr_block(self) -> None:
        """Test VNet with small CIDR block (e.g., /29).

        Azure allows down to /29 for IPv4. Verify small blocks work.
        """
        emitter = TerraformEmitter()
        graph = TenantGraph()

        vnet_properties = {
            "addressSpace": {
                "addressPrefixes": ["10.0.0.0/29"]
            },
            "subnets": []
        }

        graph.resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet-small-cidr",
                "location": "centralus",
                "resourceGroup": "test-rg",
                "properties": json.dumps(vnet_properties),
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)

            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            vnet_resource = terraform_config["resource"]["azurerm_virtual_network"][
                "vnet_small_cidr"
            ]

            assert vnet_resource["address_space"] == ["10.0.0.0/29"]

    def test_multiple_vnets_with_different_address_spaces(self) -> None:
        """Test multiple VNets with different address spaces.

        Verify that each VNet gets its own correct address space.
        """
        emitter = TerraformEmitter()
        graph = TenantGraph()

        vnet1_properties = {
            "addressSpace": {
                "addressPrefixes": ["10.0.0.0/16"]
            },
            "subnets": []
        }

        vnet2_properties = {
            "addressSpace": {
                "addressPrefixes": ["172.16.0.0/12"]
            },
            "subnets": []
        }

        vnet3_properties = {
            "addressSpace": {
                "addressPrefixes": ["192.168.0.0/16"]
            },
            "subnets": []
        }

        graph.resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet-1",
                "location": "eastus",
                "resourceGroup": "rg1",
                "properties": json.dumps(vnet1_properties),
            },
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet-2",
                "location": "westus",
                "resourceGroup": "rg2",
                "properties": json.dumps(vnet2_properties),
            },
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet-3",
                "location": "centralus",
                "resourceGroup": "rg3",
                "properties": json.dumps(vnet3_properties),
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)

            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            # Verify each VNet has correct address space
            vnet1 = terraform_config["resource"]["azurerm_virtual_network"]["vnet_1"]
            vnet2 = terraform_config["resource"]["azurerm_virtual_network"]["vnet_2"]
            vnet3 = terraform_config["resource"]["azurerm_virtual_network"]["vnet_3"]

            assert vnet1["address_space"] == ["10.0.0.0/16"]
            assert vnet2["address_space"] == ["172.16.0.0/12"]
            assert vnet3["address_space"] == ["192.168.0.0/16"]


class TestVNetAddressSpaceRegression:
    """Regression tests to prevent the original bug from returning."""

    def test_regression_properties_not_parsed_before_extraction(self) -> None:
        """REGRESSION: Ensure properties are parsed BEFORE addressSpace extraction.

        This is the core bug that was fixed. Before the fix, the code tried to
        extract addressSpace without calling _parse_properties first, causing
        it to always use the hardcoded default.

        This test verifies the fix by ensuring properties.addressSpace.addressPrefixes
        is correctly extracted when properties is a JSON string.
        """
        emitter = TerraformEmitter()
        graph = TenantGraph()

        # This is the exact scenario that triggered the bug:
        # - properties is a JSON string (as stored in Neo4j)
        # - addressSpace is nested inside: properties.addressSpace.addressPrefixes
        vnet_properties = {
            "addressSpace": {
                "addressPrefixes": ["10.8.0.0/16"]  # Custom address space
            },
            "subnets": []
        }

        graph.resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "regression-vnet",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "properties": json.dumps(vnet_properties),  # JSON string (key point!)
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)

            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            vnet_resource = terraform_config["resource"]["azurerm_virtual_network"][
                "regression_vnet"
            ]

            # THE KEY ASSERTION: Should NOT be the hardcoded default
            assert vnet_resource["address_space"] != ["10.0.0.0/16"], (
                "REGRESSION: VNet is using hardcoded default instead of actual addressSpace. "
                "This indicates properties were not parsed before extraction."
            )

            # Should be the actual value from properties
            assert vnet_resource["address_space"] == ["10.8.0.0/16"], (
                "VNet should use actual addressSpace from properties, not hardcoded default"
            )

    def test_regression_no_warning_for_valid_address_space(self, caplog: pytest.LogCaptureFixture) -> None:
        """REGRESSION: Ensure no warning is logged when addressSpace is valid.

        Before the fix, even valid VNets might log warnings because the parsing
        wasn't working correctly.
        """
        emitter = TerraformEmitter()
        graph = TenantGraph()

        vnet_properties = {
            "addressSpace": {
                "addressPrefixes": ["10.5.0.0/16"]
            },
            "subnets": []
        }

        graph.resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "valid-vnet",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "properties": json.dumps(vnet_properties),
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)

            caplog.clear()

            emitter.emit(graph, out_dir)

            # Check for warnings about this VNet
            vnet_warnings = [
                record for record in caplog.records
                if record.levelname == "WARNING"
                and "valid-vnet" in record.message
                and "addressSpace" in record.message
            ]

            # Should NOT log warnings for valid addressSpace
            assert len(vnet_warnings) == 0, (
                "REGRESSION: Warning logged for VNet with valid addressSpace. "
                "This should only happen when addressSpace is missing/empty."
            )
