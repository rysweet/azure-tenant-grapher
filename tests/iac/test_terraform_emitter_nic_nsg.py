"""Test Network Interface (NIC) with Network Security Group (NSG) support in Terraform emitter."""

import json
from pathlib import Path

from src.iac.emitters.terraform_emitter import TerraformEmitter
from src.iac.traverser import TenantGraph


class TestNicWithNsg:
    """Test NIC support with NSG attachment."""

    def test_nic_without_nsg(self, tmp_path: Path):
        """Test that NIC without NSG is emitted correctly (baseline)."""
        graph = TenantGraph(
            resources=[
                # VNet
                {
                    "type": "Microsoft.Network/virtualNetworks",
                    "name": "test-vnet",
                    "location": "eastus",
                    "resourceGroup": "test-rg",
                    "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet",
                    "properties": json.dumps(
                        {"addressSpace": {"addressPrefixes": ["10.0.0.0/16"]}}
                    ),
                },
                # Subnet
                {
                    "type": "Microsoft.Network/subnets",
                    "name": "test-subnet",
                    "resourceGroup": "test-rg",
                    "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/test-subnet",
                    "properties": json.dumps({"addressPrefix": "10.0.1.0/24"}),
                },
                # NIC without NSG
                {
                    "type": "Microsoft.Network/networkInterfaces",
                    "name": "test-nic",
                    "location": "eastus",
                    "resourceGroup": "test-rg",
                    "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/networkInterfaces/test-nic",
                    "properties": json.dumps(
                        {
                            "ipConfigurations": [
                                {
                                    "name": "internal",
                                    "properties": {
                                        "subnet": {
                                            "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/test-subnet"
                                        },
                                        "privateIPAllocationMethod": "Dynamic",
                                    },
                                }
                            ]
                        }
                    ),
                },
            ]
        )

        emitter = TerraformEmitter()
        output_files = emitter.emit(graph, tmp_path)

        # Read generated config
        with open(output_files[0]) as f:
            config = json.load(f)

        # NIC should be in the output
        assert "azurerm_network_interface" in config["resource"]
        assert "test_nic" in config["resource"]["azurerm_network_interface"]

        nic_config = config["resource"]["azurerm_network_interface"]["test_nic"]

        # Should have ip_configuration
        assert "ip_configuration" in nic_config
        assert nic_config["ip_configuration"]["subnet_id"] == (
            "${azurerm_subnet.test_vnet_test_subnet.id}"
        )

        # Should NOT have network_security_group_id
        assert "network_security_group_id" not in nic_config

    def test_nic_with_nsg(self, tmp_path: Path):
        """Test that NIC with NSG is emitted correctly with NSG reference."""
        graph = TenantGraph(
            resources=[
                # VNet
                {
                    "type": "Microsoft.Network/virtualNetworks",
                    "name": "test-vnet",
                    "location": "eastus",
                    "resourceGroup": "test-rg",
                    "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet",
                    "properties": json.dumps(
                        {"addressSpace": {"addressPrefixes": ["10.0.0.0/16"]}}
                    ),
                },
                # Subnet
                {
                    "type": "Microsoft.Network/subnets",
                    "name": "test-subnet",
                    "resourceGroup": "test-rg",
                    "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/test-subnet",
                    "properties": json.dumps({"addressPrefix": "10.0.1.0/24"}),
                },
                # NSG
                {
                    "type": "Microsoft.Network/networkSecurityGroups",
                    "name": "test-nsg",
                    "location": "eastus",
                    "resourceGroup": "test-rg",
                    "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/networkSecurityGroups/test-nsg",
                    "properties": json.dumps({}),
                },
                # NIC with NSG attached
                {
                    "type": "Microsoft.Network/networkInterfaces",
                    "name": "test-nic",
                    "location": "eastus",
                    "resourceGroup": "test-rg",
                    "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/networkInterfaces/test-nic",
                    "properties": json.dumps(
                        {
                            "ipConfigurations": [
                                {
                                    "name": "internal",
                                    "properties": {
                                        "subnet": {
                                            "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/test-subnet"
                                        },
                                        "privateIPAllocationMethod": "Dynamic",
                                    },
                                }
                            ],
                            "networkSecurityGroup": {
                                "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/networkSecurityGroups/test-nsg"
                            },
                        }
                    ),
                },
            ]
        )

        emitter = TerraformEmitter()
        output_files = emitter.emit(graph, tmp_path)

        # Read generated config
        with open(output_files[0]) as f:
            config = json.load(f)

        # NIC should be in the output
        assert "azurerm_network_interface" in config["resource"]
        assert "test_nic" in config["resource"]["azurerm_network_interface"]

        # NSG should be in the output
        assert "azurerm_network_security_group" in config["resource"]
        assert "test_nsg" in config["resource"]["azurerm_network_security_group"]

        nic_config = config["resource"]["azurerm_network_interface"]["test_nic"]

        # Should have ip_configuration
        assert "ip_configuration" in nic_config
        assert nic_config["ip_configuration"]["subnet_id"] == (
            "${azurerm_subnet.test_vnet_test_subnet.id}"
        )

        # Should have network_security_group_id referencing the NSG
        assert "network_security_group_id" in nic_config
        assert nic_config["network_security_group_id"] == (
            "${azurerm_network_security_group.test_nsg.id}"
        )

    def test_nic_with_nsg_sanitized_name(self, tmp_path: Path):
        """Test that NIC with NSG handles name sanitization correctly."""
        graph = TenantGraph(
            resources=[
                # VNet
                {
                    "type": "Microsoft.Network/virtualNetworks",
                    "name": "test-vnet",
                    "location": "eastus",
                    "resourceGroup": "test-rg",
                    "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet",
                    "properties": json.dumps(
                        {"addressSpace": {"addressPrefixes": ["10.0.0.0/16"]}}
                    ),
                },
                # Subnet
                {
                    "type": "Microsoft.Network/subnets",
                    "name": "test-subnet",
                    "resourceGroup": "test-rg",
                    "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/test-subnet",
                    "properties": json.dumps({"addressPrefix": "10.0.1.0/24"}),
                },
                # NSG with special characters in name
                {
                    "type": "Microsoft.Network/networkSecurityGroups",
                    "name": "test-nsg-web_001",
                    "location": "eastus",
                    "resourceGroup": "test-rg",
                    "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/networkSecurityGroups/test-nsg-web_001",
                    "properties": json.dumps({}),
                },
                # NIC with NSG attached
                {
                    "type": "Microsoft.Network/networkInterfaces",
                    "name": "test-nic-001",
                    "location": "eastus",
                    "resourceGroup": "test-rg",
                    "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/networkInterfaces/test-nic-001",
                    "properties": json.dumps(
                        {
                            "ipConfigurations": [
                                {
                                    "name": "internal",
                                    "properties": {
                                        "subnet": {
                                            "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/test-subnet"
                                        },
                                        "privateIPAllocationMethod": "Dynamic",
                                    },
                                }
                            ],
                            "networkSecurityGroup": {
                                "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/networkSecurityGroups/test-nsg-web_001"
                            },
                        }
                    ),
                },
            ]
        )

        emitter = TerraformEmitter()
        output_files = emitter.emit(graph, tmp_path)

        # Read generated config
        with open(output_files[0]) as f:
            config = json.load(f)

        # NIC should be in the output
        assert "azurerm_network_interface" in config["resource"]
        assert "test_nic_001" in config["resource"]["azurerm_network_interface"]

        # NSG should be in the output
        assert "azurerm_network_security_group" in config["resource"]
        assert (
            "test_nsg_web_001" in config["resource"]["azurerm_network_security_group"]
        )

        nic_config = config["resource"]["azurerm_network_interface"]["test_nic_001"]

        # Should have network_security_group_id with sanitized name
        assert "network_security_group_id" in nic_config
        assert nic_config["network_security_group_id"] == (
            "${azurerm_network_security_group.test_nsg_web_001.id}"
        )

    def test_nic_with_missing_nsg(self, tmp_path: Path):
        """Test that NIC referencing missing NSG still includes the reference.

        Note: This will create a Terraform reference to a non-existent resource.
        This is expected behavior - the reference is preserved to help users
        understand what's missing. Terraform validation will catch this error.
        """
        graph = TenantGraph(
            resources=[
                # VNet
                {
                    "type": "Microsoft.Network/virtualNetworks",
                    "name": "test-vnet",
                    "location": "eastus",
                    "resourceGroup": "test-rg",
                    "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet",
                    "properties": json.dumps(
                        {"addressSpace": {"addressPrefixes": ["10.0.0.0/16"]}}
                    ),
                },
                # Subnet
                {
                    "type": "Microsoft.Network/subnets",
                    "name": "test-subnet",
                    "resourceGroup": "test-rg",
                    "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/test-subnet",
                    "properties": json.dumps({"addressPrefix": "10.0.1.0/24"}),
                },
                # NIC with NSG reference but NSG doesn't exist in graph
                {
                    "type": "Microsoft.Network/networkInterfaces",
                    "name": "test-nic",
                    "location": "eastus",
                    "resourceGroup": "test-rg",
                    "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/networkInterfaces/test-nic",
                    "properties": json.dumps(
                        {
                            "ipConfigurations": [
                                {
                                    "name": "internal",
                                    "properties": {
                                        "subnet": {
                                            "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/test-subnet"
                                        },
                                        "privateIPAllocationMethod": "Dynamic",
                                    },
                                }
                            ],
                            "networkSecurityGroup": {
                                "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/networkSecurityGroups/missing-nsg"
                            },
                        }
                    ),
                },
            ]
        )

        emitter = TerraformEmitter()
        output_files = emitter.emit(graph, tmp_path)

        # Read generated config
        with open(output_files[0]) as f:
            config = json.load(f)

        # NIC should still be in the output
        assert "azurerm_network_interface" in config["resource"]
        assert "test_nic" in config["resource"]["azurerm_network_interface"]

        nic_config = config["resource"]["azurerm_network_interface"]["test_nic"]

        # Should have ip_configuration
        assert "ip_configuration" in nic_config

        # Should have network_security_group_id (even though NSG is missing)
        # This preserves the reference and will be caught by Terraform validation
        assert "network_security_group_id" in nic_config
        assert nic_config["network_security_group_id"] == (
            "${azurerm_network_security_group.missing_nsg.id}"
        )

    def test_multiple_nics_with_same_nsg(self, tmp_path: Path):
        """Test that multiple NICs can reference the same NSG."""
        graph = TenantGraph(
            resources=[
                # VNet
                {
                    "type": "Microsoft.Network/virtualNetworks",
                    "name": "test-vnet",
                    "location": "eastus",
                    "resourceGroup": "test-rg",
                    "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet",
                    "properties": json.dumps(
                        {"addressSpace": {"addressPrefixes": ["10.0.0.0/16"]}}
                    ),
                },
                # Subnet
                {
                    "type": "Microsoft.Network/subnets",
                    "name": "test-subnet",
                    "resourceGroup": "test-rg",
                    "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/test-subnet",
                    "properties": json.dumps({"addressPrefix": "10.0.1.0/24"}),
                },
                # NSG
                {
                    "type": "Microsoft.Network/networkSecurityGroups",
                    "name": "shared-nsg",
                    "location": "eastus",
                    "resourceGroup": "test-rg",
                    "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/networkSecurityGroups/shared-nsg",
                    "properties": json.dumps({}),
                },
                # First NIC with NSG
                {
                    "type": "Microsoft.Network/networkInterfaces",
                    "name": "nic-01",
                    "location": "eastus",
                    "resourceGroup": "test-rg",
                    "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/networkInterfaces/nic-01",
                    "properties": json.dumps(
                        {
                            "ipConfigurations": [
                                {
                                    "name": "internal",
                                    "properties": {
                                        "subnet": {
                                            "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/test-subnet"
                                        },
                                        "privateIPAllocationMethod": "Dynamic",
                                    },
                                }
                            ],
                            "networkSecurityGroup": {
                                "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/networkSecurityGroups/shared-nsg"
                            },
                        }
                    ),
                },
                # Second NIC with same NSG
                {
                    "type": "Microsoft.Network/networkInterfaces",
                    "name": "nic-02",
                    "location": "eastus",
                    "resourceGroup": "test-rg",
                    "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/networkInterfaces/nic-02",
                    "properties": json.dumps(
                        {
                            "ipConfigurations": [
                                {
                                    "name": "internal",
                                    "properties": {
                                        "subnet": {
                                            "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/test-subnet"
                                        },
                                        "privateIPAllocationMethod": "Dynamic",
                                    },
                                }
                            ],
                            "networkSecurityGroup": {
                                "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/networkSecurityGroups/shared-nsg"
                            },
                        }
                    ),
                },
            ]
        )

        emitter = TerraformEmitter()
        output_files = emitter.emit(graph, tmp_path)

        # Read generated config
        with open(output_files[0]) as f:
            config = json.load(f)

        # Both NICs should be in the output
        assert "azurerm_network_interface" in config["resource"]
        assert "nic_01" in config["resource"]["azurerm_network_interface"]
        assert "nic_02" in config["resource"]["azurerm_network_interface"]

        # NSG should be in the output (only once)
        assert "azurerm_network_security_group" in config["resource"]
        assert "shared_nsg" in config["resource"]["azurerm_network_security_group"]

        # Both NICs should reference the same NSG
        nic1_config = config["resource"]["azurerm_network_interface"]["nic_01"]
        nic2_config = config["resource"]["azurerm_network_interface"]["nic_02"]

        assert "network_security_group_id" in nic1_config
        assert "network_security_group_id" in nic2_config

        assert nic1_config["network_security_group_id"] == (
            "${azurerm_network_security_group.shared_nsg.id}"
        )
        assert nic2_config["network_security_group_id"] == (
            "${azurerm_network_security_group.shared_nsg.id}"
        )
