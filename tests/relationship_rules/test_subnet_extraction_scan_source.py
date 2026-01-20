"""
Test that SubnetExtractionRule properly includes scan_id and tenant_id
for SCAN_SOURCE_NODE relationship creation (Issue #565).
"""

import json
from unittest.mock import MagicMock

import pytest

from src.relationship_rules.subnet_extraction_rule import SubnetExtractionRule


class TestSubnetExtractionScanSource:
    """Test SubnetExtractionRule includes scan_id and tenant_id (Issue #565 fix)."""

    @pytest.fixture
    def rule(self):
        """Create SubnetExtractionRule instance."""
        return SubnetExtractionRule(enable_dual_graph=True)

    @pytest.fixture
    def mock_db_ops(self):
        """Create mock database operations."""
        db_ops = MagicMock()
        db_ops.upsert_resource = MagicMock(return_value=True)
        return db_ops

    @pytest.fixture
    def vnet_with_subnets(self):
        """Create a VNet resource with subnets including scan_id and tenant_id."""
        return {
            "id": "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Network/virtualNetworks/vnet-test",
            "name": "vnet-test",
            "type": "Microsoft.Network/virtualNetworks",
            "location": "eastus",
            "resource_group": "rg-test",
            "subscription_id": "sub-123",
            "scan_id": "scan-abc-123",  # Critical for SCAN_SOURCE_NODE
            "tenant_id": "tenant-xyz-456",  # Critical for SCAN_SOURCE_NODE
            "properties": json.dumps(
                {
                    "addressSpace": {"addressPrefixes": ["10.0.0.0/16"]},
                    "subnets": [
                        {
                            "name": "subnet-1",
                            "properties": {
                                "addressPrefix": "10.0.1.0/24",
                                "networkSecurityGroup": {
                                    "id": "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Network/networkSecurityGroups/nsg-1"
                                },
                            },
                        },
                        {
                            "name": "subnet-2",
                            "properties": {"addressPrefix": "10.0.2.0/24"},
                        },
                    ],
                }
            ),
        }

    def test_subnet_resource_includes_scan_id_and_tenant_id(
        self, rule, vnet_with_subnets
    ):
        """Test that _build_subnet_resource includes scan_id and tenant_id from parent VNet."""
        # Extract first subnet
        properties = json.loads(vnet_with_subnets["properties"])
        subnet_data = properties["subnets"][0]

        # Build subnet resource
        subnet_resource = rule._build_subnet_resource(vnet_with_subnets, subnet_data)

        # Verify scan_id and tenant_id are copied from parent VNet
        assert subnet_resource is not None
        assert subnet_resource["scan_id"] == "scan-abc-123", (
            "scan_id must be copied from parent VNet"
        )
        assert subnet_resource["tenant_id"] == "tenant-xyz-456", (
            "tenant_id must be copied from parent VNet"
        )

    def test_all_subnets_get_scan_id_and_tenant_id(
        self, rule, vnet_with_subnets, mock_db_ops
    ):
        """Test that emit() creates all subnet resources with scan_id and tenant_id."""
        # Emit subnets
        rule.emit(vnet_with_subnets, mock_db_ops)

        # Verify upsert_resource was called for each subnet
        assert mock_db_ops.upsert_resource.call_count == 2, (
            "Should create 2 subnet resources"
        )

        # Verify each subnet resource has scan_id and tenant_id
        for call in mock_db_ops.upsert_resource.call_args_list:
            subnet_resource = call[0][0]  # First positional arg
            assert "scan_id" in subnet_resource, "Subnet resource must include scan_id"
            assert "tenant_id" in subnet_resource, (
                "Subnet resource must include tenant_id"
            )
            assert subnet_resource["scan_id"] == "scan-abc-123", (
                "scan_id must match parent VNet"
            )
            assert subnet_resource["tenant_id"] == "tenant-xyz-456", (
                "tenant_id must match parent VNet"
            )

    def test_subnet_without_parent_scan_id_has_none(self, rule):
        """Test that subnets get None for scan_id/tenant_id if parent VNet doesn't have them."""
        vnet_no_scan = {
            "id": "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Network/virtualNetworks/vnet-test",
            "name": "vnet-test",
            "type": "Microsoft.Network/virtualNetworks",
            "location": "eastus",
            "resource_group": "rg-test",
            "subscription_id": "sub-123",
            # No scan_id or tenant_id
            "properties": json.dumps(
                {
                    "subnets": [
                        {
                            "name": "subnet-1",
                            "properties": {"addressPrefix": "10.0.1.0/24"},
                        }
                    ]
                }
            ),
        }

        properties = json.loads(vnet_no_scan["properties"])
        subnet_data = properties["subnets"][0]

        subnet_resource = rule._build_subnet_resource(vnet_no_scan, subnet_data)

        # scan_id and tenant_id should be None (not missing from dict)
        assert subnet_resource is not None
        assert subnet_resource["scan_id"] is None, (
            "scan_id should be None if parent doesn't have it"
        )
        assert subnet_resource["tenant_id"] is None, (
            "tenant_id should be None if parent doesn't have it"
        )

    def test_subnet_resource_structure_complete(self, rule, vnet_with_subnets):
        """Test that subnet resource has all required fields including new scan_id/tenant_id."""
        properties = json.loads(vnet_with_subnets["properties"])
        subnet_data = properties["subnets"][0]

        subnet_resource = rule._build_subnet_resource(vnet_with_subnets, subnet_data)

        # Verify all required fields
        required_fields = [
            "id",
            "name",
            "type",
            "location",
            "resource_group",
            "subscription_id",
            "parent_id",
            "properties",
            "scan_id",  # NEW: Required for SCAN_SOURCE_NODE
            "tenant_id",  # NEW: Required for SCAN_SOURCE_NODE
        ]

        for field in required_fields:
            assert field in subnet_resource, f"Subnet resource must include {field}"

        # Verify field values
        assert (
            subnet_resource["id"]
            == "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Network/virtualNetworks/vnet-test/subnets/subnet-1"
        )
        assert subnet_resource["name"] == "subnet-1"
        assert subnet_resource["type"] == "Microsoft.Network/subnets"
        assert subnet_resource["location"] == "eastus"
        assert subnet_resource["resource_group"] == "rg-test"
        assert subnet_resource["subscription_id"] == "sub-123"
        assert subnet_resource["parent_id"] == vnet_with_subnets["id"]
        assert subnet_resource["scan_id"] == "scan-abc-123"
        assert subnet_resource["tenant_id"] == "tenant-xyz-456"
