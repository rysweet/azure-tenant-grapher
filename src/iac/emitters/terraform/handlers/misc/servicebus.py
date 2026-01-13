"""Service Bus handlers for Terraform emission.

Handles: Microsoft.ServiceBus/namespaces, Microsoft.ServiceBus/namespaces/queues
Emits: azurerm_servicebus_namespace, azurerm_servicebus_queue
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from src.services.azure_name_sanitizer import AzureNameSanitizer
from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class ServiceBusNamespaceHandler(ResourceHandler):
    """Handler for Azure Service Bus Namespaces.

    Emits:
        - azurerm_servicebus_namespace
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.ServiceBus/namespaces",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_servicebus_namespace",
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
        """Convert Service Bus Namespace to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        config = self.build_base_config(resource)

        # Service Bus Namespace names must be globally unique (*.servicebus.windows.net)
        # Sanitize using centralized Azure naming rules
        abstracted_name = config["name"]
        sanitized_name = self.sanitizer.sanitize(
            abstracted_name, "Microsoft.ServiceBus/namespaces"
        )

        # Add tenant-specific suffix for cross-tenant deployments
        if (
            context.target_tenant_id
            and context.source_tenant_id != context.target_tenant_id
        ):
            # Add target tenant suffix (last 6 chars of tenant ID, alphanumeric only)
            tenant_suffix = context.target_tenant_id[-6:].replace("-", "").lower()

            # Truncate to fit (50 - 7 = 43 chars for sanitized name + dash)
            if len(sanitized_name) > 43:
                sanitized_name = sanitized_name[:43]

            config["name"] = f"{sanitized_name}-{tenant_suffix}"
            logger.info(
                f"Cross-tenant deployment: Service Bus Namespace '{abstracted_name}' → '{config['name']}' (tenant suffix: {tenant_suffix})"
            )
        else:
            config["name"] = sanitized_name

        # SKU
        sku = properties.get("sku", {})
        config["sku"] = (
            sku.get("name", "Standard") if isinstance(sku, dict) else "Standard"
        )

        # Capacity for Premium SKU
        if config["sku"] == "Premium":
            config["capacity"] = sku.get("capacity", 1) if isinstance(sku, dict) else 1

        # Premium features
        # REMOVED: zone_redundant is deprecated in azurerm provider v4+
        # Zone redundancy is now automatically enabled for Premium SKU
        if properties.get("premiumMessagingPartitions"):
            config["premium_messaging_partitions"] = properties.get(
                "premiumMessagingPartitions"
            )

        logger.debug(f"Service Bus Namespace '{resource_name}' emitted")

        return "azurerm_servicebus_namespace", safe_name, config


@handler
class ServiceBusQueueHandler(ResourceHandler):
    """Handler for Azure Service Bus Queues.

    Emits:
        - azurerm_servicebus_queue
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.ServiceBus/namespaces/queues",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_servicebus_queue",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Service Bus Queue to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        properties = self.parse_properties(resource)

        # Extract namespace and queue names
        full_name = resource_name
        if "/" in full_name:
            namespace_name = full_name.split("/")[0]
            queue_name = full_name.split("/")[1]
        else:
            namespace_name = "unknown-namespace"
            queue_name = full_name

        safe_name = self.sanitize_name(queue_name)

        config = self.build_base_config(resource)
        config["name"] = queue_name

        config.update(
            {
                "namespace_id": f"${{azurerm_servicebus_namespace.{self.sanitize_name(namespace_name)}.id}}",
                "enable_partitioning": properties.get("enablePartitioning", False),
                "max_delivery_count": properties.get("maxDeliveryCount", 10),
            }
        )

        # Optional settings
        if properties.get("lockDuration"):
            config["lock_duration"] = properties.get("lockDuration")
        if properties.get("defaultMessageTimeToLive"):
            config["default_message_ttl"] = properties.get("defaultMessageTimeToLive")
        if properties.get("deadLetteringOnMessageExpiration"):
            config["dead_lettering_on_message_expiration"] = True
        if properties.get("requiresDuplicateDetection"):
            config["requires_duplicate_detection"] = True
        if properties.get("requiresSession"):
            config["requires_session"] = True

        logger.debug(
            f"Service Bus Queue '{queue_name}' emitted for namespace '{namespace_name}'"
        )

        return "azurerm_servicebus_queue", safe_name, config
