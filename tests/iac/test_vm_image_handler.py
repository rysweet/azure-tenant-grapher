"""Tests for VM Image handler.

Tests the VMImageHandler for Microsoft.Compute/images -> azurerm_image conversion.
"""

import json

from src.iac.emitters.terraform.context import EmitterContext
from src.iac.emitters.terraform.handlers.compute.vm_image import VMImageHandler


class TestVMImageHandler:
    """Test VM Image handler basic functionality."""

    def test_handler_registration(self):
        """Test handler is registered for Microsoft.Compute/images."""
        handler = VMImageHandler()
        assert "Microsoft.Compute/images" in handler.HANDLED_TYPES
        assert "azurerm_image" in handler.TERRAFORM_TYPES

    def test_can_handle_vm_images(self):
        """Test handler can handle Microsoft.Compute/images type."""
        assert VMImageHandler.can_handle("Microsoft.Compute/images")
        assert VMImageHandler.can_handle("microsoft.compute/images")  # Case-insensitive
        assert not VMImageHandler.can_handle("Microsoft.Compute/virtualMachines")


class TestBasicImageConversion:
    """Test basic VM image conversion scenarios."""

    def test_linux_image_with_required_fields(self):
        """Test converting a minimal Linux VM image."""
        handler = VMImageHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/images/ubuntu-custom",
            "name": "ubuntu-custom",
            "type": "Microsoft.Compute/images",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "storageProfile": {
                        "osDisk": {
                            "osType": "Linux",
                            "osState": "Generalized",
                        }
                    }
                }
            ),
        }

        tf_type, tf_name, config = handler.emit(resource, context)

        assert tf_type == "azurerm_image"
        assert tf_name == "ubuntu_custom"
        assert config["name"] == "ubuntu-custom"
        assert config["location"] == "eastus"
        assert config["resource_group_name"] == "test-rg"
        assert config["os_disk"]["os_type"] == "Linux"
        assert config["os_disk"]["os_state"] == "Generalized"

    def test_windows_image_with_required_fields(self):
        """Test converting a minimal Windows VM image."""
        handler = VMImageHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/images/windows-2022",
            "name": "windows-2022",
            "type": "Microsoft.Compute/images",
            "location": "westus2",
            "resource_group": "images-rg",
            "properties": json.dumps(
                {
                    "storageProfile": {
                        "osDisk": {
                            "osType": "Windows",
                            "osState": "Generalized",
                        }
                    }
                }
            ),
        }

        tf_type, tf_name, config = handler.emit(resource, context)

        assert tf_type == "azurerm_image"
        assert tf_name == "windows_2022"
        assert config["os_disk"]["os_type"] == "Windows"
        assert config["os_disk"]["os_state"] == "Generalized"

    def test_specialized_image(self):
        """Test converting a specialized (non-generalized) VM image."""
        handler = VMImageHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/images/specialized-vm",
            "name": "specialized-vm",
            "type": "Microsoft.Compute/images",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "storageProfile": {
                        "osDisk": {
                            "osType": "Linux",
                            "osState": "Specialized",
                        }
                    }
                }
            ),
        }

        tf_type, tf_name, config = handler.emit(resource, context)

        assert config["os_disk"]["os_state"] == "Specialized"


class TestSourceVMReference:
    """Test source virtual machine reference mapping."""

    def test_image_with_source_vm_id(self):
        """Test image created from source VM includes source_virtual_machine_id."""
        handler = VMImageHandler()
        context = EmitterContext()

        source_vm_id = "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/source-vm"

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/images/vm-image",
            "name": "vm-image",
            "type": "Microsoft.Compute/images",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "sourceVirtualMachine": {"id": source_vm_id},
                    "storageProfile": {
                        "osDisk": {
                            "osType": "Linux",
                            "osState": "Generalized",
                        }
                    },
                }
            ),
        }

        tf_type, tf_name, config = handler.emit(resource, context)

        assert "source_virtual_machine_id" in config
        assert config["source_virtual_machine_id"] == source_vm_id

    def test_image_without_source_vm(self):
        """Test image created from VHD doesn't include source_virtual_machine_id."""
        handler = VMImageHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/images/vhd-image",
            "name": "vhd-image",
            "type": "Microsoft.Compute/images",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "storageProfile": {
                        "osDisk": {
                            "osType": "Linux",
                            "osState": "Generalized",
                            "blobUri": "https://storage.blob.core.windows.net/vhds/disk.vhd",
                        }
                    }
                }
            ),
        }

        tf_type, tf_name, config = handler.emit(resource, context)

        assert "source_virtual_machine_id" not in config
        assert (
            config["os_disk"]["blob_uri"]
            == "https://storage.blob.core.windows.net/vhds/disk.vhd"
        )


