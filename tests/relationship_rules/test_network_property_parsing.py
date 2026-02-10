"""Tests for property parsing in NetworkRuleOptimized (Issue #873).

This test suite validates:
- JSON parsing of properties field
- camelCase property names (networkProfile, not network_profile)
- VM → NIC relationship extraction
- Subnet → NSG relationship extraction
"""

import json
from unittest.mock import MagicMock

import pytest

from src.relationship_rules.network_rule_optimized import NetworkRuleOptimized


class TestNetworkRulePropertyParsing:
    """Test property parsing in network rule."""

    @pytest.fixture
    def mock_db_ops(self):
        """Provide mock database operations."""
        db_ops = MagicMock()
        db_ops.session_manager = None
        return db_ops

    def test_parse_properties_json_string(self, mock_db_ops):
        """Test parsing properties from JSON string."""
        rule = NetworkRuleOptimized(enable_dual_graph=True)

        properties = {
            "networkProfile": {
                "networkInterfaces": [
                    {
                        "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic1"
                    }
                ]
            }
        }

        vm = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "properties": json.dumps(properties),
        }

        rule.emit(vm, mock_db_ops)

        # Should have queued VM -> NIC relationship
        assert len(rule._relationship_buffer) == 1
        assert rule._relationship_buffer[0][1] == "USES"

    def test_parse_properties_dict(self, mock_db_ops):
        """Test parsing properties from dict."""
        rule = NetworkRuleOptimized(enable_dual_graph=True)

        vm = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {
                "networkProfile": {
                    "networkInterfaces": [
                        {
                            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic1"
                        }
                    ]
                }
            },
        }

        rule.emit(vm, mock_db_ops)

        # Should have queued VM -> NIC relationship
        assert len(rule._relationship_buffer) == 1
        assert rule._relationship_buffer[0][1] == "USES"

    def test_camel_case_network_profile(self, mock_db_ops):
        """Test that rule uses camelCase 'networkProfile' not snake_case 'network_profile'."""
        rule = NetworkRuleOptimized(enable_dual_graph=True)

        # This should work (camelCase)
        vm_camel = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {
                "networkProfile": {
                    "networkInterfaces": [
                        {
                            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic1"
                        }
                    ]
                }
            },
        }

        rule.emit(vm_camel, mock_db_ops)
        assert len(rule._relationship_buffer) == 1

        # Clear buffer
        rule._relationship_buffer.clear()

        # This should NOT work (snake_case)
        vm_snake = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm2",
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {
                "network_profile": {  # Wrong: snake_case
                    "network_interfaces": [
                        {
                            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic2"
                        }
                    ]
                }
            },
        }

        rule.emit(vm_snake, mock_db_ops)
        assert len(rule._relationship_buffer) == 0  # No relationships created

    def test_camel_case_network_security_group(self, mock_db_ops):
        """Test that rule uses camelCase 'networkSecurityGroup' not snake_case."""
        rule = NetworkRuleOptimized(enable_dual_graph=True)

        # This should work (camelCase)
        subnet_camel = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1",
            "type": "Microsoft.Network/virtualNetworks/subnets",
            "properties": {
                "networkSecurityGroup": {
                    "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkSecurityGroups/nsg1"
                }
            },
        }

        rule.emit(subnet_camel, mock_db_ops)
        assert len(rule._relationship_buffer) == 1
        assert rule._relationship_buffer[0][1] == "SECURED_BY"

        # Clear buffer
        rule._relationship_buffer.clear()

        # This should NOT work (snake_case)
        subnet_snake = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet2",
            "type": "Microsoft.Network/virtualNetworks/subnets",
            "properties": {
                "network_security_group": {  # Wrong: snake_case
                    "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkSecurityGroups/nsg2"
                }
            },
        }

        rule.emit(subnet_snake, mock_db_ops)
        assert len(rule._relationship_buffer) == 0  # No relationships created

    def test_malformed_json_handled_gracefully(self, mock_db_ops):
        """Test that malformed JSON properties are handled gracefully."""
        rule = NetworkRuleOptimized(enable_dual_graph=True)

        vm = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "properties": "{ malformed json without closing brace",
        }

        # Should not raise exception
        rule.emit(vm, mock_db_ops)

        # No relationships should be created
        assert len(rule._relationship_buffer) == 0

    def test_missing_properties_field(self, mock_db_ops):
        """Test that missing properties field is handled gracefully."""
        rule = NetworkRuleOptimized(enable_dual_graph=True)

        vm = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "type": "Microsoft.Compute/virtualMachines",
            # No properties field
        }

        # Should not raise exception
        rule.emit(vm, mock_db_ops)

        # No relationships should be created
        assert len(rule._relationship_buffer) == 0


