"""Virtual Machine handler for Terraform emission.

Handles: Microsoft.Compute/virtualMachines
Emits: azurerm_linux_virtual_machine, tls_private_key
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class VirtualMachineHandler(ResourceHandler):
    """Handler for Azure Virtual Machines.

    Emits:
        - azurerm_linux_virtual_machine
        - tls_private_key (helper resource for SSH authentication)
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Compute/virtualMachines",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_linux_virtual_machine",
        "azurerm_windows_virtual_machine",
        "tls_private_key",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Azure VM to Terraform configuration.

        Args:
            resource: Azure resource dictionary from graph
            context: Shared emitter context

        Returns:
            Tuple of (terraform_type, resource_name, config) or None if skipped
        """
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        # Validate network interfaces FIRST
        nic_refs = self._validate_and_get_nics(resource, properties, context)
        if not nic_refs:
            logger.warning(
                f"VM '{resource_name}' - all NIC references are missing. "
                f"Skipping VM (cannot create without valid network configuration)."
            )
            return None

        # Build base configuration
        config = self.build_base_config(resource)

        # Generate SSH key pair for VM authentication
        ssh_key_resource_name = f"{safe_name}_ssh_key"

        # Add tls_private_key resource to terraform config
        context.add_helper_resource(
            "tls_private_key",
            ssh_key_resource_name,
            {
                "algorithm": "RSA",
                "rsa_bits": 4096,
            },
        )

        # Detect Windows vs Linux OS FIRST (Fix #596: Need OS type before adding SSH key)
        os_profile = properties.get("osProfile", {})
        has_windows_config = "windowsConfiguration" in os_profile
        has_linux_config = "linuxConfiguration" in os_profile

        # Check osType in storage profile as fallback
        storage_profile = properties.get("storageProfile", {})
        os_disk = storage_profile.get("osDisk", {})
        os_type = os_disk.get("osType", "").lower()

        # Determine VM type
        if has_windows_config or os_type == "windows":
            vm_type = "azurerm_windows_virtual_machine"
            is_windows = True
        elif has_linux_config or os_type == "linux":
            vm_type = "azurerm_linux_virtual_machine"
            is_windows = False
        else:
            # Default to Linux if unknown
            vm_type = "azurerm_linux_virtual_machine"
            is_windows = False
            logger.warning(
                f"VM '{resource_name}' has unclear OS type, defaulting to Linux"
            )

        # Add VM-specific properties (common to both Windows and Linux)
        config.update(
            {
                "size": resource.get("size", "Standard_B2s"),
                "admin_username": resource.get("admin_username", "azureuser"),
                "network_interface_ids": nic_refs,
                "os_disk": {
                    "caching": "ReadWrite",
                    "storage_account_type": "Standard_LRS",
                },
            }
        )

        # Bug #21: Set source_image_reference based on OS type
        if is_windows:
            config["source_image_reference"] = {
                "publisher": "MicrosoftWindowsServer",
                "offer": "WindowsServer",
                "sku": "2022-Datacenter",
                "version": "latest",
            }
        else:
            config["source_image_reference"] = {
                "publisher": "Canonical",
                "offer": "0001-com-ubuntu-server-jammy",
                "sku": "22_04-lts",
                "version": "latest",
            }

        # Fix #596: Add authentication based on OS type
        if is_windows:
            # Windows VMs require admin_password
            password_resource_name = f"{safe_name}_admin_password"
            context.add_helper_resource(
                "random_password",
                password_resource_name,
                {
                    "length": 16,
                    "special": True,
                    "override_special": "!#$%&*()-_=+[]{}<>:?",
                },
            )
            config["admin_password"] = (
                f"${{random_password.{password_resource_name}.result}}"
            )
        else:
            # Linux VMs use SSH keys
            config["admin_ssh_key"] = {
                "username": resource.get("admin_username", "azureuser"),
                "public_key": f"${{tls_private_key.{ssh_key_resource_name}.public_key_openssh}}",
            }

        logger.debug(
            f"VM '{resource_name}' emitted as {vm_type} with {len(nic_refs)} NIC(s)"
        )

        return vm_type, safe_name, config

    def _validate_and_get_nics(
        self,
        resource: Dict[str, Any],
        properties: Dict[str, Any],
        context: EmitterContext,
    ) -> list:
        """Validate and collect NIC references.

        Args:
            resource: Azure resource dict
            properties: Parsed properties dict
            context: Emitter context

        Returns:
            List of valid NIC Terraform references
        """
        resource_name = resource.get("name", "unknown")
        network_profile = properties.get("networkProfile", {})
        nics = network_profile.get("networkInterfaces", [])

        if not nics:
            logger.warning(
                f"VM '{resource_name}' has no networkProfile. "
                f"Cannot create without valid network configuration."
            )
            return []

        nic_refs = []
        missing_nics = []

        for nic in nics:
            nic_id = nic.get("id", "")
            if not nic_id:
                continue

            nic_name = self.extract_name_from_id(nic_id, "networkInterfaces")
            if nic_name == "unknown":
                continue

            nic_safe = self.sanitize_name(nic_name)

            # Bug #30: Validate NIC was actually emitted
            if self.validate_resource_reference(
                "azurerm_network_interface", nic_safe, context
            ):
                nic_refs.append(f"${{azurerm_network_interface.{nic_safe}.id}}")
            else:
                missing_nics.append(
                    {
                        "nic_name": nic_name,
                        "nic_id": nic_id,
                        "nic_terraform_name": nic_safe,
                    }
                )
                context.track_missing_reference(
                    resource_name,
                    "network_interface",
                    nic_name,
                    nic_id,
                    vm_name=resource_name,
                    vm_id=resource.get("id", ""),
                )

        if missing_nics:
            for missing in missing_nics:
                logger.warning(
                    f"VM '{resource_name}' references missing NIC '{missing['nic_name']}'\n"
                    f"    Azure ID: {missing['nic_id']}\n"
                    f"    Expected Terraform name: {missing['nic_terraform_name']}"
                )

            if nic_refs:
                logger.info(
                    f"VM '{resource_name}' will be created with {len(nic_refs)} valid NIC(s), "
                    f"skipping {len(missing_nics)} missing NIC(s)"
                )

        return nic_refs
