"""VM Extensions handler for Terraform emission.

Handles: Microsoft.Compute/virtualMachines/extensions, runCommands
Emits: azurerm_virtual_machine_extension, azurerm_virtual_machine_run_command
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class VMExtensionHandler(ResourceHandler):
    """Handler for Azure VM Extensions.

    Emits:
        - azurerm_virtual_machine_extension
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Compute/virtualMachines/extensions",
        "microsoft.compute/virtualMachines/extensions",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_virtual_machine_extension",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Azure VM Extension to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        # Extract VM name from extension name (format: "vmname/extensionname")
        full_name = resource_name
        if "/" in full_name:
            vm_name = full_name.split("/")[0]
            extension_name = full_name.split("/")[1]
        else:
            vm_name = "unknown-vm"
            extension_name = full_name

        vm_safe = self.sanitize_name(vm_name)

        config = {
            "name": extension_name,
            "virtual_machine_id": f"${{azurerm_linux_virtual_machine.{vm_safe}.id}}",
            "publisher": properties.get("publisher", "Microsoft.Azure.Extensions"),
            "type": properties.get("type", "CustomScript"),
            "type_handler_version": properties.get("typeHandlerVersion", "2.1"),
        }

        # Add auto upgrade
        auto_upgrade = properties.get("autoUpgradeMinorVersion")
        if auto_upgrade is not None:
            config["auto_upgrade_minor_version"] = auto_upgrade

        logger.debug(f"VM Extension '{extension_name}' emitted for VM '{vm_name}'")

        return "azurerm_virtual_machine_extension", safe_name, config


@handler
class VMRunCommandHandler(ResourceHandler):
    """Handler for Azure VM Run Commands.

    Emits:
        - azurerm_virtual_machine_run_command
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Compute/virtualMachines/runCommands",
        "microsoft.compute/virtualmachines/runcommands",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_virtual_machine_run_command",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Azure VM Run Command to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        # Extract VM name from run command name (format: "vmname/runcommandname")
        full_name = resource_name
        if "/" in full_name:
            vm_name = full_name.split("/")[0]
            command_name = full_name.split("/")[1]
        else:
            vm_name = "unknown-vm"
            command_name = full_name

        vm_safe = self.sanitize_name(vm_name)
        location = self.get_location(resource)

        config = {
            "name": command_name,
            "location": location,
            "virtual_machine_id": f"${{azurerm_linux_virtual_machine.{vm_safe}.id}}",
        }

        # Add source script
        source = properties.get("source", {})
        if source and "script" in source:
            config["source"] = {"script": source["script"]}

        logger.debug(f"VM Run Command '{command_name}' emitted for VM '{vm_name}'")

        return "azurerm_virtual_machine_run_command", safe_name, config
