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

        # Optional: public_network_access_enabled (security - HIGH for network isolation)
        # Maps to Azure property: publicNetworkAccess
        public_network_access = properties.get("publicNetworkAccess")
        if public_network_access is not None:
            if public_network_access == "Enabled":
                config["public_network_access_enabled"] = True
            elif public_network_access == "Disabled":
                config["public_network_access_enabled"] = False
            else:
                logger.warning(
                    f"Cognitive Services '{resource_name}': publicNetworkAccess "
                    f"unexpected value '{public_network_access}', expected 'Enabled' or 'Disabled'"
                )

        # Optional: local_auth_enabled (security - MEDIUM for authentication control)
        # Maps to Azure property: disableLocalAuth (note: inverse logic!)
        disable_local_auth = properties.get("disableLocalAuth")
        if disable_local_auth is not None:
            if not isinstance(disable_local_auth, bool):
                logger.warning(
                    f"Cognitive Services '{resource_name}': disableLocalAuth "
                    f"expected bool, got {type(disable_local_auth).__name__}"
                )
            else:
                # Note: Inverse logic - Azure has disableLocalAuth, Terraform has local_auth_enabled
                config["local_auth_enabled"] = not disable_local_auth

        # Optional: network_acls (security - HIGH for network restrictions)
        # Maps to Azure property: networkAcls
        network_acls = properties.get("networkAcls")
        if network_acls and isinstance(network_acls, dict):
            acl_config = {}
            default_action = network_acls.get("defaultAction", "Allow")
            if default_action:
                acl_config["default_action"] = default_action

            # IP rules
            ip_rules = network_acls.get("ipRules", [])
            if ip_rules:
                acl_config["ip_rules"] = [
                    rule.get("value") for rule in ip_rules if rule.get("value")
                ]

            # Virtual network rules
            vnet_rules = network_acls.get("virtualNetworkRules", [])
            if vnet_rules:
                acl_config["virtual_network_rules"] = [
                    {"subnet_id": rule.get("id")}
                    for rule in vnet_rules
                    if rule.get("id")
                ]

            if acl_config:
                config["network_acls"] = acl_config

        logger.debug(f"Cognitive Services '{resource_name}' emitted with kind='{kind}'")

        return "azurerm_cognitive_account", safe_name, config
