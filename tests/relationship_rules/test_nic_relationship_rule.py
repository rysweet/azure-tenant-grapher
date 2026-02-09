"""Tests for NIC Relationship Rule (Issue #873).

This test suite validates the NICRelationshipRule which creates:
- (NetworkInterface) -[:CONNECTED_TO]-> (Subnet)
- (NetworkInterface) -[:SECURED_BY]-> (NetworkSecurityGroup)

Key scenarios:
- applies() returns True for NICs
- emit() extracts subnet from ipConfigurations[].properties.subnet
- emit() creates CONNECTED_TO relationships
- emit() creates SECURED_BY relationships if NSG attached
- extract_target_ids() finds subnet and NSG IDs
"""

import json
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

from src.relationship_rules.nic_relationship_rule import NICRelationshipRule


class TestNICRelationshipRuleApplies:
    """Test applies() method determines if rule applies to resource."""

    def test_applies_to_network_interface(self):
        """Test that rule applies to Microsoft.Network/networkInterfaces resources."""
        rule = NICRelationshipRule()

        resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic1",
            "type": "Microsoft.Network/networkInterfaces",
            "name": "nic1",
        }

        assert rule.applies(resource) is True

    def test_does_not_apply_to_other_types(self):
        """Test that rule does not apply to non-NIC resources."""
        rule = NICRelationshipRule()

        other_types = [
            "Microsoft.Compute/virtualMachines",
            "Microsoft.Network/virtualNetworks",
            "Microsoft.Network/networkSecurityGroups",
            "Microsoft.Storage/storageAccounts",
        ]

        for resource_type in other_types:
            resource = {
                "id": f"/subscriptions/sub1/resourceGroups/rg1/providers/{resource_type}/resource1",
                "type": resource_type,
                "name": "resource1",
            }
            assert rule.applies(resource) is False

    def test_applies_with_missing_type(self):
        """Test that rule handles missing type field gracefully."""
        rule = NICRelationshipRule()

        resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic1",
            "name": "nic1",
        }

        assert rule.applies(resource) is False


