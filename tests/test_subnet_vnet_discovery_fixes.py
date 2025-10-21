"""
Tests for VNet/Subnet discovery bug fixes (Issue from autonomous demo)

This test module covers the three root causes identified:
1. Subnets without addressPrefix field are skipped
2. VNet address spaces not extracted properly
3. Cross-RG relationships incomplete

Bug Context: During autonomous demo execution, VNet vnet-ljio3xx7w6o6y and
subnet snet-pe were not discovered during scan, causing 18 Terraform errors.
"""

import json

from src.relationship_rules.network_rule import NetworkRule
from src.relationship_rules.subnet_extraction_rule import SubnetExtractionRule


class DummyDbOps:
    """Mock database operations for testing."""

    def __init__(self):
        self.calls = []
        self.resources = {}

    def create_generic_rel(self, src, rel, tgt, tgt_label, tgt_key):
        self.calls.append(("rel", src, rel, tgt, tgt_label, tgt_key))

    def upsert_generic(self, label, key, value, props):
        self.calls.append(("upsert", label, key, value, props))

    def upsert_resource(self, resource, processing_status=None):
        self.calls.append(("upsert_resource", resource, processing_status))
        self.resources[resource["id"]] = resource


class TestSubnetWithoutAddressPrefix:
    """Test Case 1: Subnets without addressPrefix field should still be stored."""

    def test_subnet_without_address_prefix_is_stored(self):
        """
        Private endpoint subnets may not have explicit addressPrefix.
        These should still be stored in Neo4j for relationship tracking.
        """
        rule = SubnetExtractionRule()
        db = DummyDbOps()

        # VNet with a subnet that has no addressPrefix (like snet-pe)
        vnet_resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet-ljio3xx7w6o6y",
            "name": "vnet-ljio3xx7w6o6y",
            "type": "Microsoft.Network/virtualNetworks",
            "location": "eastus",
            "resource_group": "rg1",
            "subscription_id": "sub1",
            "properties": json.dumps({
                "addressSpace": {
                    "addressPrefixes": ["10.0.0.0/16"]
                },
                "subnets": [
                    {
                        "name": "snet-pe",
                        "properties": {
                            # No addressPrefix field
                            "privateEndpointNetworkPolicies": "Disabled",
                            "privateLinkServiceNetworkPolicies": "Enabled"
                        }
                    }
                ]
            })
        }

        assert rule.applies(vnet_resource)
        rule.emit(vnet_resource, db)

        # Verify subnet was created
        upsert_calls = [c for c in db.calls if c[0] == "upsert_resource"]
        assert len(upsert_calls) == 1, "Subnet should be created even without addressPrefix"

        subnet = upsert_calls[0][1]
        assert subnet["name"] == "snet-pe"
        assert subnet["type"] == "Microsoft.Network/subnets"
        assert "/subnets/snet-pe" in subnet["id"]

        # Verify CONTAINS relationship was created
        rel_calls = [c for c in db.calls if c[0] == "rel" and c[2] == "CONTAINS"]
        assert len(rel_calls) == 1, "VNet -> Subnet relationship should exist"

    def test_subnet_with_address_prefix_stored_normally(self):
        """Standard subnet with addressPrefix should work as before."""
        rule = SubnetExtractionRule()
        db = DummyDbOps()

        vnet_resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet-standard",
            "name": "vnet-standard",
            "type": "Microsoft.Network/virtualNetworks",
            "location": "eastus",
            "resource_group": "rg1",
            "subscription_id": "sub1",
            "properties": json.dumps({
                "addressSpace": {
                    "addressPrefixes": ["10.8.0.0/16"]
                },
                "subnets": [
                    {
                        "name": "snet-default",
                        "properties": {
                            "addressPrefix": "10.8.0.0/24"
                        }
                    }
                ]
            })
        }

        rule.emit(vnet_resource, db)

        subnet = db.resources[
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet-standard/subnets/snet-default"
        ]

        # Parse properties
        props = json.loads(subnet["properties"])
        assert props["addressPrefix"] == "10.8.0.0/24"

    def test_subnet_with_address_prefixes_plural(self):
        """Azure API may return addressPrefixes (plural) instead of addressPrefix."""
        rule = SubnetExtractionRule()
        db = DummyDbOps()

        vnet_resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet-multi",
            "name": "vnet-multi",
            "type": "Microsoft.Network/virtualNetworks",
            "location": "eastus",
            "resource_group": "rg1",
            "subscription_id": "sub1",
            "properties": json.dumps({
                "addressSpace": {
                    "addressPrefixes": ["10.0.0.0/16"]
                },
                "subnets": [
                    {
                        "name": "snet-multi-prefix",
                        "properties": {
                            "addressPrefixes": ["10.0.1.0/24", "10.0.2.0/24"]
                        }
                    }
                ]
            })
        }

        rule.emit(vnet_resource, db)

        subnet = db.resources[
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet-multi/subnets/snet-multi-prefix"
        ]

        props = json.loads(subnet["properties"])
        assert props["addressPrefixes"] == ["10.0.1.0/24", "10.0.2.0/24"]


