"""VM Image handler for Terraform emission.

Handles: Microsoft.Compute/images
Emits: azurerm_image
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


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
        if data_disks and isinstance(data_disks, list) and len(data_disks) > 0:
            data_disk_configs = []
            for data_disk in data_disks:
                if not isinstance(data_disk, dict):
                    continue

                data_disk_config = {}

                # LUN is required for data disks
                lun = data_disk.get("lun")
                if lun is not None:
                    data_disk_config["lun"] = lun

                # Optional data disk fields
                data_blob_uri = data_disk.get("blobUri")
                if data_blob_uri:
                    data_disk_config["blob_uri"] = data_blob_uri

                data_disk_size_gb = data_disk.get("diskSizeGB")
                if data_disk_size_gb:
                    data_disk_config["size_gb"] = data_disk_size_gb

                if data_disk_config:  # Only add if has at least one field
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
