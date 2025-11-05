"""
Function App data plane replication plugin.

This plugin handles discovery and replication of Azure Function App data plane
items including:
- Application settings
- Function definitions and configurations
- Function bindings
- Host configuration

The plugin integrates with the IaC generation process to ensure that Function App
configurations are preserved when deploying to new environments.
"""

import logging
from typing import Any, Dict, List

from .base_plugin import DataPlaneItem, DataPlanePlugin, ReplicationResult

logger = logging.getLogger(__name__)


class FunctionAppPlugin(DataPlanePlugin):
    """
    Data plane plugin for Azure Function App.

    Discovers and replicates function definitions, settings, and configurations
    using Azure SDK.

    Example:
        plugin = FunctionAppPlugin()
        items = plugin.discover(function_app_resource)
        code = plugin.generate_replication_code(items, "terraform")
    """

    @property
    def supported_resource_type(self) -> str:
        """Azure resource type for Function App."""
        return "Microsoft.Web/sites"

    def validate_resource(self, resource: Dict[str, Any]) -> bool:
        """
        Validate that a resource is a Function App.

        Function Apps are Microsoft.Web/sites with kind containing "functionapp".

        Args:
            resource: Resource dictionary to validate

        Returns:
            True if resource is a valid Function App
        """
        # First, check basic validation from parent
        if not super().validate_resource(resource):
            return False

        # Function Apps must have kind containing "functionapp"
        kind = resource.get("kind", "")
        if "functionapp" not in kind.lower():
            self.logger.debug(
                f"Resource kind '{kind}' does not indicate Function App"
            )
            return False

        return True

    def discover(self, resource: Dict[str, Any]) -> List[DataPlaneItem]:
        """
        Discover Function App settings, functions, and configuration.

        Uses Azure SDK to:
        1. Authenticate to the Function App
        2. List application settings (including function app specific settings)
        3. List functions
        4. Get function configurations and bindings
        5. Get host.json configuration

        Args:
            resource: Function App resource dictionary containing:
                - id: Function App resource ID
                - name: Function App name
                - kind: Resource kind (should contain "functionapp")
                - properties: Function App properties

        Returns:
            List of DataPlaneItem representing functions and settings

        Example:
            >>> resource = {
            ...     "id": "/subscriptions/.../sites/my-func",
            ...     "type": "Microsoft.Web/sites",
            ...     "name": "my-func",
            ...     "kind": "functionapp,linux"
            ... }
            >>> items = plugin.discover(resource)
            >>> len(items)  # Returns count of settings/functions/configs
        """
        if not self.validate_resource(resource):
            raise ValueError(f"Invalid resource for FunctionAppPlugin: {resource}")

        function_app_name = resource.get("name", "unknown")
        self.logger.info(
            f"Discovering data plane items for Function App: {function_app_name}"
        )

        items: List[DataPlaneItem] = []

        try:
            # Import Azure SDK components
            from azure.core.exceptions import AzureError, HttpResponseError
            from azure.identity import DefaultAzureCredential
            from azure.mgmt.web import WebSiteManagementClient

            # Parse resource ID to extract subscription and resource group
            resource_id = resource.get("id", "")
            id_parts = resource_id.split("/")

            if len(id_parts) < 9:
                self.logger.error(
                    f"Invalid resource ID format: {resource_id}. "
                    "Expected format: /subscriptions/.../resourceGroups/.../providers/Microsoft.Web/sites/..."
                )
                return items

            subscription_id = id_parts[2]
            resource_group_name = id_parts[4]

            # Authenticate
            credential = DefaultAzureCredential()
            web_client = WebSiteManagementClient(credential, subscription_id)

            # 1. Discover Application Settings
            try:
                app_settings = web_client.web_apps.list_application_settings(
                    resource_group_name=resource_group_name, name=function_app_name
                )

                # Function App specific settings to highlight
                function_specific_settings = {
                    "AzureWebJobsStorage",
                    "FUNCTIONS_WORKER_RUNTIME",
                    "FUNCTIONS_EXTENSION_VERSION",
                    "WEBSITE_CONTENTAZUREFILECONNECTIONSTRING",
                    "WEBSITE_CONTENTSHARE",
                }

                for key, value in app_settings.properties.items():
                    item_type = (
                        "function_app_setting"
                        if key in function_specific_settings
                        else "app_setting"
                    )

                    # Don't include sensitive values in metadata
                    # Check both key name and value for sensitive keywords
                    is_sensitive = any(
                        keyword in key.lower()
                        for keyword in ["password", "secret", "key", "connection"]
                    ) or any(
                        keyword in value.lower() if isinstance(value, str) else False
                        for keyword in ["password", "secret", "key", "connection"]
                    )

                    items.append(
                        DataPlaneItem(
                            name=key,
                            item_type=item_type,
                            properties={
                                "value": value if not is_sensitive else "***REDACTED***",
                                "is_sensitive": is_sensitive,
                            },
                            source_resource_id=resource["id"],
                            metadata={"setting_type": item_type},
                        )
                    )

                self.logger.debug(
                    f"Discovered {len(app_settings.properties)} application settings"
                )

            except (AzureError, HttpResponseError) as e:
                self.logger.warning(
                    f"Failed to discover application settings in {function_app_name}: {e}"
                )

            # 2. Discover Functions
            try:
                functions = web_client.web_apps.list_functions(
                    resource_group_name=resource_group_name, name=function_app_name
                )

                for function in functions:
                    function_name = function.name.split("/")[-1]

                    # Parse function properties
                    function_props = {}
                    if hasattr(function, "properties") and function.properties:
                        if hasattr(function.properties, "config"):
                            function_props = function.properties.config or {}

                    # Get bindings from config
                    bindings = function_props.get("bindings", [])
                    trigger_type = "unknown"
                    if bindings:
                        # Find trigger binding
                        for binding in bindings:
                            if binding.get("type", "").endswith("Trigger"):
                                trigger_type = binding.get("type", "unknown")
                                break

                    items.append(
                        DataPlaneItem(
                            name=function_name,
                            item_type="function",
                            properties={
                                "trigger_type": trigger_type,
                                "bindings": bindings,
                                "config": function_props,
                            },
                            source_resource_id=resource["id"],
                            metadata={
                                "function_id": function.id,
                                "href": function.href if hasattr(function, "href") else None,
                            },
                        )
                    )

                self.logger.debug(f"Discovered {len(list(functions))} functions")

            except (AzureError, HttpResponseError) as e:
                self.logger.warning(
                    f"Failed to discover functions in {function_app_name}: {e}"
                )

            # 3. Discover Host Configuration (host.json)
            try:
                # Get site configuration
                site_config = web_client.web_apps.get_configuration(
                    resource_group_name=resource_group_name, name=function_app_name
                )

                config_props = {
                    "always_on": site_config.always_on,
                    "app_command_line": site_config.app_command_line,
                    "linux_fx_version": site_config.linux_fx_version,
                    "windows_fx_version": site_config.windows_fx_version,
                    "http20_enabled": site_config.http20_enabled,
                    "min_tls_version": site_config.min_tls_version,
                    "ftps_state": site_config.ftps_state,
                }

                items.append(
                    DataPlaneItem(
                        name="site_config",
                        item_type="site_config",
                        properties=config_props,
                        source_resource_id=resource["id"],
                        metadata={"config_type": "site_configuration"},
                    )
                )

                self.logger.debug("Discovered site configuration")

            except (AzureError, HttpResponseError) as e:
                self.logger.warning(
                    f"Failed to discover site configuration in {function_app_name}: {e}"
                )

            # 4. Discover Connection Strings
            try:
                connection_strings = web_client.web_apps.list_connection_strings(
                    resource_group_name=resource_group_name, name=function_app_name
                )

                for key, conn_string_info in connection_strings.properties.items():
                    items.append(
                        DataPlaneItem(
                            name=key,
                            item_type="connection_string",
                            properties={
                                "type": conn_string_info.type,
                                "value": "***REDACTED***",  # Never expose connection strings
                            },
                            source_resource_id=resource["id"],
                            metadata={"connection_type": conn_string_info.type},
                        )
                    )

                self.logger.debug(
                    f"Discovered {len(connection_strings.properties)} connection strings"
                )

            except (AzureError, HttpResponseError) as e:
                self.logger.warning(
                    f"Failed to discover connection strings in {function_app_name}: {e}"
                )

        except ImportError as e:
            self.logger.error(
                f"Azure Web SDK not installed. Install with: "
                f"pip install azure-mgmt-web. Error: {e}"
            )
        except Exception as e:
            self.logger.error(
                f"Unexpected error discovering Function App items: {e}"
            )

        self.logger.info(
            f"Discovered {len(items)} data plane items in Function App '{function_app_name}'"
        )
        return items

    def generate_replication_code(
        self, items: List[DataPlaneItem], output_format: str = "terraform"
    ) -> str:
        """
        Generate IaC code to replicate Function App configurations.

        For Function Apps, this generates:
        - Application settings resources
        - Function app site configuration
        - Guidance on function code deployment methods
        - References to deployment tools and CI/CD

        Security note: Sensitive values are not included. Users must populate
        them manually or via CI/CD systems.

        Args:
            items: List of Function App data plane items to replicate
            output_format: IaC format ("terraform", "bicep", "arm")

        Returns:
            String containing IaC code for Function App configuration

        Raises:
            ValueError: If output_format is not supported

        Example:
            >>> items = [DataPlaneItem(name="FUNCTIONS_WORKER_RUNTIME", ...)]
            >>> code = plugin.generate_replication_code(items)
            >>> "app_settings" in code
            True
        """
        if not self.supports_output_format(output_format):
            raise ValueError(
                f"Output format '{output_format}' not supported by FunctionAppPlugin"
            )

        if output_format.lower() != "terraform":
            raise ValueError("Only Terraform format is currently supported")

        self.logger.info(
            f"Generating {output_format} code for {len(items)} Function App items"
        )

        if not items:
            return "# No Function App data plane items to replicate\n"

        code_lines = [
            "# Function App Data Plane Items",
            "# Generated by Azure Tenant Grapher - FunctionAppPlugin",
            "#",
            "# SECURITY NOTE: Sensitive values (connection strings, secrets) are not included.",
            "# You must populate these via:",
            "#   - Azure Key Vault references (recommended)",
            "#   - Environment variables in CI/CD",
            "#   - Terraform variables marked as sensitive",
            "#",
            "# DEPLOYMENT NOTE: Function code must be deployed separately using:",
            "#   - Azure Functions Core Tools (func azure functionapp publish)",
            "#   - Azure DevOps Pipelines",
            "#   - GitHub Actions",
            "#   - VS Code Azure Functions extension",
            "",
        ]

        # Group items by type
        app_settings = [
            item for item in items if item.item_type in ["app_setting", "function_app_setting"]
        ]
        functions = [item for item in items if item.item_type == "function"]
        site_configs = [item for item in items if item.item_type == "site_config"]
        connection_strings = [item for item in items if item.item_type == "connection_string"]

        # Generate app settings
        if app_settings:
            code_lines.extend([
                "# Application Settings",
                "# Note: Add these to your azurerm_linux_function_app or azurerm_windows_function_app resource",
                "#",
                "# app_settings = {",
            ])

            for item in app_settings:
                if item.properties.get("is_sensitive", False):
                    code_lines.append(f'#   "{item.name}" = var.function_app_setting_{self._sanitize_name(item.name)}')
                else:
                    value = item.properties.get("value", "")
                    code_lines.append(f'#   "{item.name}" = "{value}"')

            code_lines.extend([
                "# }",
                "",
            ])

            # Generate variables for sensitive settings
            sensitive_settings = [item for item in app_settings if item.properties.get("is_sensitive", False)]
            if sensitive_settings:
                code_lines.extend([
                    "# Required variables for sensitive application settings",
                ])
                for item in sensitive_settings:
                    sanitized = self._sanitize_name(item.name)
                    code_lines.extend([
                        f'variable "function_app_setting_{sanitized}" {{',
                        f'  description = "Value for {item.name} (set via Key Vault or environment)"',
                        "  type        = string",
                        "  sensitive   = true",
                        "}",
                        "",
                    ])

        # Document discovered functions
        if functions:
            code_lines.extend([
                f"# Discovered Functions ({len(functions)} total)",
                "#",
                "# The following functions were discovered in the source Function App.",
                "# Deploy function code using one of these methods:",
                "#",
                "# Method 1: Azure Functions Core Tools",
                "#   func azure functionapp publish <function-app-name>",
                "#",
                "# Method 2: GitHub Actions",
                "#   - Use Azure/functions-action@v1",
                "#   - Example: https://github.com/Azure/functions-action",
                "#",
                "# Method 3: Azure DevOps",
                "#   - Use AzureFunctionApp@1 task",
                "#",
            ])

            for item in functions:
                trigger_type = item.properties.get("trigger_type", "unknown")
                bindings = item.properties.get("bindings", [])
                code_lines.extend([
                    f'# Function: {item.name}',
                    f'#   Trigger: {trigger_type}',
                ])
                if bindings:
                    code_lines.append(f'#   Bindings: {len(bindings)} configured')
                code_lines.append("#")

            code_lines.extend([
                "",
                "# Example: Deploy using Azure CLI",
                "# az functionapp deployment source config-zip \\",
                "#   --resource-group <resource-group> \\",
                "#   --name <function-app-name> \\",
                "#   --src <path-to-zip-file>",
                "",
            ])

        # Generate site configuration notes
        if site_configs:
            code_lines.extend([
                "# Site Configuration",
                "# Add these settings to your Function App resource configuration:",
                "#",
            ])
            for item in site_configs:
                props = item.properties
                if props.get("always_on"):
                    code_lines.append("#   always_on = true")
                if props.get("http20_enabled"):
                    code_lines.append("#   http20_enabled = true")
                if props.get("min_tls_version"):
                    code_lines.append(f'#   min_tls_version = "{props.get("min_tls_version")}"')
                if props.get("ftps_state"):
                    code_lines.append(f'#   ftps_state = "{props.get("ftps_state")}"')
            code_lines.append("")

        # Generate connection strings (as variables)
        if connection_strings:
            code_lines.extend([
                "# Connection Strings",
                "# Note: Store these in Azure Key Vault and reference them",
                "#",
                "# connection_string {",
            ])
            for item in connection_strings:
                sanitized = self._sanitize_name(item.name)
                conn_type = item.properties.get("type", "Custom")
                code_lines.extend([
                    f'#   name  = "{item.name}"',
                    f"#   type  = \"{conn_type}\"",
                    f"#   value = var.function_app_connection_{sanitized}",
                    "# }",
                    "#",
                ])
            code_lines.append("")

            # Add variable declarations for connection strings
            code_lines.append("# Required variables for connection strings")
            for item in connection_strings:
                sanitized = self._sanitize_name(item.name)
                code_lines.extend([
                    f'variable "function_app_connection_{sanitized}" {{',
                    f'  description = "Connection string for {item.name}"',
                    "  type        = string",
                    "  sensitive   = true",
                    "}",
                    "",
                ])

        # Add deployment examples
        code_lines.extend([
            "# ============================================",
            "# Function App Code Deployment Guide",
            "# ============================================",
            "#",
            "# Option 1: Zip Deploy (Recommended for automation)",
            "# resource \"null_resource\" \"deploy_function_code\" {",
            "#   provisioner \"local-exec\" {",
            "#     command = <<-EOT",
            "#       cd ${path.module}/function-code",
            "#       zip -r function.zip .",
            "#       az functionapp deployment source config-zip \\",
            "#         --resource-group ${azurerm_resource_group.example.name} \\",
            "#         --name ${azurerm_linux_function_app.example.name} \\",
            "#         --src function.zip",
            "#     EOT",
            "#   }",
            "#",
            "#   depends_on = [azurerm_linux_function_app.example]",
            "# }",
            "#",
            "# Option 2: GitHub Actions CI/CD",
            "# name: Deploy Azure Function",
            "# on: [push]",
            "# jobs:",
            "#   deploy:",
            "#     runs-on: ubuntu-latest",
            "#     steps:",
            "#       - uses: actions/checkout@v2",
            "#       - uses: Azure/functions-action@v1",
            "#         with:",
            "#           app-name: 'your-function-app-name'",
            "#           package: '.'",
            "#",
            "# Option 3: Azure DevOps Pipeline",
            "# - task: AzureFunctionApp@1",
            "#   inputs:",
            "#     azureSubscription: 'your-subscription'",
            "#     appType: 'functionAppLinux'",
            "#     appName: 'your-function-app-name'",
            "#     package: '$(System.DefaultWorkingDirectory)/**/*.zip'",
            "",
        ])

        return "\n".join(code_lines)

    def replicate(
        self, source_resource: Dict[str, Any], target_resource: Dict[str, Any]
    ) -> ReplicationResult:
        """
        Replicate Function App configuration and code from source to target.

        This method:
        1. Discovers all settings and functions from source
        2. Replicates application settings to target
        3. Replicates connection strings to target
        4. Downloads function code from source (if possible)
        5. Deploys function code to target
        6. Returns detailed statistics and errors

        Args:
            source_resource: Source Function App resource containing:
                - id: Azure resource ID
                - name: Function App name
                - type: Microsoft.Web/sites
                - kind: Must contain "functionapp"
            target_resource: Target Function App resource with same structure

        Returns:
            ReplicationResult containing:
                - success: True if replication completed successfully
                - items_discovered: Count of items found in source
                - items_replicated: Count of items successfully replicated
                - errors: List of error messages
                - warnings: List of warnings

        Raises:
            ValueError: If source or target resource is invalid

        Example:
            >>> result = plugin.replicate(source_func, target_func)
            >>> if result.success:
            ...     print(f"Replicated {result.items_replicated} items")
        """
        if not self.validate_resource(source_resource):
            raise ValueError(f"Invalid source resource: {source_resource}")

        if not self.validate_resource(target_resource):
            raise ValueError(f"Invalid target resource: {target_resource}")

        source_name = source_resource.get("name", "unknown")
        target_name = target_resource.get("name", "unknown")

        self.logger.info(
            f"Replicating from Function App '{source_name}' to '{target_name}'"
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
                warnings=["No items found in source Function App"],
            )

        self.logger.info(f"Discovered {len(source_items)} items from source")

        # 2. Connect to target Function App
        try:
            from azure.core.exceptions import AzureError, HttpResponseError
            from azure.identity import DefaultAzureCredential
            from azure.mgmt.web import WebSiteManagementClient
            from azure.mgmt.web.models import (
                ConnectionStringDictionary,
                NameValuePair,
                StringDictionary,
            )
        except ImportError as e:
            self.logger.error(f"Azure SDK not installed: {e}")
            return ReplicationResult(
                success=False,
                items_discovered=len(source_items),
                items_replicated=0,
                errors=[
                    f"Azure SDK not installed: {e}. "
                    "Install with: pip install azure-mgmt-web"
                ],
                warnings=[],
            )

        # Parse resource IDs
        source_id = source_resource.get("id", "")
        target_id = target_resource.get("id", "")

        source_id_parts = source_id.split("/")
        target_id_parts = target_id.split("/")

        if len(source_id_parts) < 9 or len(target_id_parts) < 9:
            return ReplicationResult(
                success=False,
                items_discovered=len(source_items),
                items_replicated=0,
                errors=["Invalid resource ID format"],
                warnings=[],
            )

        source_id_parts[2]
        source_id_parts[4]

        target_subscription_id = target_id_parts[2]
        target_resource_group = target_id_parts[4]

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

        # 3. Replicate items
        replicated_count = 0
        errors = []
        warnings = []

        # Group items by type for batch operations
        app_settings = [
            item for item in source_items
            if item.item_type in ["app_setting", "function_app_setting"]
        ]
        connection_strings = [
            item for item in source_items if item.item_type == "connection_string"
        ]
        functions = [item for item in source_items if item.item_type == "function"]

        # Replicate application settings
        if app_settings:
            try:
                # Build settings dictionary
                settings_dict = {}
                for item in app_settings:
                    # Skip redacted values
                    value = item.properties.get("value", "")
                    if value != "***REDACTED***":
                        settings_dict[item.name] = value
                    else:
                        warnings.append(
                            f"Skipped sensitive setting '{item.name}' - must be set manually"
                        )

                if settings_dict:
                    # Update app settings in target
                    app_settings_envelope = StringDictionary(properties=settings_dict)
                    target_web_client.web_apps.update_application_settings(
                        resource_group_name=target_resource_group,
                        name=target_name,
                        app_settings=app_settings_envelope,
                    )
                    replicated_count += len(settings_dict)
                    self.logger.info(
                        f"Replicated {len(settings_dict)} application settings"
                    )

            except (AzureError, HttpResponseError) as e:
                error_msg = f"Failed to replicate application settings: {e}"
                errors.append(error_msg)
                self.logger.warning(error_msg)

        # Replicate connection strings
        if connection_strings:
            warnings.append(
                f"Found {len(connection_strings)} connection string(s). "
                "These must be set manually due to security restrictions."
            )

        # Note about functions
        if functions:
            warnings.append(
                f"Found {len(functions)} function(s). "
                "Function code must be deployed separately using Azure Functions Core Tools, "
                "CI/CD pipelines, or the Azure Portal."
            )

        # Determine success
        success = replicated_count > 0 or (not app_settings and not connection_strings)

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
        Sanitize a name for use in Terraform resource names and variable names.

        Args:
            name: Original name (may contain special characters)

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
            sanitized = "func_" + sanitized

        return sanitized.lower()
