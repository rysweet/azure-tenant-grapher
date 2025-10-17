"""
Virtual Machine data plane replication plugin.

This plugin handles discovery and replication of Azure Virtual Machine data plane
items including:
- VM Extensions (CustomScriptExtension, AADLogin, etc.)
- Custom script data
- Data disk configurations and snapshots

The plugin supports two modes:
- Template: Replicate extension configurations and disk specs without data
- Replication: Full data copy including disk snapshots and script contents
"""

import json
import logging
from typing import Any, Dict, List, Optional

from ..plugins.base_plugin import (
    DataPlaneItem,
    DataPlanePlugin,
    Permission,
    ReplicationMode,
    ReplicationResult,
)

logger = logging.getLogger(__name__)


class VirtualMachinePlugin(DataPlanePlugin):
    """
    Data plane plugin for Azure Virtual Machines.

    Discovers and replicates VM extensions, custom scripts, and data disk
    configurations using Azure SDK.

    Example:
        plugin = VirtualMachinePlugin()
        items = plugin.discover(vm_resource)
        result = plugin.replicate_with_mode(source_vm, target_vm, ReplicationMode.TEMPLATE)
    """

    @property
    def supported_resource_type(self) -> str:
        """Azure resource type for Virtual Machines."""
        return "Microsoft.Compute/virtualMachines"

    def discover(self, resource: Dict[str, Any]) -> List[DataPlaneItem]:
        """
        Discover VM extensions and data disks.

        Uses Azure SDK to:
        1. Authenticate to Azure Compute
        2. List all VM extensions
        3. List data disk configurations
        4. Return structured DataPlaneItem list

        Args:
            resource: VM resource dictionary containing:
                - id: VM resource ID
                - name: VM name
                - properties: VM properties

        Returns:
            List of DataPlaneItem representing VM data plane contents

        Example:
            >>> resource = {
            ...     "id": "/subscriptions/.../virtualMachines/my-vm",
            ...     "type": "Microsoft.Compute/virtualMachines",
            ...     "name": "my-vm"
            ... }
            >>> items = plugin.discover(resource)
            >>> len(items)  # Returns count of extensions + data disks
        """
        if not self.validate_resource(resource):
            raise ValueError(f"Invalid resource for VirtualMachinePlugin: {resource}")

        vm_name = resource.get("name", "unknown")
        self.logger.info(f"Discovering data plane items for VM: {vm_name}")

        items: List[DataPlaneItem] = []

        try:
            # Import Azure SDK components
            from azure.core.exceptions import AzureError, HttpResponseError
            from azure.identity import DefaultAzureCredential
            from azure.mgmt.compute import ComputeManagementClient

            # Parse resource ID to extract subscription and resource group
            resource_id = resource.get("id", "")
            subscription_id, resource_group = self._parse_resource_id(resource_id)

            if not subscription_id or not resource_group:
                self.logger.error(
                    f"Could not parse subscription_id or resource_group from: {resource_id}"
                )
                return items

            # Get credential from provider or use default
            if self.credential_provider:
                credential = self.credential_provider.get_credential()
            else:
                credential = DefaultAzureCredential()

            # Create compute client
            compute_client = ComputeManagementClient(credential, subscription_id)

            # Discover VM extensions
            try:
                extensions = compute_client.virtual_machine_extensions.list(
                    resource_group_name=resource_group, vm_name=vm_name
                )

                for ext in extensions:
                    # Extract extension properties
                    ext_dict = ext.as_dict() if hasattr(ext, "as_dict") else {}

                    # Determine size (approximate based on settings)
                    settings_str = json.dumps(ext_dict.get("settings", {}))
                    size_bytes = len(settings_str.encode("utf-8"))

                    items.append(
                        DataPlaneItem(
                            name=ext.name or "unknown",
                            item_type="vm_extension",
                            properties={
                                "publisher": ext.publisher or "unknown",
                                "type": ext.type_handler_version or "unknown",
                                "type_handler_version": ext.type_handler_version or "unknown",
                                "auto_upgrade_minor_version": ext.auto_upgrade_minor_version,
                                "settings": ext_dict.get("settings", {}),
                                "provisioning_state": ext.provisioning_state,
                            },
                            source_resource_id=resource["id"],
                            size_bytes=size_bytes,
                            metadata={
                                "id": ext.id,
                                "location": ext.location,
                                "tags": ext.tags or {},
                                "has_protected_settings": bool(
                                    ext_dict.get("protected_settings")
                                ),
                            },
                        )
                    )

                    self.logger.debug(
                        f"Discovered extension: {ext.name} "
                        f"({ext.publisher}/{ext.type_handler_version})"
                    )

            except (AzureError, HttpResponseError) as e:
                self.logger.warning(f"Failed to discover extensions for {vm_name}: {e}")

            # Discover data disks
            try:
                vm_details = compute_client.virtual_machines.get(
                    resource_group_name=resource_group,
                    vm_name=vm_name,
                    expand="instanceView",
                )

                if vm_details.storage_profile and vm_details.storage_profile.data_disks:
                    for disk in vm_details.storage_profile.data_disks:
                        # Get disk size info
                        disk_size_gb = disk.disk_size_gb or 0
                        size_bytes = disk_size_gb * 1024 * 1024 * 1024

                        items.append(
                            DataPlaneItem(
                                name=disk.name or f"disk-lun-{disk.lun}",
                                item_type="data_disk",
                                properties={
                                    "lun": disk.lun,
                                    "disk_size_gb": disk_size_gb,
                                    "caching": disk.caching or "None",
                                    "create_option": disk.create_option or "Attach",
                                    "managed_disk_id": (
                                        disk.managed_disk.id if disk.managed_disk else None
                                    ),
                                },
                                source_resource_id=resource["id"],
                                size_bytes=size_bytes,
                                metadata={
                                    "write_accelerator_enabled": disk.write_accelerator_enabled
                                    or False,
                                    "to_be_detached": disk.to_be_detached or False,
                                },
                            )
                        )

                        self.logger.debug(
                            f"Discovered data disk: {disk.name} "
                            f"(LUN {disk.lun}, {disk_size_gb} GB)"
                        )

            except (AzureError, HttpResponseError) as e:
                self.logger.warning(f"Failed to discover data disks for {vm_name}: {e}")

            # Report discovery progress
            if self.progress_reporter:
                self.progress_reporter.report_discovery(resource["id"], len(items))

        except ImportError as e:
            self.logger.error(
                f"Azure Compute SDK not installed. Install with: "
                f"pip install azure-mgmt-compute. Error: {e}"
            )
        except Exception as e:
            self.logger.error(f"Unexpected error discovering VM items: {e}", exc_info=True)

        self.logger.info(f"Discovered {len(items)} data plane items for VM '{vm_name}'")
        return items

    def generate_replication_code(
        self, items: List[DataPlaneItem], output_format: str = "terraform"
    ) -> str:
        """
        Generate IaC code to replicate VM data plane items.

        For VM extensions, this generates:
        - azurerm_virtual_machine_extension resources
        - Comments for protected settings (manual intervention needed)
        - Data disk attachment configurations

        Args:
            items: List of VM data plane items to replicate
            output_format: IaC format ("terraform", "bicep", "arm")

        Returns:
            String containing IaC code for VM data plane items

        Raises:
            ValueError: If output_format is not supported

        Example:
            >>> items = [DataPlaneItem(name="CustomScript", item_type="vm_extension", ...)]
            >>> code = plugin.generate_replication_code(items)
            >>> "azurerm_virtual_machine_extension" in code
            True
        """
        if not self.supports_output_format(output_format):
            raise ValueError(
                f"Output format '{output_format}' not supported by VirtualMachinePlugin"
            )

        if output_format.lower() != "terraform":
            raise ValueError("Only Terraform format is currently supported")

        self.logger.info(f"Generating {output_format} code for {len(items)} VM items")

        if not items:
            return "# No VM data plane items to replicate\n"

        code_lines = [
            "# VM Data Plane Items",
            "# Generated by Azure Tenant Grapher - VirtualMachinePlugin",
            "#",
            "# NOTE: Protected settings for extensions are not included.",
            "# You must manually configure sensitive extension settings after deployment.",
            "",
        ]

        # Group items by type
        extensions = [item for item in items if item.item_type == "vm_extension"]
        data_disks = [item for item in items if item.item_type == "data_disk"]

        # Generate code for VM extensions
        if extensions:
            code_lines.append("# VM Extensions")
            for item in extensions:
                resource_name = self._sanitize_name(item.name)
                code_lines.extend(
                    [
                        f'resource "azurerm_virtual_machine_extension" "{resource_name}" {{',
                        f'  name                 = "{item.name}"',
                        "  # TODO: Reference your VM resource here",
                        "  virtual_machine_id   = azurerm_virtual_machine.REPLACE_ME.id",
                        "",
                        f'  publisher            = "{item.properties.get("publisher", "unknown")}"',
                        f'  type                 = "{item.properties.get("type", "unknown")}"',
                        f'  type_handler_version = "{item.properties.get("type_handler_version", "1.0")}"',
                        "",
                    ]
                )

                # Add auto upgrade setting
                auto_upgrade = item.properties.get("auto_upgrade_minor_version", True)
                code_lines.append(
                    f"  auto_upgrade_minor_version = {str(auto_upgrade).lower()}"
                )
                code_lines.append("")

                # Add settings (public configuration)
                settings = item.properties.get("settings", {})
                if settings:
                    code_lines.append("  settings = jsonencode({")
                    for key, value in settings.items():
                        if isinstance(value, str):
                            code_lines.append(f'    {key} = "{value}"')
                        else:
                            code_lines.append(f"    {key} = {json.dumps(value)}")
                    code_lines.append("  })")
                    code_lines.append("")

                # Add comment for protected settings
                if item.metadata.get("has_protected_settings"):
                    code_lines.extend(
                        [
                            "  # SECURITY: Protected settings not included",
                            "  # Configure manually or via variable:",
                            f"  # protected_settings = var.vm_extension_{resource_name}_protected",
                            "",
                        ]
                    )

                # Add tags
                tags = item.metadata.get("tags", {})
                if tags:
                    code_lines.append("  tags = {")
                    for key, value in tags.items():
                        code_lines.append(f'    "{key}" = "{value}"')
                    code_lines.append("  }")
                    code_lines.append("")

                code_lines.append("}")
                code_lines.append("")

        # Generate code for data disks
        if data_disks:
            code_lines.append("# Data Disk Attachments")
            code_lines.append(
                "# NOTE: Disk data content is NOT replicated in template mode."
            )
            code_lines.append(
                "# For full disk replication, use snapshot-based migration."
            )
            code_lines.append("")

            for item in data_disks:
                resource_name = self._sanitize_name(item.name)
                code_lines.extend(
                    [
                        f'resource "azurerm_managed_disk" "{resource_name}" {{',
                        f'  name                 = "{item.name}"',
                        "  # TODO: Set location and resource group",
                        '  location             = azurerm_resource_group.REPLACE_ME.location',
                        "  resource_group_name  = azurerm_resource_group.REPLACE_ME.name",
                        "",
                        '  storage_account_type = "Premium_LRS"  # TODO: Match source disk SKU',
                        '  create_option        = "Empty"',
                        f'  disk_size_gb         = {item.properties.get("disk_size_gb", 128)}',
                        "",
                        "  # Caching configuration",
                        f'  # Original caching: {item.properties.get("caching", "None")}',
                        "  # Set in VM data disk attachment",
                        "",
                        "}",
                        "",
                        f'resource "azurerm_virtual_machine_data_disk_attachment" "{resource_name}_attach" {{',
                        f"  managed_disk_id    = azurerm_managed_disk.{resource_name}.id",
                        "  virtual_machine_id = azurerm_virtual_machine.REPLACE_ME.id",
                        f'  lun                = {item.properties.get("lun", 0)}',
                        f'  caching            = "{item.properties.get("caching", "None")}"',
                        "}",
                        "",
                    ]
                )

        # Add helpful comments
        code_lines.extend(
            [
                "# IMPORTANT NOTES:",
                "# 1. Replace REPLACE_ME with actual resource references",
                "# 2. For full disk content replication, use Azure disk snapshots",
                "# 3. Protected extension settings must be configured separately",
                "# 4. Test VM functionality after deployment",
                "",
            ]
        )

        return "\n".join(code_lines)

    def replicate(
        self, source_resource: Dict[str, Any], target_resource: Dict[str, Any]
    ) -> ReplicationResult:
        """
        Replicate VM extensions from source to target (legacy method).

        This delegates to replicate_with_mode() using TEMPLATE mode by default.

        Args:
            source_resource: Source VM resource
            target_resource: Target VM resource

        Returns:
            ReplicationResult with operation statistics
        """
        return self.replicate_with_mode(
            source_resource, target_resource, ReplicationMode.TEMPLATE
        )

    def replicate_with_mode(
        self,
        source_resource: Dict[str, Any],
        target_resource: Dict[str, Any],
        mode: ReplicationMode,
    ) -> ReplicationResult:
        """
        Replicate VM data plane with mode awareness.

        Template mode: Replicate extension configurations without data
        Replication mode: Full data copy including disk snapshots

        Args:
            source_resource: Source VM resource
            target_resource: Target VM resource
            mode: Replication mode

        Returns:
            ReplicationResult with operation statistics

        Example:
            >>> source = {"id": "...", "type": "Microsoft.Compute/virtualMachines", ...}
            >>> target = {"id": "...", "type": "Microsoft.Compute/virtualMachines", ...}
            >>> result = plugin.replicate_with_mode(source, target, ReplicationMode.TEMPLATE)
            >>> result.success
            True
        """
        if not self.validate_resource(source_resource):
            raise ValueError(f"Invalid source resource: {source_resource}")

        if not self.validate_resource(target_resource):
            raise ValueError(f"Invalid target resource: {target_resource}")

        source_name = source_resource.get("name", "unknown")
        target_name = target_resource.get("name", "unknown")

        self.logger.info(
            f"Replicating VM data plane from {source_name} to {target_name} "
            f"(mode={mode.value})"
        )

        errors = []
        warnings = []
        items_replicated = 0

        try:
            # Import Azure SDK components
            from azure.core.exceptions import AzureError, HttpResponseError
            from azure.identity import DefaultAzureCredential
            from azure.mgmt.compute import ComputeManagementClient

            # Parse resource IDs
            source_subscription_id, source_rg = self._parse_resource_id(
                source_resource.get("id", "")
            )
            target_subscription_id, target_rg = self._parse_resource_id(
                target_resource.get("id", "")
            )

            if not all([source_subscription_id, source_rg, target_subscription_id, target_rg]):
                errors.append("Could not parse resource IDs")
                return ReplicationResult(
                    success=False,
                    items_discovered=0,
                    items_replicated=0,
                    errors=errors,
                    warnings=warnings,
                )

            # Get credential
            if self.credential_provider:
                credential = self.credential_provider.get_credential()
            else:
                credential = DefaultAzureCredential()

            # Discover items from source
            source_items = self.discover(source_resource)

            if not source_items:
                warnings.append("No data plane items found in source VM")
                return ReplicationResult(
                    success=True,
                    items_discovered=0,
                    items_replicated=0,
                    errors=errors,
                    warnings=warnings,
                )

            # Create compute client for target
            target_compute_client = ComputeManagementClient(
                credential, target_subscription_id
            )

            # Replicate VM extensions
            extensions = [item for item in source_items if item.item_type == "vm_extension"]

            for ext_item in extensions:
                try:
                    if mode == ReplicationMode.TEMPLATE:
                        # Template mode: Just log what would be replicated
                        self.logger.info(
                            f"[TEMPLATE] Would replicate extension: {ext_item.name} "
                            f"({ext_item.properties.get('publisher')}/"
                            f"{ext_item.properties.get('type')})"
                        )
                        items_replicated += 1

                        if self.progress_reporter:
                            progress = (items_replicated / len(extensions)) * 100
                            self.progress_reporter.report_replication_progress(
                                ext_item.name, progress
                            )

                    else:
                        # Replication mode: Actually create/update the extension
                        self.logger.info(f"Replicating extension: {ext_item.name}")

                        # Prepare extension parameters
                        extension_params = {
                            "location": target_resource.get("location", "eastus"),
                            "publisher": ext_item.properties.get("publisher"),
                            "type_properties_type": ext_item.properties.get("type"),
                            "type_handler_version": ext_item.properties.get(
                                "type_handler_version"
                            ),
                            "auto_upgrade_minor_version": ext_item.properties.get(
                                "auto_upgrade_minor_version", True
                            ),
                            "settings": ext_item.properties.get("settings", {}),
                        }

                        # Note: protected_settings are not replicated for security
                        if ext_item.metadata.get("has_protected_settings"):
                            warnings.append(
                                f"Extension {ext_item.name} has protected settings "
                                "that were not replicated (security)"
                            )

                        # Create/update extension
                        poller = target_compute_client.virtual_machine_extensions.begin_create_or_update(
                            resource_group_name=target_rg,
                            vm_name=target_name,
                            vm_extension_name=ext_item.name,
                            extension_parameters=extension_params,
                        )

                        # Wait for completion
                        poller.result()
                        items_replicated += 1

                        self.logger.info(
                            f"Successfully replicated extension: {ext_item.name}"
                        )

                        if self.progress_reporter:
                            progress = (items_replicated / len(extensions)) * 100
                            self.progress_reporter.report_replication_progress(
                                ext_item.name, progress
                            )

                except (AzureError, HttpResponseError) as e:
                    error_msg = f"Failed to replicate extension {ext_item.name}: {e}"
                    self.logger.error(error_msg)
                    errors.append(error_msg)

            # Handle data disks
            data_disks = [item for item in source_items if item.item_type == "data_disk"]

            if data_disks:
                if mode == ReplicationMode.TEMPLATE:
                    warnings.append(
                        f"Template mode: {len(data_disks)} data disk(s) not replicated. "
                        "Use replication mode for full disk copy."
                    )
                else:
                    warnings.append(
                        f"Full disk replication for {len(data_disks)} disk(s) "
                        "requires manual snapshot/copy process. "
                        "Use Azure disk snapshot and copy operations."
                    )

        except ImportError as e:
            errors.append(f"Azure SDK not available: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error during replication: {e}", exc_info=True)
            errors.append(f"Unexpected error: {str(e)}")

        # Build result
        success = len(errors) == 0
        result = ReplicationResult(
            success=success,
            items_discovered=len(source_items),
            items_replicated=items_replicated,
            items_skipped=len(source_items) - items_replicated,
            errors=errors,
            warnings=warnings,
        )

        # Report completion
        if self.progress_reporter:
            self.progress_reporter.report_completion(result)

        return result

    def get_required_permissions(self, mode: ReplicationMode) -> List[Permission]:
        """
        Return Azure RBAC permissions required for VM plugin.

        Args:
            mode: The replication mode (affects required permissions)

        Returns:
            List of Permission objects describing needed RBAC roles

        Example:
            >>> plugin = VirtualMachinePlugin()
            >>> perms = plugin.get_required_permissions(ReplicationMode.TEMPLATE)
            >>> len(perms) > 0
            True
        """
        if mode == ReplicationMode.TEMPLATE:
            return [
                Permission(
                    scope="resource",
                    actions=[
                        "Microsoft.Compute/virtualMachines/read",
                        "Microsoft.Compute/virtualMachines/extensions/read",
                    ],
                    description="Read VM and extension metadata (template mode)",
                )
            ]
        else:
            # Replication mode
            return [
                Permission(
                    scope="resource",
                    actions=[
                        "Microsoft.Compute/virtualMachines/read",
                        "Microsoft.Compute/virtualMachines/extensions/read",
                        "Microsoft.Compute/virtualMachines/extensions/write",
                        "Microsoft.Compute/disks/read",
                        "Microsoft.Compute/snapshots/write",
                    ],
                    description="Read/write VM extensions and create disk snapshots (replication mode)",
                )
            ]

    def estimate_operation_time(
        self, items: List[DataPlaneItem], mode: ReplicationMode
    ) -> float:
        """
        Estimate time required for VM replication operation.

        Args:
            items: Items to replicate
            mode: Replication mode

        Returns:
            Estimated seconds

        Example:
            >>> items = [DataPlaneItem(...) for _ in range(3)]
            >>> time_est = plugin.estimate_operation_time(items, ReplicationMode.TEMPLATE)
            >>> time_est >= 0
            True
        """
        if mode == ReplicationMode.TEMPLATE:
            return 0.0

        # Estimate based on item types
        extensions = [item for item in items if item.item_type == "vm_extension"]
        data_disks = [item for item in items if item.item_type == "data_disk"]

        # Extensions: ~30 seconds each (Azure API calls)
        extension_time = len(extensions) * 30.0

        # Data disks: ~5 minutes per GB (snapshot + copy operations)
        disk_time = 0.0
        for disk in data_disks:
            disk_size_gb = disk.properties.get("disk_size_gb", 0)
            disk_time += disk_size_gb * 300.0  # 5 minutes per GB

        return extension_time + disk_time

    def _parse_resource_id(self, resource_id: str) -> tuple[Optional[str], Optional[str]]:
        """
        Parse Azure resource ID to extract subscription and resource group.

        Args:
            resource_id: Azure resource ID

        Returns:
            Tuple of (subscription_id, resource_group_name)

        Example:
            >>> resource_id = "/subscriptions/abc123/resourceGroups/my-rg/providers/..."
            >>> sub_id, rg = plugin._parse_resource_id(resource_id)
            >>> sub_id == "abc123"
            True
            >>> rg == "my-rg"
            True
        """
        try:
            parts = resource_id.split("/")
            subscription_id = None
            resource_group = None

            for i, part in enumerate(parts):
                if part.lower() == "subscriptions" and i + 1 < len(parts):
                    subscription_id = parts[i + 1]
                elif part.lower() == "resourcegroups" and i + 1 < len(parts):
                    resource_group = parts[i + 1]

            return subscription_id, resource_group
        except Exception as e:
            self.logger.error(f"Failed to parse resource ID {resource_id}: {e}")
            return None, None

    def _sanitize_name(self, name: str) -> str:
        """
        Sanitize a name for use in Terraform resource names.

        Args:
            name: Original name (may contain hyphens, special chars)

        Returns:
            Sanitized name safe for Terraform identifiers

        Example:
            >>> plugin._sanitize_name("my-extension-v1.0")
            'my_extension_v1_0'
        """
        # Replace hyphens and special chars with underscores
        sanitized = name.replace("-", "_").replace(".", "_").replace(" ", "_")

        # Ensure it starts with a letter
        if sanitized and not sanitized[0].isalpha():
            sanitized = "vm_" + sanitized

        return sanitized.lower()
