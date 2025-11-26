"""Container Group handler for Terraform emission.

Handles: Microsoft.ContainerInstance/containerGroups
Emits: azurerm_container_group
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class ContainerGroupHandler(ResourceHandler):
    """Handler for Azure Container Instances.

    Emits:
        - azurerm_container_group
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.ContainerInstance/containerGroups",
        "microsoft.containerinstance/containergroups",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_container_group",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Container Group to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        config = self.build_base_config(resource)

        # OS type (required)
        os_type = properties.get("osType", "Linux")
        config["os_type"] = os_type

        # Container block (required)
        containers = properties.get("containers", [])
        if containers and len(containers) > 0:
            container = containers[0]
            container_props = container.get("properties", {})
            resources = container_props.get("resources", {})
            requests = resources.get("requests", {})

            config["container"] = {
                "name": container.get("name", "container"),
                "image": container_props.get(
                    "image", "mcr.microsoft.com/azuredocs/aci-helloworld:latest"
                ),
                "cpu": str(requests.get("cpu", "0.5")),
                "memory": str(requests.get("memoryInGB", "1.5")),
            }
        else:
            config["container"] = {
                "name": "container",
                "image": "mcr.microsoft.com/azuredocs/aci-helloworld:latest",
                "cpu": "0.5",
                "memory": "1.5",
            }

        logger.debug(
            f"Container Group '{resource_name}' emitted with os_type='{os_type}'"
        )

        return "azurerm_container_group", safe_name, config
