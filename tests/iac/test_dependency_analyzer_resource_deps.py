"""
Tests for Resource Dependency Extraction in DependencyAnalyzer (TODO #6).

Tests cover:
- VNet -> Subnet dependency extraction
- Subnet -> NIC dependency extraction
- NIC -> VM dependency extraction
- Storage Account -> VM diagnostics dependency extraction
- Edge cases (missing properties, malformed IDs, multiple references)
"""

import pytest

from src.iac.dependency_analyzer import DependencyAnalyzer


class TestVNetSubnetDependencies:
    """Tests for VNet -> Subnet dependency extraction."""

    def test_extract_vnet_from_subnet_with_valid_id(self):
        """Test extracting VNet dependency from subnet with valid resource ID."""
        analyzer = DependencyAnalyzer()

        resource = {
            "name": "subnet1",
            "type": "Microsoft.Network/subnets",
            "resource_group": "rg-network",
            "id": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1",
        }

        dependencies = analyzer._extract_dependencies(resource)

        # Should have RG + VNet dependencies
        assert len(dependencies) >= 2
        assert "azurerm_resource_group.rg_network" in dependencies
        assert "azurerm_virtual_network.vnet1" in dependencies

    def test_extract_vnet_from_subnet_with_hyphenated_name(self):
        """Test VNet extraction with hyphenated names (sanitization)."""
        analyzer = DependencyAnalyzer()

        resource = {
            "name": "default-subnet",
            "type": "Microsoft.Network/subnets",
            "resource_group": "rg-network",
            "id": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/virtualNetworks/my-vnet-prod/subnets/default-subnet",
        }

        dependencies = analyzer._extract_dependencies(resource)

        # VNet name should be sanitized (hyphens to underscores)
        assert "azurerm_virtual_network.my_vnet_prod" in dependencies

    def test_extract_vnet_from_subnet_with_no_id(self):
        """Test subnet without resource ID (should not crash)."""
        analyzer = DependencyAnalyzer()

        resource = {
            "name": "subnet1",
            "type": "Microsoft.Network/subnets",
            "resource_group": "rg-network",
            # No 'id' field
        }

        dependencies = analyzer._extract_dependencies(resource)

        # Should only have RG dependency
        assert "azurerm_resource_group.rg_network" in dependencies
        # Should not have VNet dependency
        vnet_deps = [d for d in dependencies if "virtual_network" in d]
        assert len(vnet_deps) == 0

    def test_extract_vnet_from_subnet_with_malformed_id(self):
        """Test subnet with malformed resource ID."""
        analyzer = DependencyAnalyzer()

        resource = {
            "name": "subnet1",
            "type": "Microsoft.Network/subnets",
            "resource_group": "rg-network",
            "id": "/invalid/resource/id/format",
        }

        dependencies = analyzer._extract_dependencies(resource)

        # Should only have RG dependency
        assert "azurerm_resource_group.rg_network" in dependencies
        # Should not crash and should not have VNet dependency
        vnet_deps = [d for d in dependencies if "virtual_network" in d]
        assert len(vnet_deps) == 0

    def test_extract_vnet_from_subnet_with_fallback_properties(self):
        """Test VNet extraction from properties field as fallback."""
        analyzer = DependencyAnalyzer()

        resource = {
            "name": "subnet1",
            "type": "Microsoft.Network/subnets",
            "resource_group": "rg-network",
            "properties": {
                "virtualNetwork": {
                    "id": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/virtualNetworks/vnet-fallback"
                }
            },
        }

        dependencies = analyzer._extract_dependencies(resource)

        assert "azurerm_virtual_network.vnet_fallback" in dependencies


