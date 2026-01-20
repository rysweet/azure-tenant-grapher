"""Key Vault handler for Terraform emission.

Handles: Microsoft.KeyVault/vaults
Emits: azurerm_key_vault
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class KeyVaultHandler(ResourceHandler):
    """Handler for Azure Key Vaults.

    Emits:
        - azurerm_key_vault

    Note: Phase 5 fix - ID Abstraction Service now generates Azure-compliant names
    in the graph, so no sanitization needed here.
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.KeyVault/vaults",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_key_vault",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Azure Key Vault to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        properties = self.parse_properties(resource)

        config = self.build_base_config(resource)

        # Key Vaults need globally unique names
        # Phase 5: Names already Azure-compliant from ID Abstraction Service
        abstracted_name = config["name"]

        # Add tenant suffix for cross-tenant deployments (using resource ID hash for determinism)
        if (
            context.target_tenant_id
            and context.source_tenant_id != context.target_tenant_id
        ):
            import hashlib

            resource_id = resource.get("id", "")
            tenant_suffix = (
                hashlib.md5(resource_id.encode()).hexdigest()[:6]
                if resource_id
                else "000000"
            )

            # Name already sanitized by ID Abstraction Service - just truncate if needed
            # Truncate to fit (24 - 7 = 17 chars for abstracted name + hyphen)
            if len(abstracted_name) > 17:
                abstracted_name = abstracted_name[:17]

            config["name"] = f"{abstracted_name}-{tenant_suffix}"
            logger.info(
                f"Key Vault name made globally unique: {resource_name} → {config['name']}"
            )
        else:
            config["name"] = abstracted_name

        safe_name = self.sanitize_name(config["name"])

        # SKU (required)
        sku = properties.get("sku", {})
        sku_name = sku.get("name", "standard") if isinstance(sku, dict) else "standard"
        config["sku_name"] = sku_name.lower()  # Fix #596: Terraform requires lowercase

        # Tenant ID (required) - Fix #604: Use target tenant ID for cross-tenant deployment
        # ISSUE #475: NEVER use raw source tenantId - it leaks source tenant GUID
        # Priority: target_tenant_id (cross-tenant) > variable reference (same-tenant)
        if context.target_tenant_id:
            config["tenant_id"] = context.target_tenant_id
        else:
            # Use variable reference - NEVER fall back to properties.get("tenantId")
            config["tenant_id"] = "${var.tenant_id}"

        # Soft delete settings
        soft_delete_enabled = properties.get("enableSoftDelete", True)
        if soft_delete_enabled:
            config["soft_delete_retention_days"] = properties.get(
                "softDeleteRetentionInDays", 90
            )

        # Purge protection
        purge_protection = properties.get("enablePurgeProtection", False)
        if purge_protection:
            config["purge_protection_enabled"] = True

        # Optional: public_network_access (security - HIGH for network isolation)
        # Maps to Azure property: publicNetworkAccess
        # Note: Azure uses "Enabled"/"Disabled" strings, Terraform uses boolean
        public_network_access = properties.get("publicNetworkAccess")
        if public_network_access is not None:
            if public_network_access == "Enabled":
                config["public_network_access_enabled"] = True
            elif public_network_access == "Disabled":
                config["public_network_access_enabled"] = False
            else:
                logger.warning(
                    f"Key Vault '{resource_name}': publicNetworkAccess "
                    f"unexpected value '{public_network_access}', expected 'Enabled' or 'Disabled'"
                )

        # Optional: enable_rbac_authorization (security - MEDIUM for access control)
        # Maps to Azure property: enableRbacAuthorization
        enable_rbac = properties.get("enableRbacAuthorization")
        if enable_rbac is not None:
            if not isinstance(enable_rbac, bool):
                logger.warning(
                    f"Key Vault '{resource_name}': enableRbacAuthorization "
                    f"expected bool, got {type(enable_rbac).__name__}"
                )
            else:
                config["enable_rbac_authorization"] = enable_rbac

        # Optional: network_acls (security - HIGH for network restrictions)
        # Maps to Azure property: networkAcls
        network_acls = properties.get("networkAcls")
        if network_acls and isinstance(network_acls, dict):
            # Terraform expects network_acls block
            acl_config = {}

            # Default action
            default_action = network_acls.get("defaultAction", "Allow")
            if default_action:
                acl_config["default_action"] = default_action

            # IP rules
            ip_rules = network_acls.get("ipRules", [])
            if ip_rules:
                acl_config["ip_rules"] = [
                    rule.get("value") for rule in ip_rules if rule.get("value")
                ]

            # Virtual network subnet IDs
            vnet_rules = network_acls.get("virtualNetworkRules", [])
            if vnet_rules:
                acl_config["virtual_network_subnet_ids"] = [
                    rule.get("id") for rule in vnet_rules if rule.get("id")
                ]

            # Bypass (AzureServices, None)
            bypass = network_acls.get("bypass", "AzureServices")
            if bypass:
                acl_config["bypass"] = bypass

            if acl_config:
                config["network_acls"] = acl_config

        logger.debug(f"Key Vault '{resource_name}' -> '{config['name']}' emitted")

        return "azurerm_key_vault", safe_name, config

    def _add_unique_suffix(self, name: str, resource_id: str) -> str:
        """Add a unique suffix based on resource ID hash."""
        import hashlib

        if not resource_id:
            return name

        # Generate 6-character hash from resource ID
        hash_val = hashlib.md5(resource_id.encode()).hexdigest()[:6]
        return f"{name}-{hash_val}"
