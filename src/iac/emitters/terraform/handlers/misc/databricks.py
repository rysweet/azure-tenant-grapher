"""Databricks handler for Terraform emission.

Handles: Microsoft.Databricks/workspaces
Emits: azurerm_databricks_workspace
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class DatabricksWorkspaceHandler(ResourceHandler):
    """Handler for Azure Databricks Workspaces.

    Emits:
        - azurerm_databricks_workspace
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "microsoft.databricks/workspaces",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_databricks_workspace",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Databricks Workspace to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        config = self.build_base_config(resource)

        # SKU
        sku = resource.get("sku", {})
        config["sku"] = (
            sku.get("name", "standard") if isinstance(sku, dict) else "standard"
        )

        # Managed resource group
        managed_rg_id = properties.get("managedResourceGroupId", "")
        if managed_rg_id:
            # Extract just the name
            rg_name = (
                managed_rg_id.split("/")[-1] if "/" in managed_rg_id else managed_rg_id
            )
            config["managed_resource_group_name"] = rg_name

        # Public network access
        if properties.get("publicNetworkAccess"):
            config["public_network_access_enabled"] = (
                properties.get("publicNetworkAccess", "Enabled") == "Enabled"
            )

        # Network security
        if properties.get("requiredNsgRules"):
            config["network_security_group_rules_required"] = properties.get(
                "requiredNsgRules"
            )

        # Custom parameters for VNet injection
        custom_params = properties.get("parameters", {})
        if custom_params:
            custom_params_config = {}

            # VNet ID
            if custom_params.get("customVirtualNetworkId", {}).get("value"):
                custom_params_config["virtual_network_id"] = custom_params[
                    "customVirtualNetworkId"
                ]["value"]

            # Public subnet
            if custom_params.get("customPublicSubnetName", {}).get("value"):
                custom_params_config["public_subnet_name"] = custom_params[
                    "customPublicSubnetName"
                ]["value"]

            # Private subnet
            if custom_params.get("customPrivateSubnetName", {}).get("value"):
                custom_params_config["private_subnet_name"] = custom_params[
                    "customPrivateSubnetName"
                ]["value"]

            # Public subnet NSG association
            if custom_params.get("enableNoPublicIp", {}).get("value"):
                custom_params_config["no_public_ip"] = True

            if custom_params_config:
                config["custom_parameters"] = custom_params_config

        # Infrastructure encryption
        if (
            properties.get("encryption", {})
            .get("entities", {})
            .get("managedDisk", {})
            .get("keySource")
        ):
            config["infrastructure_encryption_enabled"] = True

        # Customer managed keys
        encryption = properties.get("encryption", {})
        if (
            encryption.get("entities", {})
            .get("managedServices", {})
            .get("keyVaultProperties")
        ):
            config["customer_managed_key_enabled"] = True

        logger.debug(f"Databricks Workspace '{resource_name}' emitted")

        return "azurerm_databricks_workspace", safe_name, config
