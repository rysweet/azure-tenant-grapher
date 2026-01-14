"""Search Service handler for Terraform emission.

Handles: Microsoft.Search/searchServices
Emits: azurerm_search_service
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from src.services.azure_name_sanitizer import AzureNameSanitizer
from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class SearchServiceHandler(ResourceHandler):
    """Handler for Azure Cognitive Search Service.

    Emits:
        - azurerm_search_service
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "microsoft.search/searchservices",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_search_service",
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
        """Convert Search Service to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        config = self.build_base_config(resource)

        # Search Service names must be globally unique (*.search.windows.net)
        # Sanitize using centralized Azure naming rules
        abstracted_name = config["name"]
        sanitized_name = self.sanitizer.sanitize(
            abstracted_name, "Microsoft.Search/searchServices"
        )

        # Add tenant-specific suffix for cross-tenant deployments
        if (
            context.target_tenant_id
            and context.source_tenant_id != context.target_tenant_id
        ):
            # Add target tenant suffix (last 6 chars of tenant ID, alphanumeric only)
            tenant_suffix = context.target_tenant_id[-6:].replace("-", "").lower()

            # Truncate to fit (60 - 7 = 53 chars for sanitized name + dash)
            if len(sanitized_name) > 53:
                sanitized_name = sanitized_name[:53]

            config["name"] = f"{sanitized_name}-{tenant_suffix}"
            logger.info(
                f"Cross-tenant deployment: Search Service '{abstracted_name}' → '{config['name']}' (tenant suffix: {tenant_suffix})"
            )
        else:
            config["name"] = sanitized_name

        # SKU
        sku = resource.get("sku", {})
        config["sku"] = (
            sku.get("name", "standard") if isinstance(sku, dict) else "standard"
        )

        # Replica and partition count
        if properties.get("replicaCount"):
            config["replica_count"] = properties.get("replicaCount")
        if properties.get("partitionCount"):
            config["partition_count"] = properties.get("partitionCount")

        # Public network access
        if properties.get("publicNetworkAccess"):
            config["public_network_access_enabled"] = (
                properties.get("publicNetworkAccess", "enabled") == "enabled"
            )

        # Hosting mode
        if properties.get("hostingMode"):
            config["hosting_mode"] = properties.get("hostingMode", "default")

        # Local authentication
        if properties.get("disableLocalAuth") is not None:
            config["local_authentication_enabled"] = not properties.get(
                "disableLocalAuth"
            )

        # Semantic search
        if properties.get("semanticSearch"):
            config["semantic_search_sku"] = properties.get("semanticSearch")

        # Allowed IPs (network rules)
        network_rules = properties.get("networkRuleSet", {})
        ip_rules = network_rules.get("ipRules", [])
        if ip_rules:
            config["allowed_ips"] = [
                rule.get("value", "") for rule in ip_rules if rule.get("value")
            ]

        # Identity
        identity = resource.get("identity", {})
        if identity.get("type"):
            identity_type = identity.get("type", "").lower()
            if "systemassigned" in identity_type:
                config["identity"] = {"type": "SystemAssigned"}

        # Customer managed key
        encryption = properties.get("encryptionWithCmk", {})
        if encryption.get("enforcement"):
            config["customer_managed_key_enforcement_enabled"] = (
                encryption.get("enforcement") == "Enabled"
            )

        logger.debug(f"Search Service '{resource_name}' emitted")

        return "azurerm_search_service", safe_name, config
