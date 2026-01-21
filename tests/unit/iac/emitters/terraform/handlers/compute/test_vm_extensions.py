"""Unit tests for VM Extensions handler (Issue #326).

Tests OS-aware extension publisher/type mapping for Linux and Windows VMs.
"""

from unittest.mock import Mock

import pytest

from src.iac.emitters.terraform.context import EmitterContext
from src.iac.emitters.terraform.handlers.compute.vm_extensions import (
    VMExtensionHandler,
)


class TestVMExtensionHandler:
    """Tests for VM Extension handler with OS-aware mapping."""

    @pytest.fixture
    def handler(self):
        """Create handler instance."""
        return VMExtensionHandler()

    @pytest.fixture
    def linux_context(self):
        """Create context with Linux VM already emitted."""
        ctx = Mock(spec=EmitterContext)
        ctx.terraform_config = {
            "resource": {
                "azurerm_linux_virtual_machine": {
                    "test_linux_vm": {
                        "name": "test-linux-vm",
                        "location": "eastus",
                        "size": "Standard_DS1_v2",
                    }
                }
            }
        }
        return ctx

    @pytest.fixture
    def windows_context(self):
        """Create context with Windows VM already emitted."""
        ctx = Mock(spec=EmitterContext)
        ctx.terraform_config = {
            "resource": {
                "azurerm_windows_virtual_machine": {
                    "test_windows_vm": {
                        "name": "test-windows-vm",
                        "location": "eastus",
                        "size": "Standard_DS1_v2",
                    }
                }
            }
        }
        return ctx

    @pytest.fixture
    def base_extension_resource(self):
        """Base extension resource structure."""
        return {
            "id": "/subscriptions/sub-12345/resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/test-vm/extensions/customscript",
            "name": "test-linux-vm/customscript",
            "type": "Microsoft.Compute/virtualMachines/extensions",
            "location": "eastus",
            "properties": {
                "publisher": "Microsoft.Compute",
                "type": "CustomScriptExtension",
                "typeHandlerVersion": "1.10",
                "autoUpgradeMinorVersion": True,
                "settings": {"script": "echo 'test'"},
            },
        }

    # ========== CustomScriptExtension Tests ==========

    def test_customscript_linux_mapping(
        self, handler, linux_context, base_extension_resource
    ):
        """Test CustomScriptExtension mapped to Linux publisher/type."""
        base_extension_resource["properties"]["publisher"] = "Microsoft.Compute"
        base_extension_resource["properties"]["type"] = "CustomScriptExtension"

        tf_type, safe_name, config = handler.emit(
            base_extension_resource, linux_context
        )

        # Verify Linux mapping applied
        assert config["publisher"] == "Microsoft.Azure.Extensions"
        assert config["type"] == "CustomScript"
        assert config["type_handler_version"] == "2.1"
        assert tf_type == "azurerm_virtual_machine_extension"

    def test_customscript_windows_mapping(
        self, handler, windows_context, base_extension_resource
    ):
        """Test CustomScriptExtension mapped to Windows publisher/type."""
        base_extension_resource["name"] = "test-windows-vm/customscript"
        base_extension_resource["properties"]["publisher"] = (
            "Microsoft.Azure.Extensions"
        )
        base_extension_resource["properties"]["type"] = "CustomScript"

        tf_type, safe_name, config = handler.emit(
            base_extension_resource, windows_context
        )

        # Verify Windows mapping applied
        assert config["publisher"] == "Microsoft.Compute"
        assert config["type"] == "CustomScriptExtension"
        assert config["type_handler_version"] == "1.10"

    # ========== DSC Extension Tests ==========

    def test_dsc_windows_mapping(
        self, handler, windows_context, base_extension_resource
    ):
        """Test DSC extension for Windows VM."""
        base_extension_resource["name"] = "test-windows-vm/dsc"
        base_extension_resource["properties"]["type"] = "DSC"
        base_extension_resource["properties"]["publisher"] = "WrongPublisher"

        tf_type, safe_name, config = handler.emit(
            base_extension_resource, windows_context
        )

        # Verify Windows DSC mapping
        assert config["publisher"] == "Microsoft.Powershell"
        assert config["type"] == "DSC"
        assert config["type_handler_version"] == "2.77"

    # ========== AADLogin Extension Tests ==========

    def test_aadlogin_linux_mapping(
        self, handler, linux_context, base_extension_resource
    ):
        """Test AADLogin extension for Linux VM."""
        base_extension_resource["properties"]["type"] = "AADSSHLoginForLinux"

        tf_type, safe_name, config = handler.emit(
            base_extension_resource, linux_context
        )

        # Verify Linux AADLogin mapping
        assert config["publisher"] == "Microsoft.Azure.ActiveDirectory"
        assert config["type"] == "AADSSHLoginForLinux"
        assert config["type_handler_version"] == "1.0"

    def test_aadlogin_windows_mapping(
        self, handler, windows_context, base_extension_resource
    ):
        """Test AADLogin extension for Windows VM."""
        base_extension_resource["name"] = "test-windows-vm/aadlogin"
        base_extension_resource["properties"]["type"] = "AADLoginForWindows"

        tf_type, safe_name, config = handler.emit(
            base_extension_resource, windows_context
        )

        # Verify Windows AADLogin mapping
        assert config["publisher"] == "Microsoft.Azure.ActiveDirectory"
        assert config["type"] == "AADLoginForWindows"
        assert config["type_handler_version"] == "1.0"

    # ========== AzureMonitorAgent Extension Tests ==========

    def test_azuremonitor_linux_mapping(
        self, handler, linux_context, base_extension_resource
    ):
        """Test AzureMonitorAgent extension for Linux VM."""
        base_extension_resource["properties"]["type"] = "AzureMonitorLinuxAgent"

        tf_type, safe_name, config = handler.emit(
            base_extension_resource, linux_context
        )

        # Verify Linux AzureMonitor mapping
        assert config["publisher"] == "Microsoft.Azure.Monitor"
        assert config["type"] == "AzureMonitorLinuxAgent"
        assert config["type_handler_version"] == "1.0"

    def test_azuremonitor_windows_mapping(
        self, handler, windows_context, base_extension_resource
    ):
        """Test AzureMonitorAgent extension for Windows VM."""
        base_extension_resource["name"] = "test-windows-vm/azuremonitor"
        base_extension_resource["properties"]["type"] = "AzureMonitorWindowsAgent"

        tf_type, safe_name, config = handler.emit(
            base_extension_resource, windows_context
        )

        # Verify Windows AzureMonitor mapping
        assert config["publisher"] == "Microsoft.Azure.Monitor"
        assert config["type"] == "AzureMonitorWindowsAgent"
        assert config["type_handler_version"] == "1.0"

    # ========== NetworkWatcherAgent Extension Tests ==========

    def test_networkwatcher_linux_mapping(
        self, handler, linux_context, base_extension_resource
    ):
        """Test NetworkWatcherAgent extension for Linux VM."""
        base_extension_resource["properties"]["type"] = "NetworkWatcherAgentLinux"

        tf_type, safe_name, config = handler.emit(
            base_extension_resource, linux_context
        )

        # Verify Linux NetworkWatcher mapping
        assert config["publisher"] == "Microsoft.Azure.NetworkWatcher"
        assert config["type"] == "NetworkWatcherAgentLinux"
        assert config["type_handler_version"] == "1.4"

    def test_networkwatcher_windows_mapping(
        self, handler, windows_context, base_extension_resource
    ):
        """Test NetworkWatcherAgent extension for Windows VM."""
        base_extension_resource["name"] = "test-windows-vm/networkwatcher"
        base_extension_resource["properties"]["type"] = "NetworkWatcherAgentWindows"

        tf_type, safe_name, config = handler.emit(
            base_extension_resource, windows_context
        )

        # Verify Windows NetworkWatcher mapping
        assert config["publisher"] == "Microsoft.Azure.NetworkWatcher"
        assert config["type"] == "NetworkWatcherAgentWindows"
        assert config["type_handler_version"] == "1.4"

    # ========== Property Preservation Tests ==========

    def test_preserves_settings(self, handler, linux_context, base_extension_resource):
        """Test that settings are preserved during mapping."""
        base_extension_resource["properties"]["settings"] = {
            "script": "echo 'complex settings'",
            "args": ["arg1", "arg2"],
        }

        tf_type, safe_name, config = handler.emit(
            base_extension_resource, linux_context
        )

        # Verify settings preserved
        assert "settings" in config
        assert "script" in config["settings"]

    def test_preserves_protected_settings(
        self, handler, linux_context, base_extension_resource
    ):
        """Test that protectedSettings are preserved during mapping."""
        base_extension_resource["properties"]["protectedSettings"] = {
            "secret": "very-secret-value"  # pragma: allowlist secret
        }

        tf_type, safe_name, config = handler.emit(
            base_extension_resource, linux_context
        )

        # Verify protectedSettings preserved
        assert "protected_settings" in config

    def test_preserves_auto_upgrade(
        self, handler, linux_context, base_extension_resource
    ):
        """Test that autoUpgradeMinorVersion is preserved during mapping."""
        base_extension_resource["properties"]["autoUpgradeMinorVersion"] = False

        tf_type, safe_name, config = handler.emit(
            base_extension_resource, linux_context
        )

        # Verify autoUpgrade preserved
        assert config["auto_upgrade_minor_version"] is False

    # ========== Fallback Tests ==========

    def test_unmapped_extension_fallback(
        self, handler, linux_context, base_extension_resource
    ):
        """Test that unmapped extensions use original metadata."""
        base_extension_resource["properties"]["publisher"] = "ThirdParty.Publisher"
        base_extension_resource["properties"]["type"] = "CustomExtension"
        base_extension_resource["properties"]["typeHandlerVersion"] = "1.0"

        tf_type, safe_name, config = handler.emit(
            base_extension_resource, linux_context
        )

        # Verify original metadata preserved for unmapped extension
        assert config["publisher"] == "ThirdParty.Publisher"
        assert config["type"] == "CustomExtension"
        assert config["type_handler_version"] == "1.0"

    # ========== Error Cases ==========

    def test_skips_extension_missing_parent_vm(self, handler, base_extension_resource):
        """Test that extension is skipped if parent VM not found."""
        empty_context = Mock(spec=EmitterContext)
        empty_context.terraform_config = {"resource": {}}

        result = handler.emit(base_extension_resource, empty_context)

        # Should return None when parent VM not found
        assert result is None

    def test_skips_malformed_extension_name(self, handler, linux_context):
        """Test that extension with malformed name is skipped."""
        malformed_resource = {
            "name": "invalid-name-no-slash",
            "type": "Microsoft.Compute/virtualMachines/extensions",
            "properties": {"publisher": "Test", "type": "Test"},
        }

        result = handler.emit(malformed_resource, linux_context)

        # Should return None for malformed name
        assert result is None
