"""Unit tests for subnet validation integration in TransformationEngine.

This module tests the integration of SubnetValidator into the IaC generation
engine to validate subnet address space containment (Issue #333).
"""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.iac.engine import TransformationEngine
from src.iac.traverser import TenantGraph


class TestEngineSubnetValidation:
    """Test subnet validation integration in TransformationEngine."""

    @pytest.fixture
    def mock_emitter(self):
        """Create a mock emitter."""
        emitter = Mock()
        emitter.emit = Mock(return_value=[Path("/tmp/test.tf")])
        return emitter

    @pytest.fixture
    def valid_vnet_resources(self):
        """Create valid VNet resources with subnets."""
        return [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "test-vnet",
                "address_space": ["10.0.0.0/16"],
                "properties": json.dumps({
                    "subnets": [
                        {
                            "name": "subnet1",
                            "properties": {"addressPrefix": "10.0.1.0/24"}
                        },
                        {
                            "name": "subnet2",
                            "properties": {"addressPrefix": "10.0.2.0/24"}
                        }
                    ]
                }),
            }
        ]

    @pytest.fixture
    def invalid_vnet_resources(self):
        """Create VNet resources with invalid subnets."""
        return [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "test-vnet",
                "address_space": ["10.0.0.0/16"],
                "properties": json.dumps({
                    "subnets": [
                        {
                            "name": "subnet1",
                            "properties": {"addressPrefix": "192.168.1.0/24"}  # Outside VNet
                        }
                    ]
                }),
            }
        ]

    def test_valid_subnets_pass_validation(self, mock_emitter, valid_vnet_resources):
        """Test that valid subnets pass validation."""
        engine = TransformationEngine()
        graph = TenantGraph(resources=valid_vnet_resources, relationships=[])
        out_dir = Path("/tmp/test")

        # Should not raise an exception
        result = engine.generate_iac(
            graph,
            mock_emitter,
            out_dir,
            validate_subnet_containment=True,
            auto_fix_subnets=False,
        )

        assert result == [Path("/tmp/test.tf")]
        mock_emitter.emit.assert_called_once()

    def test_invalid_subnets_fail_validation(self, mock_emitter, invalid_vnet_resources):
        """Test that invalid subnets fail validation."""
        engine = TransformationEngine()
        graph = TenantGraph(resources=invalid_vnet_resources, relationships=[])
        out_dir = Path("/tmp/test")

        # Should raise ValueError
        with pytest.raises(ValueError, match="Subnet validation failed"):
            engine.generate_iac(
                graph,
                mock_emitter,
                out_dir,
                validate_subnet_containment=True,
                auto_fix_subnets=False,
            )

        # Emitter should not be called
        mock_emitter.emit.assert_not_called()

    def test_invalid_subnets_auto_fix(self, mock_emitter, invalid_vnet_resources):
        """Test that auto-fix corrects invalid subnets."""
        engine = TransformationEngine()
        graph = TenantGraph(resources=invalid_vnet_resources, relationships=[])
        out_dir = Path("/tmp/test")

        # Should not raise an exception with auto-fix enabled
        result = engine.generate_iac(
            graph,
            mock_emitter,
            out_dir,
            validate_subnet_containment=True,
            auto_fix_subnets=True,
        )

        assert result == [Path("/tmp/test.tf")]
        mock_emitter.emit.assert_called_once()

    def test_skip_subnet_validation(self, mock_emitter, invalid_vnet_resources):
        """Test that validation can be skipped."""
        engine = TransformationEngine()
        graph = TenantGraph(resources=invalid_vnet_resources, relationships=[])
        out_dir = Path("/tmp/test")

        # Should not raise an exception when validation is skipped
        result = engine.generate_iac(
            graph,
            mock_emitter,
            out_dir,
            validate_subnet_containment=False,  # Skip validation
            auto_fix_subnets=False,
        )

        assert result == [Path("/tmp/test.tf")]
        mock_emitter.emit.assert_called_once()

    def test_no_vnets_no_validation_error(self, mock_emitter):
        """Test that no VNets doesn't cause validation errors."""
        engine = TransformationEngine()
        graph = TenantGraph(
            resources=[{"type": "Microsoft.Storage/storageAccounts", "name": "test"}],
            relationships=[],
        )
        out_dir = Path("/tmp/test")

        # Should not raise an exception
        result = engine.generate_iac(
            graph,
            mock_emitter,
            out_dir,
            validate_subnet_containment=True,
            auto_fix_subnets=False,
        )

        assert result == [Path("/tmp/test.tf")]
        mock_emitter.emit.assert_called_once()

    def test_validation_with_subset_filter(self, mock_emitter, valid_vnet_resources):
        """Test validation works with subset filters."""
        engine = TransformationEngine()
        graph = TenantGraph(resources=valid_vnet_resources, relationships=[])
        out_dir = Path("/tmp/test")

        # Should not raise an exception
        result = engine.generate_iac(
            graph,
            mock_emitter,
            out_dir,
            subset_filter=None,  # Could use SubsetFilter here
            validate_subnet_containment=True,
            auto_fix_subnets=False,
        )

        assert result == [Path("/tmp/test.tf")]
        mock_emitter.emit.assert_called_once()

    def test_extract_subnets_from_vnet_dict_properties(self):
        """Test subnet extraction with dict properties."""
        engine = TransformationEngine()
        vnet = {
            "type": "Microsoft.Network/virtualNetworks",
            "name": "test-vnet",
            "properties": {
                "subnets": [
                    {"name": "subnet1", "properties": {"addressPrefix": "10.0.1.0/24"}},
                    {"name": "subnet2", "properties": {"addressPrefixes": ["10.0.2.0/24"]}},
                ]
            },
        }

        subnets = engine._extract_subnets_from_vnet(vnet)

        assert len(subnets) == 2
        assert subnets[0]["name"] == "subnet1"
        assert subnets[0]["address_prefixes"] == ["10.0.1.0/24"]
        assert subnets[1]["name"] == "subnet2"
        assert subnets[1]["address_prefixes"] == ["10.0.2.0/24"]

    def test_extract_subnets_from_vnet_json_string_properties(self):
        """Test subnet extraction with JSON string properties."""
        engine = TransformationEngine()
        vnet = {
            "type": "Microsoft.Network/virtualNetworks",
            "name": "test-vnet",
            "properties": json.dumps({
                "subnets": [
                    {"name": "subnet1", "properties": {"addressPrefix": "10.0.1.0/24"}},
                ]
            }),
        }

        subnets = engine._extract_subnets_from_vnet(vnet)

        assert len(subnets) == 1
        assert subnets[0]["name"] == "subnet1"
        assert subnets[0]["address_prefixes"] == ["10.0.1.0/24"]

    def test_extract_subnets_handles_malformed_json(self):
        """Test that malformed JSON doesn't crash extraction."""
        engine = TransformationEngine()
        vnet = {
            "type": "Microsoft.Network/virtualNetworks",
            "name": "test-vnet",
            "properties": "{invalid json}",
        }

        subnets = engine._extract_subnets_from_vnet(vnet)

        assert len(subnets) == 0
