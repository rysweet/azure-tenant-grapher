"""DevTest Lab Virtual Network handler for Terraform emission.

Handles: Microsoft.DevTestLab/labs/virtualnetworks
Emits: azurerm_dev_test_virtual_network
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class DevTestVirtualNetworkHandler(ResourceHandler):
    """Handler for Azure DevTest Lab Virtual Networks.

    Emits:
        - azurerm_dev_test_virtual_network
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.DevTestLab/labs/virtualnetworks",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_dev_test_virtual_network",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert DevTest Lab Virtual Network to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        properties = self.parse_properties(resource)

        # Extract lab and vnet names
        # Format: lab/vnet (e.g., "mylab/myvnet")
        parts = resource_name.split("/")
        if len(parts) >= 2:
            lab_name = parts[0]
            vnet_name = parts[1]
        else:
            lab_name = "unknown-lab"
            vnet_name = resource_name

        safe_name = self.sanitize_name(vnet_name)

        config = self.build_base_config(resource)
        config["name"] = vnet_name
        config["lab_name"] = lab_name

        # Virtual network description
        description = properties.get("description", "")
        if description:
            config["description"] = description

        # Subnet configuration from subnetOverrides
        subnet_overrides = properties.get("subnetOverrides", [])
        if subnet_overrides and len(subnet_overrides) > 0:
            # Use first subnet override (primary subnet)
            primary_subnet = subnet_overrides[0]

            use_in_vm_creation = primary_subnet.get(
                "useInVmCreationPermission", "Default"
            )
            use_public_ip = primary_subnet.get(
                "usePublicIpAddressPermission", "Default"
            )

            config["subnet"] = {
                "use_in_virtual_machine_creation": use_in_vm_creation,
                "use_public_ip_address": use_public_ip,
            }

        logger.debug(
            f"DevTest Virtual Network '{vnet_name}' emitted for lab '{lab_name}'"
        )

        return "azurerm_dev_test_virtual_network", safe_name, config