class TestOSDiskConfiguration:
    """Test OS disk configuration mapping."""

    def test_os_disk_with_size(self):
        """Test OS disk with size_gb specified."""
        handler = VMImageHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/images/test-image",
            "name": "test-image",
            "type": "Microsoft.Compute/images",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "storageProfile": {
                        "osDisk": {
                            "osType": "Linux",
                            "osState": "Generalized",
                            "diskSizeGB": 64,
                        }
                    }
                }
            ),
        }

        tf_type, tf_name, config = handler.emit(resource, context)

        assert config["os_disk"]["size_gb"] == 64

    def test_os_disk_with_blob_uri(self):
        """Test OS disk with VHD blob URI."""
        handler = VMImageHandler()
        context = EmitterContext()

        blob_uri = "https://mystorage.blob.core.windows.net/vhds/os-disk.vhd"

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/images/test-image",
            "name": "test-image",
            "type": "Microsoft.Compute/images",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "storageProfile": {
                        "osDisk": {
                            "osType": "Linux",
                            "osState": "Generalized",
                            "blobUri": blob_uri,
                            "diskSizeGB": 32,
                        }
                    }
                }
            ),
        }

        tf_type, tf_name, config = handler.emit(resource, context)

        assert config["os_disk"]["blob_uri"] == blob_uri
        assert config["os_disk"]["size_gb"] == 32


class TestDataDisks:
    """Test data disk configuration mapping."""

    def test_image_with_single_data_disk(self):
        """Test image with one data disk."""
        handler = VMImageHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/images/test-image",
            "name": "test-image",
            "type": "Microsoft.Compute/images",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "storageProfile": {
                        "osDisk": {
                            "osType": "Linux",
                            "osState": "Generalized",
                        },
                        "dataDisks": [
                            {
                                "lun": 0,
                                "diskSizeGB": 128,
                            }
                        ],
                    }
                }
            ),
        }

        tf_type, tf_name, config = handler.emit(resource, context)

        assert "data_disk" in config
        assert len(config["data_disk"]) == 1
        assert config["data_disk"][0]["lun"] == 0
        assert config["data_disk"][0]["size_gb"] == 128

    def test_image_with_multiple_data_disks(self):
        """Test image with multiple data disks."""
        handler = VMImageHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/images/test-image",
            "name": "test-image",
            "type": "Microsoft.Compute/images",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "storageProfile": {
                        "osDisk": {
                            "osType": "Linux",
                            "osState": "Generalized",
                        },
                        "dataDisks": [
                            {
                                "lun": 0,
                                "diskSizeGB": 128,
                            },
                            {
                                "lun": 1,
                                "diskSizeGB": 256,
                            },
                            {
                                "lun": 2,
                                "diskSizeGB": 512,
                                "blobUri": "https://storage.blob.core.windows.net/vhds/data-disk-2.vhd",
                            },
                        ],
                    }
                }
            ),
        }

        tf_type, tf_name, config = handler.emit(resource, context)

        assert len(config["data_disk"]) == 3
        assert config["data_disk"][0]["lun"] == 0
        assert config["data_disk"][0]["size_gb"] == 128
        assert config["data_disk"][1]["lun"] == 1
        assert config["data_disk"][1]["size_gb"] == 256
        assert config["data_disk"][2]["lun"] == 2
        assert config["data_disk"][2]["size_gb"] == 512
        assert (
            config["data_disk"][2]["blob_uri"]
            == "https://storage.blob.core.windows.net/vhds/data-disk-2.vhd"
        )

    def test_image_without_data_disks(self):
        """Test image with no data disks."""
        handler = VMImageHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/images/test-image",
            "name": "test-image",
            "type": "Microsoft.Compute/images",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "storageProfile": {
                        "osDisk": {
                            "osType": "Linux",
                            "osState": "Generalized",
                        }
                    }
                }
            ),
        }

        tf_type, tf_name, config = handler.emit(resource, context)

        assert "data_disk" not in config


