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

    Note: Phase 5 fix - ID Abstraction Service now generates Azure-compliant names
    in the graph, so no sanitization needed here.
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

        # Cognitive Services names must be globally unique
        # Phase 5: Names already Azure-compliant from ID Abstraction Service
        abstracted_name = config["name"]

        # Add tenant-specific suffix for cross-tenant deployments
        if (
            context.target_tenant_id
            and context.source_tenant_id != context.target_tenant_id
        ):
            # Add target tenant suffix (last 6 chars of tenant ID, alphanumeric only)
            tenant_suffix = context.target_tenant_id[-6:].replace("-", "").lower()

            # Name already sanitized by ID Abstraction Service - just truncate if needed
            # Truncate to fit (64 - 7 = 57 chars for abstracted name + dash)
            if len(abstracted_name) > 57:
                abstracted_name = abstracted_name[:57]

            config["name"] = f"{abstracted_name}-{tenant_suffix}"
            logger.info(
                f"Cross-tenant deployment: Cognitive Services '{abstracted_name}' → '{config['name']}' (tenant suffix: {tenant_suffix})"
            )
        else:
            config["name"] = abstracted_name

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
