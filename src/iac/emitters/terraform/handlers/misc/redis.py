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

        # SKU configuration
        sku = properties.get("sku", {})
        config["capacity"] = sku.get("capacity", 1) if isinstance(sku, dict) else 1
        config["family"] = sku.get("family", "C") if isinstance(sku, dict) else "C"
        config["sku_name"] = (
            sku.get("name", "Standard") if isinstance(sku, dict) else "Standard"
        )

        # Redis version
        config["redis_version"] = properties.get("redisVersion", "6")

        # Non-SSL port (Bug #567: correct property name)
        # Note: Azure uses enableNonSslPort, Terraform uses non_ssl_port_enabled
        config["non_ssl_port_enabled"] = properties.get("enableNonSslPort", False)

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
