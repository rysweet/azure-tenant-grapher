"""Cosmos DB handler for Terraform emission.

Handles: Microsoft.DocumentDB/databaseAccounts
Emits: azurerm_cosmosdb_account
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class CosmosDBHandler(ResourceHandler):
    """Handler for Azure Cosmos DB Accounts.

    Emits:
        - azurerm_cosmosdb_account
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "microsoft.documentdb/databaseaccounts",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_cosmosdb_account",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Cosmos DB Account to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        config = self.build_base_config(resource)

        # Required: offer_type
        config["offer_type"] = "Standard"

        # Required: consistency_policy block
        consistency = properties.get("consistencyPolicy", {})
        config["consistency_policy"] = {
            "consistency_level": consistency.get("defaultConsistencyLevel", "Session"),
            "max_interval_in_seconds": consistency.get("maxIntervalInSeconds", 5),
            "max_staleness_prefix": consistency.get("maxStalenessPrefix", 100),
        }

        # Required: geo_location block
        locations = properties.get("locations", [])
        location = self.get_location(resource)

        if locations:
            config["geo_location"] = [
                {
                    "location": loc.get("locationName", location).lower(),
                    "failover_priority": loc.get("failoverPriority", 0),
                }
                for loc in locations
            ]
        else:
            config["geo_location"] = [{"location": location, "failover_priority": 0}]

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
                    f"Cosmos DB '{resource_name}': publicNetworkAccess "
                    f"unexpected value '{public_network_access}', expected 'Enabled' or 'Disabled'"
                )

        # Optional: local_authentication_disabled (security - MEDIUM for auth control)
        # Maps to Azure property: disableLocalAuth
        disable_local_auth = properties.get("disableLocalAuth")
        if disable_local_auth is not None:
            if not isinstance(disable_local_auth, bool):
                logger.warning(
                    f"Cosmos DB '{resource_name}': disableLocalAuth "
                    f"expected bool, got {type(disable_local_auth).__name__}"
                )
            else:
                config["local_authentication_disabled"] = disable_local_auth

        # Optional: ip_range_filter (security - HIGH for IP firewall)
        # Maps to Azure property: ipRules
        ip_rules = properties.get("ipRules", [])
        if ip_rules:
            # Cosmos DB expects comma-separated CIDR ranges
            config["ip_range_filter"] = ",".join([rule.get("ipAddressOrRange", "") for rule in ip_rules if rule.get("ipAddressOrRange")])

        # Optional: virtual_network_rule (security - HIGH for VNet restrictions)
        # Maps to Azure property: virtualNetworkRules
        vnet_rules = properties.get("virtualNetworkRules", [])
        if vnet_rules:
            config["virtual_network_rule"] = [{
                "id": rule.get("id")
            } for rule in vnet_rules if rule.get("id")]

        logger.debug(
            f"Cosmos DB '{resource_name}' emitted with "
            f"{len(config.get('geo_location', []))} locations"
        )

        return "azurerm_cosmosdb_account", safe_name, config