class TestSubnetNICDependencies:
    """Tests for Subnet -> NIC dependency extraction."""

    def test_extract_subnet_from_nic_with_single_ip_config(self):
        """Test extracting subnet dependency from NIC with single IP configuration."""
        analyzer = DependencyAnalyzer()

        resource = {
            "name": "nic1",
            "type": "Microsoft.Network/networkInterfaces",
            "resource_group": "rg-compute",
            "properties": {
                "ipConfigurations": [
                    {
                        "subnet": {
                            "id": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1"
                        }
                    }
                ]
            },
        }

        dependencies = analyzer._extract_dependencies(resource)

        assert "azurerm_resource_group.rg_compute" in dependencies
        assert "azurerm_subnet.subnet1" in dependencies

    def test_extract_subnet_from_nic_with_multiple_ip_configs(self):
        """Test NIC with multiple IP configurations (multiple subnets)."""
        analyzer = DependencyAnalyzer()

        resource = {
            "name": "nic-multi",
            "type": "Microsoft.Network/networkInterfaces",
            "resource_group": "rg-compute",
            "properties": {
                "ipConfigurations": [
                    {
                        "subnet": {
                            "id": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1"
                        }
                    },
                    {
                        "subnet": {
                            "id": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet2"
                        }
                    },
                ]
            },
        }

        dependencies = analyzer._extract_dependencies(resource)

        assert "azurerm_subnet.subnet1" in dependencies
        assert "azurerm_subnet.subnet2" in dependencies

    def test_extract_subnet_from_nic_with_no_ip_configs(self):
        """Test NIC with no IP configurations (edge case)."""
        analyzer = DependencyAnalyzer()

        resource = {
            "name": "nic1",
            "type": "Microsoft.Network/networkInterfaces",
            "resource_group": "rg-compute",
            "properties": {
                # No ipConfigurations field
            },
        }

        dependencies = analyzer._extract_dependencies(resource)

        # Should only have RG dependency
        assert "azurerm_resource_group.rg_compute" in dependencies
        subnet_deps = [d for d in dependencies if "subnet" in d]
        assert len(subnet_deps) == 0

    def test_extract_subnet_from_nic_with_empty_subnet_id(self):
        """Test NIC with empty subnet ID."""
        analyzer = DependencyAnalyzer()

        resource = {
            "name": "nic1",
            "type": "Microsoft.Network/networkInterfaces",
            "resource_group": "rg-compute",
            "properties": {"ipConfigurations": [{"subnet": {"id": ""}}]},
        }

        dependencies = analyzer._extract_dependencies(resource)

        # Should only have RG dependency
        assert "azurerm_resource_group.rg_compute" in dependencies
        subnet_deps = [d for d in dependencies if "subnet" in d]
        assert len(subnet_deps) == 0

    def test_extract_subnet_from_nic_with_hyphenated_subnet_name(self):
        """Test subnet name sanitization for NICs."""
        analyzer = DependencyAnalyzer()

        resource = {
            "name": "nic1",
            "type": "Microsoft.Network/networkInterfaces",
            "resource_group": "rg-compute",
            "properties": {
                "ipConfigurations": [
                    {
                        "subnet": {
                            "id": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/frontend-subnet"
                        }
                    }
                ]
            },
        }

        dependencies = analyzer._extract_dependencies(resource)

        assert "azurerm_subnet.frontend_subnet" in dependencies


