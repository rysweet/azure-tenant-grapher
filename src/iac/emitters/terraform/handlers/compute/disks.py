"""Managed Disk and Snapshot handlers for Terraform emission.

Handles: Microsoft.Compute/disks, Microsoft.Compute/snapshots
Emits: azurerm_managed_disk, azurerm_snapshot
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class ManagedDiskHandler(ResourceHandler):
    """Handler for Azure Managed Disks.

    Emits:
        - azurerm_managed_disk
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Compute/disks",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_managed_disk",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Azure Managed Disk to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        config = self.build_base_config(resource)

        # Storage account type (required)
        sku = properties.get("sku", {}) or resource.get("sku", {})
        storage_account_type = (
            sku.get("name", "Standard_LRS") if isinstance(sku, dict) else "Standard_LRS"
        )
        config["storage_account_type"] = storage_account_type

        # Create option (required)
        creation_data = properties.get("creationData", {})
        create_option = creation_data.get("createOption", "Empty")
        config["create_option"] = create_option

        # Disk size
        disk_size_gb = properties.get("diskSizeGB") or resource.get("diskSizeGB")
        if disk_size_gb:
            config["disk_size_gb"] = disk_size_gb

        # OS type (optional)
        os_type = properties.get("osType")
        if os_type:
            config["os_type"] = os_type

        logger.debug(f"Managed Disk '{resource_name}' emitted")

        return "azurerm_managed_disk", safe_name, config


@handler
class SnapshotHandler(ResourceHandler):
    """Handler for Azure Disk Snapshots.

    Emits:
        - azurerm_snapshot
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Compute/snapshots",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_snapshot",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Azure Snapshot to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        config = self.build_base_config(resource)

        # Create option (required)
        creation_data = properties.get("creationData", {})
        create_option = creation_data.get("createOption", "Copy")
        config["create_option"] = create_option

        # Source disk ID (for Copy create option)
        source_disk_id = creation_data.get("sourceResourceId")
        if source_disk_id:
            config["source_resource_id"] = source_disk_id

        logger.debug(f"Snapshot '{resource_name}' emitted")

        return "azurerm_snapshot", safe_name, config