class TestNICRelationshipRuleEmit:
    """Test emit() method creates relationships."""

    @pytest.fixture
    def mock_db_ops(self):
        """Provide mock database operations."""
        db_ops = MagicMock()
        db_ops.session_manager = None  # Use legacy mode for tests
        return db_ops

    @pytest.fixture
    def nic_with_subnet_json_string(self):
        """NIC resource with subnet in JSON string format."""
        properties = {
            "ipConfigurations": [
                {
                    "name": "ipconfig1",
                    "properties": {
                        "subnet": {
                            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1"
                        },
                        "privateIPAddress": "10.0.0.4",
                    },
                }
            ]
        }

        return {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic1",
            "type": "Microsoft.Network/networkInterfaces",
            "name": "nic1",
            "properties": json.dumps(properties),
        }

    @pytest.fixture
    def nic_with_subnet_dict(self):
        """NIC resource with subnet in dict format."""
        return {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic1",
            "type": "Microsoft.Network/networkInterfaces",
            "name": "nic1",
            "properties": {
                "ipConfigurations": [
                    {
                        "name": "ipconfig1",
                        "properties": {
                            "subnet": {
                                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1"
                            },
                            "privateIPAddress": "10.0.0.4",
                        },
                    }
                ]
            },
        }

    @pytest.fixture
    def nic_with_nsg_json_string(self):
        """NIC resource with NSG attached (JSON string format)."""
        properties = {
            "ipConfigurations": [
                {
                    "name": "ipconfig1",
                    "properties": {
                        "subnet": {
                            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1"
                        }
                    },
                }
            ],
            "networkSecurityGroup": {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkSecurityGroups/nsg1"
            },
        }

        return {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic1",
            "type": "Microsoft.Network/networkInterfaces",
            "name": "nic1",
            "properties": json.dumps(properties),
        }

    def test_emit_creates_connected_to_relationship_json_string(
        self, nic_with_subnet_json_string, mock_db_ops
    ):
        """Test that emit() creates CONNECTED_TO relationship (JSON string properties)."""
        rule = NICRelationshipRule(enable_dual_graph=True)

        rule.emit(nic_with_subnet_json_string, mock_db_ops)

        # Verify relationship was queued
        assert len(rule._relationship_buffer) == 1
        buffered = rule._relationship_buffer[0]
        assert (
            buffered[0]
            == "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic1"
        )
        assert buffered[1] == "CONNECTED_TO"
        assert (
            buffered[2]
            == "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1"
        )

    def test_emit_creates_connected_to_relationship_dict(
        self, nic_with_subnet_dict, mock_db_ops
    ):
        """Test that emit() creates CONNECTED_TO relationship (dict properties)."""
        rule = NICRelationshipRule(enable_dual_graph=True)

        rule.emit(nic_with_subnet_dict, mock_db_ops)

        # Verify relationship was queued
        assert len(rule._relationship_buffer) == 1
        buffered = rule._relationship_buffer[0]
        assert buffered[1] == "CONNECTED_TO"

    def test_emit_creates_secured_by_relationship(
        self, nic_with_nsg_json_string, mock_db_ops
    ):
        """Test that emit() creates SECURED_BY relationship when NSG attached."""
        rule = NICRelationshipRule(enable_dual_graph=True)

        rule.emit(nic_with_nsg_json_string, mock_db_ops)

        # Should have 2 relationships: CONNECTED_TO + SECURED_BY
        assert len(rule._relationship_buffer) == 2

        # Find SECURED_BY relationship
        secured_by = [r for r in rule._relationship_buffer if r[1] == "SECURED_BY"]
        assert len(secured_by) == 1

        buffered = secured_by[0]
        assert (
            buffered[0]
            == "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic1"
        )
        assert buffered[1] == "SECURED_BY"
        assert (
            buffered[2]
            == "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkSecurityGroups/nsg1"
        )

    def test_emit_handles_multiple_ip_configurations(self, mock_db_ops):
        """Test that emit() handles NICs with multiple IP configurations."""
        nic = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic1",
            "type": "Microsoft.Network/networkInterfaces",
            "name": "nic1",
            "properties": {
                "ipConfigurations": [
                    {
                        "name": "ipconfig1",
                        "properties": {
                            "subnet": {
                                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1"
                            }
                        },
                    },
                    {
                        "name": "ipconfig2",
                        "properties": {
                            "subnet": {
                                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet2"
                            }
                        },
                    },
                ]
            },
        }

        rule = NICRelationshipRule(enable_dual_graph=True)
        rule.emit(nic, mock_db_ops)

        # Should have 2 CONNECTED_TO relationships (one per subnet)
        assert len(rule._relationship_buffer) == 2
        assert all(r[1] == "CONNECTED_TO" for r in rule._relationship_buffer)

    def test_emit_handles_missing_properties(self, mock_db_ops):
        """Test that emit() handles NIC with missing properties gracefully."""
        nic = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic1",
            "type": "Microsoft.Network/networkInterfaces",
            "name": "nic1",
        }

        rule = NICRelationshipRule(enable_dual_graph=True)
        rule.emit(nic, mock_db_ops)

        # No relationships should be created
        assert len(rule._relationship_buffer) == 0

    def test_emit_handles_malformed_json(self, mock_db_ops):
        """Test that emit() handles malformed JSON properties gracefully."""
        nic = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic1",
            "type": "Microsoft.Network/networkInterfaces",
            "name": "nic1",
            "properties": "{ malformed json",
        }

        rule = NICRelationshipRule(enable_dual_graph=True)
        rule.emit(nic, mock_db_ops)

        # No relationships should be created
        assert len(rule._relationship_buffer) == 0

    def test_emit_handles_missing_subnet_in_ip_config(self, mock_db_ops):
        """Test that emit() handles IP configuration without subnet."""
        nic = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic1",
            "type": "Microsoft.Network/networkInterfaces",
            "name": "nic1",
            "properties": {
                "ipConfigurations": [
                    {
                        "name": "ipconfig1",
                        "properties": {
                            "privateIPAddress": "10.0.0.4"
                            # No subnet
                        },
                    }
                ]
            },
        }

        rule = NICRelationshipRule(enable_dual_graph=True)
        rule.emit(nic, mock_db_ops)

        # No relationships should be created
        assert len(rule._relationship_buffer) == 0

    def test_emit_handles_nsg_without_subnet(self, mock_db_ops):
        """Test that emit() creates SECURED_BY even if no subnet present."""
        nic = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic1",
            "type": "Microsoft.Network/networkInterfaces",
            "name": "nic1",
            "properties": {
                "ipConfigurations": [],
                "networkSecurityGroup": {
                    "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkSecurityGroups/nsg1"
                },
            },
        }

        rule = NICRelationshipRule(enable_dual_graph=True)
        rule.emit(nic, mock_db_ops)

        # Should have 1 SECURED_BY relationship
        assert len(rule._relationship_buffer) == 1
        assert rule._relationship_buffer[0][1] == "SECURED_BY"


