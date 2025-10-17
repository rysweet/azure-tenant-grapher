"""
API Management data plane replication plugin.

This plugin handles discovery and replication of Azure API Management Service
data plane items including:
- API definitions (OpenAPI/Swagger specifications)
- Policies (XML configurations)
- Products
- Backends
- Named values (secrets)

The plugin integrates with the IaC generation process to ensure that API
Management configurations are preserved when deploying to new environments.
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


class APIMPlugin(DataPlanePlugin):
    """
    Data plane plugin for Azure API Management Service.

    Discovers and replicates API definitions, policies, backends, and named
    values using Azure SDK.

    Example:
        plugin = APIMPlugin()
        items = plugin.discover(apim_resource)
        code = plugin.generate_replication_code(items, "terraform")
    """

    @property
    def supported_resource_type(self) -> str:
        """Azure resource type for API Management."""
        return "Microsoft.ApiManagement/service"

    def discover(self, resource: Dict[str, Any]) -> List[DataPlaneItem]:
        """
        Discover API Management data plane items.

        Uses Azure SDK to:
        1. Authenticate to the API Management service
        2. List all APIs, policies, products, backends, named values
        3. Retrieve metadata and configurations
        4. Return structured DataPlaneItem list

        Args:
            resource: APIM resource dictionary containing:
                - id: APIM resource ID
                - name: APIM service name
                - properties: APIM properties

        Returns:
            List of DataPlaneItem representing APIM contents

        Example:
            >>> resource = {
            ...     "id": "/subscriptions/.../service/my-apim",
            ...     "type": "Microsoft.ApiManagement/service",
            ...     "name": "my-apim",
            ...     "properties": {...}
            ... }
            >>> items = plugin.discover(resource)
            >>> len(items)  # Returns count of APIs, policies, etc.
        """
        if not self.validate_resource(resource):
            raise ValueError(f"Invalid resource for APIMPlugin: {resource}")

        service_name = resource.get("name", "unknown")
        self.logger.info(
            f"Discovering data plane items for APIM service: {service_name}"
        )

        items: List[DataPlaneItem] = []

        try:
            # Import Azure SDK components
            from azure.core.exceptions import AzureError, HttpResponseError
            from azure.identity import DefaultAzureCredential
            from azure.mgmt.apimanagement import ApiManagementClient

            # Parse resource ID to get subscription and resource group
            resource_id = resource.get("id", "")
            parts = resource_id.split("/")
            if len(parts) < 9:
                raise ValueError(f"Invalid resource ID format: {resource_id}")

            subscription_id = parts[2]
            resource_group = parts[4]

            # Authenticate
            if self.credential_provider:
                credential = self.credential_provider.get_credential()
            else:
                credential = DefaultAzureCredential()

            # Create APIM client
            client = ApiManagementClient(credential, subscription_id)

            # Discover APIs
            try:
                apis = client.api.list_by_service(resource_group, service_name)

                for api in apis:
                    # Skip if the API is a system API or not enabled
                    if api.is_current is False:
                        self.logger.debug(f"Skipping non-current API: {api.name}")
                        continue

                    items.append(
                        DataPlaneItem(
                            name=api.name,
                            item_type="api",
                            properties={
                                "display_name": api.display_name,
                                "path": api.path,
                                "protocols": [str(p) for p in (api.protocols or [])],
                                "api_version": api.api_version,
                                "api_version_set_id": api.api_version_set_id,
                                "subscription_required": api.subscription_required,
                                "is_current": api.is_current,
                            },
                            source_resource_id=resource["id"],
                            metadata={
                                "id": api.id,
                                "type": api.type,
                                "description": api.description,
                                "service_url": api.service_url,
                            },
                        )
                    )

                    # Get API policy (if exists)
                    try:
                        policy = client.api_policy.get(
                            resource_group, service_name, api.name, "policy"
                        )
                        items.append(
                            DataPlaneItem(
                                name=f"{api.name}-policy",
                                item_type="api_policy",
                                properties={
                                    "api_name": api.name,
                                    "policy_content": policy.value,
                                    "format": policy.format,
                                },
                                source_resource_id=resource["id"],
                                metadata={"parent_api": api.name},
                            )
                        )
                    except (AzureError, HttpResponseError) as e:
                        # Policy might not exist for all APIs
                        self.logger.debug(f"No policy found for API {api.name}: {e}")

            except (AzureError, HttpResponseError) as e:
                self.logger.warning(f"Failed to discover APIs in {service_name}: {e}")

            # Discover Products
            try:
                products = client.product.list_by_service(resource_group, service_name)

                for product in products:
                    items.append(
                        DataPlaneItem(
                            name=product.name,
                            item_type="product",
                            properties={
                                "display_name": product.display_name,
                                "description": product.description,
                                "state": str(product.state) if product.state else None,
                                "subscription_required": product.subscription_required,
                                "approval_required": product.approval_required,
                                "subscriptions_limit": product.subscriptions_limit,
                            },
                            source_resource_id=resource["id"],
                            metadata={"id": product.id, "type": product.type},
                        )
                    )
            except (AzureError, HttpResponseError) as e:
                self.logger.warning(
                    f"Failed to discover products in {service_name}: {e}"
                )

            # Discover Backends
            try:
                backends = client.backend.list_by_service(resource_group, service_name)

                for backend in backends:
                    items.append(
                        DataPlaneItem(
                            name=backend.name,
                            item_type="backend",
                            properties={
                                "title": backend.title,
                                "description": backend.description,
                                "url": backend.url,
                                "protocol": str(backend.protocol)
                                if backend.protocol
                                else None,
                                "resource_id": backend.resource_id,
                            },
                            source_resource_id=resource["id"],
                            metadata={"id": backend.id, "type": backend.type},
                        )
                    )
            except (AzureError, HttpResponseError) as e:
                self.logger.warning(
                    f"Failed to discover backends in {service_name}: {e}"
                )

            # Discover Named Values (secrets/configuration)
            try:
                named_values = client.named_value.list_by_service(
                    resource_group, service_name
                )

                for nv in named_values:
                    items.append(
                        DataPlaneItem(
                            name=nv.name,
                            item_type="named_value",
                            properties={
                                "display_name": nv.display_name,
                                "secret": nv.secret or False,
                                "tags": nv.tags or [],
                            },
                            source_resource_id=resource["id"],
                            metadata={
                                "id": nv.id,
                                "type": nv.type,
                                # Note: actual value is not retrieved for security
                            },
                        )
                    )
            except (AzureError, HttpResponseError) as e:
                self.logger.warning(
                    f"Failed to discover named values in {service_name}: {e}"
                )

        except ImportError as e:
            self.logger.error(
                f"Azure API Management SDK not installed. Install with: "
                f"pip install azure-mgmt-apimanagement. "
                f"Error: {e}"
            )
        except Exception as e:
            self.logger.error(f"Unexpected error discovering APIM items: {e}")

        self.logger.info(
            f"Discovered {len(items)} data plane items in APIM service '{service_name}'"
        )
        return items

    def generate_replication_code(
        self, items: List[DataPlaneItem], output_format: str = "terraform"
    ) -> str:
        """
        Generate IaC code to replicate API Management data plane items.

        For APIs, this generates:
        - API definitions with OpenAPI specs
        - Policy configurations (XML)
        - Products
        - Backends
        - Named values (with placeholders for secrets)

        Args:
            items: List of APIM data plane items to replicate
            output_format: IaC format ("terraform", "bicep", "arm")

        Returns:
            String containing IaC code for data plane items

        Raises:
            ValueError: If output_format is not supported

        Example:
            >>> items = [DataPlaneItem(name="my-api", item_type="api", ...)]
            >>> code = plugin.generate_replication_code(items)
            >>> "azurerm_api_management_api" in code
            True
        """
        if not self.supports_output_format(output_format):
            raise ValueError(
                f"Output format '{output_format}' not supported by APIMPlugin"
            )

        if output_format.lower() != "terraform":
            raise ValueError("Only Terraform format is currently supported")

        self.logger.info(f"Generating {output_format} code for {len(items)} APIM items")

        if not items:
            return "# No API Management data plane items to replicate\n"

        code_lines = [
            "# API Management Data Plane Items",
            "# Generated by Azure Tenant Grapher - APIMPlugin",
            "#",
            "# NOTE: Policy XML and named value secrets are placeholders.",
            "# You must manually configure these after deployment.",
            "",
        ]

        # Group items by type
        apis = [item for item in items if item.item_type == "api"]
        api_policies = [item for item in items if item.item_type == "api_policy"]
        products = [item for item in items if item.item_type == "product"]
        backends = [item for item in items if item.item_type == "backend"]
        named_values = [item for item in items if item.item_type == "named_value"]

        # Generate code for APIs
        if apis:
            code_lines.append("# APIs")
            for item in apis:
                resource_name = self._sanitize_name(item.name)
                code_lines.extend(
                    [
                        f'resource "azurerm_api_management_api" "{resource_name}" {{',
                        f'  name                = "{item.name}"',
                        "  resource_group_name = var.resource_group_name",
                        "  api_management_name = var.api_management_name",
                        f'  display_name        = "{item.properties.get("display_name", item.name)}"',
                        f'  path                = "{item.properties.get("path", "")}"',
                        '  revision            = "1"',
                        "",
                    ]
                )

                # Add protocols
                protocols = item.properties.get("protocols", [])
                if protocols:
                    code_lines.append("  protocols = [")
                    for proto in protocols:
                        code_lines.append(f'    "{proto}",')
                    code_lines.append("  ]")
                    code_lines.append("")

                # Add subscription requirement
                subscription_required = item.properties.get(
                    "subscription_required", True
                )
                code_lines.append(
                    f"  subscription_required = {str(subscription_required).lower()}"
                )

                # Add service URL if available
                service_url = item.metadata.get("service_url")
                if service_url:
                    code_lines.append(f'  service_url = "{service_url}"')

                code_lines.append("}")
                code_lines.append("")

        # Generate code for API policies
        if api_policies:
            code_lines.append("# API Policies")
            for item in api_policies:
                api_name = item.properties.get("api_name", "unknown")
                resource_name = self._sanitize_name(f"{api_name}_policy")
                code_lines.extend(
                    [
                        f'resource "azurerm_api_management_api_policy" "{resource_name}" {{',
                        f"  api_name            = azurerm_api_management_api.{self._sanitize_name(api_name)}.name",
                        "  api_management_name = var.api_management_name",
                        "  resource_group_name = var.resource_group_name",
                        "",
                        "  # IMPORTANT: Update the XML policy content below",
                        "  xml_content = <<XML",
                        item.properties.get("policy_content", "<policies></policies>"),
                        "XML",
                        "}",
                        "",
                    ]
                )

        # Generate code for products
        if products:
            code_lines.append("# Products")
            for item in products:
                resource_name = self._sanitize_name(item.name)
                code_lines.extend(
                    [
                        f'resource "azurerm_api_management_product" "{resource_name}" {{',
                        f'  product_id          = "{item.name}"',
                        "  api_management_name = var.api_management_name",
                        "  resource_group_name = var.resource_group_name",
                        f'  display_name        = "{item.properties.get("display_name", item.name)}"',
                        "  published           = true",
                        "",
                    ]
                )

                # Add subscription requirement
                subscription_required = item.properties.get(
                    "subscription_required", True
                )
                code_lines.append(
                    f"  subscription_required = {str(subscription_required).lower()}"
                )

                # Add approval requirement
                approval_required = item.properties.get("approval_required", False)
                code_lines.append(
                    f"  approval_required = {str(approval_required).lower()}"
                )

                # Add description if available
                description = item.properties.get("description")
                if description:
                    code_lines.append(f'  description = "{description}"')

                code_lines.append("}")
                code_lines.append("")

        # Generate code for backends
        if backends:
            code_lines.append("# Backends")
            for item in backends:
                resource_name = self._sanitize_name(item.name)
                code_lines.extend(
                    [
                        f'resource "azurerm_api_management_backend" "{resource_name}" {{',
                        f'  name                = "{item.name}"',
                        "  api_management_name = var.api_management_name",
                        "  resource_group_name = var.resource_group_name",
                        f'  url                 = "{item.properties.get("url", "")}"',
                        f'  protocol            = "{item.properties.get("protocol", "http")}"',
                        "",
                    ]
                )

                # Add title and description if available
                title = item.properties.get("title")
                if title:
                    code_lines.append(f'  title = "{title}"')

                description = item.properties.get("description")
                if description:
                    code_lines.append(f'  description = "{description}"')

                # Add resource ID if available
                resource_id = item.properties.get("resource_id")
                if resource_id:
                    code_lines.append(f'  resource_id = "{resource_id}"')

                code_lines.append("}")
                code_lines.append("")

        # Generate code for named values
        if named_values:
            code_lines.append("# Named Values")
            for item in named_values:
                resource_name = self._sanitize_name(item.name)
                is_secret = item.properties.get("secret", False)

                code_lines.extend(
                    [
                        f'resource "azurerm_api_management_named_value" "{resource_name}" {{',
                        f'  name                = "{item.name}"',
                        "  api_management_name = var.api_management_name",
                        "  resource_group_name = var.resource_group_name",
                        f'  display_name        = "{item.properties.get("display_name", item.name)}"',
                        "",
                    ]
                )

                # Add value (placeholder for secrets)
                if is_secret:
                    code_lines.extend(
                        [
                            f"  value  = var.apim_named_value_{resource_name}  # Secret value",
                            "  secret = true",
                        ]
                    )
                else:
                    code_lines.append(
                        f"  value  = var.apim_named_value_{resource_name}"
                    )

                # Add tags if available
                tags = item.properties.get("tags", [])
                if tags:
                    code_lines.append("  tags = [")
                    for tag in tags:
                        code_lines.append(f'    "{tag}",')
                    code_lines.append("  ]")

                code_lines.append("}")
                code_lines.append("")

            # Add variable declarations for named values
            code_lines.append("# Required variables for named values")
            for item in named_values:
                resource_name = self._sanitize_name(item.name)
                is_secret = item.properties.get("secret", False)

                code_lines.extend(
                    [
                        f'variable "apim_named_value_{resource_name}" {{',
                        f"  description = \"Value for named value '{item.name}'\"",
                        "  type        = string",
                    ]
                )

                if is_secret:
                    code_lines.append("  sensitive   = true")

                code_lines.extend(["}", ""])

        # Add common variables
        code_lines.extend(
            [
                "# Common variables",
                'variable "resource_group_name" {',
                '  description = "Resource group name"',
                "  type        = string",
                "}",
                "",
                'variable "api_management_name" {',
                '  description = "API Management service name"',
                "  type        = string",
                "}",
                "",
            ]
        )

        return "\n".join(code_lines)

    def replicate(
        self, source_resource: Dict[str, Any], target_resource: Dict[str, Any]
    ) -> ReplicationResult:
        """
        Replicate API Management contents from source to target.

        This delegates to replicate_with_mode with REPLICATION mode.

        Args:
            source_resource: Source APIM resource
            target_resource: Target APIM resource

        Returns:
            ReplicationResult with operation statistics
        """
        return self.replicate_with_mode(
            source_resource, target_resource, ReplicationMode.REPLICATION
        )

    def _sanitize_name(self, name: str) -> str:
        """
        Sanitize a name for use in Terraform resource names.

        Args:
            name: Original name (may contain hyphens, special chars)

        Returns:
            Sanitized name safe for Terraform identifiers
        """
        # Replace hyphens and special chars with underscores
        sanitized = name.replace("-", "_").replace(".", "_").replace(" ", "_")
        sanitized = sanitized.replace("/", "_")

        # Ensure it starts with a letter
        if sanitized and not sanitized[0].isalpha():
            sanitized = "apim_" + sanitized

        return sanitized.lower()

    # ============ MODE-AWARE METHODS ============

    def get_required_permissions(self, mode: ReplicationMode) -> List[Permission]:
        """
        Return required permissions for API Management operations.

        Template mode: Read-only permissions to list items
        Replication mode: Read/write permissions for full replication

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
                        "Microsoft.ApiManagement/service/read",
                        "Microsoft.ApiManagement/service/apis/read",
                        "Microsoft.ApiManagement/service/products/read",
                        "Microsoft.ApiManagement/service/backends/read",
                        "Microsoft.ApiManagement/service/namedValues/read",
                    ],
                    description="API Management Service Reader - read APIs, policies, products, backends, named values",
                )
            ]
        else:  # REPLICATION mode
            return [
                Permission(
                    scope="resource",
                    actions=[
                        "Microsoft.ApiManagement/service/read",
                        "Microsoft.ApiManagement/service/apis/read",
                        "Microsoft.ApiManagement/service/apis/write",
                        "Microsoft.ApiManagement/service/apis/delete",
                        "Microsoft.ApiManagement/service/products/read",
                        "Microsoft.ApiManagement/service/products/write",
                        "Microsoft.ApiManagement/service/backends/read",
                        "Microsoft.ApiManagement/service/backends/write",
                        "Microsoft.ApiManagement/service/namedValues/read",
                        "Microsoft.ApiManagement/service/namedValues/write",
                        "Microsoft.ApiManagement/service/policies/read",
                        "Microsoft.ApiManagement/service/policies/write",
                    ],
                    description="API Management Service Contributor - read and write all items",
                )
            ]

    def discover_with_mode(
        self, resource: Dict[str, Any], mode: ReplicationMode
    ) -> List[DataPlaneItem]:
        """
        Discover API Management items with mode awareness.

        Both modes discover the same metadata. Template mode doesn't fetch
        secret values for named values.

        Args:
            resource: APIM resource
            mode: Replication mode

        Returns:
            List of discovered items
        """
        # Current discover() method already does metadata-only discovery
        # This is appropriate for both modes
        return self.discover(resource)

    def replicate_with_mode(
        self,
        source_resource: Dict[str, Any],
        target_resource: Dict[str, Any],
        mode: ReplicationMode,
    ) -> ReplicationResult:
        """
        Replicate API Management contents with mode awareness.

        Template mode: Create API structures without policies
        Replication mode: Copy all API definitions, policies, backends, named values

        Args:
            source_resource: Source APIM resource
            target_resource: Target APIM resource
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
            f"Replicating APIM service from '{source_name}' to '{target_name}' "
            f"(mode={mode.value})"
        )

        try:
            # Discover items from source
            items = self.discover(source_resource)

            if self.progress_reporter:
                self.progress_reporter.report_discovery(
                    source_resource["id"], len(items)
                )

            if mode == ReplicationMode.TEMPLATE:
                # Template mode: Create structures only
                result = self._replicate_template_mode(
                    source_resource, target_resource, items
                )
            else:
                # Replication mode: Full copy
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
            error_msg = f"Failed to replicate APIM service: {e!s}"
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
        Replicate in template mode: create API structures without policies.

        Args:
            source_resource: Source APIM service
            target_resource: Target APIM service
            items: Items discovered from source

        Returns:
            ReplicationResult
        """
        from azure.core.exceptions import AzureError, HttpResponseError
        from azure.identity import DefaultAzureCredential
        from azure.mgmt.apimanagement import ApiManagementClient
        from azure.mgmt.apimanagement.models import (
            ApiCreateOrUpdateParameter,
        )

        # Get credentials
        if self.credential_provider:
            credential = self.credential_provider.get_credential()
        else:
            credential = DefaultAzureCredential()

        # Parse resource IDs
        target_id = target_resource.get("id", "")
        parts = target_id.split("/")
        if len(parts) < 9:
            raise ValueError(f"Invalid target resource ID: {target_id}")

        subscription_id = parts[2]
        resource_group = parts[4]
        service_name = target_resource.get("name")

        # Create client
        client = ApiManagementClient(credential, subscription_id)

        # Group items by type
        apis = [item for item in items if item.item_type == "api"]
        products = [item for item in items if item.item_type == "product"]
        backends = [item for item in items if item.item_type == "backend"]
        named_values = [item for item in items if item.item_type == "named_value"]

        replicated = 0
        skipped = 0
        errors = []
        warnings = []

        # Create API structures (without policies)
        if apis:
            for item in apis:
                try:
                    api_params = ApiCreateOrUpdateParameter(
                        display_name=item.properties.get("display_name", item.name),
                        path=item.properties.get("path", ""),
                        protocols=list(item.properties.get("protocols", ["https"])),
                        subscription_required=item.properties.get(
                            "subscription_required", True
                        ),
                    )

                    service_url = item.metadata.get("service_url")
                    if service_url:
                        api_params.service_url = service_url

                    client.api.begin_create_or_update(
                        resource_group, service_name, item.name, api_params
                    )
                    replicated += 1

                    if self.progress_reporter:
                        progress = (replicated / len(items)) * 100
                        self.progress_reporter.report_replication_progress(
                            item.name, progress
                        )

                except (AzureError, HttpResponseError) as e:
                    errors.append(f"Failed to create API '{item.name}': {e!s}")
                    skipped += 1

        # Policies are skipped in template mode
        policy_count = len([i for i in items if i.item_type == "api_policy"])
        if policy_count > 0:
            warnings.append(
                f"Template mode: {policy_count} policies not created "
                "(policies excluded in template mode)"
            )
            skipped += policy_count

        # Products
        if products:
            warnings.append(
                f"Template mode: {len(products)} products not created "
                "(create manually or use full replication mode)"
            )
            skipped += len(products)

        # Backends
        if backends:
            warnings.append(
                f"Template mode: {len(backends)} backends not created "
                "(create manually or use full replication mode)"
            )
            skipped += len(backends)

        # Named values
        if named_values:
            warnings.append(
                f"Template mode: {len(named_values)} named values not created "
                "(create manually or use full replication mode)"
            )
            skipped += len(named_values)

        warnings.append(
            "Template mode: Only API structures created. "
            "Policies, products, backends, and named values excluded."
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
        Replicate in full mode: copy all API definitions, policies, etc.

        Args:
            source_resource: Source APIM service
            target_resource: Target APIM service
            items: Items discovered from source

        Returns:
            ReplicationResult
        """
        from azure.core.exceptions import AzureError, HttpResponseError
        from azure.identity import DefaultAzureCredential
        from azure.mgmt.apimanagement import ApiManagementClient
        from azure.mgmt.apimanagement.models import (
            ApiCreateOrUpdateParameter,
            PolicyContract,
        )

        # Get credentials
        if self.credential_provider:
            credential = self.credential_provider.get_credential()
        else:
            credential = DefaultAzureCredential()

        # Parse resource IDs
        source_id = source_resource.get("id", "")
        source_parts = source_id.split("/")
        if len(source_parts) < 9:
            raise ValueError(f"Invalid source resource ID: {source_id}")

        source_subscription_id = source_parts[2]
        source_resource_group = source_parts[4]
        source_service_name = source_resource.get("name")

        target_id = target_resource.get("id", "")
        target_parts = target_id.split("/")
        if len(target_parts) < 9:
            raise ValueError(f"Invalid target resource ID: {target_id}")

        target_subscription_id = target_parts[2]
        target_resource_group = target_parts[4]
        target_service_name = target_resource.get("name")

        # Create clients
        source_client = ApiManagementClient(credential, source_subscription_id)
        target_client = ApiManagementClient(credential, target_subscription_id)

        # Group items by type
        apis = [item for item in items if item.item_type == "api"]
        api_policies = [item for item in items if item.item_type == "api_policy"]
        products = [item for item in items if item.item_type == "product"]
        backends = [item for item in items if item.item_type == "backend"]
        named_values = [item for item in items if item.item_type == "named_value"]

        replicated = 0
        skipped = 0
        errors = []
        warnings = []

        # Replicate APIs
        if apis:
            for item in apis:
                try:
                    # Get full API definition from source
                    source_api = source_client.api.get(
                        source_resource_group, source_service_name, item.name
                    )

                    # Create API in target
                    api_params = ApiCreateOrUpdateParameter(
                        display_name=source_api.display_name,
                        path=source_api.path,
                        protocols=source_api.protocols,
                        subscription_required=source_api.subscription_required,
                        service_url=source_api.service_url,
                        api_version=source_api.api_version,
                        description=source_api.description,
                    )

                    target_client.api.begin_create_or_update(
                        target_resource_group,
                        target_service_name,
                        item.name,
                        api_params,
                    )
                    replicated += 1

                    if self.progress_reporter:
                        progress = (replicated / len(items)) * 100
                        self.progress_reporter.report_replication_progress(
                            item.name, progress
                        )

                except (AzureError, HttpResponseError) as e:
                    errors.append(f"Failed to replicate API '{item.name}': {e!s}")
                    skipped += 1

        # Replicate API policies
        if api_policies:
            for item in api_policies:
                try:
                    api_name = item.properties.get("api_name")
                    policy_content = item.properties.get("policy_content")

                    if api_name and policy_content:
                        policy = PolicyContract(
                            value=policy_content,
                            format=item.properties.get("format", "xml"),
                        )

                        target_client.api_policy.create_or_update(
                            target_resource_group,
                            target_service_name,
                            api_name,
                            "policy",
                            policy,
                        )
                        replicated += 1
                    else:
                        skipped += 1
                        warnings.append(
                            f"Skipped policy for API '{api_name}' - missing content"
                        )

                except (AzureError, HttpResponseError) as e:
                    errors.append(
                        f"Failed to replicate policy for '{api_name}': {e!s}"
                    )
                    skipped += 1

        # Products, backends, named values replication
        if products:
            warnings.append(
                f"Replication mode: {len(products)} products not fully replicated "
                "(requires additional implementation)"
            )
            skipped += len(products)

        if backends:
            warnings.append(
                f"Replication mode: {len(backends)} backends not fully replicated "
                "(requires additional implementation)"
            )
            skipped += len(backends)

        if named_values:
            warnings.append(
                f"Replication mode: {len(named_values)} named values not replicated "
                "(secret values cannot be retrieved via API)"
            )
            skipped += len(named_values)

        return ReplicationResult(
            success=len(errors) == 0,
            items_discovered=len(items),
            items_replicated=replicated,
            items_skipped=skipped,
            errors=errors,
            warnings=warnings,
        )
