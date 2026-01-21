"""VM Extensions handler for Terraform emission.

Handles: Microsoft.Compute/virtualMachines/extensions, runCommands
Emits: azurerm_virtual_machine_extension, azurerm_virtual_machine_run_command
"""

import json
import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class VMExtensionHandler(ResourceHandler):
    """Handler for Azure VM Extensions.

    Features:
    - Automatic OS type detection (Linux vs Windows)
    - OS-aware extension metadata mapping (publisher, type, version)
    - Complete property mapping including settings and protected_settings
    - Parent VM validation before emission
    - Sensitive data protection for protected_settings

    Emits:
        - azurerm_virtual_machine_extension
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Compute/virtualMachines/extensions",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_virtual_machine_extension",
    }

    # OS-aware extension metadata mappings
    # Key: (OS type, extension type) -> {publisher, type, type_handler_version}
    EXTENSION_MAPPINGS: ClassVar[Dict[Tuple[str, str], Dict[str, str]]] = {
        # CustomScriptExtension
        ("Linux", "CustomScriptExtension"): {
            "publisher": "Microsoft.Azure.Extensions",
            "type": "CustomScript",
            "type_handler_version": "2.1",
        },
        ("Windows", "CustomScriptExtension"): {
            "publisher": "Microsoft.Compute",
            "type": "CustomScriptExtension",
            "type_handler_version": "1.10",
        },
        # CustomScript (inverse mapping - when already correct)
        ("Linux", "CustomScript"): {
            "publisher": "Microsoft.Azure.Extensions",
            "type": "CustomScript",
            "type_handler_version": "2.1",
        },
        ("Windows", "CustomScript"): {
            "publisher": "Microsoft.Compute",
            "type": "CustomScriptExtension",
            "type_handler_version": "1.10",
        },
        # DSC (Desired State Configuration) - Windows only
        ("Windows", "DSC"): {
            "publisher": "Microsoft.Powershell",
            "type": "DSC",
            "type_handler_version": "2.77",
        },
        # AADLogin (Azure AD authentication)
        ("Linux", "AADSSHLoginForLinux"): {
            "publisher": "Microsoft.Azure.ActiveDirectory",
            "type": "AADSSHLoginForLinux",
            "type_handler_version": "1.0",
        },
        ("Windows", "AADLoginForWindows"): {
            "publisher": "Microsoft.Azure.ActiveDirectory",
            "type": "AADLoginForWindows",
            "type_handler_version": "1.0",
        },
        # AzureMonitorAgent
        ("Linux", "AzureMonitorLinuxAgent"): {
            "publisher": "Microsoft.Azure.Monitor",
            "type": "AzureMonitorLinuxAgent",
            "type_handler_version": "1.0",
        },
        ("Windows", "AzureMonitorWindowsAgent"): {
            "publisher": "Microsoft.Azure.Monitor",
            "type": "AzureMonitorWindowsAgent",
            "type_handler_version": "1.0",
        },
        # NetworkWatcherAgent
        ("Linux", "NetworkWatcherAgentLinux"): {
            "publisher": "Microsoft.Azure.NetworkWatcher",
            "type": "NetworkWatcherAgentLinux",
            "type_handler_version": "1.4",
        },
        ("Windows", "NetworkWatcherAgentWindows"): {
            "publisher": "Microsoft.Azure.NetworkWatcher",
            "type": "NetworkWatcherAgentWindows",
            "type_handler_version": "1.4",
        },
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Azure VM Extension to Terraform configuration.

        Args:
            resource: Azure extension resource from graph
            context: Shared emitter context

        Returns:
            Tuple of (terraform_type, resource_name, config) or None if skipped
        """
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        # Extract VM name from extension name (format: "vmname/extensionname")
        full_name = resource_name
        if "/" in full_name:
            vm_name = full_name.split("/")[0]
            extension_name = full_name.split("/")[1]
        else:
            # Malformed name - skip extension
            logger.warning(
                f"VM Extension '{resource_name}' - malformed name (expected format: 'vm_name/extension_name'). Skipping."
            )
            return None

        vm_safe = self.sanitize_name(vm_name)

        # Detect parent VM OS type and validate existence
        vm_reference, os_type = self._get_vm_reference_and_os(vm_name, vm_safe, context)
        if vm_reference is None:
            logger.warning(
                f"VM Extension '{extension_name}' - parent VM '{vm_name}' not found in emitted resources. Skipping extension."
            )
            return None

        # Get original extension metadata
        original_publisher = properties.get("publisher", "Microsoft.Azure.Extensions")
        original_type = properties.get("type", "CustomScript")
        original_version = properties.get("typeHandlerVersion", "2.1")

        # Apply OS-aware mapping if available
        publisher, ext_type, version = self._map_extension_metadata(
            os_type,
            original_type,
            original_publisher,
            original_version,
            extension_name,
            vm_name,
        )

        # Build base config
        config = {
            "name": extension_name,
            "virtual_machine_id": vm_reference,
            "publisher": publisher,
            "type": ext_type,
            "type_handler_version": version,
        }

        # Add auto upgrade if specified
        auto_upgrade = properties.get("autoUpgradeMinorVersion")
        if auto_upgrade is not None:
            config["auto_upgrade_minor_version"] = auto_upgrade

        # Add settings if present
        settings = properties.get("settings")
        if settings:
            # Settings are JSON objects - wrap in jsonencode() for Terraform
            config["settings"] = f"jsonencode({json.dumps(settings)})"

        # Add protected settings if present (sensitive data)
        protected_settings = properties.get("protectedSettings")
        if protected_settings:
            # Protected settings contain sensitive data - wrap in jsonencode()
            config["protected_settings"] = (
                f"jsonencode({json.dumps(protected_settings)})"
            )

        logger.debug(f"VM Extension '{extension_name}' emitted for VM '{vm_name}'")

        return "azurerm_virtual_machine_extension", safe_name, config

    def _get_vm_reference_and_os(
        self, vm_name: str, vm_safe: str, context: EmitterContext
    ) -> Tuple[Optional[str], Optional[str]]:
        """Get Terraform reference for parent VM with OS type detection.

        Args:
            vm_name: Original VM name
            vm_safe: Sanitized VM name for Terraform
            context: Emitter context with emitted resources

        Returns:
            Tuple of (Terraform VM reference string, OS type) or (None, None) if VM not found
        """
        # Check emitted resources for parent VM
        terraform_config = context.terraform_config.get("resource", {})

        # Check for Linux VM
        linux_vms = terraform_config.get("azurerm_linux_virtual_machine", {})
        if vm_safe in linux_vms:
            return f"${{azurerm_linux_virtual_machine.{vm_safe}.id}}", "Linux"

        # Check for Windows VM
        windows_vms = terraform_config.get("azurerm_windows_virtual_machine", {})
        if vm_safe in windows_vms:
            return f"${{azurerm_windows_virtual_machine.{vm_safe}.id}}", "Windows"

        # Parent VM not found in emitted resources
        return None, None

    def _map_extension_metadata(
        self,
        os_type: str,
        original_type: str,
        original_publisher: str,
        original_version: str,
        extension_name: str,
        vm_name: str,
    ) -> Tuple[str, str, str]:
        """Map extension metadata to OS-appropriate values.

        Args:
            os_type: VM OS type (Linux or Windows)
            original_type: Original extension type from Azure
            original_publisher: Original publisher from Azure
            original_version: Original version from Azure
            extension_name: Extension name for logging
            vm_name: Parent VM name for logging

        Returns:
            Tuple of (publisher, type, version) with mapping applied if available
        """
        # Try to find mapping for this OS and extension type
        mapping_key = (os_type, original_type)
        mapping = self.EXTENSION_MAPPINGS.get(mapping_key)

        if mapping:
            # Check if mapping actually changes anything
            mapped_publisher = mapping["publisher"]
            mapped_type = mapping["type"]
            mapped_version = mapping["type_handler_version"]

            # Log if mapping changed metadata
            if (
                mapped_publisher != original_publisher
                or mapped_type != original_type
                or mapped_version != original_version
            ):
                logger.warning(
                    f"Extension '{extension_name}' mapped from "
                    f"{original_publisher}/{original_type}/{original_version} "
                    f"to {mapped_publisher}/{mapped_type}/{mapped_version} "
                    f"for {os_type} VM '{vm_name}'"
                )

            return mapped_publisher, mapped_type, mapped_version

        # No mapping found - use original metadata
        return original_publisher, original_type, original_version


