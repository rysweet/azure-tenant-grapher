"""Redis Cache handler for Terraform emission.

Handles: Microsoft.Cache/Redis
Emits: azurerm_redis_cache
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class RedisCacheHandler(ResourceHandler):
    """Handler for Azure Redis Cache.

    Emits:
        - azurerm_redis_cache

    Note: Phase 5 fix - ID Abstraction Service now generates Azure-compliant names
    in the graph, so no sanitization needed here.
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "microsoft.cache/redis",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_redis_cache",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Redis Cache to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        config = self.build_base_config(resource)

        # Redis Cache names must be globally unique (*.redis.cache.windows.net)
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
            # Truncate to fit (63 - 7 = 56 chars for abstracted name + dash)
            if len(abstracted_name) > 56:
                abstracted_name = abstracted_name[:56]

            config["name"] = f"{abstracted_name}-{tenant_suffix}"
            logger.info(
                f"Cross-tenant deployment: Redis Cache '{abstracted_name}' → '{config['name']}' (tenant suffix: {tenant_suffix})"
            )
        else:
            config["name"] = abstracted_name

        # SKU configuration
        sku = properties.get("sku", {})
        config["capacity"] = sku.get("capacity", 1) if isinstance(sku, dict) else 1
        config["family"] = sku.get("family", "C") if isinstance(sku, dict) else "C"
        config["sku_name"] = (
            sku.get("name", "Standard") if isinstance(sku, dict) else "Standard"
        )

        # Redis version - must be "4" or "6" (string without decimal)
        redis_version = str(properties.get("redisVersion", "6"))
        # Strip decimal if present (e.g., "6.0" -> "6")
        if "." in redis_version:
            redis_version = redis_version.split(".")[0]
        config["redis_version"] = redis_version

        # Non-SSL port - REMOVED: enable_non_ssl_port is deprecated in azurerm provider
        # The field has been removed from the provider and causes validation errors
        # Azure Redis Cache now only supports SSL connections

        # Minimum TLS version
        config["minimum_tls_version"] = properties.get("minimumTlsVersion", "1.2")

        # Public network access
        if properties.get("publicNetworkAccess"):
            config["public_network_access_enabled"] = (
                properties.get("publicNetworkAccess", "Enabled") == "Enabled"
            )

        # Redis configuration
        redis_config = properties.get("redisConfiguration", {})
        if redis_config:
            tf_redis_config = {}
            if redis_config.get("maxmemory-policy"):
                tf_redis_config["maxmemory_policy"] = redis_config.get(
                    "maxmemory-policy"
                )
            if redis_config.get("maxmemory-reserved"):
                tf_redis_config["maxmemory_reserved"] = redis_config.get(
                    "maxmemory-reserved"
                )
            if redis_config.get("maxfragmentationmemory-reserved"):
                tf_redis_config["maxfragmentationmemory_reserved"] = redis_config.get(
                    "maxfragmentationmemory-reserved"
                )
            if tf_redis_config:
                config["redis_configuration"] = tf_redis_config

        logger.debug(f"Redis Cache '{resource_name}' emitted")

        return "azurerm_redis_cache", safe_name, config
