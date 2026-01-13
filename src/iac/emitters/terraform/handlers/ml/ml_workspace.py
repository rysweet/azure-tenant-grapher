"""ML Workspace handler for Terraform emission.

Handles: Microsoft.MachineLearningServices/workspaces
Emits: azurerm_machine_learning_workspace
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class MLWorkspaceHandler(ResourceHandler):
    """Handler for Azure Machine Learning Workspaces.

    Emits:
        - azurerm_machine_learning_workspace
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.MachineLearningServices/workspaces",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_machine_learning_workspace",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert ML Workspace to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        config = self.build_base_config(resource)

        # SKU
        sku = properties.get("sku", {})
        config["sku_name"] = (
            sku.get("name", "Basic") if isinstance(sku, dict) else "Basic"
        )

        # Identity (required)
        config["identity"] = {"type": "SystemAssigned"}

        rg_name = self.get_resource_group(resource)
        sub_id = context.get_effective_subscription_id(resource)

        # Storage account (required)
        storage_account_id = properties.get("storageAccount")
        if not storage_account_id:
            storage_account_id = (
                f"/subscriptions/{sub_id}/resourceGroups/{rg_name}/"
                f"providers/Microsoft.Storage/storageAccounts/mlworkspace{resource_name[:8]}"
            )
        config["storage_account_id"] = storage_account_id

        # Key Vault (required)
        key_vault_id = properties.get("keyVault")
        if not key_vault_id:
            key_vault_id = (
                f"/subscriptions/{sub_id}/resourceGroups/{rg_name}/"
                f"providers/Microsoft.KeyVault/vaults/mlworkspace{resource_name[:8]}"
            )

        # Fix casing: Azure might return "Microsoft.Keyvault" but Terraform expects "Microsoft.KeyVault"
        if key_vault_id:
            key_vault_id = key_vault_id.replace(
                "/Microsoft.Keyvault/", "/Microsoft.KeyVault/"
            )
            key_vault_id = key_vault_id.replace(
                "/microsoft.keyvault/", "/Microsoft.KeyVault/"
            )

        config["key_vault_id"] = key_vault_id

        # Application Insights (required)
        app_insights_id = properties.get("applicationInsights")
        if not app_insights_id:
            app_insights_id = (
                f"/subscriptions/{sub_id}/resourceGroups/{rg_name}/"
                f"providers/Microsoft.Insights/components/mlworkspace{resource_name[:8]}"
            )

        # Fix casing: Azure returns "Microsoft.insights" but Terraform expects "Microsoft.Insights"
        if app_insights_id:
            app_insights_id = app_insights_id.replace(
                "/Microsoft.insights/", "/Microsoft.Insights/"
            )
            app_insights_id = app_insights_id.replace(
                "/microsoft.insights/", "/Microsoft.Insights/"
            )

        config["application_insights_id"] = app_insights_id

        logger.debug(f"ML Workspace '{resource_name}' emitted")

        return "azurerm_machine_learning_workspace", safe_name, config
