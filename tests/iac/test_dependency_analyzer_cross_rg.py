"""
Tests for Cross-Resource Group Dependency Detection in DependencyAnalyzer.

Tests cover:
- ResourceGroupDependency dataclass
- Cross-RG dependency detection
- Deployment ordering with cross-RG dependencies
- Broken reference warnings
- Resource grouping by cross-RG dependencies
- Edge cases (single RG, no dependencies, circular dependencies)
"""

import pytest

from src.iac.dependency_analyzer import (
    DependencyAnalyzer,
    ResourceGroupDependency,
)


class TestResourceGroupDependency:
    """Tests for ResourceGroupDependency dataclass."""

    def test_create_resource_group_dependency(self):
        """Test creating ResourceGroupDependency with all fields."""
        dep = ResourceGroupDependency(
            source_rg="rg-compute",
            target_rg="rg-network",
            dependency_count=2,
            resources=["vm1", "vm2"],
        )

        assert dep.source_rg == "rg-compute"
        assert dep.target_rg == "rg-network"
        assert dep.dependency_count == 2
        assert dep.resources == ["vm1", "vm2"]

    def test_resource_group_dependency_default_resources(self):
        """Test ResourceGroupDependency with default empty resources list."""
        dep = ResourceGroupDependency(
            source_rg="rg-apps",
            target_rg="rg-shared",
            dependency_count=1,
        )

        assert dep.source_rg == "rg-apps"
        assert dep.target_rg == "rg-shared"
        assert dep.dependency_count == 1
        assert dep.resources == []


class TestCrossRGDependencyDetection:
    """Tests for detecting cross-Resource Group dependencies."""

    def test_detect_simple_cross_rg_dependency(self):
        """Test detecting a simple cross-RG dependency."""
        analyzer = DependencyAnalyzer()

        resources = [
            {
                "name": "vm1",
                "type": "Microsoft.Compute/virtualMachines",
                "resource_group": "rg-compute",
                "properties": {
                    "networkProfile": {
                        "networkInterfaces": [
                            {
                                "id": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic1"
                            }
                        ]
                    }
                },
            },
            {
                "name": "nic1",
                "type": "Microsoft.Network/networkInterfaces",
                "resource_group": "rg-network",
            },
        ]

        cross_rg_deps = analyzer.get_cross_rg_dependencies(resources)

        assert len(cross_rg_deps) == 1
        assert cross_rg_deps[0].source_rg == "rg-compute"
        assert cross_rg_deps[0].target_rg == "rg-network"
        assert cross_rg_deps[0].dependency_count >= 1
        assert "vm1" in cross_rg_deps[0].resources

    def test_detect_multiple_cross_rg_dependencies(self):
        """Test detecting multiple cross-RG dependencies."""
        analyzer = DependencyAnalyzer()

        resources = [
            {
                "name": "vm1",
                "type": "Microsoft.Compute/virtualMachines",
                "resource_group": "rg-compute",
                "properties": {
                    "networkProfile": {
                        "networkInterfaces": [
                            {
                                "id": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic1"
                            }
                        ]
                    }
                },
            },
            {
                "name": "app1",
                "type": "Microsoft.Web/sites",
                "resource_group": "rg-apps",
                "properties": {
                    "virtualNetworkSubnetId": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1"
                },
            },
            {
                "name": "nic1",
                "type": "Microsoft.Network/networkInterfaces",
                "resource_group": "rg-network",
            },
            {
                "name": "vnet1",
                "type": "Microsoft.Network/virtualNetworks",
                "resource_group": "rg-network",
            },
        ]

        cross_rg_deps = analyzer.get_cross_rg_dependencies(resources)

        # Should detect rg-compute -> rg-network and rg-apps -> rg-network
        assert len(cross_rg_deps) >= 2

        source_rgs = [dep.source_rg for dep in cross_rg_deps]
        assert "rg-compute" in source_rgs
        assert "rg-apps" in source_rgs

        target_rgs = [dep.target_rg for dep in cross_rg_deps]
        assert all(rg == "rg-network" for rg in target_rgs)

    def test_no_cross_rg_dependencies(self):
        """Test when resources have no cross-RG dependencies."""
        analyzer = DependencyAnalyzer()

        resources = [
            {
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
            },
            {
                "name": "nic1",
                "type": "Microsoft.Network/networkInterfaces",
                "resource_group": "rg-compute",
            },
        ]

        cross_rg_deps = analyzer.get_cross_rg_dependencies(resources)

        assert len(cross_rg_deps) == 0

    def test_single_resource_group(self):
        """Test when all resources are in a single RG."""
        analyzer = DependencyAnalyzer()

        resources = [
            {
                "name": "resource1",
                "type": "Microsoft.Storage/storageAccounts",
                "resource_group": "rg-all",
            },
            {
                "name": "resource2",
                "type": "Microsoft.Network/virtualNetworks",
                "resource_group": "rg-all",
            },
            {
                "name": "resource3",
                "type": "Microsoft.Compute/virtualMachines",
                "resource_group": "rg-all",
            },
        ]

        cross_rg_deps = analyzer.get_cross_rg_dependencies(resources)

        assert len(cross_rg_deps) == 0


