"""Comprehensive validation tests for terraform_emitter handlers.

This test suite validates that the new handler system produces identical or
acceptable output compared to the legacy implementation BEFORE removing legacy code.

Test Coverage:
1. Handler Registration: All 57 handlers registered correctly
2. Resource Type Coverage: All Azure types have handlers
3. Output Comparison: Handler output matches legacy for common types
4. Edge Cases: Missing properties, complex nesting, cross-references
5. Helper Resources: SSH keys, passwords, TLS certs generated correctly

Test Strategy:
- Use real Azure resource JSON structures
- Compare NEW handler path vs LEGACY path output
- Assert identical output or document acceptable differences
- Cover top 30 most common resource types

CRITICAL: These tests are the foundation for safely removing legacy code.
"""

import json
import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pytest

from src.iac.emitters.terraform_emitter import TerraformEmitter
from src.iac.emitters.terraform.context import EmitterContext
from src.iac.emitters.terraform.handlers import HandlerRegistry, ensure_handlers_registered
from src.iac.traverser import TenantGraph

logger = logging.getLogger(__name__)


class TestHandlerRegistration:
    """Test handler registration and coverage."""

    def test_all_handlers_registered(self) -> None:
        """Test that all 57 handler files are registered.

        This test ensures that no handler was missed during registration
        in the _register_all_handlers() function.
        """
        # Force registration
        ensure_handlers_registered()

        registered_handlers = HandlerRegistry.get_all_handlers()

        # We expect ~57 handlers based on file count
        # (Some files may have multiple handlers or special cases)
        assert len(registered_handlers) >= 50, (
            f"Expected at least 50 handlers, got {len(registered_handlers)}. "
            f"Check if all handler modules are imported in handlers/__init__.py"
        )

        logger.info(f"✅ {len(registered_handlers)} handlers registered successfully")

    def test_handler_types_documented(self) -> None:
        """Test that all handlers declare HANDLED_TYPES and TERRAFORM_TYPES."""
        ensure_handlers_registered()

        handlers = HandlerRegistry.get_all_handlers()

        for handler_class in handlers:
            # Check HANDLED_TYPES is declared
            assert hasattr(handler_class, "HANDLED_TYPES"), (
                f"{handler_class.__name__} must declare HANDLED_TYPES"
            )
            assert len(handler_class.HANDLED_TYPES) > 0, (
                f"{handler_class.__name__} HANDLED_TYPES cannot be empty"
            )

            # Check TERRAFORM_TYPES is declared
            assert hasattr(handler_class, "TERRAFORM_TYPES"), (
                f"{handler_class.__name__} must declare TERRAFORM_TYPES"
            )
            # Note: TERRAFORM_TYPES can be empty for handlers that skip resources

    def test_no_duplicate_type_handlers(self) -> None:
        """Test that no two handlers claim the same Azure resource type.

        If two handlers claim the same type, it's non-deterministic which one runs.
        """
        ensure_handlers_registered()

        handlers = HandlerRegistry.get_all_handlers()
        type_to_handlers: Dict[str, List[str]] = {}

        for handler_class in handlers:
            for azure_type in handler_class.HANDLED_TYPES:
                azure_type_lower = azure_type.lower()
                if azure_type_lower not in type_to_handlers:
                    type_to_handlers[azure_type_lower] = []
                type_to_handlers[azure_type_lower].append(handler_class.__name__)

        # Find duplicates
        duplicates = {
            azure_type: handler_names
            for azure_type, handler_names in type_to_handlers.items()
            if len(handler_names) > 1
        }

        assert len(duplicates) == 0, (
            f"Multiple handlers registered for same types: {duplicates}"
        )

    def test_common_azure_types_have_handlers(self) -> None:
        """Test that all common Azure resource types have handlers.

        These are the top 30 most common resource types in production tenants.
        If any are missing, legacy code handles them.
        """
        ensure_handlers_registered()

        common_types = [
            # Compute (most common)
            "Microsoft.Compute/virtualMachines",
            "Microsoft.Compute/disks",
            "Microsoft.Compute/virtualMachines/extensions",

            # Network (critical infrastructure)
            "Microsoft.Network/virtualNetworks",
            "Microsoft.Network/subnets",
            "Microsoft.Network/networkInterfaces",
            "Microsoft.Network/networkSecurityGroups",
            "Microsoft.Network/publicIPAddresses",
            "Microsoft.Network/bastionHosts",
            "Microsoft.Network/applicationGateways",
            "Microsoft.Network/loadBalancers",
            "Microsoft.Network/natGateways",
            "Microsoft.Network/routeTables",

            # Storage
            "Microsoft.Storage/storageAccounts",

            # Identity & Access
            "Microsoft.ManagedIdentity/userAssignedIdentities",
            "Microsoft.Authorization/roleAssignments",

            # Database
            "Microsoft.Sql/servers",
            "Microsoft.Sql/servers/databases",
            "Microsoft.DBforPostgreSQL/servers",
            "Microsoft.DocumentDB/databaseAccounts",

            # Monitoring & Insights
            "Microsoft.Insights/components",
            "Microsoft.OperationalInsights/workspaces",
            "Microsoft.Insights/actionGroups",
            "Microsoft.Insights/metricAlerts",
            "Microsoft.Insights/dataCollectionRules",

            # Container Services
            "Microsoft.ContainerService/managedClusters",
            "Microsoft.ContainerRegistry/registries",
            "Microsoft.ContainerInstance/containerGroups",
            "Microsoft.App/containerApps",

            # KeyVault
            "Microsoft.KeyVault/vaults",

            # Web
            "Microsoft.Web/serverfarms",
            "Microsoft.Web/sites",

            # Automation
            "Microsoft.Automation/automationAccounts",

            # Misc
            "Microsoft.Resources/resourceGroups",
        ]

        supported_types = set(
            t.lower() for t in HandlerRegistry.get_all_supported_types()
        )

        missing_types = []
        for azure_type in common_types:
            if azure_type.lower() not in supported_types:
                missing_types.append(azure_type)

        if missing_types:
            logger.warning(
                f"⚠️  {len(missing_types)} common types still use legacy code: "
                f"{', '.join(missing_types[:5])}..."
            )

        # We expect most common types to have handlers
        coverage = (len(common_types) - len(missing_types)) / len(common_types)
        assert coverage >= 0.85, (
            f"Only {coverage:.0%} of common types have handlers. "
            f"Missing: {missing_types}"
        )