class TestNICVMDependencies:
    """Tests for NIC -> VM dependency extraction."""

    def test_extract_nic_from_vm_with_single_nic(self):
        """Test extracting NIC dependency from VM with single NIC."""
        analyzer = DependencyAnalyzer()

        resource = {
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "resource_group": "rg-compute",
            "properties": {
                "networkProfile": {
                    "networkInterfaces": [
                        {
                            "id": "/subscriptions/sub1/resourceGroups/rg-compute/providers/Microsoft.Network/networkInterfaces/nic1"
                        }
                    ]
                }
            },
        }

        dependencies = analyzer._extract_dependencies(resource)

        assert "azurerm_resource_group.rg_compute" in dependencies
        assert "azurerm_network_interface.nic1" in dependencies

    def test_extract_nic_from_vm_with_multiple_nics(self):
        """Test VM with multiple NICs."""
        analyzer = DependencyAnalyzer()

        resource = {
            "name": "vm-multi-nic",
            "type": "Microsoft.Compute/virtualMachines",
            "resource_group": "rg-compute",
            "properties": {
                "networkProfile": {
                    "networkInterfaces": [
                        {
                            "id": "/subscriptions/sub1/resourceGroups/rg-compute/providers/Microsoft.Network/networkInterfaces/nic1"
                        },
                        {
                            "id": "/subscriptions/sub1/resourceGroups/rg-compute/providers/Microsoft.Network/networkInterfaces/nic2"
                        },
                    ]
                }
            },
        }

        dependencies = analyzer._extract_dependencies(resource)

        assert "azurerm_network_interface.nic1" in dependencies
        assert "azurerm_network_interface.nic2" in dependencies

    def test_extract_nic_from_vm_with_no_network_profile(self):
        """Test VM with no network profile (edge case)."""
        analyzer = DependencyAnalyzer()

        resource = {
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "resource_group": "rg-compute",
            "properties": {
                # No networkProfile field
            },
        }

        dependencies = analyzer._extract_dependencies(resource)

        # Should only have RG dependency
        assert "azurerm_resource_group.rg_compute" in dependencies
        nic_deps = [d for d in dependencies if "network_interface" in d]
        assert len(nic_deps) == 0

    def test_extract_nic_from_vm_with_empty_nic_id(self):
        """Test VM with empty NIC ID."""
        analyzer = DependencyAnalyzer()

        resource = {
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "resource_group": "rg-compute",
            "properties": {"networkProfile": {"networkInterfaces": [{"id": ""}]}},
        }

        dependencies = analyzer._extract_dependencies(resource)

        # Should only have RG dependency
        assert "azurerm_resource_group.rg_compute" in dependencies
        nic_deps = [d for d in dependencies if "network_interface" in d]
        assert len(nic_deps) == 0

    def test_extract_nic_from_vm_with_hyphenated_nic_name(self):
        """Test NIC name sanitization for VMs."""
        analyzer = DependencyAnalyzer()

        resource = {
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "resource_group": "rg-compute",
            "properties": {
                "networkProfile": {
                    "networkInterfaces": [
                        {
                            "id": "/subscriptions/sub1/resourceGroups/rg-compute/providers/Microsoft.Network/networkInterfaces/vm1-nic-primary"
                        }
                    ]
                }
            },
        }

        dependencies = analyzer._extract_dependencies(resource)

        assert "azurerm_network_interface.vm1_nic_primary" in dependencies