@handler
class VMRunCommandHandler(ResourceHandler):
    """Handler for Azure VM Run Commands.

    Features:
    - OS-aware parent VM detection
    - Parent VM validation before emission

    Emits:
        - azurerm_virtual_machine_run_command
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Compute/virtualMachines/runCommands",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_virtual_machine_run_command",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Azure VM Run Command to Terraform configuration.

        Args:
            resource: Azure run command resource from graph
            context: Shared emitter context

        Returns:
            Tuple of (terraform_type, resource_name, config) or None if skipped
        """
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        # Extract VM name from run command name (format: "vmname/runcommandname")
        full_name = resource_name
        if "/" in full_name:
            vm_name = full_name.split("/")[0]
            command_name = full_name.split("/")[1]
        else:
            logger.warning(
                f"VM Run Command '{resource_name}' - malformed name (expected format: 'vm_name/command_name'). Skipping."
            )
            return None

        vm_safe = self.sanitize_name(vm_name)

        # Detect parent VM OS type and validate existence
        vm_reference = self._get_vm_reference(vm_name, vm_safe, context)
        if vm_reference is None:
            logger.warning(
                f"VM Run Command '{command_name}' - parent VM '{vm_name}' not found in emitted resources. Skipping command."
            )
            return None

        location = self.get_location(resource)

        config = {
            "name": command_name,
            "location": location,
            "virtual_machine_id": vm_reference,
        }

        # Add source script
        source = properties.get("source", {})
        if source and "script" in source:
            config["source"] = {"script": source["script"]}

        logger.debug(f"VM Run Command '{command_name}' emitted for VM '{vm_name}'")

        return "azurerm_virtual_machine_run_command", safe_name, config

    def _get_vm_reference(
        self, vm_name: str, vm_safe: str, context: EmitterContext
    ) -> Optional[str]:
        """Get Terraform reference for parent VM with OS type detection.

        Args:
            vm_name: Original VM name
            vm_safe: Sanitized VM name for Terraform
            context: Emitter context with emitted resources

        Returns:
            Terraform VM reference string or None if VM not found
        """
        # Check emitted resources for parent VM
        terraform_config = context.terraform_config.get("resource", {})

        # Check for Linux VM
        linux_vms = terraform_config.get("azurerm_linux_virtual_machine", {})
        if vm_safe in linux_vms:
            return f"${{azurerm_linux_virtual_machine.{vm_safe}.id}}"

        # Check for Windows VM
        windows_vms = terraform_config.get("azurerm_windows_virtual_machine", {})
        if vm_safe in windows_vms:
            return f"${{azurerm_windows_virtual_machine.{vm_safe}.id}}"

        # Parent VM not found in emitted resources
        return None