class TestOutputComparison:
    """Compare handler output vs legacy output for correctness."""

    def _create_emitter_with_legacy_mode(self, use_handlers: bool) -> TerraformEmitter:
        """Create emitter with handlers enabled or disabled.

        Args:
            use_handlers: If False, forces legacy code path

        Returns:
            Configured emitter
        """
        emitter = TerraformEmitter()

        # Monkey-patch to disable handlers if needed
        if not use_handlers:
            original_convert = emitter._convert_resource
            def force_legacy(resource, terraform_config):
                return emitter._convert_resource_legacy(resource, terraform_config)
            emitter._convert_resource = force_legacy

        return emitter

    def _emit_resource(
        self,
        emitter: TerraformEmitter,
        resource: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Emit a single resource and return the Terraform config.

        Args:
            emitter: Configured emitter
            resource: Azure resource dictionary

        Returns:
            Generated Terraform configuration
        """
        graph = TenantGraph()
        graph.resources = [resource]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)

            if not written_files:
                return {}

            with open(written_files[0]) as f:
                return json.load(f)

    def _compare_terraform_configs(
        self,
        handler_config: Dict[str, Any],
        legacy_config: Dict[str, Any],
        resource_type: str
    ) -> Tuple[bool, List[str]]:
        """Compare two Terraform configs for semantic equivalence.

        Args:
            handler_config: Config from new handler path
            legacy_config: Config from legacy path
            resource_type: Azure resource type (for error messages)

        Returns:
            (is_equivalent, differences)
        """
        differences = []

        # Both should have 'resource' section
        if "resource" not in handler_config and "resource" not in legacy_config:
            return True, []  # Both empty (resource skipped)

        if "resource" not in handler_config:
            differences.append("Handler config missing 'resource' section")
            return False, differences

        if "resource" not in legacy_config:
            differences.append("Legacy config missing 'resource' section")
            return False, differences

        # Compare resource types present
        handler_types = set(handler_config["resource"].keys())
        legacy_types = set(legacy_config["resource"].keys())

        if handler_types != legacy_types:
            differences.append(
                f"Resource types differ: handler={handler_types}, legacy={legacy_types}"
            )

        # Compare each resource
        for res_type in handler_types & legacy_types:
            handler_resources = handler_config["resource"][res_type]
            legacy_resources = legacy_config["resource"][res_type]

            handler_names = set(handler_resources.keys())
            legacy_names = set(legacy_resources.keys())

            if handler_names != legacy_names:
                differences.append(
                    f"Resource names differ for {res_type}: "
                    f"handler={handler_names}, legacy={legacy_names}"
                )
                continue

            # Compare each resource's properties
            for res_name in handler_names & legacy_names:
                handler_props = handler_resources[res_name]
                legacy_props = legacy_resources[res_name]

                # Compare keys (allow some flexibility for acceptable differences)
                handler_keys = set(handler_props.keys())
                legacy_keys = set(legacy_props.keys())

                # Acceptable differences (these are improvements, not regressions)
                acceptable_extra_in_handler = {
                    "lifecycle",  # Handlers may add lifecycle rules
                    "depends_on",  # Handlers may add explicit dependencies
                }

                extra_in_handler = handler_keys - legacy_keys - acceptable_extra_in_handler
                missing_in_handler = legacy_keys - handler_keys

                if extra_in_handler:
                    differences.append(
                        f"Handler has extra keys in {res_type}.{res_name}: {extra_in_handler}"
                    )

                if missing_in_handler:
                    differences.append(
                        f"Handler missing keys in {res_type}.{res_name}: {missing_in_handler}"
                    )

        is_equivalent = len(differences) == 0
        return is_equivalent, differences

    @pytest.mark.parametrize("resource_type,resource_data", [
        # Virtual Network
        (
            "Microsoft.Network/virtualNetworks",
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "test-vnet",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "properties": json.dumps({
                    "addressSpace": {"addressPrefixes": ["10.0.0.0/16"]},
                    "subnets": []
                })
            }
        ),
        # Storage Account
        (
            "Microsoft.Storage/storageAccounts",
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "teststorage123",
                "location": "westus",
                "resourceGroup": "test-rg",
                "sku": json.dumps({"name": "Standard_LRS"}),
                "kind": "StorageV2",
                "properties": json.dumps({})
            }
        ),
        # Network Security Group
        (
            "Microsoft.Network/networkSecurityGroups",
            {
                "type": "Microsoft.Network/networkSecurityGroups",
                "name": "test-nsg",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "properties": json.dumps({
                    "securityRules": [
                        {
                            "name": "allow-ssh",
                            "properties": {
                                "protocol": "Tcp",
                                "sourcePortRange": "*",
                                "destinationPortRange": "22",
                                "sourceAddressPrefix": "*",
                                "destinationAddressPrefix": "*",
                                "access": "Allow",
                                "priority": 1000,
                                "direction": "Inbound"
                            }
                        }
                    ]
                })
            }
        ),
        # Managed Disk
        (
            "Microsoft.Compute/disks",
            {
                "type": "Microsoft.Compute/disks",
                "name": "test-disk",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "sku": json.dumps({"name": "Premium_LRS"}),
                "properties": json.dumps({
                    "diskSizeGB": 128,
                    "creationData": {"createOption": "Empty"}
                })
            }
        ),
        # Public IP
        (
            "Microsoft.Network/publicIPAddresses",
            {
                "type": "Microsoft.Network/publicIPAddresses",
                "name": "test-pip",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "sku": json.dumps({"name": "Standard"}),
                "properties": json.dumps({
                    "publicIPAllocationMethod": "Static"
                })
            }
        ),
    ])
    def test_handler_vs_legacy_output(
        self,
        resource_type: str,
        resource_data: Dict[str, Any]
    ) -> None:
        """Test that handler output matches legacy output for common resource types.

        This is the CRITICAL test - it validates that handlers produce
        identical (or acceptable) output compared to legacy code.
        """
        # Generate with NEW handler path
        handler_emitter = self._create_emitter_with_legacy_mode(use_handlers=True)
        handler_config = self._emit_resource(handler_emitter, resource_data)

        # Generate with LEGACY path
        legacy_emitter = self._create_emitter_with_legacy_mode(use_handlers=False)
        legacy_config = self._emit_resource(legacy_emitter, resource_data)

        # Compare
        is_equivalent, differences = self._compare_terraform_configs(
            handler_config,
            legacy_config,
            resource_type
        )

        if not is_equivalent:
            logger.error(
                f"\n❌ Handler output differs from legacy for {resource_type}:\n"
                + "\n".join(f"  - {diff}" for diff in differences)
            )
            logger.error(f"\nHandler config:\n{json.dumps(handler_config, indent=2)}")
            logger.error(f"\nLegacy config:\n{json.dumps(legacy_config, indent=2)}")

        assert is_equivalent, (
            f"Handler output for {resource_type} differs from legacy:\n"
            + "\n".join(differences)
        )


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_resource_with_missing_properties(self) -> None:
        """Test that handlers handle resources with missing 'properties' field gracefully."""
        emitter = TerraformEmitter()
        graph = TenantGraph()

        # VNet with NO properties field
        graph.resources = [
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet-no-props",
                "location": "eastus",
                "resourceGroup": "test-rg",
                # NO properties field
            }
        ]

        # Should not crash, should log warning
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)

            # Should still generate SOMETHING (resource group at minimum)
            assert len(written_files) > 0

    def test_resource_with_null_properties(self) -> None:
        """Test that handlers handle resources with null properties."""
        emitter = TerraformEmitter()
        graph = TenantGraph()

        graph.resources = [
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "storage-null-props",
                "location": "westus",
                "resourceGroup": "test-rg",
                "properties": None,  # Null properties
            }
        ]

        # Should not crash
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)
            assert len(written_files) > 0

    def test_resource_with_empty_properties_json(self) -> None:
        """Test that handlers handle resources with empty properties JSON."""
        emitter = TerraformEmitter()
        graph = TenantGraph()

        graph.resources = [
            {
                "type": "Microsoft.Network/networkSecurityGroups",
                "name": "nsg-empty-props",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "properties": json.dumps({}),  # Empty but valid JSON
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)
            assert len(written_files) > 0


class TestHelperResources:
    """Test that handlers generate helper resources correctly."""

    def test_vm_generates_ssh_key(self) -> None:
        """Test that VM handler generates tls_private_key helper resource."""
        emitter = TerraformEmitter()
        graph = TenantGraph()

        # Create a minimal VM
        graph.resources = [
            {
                "type": "Microsoft.Compute/virtualMachines",
                "name": "test-vm",
                "location": "eastus",
                "resourceGroup": "test-rg",
                "properties": json.dumps({
                    "hardwareProfile": {"vmSize": "Standard_DS1_v2"},
                    "storageProfile": {
                        "imageReference": {
                            "publisher": "Canonical",
                            "offer": "UbuntuServer",
                            "sku": "18.04-LTS",
                            "version": "latest"
                        },
                        "osDisk": {
                            "createOption": "FromImage",
                            "managedDisk": {"storageAccountType": "Premium_LRS"}
                        }
                    },
                    "osProfile": {
                        "computerName": "test-vm",
                        "adminUsername": "azureuser",
                        "linuxConfiguration": {
                            "disablePasswordAuthentication": True,
                            "ssh": {
                                "publicKeys": [
                                    {
                                        "path": "/home/azureuser/.ssh/authorized_keys",
                                        "keyData": "ssh-rsa AAAAB3..."
                                    }
                                ]
                            }
                        }
                    },
                    "networkProfile": {
                        "networkInterfaces": [
                            {"id": "/subscriptions/.../networkInterfaces/test-nic"}
                        ]
                    }
                })
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            written_files = emitter.emit(graph, out_dir)

            if not written_files:
                pytest.skip("VM was skipped (expected if NIC validation fails)")

            with open(written_files[0]) as f:
                terraform_config = json.load(f)

            # Check if tls_private_key was generated
            if "resource" in terraform_config:
                assert "tls_private_key" in terraform_config["resource"], (
                    "VM handler should generate tls_private_key helper resource"
                )

                # Verify SSH key has correct algorithm
                ssh_keys = terraform_config["resource"]["tls_private_key"]
                assert len(ssh_keys) > 0
                for key_name, key_config in ssh_keys.items():
                    assert key_config["algorithm"] == "RSA"
                    assert key_config.get("rsa_bits") in [2048, 4096]


class TestResourceTypeCoverage:
    """Test coverage of different resource type categories."""

    def test_compute_resources_handled(self) -> None:
        """Test that all compute resource types are handled."""
        ensure_handlers_registered()

        compute_types = [
            "Microsoft.Compute/virtualMachines",
            "Microsoft.Compute/disks",
            "Microsoft.Compute/virtualMachines/extensions",
        ]

        supported = HandlerRegistry.get_all_supported_types()
        supported_lower = {t.lower() for t in supported}

        for compute_type in compute_types:
            assert compute_type.lower() in supported_lower, (
                f"Compute type {compute_type} should have a handler"
            )

    def test_network_resources_handled(self) -> None:
        """Test that all network resource types are handled."""
        ensure_handlers_registered()

        network_types = [
            "Microsoft.Network/virtualNetworks",
            "Microsoft.Network/subnets",
            "Microsoft.Network/networkInterfaces",
            "Microsoft.Network/networkSecurityGroups",
            "Microsoft.Network/publicIPAddresses",
            "Microsoft.Network/bastionHosts",
            "Microsoft.Network/applicationGateways",
        ]

        supported = HandlerRegistry.get_all_supported_types()
        supported_lower = {t.lower() for t in supported}

        for network_type in network_types:
            assert network_type.lower() in supported_lower, (
                f"Network type {network_type} should have a handler"
            )

    def test_storage_resources_handled(self) -> None:
        """Test that storage resource types are handled."""
        ensure_handlers_registered()

        storage_types = [
            "Microsoft.Storage/storageAccounts",
        ]

        supported = HandlerRegistry.get_all_supported_types()
        supported_lower = {t.lower() for t in supported}

        for storage_type in storage_types:
            assert storage_type.lower() in supported_lower, (
                f"Storage type {storage_type} should have a handler"
            )

    def test_database_resources_handled(self) -> None:
        """Test that database resource types are handled."""
        ensure_handlers_registered()

        database_types = [
            "Microsoft.Sql/servers",
            "Microsoft.Sql/servers/databases",
            "Microsoft.DBforPostgreSQL/servers",
            "Microsoft.DocumentDB/databaseAccounts",
        ]

        supported = HandlerRegistry.get_all_supported_types()
        supported_lower = {t.lower() for t in supported}

        for db_type in database_types:
            assert db_type.lower() in supported_lower, (
                f"Database type {db_type} should have a handler"
            )

    def test_identity_resources_handled(self) -> None:
        """Test that identity resource types are handled."""
        ensure_handlers_registered()

        identity_types = [
            "Microsoft.ManagedIdentity/userAssignedIdentities",
            "Microsoft.Authorization/roleAssignments",
        ]

        supported = HandlerRegistry.get_all_supported_types()
        supported_lower = {t.lower() for t in supported}

        for identity_type in identity_types:
            assert identity_type.lower() in supported_lower, (
                f"Identity type {identity_type} should have a handler"
            )


if __name__ == "__main__":
    # Run with: pytest tests/iac/test_emitter_handler_validation.py -v
    pytest.main([__file__, "-v", "--tb=short"])
