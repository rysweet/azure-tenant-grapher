"""VM Image handler for Terraform emission.

Handles: Microsoft.Compute/images
Emits: azurerm_image
"""

import logging
import re
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)

# Regex pattern to extract subscription ID from Azure resource IDs
SUBSCRIPTION_ID_PATTERN = re.compile(r"/subscriptions/([^/]+)/", re.IGNORECASE)


@handler
class VMImageHandler(ResourceHandler):
    """Handler for Azure VM Images.

    Emits:
        - azurerm_image
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Compute/images",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_image",
    }

    def _mask_subscription_id(self, subscription_id: str) -> str:
        """Mask subscription ID for logging (security hardening).

        Args:
            subscription_id: Full subscription ID

        Returns:
            Masked subscription ID showing first 8 chars only
        """
        if len(subscription_id) > 8:
            return f"{subscription_id[:8]}...***"
        return subscription_id

    def _extract_subscription_id(self, resource_id: str) -> Optional[str]:
        """Extract subscription ID from Azure resource ID.

        Args:
            resource_id: Azure resource ID (e.g., /subscriptions/sub-12345/resourceGroups/rg/...)

        Returns:
            Subscription ID if found, None otherwise
        """
        # DoS protection: reject excessively long resource IDs
        if len(resource_id) > 2048:
            logger.warning(
                f"Resource ID exceeds maximum length (2048 chars): {len(resource_id)} chars. Skipping."
            )
            return None

        match = SUBSCRIPTION_ID_PATTERN.search(resource_id)
        if match:
            return match.group(1).lower()
        return None

    def _validate_disk_subscription(
        self,
        resource_name: str,
        storage_profile: Dict[str, Any],
        target_subscription_id: Optional[str],
    ) -> bool:
        """Validate that all managed disks are in the target subscription.

        Args:
            resource_name: Name of the VM Image resource
            storage_profile: Storage profile from VM Image properties
            target_subscription_id: Target subscription ID for deployment (None if not set)

        Returns:
            True if validation passes, False if cross-subscription references found
        """
        # Fail secure if target_subscription_id is None
        if target_subscription_id is None:
            logger.error(
                f"VM Image '{resource_name}' cannot be validated: target_subscription_id is None. Skipping."
            )
            return False

        # Normalize target subscription ID to lowercase
        target_sub_id = target_subscription_id.lower()

        # Validate OS disk
        os_disk = storage_profile.get("osDisk", {})
        managed_disk = os_disk.get("managedDisk", {})
        disk_id = managed_disk.get("id")
        if disk_id:
            disk_sub_id = self._extract_subscription_id(disk_id)
            if disk_sub_id is None:
                logger.warning(
                    f"VM Image '{resource_name}' has malformed OS disk ID: {disk_id}. Skipping."
                )
                return False
            if disk_sub_id != target_sub_id:
                logger.warning(
                    f"VM Image '{resource_name}' references cross-subscription OS disk "
                    f"(disk subscription: {self._mask_subscription_id(disk_sub_id)}, "
                    f"target: {self._mask_subscription_id(target_sub_id)}). Skipping."
                )
                return False

        # Validate data disks
        data_disks = storage_profile.get("dataDisks", [])
        for idx, data_disk in enumerate(data_disks):
            if not isinstance(data_disk, dict):
                continue
            managed_disk = data_disk.get("managedDisk", {})
            disk_id = managed_disk.get("id")
            if disk_id:
                disk_sub_id = self._extract_subscription_id(disk_id)
                if disk_sub_id is None:
                    logger.warning(
                        f"VM Image '{resource_name}' has malformed data disk ID at index {idx}: {disk_id}. Skipping."
                    )
                    return False
                if disk_sub_id != target_sub_id:
                    logger.warning(
                        f"VM Image '{resource_name}' references cross-subscription data disk at index {idx} "
                        f"(disk subscription: {self._mask_subscription_id(disk_sub_id)}, "
                        f"target: {self._mask_subscription_id(target_sub_id)}). Skipping."
                    )
                    return False

        return True

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Azure VM Image to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        # Validate storage profile exists
        storage_profile = properties.get("storageProfile", {})
        if not storage_profile:
            logger.warning(
                f"VM Image '{resource_name}' missing storageProfile. Skipping."
            )
            return None

        # Validate OS disk configuration (required)
        os_disk = storage_profile.get("osDisk", {})
        if not os_disk:
            logger.warning(
                f"VM Image '{resource_name}' missing osDisk configuration. Skipping."
            )
            return None

        # Validate required OS disk fields
        os_type = os_disk.get("osType")
        os_state = os_disk.get("osState")

        if not os_type or not os_state:
            logger.warning(
                f"VM Image '{resource_name}' missing required osType or osState. Skipping."
            )
            return None

        # Validate context has target_subscription_id (defensive check)
        target_sub_id = getattr(context, "target_subscription_id", None)
        if target_sub_id is None:
            logger.error(
                f"VM Image '{resource_name}' cannot be emitted: context.target_subscription_id is None. Skipping."
            )
            return None

        # Validate managed disk subscriptions
        if not self._validate_disk_subscription(
            resource_name, storage_profile, target_sub_id
        ):
            return None

        # Build base configuration
        config = self.build_base_config(resource)

        # Source virtual machine ID (optional)
        source_vm = properties.get("sourceVirtualMachine", {})
        if source_vm and isinstance(source_vm, dict):
            source_vm_id = source_vm.get("id")
            if source_vm_id:
                config["source_virtual_machine_id"] = source_vm_id

        # OS disk configuration (required)
        os_disk_config = {
            "os_type": os_type,
            "os_state": os_state,
        }

        # Optional OS disk fields
        blob_uri = os_disk.get("blobUri")
        if blob_uri:
            os_disk_config["blob_uri"] = blob_uri

        disk_size_gb = os_disk.get("diskSizeGB")
        if disk_size_gb:
            os_disk_config["size_gb"] = disk_size_gb

        config["os_disk"] = os_disk_config

        # Data disks (optional)
        data_disks = storage_profile.get("dataDisks", [])
        if data_disks:
            data_disk_configs = []
            for data_disk in data_disks:
                if not isinstance(data_disk, dict):
                    continue

                data_disk_config = {}
                if (lun := data_disk.get("lun")) is not None:
                    data_disk_config["lun"] = lun
                if blob_uri := data_disk.get("blobUri"):
                    data_disk_config["blob_uri"] = blob_uri
                if size_gb := data_disk.get("diskSizeGB"):
                    data_disk_config["size_gb"] = size_gb

                if data_disk_config:
                    data_disk_configs.append(data_disk_config)

            if data_disk_configs:
                config["data_disk"] = data_disk_configs

        # Zone resilience (optional)
        zone_resilient = storage_profile.get("zoneResilient")
        if zone_resilient is not None:
            config["zone_resilient"] = zone_resilient

        # Hyper-V generation (optional)
        hyper_v_generation = properties.get("hyperVGeneration")
        if hyper_v_generation:
            config["hyper_v_generation"] = hyper_v_generation

        logger.debug(f"VM Image '{resource_name}' emitted")

        return "azurerm_image", safe_name, config