class TestStorageAccountVMDiagnosticsDependencies:
    """Tests for Storage Account -> VM diagnostics dependency extraction."""

    def test_extract_storage_from_vm_diagnostics_with_valid_uri(self):
        """Test extracting storage account from VM boot diagnostics URI."""
        analyzer = DependencyAnalyzer()

        resource = {
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "resource_group": "rg-compute",
            "properties": {
                "diagnosticsProfile": {
                    "bootDiagnostics": {
                        "storageUri": "https://mystorageaccount.blob.core.windows.net/"
                    }
                }
            },
        }

        dependencies = analyzer._extract_dependencies(resource)

        assert "azurerm_resource_group.rg_compute" in dependencies
        assert "azurerm_storage_account.mystorageaccount" in dependencies

    def test_extract_storage_from_vm_diagnostics_with_hyphenated_name(self):
        """Test storage account name sanitization."""
        analyzer = DependencyAnalyzer()

        resource = {
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "resource_group": "rg-compute",
            "properties": {
                "diagnosticsProfile": {
                    "bootDiagnostics": {
                        "storageUri": "https://my-storage-prod.blob.core.windows.net/"
                    }
                }
            },
        }

        dependencies = analyzer._extract_dependencies(resource)

        assert "azurerm_storage_account.my_storage_prod" in dependencies

    def test_extract_storage_from_vm_diagnostics_with_no_diagnostics_profile(self):
        """Test VM with no diagnostics profile."""
        analyzer = DependencyAnalyzer()

        resource = {
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "resource_group": "rg-compute",
            "properties": {
                # No diagnosticsProfile
            },
        }

        dependencies = analyzer._extract_dependencies(resource)

        # Should only have RG dependency (no storage dependency)
        assert "azurerm_resource_group.rg_compute" in dependencies
        storage_deps = [d for d in dependencies if "storage_account" in d]
        assert len(storage_deps) == 0

    def test_extract_storage_from_vm_diagnostics_with_empty_uri(self):
        """Test VM with empty storage URI."""
        analyzer = DependencyAnalyzer()

        resource = {
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "resource_group": "rg-compute",
            "properties": {
                "diagnosticsProfile": {"bootDiagnostics": {"storageUri": ""}}
            },
        }

        dependencies = analyzer._extract_dependencies(resource)

        # Should only have RG dependency
        assert "azurerm_resource_group.rg_compute" in dependencies
        storage_deps = [d for d in dependencies if "storage_account" in d]
        assert len(storage_deps) == 0

    def test_extract_storage_from_vm_diagnostics_with_malformed_uri(self):
        """Test VM with malformed storage URI (should not crash)."""
        analyzer = DependencyAnalyzer()

        resource = {
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "resource_group": "rg-compute",
            "properties": {
                "diagnosticsProfile": {
                    "bootDiagnostics": {"storageUri": "invalid-uri-format"}
                }
            },
        }

        dependencies = analyzer._extract_dependencies(resource)

        # Should only have RG dependency (malformed URI should be handled gracefully)
        assert "azurerm_resource_group.rg_compute" in dependencies
        # May or may not have storage dependency depending on parsing


