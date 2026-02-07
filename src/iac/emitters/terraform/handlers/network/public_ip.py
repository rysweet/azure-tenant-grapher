"""Public IP Address handler for Terraform emission.

Handles: Microsoft.Network/publicIPAddresses
Emits: azurerm_public_ip
"""

import hashlib
import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class PublicIPHandler(ResourceHandler):
    """Handler for Azure Public IP Addresses.

    Emits:
        - azurerm_public_ip
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Network/publicIPAddresses",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_public_ip",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Azure Public IP to Terraform configuration.

        Args:
            resource: Azure resource dictionary from graph
            context: Shared emitter context

        Returns:
            Tuple of (terraform_type, resource_name, config) or None if skipped
        """
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)

        # Build base configuration
        config = self.build_base_config(resource)

        # Public IP specific properties
        properties = self.parse_properties(resource)

        # Allocation method (required)
        allocation_method = resource.get("allocation_method") or properties.get(
            "publicIPAllocationMethod", "Static"
        )
        config["allocation_method"] = allocation_method

        # SKU
        sku = properties.get("sku", {})
        if sku and "name" in sku:
            config["sku"] = sku["name"]

        # IP version
        ip_version = properties.get("publicIPAddressVersion")
        if ip_version:
            config["ip_version"] = ip_version

        # Domain name label - Must be globally unique within region
        # Fix #892: Add hash suffix to ensure uniqueness across deployments
        dns_settings = properties.get("dnsSettings", {})
        if dns_settings and "domainNameLabel" in dns_settings:
            original_label = dns_settings["domainNameLabel"]

            # DNS labels must be globally unique within region
            # Add hash-based suffix for uniqueness (similar to Storage Account pattern)
            resource_id = resource.get("id", "")
            if resource_id:
                hash_val = hashlib.md5(
                    resource_id.encode(), usedforsecurity=False
                ).hexdigest()[:6]

                # DNS label must be lowercase alphanumeric with hyphens, max 63 chars
                # Truncate if needed to leave room for hash suffix (6 chars + hyphen)
                sanitized_label = original_label.lower()
                if len(sanitized_label) > 56:
                    sanitized_label = sanitized_label[:56]

                transformed_label = f"{sanitized_label}-{hash_val}"
                config["domain_name_label"] = transformed_label

                logger.info(
                    f"DNS label transformed for global uniqueness: {original_label} → {transformed_label}"
                )

                # Preserve original label in tags for reference
                if "tags" not in config:
                    config["tags"] = {}
                config["tags"]["original_dns_label"] = original_label
            else:
                # Fallback: use original label if no resource ID
                config["domain_name_label"] = original_label.lower()

        logger.debug(
            f"Public IP '{resource_name}' emitted with allocation_method={allocation_method}"
        )

        return "azurerm_public_ip", safe_name, config