class TestVMToNICRelationshipExtraction:
    """Test VM -> NIC relationship extraction."""

    @pytest.fixture
    def mock_db_ops(self):
        """Provide mock database operations."""
        db_ops = MagicMock()
        db_ops.session_manager = None
        return db_ops

    def test_vm_single_nic(self, mock_db_ops):
        """Test VM with single NIC creates USES relationship."""
        rule = NetworkRuleOptimized(enable_dual_graph=True)

        vm = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {
                "networkProfile": {
                    "networkInterfaces": [
                        {
                            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic1"
                        }
                    ]
                }
            },
        }

        rule.emit(vm, mock_db_ops)

        assert len(rule._relationship_buffer) == 1
        buffered = rule._relationship_buffer[0]
        assert (
            buffered[0]
            == "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1"
        )
        assert buffered[1] == "USES"
        assert (
            buffered[2]
            == "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic1"
        )

    def test_vm_multiple_nics(self, mock_db_ops):
        """Test VM with multiple NICs creates multiple USES relationships."""
        rule = NetworkRuleOptimized(enable_dual_graph=True)

        vm = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {
                "networkProfile": {
                    "networkInterfaces": [
                        {
                            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic1"
                        },
                        {
                            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic2"
                        },
                    ]
                }
            },
        }

        rule.emit(vm, mock_db_ops)

        assert len(rule._relationship_buffer) == 2
        assert all(r[1] == "USES" for r in rule._relationship_buffer)

        # Verify both NIC IDs
        nic_ids = {r[2] for r in rule._relationship_buffer}
        assert (
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic1"
            in nic_ids
        )
        assert (
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic2"
            in nic_ids
        )

    def test_vm_missing_network_profile(self, mock_db_ops):
        """Test VM without networkProfile creates no relationships."""
        rule = NetworkRuleOptimized(enable_dual_graph=True)

        vm = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {},
        }

        rule.emit(vm, mock_db_ops)

        assert len(rule._relationship_buffer) == 0

    def test_vm_empty_network_interfaces_array(self, mock_db_ops):
        """Test VM with empty networkInterfaces array creates no relationships."""
        rule = NetworkRuleOptimized(enable_dual_graph=True)

        vm = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {"networkProfile": {"networkInterfaces": []}},
        }

        rule.emit(vm, mock_db_ops)

        assert len(rule._relationship_buffer) == 0

    def test_vm_nic_without_id(self, mock_db_ops):
        """Test VM with NIC entry missing 'id' field."""
        rule = NetworkRuleOptimized(enable_dual_graph=True)

        vm = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {
                "networkProfile": {
                    "networkInterfaces": [
                        {"name": "nic1"}  # Missing 'id' field
                    ]
                }
            },
        }

        rule.emit(vm, mock_db_ops)

        assert len(rule._relationship_buffer) == 0