class TestRGDeploymentOrdering:
    """Tests for Resource Group deployment ordering."""

    def test_simple_deployment_order(self):
        """Test simple deployment order: network before compute."""
        analyzer = DependencyAnalyzer()

        resources = [
            {
                "name": "vm1",
                "type": "Microsoft.Compute/virtualMachines",
                "resource_group": "rg-compute",
                "properties": {
                    "networkProfile": {
                        "networkInterfaces": [
                            {
                                "id": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic1"
                            }
                        ]
                    }
                },
            },
            {
                "name": "nic1",
                "type": "Microsoft.Network/networkInterfaces",
                "resource_group": "rg-network",
            },
        ]

        deployment_order = analyzer.get_rg_deployment_order(resources)

        # rg-network must come before rg-compute
        assert deployment_order.index("rg-network") < deployment_order.index(
            "rg-compute"
        )

    def test_complex_deployment_order(self):
        """Test complex deployment order with multiple dependency levels."""
        analyzer = DependencyAnalyzer()

        resources = [
            # Level 3: App depends on Compute and Shared
            {
                "name": "app1",
                "type": "Microsoft.Web/sites",
                "resource_group": "rg-apps",
                "properties": {
                    "virtualNetworkSubnetId": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1",
                    "keyVaultId": "/subscriptions/sub1/resourceGroups/rg-shared/providers/Microsoft.KeyVault/vaults/kv1",
                },
            },
            # Level 2: Compute depends on Network
            {
                "name": "vm1",
                "type": "Microsoft.Compute/virtualMachines",
                "resource_group": "rg-compute",
                "properties": {
                    "networkProfile": {
                        "networkInterfaces": [
                            {
                                "id": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic1"
                            }
                        ]
                    }
                },
            },
            # Level 1: Network (no dependencies)
            {
                "name": "nic1",
                "type": "Microsoft.Network/networkInterfaces",
                "resource_group": "rg-network",
            },
            # Level 1: Shared (no dependencies)
            {
                "name": "kv1",
                "type": "Microsoft.KeyVault/vaults",
                "resource_group": "rg-shared",
            },
        ]

        deployment_order = analyzer.get_rg_deployment_order(resources)

        # rg-network and rg-shared have no dependencies (can be first or second)
        # rg-compute depends on rg-network (must come after network)
        # rg-apps depends on network and shared (must come last)

        network_idx = deployment_order.index("rg-network")
        shared_idx = deployment_order.index("rg-shared")
        compute_idx = deployment_order.index("rg-compute")
        apps_idx = deployment_order.index("rg-apps")

        assert network_idx < compute_idx
        assert network_idx < apps_idx
        assert shared_idx < apps_idx

    def test_deployment_order_single_rg(self):
        """Test deployment order with single Resource Group."""
        analyzer = DependencyAnalyzer()

        resources = [
            {
                "name": "resource1",
                "type": "Microsoft.Storage/storageAccounts",
                "resource_group": "rg-all",
            },
        ]

        deployment_order = analyzer.get_rg_deployment_order(resources)

        assert deployment_order == ["rg-all"]

    def test_deployment_order_circular_dependency(self):
        """Test deployment order handles circular dependencies gracefully."""
        analyzer = DependencyAnalyzer()

        # This creates a circular dependency: rg-a -> rg-b -> rg-a
        resources = [
            {
                "name": "resource_a",
                "type": "Microsoft.Storage/storageAccounts",
                "resource_group": "rg-a",
                "properties": {
                    "networkAcls": {
                        "virtualNetworkRules": [
                            {
                                "id": "/subscriptions/sub1/resourceGroups/rg-b/providers/Microsoft.Network/virtualNetworks/vnet-b/subnets/subnet1"
                            }
                        ]
                    }
                },
            },
            {
                "name": "resource_b",
                "type": "Microsoft.Network/virtualNetworks",
                "resource_group": "rg-b",
                "properties": {
                    "subnets": [
                        {
                            "properties": {
                                "serviceEndpoints": [
                                    {
                                        "service": "Microsoft.Storage",
                                        "locations": [
                                            "/subscriptions/sub1/resourceGroups/rg-a/providers/Microsoft.Storage/storageAccounts/storage-a"
                                        ],
                                    }
                                ]
                            }
                        }
                    ]
                },
            },
        ]

        # Should either:
        # 1. Detect cycle and raise error, OR
        # 2. Return best-effort ordering with warning
        with pytest.raises((ValueError, RuntimeError)):
            analyzer.get_rg_deployment_order(resources)


