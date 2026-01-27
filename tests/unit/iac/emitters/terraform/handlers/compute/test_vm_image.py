"""Unit tests for VM Image handler cross-subscription validation (Issue #329).

Tests validation logic that skips VM Images with cross-subscription managed disk references.
These tests follow TDD methodology and are written BEFORE implementation.
"""

from unittest.mock import Mock

import pytest

from src.iac.emitters.terraform.context import EmitterContext
from src.iac.emitters.terraform.handlers.compute.vm_image import VMImageHandler


class TestVMImageHandler:
    """Tests for VM Image handler with cross-subscription validation."""

    @pytest.fixture
    def handler(self):
        """Create handler instance."""
        return VMImageHandler()

    @pytest.fixture
    def context_same_subscription(self):
        """Create context with target subscription matching image subscription."""
        ctx = Mock(spec=EmitterContext)
        ctx.target_subscription_id = "sub-12345"
        ctx.terraform_config = {"resource": {}}
        return ctx

    @pytest.fixture
    def context_different_subscription(self):
        """Create context with target subscription different from image subscription."""
        ctx = Mock(spec=EmitterContext)
        ctx.target_subscription_id = "sub-99999"
        ctx.terraform_config = {"resource": {}}
        return ctx

    @pytest.fixture
    def base_vm_image_resource(self):
        """Base VM Image resource structure with managed disk references."""
        return {
            "id": "/subscriptions/sub-12345/resourceGroups/rg-test/providers/Microsoft.Compute/images/test-image",
            "name": "test-image",
            "type": "Microsoft.Compute/images",
            "location": "eastus",
            "subscription_id": "sub-12345",
            "properties": {
                "storageProfile": {
                    "osDisk": {
                        "osType": "Linux",
                        "osState": "Generalized",
                        "managedDisk": {
                            "id": "/subscriptions/sub-12345/resourceGroups/rg-disks/providers/Microsoft.Compute/disks/os-disk"
                        },
                        "diskSizeGB": 30,
                    },
                    "dataDisks": [],
                    "zoneResilient": False,
                },
                "hyperVGeneration": "V1",
            },
        }

    # ========== Test Case 1: Valid same-subscription OS managed disk ==========

    def test_same_subscription_os_disk_emits_successfully(
        self, handler, context_same_subscription, base_vm_image_resource
    ):
        """Test that VM Image with OS disk in same subscription emits successfully.

        Scenario: OS disk subscription matches target subscription.
        Expected: Image should be emitted with proper configuration.
        """
        # OS disk is in same subscription as target (sub-12345)
        tf_type, safe_name, config = handler.emit(
            base_vm_image_resource, context_same_subscription
        )

        # Should emit successfully
        assert tf_type == "azurerm_image"
        assert safe_name == "test_image"
        assert "os_disk" in config
        assert config["os_disk"]["os_type"] == "Linux"
        assert config["os_disk"]["os_state"] == "Generalized"

    # ========== Test Case 2: Valid same-subscription with data disks ==========

    def test_same_subscription_with_data_disks_emits_successfully(
        self, handler, context_same_subscription, base_vm_image_resource
    ):
        """Test that VM Image with data disks in same subscription emits successfully.

        Scenario: Both OS and data disks are in same subscription as target.
        Expected: Image should be emitted with both OS and data disks.
        """
        # Add data disks in same subscription
        base_vm_image_resource["properties"]["storageProfile"]["dataDisks"] = [
            {
                "lun": 0,
                "managedDisk": {
                    "id": "/subscriptions/sub-12345/resourceGroups/rg-disks/providers/Microsoft.Compute/disks/data-disk-0"
                },
                "diskSizeGB": 128,
            },
            {
                "lun": 1,
                "managedDisk": {
                    "id": "/subscriptions/sub-12345/resourceGroups/rg-disks/providers/Microsoft.Compute/disks/data-disk-1"
                },
                "diskSizeGB": 256,
            },
        ]

        tf_type, _, config = handler.emit(
            base_vm_image_resource, context_same_subscription
        )

        # Should emit successfully with data disks
        assert tf_type == "azurerm_image"
        assert "data_disk" in config
        assert len(config["data_disk"]) == 2

    # ========== Test Case 3: Cross-subscription OS disk (should skip) ==========

    def test_cross_subscription_os_disk_skips_with_warning(
        self, handler, context_different_subscription, base_vm_image_resource, caplog
    ):
        """Test that VM Image with OS disk in different subscription is skipped.

        Scenario: OS disk subscription (sub-12345) differs from target (sub-99999).
        Expected: Should return None and log warning about cross-subscription reference.
        """
        import logging

        # OS disk is in sub-12345, but target is sub-99999
        with caplog.at_level(logging.WARNING):
            result = handler.emit(
                base_vm_image_resource, context_different_subscription
            )

        # Should skip emission
        assert result is None

        # Should log warning about cross-subscription OS disk
        assert any(
            "cross-subscription" in record.message.lower()
            and "os disk" in record.message.lower()
            for record in caplog.records
        )

    # ========== Test Case 4: Cross-subscription data disk (should skip) ==========

    def test_cross_subscription_data_disk_skips_with_warning(
        self, handler, context_different_subscription, base_vm_image_resource, caplog
    ):
        """Test that VM Image with data disk in different subscription is skipped.

        Scenario: OS disk in same subscription, but one data disk in different subscription.
        Expected: Should return None and log warning about cross-subscription data disk.
        """
        import logging

        # OS disk in target subscription, but data disk in different subscription
        base_vm_image_resource["properties"]["storageProfile"]["osDisk"]["managedDisk"][
            "id"
        ] = "/subscriptions/sub-99999/resourceGroups/rg-disks/providers/Microsoft.Compute/disks/os-disk"
        base_vm_image_resource["properties"]["storageProfile"]["dataDisks"] = [
            {
                "lun": 0,
                "managedDisk": {
                    "id": "/subscriptions/sub-99999/resourceGroups/rg-disks/providers/Microsoft.Compute/disks/data-disk-0"
                },
            },
            {
                "lun": 1,
                "managedDisk": {
                    "id": "/subscriptions/sub-12345/resourceGroups/rg-disks/providers/Microsoft.Compute/disks/data-disk-1"
                },
            },
        ]

        with caplog.at_level(logging.WARNING):
            result = handler.emit(
                base_vm_image_resource, context_different_subscription
            )

        # Should skip emission
        assert result is None

        # Should log warning about cross-subscription data disk
        assert any(
            "cross-subscription" in record.message.lower()
            and "data disk" in record.message.lower()
            for record in caplog.records
        )

    # ========== Test Case 5: Malformed disk ID (should skip) ==========

    def test_malformed_disk_id_skips_with_warning(
        self, handler, context_same_subscription, base_vm_image_resource, caplog
    ):
        """Test that VM Image with malformed managed disk ID is skipped.

        Scenario: Disk ID doesn't match expected format (no subscription segment).
        Expected: Should return None and log warning about malformed ID.
        """
        import logging

        # Malformed disk ID (missing /subscriptions/ segment)
        base_vm_image_resource["properties"]["storageProfile"]["osDisk"]["managedDisk"][
            "id"
        ] = "/resourceGroups/rg-disks/providers/Microsoft.Compute/disks/os-disk"

        with caplog.at_level(logging.WARNING):
            result = handler.emit(base_vm_image_resource, context_same_subscription)

        # Should skip emission
        assert result is None

        # Should log warning about malformed disk ID
        assert any(
            "malformed" in record.message.lower() or "invalid" in record.message.lower()
            for record in caplog.records
        )

    # ========== Test Case 6: VHD-based image (bypasses validation) ==========

    def test_vhd_based_image_bypasses_validation(
        self, handler, context_different_subscription, base_vm_image_resource
    ):
        """Test that VHD-based VM Image bypasses managed disk validation.

        Scenario: Image uses blobUri instead of managed disks.
        Expected: Should emit successfully without cross-subscription checks.
        """
        # Remove managedDisk, add blobUri instead
        base_vm_image_resource["properties"]["storageProfile"]["osDisk"].pop(
            "managedDisk", None
        )
        base_vm_image_resource["properties"]["storageProfile"]["osDisk"][
            "blobUri"
        ] = "https://storage.blob.core.windows.net/vhds/os-disk.vhd"

        tf_type, _safe_name, config = handler.emit(
            base_vm_image_resource, context_different_subscription
        )

        # Should emit successfully (VHD-based images don't need cross-subscription validation)
        assert tf_type == "azurerm_image"
        assert (
            config["os_disk"]["blob_uri"]
            == "https://storage.blob.core.windows.net/vhds/os-disk.vhd"
        )

    # ========== Test Case 7: Case-insensitive subscription comparison ==========

    def test_subscription_comparison_is_case_insensitive(
        self, handler, base_vm_image_resource
    ):
        """Test that subscription ID comparison is case-insensitive.

        Scenario: Disk subscription ID has different casing than target subscription.
        Expected: Should recognize as same subscription and emit successfully.
        """
        # Context with lowercase subscription ID
        ctx = Mock(spec=EmitterContext)
        ctx.target_subscription_id = "sub-12345"
        ctx.terraform_config = {"resource": {}}

        # Disk ID with uppercase subscription ID
        base_vm_image_resource["properties"]["storageProfile"]["osDisk"]["managedDisk"][
            "id"
        ] = "/subscriptions/SUB-12345/resourceGroups/rg-disks/providers/Microsoft.Compute/disks/os-disk"

        tf_type, _safe_name, config = handler.emit(base_vm_image_resource, ctx)

        # Should emit successfully (case-insensitive match)
        assert tf_type == "azurerm_image"
        assert "os_disk" in config

    # ========== Test Case 8: Empty data_disks array ==========

    def test_empty_data_disks_array_emits_successfully(
        self, handler, context_same_subscription, base_vm_image_resource
    ):
        """Test that VM Image with empty data_disks array emits successfully.

        Scenario: dataDisks is explicitly set to empty array.
        Expected: Should emit successfully with only OS disk configuration.
        """
        # Explicitly set empty data disks array
        base_vm_image_resource["properties"]["storageProfile"]["dataDisks"] = []

        tf_type, _safe_name, config = handler.emit(
            base_vm_image_resource, context_same_subscription
        )

        # Should emit successfully
        assert tf_type == "azurerm_image"
        assert "os_disk" in config
        assert "data_disk" not in config

    # ========== Additional Edge Cases ==========

    def test_missing_managed_disk_field_uses_blob_uri(
        self, handler, context_same_subscription, base_vm_image_resource
    ):
        """Test that missing managedDisk field doesn't break validation.

        Scenario: OS disk has neither managedDisk nor blobUri.
        Expected: Existing validation should handle this (not cross-subscription issue).
        """
        # Remove managedDisk field entirely
        base_vm_image_resource["properties"]["storageProfile"]["osDisk"].pop(
            "managedDisk", None
        )

        # This should be handled by existing validation, not cross-subscription validation
        # Existing code may skip or emit based on other validation rules
        result = handler.emit(base_vm_image_resource, context_same_subscription)

        # Test that cross-subscription validation doesn't interfere
        # Result may be None or valid config depending on existing validation
        # This test ensures no exceptions are raised
        assert result is None or isinstance(result, tuple)

    def test_data_disk_without_managed_disk_field(
        self, handler, context_same_subscription, base_vm_image_resource
    ):
        """Test that data disk without managedDisk field is handled gracefully.

        Scenario: Data disk with blobUri instead of managedDisk.
        Expected: Should not trigger cross-subscription validation.
        """
        base_vm_image_resource["properties"]["storageProfile"]["dataDisks"] = [
            {
                "lun": 0,
                "blobUri": "https://storage.blob.core.windows.net/vhds/data-disk.vhd",
                "diskSizeGB": 128,
            }
        ]

        tf_type, _safe_name, config = handler.emit(
            base_vm_image_resource, context_same_subscription
        )

        # Should emit successfully (VHD-based data disk)
        assert tf_type == "azurerm_image"
        assert "data_disk" in config

    # ========== Test Case 11: None target_subscription_id (should skip) ==========

    def test_none_target_subscription_skips_with_error(
        self, handler, base_vm_image_resource, caplog
    ):
        """Test that VM Image with None target_subscription_id is skipped.

        Scenario: Context has target_subscription_id set to None.
        Expected: Should return None and log error about missing target_subscription_id.
        """
        import logging

        # Create context with None target_subscription_id
        ctx = Mock(spec=EmitterContext)
        ctx.target_subscription_id = None
        ctx.terraform_config = {"resource": {}}

        with caplog.at_level(logging.ERROR):
            result = handler.emit(base_vm_image_resource, ctx)

        # Should skip emission
        assert result is None

        # Should log error about None target_subscription_id
        assert any(
            "target_subscription_id is none" in record.message.lower()
            for record in caplog.records
        )