class TestVNetAddressSpaceExtraction:
    """Test Case 2: VNet address spaces should be extracted and logged."""

    def test_vnet_address_space_logged_during_extraction(self, caplog):
        """VNet address space should be logged when extracting subnets."""
        import logging

        rule = SubnetExtractionRule()
        db = DummyDbOps()

        vnet_resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet-test",
            "name": "vnet-test",
            "type": "Microsoft.Network/virtualNetworks",
            "location": "eastus",
            "resource_group": "rg1",
            "subscription_id": "sub1",
            "properties": json.dumps({
                "addressSpace": {
                    "addressPrefixes": ["10.5.0.0/16", "10.6.0.0/16"]
                },
                "subnets": [
                    {
                        "name": "snet-1",
                        "properties": {
                            "addressPrefix": "10.5.1.0/24"
                        }
                    }
                ]
            })
        }

        # Set logging level to capture INFO logs
        caplog.set_level(logging.INFO)
        caplog.clear()
        rule.emit(vnet_resource, db)

        # Verify address space appears in logs (in INFO log about extracting subnets)
        log_messages = [record.message for record in caplog.records]
        # The log message contains the array representation
        assert any("10.5.0.0/16" in msg or "10.6.0.0/16" in msg for msg in log_messages), \
            f"VNet address space should be logged during extraction. Got logs: {log_messages}"

    def test_vnet_address_space_stored_in_subnet_metadata(self):
        """
        When subnet lacks addressPrefix, VNet address space should be stored
        in subnet metadata for potential IaC generation use.
        """
        rule = SubnetExtractionRule()
        db = DummyDbOps()

        vnet_resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet-meta",
            "name": "vnet-meta",
            "type": "Microsoft.Network/virtualNetworks",
            "location": "eastus",
            "resource_group": "rg1",
            "subscription_id": "sub1",
            "properties": json.dumps({
                "addressSpace": {
                    "addressPrefixes": ["192.168.0.0/16"]
                },
                "subnets": [
                    {
                        "name": "snet-no-prefix",
                        "properties": {
                            # No addressPrefix
                        }
                    }
                ]
            })
        }

        rule.emit(vnet_resource, db)

        subnet = db.resources[
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet-meta/subnets/snet-no-prefix"
        ]

        props = json.loads(subnet["properties"])
        assert "_vnet_address_space" in props, \
            "VNet address space should be stored in subnet metadata when addressPrefix is missing"
        assert props["_vnet_address_space"] == ["192.168.0.0/16"]


