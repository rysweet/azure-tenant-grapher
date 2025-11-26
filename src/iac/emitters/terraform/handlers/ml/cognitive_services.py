"""Cognitive Services handler for Terraform emission.

Handles: Microsoft.CognitiveServices/accounts
Emits: azurerm_cognitive_account
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class CognitiveServicesHandler(ResourceHandler):
    """Handler for Azure Cognitive Services.

    Emits:
        - azurerm_cognitive_account
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.CognitiveServices/accounts",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_cognitive_account",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Cognitive Services account to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        config = self.build_base_config(resource)

        # Kind (required)
        kind = properties.get("kind", resource.get("kind", "OpenAI"))
        config["kind"] = kind

        # SKU (required)
        sku = properties.get("sku", {})
        config["sku_name"] = sku.get("name", "S0") if isinstance(sku, dict) else "S0"

        # Custom subdomain
        custom_subdomain = properties.get("customSubDomainName")
        if custom_subdomain:
            config["custom_subdomain_name"] = custom_subdomain

        logger.debug(f"Cognitive Services '{resource_name}' emitted with kind='{kind}'")

        return "azurerm_cognitive_account", safe_name, config
