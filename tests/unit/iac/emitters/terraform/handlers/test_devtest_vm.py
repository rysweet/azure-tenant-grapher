"""Unit tests for DevTestLab VM handler (GAP-002).

Tests both Linux and Windows VM detection and Terraform emission.
"""

from unittest.mock import Mock

import pytest

from src.iac.emitters.terraform.context import EmitterContext
from src.iac.emitters.terraform.handlers.devtest.devtest_vm import DevTestVMHandler


class TestDevTestVMHandler:
    """Tests for DevTestLab Virtual Machine handler."""

    @pytest.fixture
    def handler(self):
        """Create handler instance."""
        return DevTestVMHandler()

    @pytest.fixture
    def context(self):
        """Create mock emitter context."""
        ctx = Mock(spec=EmitterContext)
        ctx.get_effective_subscription_id.return_value = "sub-12345"
        return ctx

    @pytest.fixture
    def base_vm_resource(self):
        """Base DevTestLab VM resource structure."""
        return {
            "id": "/subscriptions/sub-12345/resourceGroups/rg-test/providers/Microsoft.DevTestLab/labs/testlab/virtualMachines/testvm",
            "name": "testlab/testvm",
            "type": "Microsoft.DevTestLab/labs/virtualMachines",
            "location": "eastus",
            "properties": {
                "size": "Standard_DS1_v2",
                "userName": "azureuser",
                "storageType": "Standard",
                "labSubnetName": "default",
                "labVirtualNetworkId": "/subscriptions/sub-12345/resourceGroups/rg-test/providers/Microsoft.DevTestLab/labs/testlab/virtualnetworks/testlabVnet",
            },
        }

    # ========== Linux VM Tests ==========

    def test_emit_linux_vm_via_ostype(self, handler, context, base_vm_resource):
        """Test Linux VM emission when osType=Linux."""
        base_vm_resource["properties"]["galleryImageReference"] = {
            "osType": "Linux",
            "offer": "0001-com-ubuntu-server-jammy",
            "publisher": "Canonical",
            "sku": "22_04-lts-gen2",
            "version": "latest",
        }

        tf_type, safe_name, config = handler.emit(base_vm_resource, context)

        assert tf_type == "azurerm_dev_test_linux_virtual_machine"
        assert "ssh_key" in config
        assert "password" not in config
        assert config["ssh_key"] == f"var.devtest_vm_ssh_key_{safe_name}"

    def test_emit_linux_vm_via_offer(self, handler, context, base_vm_resource):
        """Test Linux VM detection via offer field (Ubuntu)."""
        base_vm_resource["properties"]["galleryImageReference"] = {
            "offer": "UbuntuServer",
            "publisher": "Canonical",
            "sku": "18.04-LTS",
            "version": "latest",
        }

        tf_type, safe_name, config = handler.emit(base_vm_resource, context)

        assert tf_type == "azurerm_dev_test_linux_virtual_machine"
        assert "ssh_key" in config
        assert "password" not in config

    def test_emit_linux_vm_centos(self, handler, context, base_vm_resource):
        """Test Linux VM detection for CentOS."""
        base_vm_resource["properties"]["galleryImageReference"] = {
            "osType": "Linux",
            "offer": "CentOS",
            "publisher": "OpenLogic",
            "sku": "7.5",
            "version": "latest",
        }

        tf_type, safe_name, config = handler.emit(base_vm_resource, context)

        assert tf_type == "azurerm_dev_test_linux_virtual_machine"
        assert "ssh_key" in config

    # ========== Windows VM Tests ==========

    def test_emit_windows_vm_via_ostype(self, handler, context, base_vm_resource):
        """Test Windows VM emission when osType=Windows."""
        base_vm_resource["properties"]["galleryImageReference"] = {
            "osType": "Windows",
            "offer": "WindowsServer",
            "publisher": "MicrosoftWindowsServer",
            "sku": "2022-Datacenter",
            "version": "latest",
        }

        tf_type, safe_name, config = handler.emit(base_vm_resource, context)

        assert tf_type == "azurerm_dev_test_windows_virtual_machine"
        assert "password" in config
        assert "ssh_key" not in config
        assert config["password"] == f"var.devtest_vm_password_{safe_name}"

    def test_emit_windows_vm_via_offer(self, handler, context, base_vm_resource):
        """Test Windows VM detection via offer field."""
        base_vm_resource["properties"]["galleryImageReference"] = {
            "offer": "WindowsServer",
            "publisher": "MicrosoftWindowsServer",
            "sku": "2019-Datacenter",
            "version": "latest",
        }

        tf_type, safe_name, config = handler.emit(base_vm_resource, context)

        assert tf_type == "azurerm_dev_test_windows_virtual_machine"
        assert "password" in config
        assert "ssh_key" not in config

    def test_emit_windows_vm_via_publisher(self, handler, context, base_vm_resource):
        """Test Windows VM detection via publisher field."""
        base_vm_resource["properties"]["galleryImageReference"] = {
            "offer": "custom-windows-image",
            "publisher": "MicrosoftWindowsServer",
            "sku": "custom",
            "version": "1.0.0",
        }

        tf_type, safe_name, config = handler.emit(base_vm_resource, context)

        assert tf_type == "azurerm_dev_test_windows_virtual_machine"
        assert "password" in config

    # ========== Common Configuration Tests ==========

    def test_vm_name_parsing(self, handler, context, base_vm_resource):
        """Test lab/vm name parsing from resource name."""
        base_vm_resource["name"] = "mylab/myvm"
        base_vm_resource["properties"]["galleryImageReference"] = {"osType": "Linux"}

        _, safe_name, config = handler.emit(base_vm_resource, context)

        assert config["lab_name"] == "mylab"
        assert config["name"] == "myvm"

    def test_vm_size_configuration(self, handler, context, base_vm_resource):
        """Test VM size is correctly extracted."""
        base_vm_resource["properties"]["size"] = "Standard_B2ms"
        base_vm_resource["properties"]["galleryImageReference"] = {"osType": "Linux"}

        _, _, config = handler.emit(base_vm_resource, context)

        assert config["size"] == "Standard_B2ms"

    def test_storage_type_configuration(self, handler, context, base_vm_resource):
        """Test storage type is correctly extracted."""
        base_vm_resource["properties"]["storageType"] = "Premium"
        base_vm_resource["properties"]["galleryImageReference"] = {"osType": "Linux"}

        _, _, config = handler.emit(base_vm_resource, context)

        assert config["storage_type"] == "Premium"

    def test_lab_virtual_network_configuration(
        self, handler, context, base_vm_resource
    ):
        """Test lab virtual network ID is included."""
        vnet_id = (
            "/subscriptions/sub-12345/resourceGroups/rg-test/providers/"
            "Microsoft.DevTestLab/labs/testlab/virtualnetworks/testlabVnet"
        )
        base_vm_resource["properties"]["labVirtualNetworkId"] = vnet_id
        base_vm_resource["properties"]["galleryImageReference"] = {"osType": "Linux"}

        _, _, config = handler.emit(base_vm_resource, context)

        assert config["lab_virtual_network_id"] == vnet_id

    # ========== Edge Cases ==========

    def test_default_to_linux_when_ostype_missing(
        self, handler, context, base_vm_resource
    ):
        """Test default to Linux VM when osType is ambiguous."""
        base_vm_resource["properties"]["galleryImageReference"] = {
            "offer": "custom-image",
            "publisher": "CustomPublisher",
            "sku": "1.0",
            "version": "latest",
        }

        tf_type, _, _ = handler.emit(base_vm_resource, context)

        # Default behavior: if unclear, emit Linux VM
        assert tf_type == "azurerm_dev_test_linux_virtual_machine"

    def test_case_insensitive_os_detection(self, handler, context, base_vm_resource):
        """Test OS detection is case-insensitive."""
        base_vm_resource["properties"]["galleryImageReference"] = {
            "osType": "WINDOWS",  # Uppercase
            "offer": "WindowsServer",
            "publisher": "MicrosoftWindowsServer",
        }

        tf_type, _, _ = handler.emit(base_vm_resource, context)

        assert tf_type == "azurerm_dev_test_windows_virtual_machine"

    def test_partial_publisher_match(self, handler, context, base_vm_resource):
        """Test Windows detection with partial publisher match."""
        base_vm_resource["properties"]["galleryImageReference"] = {
            "offer": "server-2022",
            "publisher": "microsoftwindowsserver",  # Lowercase
            "sku": "datacenter",
        }

        tf_type, _, _ = handler.emit(base_vm_resource, context)

        assert tf_type == "azurerm_dev_test_windows_virtual_machine"

    # ========== Regression Tests ==========

    def test_existing_linux_behavior_preserved(
        self, handler, context, base_vm_resource
    ):
        """Test that existing Linux VM emission behavior is preserved."""
        # This is the original test case - should still work
        base_vm_resource["properties"]["galleryImageReference"] = {
            "offer": "0001-com-ubuntu-server-jammy",
            "publisher": "Canonical",
            "sku": "22_04-lts-gen2",
            "version": "latest",
        }

        tf_type, safe_name, config = handler.emit(base_vm_resource, context)

        assert tf_type == "azurerm_dev_test_linux_virtual_machine"
        assert config["ssh_key"] == f"var.devtest_vm_ssh_key_{safe_name}"
        assert config["gallery_image_reference"]["publisher"] == "Canonical"

    def test_handler_type_registration(self, handler):
        """Test handler registers both Linux and Windows terraform types."""
        assert "azurerm_dev_test_linux_virtual_machine" in handler.TERRAFORM_TYPES
        assert "azurerm_dev_test_windows_virtual_machine" in handler.TERRAFORM_TYPES

    def test_handler_handles_correct_azure_type(self, handler):
        """Test handler is registered for DevTestLab VMs."""
        assert "Microsoft.DevTestLab/labs/virtualMachines" in handler.HANDLED_TYPES
