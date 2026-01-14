"""Data Factory handler for Terraform emission.

Handles: Microsoft.DataFactory/factories
Emits: azurerm_data_factory
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from src.services.azure_name_sanitizer import AzureNameSanitizer
from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class DataFactoryHandler(ResourceHandler):
    """Handler for Azure Data Factory.

    Emits:
        - azurerm_data_factory
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "microsoft.datafactory/factories",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_data_factory",
    }

    def __init__(self):
        """Initialize handler with Azure name sanitizer."""
        super().__init__()
        self.sanitizer = AzureNameSanitizer()

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Data Factory to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        config = self.build_base_config(resource)

        # Data Factory names must be globally unique
        # Sanitize using centralized Azure naming rules
        abstracted_name = config["name"]
        sanitized_name = self.sanitizer.sanitize(
            abstracted_name, "Microsoft.DataFactory/factories"
        )

        # Add tenant-specific suffix for cross-tenant deployments
        if (
            context.target_tenant_id
            and context.source_tenant_id != context.target_tenant_id
        ):
            # Add target tenant suffix (last 6 chars of tenant ID, alphanumeric only)
            tenant_suffix = context.target_tenant_id[-6:].replace("-", "").lower()

            # Truncate to fit (63 - 7 = 56 chars for sanitized name + dash)
            if len(sanitized_name) > 56:
                sanitized_name = sanitized_name[:56]

            config["name"] = f"{sanitized_name}-{tenant_suffix}"
            logger.info(
                f"Cross-tenant deployment: Data Factory '{abstracted_name}' → '{config['name']}' (tenant suffix: {tenant_suffix})"
            )
        else:
            config["name"] = sanitized_name

        # Public network access
        if properties.get("publicNetworkAccess"):
            config["public_network_enabled"] = (
                properties.get("publicNetworkAccess", "Enabled") == "Enabled"
            )

        # Managed virtual network
        if properties.get("managedVirtualNetworkEnabled"):
            config["managed_virtual_network_enabled"] = True

        # Identity
        identity = resource.get("identity", {})
        if identity.get("type"):
            identity_type = identity.get("type", "").lower()
            if "systemassigned" in identity_type:
                config["identity"] = {"type": "SystemAssigned"}
            elif "userassigned" in identity_type:
                user_ids = list(identity.get("userAssignedIdentities", {}).keys())
                config["identity"] = {
                    "type": "UserAssigned",
                    "identity_ids": user_ids,
                }

        # Global parameters
        global_params = properties.get("globalParameters", {})
        if global_params:
            tf_params = []
            for name, param_config in global_params.items():
                tf_params.append(
                    {
                        "name": name,
                        "type": param_config.get("type", "String"),
                        "value": str(param_config.get("value", "")),
                    }
                )
            if tf_params:
                config["global_parameter"] = tf_params

        # Git configuration
        repo_config = properties.get("repoConfiguration", {})
        if repo_config:
            repo_type = repo_config.get("type", "")
            if "GitHub" in repo_type:
                config["github_configuration"] = {
                    "account_name": repo_config.get("accountName", ""),
                    "branch_name": repo_config.get("collaborationBranch", "main"),
                    "repository_name": repo_config.get("repositoryName", ""),
                    "root_folder": repo_config.get("rootFolder", "/"),
                    "git_url": repo_config.get("hostName", "https://github.com"),
                }
            elif "AzureDevOps" in repo_type or "FactoryVSTS" in repo_type:
                config["vsts_configuration"] = {
                    "account_name": repo_config.get("accountName", ""),
                    "branch_name": repo_config.get("collaborationBranch", "main"),
                    "project_name": repo_config.get("projectName", ""),
                    "repository_name": repo_config.get("repositoryName", ""),
                    "root_folder": repo_config.get("rootFolder", "/"),
                    "tenant_id": repo_config.get("tenantId", ""),
                }

        logger.debug(f"Data Factory '{resource_name}' emitted")

        return "azurerm_data_factory", safe_name, config
