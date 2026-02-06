"""Integration tests for NSG associations and diagnostic settings.

Testing Strategy (TDD - 30% Integration Tests):
- Test complete workflow: resource emission → handler post_emit → associations
- Test diagnostic settings are emitted alongside other resources
- Test NO duplicate NSG associations (legacy + handler)
- Test handlers coordinate properly through EmitterContext

These tests verify the integration between TerraformEmitter, handlers,
and the context object to ensure proper workflow execution.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

import pytest

from src.iac.emitters.terraform.context import EmitterContext
from src.iac.emitters.terraform.emitter import TerraformEmitter
from src.iac.emitters.terraform.handlers import HandlerRegistry, ensure_handlers_registered


class TestNSGAssociationIntegration:
    """Integration tests for NSG association workflow (30% - Integration)."""

    def setup_method(self):
        """Setup test environment."""
        HandlerRegistry.clear()
        ensure_handlers_registered()

    def test_nsg_associations_emitted_via_handler_not_legacy(self):
        """Test that NSG associations are emitted via handler, not legacy code.

        THIS TEST WILL FAIL IF:
        1. Legacy _emit_deferred_resources() still exists and emits associations
        2. Both legacy and handler emit associations (duplicate emissions)

        THIS TEST WILL PASS WHEN:
        1. Legacy _emit_deferred_resources() is removed
        2. Only handler-based emission occurs
        """
        emitter = TerraformEmitter()

        # Create resources with NSG association
        resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "test-vnet",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet",
                "properties": {"addressSpace": {"addressPrefixes": ["10.0.0.0/16"]}},
            },
            {
                "type": "Microsoft.Network/subnets",
                "name": "test-subnet",
                "resourceGroup": "test-rg",
                "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/test-subnet",
                "properties": {
                    "addressPrefix": "10.0.1.0/24",
                    "networkSecurityGroup": {
                        "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/networkSecurityGroups/test-nsg"
                    },
                },
            },
            {
                "type": "Microsoft.Network/networkSecurityGroups",
                "name": "test-nsg",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/networkSecurityGroups/test-nsg",
                "properties": {},
            },
        ]

        # Emit configuration
        config = emitter.emit(resources)

        # Verify associations exist
        associations = config.get("resource", {}).get(
            "azurerm_subnet_network_security_group_association", {}
        )

        # Should have exactly ONE association (not duplicates)
        assert len(associations) == 1, (
            f"Expected 1 association, got {len(associations)}. "
            f"If >1, check for duplicate emissions from legacy code."
        )

        # Verify association is correctly formed
        assoc_name = list(associations.keys())[0]
        assoc_config = associations[assoc_name]

        assert "subnet_id" in assoc_config
        assert "network_security_group_id" in assoc_config
        assert "azurerm_subnet" in assoc_config["subnet_id"]
        assert "azurerm_network_security_group" in assoc_config["network_security_group_id"]

    def test_nic_nsg_associations_emitted_via_handler_not_legacy(self):
        """Test that NIC-NSG associations are emitted via handler, not legacy code."""
        emitter = TerraformEmitter()

        resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "test-vnet",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet",
                "properties": {"addressSpace": {"addressPrefixes": ["10.0.0.0/16"]}},
            },
            {
                "type": "Microsoft.Network/subnets",
                "name": "test-subnet",
                "resourceGroup": "test-rg",
                "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/test-subnet",
                "properties": {"addressPrefix": "10.0.1.0/24"},
            },
            {
                "type": "Microsoft.Network/networkSecurityGroups",
                "name": "test-nsg",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/networkSecurityGroups/test-nsg",
                "properties": {},
            },
            {
                "type": "Microsoft.Network/networkInterfaces",
                "name": "test-nic",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/networkInterfaces/test-nic",
                "properties": {
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
                },
            },
        ]

        config = emitter.emit(resources)

        # Verify NIC-NSG associations exist
        associations = config.get("resource", {}).get(
            "azurerm_network_interface_security_group_association", {}
        )

        # Should have exactly ONE association (not duplicates)
        assert len(associations) == 1, (
            f"Expected 1 NIC-NSG association, got {len(associations)}. "
            f"Check for duplicate emissions."
        )

    def test_no_duplicate_nsg_associations_with_multiple_subnets(self):
        """Test that multiple subnet-NSG associations don't create duplicates.

        THIS IS CRITICAL:
        If legacy _emit_deferred_resources() still exists alongside handler,
        we'll get 2x the expected associations.
        """
        emitter = TerraformEmitter()

        # Create multiple subnets with NSG
        resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "test-vnet",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet",
                "properties": {"addressSpace": {"addressPrefixes": ["10.0.0.0/16"]}},
            },
            {
                "type": "Microsoft.Network/networkSecurityGroups",
                "name": "test-nsg",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/networkSecurityGroups/test-nsg",
                "properties": {},
            },
        ]

        # Add 3 subnets with same NSG
        for i in range(3):
            resources.append(
                {
                    "type": "Microsoft.Network/subnets",
                    "name": f"test-subnet-{i}",
                    "resourceGroup": "test-rg",
                    "id": f"/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/test-subnet-{i}",
                    "properties": {
                        "addressPrefix": f"10.0.{i}.0/24",
                        "networkSecurityGroup": {
                            "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/networkSecurityGroups/test-nsg"
                        },
                    },
                }
            )

        config = emitter.emit(resources)

        associations = config.get("resource", {}).get(
            "azurerm_subnet_network_security_group_association", {}
        )

        # Should have exactly 3 associations (one per subnet), not 6 (duplicates)
        assert len(associations) == 3, (
            f"Expected 3 associations (one per subnet), got {len(associations)}. "
            f"If 6, legacy code is emitting duplicates alongside handler."
        )

    def test_cross_rg_nsg_associations_still_skipped(self):
        """Test that Bug #13 fix is preserved - cross-RG associations skipped.

        THIS IS CRITICAL:
        The fix must preserve the Bug #13 behavior where cross-resource-group
        NSG associations are skipped.
        """
        emitter = TerraformEmitter()

        resources = [
            # VNet in rg1
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "test-vnet",
                "location": "eastus",
                "resourceGroup": "rg1",
                "id": "/subscriptions/test/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/test-vnet",
                "properties": {"addressSpace": {"addressPrefixes": ["10.0.0.0/16"]}},
            },
            # Subnet in rg1
            {
                "type": "Microsoft.Network/subnets",
                "name": "test-subnet",
                "resourceGroup": "rg1",
                "id": "/subscriptions/test/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/test-subnet",
                "properties": {
                    "addressPrefix": "10.0.1.0/24",
                    "networkSecurityGroup": {
                        "id": "/subscriptions/test/resourceGroups/rg2/providers/Microsoft.Network/networkSecurityGroups/test-nsg"
                    },
                },
            },
            # NSG in rg2 (different RG!)
            {
                "type": "Microsoft.Network/networkSecurityGroups",
                "name": "test-nsg",
                "location": "eastus",
                "resourceGroup": "rg2",
                "id": "/subscriptions/test/resourceGroups/rg2/providers/Microsoft.Network/networkSecurityGroups/test-nsg",
                "properties": {},
            },
        ]

        config = emitter.emit(resources)

        associations = config.get("resource", {}).get(
            "azurerm_subnet_network_security_group_association", {}
        )

        # Should have ZERO associations (cross-RG skipped)
        assert len(associations) == 0, (
            "Cross-RG NSG association should be skipped (Bug #13 fix). "
            f"Got {len(associations)} associations."
        )


class TestDiagnosticSettingsIntegration:
    """Integration tests for diagnostic settings emission (30% - Integration)."""

    def setup_method(self):
        """Setup test environment."""
        HandlerRegistry.clear()
        ensure_handlers_registered()

    def test_diagnostic_settings_emitted_with_storage_account(self):
        """Test that diagnostic settings are emitted for storage accounts.

        THIS TEST WILL FAIL IF:
        Handler is not imported in handlers/__init__.py

        THIS TEST WILL PASS WHEN:
        Handler is properly imported and registered.
        """
        emitter = TerraformEmitter()

        resources = [
            # Storage Account
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "teststorage",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/teststorage",
                "sku": {"name": "Standard_LRS"},
                "kind": "StorageV2",
                "properties": {},
            },
            # Diagnostic Setting for Storage Account
            {
                "type": "Microsoft.Insights/diagnosticSettings",
                "name": "diag-settings",
                "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/teststorage/providers/Microsoft.Insights/diagnosticSettings/diag-settings",
                "properties": {
                    "workspaceId": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.OperationalInsights/workspaces/test-workspace",
                    "logs": [
                        {"category": "StorageRead", "enabled": True},
                    ],
                    "metrics": [
                        {"category": "Transaction", "enabled": True},
                    ],
                },
            },
        ]

        config = emitter.emit(resources)

        # Verify storage account was emitted
        assert "azurerm_storage_account" in config.get("resource", {})

        # Verify diagnostic setting was emitted
        diag_settings = config.get("resource", {}).get(
            "azurerm_monitor_diagnostic_setting", {}
        )

        assert len(diag_settings) > 0, (
            "Diagnostic setting not emitted. "
            "Check that diagnostic_settings handler is imported in handlers/__init__.py"
        )

        # Verify diagnostic setting references storage account
        diag_config = list(diag_settings.values())[0]
        assert "target_resource_id" in diag_config
        assert "log_analytics_workspace_id" in diag_config

    def test_diagnostic_settings_emitted_with_nsg(self):
        """Test that diagnostic settings work with NSGs."""
        emitter = TerraformEmitter()

        resources = [
            # NSG
            {
                "type": "Microsoft.Network/networkSecurityGroups",
                "name": "test-nsg",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/networkSecurityGroups/test-nsg",
                "properties": {},
            },
            # Diagnostic Setting for NSG
            {
                "type": "Microsoft.Insights/diagnosticSettings",
                "name": "nsg-diag",
                "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/networkSecurityGroups/test-nsg/providers/Microsoft.Insights/diagnosticSettings/nsg-diag",
                "properties": {
                    "workspaceId": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.OperationalInsights/workspaces/test-workspace",
                    "logs": [
                        {"category": "NetworkSecurityGroupEvent", "enabled": True},
                        {"category": "NetworkSecurityGroupRuleCounter", "enabled": True},
                    ],
                },
            },
        ]

        config = emitter.emit(resources)

        # Verify NSG was emitted
        assert "azurerm_network_security_group" in config.get("resource", {})

        # Verify diagnostic setting was emitted
        diag_settings = config.get("resource", {}).get(
            "azurerm_monitor_diagnostic_setting", {}
        )

        assert len(diag_settings) > 0
        diag_config = list(diag_settings.values())[0]

        # Verify logs
        assert "enabled_log" in diag_config
        assert len(diag_config["enabled_log"]) == 2


class TestHandlerCoordination:
    """Integration tests for handler coordination (30% - Integration)."""

    def setup_method(self):
        """Setup test environment."""
        HandlerRegistry.clear()
        ensure_handlers_registered()

    def test_handlers_coordinate_via_context(self):
        """Test that handlers properly coordinate through EmitterContext.

        This verifies:
        1. VNet/Subnet handlers track associations in context
        2. NSG association handler reads from context
        3. All handlers work together via shared context
        """
        emitter = TerraformEmitter()

        resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "test-vnet",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet",
                "properties": {"addressSpace": {"addressPrefixes": ["10.0.0.0/16"]}},
            },
            {
                "type": "Microsoft.Network/subnets",
                "name": "test-subnet",
                "resourceGroup": "test-rg",
                "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/test-subnet",
                "properties": {
                    "addressPrefix": "10.0.1.0/24",
                    "networkSecurityGroup": {
                        "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/networkSecurityGroups/test-nsg"
                    },
                },
            },
            {
                "type": "Microsoft.Network/networkSecurityGroups",
                "name": "test-nsg",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/networkSecurityGroups/test-nsg",
                "properties": {},
            },
        ]

        config = emitter.emit(resources)

        # Verify all resource types were emitted
        resource_types = set(config.get("resource", {}).keys())

        expected_types = {
            "azurerm_virtual_network",
            "azurerm_subnet",
            "azurerm_network_security_group",
            "azurerm_subnet_network_security_group_association",
        }

        assert expected_types.issubset(resource_types), (
            f"Missing expected resource types. "
            f"Expected: {expected_types}, Got: {resource_types}"
        )
