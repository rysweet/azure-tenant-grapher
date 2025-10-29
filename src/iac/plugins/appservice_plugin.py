"""
App Service and Functions data plane replication plugin.

This plugin handles discovery and replication of Azure App Service and Azure Functions
data plane items including:
- App settings (environment variables)
- Connection strings
- Deployment slots
- Functions-specific settings

The plugin integrates with the IaC generation process to ensure that App Service
configurations are preserved when deploying to new environments.
"""

import logging
import time
from typing import Any, Dict, List

from .base_plugin import (
    DataPlaneItem,
    DataPlanePlugin,
    Permission,
    ReplicationMode,
    ReplicationResult,
)

logger = logging.getLogger(__name__)


class AppServicePlugin(DataPlanePlugin):
    """
    Data plane plugin for Azure App Service and Functions.

    Discovers and replicates App Service app settings, connection strings, and
    deployment slots using Azure SDK.

    Example:
        plugin = AppServicePlugin()
        items = plugin.discover(appservice_resource)
        code = plugin.generate_replication_code(items, "terraform")
    """

    @property
    def supported_resource_type(self) -> str:
        """Azure resource type for App Service and Functions."""
        return "Microsoft.Web/sites"

    def discover(self, resource: Dict[str, Any]) -> List[DataPlaneItem]:
        """
        Discover App Service app settings, connection strings, and deployment slots.

        Uses Azure SDK to:
        1. Authenticate to the App Service
        2. List all app settings
        3. List all connection strings
        4. List deployment slots (if any)
        5. Return structured DataPlaneItem list

        Args:
            resource: App Service resource dictionary containing:
                - id: App Service resource ID
                - name: App Service name
                - properties: App Service properties

        Returns:
            List of DataPlaneItem representing App Service configuration

        Example:
            >>> resource = {
            ...     "id": "/subscriptions/.../sites/my-app",
            ...     "type": "Microsoft.Web/sites",
            ...     "name": "my-app",
            ...     "properties": {...}
            ... }
            >>> items = plugin.discover(resource)
            >>> len(items)  # Returns count of settings/connection strings/slots
        """
        if not self.validate_resource(resource):
            raise ValueError(f"Invalid resource for AppServicePlugin: {resource}")

        app_name = resource.get("name", "unknown")
        self.logger.info(f"Discovering data plane items for App Service: {app_name}")

        items: List[DataPlaneItem] = []

        try:
            # Import Azure SDK components
            from azure.core.exceptions import AzureError, HttpResponseError
            from azure.identity import DefaultAzureCredential
            from azure.mgmt.web import WebSiteManagementClient

            # Parse resource ID to extract subscription and resource group
            resource_id = resource.get("id", "")
            parts = resource_id.split("/")

            if len(parts) < 9:
                self.logger.error(
                    f"Invalid resource ID format: {resource_id}. "
                    "Expected format: /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Web/sites/<name>"
                )
                return items

            subscription_id = parts[2]
            resource_group = parts[4]

            # Authenticate
            if self.credential_provider:
                credential = self.credential_provider.get_credential()
            else:
                credential = DefaultAzureCredential()

            # Create Web Site Management Client
            web_client = WebSiteManagementClient(credential, subscription_id)

            # Discover app settings
            try:
                app_settings = web_client.web_apps.list_application_settings(
                    resource_group_name=resource_group, name=app_name
                )

                if app_settings and app_settings.properties:
                    for key, value in app_settings.properties.items():
                        items.append(
                            DataPlaneItem(
                                name=key,
                                item_type="app_setting",
                                properties={
                                    "value": value,
                                    "is_sensitive": self._is_sensitive_key(key),
                                },
                                source_resource_id=resource["id"],
                                metadata={
                                    "resource_type": "app_setting",
                                },
                            )
                        )

                    self.logger.info(
                        f"Discovered {len(app_settings.properties)} app settings"
                    )

            except (AzureError, HttpResponseError) as e:
                self.logger.warning(
                    f"Failed to discover app settings for {app_name}: {e}"
                )

            # Discover connection strings
            try:
                conn_strings = web_client.web_apps.list_connection_strings(
                    resource_group_name=resource_group, name=app_name
                )

                if conn_strings and conn_strings.properties:
                    for key, conn_info in conn_strings.properties.items():
                        items.append(
                            DataPlaneItem(
                                name=key,
                                item_type="connection_string",
                                properties={
                                    "value": conn_info.value,
                                    "type": conn_info.type,
                                    "is_sensitive": True,  # Connection strings are always sensitive
                                },
                                source_resource_id=resource["id"],
                                metadata={
                                    "resource_type": "connection_string",
                                    "connection_type": conn_info.type,
                                },
                            )
                        )

                    self.logger.info(
                        f"Discovered {len(conn_strings.properties)} connection strings"
                    )

            except (AzureError, HttpResponseError) as e:
                self.logger.warning(
                    f"Failed to discover connection strings for {app_name}: {e}"
                )

            # Discover deployment slots
            try:
                slots = web_client.web_apps.list_slots(
                    resource_group_name=resource_group, name=app_name
                )

                slot_count = 0
                for slot in slots:
                    slot_name = slot.name.split("/")[
                        -1
                    ]  # Extract slot name from full name

                    items.append(
                        DataPlaneItem(
                            name=slot_name,
                            item_type="deployment_slot",
                            properties={
                                "state": slot.state,
                                "enabled": slot.enabled,
                                "default_host_name": slot.default_host_name,
                            },
                            source_resource_id=resource["id"],
                            metadata={
                                "resource_type": "deployment_slot",
                                "slot_id": slot.id,
                            },
                        )
                    )
                    slot_count += 1

                    # Discover app settings for each slot
                    try:
                        slot_settings = (
                            web_client.web_apps.list_application_settings_slot(
                                resource_group_name=resource_group,
                                name=app_name,
                                slot=slot_name,
                            )
                        )

                        if slot_settings and slot_settings.properties:
                            for key, value in slot_settings.properties.items():
                                items.append(
                                    DataPlaneItem(
                                        name=f"{slot_name}/{key}",
                                        item_type="slot_app_setting",
                                        properties={
                                            "value": value,
                                            "is_sensitive": self._is_sensitive_key(key),
                                            "slot_name": slot_name,
                                        },
                                        source_resource_id=resource["id"],
                                        metadata={
                                            "resource_type": "slot_app_setting",
                                            "slot_name": slot_name,
                                        },
                                    )
                                )

                    except (AzureError, HttpResponseError) as e:
                        self.logger.warning(
                            f"Failed to discover app settings for slot {slot_name}: {e}"
                        )

                    # Discover connection strings for each slot
                    try:
                        slot_conn_strings = (
                            web_client.web_apps.list_connection_strings_slot(
                                resource_group_name=resource_group,
                                name=app_name,
                                slot=slot_name,
                            )
                        )

                        if slot_conn_strings and slot_conn_strings.properties:
                            for key, conn_info in slot_conn_strings.properties.items():
                                items.append(
                                    DataPlaneItem(
                                        name=f"{slot_name}/{key}",
                                        item_type="slot_connection_string",
                                        properties={
                                            "value": conn_info.value,
                                            "type": conn_info.type,
                                            "is_sensitive": True,
                                            "slot_name": slot_name,
                                        },
                                        source_resource_id=resource["id"],
                                        metadata={
                                            "resource_type": "slot_connection_string",
                                            "slot_name": slot_name,
                                            "connection_type": conn_info.type,
                                        },
                                    )
                                )

                    except (AzureError, HttpResponseError) as e:
                        self.logger.warning(
                            f"Failed to discover connection strings for slot {slot_name}: {e}"
                        )

                if slot_count > 0:
                    self.logger.info(f"Discovered {slot_count} deployment slots")

            except (AzureError, HttpResponseError) as e:
                self.logger.warning(
                    f"Failed to discover deployment slots for {app_name}: {e}"
                )

        except ImportError as e:
            self.logger.error(
                f"Azure Web SDK not installed. Install with: "
                f"pip install azure-mgmt-web. "
                f"Error: {e}"
            )
        except Exception as e:
            self.logger.error(f"Unexpected error discovering App Service items: {e}")

        self.logger.info(
            f"Discovered {len(items)} total data plane items in App Service '{app_name}'"
        )
        return items

    def generate_replication_code(
        self, items: List[DataPlaneItem], output_format: str = "terraform"
    ) -> str:
        """
        Generate IaC code to replicate App Service data plane items.

        For app settings and connection strings, this generates:
        - azurerm_app_service_application_settings resources
        - azurerm_app_service_connection_string resources
        - Variables for sensitive values
        - Deployment slot configurations

        Security note: Actual sensitive values are never included in generated
        code. Users must manually populate secrets or integrate with external
        secret management systems.

        Args:
            items: List of App Service data plane items to replicate
            output_format: IaC format ("terraform", "bicep", "arm")

        Returns:
            String containing IaC code with placeholders for data plane items

        Raises:
            ValueError: If output_format is not supported

        Example:
            >>> items = [DataPlaneItem(name="DB_HOST", item_type="app_setting", ...)]
            >>> code = plugin.generate_replication_code(items)
            >>> "app_settings" in code
            True
        """
        if not self.supports_output_format(output_format):
            raise ValueError(
                f"Output format '{output_format}' not supported by AppServicePlugin"
            )

        if output_format.lower() != "terraform":
            # Future: Support Bicep and ARM templates
            raise ValueError("Only Terraform format is currently supported")

        self.logger.info(
            f"Generating {output_format} code for {len(items)} App Service items"
        )

        if not items:
            return "# No App Service data plane items to replicate\n"

        code_lines = [
            "# App Service Data Plane Items",
            "# Generated by Azure Tenant Grapher - AppServicePlugin",
            "#",
            "# SECURITY NOTE: Sensitive values are not included in generated code.",
            "# You must manually populate secrets after deployment or integrate",
            "# with external secret management (e.g., Azure Key Vault, GitHub Secrets).",
            "",
        ]

        # Group items by type
        app_settings = [item for item in items if item.item_type == "app_setting"]
        connection_strings = [
            item for item in items if item.item_type == "connection_string"
        ]
        deployment_slots = [
            item for item in items if item.item_type == "deployment_slot"
        ]
        slot_app_settings = [
            item for item in items if item.item_type == "slot_app_setting"
        ]
        slot_conn_strings = [
            item for item in items if item.item_type == "slot_connection_string"
        ]

        # Generate app settings block
        if app_settings:
            code_lines.append("# App Settings")
            code_lines.append(
                "# Add these to your azurerm_app_service or azurerm_linux_web_app resource:"
            )
            code_lines.append("#")
            code_lines.append("# app_settings = {")

            for item in app_settings:
                is_sensitive = item.properties.get("is_sensitive", False)
                if is_sensitive:
                    var_name = self._sanitize_name(item.name)
                    code_lines.append(f"#   {item.name} = var.app_setting_{var_name}")
                else:
                    value = item.properties.get("value", "")
                    code_lines.append(f'#   {item.name} = "{value}"')

            code_lines.append("# }")
            code_lines.append("")

        # Generate connection strings block
        if connection_strings:
            code_lines.append("# Connection Strings")
            code_lines.append(
                "# Add these to your azurerm_app_service or azurerm_linux_web_app resource:"
            )
            code_lines.append("#")

            for item in connection_strings:
                resource_name = self._sanitize_name(item.name)
                conn_type = item.properties.get("type", "Custom")

                code_lines.extend(
                    [
                        "# connection_string {",
                        f'#   name  = "{item.name}"',
                        f'#   type  = "{conn_type}"',
                        f"#   value = var.connection_string_{resource_name}",
                        "# }",
                        "#",
                    ]
                )

        # Generate deployment slot configurations
        if deployment_slots:
            code_lines.append("# Deployment Slots")
            code_lines.append("# Create separate slot resources:")
            code_lines.append("")

            for slot in deployment_slots:
                slot_name = slot.name
                resource_name = self._sanitize_name(slot_name)

                code_lines.extend(
                    [
                        f'resource "azurerm_app_service_slot" "{resource_name}" {{',
                        f'  name                = "{slot_name}"',
                        "  # TODO: Reference your App Service resource here",
                        "  app_service_name    = azurerm_app_service.REPLACE_ME.name",
                        "  resource_group_name = azurerm_app_service.REPLACE_ME.resource_group_name",
                        "  location            = azurerm_app_service.REPLACE_ME.location",
                        "  app_service_plan_id = azurerm_app_service.REPLACE_ME.app_service_plan_id",
                        "",
                    ]
                )

                # Add slot-specific app settings
                slot_settings = [
                    item
                    for item in slot_app_settings
                    if item.properties.get("slot_name") == slot_name
                ]

                if slot_settings:
                    code_lines.append("  app_settings = {")
                    for setting in slot_settings:
                        setting_name = setting.name.split("/")[-1]  # Remove slot prefix
                        is_sensitive = setting.properties.get("is_sensitive", False)

                        if is_sensitive:
                            var_name = self._sanitize_name(
                                f"{slot_name}_{setting_name}"
                            )
                            code_lines.append(
                                f"    {setting_name} = var.slot_setting_{var_name}"
                            )
                        else:
                            value = setting.properties.get("value", "")
                            code_lines.append(f'    {setting_name} = "{value}"')

                    code_lines.append("  }")
                    code_lines.append("")

                # Add slot-specific connection strings
                slot_conns = [
                    item
                    for item in slot_conn_strings
                    if item.properties.get("slot_name") == slot_name
                ]

                for conn in slot_conns:
                    conn_name = conn.name.split("/")[-1]  # Remove slot prefix
                    conn_type = conn.properties.get("type", "Custom")
                    var_name = self._sanitize_name(f"{slot_name}_{conn_name}")

                    code_lines.extend(
                        [
                            "  connection_string {",
                            f'    name  = "{conn_name}"',
                            f'    type  = "{conn_type}"',
                            f"    value = var.slot_connection_{var_name}",
                            "  }",
                            "",
                        ]
                    )

                code_lines.append("}")
                code_lines.append("")

        # Generate variable declarations for sensitive values
        code_lines.append("# Required variables for sensitive values")

        # Variables for app settings
        for item in app_settings:
            if item.properties.get("is_sensitive", False):
                var_name = self._sanitize_name(item.name)
                code_lines.extend(
                    [
                        f'variable "app_setting_{var_name}" {{',
                        f'  description = "Value for app setting {item.name} (set via environment or tfvars)"',
                        "  type        = string",
                        "  sensitive   = true",
                        "}",
                        "",
                    ]
                )

        # Variables for connection strings
        for item in connection_strings:
            var_name = self._sanitize_name(item.name)
            code_lines.extend(
                [
                    f'variable "connection_string_{var_name}" {{',
                    f'  description = "Value for connection string {item.name} (set via environment or tfvars)"',
                    "  type        = string",
                    "  sensitive   = true",
                    "}",
                    "",
                ]
            )

        # Variables for slot settings
        for item in slot_app_settings:
            if item.properties.get("is_sensitive", False):
                slot_name = item.properties.get("slot_name", "")
                setting_name = item.name.split("/")[-1]
                var_name = self._sanitize_name(f"{slot_name}_{setting_name}")
                code_lines.extend(
                    [
                        f'variable "slot_setting_{var_name}" {{',
                        f'  description = "Value for slot {slot_name} app setting {setting_name}"',
                        "  type        = string",
                        "  sensitive   = true",
                        "}",
                        "",
                    ]
                )

        # Variables for slot connection strings
        for item in slot_conn_strings:
            slot_name = item.properties.get("slot_name", "")
            conn_name = item.name.split("/")[-1]
            var_name = self._sanitize_name(f"{slot_name}_{conn_name}")
            code_lines.extend(
                [
                    f'variable "slot_connection_{var_name}" {{',
                    f'  description = "Value for slot {slot_name} connection string {conn_name}"',
                    "  type        = string",
                    "  sensitive   = true",
                    "}",
                    "",
                ]
            )

        return "\n".join(code_lines)

    def replicate(
        self, source_resource: Dict[str, Any], target_resource: Dict[str, Any]
    ) -> ReplicationResult:
        """
        Replicate App Service configuration from source to target.

        This is a stub implementation that delegates to replicate_with_mode.
        Use replicate_with_mode for mode-aware replication.

        Args:
            source_resource: Source App Service resource
            target_resource: Target App Service resource

        Returns:
            ReplicationResult with operation statistics
        """
        # Default to replication mode for backward compatibility
        return self.replicate_with_mode(
            source_resource, target_resource, ReplicationMode.REPLICATION
        )

    def _sanitize_name(self, name: str) -> str:
        """
        Sanitize a name for use in Terraform resource names.

        Args:
            name: Original name (may contain special chars)

        Returns:
            Sanitized name safe for Terraform identifiers
        """
        # Replace special chars with underscores
        sanitized = name.replace("-", "_").replace(".", "_").replace(" ", "_")
        sanitized = sanitized.replace("/", "_").replace(":", "_")

        # Ensure it starts with a letter
        if sanitized and not sanitized[0].isalpha():
            sanitized = "app_" + sanitized

        return sanitized.lower()

    def _is_sensitive_key(self, key: str) -> bool:
        """
        Determine if an app setting key likely contains sensitive data.

        Args:
            key: App setting key name

        Returns:
            True if key appears to contain sensitive data
        """
        sensitive_keywords = [
            "password",
            "secret",
            "key",
            "token",
            "connectionstring",
            "connection_string",
            "apikey",
            "api_key",
            "credential",
            "cert",
            "certificate",
        ]

        key_lower = key.lower()
        return any(keyword in key_lower for keyword in sensitive_keywords)

    # ============ MODE-AWARE METHODS ============

    def get_required_permissions(self, mode: ReplicationMode) -> List[Permission]:
        """
        Return required permissions for App Service operations.

        Template mode: Read-only permissions to list configuration
        Replication mode: Read/write permissions to get and set configuration

        Args:
            mode: Replication mode

        Returns:
            List of required permissions
        """
        if mode == ReplicationMode.TEMPLATE:
            return [
                Permission(
                    scope="resource",
                    actions=[
                        "Microsoft.Web/sites/read",
                        "Microsoft.Web/sites/config/read",
                        "Microsoft.Web/sites/slots/read",
                        "Microsoft.Web/sites/slots/config/read",
                    ],
                    data_actions=[],
                    description="Website Contributor (Read) - list app settings and connection strings",
                )
            ]
        else:  # REPLICATION mode
            return [
                Permission(
                    scope="resource",
                    actions=[
                        "Microsoft.Web/sites/read",
                        "Microsoft.Web/sites/config/read",
                        "Microsoft.Web/sites/config/write",
                        "Microsoft.Web/sites/slots/read",
                        "Microsoft.Web/sites/slots/config/read",
                        "Microsoft.Web/sites/slots/config/write",
                    ],
                    data_actions=[],
                    description="Website Contributor - read and write app settings and connection strings",
                )
            ]

    def discover_with_mode(
        self, resource: Dict[str, Any], mode: ReplicationMode
    ) -> List[DataPlaneItem]:
        """
        Discover App Service configuration with mode awareness.

        Template mode: Discover configuration names and structure (mask sensitive values)
        Replication mode: Discover full configuration including actual values

        Args:
            resource: App Service resource
            mode: Replication mode

        Returns:
            List of discovered items (detail level varies by mode)
        """
        if mode == ReplicationMode.TEMPLATE:
            # In template mode, mask sensitive values
            items = self.discover(resource)

            for item in items:
                if item.properties.get("is_sensitive", False):
                    # Replace actual value with placeholder
                    item.properties["value"] = "PLACEHOLDER-SET-MANUALLY"

            return items
        else:
            # In replication mode, return full values
            return self.discover(resource)

    def replicate_with_mode(
        self,
        source_resource: Dict[str, Any],
        target_resource: Dict[str, Any],
        mode: ReplicationMode,
    ) -> ReplicationResult:
        """
        Replicate App Service configuration with mode awareness.

        Template mode: Create configuration structure with placeholder values
        Replication mode: Copy actual configuration values from source to target

        Args:
            source_resource: Source App Service resource
            target_resource: Target App Service resource
            mode: Replication mode

        Returns:
            ReplicationResult with operation statistics
        """
        start_time = time.time()

        if not self.validate_resource(source_resource):
            raise ValueError(f"Invalid source resource: {source_resource}")

        if not self.validate_resource(target_resource):
            raise ValueError(f"Invalid target resource: {target_resource}")

        source_name = source_resource.get("name", "unknown")
        target_name = target_resource.get("name", "unknown")

        self.logger.info(
            f"Replicating App Service from '{source_name}' to '{target_name}' "
            f"(mode={mode.value})"
        )

        try:
            # Discover items from source
            items = self.discover_with_mode(source_resource, mode)

            if self.progress_reporter:
                self.progress_reporter.report_discovery(
                    source_resource["id"], len(items)
                )

            if mode == ReplicationMode.TEMPLATE:
                # Template mode: Create configuration with placeholder values
                result = self._replicate_template_mode(
                    source_resource, target_resource, items
                )
            else:
                # Replication mode: Copy actual configuration values
                result = self._replicate_full_mode(
                    source_resource, target_resource, items
                )

            # Add timing information
            result.duration_seconds = time.time() - start_time

            if self.progress_reporter:
                self.progress_reporter.report_completion(result)

            return result

        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Failed to replicate App Service: {e!s}"
            self.logger.error(error_msg)

            return ReplicationResult(
                success=False,
                items_discovered=0,
                items_replicated=0,
                items_skipped=0,
                errors=[error_msg],
                warnings=[],
                duration_seconds=duration,
            )

    def _replicate_template_mode(
        self,
        source_resource: Dict[str, Any],
        target_resource: Dict[str, Any],
        items: List[DataPlaneItem],
    ) -> ReplicationResult:
        """
        Replicate in template mode: create configuration with placeholder values.

        Args:
            source_resource: Source App Service
            target_resource: Target App Service
            items: Items discovered from source

        Returns:
            ReplicationResult
        """
        from azure.core.exceptions import AzureError, HttpResponseError
        from azure.identity import DefaultAzureCredential
        from azure.mgmt.web import WebSiteManagementClient
        from azure.mgmt.web.models import ConnStringValueTypePair, StringDictionary

        # Get credentials
        if self.credential_provider:
            credential = self.credential_provider.get_credential()
        else:
            credential = DefaultAzureCredential()

        # Parse target resource ID
        target_id = target_resource.get("id", "")
        parts = target_id.split("/")

        if len(parts) < 9:
            return ReplicationResult(
                success=False,
                items_discovered=len(items),
                items_replicated=0,
                items_skipped=len(items),
                errors=[f"Invalid target resource ID: {target_id}"],
                warnings=[],
            )

        subscription_id = parts[2]
        resource_group = parts[4]
        target_name = target_resource.get("name")

        web_client = WebSiteManagementClient(credential, subscription_id)

        # Group items by type
        app_settings = [item for item in items if item.item_type == "app_setting"]
        connection_strings = [
            item for item in items if item.item_type == "connection_string"
        ]
        deployment_slots = [
            item for item in items if item.item_type == "deployment_slot"
        ]

        replicated = 0
        skipped = 0
        errors = []
        warnings = []

        # Create app settings with placeholder values
        if app_settings:
            try:
                settings_dict = {}
                for item in app_settings:
                    # Use placeholder for all values in template mode
                    settings_dict[item.name] = "PLACEHOLDER-SET-MANUALLY"

                web_client.web_apps.update_application_settings(
                    resource_group_name=resource_group,
                    name=target_name,
                    app_settings=StringDictionary(properties=settings_dict),
                )
                replicated += len(app_settings)

                if self.progress_reporter:
                    progress = (replicated / len(items)) * 100
                    self.progress_reporter.report_replication_progress(
                        "app_settings", progress
                    )

            except (AzureError, HttpResponseError) as e:
                errors.append(f"Failed to create app settings: {e!s}")
                skipped += len(app_settings)

        # Create connection strings with placeholder values
        if connection_strings:
            try:
                conn_dict = {}
                for item in connection_strings:
                    conn_type = item.properties.get("type", "Custom")
                    conn_dict[item.name] = ConnStringValueTypePair(
                        value="PLACEHOLDER-SET-MANUALLY", type=conn_type
                    )

                web_client.web_apps.update_connection_strings(
                    resource_group_name=resource_group,
                    name=target_name,
                    connection_strings=StringDictionary(properties=conn_dict),
                )
                replicated += len(connection_strings)

                if self.progress_reporter:
                    progress = (replicated / len(items)) * 100
                    self.progress_reporter.report_replication_progress(
                        "connection_strings", progress
                    )

            except (AzureError, HttpResponseError) as e:
                errors.append(f"Failed to create connection strings: {e!s}")
                skipped += len(connection_strings)

        # Deployment slots are not created in template mode
        if deployment_slots:
            warnings.append(
                f"Template mode: {len(deployment_slots)} deployment slots not created "
                "(create slots manually or use replication mode)"
            )
            skipped += len(deployment_slots)

        warnings.append(
            "Template mode: Configuration created with placeholder values. "
            "You must manually set actual values after deployment."
        )

        return ReplicationResult(
            success=len(errors) == 0,
            items_discovered=len(items),
            items_replicated=replicated,
            items_skipped=skipped,
            errors=errors,
            warnings=warnings,
        )

    def _replicate_full_mode(
        self,
        source_resource: Dict[str, Any],
        target_resource: Dict[str, Any],
        items: List[DataPlaneItem],
    ) -> ReplicationResult:
        """
        Replicate in full mode: copy actual configuration values.

        Args:
            source_resource: Source App Service
            target_resource: Target App Service
            items: Items discovered from source

        Returns:
            ReplicationResult
        """
        from azure.core.exceptions import AzureError, HttpResponseError
        from azure.identity import DefaultAzureCredential
        from azure.mgmt.web import WebSiteManagementClient
        from azure.mgmt.web.models import ConnStringValueTypePair, StringDictionary

        # Get credentials
        if self.credential_provider:
            credential = self.credential_provider.get_credential()
        else:
            credential = DefaultAzureCredential()

        # Parse target resource ID
        target_id = target_resource.get("id", "")
        parts = target_id.split("/")

        if len(parts) < 9:
            return ReplicationResult(
                success=False,
                items_discovered=len(items),
                items_replicated=0,
                items_skipped=len(items),
                errors=[f"Invalid target resource ID: {target_id}"],
                warnings=[],
            )

        subscription_id = parts[2]
        resource_group = parts[4]
        target_name = target_resource.get("name")

        web_client = WebSiteManagementClient(credential, subscription_id)

        # Group items by type
        app_settings = [item for item in items if item.item_type == "app_setting"]
        connection_strings = [
            item for item in items if item.item_type == "connection_string"
        ]
        deployment_slots = [
            item for item in items if item.item_type == "deployment_slot"
        ]
        slot_settings = [item for item in items if item.item_type == "slot_app_setting"]
        slot_conns = [
            item for item in items if item.item_type == "slot_connection_string"
        ]

        replicated = 0
        skipped = 0
        errors = []
        warnings = []

        # Replicate app settings with actual values
        if app_settings:
            try:
                settings_dict = {}
                for item in app_settings:
                    settings_dict[item.name] = item.properties.get("value", "")

                web_client.web_apps.update_application_settings(
                    resource_group_name=resource_group,
                    name=target_name,
                    app_settings=StringDictionary(properties=settings_dict),
                )
                replicated += len(app_settings)

                if self.progress_reporter:
                    progress = (replicated / len(items)) * 100
                    self.progress_reporter.report_replication_progress(
                        "app_settings", progress
                    )

            except (AzureError, HttpResponseError) as e:
                errors.append(f"Failed to replicate app settings: {e!s}")
                skipped += len(app_settings)

        # Replicate connection strings with actual values
        if connection_strings:
            try:
                conn_dict = {}
                for item in connection_strings:
                    conn_type = item.properties.get("type", "Custom")
                    conn_dict[item.name] = ConnStringValueTypePair(
                        value=item.properties.get("value", ""), type=conn_type
                    )

                web_client.web_apps.update_connection_strings(
                    resource_group_name=resource_group,
                    name=target_name,
                    connection_strings=StringDictionary(properties=conn_dict),
                )
                replicated += len(connection_strings)

                if self.progress_reporter:
                    progress = (replicated / len(items)) * 100
                    self.progress_reporter.report_replication_progress(
                        "connection_strings", progress
                    )

            except (AzureError, HttpResponseError) as e:
                errors.append(f"Failed to replicate connection strings: {e!s}")
                skipped += len(connection_strings)

        # Handle deployment slots
        if deployment_slots:
            warnings.append(
                f"Replication mode: {len(deployment_slots)} deployment slots discovered "
                "but slot creation requires manual configuration (slots should be created via control plane)"
            )
            skipped += len(deployment_slots)

        # Replicate slot-specific settings
        for slot_item in deployment_slots:
            slot_name = slot_item.name

            # Slot app settings
            slot_app_settings = [
                item
                for item in slot_settings
                if item.properties.get("slot_name") == slot_name
            ]

            if slot_app_settings:
                try:
                    settings_dict = {}
                    for item in slot_app_settings:
                        setting_name = item.name.split("/")[-1]
                        settings_dict[setting_name] = item.properties.get("value", "")

                    web_client.web_apps.update_application_settings_slot(
                        resource_group_name=resource_group,
                        name=target_name,
                        slot=slot_name,
                        app_settings=StringDictionary(properties=settings_dict),
                    )
                    replicated += len(slot_app_settings)

                except (AzureError, HttpResponseError) as e:
                    errors.append(
                        f"Failed to replicate app settings for slot {slot_name}: {e!s}"
                    )
                    skipped += len(slot_app_settings)

            # Slot connection strings
            slot_conn_strings = [
                item
                for item in slot_conns
                if item.properties.get("slot_name") == slot_name
            ]

            if slot_conn_strings:
                try:
                    conn_dict = {}
                    for item in slot_conn_strings:
                        conn_name = item.name.split("/")[-1]
                        conn_type = item.properties.get("type", "Custom")
                        conn_dict[conn_name] = ConnStringValueTypePair(
                            value=item.properties.get("value", ""), type=conn_type
                        )

                    web_client.web_apps.update_connection_strings_slot(
                        resource_group_name=resource_group,
                        name=target_name,
                        slot=slot_name,
                        connection_strings=StringDictionary(properties=conn_dict),
                    )
                    replicated += len(slot_conn_strings)

                except (AzureError, HttpResponseError) as e:
                    errors.append(
                        f"Failed to replicate connection strings for slot {slot_name}: {e!s}"
                    )
                    skipped += len(slot_conn_strings)

        warnings.append(
            "Replication mode: Actual configuration values have been copied. "
            "Review security implications of copying secrets across tenants."
        )

        return ReplicationResult(
            success=len(errors) == 0,
            items_discovered=len(items),
            items_replicated=replicated,
            items_skipped=skipped,
            errors=errors,
            warnings=warnings,
        )
