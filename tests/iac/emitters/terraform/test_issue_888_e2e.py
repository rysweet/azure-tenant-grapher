"""End-to-end tests for Issue #888 fix.

Testing Strategy (TDD - 10% E2E Tests):
- Test complete fix scenario from issue description
- Test realistic Azure environment with multiple resources
- Test that fix addresses both reported issues:
  1. Diagnostic settings handler not imported
  2. Duplicate NSG association code

These tests represent real-world usage scenarios and verify the complete
fix workflow from start to finish.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

import pytest

from src.iac.emitters.terraform.emitter import TerraformEmitter
from src.iac.emitters.terraform.handlers import HandlerRegistry, ensure_handlers_registered


class TestIssue888E2E:
    """End-to-end tests for Issue #888 complete fix (10% - E2E)."""

    def setup_method(self):
        """Setup test environment."""
        HandlerRegistry.clear()
        ensure_handlers_registered()

    def test_issue_888_complete_fix_scenario(self):
        """Test the complete Issue #888 fix scenario.

        This test verifies the ENTIRE fix works end-to-end:

        Issue #888 had TWO problems:
        1. Diagnostic Settings handler exists but not imported in handlers/__init__.py
        2. Duplicate NSG association code (legacy _emit_deferred_resources() + handler)

        Solution:
        1. Add diagnostic_settings import to handlers/__init__.py
        2. Remove legacy _emit_deferred_resources() method from emitter.py
        3. Keep handler-based architecture

        THIS TEST WILL FAIL IF:
        - Diagnostic settings handler is not imported (Issue #888 part 1)
        - Duplicate NSG associations are emitted (Issue #888 part 2)
        - Cross-RG associations are not skipped (Bug #13 regression)

        THIS TEST WILL PASS WHEN:
        - All handlers are properly registered
        - No duplicate emissions occur
        - Bug #13 fix is preserved
        """
        emitter = TerraformEmitter()

        # Create realistic Azure environment from Issue #888
        resources = [
            # Resource Group
            {
                "type": "Microsoft.Resources/resourceGroups",
                "name": "prod-rg",
                "location": "eastus",
                "id": "/subscriptions/test/resourceGroups/prod-rg",
                "properties": {},
            },
            # VNet
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "prod-vnet",
                "location": "eastus",
                "resourceGroup": "prod-rg",
                "id": "/subscriptions/test/resourceGroups/prod-rg/providers/Microsoft.Network/virtualNetworks/prod-vnet",
                "properties": {"addressSpace": {"addressPrefixes": ["10.0.0.0/16"]}},
            },
            # Subnet with NSG
            {
                "type": "Microsoft.Network/subnets",
                "name": "app-subnet",
                "resourceGroup": "prod-rg",
                "id": "/subscriptions/test/resourceGroups/prod-rg/providers/Microsoft.Network/virtualNetworks/prod-vnet/subnets/app-subnet",
                "properties": {
                    "addressPrefix": "10.0.1.0/24",
                    "networkSecurityGroup": {
                        "id": "/subscriptions/test/resourceGroups/prod-rg/providers/Microsoft.Network/networkSecurityGroups/app-nsg"
                    },
                },
            },
            # NSG
            {
                "type": "Microsoft.Network/networkSecurityGroups",
                "name": "app-nsg",
                "location": "eastus",
                "resourceGroup": "prod-rg",
                "id": "/subscriptions/test/resourceGroups/prod-rg/providers/Microsoft.Network/networkSecurityGroups/app-nsg",
                "properties": {
                    "securityRules": [
                        {
                            "name": "AllowHTTPS",
                            "properties": {
                                "protocol": "Tcp",
                                "sourcePortRange": "*",
                                "destinationPortRange": "443",
                                "access": "Allow",
                                "direction": "Inbound",
                                "priority": 100,
                            },
                        }
                    ]
                },
            },
            # Diagnostic Settings for NSG (Issue #888 part 1)
            {
                "type": "Microsoft.Insights/diagnosticSettings",
                "name": "nsg-diagnostics",
                "id": "/subscriptions/test/resourceGroups/prod-rg/providers/Microsoft.Network/networkSecurityGroups/app-nsg/providers/Microsoft.Insights/diagnosticSettings/nsg-diagnostics",
                "properties": {
                    "workspaceId": "/subscriptions/test/resourceGroups/prod-rg/providers/Microsoft.OperationalInsights/workspaces/prod-workspace",
                    "logs": [
                        {"category": "NetworkSecurityGroupEvent", "enabled": True},
                        {"category": "NetworkSecurityGroupRuleCounter", "enabled": True},
                    ],
                    "metrics": [
                        {"category": "AllMetrics", "enabled": False},
                    ],
                },
            },
            # NIC with NSG
            {
                "type": "Microsoft.Network/networkInterfaces",
                "name": "app-nic",
                "location": "eastus",
                "resourceGroup": "prod-rg",
                "id": "/subscriptions/test/resourceGroups/prod-rg/providers/Microsoft.Network/networkInterfaces/app-nic",
                "properties": {
                    "ipConfigurations": [
                        {
                            "name": "ipconfig1",
                            "properties": {
                                "subnet": {
                                    "id": "/subscriptions/test/resourceGroups/prod-rg/providers/Microsoft.Network/virtualNetworks/prod-vnet/subnets/app-subnet"
                                },
                                "privateIPAllocationMethod": "Dynamic",
                            },
                        }
                    ],
                    "networkSecurityGroup": {
                        "id": "/subscriptions/test/resourceGroups/prod-rg/providers/Microsoft.Network/networkSecurityGroups/app-nsg"
                    },
                },
            },
            # Storage Account with Diagnostic Settings
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "prodstorage",
                "location": "eastus",
                "resourceGroup": "prod-rg",
                "id": "/subscriptions/test/resourceGroups/prod-rg/providers/Microsoft.Storage/storageAccounts/prodstorage",
                "sku": {"name": "Standard_LRS"},
                "kind": "StorageV2",
                "properties": {},
            },
            # Diagnostic Settings for Storage Account
            {
                "type": "Microsoft.Insights/diagnosticSettings",
                "name": "storage-diagnostics",
                "id": "/subscriptions/test/resourceGroups/prod-rg/providers/Microsoft.Storage/storageAccounts/prodstorage/providers/Microsoft.Insights/diagnosticSettings/storage-diagnostics",
                "properties": {
                    "workspaceId": "/subscriptions/test/resourceGroups/prod-rg/providers/Microsoft.OperationalInsights/workspaces/prod-workspace",
                    "logs": [
                        {"category": "StorageRead", "enabled": True},
                        {"category": "StorageWrite", "enabled": True},
                        {"category": "StorageDelete", "enabled": False},
                    ],
                    "metrics": [
                        {"category": "Transaction", "enabled": True},
                    ],
                },
            },
        ]

        # Emit configuration
        config = emitter.emit(resources)

        # ===== VERIFICATION: Issue #888 Part 1 - Diagnostic Settings =====
        # Verify diagnostic settings are emitted
        diag_settings = config.get("resource", {}).get(
            "azurerm_monitor_diagnostic_setting", {}
        )

        assert len(diag_settings) == 2, (
            f"Expected 2 diagnostic settings (NSG + Storage), got {len(diag_settings)}. "
            f"If 0, diagnostic_settings handler is not imported in handlers/__init__.py"
        )

        # Verify NSG diagnostic setting
        nsg_diag_found = False
        for diag_name, diag_config in diag_settings.items():
            if "app_nsg" in diag_config.get("target_resource_id", ""):
                nsg_diag_found = True
                assert "enabled_log" in diag_config
                assert len(diag_config["enabled_log"]) == 2  # 2 enabled logs
                break

        assert nsg_diag_found, "NSG diagnostic setting not found"

        # ===== VERIFICATION: Issue #888 Part 2 - No Duplicate NSG Associations =====
        # Verify subnet-NSG associations (should be exactly 1, not 2)
        subnet_associations = config.get("resource", {}).get(
            "azurerm_subnet_network_security_group_association", {}
        )

        assert len(subnet_associations) == 1, (
            f"Expected 1 subnet-NSG association, got {len(subnet_associations)}. "
            f"If 2, legacy _emit_deferred_resources() is emitting duplicates."
        )

        # Verify NIC-NSG associations (should be exactly 1, not 2)
        nic_associations = config.get("resource", {}).get(
            "azurerm_network_interface_security_group_association", {}
        )

        assert len(nic_associations) == 1, (
            f"Expected 1 NIC-NSG association, got {len(nic_associations)}. "
            f"If 2, legacy _emit_deferred_resources() is emitting duplicates."
        )

        # ===== VERIFICATION: Bug #13 Still Fixed =====
        # Verify associations are properly formed (not skipped incorrectly)
        subnet_assoc_config = list(subnet_associations.values())[0]
        assert "subnet_id" in subnet_assoc_config
        assert "network_security_group_id" in subnet_assoc_config

        nic_assoc_config = list(nic_associations.values())[0]
        assert "network_interface_id" in nic_assoc_config
        assert "network_security_group_id" in nic_assoc_config

        # ===== VERIFICATION: All Expected Resources Emitted =====
        expected_resources = {
            "azurerm_resource_group",
            "azurerm_virtual_network",
            "azurerm_subnet",
            "azurerm_network_security_group",
            "azurerm_network_interface",
            "azurerm_storage_account",
            "azurerm_monitor_diagnostic_setting",
            "azurerm_subnet_network_security_group_association",
            "azurerm_network_interface_security_group_association",
        }

        actual_resources = set(config.get("resource", {}).keys())

        missing_resources = expected_resources - actual_resources
        assert len(missing_resources) == 0, (
            f"Missing expected resources: {missing_resources}"
        )

    def test_issue_888_cross_rg_scenario_preserved(self):
        """Test that Bug #13 fix is preserved in Issue #888 solution.

        This verifies that the fix for Issue #888 does NOT break
        the existing Bug #13 fix (cross-RG NSG associations skipped).
        """
        emitter = TerraformEmitter()

        # Create cross-RG scenario
        resources = [
            # VNet in rg1
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet1",
                "location": "eastus",
                "resourceGroup": "rg1",
                "id": "/subscriptions/test/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1",
                "properties": {"addressSpace": {"addressPrefixes": ["10.0.0.0/16"]}},
            },
            # Subnet in rg1 referencing NSG in rg2
            {
                "type": "Microsoft.Network/subnets",
                "name": "subnet1",
                "resourceGroup": "rg1",
                "id": "/subscriptions/test/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1",
                "properties": {
                    "addressPrefix": "10.0.1.0/24",
                    "networkSecurityGroup": {
                        "id": "/subscriptions/test/resourceGroups/rg2/providers/Microsoft.Network/networkSecurityGroups/nsg2"
                    },
                },
            },
            # NSG in rg2 (different RG!)
            {
                "type": "Microsoft.Network/networkSecurityGroups",
                "name": "nsg2",
                "location": "eastus",
                "resourceGroup": "rg2",
                "id": "/subscriptions/test/resourceGroups/rg2/providers/Microsoft.Network/networkSecurityGroups/nsg2",
                "properties": {},
            },
        ]

        config = emitter.emit(resources)

        # Verify NO associations were created (cross-RG skipped)
        subnet_associations = config.get("resource", {}).get(
            "azurerm_subnet_network_security_group_association", {}
        )

        assert len(subnet_associations) == 0, (
            f"Cross-RG associations should be skipped (Bug #13), "
            f"but got {len(subnet_associations)} associations. "
            f"Issue #888 fix may have broken Bug #13 fix."
        )

    def test_issue_888_multiple_diagnostic_settings_scenario(self):
        """Test realistic scenario with multiple diagnostic settings.

        This tests a production-like environment with diagnostic settings
        on multiple resource types to ensure the fix works at scale.
        """
        emitter = TerraformEmitter()

        resources = []

        # Create 5 NSGs with diagnostic settings
        for i in range(5):
            resources.extend(
                [
                    {
                        "type": "Microsoft.Network/networkSecurityGroups",
                        "name": f"nsg-{i}",
                        "location": "eastus",
                        "resourceGroup": "test-rg",
                        "id": f"/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/networkSecurityGroups/nsg-{i}",
                        "properties": {},
                    },
                    {
                        "type": "Microsoft.Insights/diagnosticSettings",
                        "name": f"nsg-{i}-diag",
                        "id": f"/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/networkSecurityGroups/nsg-{i}/providers/Microsoft.Insights/diagnosticSettings/nsg-{i}-diag",
                        "properties": {
                            "workspaceId": "/subscriptions/test/workspace",
                            "logs": [
                                {"category": "NetworkSecurityGroupEvent", "enabled": True}
                            ],
                        },
                    },
                ]
            )

        config = emitter.emit(resources)

        # Verify all diagnostic settings were emitted
        diag_settings = config.get("resource", {}).get(
            "azurerm_monitor_diagnostic_setting", {}
        )

        assert len(diag_settings) == 5, (
            f"Expected 5 diagnostic settings, got {len(diag_settings)}. "
            f"Diagnostic settings handler may not be working properly."
        )

        # Verify all NSGs were emitted
        nsgs = config.get("resource", {}).get("azurerm_network_security_group", {})
        assert len(nsgs) == 5, f"Expected 5 NSGs, got {len(nsgs)}"
