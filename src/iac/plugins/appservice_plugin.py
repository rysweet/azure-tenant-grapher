"""
App Service data plane replication plugin.

This plugin handles discovery and replication of Azure App Service data plane
items including:
- Application settings (environment variables)
- Connection strings
- Configuration settings
- Deployment slots

The plugin integrates with the IaC generation process to ensure that App Service
configurations are preserved when deploying to new environments.
"""

import logging
from typing import Any, Dict, List

from .base_plugin import DataPlaneItem, DataPlanePlugin, ReplicationResult

logger = logging.getLogger(__name__)


class AppServicePlugin(DataPlanePlugin):
    """
    Data plane plugin for Azure App Service.

    Discovers and replicates app settings, connection strings, and configurations
    using Azure SDK.

    Example:
        plugin = AppServicePlugin()
        items = plugin.discover(app_service_resource)
        code = plugin.generate_replication_code(items, "terraform")
    """

    @property
    def supported_resource_type(self) -> str:
        """Azure resource type for App Service."""
        return "Microsoft.Web/sites"

    def discover(self, resource: Dict[str, Any]) -> List[DataPlaneItem]:
        """
        Discover App Service settings and configuration.

        Uses Azure SDK to:
        1. Authenticate to the App Service
        2. List application settings
        3. List connection strings
        4. Get configuration settings
        5. List deployment slots

        Args:
            resource: App Service resource dictionary containing:
                - id: App Service resource ID
                - name: App Service name
                - properties: App Service properties

        Returns:
            List of DataPlaneItem representing app settings and config

        Example:
            >>> resource = {
            ...     "id": "/subscriptions/.../sites/my-app",
            ...     "type": "Microsoft.Web/sites",
            ...     "name": "my-app"
            ... }
            >>> items = plugin.discover(resource)
            >>> len(items)  # Returns count of settings/config items
        """
        if not self.validate_resource(resource):
            raise ValueError(f"Invalid resource for AppServicePlugin: {resource}")

        app_name = resource.get("name", "unknown")
        resource_id = resource.get("id", "")
        self.logger.info(f"Discovering data plane items for App Service: {app_name}")

        items: List[DataPlaneItem] = []

        try:
            # Import Azure SDK components
            from azure.core.exceptions import AzureError, HttpResponseError
            from azure.identity import DefaultAzureCredential
            from azure.mgmt.web import WebSiteManagementClient

            # Parse subscription ID and resource group from resource ID
            # Format: /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Web/sites/{name}
            parts = resource_id.split("/")
            if len(parts) < 9:
                self.logger.error(
                    f"Invalid resource ID format: {resource_id}. "
                    "Expected: /subscriptions/.../resourceGroups/.../providers/Microsoft.Web/sites/..."
                )
                return items

            subscription_id = parts[2]
            resource_group_name = parts[4]

            # Authenticate
            credential = DefaultAzureCredential()
            web_client = WebSiteManagementClient(credential, subscription_id)

            # Discover application settings
            try:
                app_settings_response = web_client.web_apps.list_application_settings(
                    resource_group_name=resource_group_name, name=app_name
                )

                if app_settings_response and hasattr(
                    app_settings_response, "properties"
                ):
                    app_settings = app_settings_response.properties or {}

                    for key, value in app_settings.items():
                        # Skip system-managed settings (Azure manages these)
                        if key.startswith("WEBSITE_") or key.startswith("APPSETTING_"):
                            self.logger.debug(f"Skipping system setting: {key}")
                            continue

                        items.append(
                            DataPlaneItem(
                                name=key,
                                item_type="app_setting",
                                properties={
                                    "value": value,
                                    "slot_setting": False,  # Default, actual value requires additional API call
                                },
                                source_resource_id=resource_id,
                                metadata={
                                    "sensitive": self._is_sensitive_key(key),
                                },
                            )
                        )

                    self.logger.info(
                        f"Discovered {len([i for i in items if i.item_type == 'app_setting'])} "
                        f"application settings"
                    )

            except (AzureError, HttpResponseError) as e:
                self.logger.warning(
                    f"Failed to discover application settings in {app_name}: {e}"
                )

            # Discover connection strings
            try:
                conn_strings_response = web_client.web_apps.list_connection_strings(
                    resource_group_name=resource_group_name, name=app_name
                )

                if conn_strings_response and hasattr(
                    conn_strings_response, "properties"
                ):
                    conn_strings = conn_strings_response.properties or {}

                    for key, conn_string_dict in conn_strings.items():
                        # conn_string_dict has 'value' and 'type' properties
                        items.append(
                            DataPlaneItem(
                                name=key,
                                item_type="connection_string",
                                properties={
                                    "value": conn_string_dict.value
                                    if hasattr(conn_string_dict, "value")
                                    else str(conn_string_dict),
                                    "type": conn_string_dict.type
                                    if hasattr(conn_string_dict, "type")
                                    else "Custom",
                                    "slot_setting": False,
                                },
                                source_resource_id=resource_id,
                                metadata={
                                    "sensitive": True,  # Always sensitive
                                },
                            )
                        )

                    self.logger.info(
                        f"Discovered {len([i for i in items if i.item_type == 'connection_string'])} "
                        f"connection strings"
                    )

            except (AzureError, HttpResponseError) as e:
                self.logger.warning(
                    f"Failed to discover connection strings in {app_name}: {e}"
                )

            # Discover site configuration
            try:
                site_config = web_client.web_apps.get_configuration(
                    resource_group_name=resource_group_name, name=app_name
                )

                # Extract key configuration properties
                config_props = {}

                # Platform settings
                if hasattr(site_config, "always_on"):
                    always_on_val = site_config.always_on
                    if always_on_val is not None:
                        config_props["always_on"] = always_on_val
                if hasattr(site_config, "http20_enabled"):
                    http20_val = site_config.http20_enabled
                    if http20_val is not None:
                        config_props["http20_enabled"] = http20_val
                if hasattr(site_config, "ftps_state") and site_config.ftps_state:
                    config_props["ftps_state"] = site_config.ftps_state
                if (
                    hasattr(site_config, "min_tls_version")
                    and site_config.min_tls_version
                ):
                    config_props["min_tls_version"] = site_config.min_tls_version

                # Stack settings
                if (
                    hasattr(site_config, "linux_fx_version")
                    and site_config.linux_fx_version
                ):
                    config_props["linux_fx_version"] = site_config.linux_fx_version
                if (
                    hasattr(site_config, "windows_fx_version")
                    and site_config.windows_fx_version
                ):
                    config_props["windows_fx_version"] = site_config.windows_fx_version

                if config_props:
                    items.append(
                        DataPlaneItem(
                            name="site_config",
                            item_type="configuration",
                            properties=config_props,
                            source_resource_id=resource_id,
                            metadata={},
                        )
                    )

                    self.logger.info("Discovered site configuration")

            except (AzureError, HttpResponseError) as e:
                self.logger.warning(
                    f"Failed to discover site configuration in {app_name}: {e}"
                )

            # Discover deployment slots
            try:
                slots = web_client.web_apps.list_slots(
                    resource_group_name=resource_group_name, name=app_name
                )

                slot_count = 0
                for slot in slots:
                    slot_full_name = (
                        slot.name if hasattr(slot, "name") and slot.name else ""
                    )
                    slot_name = (
                        slot_full_name.split("/")[-1]
                        if "/" in slot_full_name
                        else slot_full_name
                    )
                    if slot_name == app_name or not slot_name:
                        # Skip production slot (already covered) or empty slot names
                        continue

                    items.append(
                        DataPlaneItem(
                            name=slot_name,
                            item_type="deployment_slot",
                            properties={
                                "location": slot.location
                                if hasattr(slot, "location")
                                else None,
                                "state": slot.state if hasattr(slot, "state") else None,
                                "enabled": slot.enabled
                                if hasattr(slot, "enabled")
                                else True,
                            },
                            source_resource_id=resource_id,
                            metadata={},
                        )
                    )
                    slot_count += 1

                if slot_count > 0:
                    self.logger.info(f"Discovered {slot_count} deployment slots")

            except (AzureError, HttpResponseError) as e:
                self.logger.warning(
                    f"Failed to discover deployment slots in {app_name}: {e}"
                )

        except ImportError as e:
            self.logger.error(
                f"Azure Web SDK not installed. Install with: "
                f"pip install azure-mgmt-web. Error: {e}"
            )
        except Exception as e:
            self.logger.error(
                f"Unexpected error discovering App Service items: {e}", exc_info=True
            )

        self.logger.info(
            f"Discovered {len(items)} data plane items in App Service '{app_name}'"
        )
        return items

    def generate_replication_code(
        self, items: List[DataPlaneItem], output_format: str = "terraform"
    ) -> str:
        """
        Generate IaC code to replicate App Service configurations.

        For app settings and connection strings, this generates:
        - Terraform resources for app settings
        - Terraform resources for connection strings
        - Documentation about deployment methods
        - Security warnings for sensitive values

        Security note: Connection string values are parameterized as variables.
        Users must provide actual values via terraform.tfvars or environment variables.

        Args:
            items: List of App Service data plane items to replicate
            output_format: IaC format ("terraform", "bicep", "arm")

        Returns:
            String containing IaC code with App Service configuration

        Raises:
            ValueError: If output_format is not supported

        Example:
            >>> items = [DataPlaneItem(name="DB_HOST", item_type="app_setting", ...)]
            >>> code = plugin.generate_replication_code(items)
            >>> "azurerm_linux_web_app" in code or "azurerm_windows_web_app" in code
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
            "# SECURITY NOTE: Sensitive values (connection strings, secrets) are not included.",
            "# You must provide these values via terraform.tfvars or environment variables.",
            "#",
            "# DEPLOYMENT NOTE: This code only replicates configuration.",
            "# Application code must be deployed separately using:",
            "#   - Azure DevOps Pipelines",
            "#   - GitHub Actions",
            "#   - Git deployment (az webapp deployment source config)",
            "#   - ZIP deployment (az webapp deployment source config-zip)",
            "#   - FTP/FTPS",
            "",
        ]

        # Group items by type
        app_settings = [item for item in items if item.item_type == "app_setting"]
        connection_strings = [
            item for item in items if item.item_type == "connection_string"
        ]
        configurations = [item for item in items if item.item_type == "configuration"]
        deployment_slots = [
            item for item in items if item.item_type == "deployment_slot"
        ]

        # Generate app settings
        if app_settings:
            code_lines.append("# Application Settings")
            code_lines.append(
                "# Add these to your azurerm_linux_web_app or azurerm_windows_web_app resource:"
            )
            code_lines.append("#")
            code_lines.append("# app_settings = {")

            for item in app_settings:
                metadata = item.metadata or {}
                is_sensitive = metadata.get("sensitive", False)
                value = item.properties.get("value", "")

                if is_sensitive or self._is_sensitive_key(item.name):
                    # Use variable reference for sensitive values
                    code_lines.append(
                        f'#   "{item.name}" = var.app_setting_{self._sanitize_name(item.name)}'
                    )
                else:
                    # Include non-sensitive values directly
                    escaped_value = self._escape_terraform_string(str(value))
                    code_lines.append(f'#   "{item.name}" = "{escaped_value}"')

            code_lines.append("# }")
            code_lines.append("")

        # Generate connection strings
        if connection_strings:
            code_lines.append("# Connection Strings")
            code_lines.append(
                "# Add these to your azurerm_linux_web_app or azurerm_windows_web_app resource:"
            )
            code_lines.append("#")

            for item in connection_strings:
                conn_type = item.properties.get("type", "Custom")
                sanitized_name = self._sanitize_name(item.name)

                code_lines.extend(
                    [
                        "# connection_string {",
                        f'#   name  = "{item.name}"',
                        f'#   type  = "{conn_type}"',
                        f"#   value = var.connection_string_{sanitized_name}",
                        "# }",
                        "#",
                    ]
                )

            code_lines.append("")

        # Generate site configuration notes
        if configurations:
            code_lines.append("# Site Configuration")
            code_lines.append(
                "# Add these to your azurerm_linux_web_app or azurerm_windows_web_app resource:"
            )
            code_lines.append("#")
            code_lines.append("# site_config {")

            config = configurations[0]  # Should only be one
            props = config.properties

            always_on = props.get("always_on")
            if always_on is not None:
                code_lines.append(f"#   always_on = {str(always_on).lower()}")
            http20_enabled = props.get("http20_enabled")
            if http20_enabled is not None:
                code_lines.append(f"#   http2_enabled = {str(http20_enabled).lower()}")
            ftps_state = props.get("ftps_state")
            if ftps_state:
                code_lines.append(f'#   ftps_state = "{ftps_state}"')
            min_tls_version = props.get("min_tls_version")
            if min_tls_version:
                code_lines.append(f'#   minimum_tls_version = "{min_tls_version}"')
            linux_fx_version = props.get("linux_fx_version")
            if linux_fx_version:
                code_lines.append(f'#   linux_fx_version = "{linux_fx_version}"')
            windows_fx_version = props.get("windows_fx_version")
            if windows_fx_version:
                code_lines.append(f'#   windows_fx_version = "{windows_fx_version}"')

            code_lines.append("# }")
            code_lines.append("")

        # Generate deployment slot resources
        if deployment_slots:
            code_lines.append("# Deployment Slots")
            for item in deployment_slots:
                sanitized_name = self._sanitize_name(item.name)
                code_lines.extend(
                    [
                        f'# resource "azurerm_linux_web_app_slot" "{sanitized_name}" {{',
                        f'#   name           = "{item.name}"',
                        "#   app_service_id = azurerm_linux_web_app.REPLACE_ME.id",
                        "#",
                        "#   site_config {",
                        "#     # Copy site_config from main app",
                        "#   }",
                        "# }",
                        "",
                    ]
                )

        # Generate variable declarations for sensitive values
        sensitive_settings = [
            item
            for item in app_settings
            if (item.metadata and item.metadata.get("sensitive", False))
            or self._is_sensitive_key(item.name)
        ]

        if sensitive_settings or connection_strings:
            code_lines.append("# Required Variables")
            code_lines.append(
                "# Add these variable declarations to your variables.tf file:"
            )
            code_lines.append("")

            # Variables for sensitive app settings
            for item in sensitive_settings:
                sanitized_name = self._sanitize_name(item.name)
                code_lines.extend(
                    [
                        f'# variable "app_setting_{sanitized_name}" {{',
                        f'#   description = "Value for app setting: {item.name}"',
                        "#   type        = string",
                        "#   sensitive   = true",
                        "# }",
                        "#",
                    ]
                )

            # Variables for connection strings
            for item in connection_strings:
                sanitized_name = self._sanitize_name(item.name)
                code_lines.extend(
                    [
                        f'# variable "connection_string_{sanitized_name}" {{',
                        f'#   description = "Connection string: {item.name}"',
                        "#   type        = string",
                        "#   sensitive   = true",
                        "# }",
                        "#",
                    ]
                )

        # Add deployment guidance
        code_lines.extend(
            [
                "",
                "# Application Deployment Guide",
                "#",
                "# After deploying the infrastructure, deploy your application code using one of:",
                "#",
                "# 1. Azure CLI ZIP deployment:",
                "#    az webapp deployment source config-zip \\",
                "#      --resource-group <rg> \\",
                "#      --name <app-name> \\",
                "#      --src app.zip",
                "#",
                "# 2. Git deployment:",
                "#    az webapp deployment source config \\",
                "#      --name <app-name> \\",
                "#      --resource-group <rg> \\",
                "#      --repo-url <git-url> \\",
                "#      --branch main \\",
                "#      --manual-integration",
                "#",
                "# 3. GitHub Actions or Azure DevOps:",
                "#    Set up CI/CD pipeline using the deployment credentials",
                "#",
                "# 4. Container deployment (for containerized apps):",
                "#    Set DOCKER_REGISTRY_SERVER_URL, DOCKER_REGISTRY_SERVER_USERNAME,",
                "#    and DOCKER_REGISTRY_SERVER_PASSWORD in app settings",
                "",
            ]
        )

        return "\n".join(code_lines)

    def replicate(
        self, source_resource: Dict[str, Any], target_resource: Dict[str, Any]
    ) -> ReplicationResult:
        """
        Replicate App Service settings from source to target.

        This method:
        1. Discovers all settings from the source App Service
        2. Connects to the target App Service
        3. Replicates app settings and connection strings
        4. Handles permission errors and conflicts
        5. Returns detailed statistics

        Args:
            source_resource: Source App Service resource containing:
                - id: Azure resource ID
                - type: Microsoft.Web/sites
                - name: App Service name
            target_resource: Target App Service resource with same structure

        Returns:
            ReplicationResult with:
                - success: True if at least one item replicated
                - items_discovered: Count of items found in source
                - items_replicated: Count of items successfully replicated
                - errors: List of error messages
                - warnings: List of warnings

        Raises:
            ValueError: If source or target resources are invalid

        Example:
            >>> source = {"id": "...", "type": "Microsoft.Web/sites", ...}
            >>> target = {"id": "...", "type": "Microsoft.Web/sites", ...}
            >>> result = plugin.replicate(source, target)
            >>> result.success
            True
            >>> result.items_replicated
            12
        """
        if not self.validate_resource(source_resource):
            raise ValueError(f"Invalid source resource: {source_resource}")

        if not self.validate_resource(target_resource):
            raise ValueError(f"Invalid target resource: {target_resource}")

        source_name = source_resource.get("name", "unknown")
        target_name = target_resource.get("name", "unknown")

        self.logger.info(
            f"Replicating from App Service '{source_name}' to '{target_name}'"
        )

        # 1. Discover items from source
        try:
            source_items = self.discover(source_resource)
        except Exception as e:
            self.logger.error(f"Failed to discover items from source: {e}")
            return ReplicationResult(
                success=False,
                items_discovered=0,
                items_replicated=0,
                errors=[f"Failed to discover items from source: {e}"],
                warnings=[],
            )

        if not source_items:
            self.logger.info("No items to replicate")
            return ReplicationResult(
                success=True,
                items_discovered=0,
                items_replicated=0,
                errors=[],
                warnings=["No items found in source App Service"],
            )

        self.logger.info(f"Discovered {len(source_items)} items from source")

        # 2. Connect to target App Service
        try:
            from azure.core.exceptions import HttpResponseError
            from azure.identity import DefaultAzureCredential
            from azure.mgmt.web import WebSiteManagementClient
            from azure.mgmt.web.models import (
                ConnectionStringDictionary,
                ConnStringValueTypePair,
                StringDictionary,
            )
        except ImportError as e:
            self.logger.error(f"Azure SDK not installed: {e}")
            return ReplicationResult(
                success=False,
                items_discovered=len(source_items),
                items_replicated=0,
                errors=[
                    f"Azure SDK not installed: {e}. Install with: pip install azure-mgmt-web"
                ],
                warnings=[],
            )

        # Parse resource IDs
        source_id = source_resource.get("id", "")
        target_id = target_resource.get("id", "")

        source_parts = source_id.split("/")
        target_parts = target_id.split("/")

        if len(source_parts) < 9 or len(target_parts) < 9:
            return ReplicationResult(
                success=False,
                items_discovered=len(source_items),
                items_replicated=0,
                errors=["Invalid resource ID format for source or target"],
                warnings=[],
            )

        target_subscription_id = target_parts[2]
        target_resource_group = target_parts[4]

        # Authenticate
        try:
            credential = DefaultAzureCredential()
            target_web_client = WebSiteManagementClient(
                credential, target_subscription_id
            )
        except Exception as e:
            self.logger.error(f"Failed to authenticate: {e}")
            return ReplicationResult(
                success=False,
                items_discovered=len(source_items),
                items_replicated=0,
                errors=[f"Failed to authenticate with Azure: {e}"],
                warnings=[],
            )

        # 3. Replicate each item
        replicated_count = 0
        errors = []
        warnings = []

        # Group items by type for batch operations
        app_settings = [
            item for item in source_items if item.item_type == "app_setting"
        ]
        connection_strings = [
            item for item in source_items if item.item_type == "connection_string"
        ]

        # Replicate app settings (batch operation)
        if app_settings:
            try:
                # Build app settings dictionary
                settings_dict = {}
                for item in app_settings:
                    settings_dict[item.name] = item.properties.get("value", "")

                # Create StringDictionary
                app_settings_update = StringDictionary(properties=settings_dict)

                # Update target app settings
                # Note: Type ignore needed due to SDK type definitions being incomplete
                target_web_client.web_apps.update_application_settings(  # type: ignore
                    resource_group_name=target_resource_group,
                    name=target_name,
                    app_settings=app_settings_update,
                )

                replicated_count += len(app_settings)
                self.logger.info(
                    f"Successfully replicated {len(app_settings)} app settings"
                )

            except HttpResponseError as e:
                if e.status_code == 403:
                    error_msg = f"Permission denied to update app settings: {e.message}"
                    errors.append(error_msg)
                    self.logger.warning(error_msg)
                else:
                    error_msg = f"HTTP error updating app settings: {e.message}"
                    errors.append(error_msg)
                    self.logger.warning(error_msg)
            except Exception as e:
                error_msg = f"Error replicating app settings: {e!s}"
                errors.append(error_msg)
                self.logger.error(error_msg)

        # Replicate connection strings (batch operation)
        if connection_strings:
            try:
                # Build connection strings dictionary
                conn_strings_dict = {}
                for item in connection_strings:
                    conn_type = item.properties.get("type", "Custom")
                    conn_value = item.properties.get("value", "")

                    conn_strings_dict[item.name] = ConnStringValueTypePair(
                        value=conn_value, type=conn_type
                    )

                # Create ConnectionStringDictionary
                conn_strings_update = ConnectionStringDictionary(
                    properties=conn_strings_dict
                )

                # Update target connection strings
                # Note: Type ignore needed due to SDK type definitions being incomplete
                target_web_client.web_apps.update_connection_strings(  # type: ignore
                    resource_group_name=target_resource_group,
                    name=target_name,
                    connection_strings=conn_strings_update,
                )

                replicated_count += len(connection_strings)
                self.logger.info(
                    f"Successfully replicated {len(connection_strings)} connection strings"
                )

                # Add security warning
                warnings.append(
                    "Connection strings contain sensitive data. "
                    "Verify that target environment security is properly configured."
                )

            except HttpResponseError as e:
                if e.status_code == 403:
                    error_msg = (
                        f"Permission denied to update connection strings: {e.message}"
                    )
                    errors.append(error_msg)
                    self.logger.warning(error_msg)
                else:
                    error_msg = f"HTTP error updating connection strings: {e.message}"
                    errors.append(error_msg)
                    self.logger.warning(error_msg)
            except Exception as e:
                error_msg = f"Error replicating connection strings: {e!s}"
                errors.append(error_msg)
                self.logger.error(error_msg)

        # Note: Deployment slots are not replicated automatically (they're infrastructure)
        # Note: Site configuration is partially covered by app_settings

        # Determine success
        success = replicated_count > 0

        self.logger.info(
            f"Replication complete: {replicated_count}/{len(source_items)} items replicated"
        )

        if errors:
            self.logger.warning(f"Encountered {len(errors)} errors during replication")
        if warnings:
            self.logger.debug(f"Generated {len(warnings)} warnings during replication")

        return ReplicationResult(
            success=success,
            items_discovered=len(source_items),
            items_replicated=replicated_count,
            errors=errors,
            warnings=warnings,
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
        sanitized = (
            name.replace("-", "_")
            .replace(".", "_")
            .replace(" ", "_")
            .replace(":", "_")
            .replace("/", "_")
        )

        # Ensure it starts with a letter
        if sanitized and not sanitized[0].isalpha():
            sanitized = "app_" + sanitized

        return sanitized.lower()

    def _is_sensitive_key(self, key: str) -> bool:
        """
        Determine if a setting key likely contains sensitive data.

        Args:
            key: Setting key name

        Returns:
            True if key suggests sensitive data
        """
        sensitive_keywords = [
            "password",
            "secret",
            "key",
            "token",
            "credential",
            "connectionstring",
            "apikey",
            "api_key",
        ]

        key_lower = key.lower()
        return any(keyword in key_lower for keyword in sensitive_keywords)

    def _escape_terraform_string(self, value: str) -> str:
        """
        Escape special characters for Terraform string literals.

        Args:
            value: String value to escape

        Returns:
            Escaped string safe for Terraform
        """
        # Escape backslashes and quotes
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')

        # Handle newlines and other special chars
        escaped = escaped.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")

        return escaped
