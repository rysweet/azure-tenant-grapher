"""Automation Account handler for Terraform emission.

Handles: Microsoft.Automation/automationAccounts
Emits: azurerm_automation_account
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class AutomationAccountHandler(ResourceHandler):
    """Handler for Azure Automation Accounts.

    Emits:
        - azurerm_automation_account
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Automation/automationAccounts",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_automation_account",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Automation Account to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        config = self.build_base_config(resource)

        # SKU (required)
        sku = properties.get("sku", {})
        config["sku_name"] = (
            sku.get("name", "Basic") if isinstance(sku, dict) else "Basic"
        )

        logger.debug(f"Automation Account '{resource_name}' emitted")

        return "azurerm_automation_account", safe_name, config