class TestCombinedDependencies:
    """Tests for combined dependency scenarios (multiple dependency types)."""

    def test_vm_with_all_dependencies(self):
        """Test VM with NIC and storage account dependencies."""
        analyzer = DependencyAnalyzer()

        resource = {
            "name": "vm-full",
            "type": "Microsoft.Compute/virtualMachines",
            "resource_group": "rg-compute",
            "properties": {
                "networkProfile": {
                    "networkInterfaces": [
                        {
                            "id": "/subscriptions/sub1/resourceGroups/rg-compute/providers/Microsoft.Network/networkInterfaces/nic1"
                        }
                    ]
                },
                "diagnosticsProfile": {
                    "bootDiagnostics": {
                        "storageUri": "https://diagstorage.blob.core.windows.net/"
                    }
                },
            },
        }

        dependencies = analyzer._extract_dependencies(resource)

        assert "azurerm_resource_group.rg_compute" in dependencies
        assert "azurerm_network_interface.nic1" in dependencies
        assert "azurerm_storage_account.diagstorage" in dependencies

    def test_full_dependency_chain(self):
        """Test full dependency chain: Storage -> RG, VNet -> RG, Subnet -> VNet, NIC -> Subnet, VM -> NIC + Storage."""
        analyzer = DependencyAnalyzer()

        resources = [
            {
                "name": "rg-network",
                "type": "Microsoft.Resources/resourceGroups",
            },
            {
                "name": "vnet1",
                "type": "Microsoft.Network/virtualNetworks",
                "resource_group": "rg-network",
            },
            {
                "name": "subnet1",
                "type": "Microsoft.Network/subnets",
                "resource_group": "rg-network",
                "id": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1",
            },
            {
                "name": "nic1",
                "type": "Microsoft.Network/networkInterfaces",
                "resource_group": "rg-network",
                "properties": {
                    "ipConfigurations": [
                        {
                            "subnet": {
                                "id": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1"
                            }
                        }
                    ]
                },
            },
            {
                "name": "storage1",
                "type": "Microsoft.Storage/storageAccounts",
                "resource_group": "rg-network",
            },
            {
                "name": "vm1",
                "type": "Microsoft.Compute/virtualMachines",
                "resource_group": "rg-network",
                "properties": {
                    "networkProfile": {
                        "networkInterfaces": [
                            {
                                "id": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic1"
                            }
                        ]
                    },
                    "diagnosticsProfile": {
                        "bootDiagnostics": {
                            "storageUri": "https://storage1.blob.core.windows.net/"
                        }
                    },
                },
            },
        ]

        # Analyze all resources
        result = analyzer.analyze(resources)

        # Verify dependency chain
        # Find each resource in result
        rg = next(r for r in result if r.resource["name"] == "rg-network")
        vnet = next(r for r in result if r.resource["name"] == "vnet1")
        subnet = next(r for r in result if r.resource["name"] == "subnet1")
        nic = next(r for r in result if r.resource["name"] == "nic1")
        storage = next(r for r in result if r.resource["name"] == "storage1")
        vm = next(r for r in result if r.resource["name"] == "vm1")

        # Verify tier ordering
        assert rg.tier == 0  # Resource groups first
        assert vnet.tier == 1  # VNets in tier 1
        assert subnet.tier == 2  # Subnets in tier 2
        assert storage.tier == 3  # Storage in tier 3
        assert nic.tier == 4  # NICs in tier 4
        assert vm.tier == 5  # VMs in tier 5

        # Verify dependency relationships
        assert "azurerm_resource_group.rg_network" in vnet.depends_on
        assert "azurerm_resource_group.rg_network" in subnet.depends_on
        assert "azurerm_virtual_network.vnet1" in subnet.depends_on
        assert "azurerm_resource_group.rg_network" in nic.depends_on
        assert "azurerm_subnet.subnet1" in nic.depends_on
        assert "azurerm_resource_group.rg_network" in storage.depends_on
        assert "azurerm_resource_group.rg_network" in vm.depends_on
        assert "azurerm_network_interface.nic1" in vm.depends_on
        assert "azurerm_storage_account.storage1" in vm.depends_on


class TestHelperMethods:
    """Tests for helper methods used in dependency extraction."""

    def test_extract_resource_name_from_id(self):
        """Test extracting resource name from Azure resource ID."""
        analyzer = DependencyAnalyzer()

        # Standard resource ID
        resource_id = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1"
        name = analyzer._extract_resource_name_from_id(resource_id)
        assert name == "vnet1"

        # Subnet ID (nested resource)
        subnet_id = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1"
        name = analyzer._extract_resource_name_from_id(subnet_id)
        assert name == "subnet1"

        # Empty ID
        name = analyzer._extract_resource_name_from_id("")
        assert name == ""

        # Malformed ID
        name = analyzer._extract_resource_name_from_id("/invalid")
        assert name == "invalid"

    def test_extract_storage_from_diagnostics(self):
        """Test storage account extraction from diagnostics URI."""
        analyzer = DependencyAnalyzer()

        # Valid storage URI
        resource = {
            "properties": {
                "diagnosticsProfile": {
                    "bootDiagnostics": {
                        "storageUri": "https://mystorageaccount.blob.core.windows.net/"
                    }
                }
            }
        }
        storage = analyzer._extract_storage_from_diagnostics(resource)
        assert storage == "mystorageaccount"

        # No diagnostics profile
        resource = {"properties": {}}
        storage = analyzer._extract_storage_from_diagnostics(resource)
        assert storage == ""

        # Empty storage URI
        resource = {
            "properties": {"diagnosticsProfile": {"bootDiagnostics": {"storageUri": ""}}}
        }
        storage = analyzer._extract_storage_from_diagnostics(resource)
        assert storage == ""
