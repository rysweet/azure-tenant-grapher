"""Container Registry handler for Terraform emission.

Handles: Microsoft.ContainerRegistry/registries
Emits: azurerm_container_registry
"""

import hashlib
import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class ContainerRegistryHandler(ResourceHandler):
    """Handler for Azure Container Registries.

    Emits:
        - azurerm_container_registry

    Note: Phase 5 fix - ID Abstraction Service now generates Azure-compliant names
    in the graph, so no sanitization needed here.
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.ContainerRegistry/registries",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_container_registry",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Container Registry to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        config = self.build_base_config(resource)

        # Container Registry names must be globally unique (*.azurecr.io)
        # Phase 5: Names already Azure-compliant from ID Abstraction Service
        abstracted_name = config["name"]

        # Add hash-based suffix for global uniqueness (works in all deployment modes)
        resource_id = resource.get("id", "")
        if resource_id:
            hash_val = hashlib.md5(
                resource_id.encode(), usedforsecurity=False
            ).hexdigest()[:6]
            # Name already sanitized by ID Abstraction Service - just truncate if needed
            if len(abstracted_name) > 44:  # 50 char limit - 6 char hash
                abstracted_name = abstracted_name[:44]
            config["name"] = f"{abstracted_name}{hash_val}"
            logger.info(
                f"Container Registry name made globally unique: {resource_name} → {config['name']}"
            )
        else:
            config["name"] = abstracted_name

        # SKU (required)
        sku = properties.get("sku", {})
        sku_name = sku.get("name", "Basic") if isinstance(sku, dict) else "Basic"
        config["sku"] = sku_name

        # Admin enabled
        admin_enabled = properties.get("adminUserEnabled", False)
        if admin_enabled:
            config["admin_enabled"] = True

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
                    f"Container Registry '{resource_name}': publicNetworkAccess "
                    f"unexpected value '{public_network_access}', expected 'Enabled' or 'Disabled'"
                )

        # Optional: data_endpoint_enabled (security - MEDIUM for data access control)
        # Maps to Azure property: dataEndpointEnabled
        data_endpoint = properties.get("dataEndpointEnabled")
        if data_endpoint is not None:
            if not isinstance(data_endpoint, bool):
                logger.warning(
                    f"Container Registry '{resource_name}': dataEndpointEnabled "
                    f"expected bool, got {type(data_endpoint).__name__}"
                )
            else:
                config["data_endpoint_enabled"] = data_endpoint

        # Optional: network_rule_set (security - HIGH for network restrictions)
        # Maps to Azure property: networkRuleSet
        network_rule_set = properties.get("networkRuleSet")
        if network_rule_set and isinstance(network_rule_set, dict):
            default_action = network_rule_set.get("defaultAction", "Allow")
            if default_action:
                config["network_rule_set"] = [{
                    "default_action": default_action
                }]

        logger.debug(f"Container Registry '{resource_name}' emitted")

        return "azurerm_container_registry", safe_name, config
