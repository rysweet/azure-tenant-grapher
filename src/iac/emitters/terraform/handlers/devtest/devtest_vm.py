"""DevTest VM handler for Terraform emission.

Handles: Microsoft.DevTestLab/labs/virtualMachines
Emits: azurerm_dev_test_linux_virtual_machine
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class DevTestVMHandler(ResourceHandler):
    """Handler for DevTest Lab Virtual Machines.

    Emits:
        - azurerm_dev_test_linux_virtual_machine
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.DevTestLab/labs/virtualMachines",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_dev_test_linux_virtual_machine",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert DevTest VM to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        properties = self.parse_properties(resource)

        # Extract lab and VM names
        full_name = resource_name
        if "/" in full_name:
            lab_name = full_name.split("/")[0]
            vm_name = full_name.split("/")[1]
        else:
            lab_name = "unknown-lab"
            vm_name = full_name

        safe_name = self.sanitize_name(vm_name)

        config = self.build_base_config(resource)
        config["name"] = vm_name

        # VM properties
        size = properties.get("size", "Standard_DS1_v2")
        username = properties.get("userName", "labuser")
        storage_type = properties.get("storageType", "Standard")
        lab_subnet_name = properties.get("labSubnetName", "default")

        rg_name = self.get_resource_group(resource)
        sub_id = context.get_effective_subscription_id(resource)

        # Virtual network ID
        lab_virtual_network_id = properties.get("labVirtualNetworkId")
        if not lab_virtual_network_id:
            lab_virtual_network_id = (
                f"/subscriptions/{sub_id}/resourceGroups/{rg_name}/"
                f"providers/Microsoft.DevTestLab/labs/{lab_name}/"
                f"virtualnetworks/{lab_name}Vnet"
            )

        # Gallery image reference
        gallery_image_ref = properties.get("galleryImageReference", {})

        config.update(
            {
                "lab_name": lab_name,
                "size": size,
                "username": username,
                "storage_type": storage_type,
                "lab_subnet_name": lab_subnet_name,
                "lab_virtual_network_id": lab_virtual_network_id,
                "ssh_key": f"var.devtest_vm_ssh_key_{safe_name}",
                "gallery_image_reference": {
                    "offer": gallery_image_ref.get(
                        "offer", "0001-com-ubuntu-server-jammy"
                    ),
                    "publisher": gallery_image_ref.get("publisher", "Canonical"),
                    "sku": gallery_image_ref.get("sku", "22_04-lts-gen2"),
                    "version": gallery_image_ref.get("version", "latest"),
                },
            }
        )

        logger.debug(f"DevTest VM '{vm_name}' emitted for lab '{lab_name}'")

        return "azurerm_dev_test_linux_virtual_machine", safe_name, config