class TestSubnetToNSGRelationshipExtraction:
    """Test Subnet -> NSG relationship extraction."""

    @pytest.fixture
    def mock_db_ops(self):
        """Provide mock database operations."""
        db_ops = MagicMock()
        db_ops.session_manager = None
        return db_ops

    def test_subnet_with_nsg(self, mock_db_ops):
        """Test subnet with NSG creates SECURED_BY relationship."""
        rule = NetworkRuleOptimized(enable_dual_graph=True)

        subnet = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1",
            "type": "Microsoft.Network/virtualNetworks/subnets",
            "properties": {
                "networkSecurityGroup": {
                    "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkSecurityGroups/nsg1"
                }
            },
        }

        rule.emit(subnet, mock_db_ops)

        assert len(rule._relationship_buffer) == 1
        buffered = rule._relationship_buffer[0]
        assert (
            buffered[0]
            == "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1"
        )
        assert buffered[1] == "SECURED_BY"
        assert (
            buffered[2]
            == "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkSecurityGroups/nsg1"
        )

    def test_subnet_without_nsg(self, mock_db_ops):
        """Test subnet without NSG creates no SECURED_BY relationship."""
        rule = NetworkRuleOptimized(enable_dual_graph=True)

        subnet = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1",
            "type": "Microsoft.Network/virtualNetworks/subnets",
            "properties": {},
        }

        rule.emit(subnet, mock_db_ops)

        assert len(rule._relationship_buffer) == 0

    def test_subnet_nsg_without_id(self, mock_db_ops):
        """Test subnet with NSG entry missing 'id' field."""
        rule = NetworkRuleOptimized(enable_dual_graph=True)

        subnet = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1",
            "type": "Microsoft.Network/virtualNetworks/subnets",
            "properties": {
                "networkSecurityGroup": {
                    "name": "nsg1"  # Missing 'id' field
                }
            },
        }

        rule.emit(subnet, mock_db_ops)

        assert len(rule._relationship_buffer) == 0

    def test_subnet_nsg_null(self, mock_db_ops):
        """Test subnet with null NSG."""
        rule = NetworkRuleOptimized(enable_dual_graph=True)

        subnet = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1",
            "type": "Microsoft.Network/virtualNetworks/subnets",
            "properties": {"networkSecurityGroup": None},
        }

        rule.emit(subnet, mock_db_ops)

        assert len(rule._relationship_buffer) == 0


class TestNetworkRuleApplies:
    """Test applies() method for network rule."""

    def test_applies_to_virtual_machines(self):
        """Test rule applies to virtual machines."""
        rule = NetworkRuleOptimized()

        vm = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "type": "Microsoft.Compute/virtualMachines",
        }

        assert rule.applies(vm) is True

    def test_applies_to_subnets(self):
        """Test rule applies to subnets."""
        rule = NetworkRuleOptimized()

        subnet = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1",
            "type": "Microsoft.Network/virtualNetworks/subnets",
        }

        assert rule.applies(subnet) is True

    def test_applies_to_private_endpoints(self):
        """Test rule applies to private endpoints."""
        rule = NetworkRuleOptimized()

        pe = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/privateEndpoints/pe1",
            "type": "Microsoft.Network/privateEndpoints",
        }

        assert rule.applies(pe) is True

    def test_applies_to_dns_zones(self):
        """Test rule applies to DNS zones."""
        rule = NetworkRuleOptimized()

        dns_zone = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/dnszones/zone1",
            "type": "Microsoft.Network/dnszones",
        }

        assert rule.applies(dns_zone) is True

    def test_does_not_apply_to_other_types(self):
        """Test rule does not apply to non-network resources."""
        rule = NetworkRuleOptimized()

        other_types = [
            "Microsoft.Storage/storageAccounts",
            "Microsoft.KeyVault/vaults",
            "Microsoft.Sql/servers",
        ]

        for resource_type in other_types:
            resource = {
                "id": f"/subscriptions/sub1/resourceGroups/rg1/providers/{resource_type}/resource1",
                "type": resource_type,
            }
            assert rule.applies(resource) is False


class TestNetworkRuleLogging:
    """Test logging in network rule."""

    @pytest.fixture
    def mock_db_ops(self):
        """Provide mock database operations."""
        db_ops = MagicMock()
        db_ops.session_manager = None
        return db_ops

    def test_emit_logs_queued_relationships(self, mock_db_ops):
        """Test that emit logs queued relationships."""
        import structlog
        from unittest.mock import patch

        rule = NetworkRuleOptimized(enable_dual_graph=True)

        vm = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {
                "networkProfile": {
                    "networkInterfaces": [
                        {
                            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic1"
                        }
                    ]
                }
            },
        }

        # Mock logger to capture debug calls
        with patch("src.relationship_rules.network_rule_optimized.logger") as mock_logger:
            rule.emit(vm, mock_db_ops)

            # Verify logger.debug was called
            assert mock_logger.debug.called

            # Check for "Queued" in log messages
            debug_calls = [call[0][0] for call in mock_logger.debug.call_args_list]
            queued_logs = [log for log in debug_calls if "Queued" in log]
            assert len(queued_logs) > 0