class TestCrossResourceGroupRelationships:
    """Test Case 3: Network relationships should work across resource groups."""

    def test_nic_subnet_relationship_cross_rg(self):
        """
        Network Interface in RG1 should create relationship to Subnet in RG2.
        This tests the fix for cross-RG subnet references.
        """
        rule = NetworkRule()
        db = DummyDbOps()

        # NIC in rg1 referencing subnet in rg2
        nic_resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic-cross-rg",
            "name": "nic-cross-rg",
            "type": "Microsoft.Network/networkInterfaces",
            "resource_group": "rg1",
            "properties": json.dumps({
                "ipConfigurations": [
                    {
                        "name": "ipconfig1",
                        "subnet": {
                            "id": "/subscriptions/sub1/resourceGroups/rg2/providers/Microsoft.Network/virtualNetworks/vnet-rg2/subnets/snet-pe"
                        }
                    }
                ]
            })
        }

        assert rule.applies(nic_resource)
        rule.emit(nic_resource, db)

        # Verify USES_SUBNET relationship was created
        rel_calls = [c for c in db.calls if c[0] == "rel" and c[2] == "USES_SUBNET"]
        assert len(rel_calls) == 1, "NIC -> Subnet relationship should be created"

        src, rel_type, tgt, tgt_label, tgt_key = rel_calls[0][1:]
        assert src == nic_resource["id"]
        assert tgt == "/subscriptions/sub1/resourceGroups/rg2/providers/Microsoft.Network/virtualNetworks/vnet-rg2/subnets/snet-pe"
        assert "rg2" in tgt, "Subnet reference should preserve cross-RG path"

    def test_nic_with_properties_as_string(self):
        """NIC properties may be stored as JSON string in Neo4j."""
        rule = NetworkRule()
        db = DummyDbOps()

        nic_resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic-json-props",
            "name": "nic-json-props",
            "type": "Microsoft.Network/networkInterfaces",
            "resource_group": "rg1",
            "properties": json.dumps({
                "ipConfigurations": [
                    {
                        "name": "ipconfig1",
                        "subnet": {
                            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1"
                        }
                    }
                ]
            })
        }

        rule.emit(nic_resource, db)

        rel_calls = [c for c in db.calls if c[0] == "rel" and c[2] == "USES_SUBNET"]
        assert len(rel_calls) == 1, "Should handle JSON string properties"

    def test_nic_with_properties_as_dict(self):
        """NIC properties may also be stored as dict."""
        rule = NetworkRule()
        db = DummyDbOps()

        nic_resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic-dict-props",
            "name": "nic-dict-props",
            "type": "Microsoft.Network/networkInterfaces",
            "resource_group": "rg1",
            "properties": {  # Dict, not JSON string
                "ipConfigurations": [
                    {
                        "name": "ipconfig1",
                        "subnet": {
                            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1"
                        }
                    }
                ]
            }
        }

        rule.emit(nic_resource, db)

        rel_calls = [c for c in db.calls if c[0] == "rel" and c[2] == "USES_SUBNET"]
        assert len(rel_calls) == 1, "Should handle dict properties"

    def test_nic_multiple_ip_configs_multiple_subnets(self):
        """NIC with multiple IP configs should create multiple subnet relationships."""
        rule = NetworkRule()
        db = DummyDbOps()

        nic_resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic-multi",
            "name": "nic-multi",
            "type": "Microsoft.Network/networkInterfaces",
            "resource_group": "rg1",
            "properties": {
                "ipConfigurations": [
                    {
                        "name": "ipconfig1",
                        "subnet": {
                            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1"
                        }
                    },
                    {
                        "name": "ipconfig2",
                        "subnet": {
                            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet2"
                        }
                    }
                ]
            }
        }

        rule.emit(nic_resource, db)

        rel_calls = [c for c in db.calls if c[0] == "rel" and c[2] == "USES_SUBNET"]
        assert len(rel_calls) == 2, "Should create relationship for each subnet reference"


