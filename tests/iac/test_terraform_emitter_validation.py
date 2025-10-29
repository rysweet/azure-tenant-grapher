"""Tests for Terraform emitter resource reference validation.

Tests for Issue #WORKSTREAM_F - Missing Network Interface Bug
"""

import json
from pathlib import Path

from src.iac.emitters.terraform_emitter import TerraformEmitter
from src.iac.traverser import TenantGraph


class TestTerraformEmitterValidation:
    """Test resource reference validation in Terraform emitter."""

    def test_vm_with_missing_nic_is_filtered_out(self, tmp_path: Path):
        """Test that VMs referencing missing NICs are filtered out."""
        # Create a VM that references a NIC that doesn't exist
        graph = TenantGraph(
            resources=[
                {
                    "type": "Microsoft.Compute/virtualMachines",
                    "name": "test-vm",
                    "location": "eastus",
                    "resourceGroup": "test-rg",
                    "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm",
                    "properties": json.dumps(
                        {
                            "networkProfile": {
                                "networkInterfaces": [
                                    {
                                        "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/networkInterfaces/missing-nic"
                                    }
                                ]
                            }
                        }
                    ),
                }
            ]
        )

        emitter = TerraformEmitter()
        output_files = emitter.emit(graph, tmp_path)

        # Read generated config
        with open(output_files[0]) as f:
            config = json.load(f)

        # VM should NOT be in the output since its NIC is missing
        assert "azurerm_linux_virtual_machine" not in config.get("resource", {})

    def test_vm_with_existing_nic_is_included(self, tmp_path: Path):
        """Test that VMs with valid NIC references are included."""
        graph = TenantGraph(
            resources=[
                # First add the NIC
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
                # Then add the VM that references it
                {
                    "type": "Microsoft.Compute/virtualMachines",
                    "name": "test-vm",
                    "location": "eastus",
                    "resourceGroup": "test-rg",
                    "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm",
                    "properties": json.dumps(
                        {
                            "networkProfile": {
                                "networkInterfaces": [
                                    {
                                        "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/networkInterfaces/test-nic"
                                    }
                                ]
                            }
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

        # VM should be in the output
        assert "azurerm_linux_virtual_machine" in config["resource"]
        assert "test_vm" in config["resource"]["azurerm_linux_virtual_machine"]

        # NIC should be in the output
        assert "azurerm_network_interface" in config["resource"]
        assert "test_nic" in config["resource"]["azurerm_network_interface"]

        # VM should reference the NIC correctly
        vm = config["resource"]["azurerm_linux_virtual_machine"]["test_vm"]
        assert "network_interface_ids" in vm
        assert len(vm["network_interface_ids"]) == 1
        assert "${azurerm_network_interface.test_nic.id}" in vm["network_interface_ids"]

    def test_vm_with_multiple_nics_some_missing(self, tmp_path: Path):
        """Test VM with multiple NICs where some are missing."""
        graph = TenantGraph(
            resources=[
                # Only one of the two NICs exists
                {
                    "type": "Microsoft.Network/networkInterfaces",
                    "name": "existing-nic",
                    "location": "eastus",
                    "resourceGroup": "test-rg",
                    "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/networkInterfaces/existing-nic",
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
                # VM references both existing and missing NIC
                {
                    "type": "Microsoft.Compute/virtualMachines",
                    "name": "test-vm",
                    "location": "eastus",
                    "resourceGroup": "test-rg",
                    "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm",
                    "properties": json.dumps(
                        {
                            "networkProfile": {
                                "networkInterfaces": [
                                    {
                                        "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/networkInterfaces/existing-nic"
                                    },
                                    {
                                        "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/networkInterfaces/missing-nic"
                                    },
                                ]
                            }
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

        # VM should still be included (has at least one valid NIC)
        assert "azurerm_linux_virtual_machine" in config["resource"]
        assert "test_vm" in config["resource"]["azurerm_linux_virtual_machine"]

        # VM should only reference the existing NIC
        vm = config["resource"]["azurerm_linux_virtual_machine"]["test_vm"]
        assert "network_interface_ids" in vm
        assert len(vm["network_interface_ids"]) == 1
        assert (
            "${azurerm_network_interface.existing_nic.id}"
            in vm["network_interface_ids"]
        )
        # Should NOT reference the missing NIC
        assert (
            "${azurerm_network_interface.missing_nic.id}"
            not in vm["network_interface_ids"]
        )

    def test_missing_references_are_tracked(self, tmp_path: Path):
        """Test that missing references are tracked for reporting."""
        graph = TenantGraph(
            resources=[
                {
                    "type": "Microsoft.Compute/virtualMachines",
                    "name": "test-vm",
                    "location": "eastus",
                    "resourceGroup": "test-rg",
                    "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm",
                    "properties": json.dumps(
                        {
                            "networkProfile": {
                                "networkInterfaces": [
                                    {
                                        "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/networkInterfaces/missing-nic"
                                    }
                                ]
                            }
                        }
                    ),
                }
            ]
        )

        emitter = TerraformEmitter()
        emitter.emit(graph, tmp_path)

        # Check that missing reference was tracked
        assert len(emitter._missing_references) == 1
        ref = emitter._missing_references[0]
        assert ref["vm_name"] == "test-vm"
        assert ref["resource_type"] == "network_interface"
        assert ref["missing_resource_name"] == "missing-nic"
        assert "missing-nic" in ref["missing_resource_id"]

    def test_cross_resource_group_nic_reference(self, tmp_path: Path):
        """Test VM referencing NIC in different resource group (Issue WORKSTREAM_F)."""
        # This is the actual scenario from csiska-01 VM
        graph = TenantGraph(
            resources=[
                {
                    "type": "Microsoft.Compute/virtualMachines",
                    "name": "csiska-01",
                    "location": "eastus",
                    "resourceGroup": "sparta_attackbot",
                    "id": "/subscriptions/test/resourceGroups/sparta_attackbot/providers/Microsoft.Compute/virtualMachines/csiska-01",
                    "properties": json.dumps(
                        {
                            "networkProfile": {
                                "networkInterfaces": [
                                    {
                                        # NIC is in a DIFFERENT resource group
                                        "id": "/subscriptions/test/resourceGroups/Ballista_UCAScenario/providers/Microsoft.Network/networkInterfaces/csiska-01654"
                                    }
                                ]
                            }
                        }
                    ),
                }
            ]
        )

        emitter = TerraformEmitter()
        output_files = emitter.emit(graph, tmp_path)

        # Read generated config
        with open(output_files[0]) as f:
            config = json.load(f)

        # VM should be filtered out (NIC not in graph)
        assert "azurerm_linux_virtual_machine" not in config.get("resource", {})

        # Missing reference should be tracked with cross-RG details
        assert len(emitter._missing_references) == 1
        ref = emitter._missing_references[0]
        assert ref["vm_name"] == "csiska-01"
        assert "Ballista_UCAScenario" in ref["missing_resource_id"]
        assert "sparta_attackbot" in ref["vm_id"]