class TestNICRelationshipRuleExtractTargetIds:
    """Test extract_target_ids() method for dependency collection."""

    def test_extract_subnet_id_json_string(self):
        """Test extracting subnet ID from JSON string properties."""
        rule = NICRelationshipRule()

        properties = {
            "ipConfigurations": [
                {
                    "properties": {
                        "subnet": {
                            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1"
                        }
                    }
                }
            ]
        }

        nic = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic1",
            "type": "Microsoft.Network/networkInterfaces",
            "properties": json.dumps(properties),
        }

        target_ids = rule.extract_target_ids(nic)

        assert len(target_ids) == 1
        assert (
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1"
            in target_ids
        )

    def test_extract_subnet_id_dict(self):
        """Test extracting subnet ID from dict properties."""
        rule = NICRelationshipRule()

        nic = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic1",
            "type": "Microsoft.Network/networkInterfaces",
            "properties": {
                "ipConfigurations": [
                    {
                        "properties": {
                            "subnet": {
                                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1"
                            }
                        }
                    }
                ]
            },
        }

        target_ids = rule.extract_target_ids(nic)

        assert len(target_ids) == 1
        assert (
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1"
            in target_ids
        )

    def test_extract_nsg_id(self):
        """Test extracting NSG ID."""
        rule = NICRelationshipRule()

        nic = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic1",
            "type": "Microsoft.Network/networkInterfaces",
            "properties": {
                "ipConfigurations": [
                    {
                        "properties": {
                            "subnet": {
                                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1"
                            }
                        }
                    }
                ],
                "networkSecurityGroup": {
                    "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkSecurityGroups/nsg1"
                },
            },
        }

        target_ids = rule.extract_target_ids(nic)

        # Should have both subnet and NSG
        assert len(target_ids) == 2
        assert (
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1"
            in target_ids
        )
        assert (
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkSecurityGroups/nsg1"
            in target_ids
        )

    def test_extract_multiple_subnet_ids(self):
        """Test extracting multiple subnet IDs from multiple IP configurations."""
        rule = NICRelationshipRule()

        nic = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic1",
            "type": "Microsoft.Network/networkInterfaces",
            "properties": {
                "ipConfigurations": [
                    {
                        "properties": {
                            "subnet": {
                                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1"
                            }
                        }
                    },
                    {
                        "properties": {
                            "subnet": {
                                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet2"
                            }
                        }
                    },
                ]
            },
        }

        target_ids = rule.extract_target_ids(nic)

        assert len(target_ids) == 2
        assert (
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1"
            in target_ids
        )
        assert (
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet2"
            in target_ids
        )

    def test_extract_returns_empty_set_for_missing_properties(self):
        """Test that extract_target_ids returns empty set for missing properties."""
        rule = NICRelationshipRule()

        nic = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic1",
            "type": "Microsoft.Network/networkInterfaces",
        }

        target_ids = rule.extract_target_ids(nic)

        assert len(target_ids) == 0

    def test_extract_handles_malformed_json(self):
        """Test that extract_target_ids handles malformed JSON gracefully."""
        rule = NICRelationshipRule()

        nic = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic1",
            "type": "Microsoft.Network/networkInterfaces",
            "properties": "{ malformed json",
        }

        target_ids = rule.extract_target_ids(nic)

        assert len(target_ids) == 0


class TestNICRelationshipRuleIntegration:
    """Integration tests for NIC relationship rule."""

    @pytest.fixture
    def mock_db_ops(self):
        """Provide mock database operations."""
        db_ops = MagicMock()
        db_ops.session_manager = None
        return db_ops

    def test_end_to_end_nic_with_subnet_and_nsg(self, mock_db_ops):
        """Test complete workflow: applies -> emit -> extract."""
        rule = NICRelationshipRule(enable_dual_graph=True)

        nic = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic1",
            "type": "Microsoft.Network/networkInterfaces",
            "name": "nic1",
            "properties": {
                "ipConfigurations": [
                    {
                        "properties": {
                            "subnet": {
                                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1"
                            }
                        }
                    }
                ],
                "networkSecurityGroup": {
                    "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkSecurityGroups/nsg1"
                },
            },
        }

        # Test applies
        assert rule.applies(nic) is True

        # Test emit
        rule.emit(nic, mock_db_ops)
        assert len(rule._relationship_buffer) == 2

        # Test extract_target_ids
        target_ids = rule.extract_target_ids(nic)
        assert len(target_ids) == 2

        # Verify extracted IDs match emitted relationships
        buffered_targets = {r[2] for r in rule._relationship_buffer}
        assert buffered_targets == target_ids