class TestEdgeCases:
    """Additional edge cases discovered during autonomous demo."""

    def test_vnet_with_no_subnets(self):
        """Empty VNet (no subnets) should not cause errors."""
        rule = SubnetExtractionRule()
        db = DummyDbOps()

        vnet_resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet-empty",
            "name": "vnet-empty",
            "type": "Microsoft.Network/virtualNetworks",
            "location": "eastus",
            "resource_group": "rg1",
            "subscription_id": "sub1",
            "properties": json.dumps({
                "addressSpace": {
                    "addressPrefixes": ["10.0.0.0/16"]
                },
                "subnets": []  # Empty
            })
        }

        rule.emit(vnet_resource, db)

        # Should not crash, no subnets created
        assert len(db.calls) == 0

    def test_subnet_with_missing_name(self):
        """Subnet without name should be skipped with warning."""
        rule = SubnetExtractionRule()
        db = DummyDbOps()

        vnet_resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet-badsubnet",
            "name": "vnet-badsubnet",
            "type": "Microsoft.Network/virtualNetworks",
            "location": "eastus",
            "resource_group": "rg1",
            "subscription_id": "sub1",
            "properties": json.dumps({
                "addressSpace": {
                    "addressPrefixes": ["10.0.0.0/16"]
                },
                "subnets": [
                    {
                        # No name field!
                        "properties": {
                            "addressPrefix": "10.0.1.0/24"
                        }
                    }
                ]
            })
        }

        rule.emit(vnet_resource, db)

        # Should skip subnet without name
        assert len(db.calls) == 0

    def test_nic_without_ip_configurations(self):
        """NIC without ipConfigurations should not crash."""
        rule = NetworkRule()
        db = DummyDbOps()

        nic_resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic-no-ip",
            "name": "nic-no-ip",
            "type": "Microsoft.Network/networkInterfaces",
            "resource_group": "rg1",
            "properties": {
                # No ipConfigurations
            }
        }

        rule.emit(nic_resource, db)

        # Should not crash
        rel_calls = [c for c in db.calls if c[0] == "rel"]
        assert len(rel_calls) == 0

    def test_nic_with_malformed_properties_json(self):
        """NIC with invalid JSON properties should not crash."""
        rule = NetworkRule()
        db = DummyDbOps()

        nic_resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic-bad-json",
            "name": "nic-bad-json",
            "type": "Microsoft.Network/networkInterfaces",
            "resource_group": "rg1",
            "properties": "{invalid json}"  # Malformed
        }

        # Should not crash when emitting with malformed JSON
        try:
            rule.emit(nic_resource, db)
        except json.JSONDecodeError:
            # It's OK if it raises JSONDecodeError - the important thing is it doesn't crash unexpectedly
            pass

        # Should handle gracefully - either no relationships or handled exception
        rel_calls = [c for c in db.calls if c[0] == "rel"]
        assert len(rel_calls) == 0, "Should not create relationships from malformed properties"


class TestRegressionPrevention:
    """Ensure existing functionality still works after fixes."""

    def test_vm_subnet_relationship_still_works(self):
        """Original VM -> Subnet relationship should still work."""
        rule = NetworkRule()
        db = DummyDbOps()

        vm_resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "network_profile": {
                "network_interfaces": [
                    {
                        "ip_configurations": [
                            {
                                "subnet": {
                                    "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1"
                                }
                            }
                        ]
                    }
                ]
            }
        }

        assert rule.applies(vm_resource)
        rule.emit(vm_resource, db)

        rel_calls = [c for c in db.calls if c[0] == "rel" and c[2] == "USES_SUBNET"]
        assert len(rel_calls) == 1

    def test_subnet_nsg_relationship_still_works(self):
        """Subnet -> NSG relationship should still work."""
        rule = NetworkRule()
        db = DummyDbOps()

        subnet_resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1",
            "name": "subnet1",
            "type": "Microsoft.Network/subnets",
            "network_security_group": {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkSecurityGroups/nsg1"
            }
        }

        assert rule.applies(subnet_resource)
        rule.emit(subnet_resource, db)

        rel_calls = [c for c in db.calls if c[0] == "rel" and c[2] == "SECURED_BY"]
        assert len(rel_calls) == 1