class TestZoneResilienceAndHyperV:
    """Test zone resilience and Hyper-V generation mapping."""

    def test_zone_resilient_image(self):
        """Test image with zone resilience enabled."""
        handler = VMImageHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/images/test-image",
            "name": "test-image",
            "type": "Microsoft.Compute/images",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "storageProfile": {
                        "osDisk": {
                            "osType": "Linux",
                            "osState": "Generalized",
                        },
                        "zoneResilient": True,
                    }
                }
            ),
        }

        tf_type, tf_name, config = handler.emit(resource, context)

        assert "zone_resilient" in config
        assert config["zone_resilient"] is True

    def test_non_zone_resilient_image(self):
        """Test image without zone resilience."""
        handler = VMImageHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/images/test-image",
            "name": "test-image",
            "type": "Microsoft.Compute/images",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "storageProfile": {
                        "osDisk": {
                            "osType": "Linux",
                            "osState": "Generalized",
                        }
                    }
                }
            ),
        }

        tf_type, tf_name, config = handler.emit(resource, context)

        assert "zone_resilient" not in config

    def test_hyper_v_generation_v2(self):
        """Test image with Hyper-V generation V2."""
        handler = VMImageHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/images/test-image",
            "name": "test-image",
            "type": "Microsoft.Compute/images",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "hyperVGeneration": "V2",
                    "storageProfile": {
                        "osDisk": {
                            "osType": "Linux",
                            "osState": "Generalized",
                        }
                    },
                }
            ),
        }

        tf_type, tf_name, config = handler.emit(resource, context)

        assert "hyper_v_generation" in config
        assert config["hyper_v_generation"] == "V2"

    def test_hyper_v_generation_v1(self):
        """Test image with Hyper-V generation V1 (default)."""
        handler = VMImageHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/images/test-image",
            "name": "test-image",
            "type": "Microsoft.Compute/images",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "hyperVGeneration": "V1",
                    "storageProfile": {
                        "osDisk": {
                            "osType": "Linux",
                            "osState": "Generalized",
                        }
                    },
                }
            ),
        }

        tf_type, tf_name, config = handler.emit(resource, context)

        assert config["hyper_v_generation"] == "V1"


class TestTagsAndMetadata:
    """Test tags and metadata handling."""

    def test_image_with_tags(self):
        """Test image with tags."""
        handler = VMImageHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/images/test-image",
            "name": "test-image",
            "type": "Microsoft.Compute/images",
            "location": "eastus",
            "resource_group": "test-rg",
            "tags": {
                "environment": "production",
                "version": "1.0.0",
                "created_by": "atg",
            },
            "properties": json.dumps(
                {
                    "storageProfile": {
                        "osDisk": {
                            "osType": "Linux",
                            "osState": "Generalized",
                        }
                    }
                }
            ),
        }

        tf_type, tf_name, config = handler.emit(resource, context)

        assert "tags" in config
        assert config["tags"]["environment"] == "production"
        assert config["tags"]["version"] == "1.0.0"
        assert config["tags"]["created_by"] == "atg"


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_image_with_missing_os_disk(self):
        """Test image missing required osDisk returns None."""
        handler = VMImageHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/images/test-image",
            "name": "test-image",
            "type": "Microsoft.Compute/images",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps({"storageProfile": {}}),
        }

        result = handler.emit(resource, context)

        assert result is None

    def test_image_with_missing_os_type(self):
        """Test image missing required osType returns None."""
        handler = VMImageHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/images/test-image",
            "name": "test-image",
            "type": "Microsoft.Compute/images",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "storageProfile": {
                        "osDisk": {
                            "osState": "Generalized",
                        }
                    }
                }
            ),
        }

        result = handler.emit(resource, context)

        assert result is None

    def test_image_with_invalid_properties_json(self):
        """Test image with malformed properties JSON."""
        handler = VMImageHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/images/test-image",
            "name": "test-image",
            "type": "Microsoft.Compute/images",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": "not valid json {{{",
        }

        result = handler.emit(resource, context)

        assert result is None

    def test_image_name_sanitization(self):
        """Test that image names with special characters are sanitized."""
        handler = VMImageHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/images/my-image@v1.0",
            "name": "my-image@v1.0",
            "type": "Microsoft.Compute/images",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "storageProfile": {
                        "osDisk": {
                            "osType": "Linux",
                            "osState": "Generalized",
                        }
                    }
                }
            ),
        }

        tf_type, tf_name, config = handler.emit(resource, context)

        assert tf_name == "my_image_v1_0"  # Special chars replaced with underscores
