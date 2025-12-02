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
