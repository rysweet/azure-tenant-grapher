"""Tests for VM disk sanitization in ARM templates (Issue #389).

This module tests that managedDisk.id references are removed from VM
storageProfile while preserving valid disk configuration properties.
"""

import json
import tempfile
from pathlib import Path

from src.iac.emitters.arm_emitter import ArmEmitter
from src.iac.traverser import TenantGraph


def test_vm_osdisk_manageddisk_id_removed():
    """Test that osDisk.managedDisk.id is removed from ARM template."""
    emitter = ArmEmitter()
    graph = TenantGraph()
    graph.resources = [
        {
            "type": "Microsoft.Compute/virtualMachines",
            "name": "testvm",
            "location": "eastus",
            "properties": {
                "storageProfile": {
                    "osDisk": {
                        "name": "testvm_OsDisk_1",
                        "caching": "ReadWrite",
                        "createOption": "FromImage",
                        "managedDisk": {
                            "id": "/subscriptions/xxx/resourceGroups/yyy/providers/Microsoft.Compute/disks/testvm_OsDisk_1",
                            "storageAccountType": "Premium_LRS",
                        },
                    }
                }
            },
        }
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        out_dir = Path(temp_dir)
        files = emitter.emit(graph, out_dir)

        with open(files[0]) as f:
            template = json.load(f)

        vm_resource = next(
            r
            for r in template["resources"]
            if r["type"] == "Microsoft.Compute/virtualMachines"
        )
        os_disk = vm_resource["properties"]["storageProfile"]["osDisk"]

        # Verify managedDisk.id is removed
        assert "id" not in os_disk["managedDisk"], "managedDisk.id should be removed"

        # Verify storageAccountType is preserved
        assert os_disk["managedDisk"]["storageAccountType"] == "Premium_LRS", (
            "storageAccountType should be preserved"
        )

        # Verify other osDisk properties are preserved
        assert os_disk["name"] == "testvm_OsDisk_1"
        assert os_disk["caching"] == "ReadWrite"
        assert os_disk["createOption"] == "FromImage"


def test_vm_datadisks_manageddisk_id_removed():
    """Test that dataDisks[*].managedDisk.id is removed from ARM template."""
    emitter = ArmEmitter()
    graph = TenantGraph()
    graph.resources = [
        {
            "type": "Microsoft.Compute/virtualMachines",
            "name": "testvm",
            "location": "eastus",
            "properties": {
                "storageProfile": {
                    "dataDisks": [
                        {
                            "lun": 0,
                            "name": "testvm_DataDisk_0",
                            "caching": "None",
                            "createOption": "Attach",
                            "managedDisk": {
                                "id": "/subscriptions/xxx/resourceGroups/yyy/providers/Microsoft.Compute/disks/testvm_DataDisk_0",
                                "storageAccountType": "Standard_LRS",
                            },
                        },
                        {
                            "lun": 1,
                            "name": "testvm_DataDisk_1",
                            "caching": "ReadOnly",
                            "createOption": "Attach",
                            "managedDisk": {
                                "id": "/subscriptions/xxx/resourceGroups/yyy/providers/Microsoft.Compute/disks/testvm_DataDisk_1",
                                "storageAccountType": "Premium_LRS",
                            },
                        },
                    ]
                }
            },
        }
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        out_dir = Path(temp_dir)
        files = emitter.emit(graph, out_dir)

        with open(files[0]) as f:
            template = json.load(f)

        vm_resource = next(
            r
            for r in template["resources"]
            if r["type"] == "Microsoft.Compute/virtualMachines"
        )
        data_disks = vm_resource["properties"]["storageProfile"]["dataDisks"]

        # Verify both dataDisks have managedDisk.id removed
        for disk in data_disks:
            assert "id" not in disk["managedDisk"], (
                f"managedDisk.id should be removed from disk lun {disk['lun']}"
            )
            assert "storageAccountType" in disk["managedDisk"], (
                f"storageAccountType should be preserved for disk lun {disk['lun']}"
            )

        # Verify specific disk properties are preserved
        assert data_disks[0]["lun"] == 0
        assert data_disks[0]["managedDisk"]["storageAccountType"] == "Standard_LRS"
        assert data_disks[1]["lun"] == 1
        assert data_disks[1]["managedDisk"]["storageAccountType"] == "Premium_LRS"


def test_vm_complete_disk_sanitization():
    """Test VM with both osDisk and dataDisks - verify complete sanitization."""
    emitter = ArmEmitter()
    graph = TenantGraph()
    graph.resources = [
        {
            "type": "Microsoft.Compute/virtualMachines",
            "name": "testvm",
            "location": "eastus",
            "properties": {
                "storageProfile": {
                    "osDisk": {
                        "name": "testvm_OsDisk_1",
                        "caching": "ReadWrite",
                        "createOption": "FromImage",
                        "managedDisk": {
                            "id": "/subscriptions/xxx/resourceGroups/yyy/providers/Microsoft.Compute/disks/testvm_OsDisk_1",
                            "storageAccountType": "Premium_LRS",
                        },
                    },
                    "dataDisks": [
                        {
                            "lun": 0,
                            "name": "testvm_DataDisk_0",
                            "caching": "None",
                            "createOption": "Attach",
                            "managedDisk": {
                                "id": "/subscriptions/xxx/resourceGroups/yyy/providers/Microsoft.Compute/disks/testvm_DataDisk_0",
                                "storageAccountType": "Standard_LRS",
                            },
                        }
                    ],
                }
            },
        }
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        out_dir = Path(temp_dir)
        files = emitter.emit(graph, out_dir)

        with open(files[0]) as f:
            template = json.load(f)

        vm_resource = next(
            r
            for r in template["resources"]
            if r["type"] == "Microsoft.Compute/virtualMachines"
        )
        storage_profile = vm_resource["properties"]["storageProfile"]

        # Verify osDisk sanitization
        assert "id" not in storage_profile["osDisk"]["managedDisk"]
        assert (
            storage_profile["osDisk"]["managedDisk"]["storageAccountType"]
            == "Premium_LRS"
        )

        # Verify dataDisks sanitization
        assert "id" not in storage_profile["dataDisks"][0]["managedDisk"]
        assert (
            storage_profile["dataDisks"][0]["managedDisk"]["storageAccountType"]
            == "Standard_LRS"
        )


def test_vm_without_manageddisk_unchanged():
    """Test that VM without managedDisk fields is unchanged."""
    emitter = ArmEmitter()
    graph = TenantGraph()
    graph.resources = [
        {
            "type": "Microsoft.Compute/virtualMachines",
            "name": "testvm",
            "location": "eastus",
            "properties": {
                "storageProfile": {
                    "osDisk": {
                        "name": "testvm_OsDisk_1",
                        "caching": "ReadWrite",
                        "createOption": "FromImage",
                    }
                }
            },
        }
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        out_dir = Path(temp_dir)
        files = emitter.emit(graph, out_dir)

        with open(files[0]) as f:
            template = json.load(f)

        vm_resource = next(
            r
            for r in template["resources"]
            if r["type"] == "Microsoft.Compute/virtualMachines"
        )
        os_disk = vm_resource["properties"]["storageProfile"]["osDisk"]

        # Verify osDisk properties are unchanged
        assert os_disk["name"] == "testvm_OsDisk_1"
        assert os_disk["caching"] == "ReadWrite"
        assert os_disk["createOption"] == "FromImage"
        assert "managedDisk" not in os_disk


def test_vm_without_storageprofile_unchanged():
    """Test that VM without storageProfile is unchanged."""
    emitter = ArmEmitter()
    graph = TenantGraph()
    graph.resources = [
        {
            "type": "Microsoft.Compute/virtualMachines",
            "name": "testvm",
            "location": "eastus",
            "properties": {"hardwareProfile": {"vmSize": "Standard_DS2_v2"}},
        }
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        out_dir = Path(temp_dir)
        files = emitter.emit(graph, out_dir)

        with open(files[0]) as f:
            template = json.load(f)

        vm_resource = next(
            r
            for r in template["resources"]
            if r["type"] == "Microsoft.Compute/virtualMachines"
        )

        # Verify VM properties are unchanged
        assert "hardwareProfile" in vm_resource["properties"]
        assert "storageProfile" not in vm_resource["properties"]


def test_arm_template_deployable_format():
    """Test that generated ARM template with sanitized VM is valid and deployable."""
    emitter = ArmEmitter()
    graph = TenantGraph()
    graph.resources = [
        {
            "type": "Microsoft.Compute/virtualMachines",
            "name": "testvm",
            "location": "eastus",
            "properties": {
                "storageProfile": {
                    "osDisk": {
                        "name": "testvm_OsDisk_1",
                        "caching": "ReadWrite",
                        "createOption": "FromImage",
                        "managedDisk": {
                            "id": "/subscriptions/xxx/resourceGroups/yyy/providers/Microsoft.Compute/disks/testvm_OsDisk_1",
                            "storageAccountType": "Premium_LRS",
                        },
                    }
                }
            },
        }
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        out_dir = Path(temp_dir)
        files = emitter.emit(graph, out_dir)

        with open(files[0]) as f:
            template = json.load(f)

        # Verify ARM template is valid
        assert emitter.validate_template(template), "Generated template should be valid"

        # Verify no managedDisk.id in any VM resource
        for resource in template["resources"]:
            if resource["type"] == "Microsoft.Compute/virtualMachines":
                storage_profile = resource.get("properties", {}).get(
                    "storageProfile", {}
                )

                # Check osDisk
                os_disk = storage_profile.get("osDisk", {})
                if "managedDisk" in os_disk:
                    assert "id" not in os_disk["managedDisk"], (
                        "osDisk.managedDisk.id must not be present"
                    )

                # Check dataDisks
                for data_disk in storage_profile.get("dataDisks", []):
                    if "managedDisk" in data_disk:
                        assert "id" not in data_disk["managedDisk"], (
                            "dataDisk.managedDisk.id must not be present"
                        )
