"""Event Hub handlers for Terraform emission.

Handles: Microsoft.EventHub/namespaces, Microsoft.EventHub/namespaces/eventhubs
Emits: azurerm_eventhub_namespace, azurerm_eventhub
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class EventHubNamespaceHandler(ResourceHandler):
    """Handler for Azure Event Hub Namespaces.

    Emits:
        - azurerm_eventhub_namespace

    Note: Phase 5 fix - ID Abstraction Service now generates Azure-compliant names
    in the graph, so no sanitization needed here.
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.EventHub/namespaces",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_eventhub_namespace",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Event Hub Namespace to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        config = self.build_base_config(resource)

        # Event Hub Namespace names must be globally unique (*.servicebus.windows.net)
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
            # Truncate to fit (50 - 7 = 43 chars for abstracted name + dash)
            if len(abstracted_name) > 43:
                abstracted_name = abstracted_name[:43]

            config["name"] = f"{abstracted_name}-{tenant_suffix}"
            logger.info(
                f"Cross-tenant deployment: Event Hub Namespace '{abstracted_name}' → '{config['name']}' (tenant suffix: {tenant_suffix})"
            )
        else:
            config["name"] = abstracted_name

        # SKU
        sku = properties.get("sku", {})
        config["sku"] = (
            sku.get("name", "Standard") if isinstance(sku, dict) else "Standard"
        )
        config["capacity"] = sku.get("capacity", 1) if isinstance(sku, dict) else 1

        # Additional settings
        config["auto_inflate_enabled"] = properties.get("isAutoInflateEnabled", False)
        if config["auto_inflate_enabled"]:
            config["maximum_throughput_units"] = properties.get(
                "maximumThroughputUnits", 20
            )

        logger.debug(f"Event Hub Namespace '{resource_name}' emitted")

        return "azurerm_eventhub_namespace", safe_name, config


@handler
class EventHubHandler(ResourceHandler):
    """Handler for Azure Event Hubs.

    Emits:
        - azurerm_eventhub
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.EventHub/namespaces/eventhubs",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_eventhub",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Event Hub to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        properties = self.parse_properties(resource)

        # Extract namespace and hub names
        full_name = resource_name
        if "/" in full_name:
            namespace_name = full_name.split("/")[0]
            hub_name = full_name.split("/")[1]
        else:
            namespace_name = "unknown-namespace"
            hub_name = full_name

        safe_name = self.sanitize_name(hub_name)

        config = self.build_base_config(resource)
        config["name"] = hub_name

        config.update(
            {
                "namespace_name": namespace_name,
                "partition_count": properties.get("partitionCount", 2),
                "message_retention": properties.get("messageRetentionInDays", 1),
            }
        )

        logger.debug(f"Event Hub '{hub_name}' emitted for namespace '{namespace_name}'")

        return "azurerm_eventhub", safe_name, config