class TestBrokenReferenceWarnings:
    """Tests for broken reference warning system."""

    def test_warn_on_rg_removal(self):
        """Test warning when removing RG would break references."""
        analyzer = DependencyAnalyzer()

        current_resources = [
            {
                "name": "vm1",
                "type": "Microsoft.Compute/virtualMachines",
                "resource_group": "rg-compute",
                "properties": {
                    "networkProfile": {
                        "networkInterfaces": [
                            {
                                "id": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic1"
                            }
                        ]
                    }
                },
            },
            {
                "name": "nic1",
                "type": "Microsoft.Network/networkInterfaces",
                "resource_group": "rg-network",
            },
        ]

        # Proposed: Remove rg-network
        proposed_rg_structure = ["rg-compute"]

        warnings = analyzer.check_broken_references(
            current_resources, proposed_rg_structure
        )

        assert len(warnings) > 0
        assert any("rg-network" in warning for warning in warnings)

    def test_warn_on_resource_move(self):
        """Test warning when moving resource would break references."""
        analyzer = DependencyAnalyzer()

        current_resources = [
            {
                "name": "vm1",
                "type": "Microsoft.Compute/virtualMachines",
                "resource_group": "rg-compute",
                "properties": {
                    "networkProfile": {
                        "networkInterfaces": [
                            {
                                "id": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic1"
                            }
                        ]
                    }
                },
            },
            {
                "name": "nic1",
                "type": "Microsoft.Network/networkInterfaces",
                "resource_group": "rg-network",
            },
        ]

        # Proposed: Move nic1 from rg-network to rg-compute
        proposed_resources = [
            {
                "name": "vm1",
                "type": "Microsoft.Compute/virtualMachines",
                "resource_group": "rg-compute",
                "properties": {
                    "networkProfile": {
                        "networkInterfaces": [
                            {
                                "id": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic1"
                            }
                        ]
                    }
                },
            },
            {
                "name": "nic1",
                "type": "Microsoft.Network/networkInterfaces",
                "resource_group": "rg-compute",  # MOVED
            },
        ]

        warnings = analyzer.check_broken_references_on_move(
            current_resources, proposed_resources
        )

        assert len(warnings) > 0
        assert any(
            "nic1" in warning and "rg-network" in warning for warning in warnings
        )

    def test_no_warnings_on_safe_changes(self):
        """Test no warnings when changes don't break references."""
        analyzer = DependencyAnalyzer()

        current_resources = [
            {
                "name": "vm1",
                "type": "Microsoft.Compute/virtualMachines",
                "resource_group": "rg-compute",
            },
            {
                "name": "storage1",
                "type": "Microsoft.Storage/storageAccounts",
                "resource_group": "rg-storage",
            },
        ]

        # Proposed: Remove rg-storage (no dependencies)
        proposed_rg_structure = ["rg-compute"]

        warnings = analyzer.check_broken_references(
            current_resources, proposed_rg_structure
        )

        assert len(warnings) == 0


class TestResourceGrouping:
    """Tests for resource grouping by cross-RG dependencies."""

    def test_group_by_cross_rg_deps_simple(self):
        """Test grouping resources by cross-RG dependencies."""
        analyzer = DependencyAnalyzer()

        resources = [
            {
                "name": "vm1",
                "type": "Microsoft.Compute/virtualMachines",
                "resource_group": "rg-compute",
                "properties": {
                    "networkProfile": {
                        "networkInterfaces": [
                            {
                                "id": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic1"
                            }
                        ]
                    }
                },
            },
            {
                "name": "nic1",
                "type": "Microsoft.Network/networkInterfaces",
                "resource_group": "rg-network",
            },
        ]

        groups = analyzer.group_by_cross_rg_deps(resources)

        # rg-network: no dependencies, has rg-compute as dependent
        # rg-compute: depends on rg-network, no dependents
        assert "rg-network" in groups
        assert "rg-compute" in groups

        assert groups["rg-network"]["dependencies"] == []
        assert "rg-compute" in groups["rg-network"]["dependents"]

        assert "rg-network" in groups["rg-compute"]["dependencies"]
        assert groups["rg-compute"]["dependents"] == []

    def test_group_by_cross_rg_deps_complex(self):
        """Test grouping with complex cross-RG dependency structure."""
        analyzer = DependencyAnalyzer()

        resources = [
            {
                "name": "app1",
                "type": "Microsoft.Web/sites",
                "resource_group": "rg-apps",
                "properties": {
                    "virtualNetworkSubnetId": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1"
                },
            },
            {
                "name": "vm1",
                "type": "Microsoft.Compute/virtualMachines",
                "resource_group": "rg-compute",
                "properties": {
                    "networkProfile": {
                        "networkInterfaces": [
                            {
                                "id": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic1"
                            }
                        ]
                    }
                },
            },
            {
                "name": "nic1",
                "type": "Microsoft.Network/networkInterfaces",
                "resource_group": "rg-network",
            },
        ]

        groups = analyzer.group_by_cross_rg_deps(resources)

        # rg-network should have both rg-apps and rg-compute as dependents
        assert "rg-apps" in groups["rg-network"]["dependents"]
        assert "rg-compute" in groups["rg-network"]["dependents"]

        # rg-apps and rg-compute should both depend on rg-network
        assert "rg-network" in groups["rg-apps"]["dependencies"]
        assert "rg-network" in groups["rg-compute"]["dependencies"]
