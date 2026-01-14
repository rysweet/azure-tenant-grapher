"""Azure Resource ID Builder.

This module provides strategy-based Azure resource ID construction for import blocks.
Azure resources use different ID patterns based on scope and hierarchy.

Architecture:
- AzureResourceIdPattern enum: Defines resource ID patterns
- AzureResourceIdBuilder: Strategy pattern dispatcher
- Pattern-specific builders: Construct IDs for each pattern type

Phase 1 & 2 Implementation: Minimum viable fix for critical resources (4 patterns)
- Resource Group Level: Standard Azure resources (existing logic)
- Child Resources: Subnets (266 resources)
- Subscription Level: Role assignments (1,017 resources)
- Association Resources: NSG associations (86 resources - NOT importable, skipped)

Expected Impact: +1,283 import blocks (from 228 → 1,511)
Note: Association resources excluded - they're synthetic Terraform constructs, not Azure resources

Note: Additional patterns (Tenant-level, Custom) will be added in Phase 3 if needed.
"""

import logging
from enum import Enum
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class AzureResourceIdPattern(Enum):
    """Azure resource ID patterns.

    Azure uses different ID structures based on resource scope and hierarchy.
    Each pattern requires different construction logic.
    """

    RESOURCE_GROUP_LEVEL = "resource_group"
    """Standard resources under resource groups.

    Format: /subscriptions/{sub}/resourceGroups/{rg}/providers/{provider}/{type}/{name}
    Examples: Storage accounts, VMs, VNets
    """

    CHILD_RESOURCE = "child"
    """Child resources nested under parent resources.

    Format: /subscriptions/{sub}/resourceGroups/{rg}/providers/{provider}/{parentType}/{parentName}/{childType}/{childName}
    Examples: Subnets, VM extensions
    """

    SUBSCRIPTION_LEVEL = "subscription"
    """Resources scoped to subscription, not resource groups.

    Format: /subscriptions/{sub}/providers/{provider}/{type}/{name}
    Examples: Role assignments, policy definitions
    """

    ASSOCIATION = "association"
    """Association resources linking two other resources.

    Format: {resource1_id}|{resource2_id} (compound ID)
    Examples: Subnet-NSG associations, NIC-NSG associations
    """


# Type-to-pattern mapping (Phase 1: Critical types only)
TERRAFORM_TYPE_TO_ID_PATTERN: Dict[str, AzureResourceIdPattern] = {
    # Child resources (HIGHEST IMPACT - 266 resources)
    "azurerm_subnet": AzureResourceIdPattern.CHILD_RESOURCE,
    # Subscription-level (HIGH IMPACT - 1,017 resources)
    "azurerm_role_assignment": AzureResourceIdPattern.SUBSCRIPTION_LEVEL,
    # Association resources (MEDIUM IMPACT - 86 resources)
    "azurerm_subnet_network_security_group_association": AzureResourceIdPattern.ASSOCIATION,
    "azurerm_network_interface_security_group_association": AzureResourceIdPattern.ASSOCIATION,
    # All other types default to RESOURCE_GROUP_LEVEL
    # (Handled by default case in builder)
}


class AzureResourceIdBuilder:
    """Azure Resource ID Builder using strategy pattern.

    Constructs Azure resource IDs for import blocks based on resource type patterns.
    Each Azure resource type follows one of several ID patterns. This builder dispatches
    to the appropriate construction method based on pattern detection.

    Usage:
        builder = AzureResourceIdBuilder(emitter)
        resource_id = builder.build("azurerm_subnet", config, subscription_id)

    Attributes:
        emitter: Reference to TerraformEmitter for accessing mappings and utilities
        _terraform_to_azure: Cached reverse mapping (Terraform type -> Azure type)
    """

    def __init__(self, emitter: Any):
        """Initialize the builder with reference to emitter.

        Args:
            emitter: TerraformEmitter instance for accessing AZURE_TO_TERRAFORM_MAPPING
        """
        self.emitter = emitter

        # Cache reverse mapping for performance (Issue #502 Review - Issue #3)
        self._terraform_to_azure: Dict[str, str] = {
            v: k for k, v in emitter.AZURE_TO_TERRAFORM_MAPPING.items()
        }

        # Strategy dispatch table: Pattern -> builder method
        self._builders: Dict[
            AzureResourceIdPattern,
            Callable[
                [str, Dict[str, Any], str, Optional[Dict[str, str]], Optional[str]],
                Optional[str],
            ],
        ] = {
            AzureResourceIdPattern.RESOURCE_GROUP_LEVEL: self._build_resource_group_level_id,
            AzureResourceIdPattern.CHILD_RESOURCE: self._build_child_resource_id,
            AzureResourceIdPattern.SUBSCRIPTION_LEVEL: self._build_subscription_level_id,
            AzureResourceIdPattern.ASSOCIATION: self._build_association_id,
        }

    def build(
        self,
        tf_resource_type: str,
        resource_config: Dict[str, Any],
        subscription_id: str,
        original_id_map: Optional[Dict[str, str]] = None,
        source_subscription_id: Optional[str] = None,
    ) -> Optional[str]:
        """Build Azure resource ID from Terraform resource config.

        Main entry point for ID construction. Detects pattern and dispatches to
        appropriate builder method.

        Bug #10 Fix: Accepts optional original_id_map to use real Azure IDs from Neo4j
        instead of constructing from config (which may contain Terraform variables).

        Args:
            tf_resource_type: Terraform resource type (e.g., "azurerm_storage_account")
            resource_config: Terraform resource configuration dict
            subscription_id: Azure subscription ID (target subscription for cross-tenant)
            original_id_map: Optional map of {terraform_resource_name: original_azure_id}
            source_subscription_id: Optional source subscription ID for cross-tenant translation

        Returns:
            Azure resource ID string or None if cannot be constructed
        """
        # Detect pattern for this resource type
        pattern = TERRAFORM_TYPE_TO_ID_PATTERN.get(
            tf_resource_type,
            AzureResourceIdPattern.RESOURCE_GROUP_LEVEL,  # Default pattern
        )

        # Dispatch to appropriate builder
        builder_method = self._builders.get(pattern)
        if not builder_method:
            logger.warning(
                f"No builder method for pattern {pattern.value} "
                f"(resource type: {tf_resource_type})"
            )
            return None

        # Build the ID
        try:
            return builder_method(
                tf_resource_type,
                resource_config,
                subscription_id,
                original_id_map,
                source_subscription_id,
            )
        except Exception as e:
            logger.warning(
                f"Failed to build resource ID for {tf_resource_type}: {e}",
                exc_info=True,
            )
            return None

    def _is_terraform_variable(self, value: str) -> bool:
        """Check if a string contains Terraform variable interpolation syntax.

        Detects patterns like:
        - ${azurerm_virtual_network.vnet.name}
        - ${var.vnet_name}
        - ${module.network.vnet_name}

        Args:
            value: String to check

        Returns:
            True if value contains Terraform variable syntax, False otherwise
        """
        import re

        return bool(re.search(r"\$\{.*?\}", value))

    def _translate_subscription_in_id(
        self,
        azure_resource_id: str,
        source_subscription_id: str,
        target_subscription_id: str,
    ) -> str:
        """Replace source subscription ID with target subscription ID in an Azure resource ID.

        Used for cross-tenant deployment where original_id from source tenant needs
        to be translated to target tenant's subscription.

        Args:
            azure_resource_id: Full Azure resource ID from source tenant
            source_subscription_id: Source subscription ID to replace
            target_subscription_id: Target subscription ID to use

        Returns:
            Azure resource ID with subscription translated to target

        Example:
            Input:  /subscriptions/source-123/resourceGroups/rg/...
            Output: /subscriptions/target-456/resourceGroups/rg/...
        """
        return azure_resource_id.replace(
            f"/subscriptions/{source_subscription_id}",
            f"/subscriptions/{target_subscription_id}",
            1,  # Only replace first occurrence
        )

    def _build_resource_group_level_id(
        self,
        tf_resource_type: str,
        resource_config: Dict[str, Any],
        subscription_id: str,
        original_id_map: Optional[Dict[str, str]] = None,
        source_subscription_id: Optional[str] = None,
    ) -> Optional[str]:
        """Build resource ID for standard resource group-level resources.

        This is the existing logic from terraform_emitter.py._build_azure_resource_id().
        Handles most Azure resources that live under resource groups.

        Format: /subscriptions/{sub}/resourceGroups/{rg}/providers/{provider}/{type}/{name}

        Args:
            tf_resource_type: Terraform resource type
            resource_config: Resource configuration dict
            subscription_id: Azure subscription ID

        Returns:
            Azure resource ID or None if cannot be constructed
        """
        resource_name = resource_config.get("name")
        if not resource_name:
            logger.warning(
                f"Resource group level resource missing 'name' field: {tf_resource_type}"
            )
            return None

        # Resource groups are special - no provider namespace needed
        if tf_resource_type == "azurerm_resource_group":
            return f"/subscriptions/{subscription_id}/resourceGroups/{resource_name}"

        # All other resources need resource group and provider namespace
        resource_group = resource_config.get("resource_group_name")
        if not resource_group:
            logger.warning(
                f"Resource missing 'resource_group_name' field: {tf_resource_type} ({resource_name})"
            )
            return None

        # Map Terraform type back to Azure provider/resource type
        # Use cached reverse mapping for performance
        azure_type = self._terraform_to_azure.get(tf_resource_type)

        if not azure_type:
            logger.warning(
                f"Unknown Terraform type (no Azure mapping): {tf_resource_type}"
            )
            return None

        # Standard Azure resource ID format
        return (
            f"/subscriptions/{subscription_id}/"
            f"resourceGroups/{resource_group}/"
            f"providers/{azure_type}/{resource_name}"
        )

    def _build_child_resource_id(
        self,
        tf_resource_type: str,
        resource_config: Dict[str, Any],
        subscription_id: str,
        original_id_map: Optional[Dict[str, str]] = None,
        source_subscription_id: Optional[str] = None,
    ) -> Optional[str]:
        """Build resource ID for child resources nested under parents.

        Child resources are nested under parent resources in Azure's hierarchy.
        Phase 1 implementation focuses on subnets only.

        Bug #10: Passes original_id_map to child builders for proper handling.

        Args:
            tf_resource_type: Terraform resource type
            resource_config: Resource configuration dict
            subscription_id: Azure subscription ID
            original_id_map: Optional map of original Azure IDs
            source_subscription_id: Optional source subscription for cross-tenant

        Returns:
            Azure resource ID or None if cannot be constructed
        """
        # Dispatch to specific child resource builders
        if tf_resource_type == "azurerm_subnet":
            return self._build_subnet_id(
                tf_resource_type,
                resource_config,
                subscription_id,
                original_id_map,
                source_subscription_id,
            )

        logger.warning(
            str(f"Child resource type not yet implemented: {tf_resource_type}")
        )
        return None

    def _build_subnet_id(
        self,
        tf_resource_type: str,
        resource_config: Dict[str, Any],
        subscription_id: str,
        original_id_map: Optional[Dict[str, str]] = None,
        source_subscription_id: Optional[str] = None,
    ) -> Optional[str]:
        """Build subnet ID with Bug #10 fix.

        Bug #10 Fix: Tries to use original_id from Neo4j first (if available in original_id_map).
        Falls back to config-based construction only if:
        1. No original_id_map provided, OR
        2. Resource not found in map, AND
        3. Config values are valid (not Terraform variables)

        Subnets are child resources of Virtual Networks with this structure:
        /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Network/virtualNetworks/{vnet}/subnets/{subnet}

        Impact: 266 resources

        Args:
            tf_resource_type: Terraform resource type ("azurerm_subnet")
            resource_config: Subnet configuration dict
            subscription_id: Azure subscription ID (target subscription for cross-tenant)
            original_id_map: Optional map of original Azure IDs
            source_subscription_id: Optional source subscription for cross-tenant

        Returns:
            Azure subnet resource ID or None if cannot be constructed
        """
        resource_name = resource_config.get("name")
        vnet_name = resource_config.get("virtual_network_name")
        resource_group = resource_config.get("resource_group_name")

        # Bug #10 Fix: Try original_id first (from Neo4j)
        if original_id_map and resource_name:
            # DEBUG: Log what we're working with
            logger.info(f"🔍 DEBUG _build_subnet_id for '{resource_name}':")
            logger.info(str(f"  subscription_id (target): {subscription_id}"))
            logger.info(str(f"  source_subscription_id: {source_subscription_id}"))
            logger.info(str(f"  original_id_map size: {len(original_id_map)}"))

            # Search for this subnet in the original_id_map by matching subnet name in Azure ID
            for tf_name, original_id in original_id_map.items():
                if (
                    tf_name.startswith(f"{tf_resource_type}.")
                    and "/subnets/" in original_id
                ):
                    # Extract subnet name from Azure ID: .../subnets/{subnet_name}
                    id_subnet_name = original_id.split("/subnets/")[-1]
                    if id_subnet_name == resource_name:
                        logger.info(
                            f"  ✓ Found original_id for subnet '{resource_name}': {original_id}"
                        )

                        # Cross-tenant translation if needed
                        if (
                            source_subscription_id
                            and source_subscription_id != subscription_id
                        ):
                            logger.info(
                                f"  🔄 TRANSLATING: {source_subscription_id[:8]}... -> {subscription_id[:8]}..."
                            )
                            original_id = self._translate_subscription_in_id(
                                original_id, source_subscription_id, subscription_id
                            )
                            logger.info(str(f"  ✅ Translated ID: {original_id}"))
                        else:
                            logger.info(
                                f"  ⚠️ NO TRANSLATION: source={source_subscription_id}, target={subscription_id}"
                            )

                        return original_id

        # Fallback: Build from config (if config is valid)
        if not all([resource_name, vnet_name, resource_group]):
            logger.warning(
                f"Subnet missing required fields: "
                f"name={resource_name}, vnet={vnet_name}, rg={resource_group}"
            )
            return None

        # Check if vnet_name contains Terraform variable
        if self._is_terraform_variable(vnet_name):
            logger.debug(
                f"Cannot build subnet ID: vnet_name contains Terraform variable: {vnet_name}"
            )
            return None

        # Config is valid - build ID
        return (
            f"/subscriptions/{subscription_id}/"
            f"resourceGroups/{resource_group}/"
            f"providers/Microsoft.Network/virtualNetworks/{vnet_name}/"
            f"subnets/{resource_name}"
        )

    def _build_subscription_level_id(
        self,
        tf_resource_type: str,
        resource_config: Dict[str, Any],
        subscription_id: str,
        original_id_map: Optional[Dict[str, str]] = None,
        source_subscription_id: Optional[str] = None,
    ) -> Optional[str]:
        """Build resource ID for subscription-level resources.

        Subscription-level resources are not scoped to resource groups.
        Phase 1 implementation focuses on role assignments only.

        Args:
            tf_resource_type: Terraform resource type
            resource_config: Resource configuration dict
            subscription_id: Azure subscription ID

        Returns:
            Azure resource ID or None if cannot be constructed
        """
        # Dispatch to specific subscription-level resource builders
        if tf_resource_type == "azurerm_role_assignment":
            return self._build_role_assignment_id(resource_config, subscription_id)

        logger.warning(
            f"Subscription-level resource type not yet implemented: {tf_resource_type}"
        )
        return None

    def _build_role_assignment_id(
        self,
        resource_config: Dict[str, Any],
        subscription_id: str,
    ) -> Optional[str]:
        """Build role assignment ID based on scope.

        Role assignments can be scoped to:
        - Subscription: /subscriptions/{sub}/providers/Microsoft.Authorization/roleAssignments/{name}
        - Resource Group: /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Authorization/roleAssignments/{name}
        - Resource: /{resource_id}/providers/Microsoft.Authorization/roleAssignments/{name}

        Impact: 1,017 resources

        Args:
            resource_config: Role assignment configuration dict
            subscription_id: Azure subscription ID

        Returns:
            Azure role assignment resource ID or None if cannot be constructed
        """
        name = resource_config.get("name")
        scope = resource_config.get("scope", "").strip()  # Trim whitespace

        if not name:
            logger.warning("Role assignment missing 'name' field")
            return None

        # Check if explicit scope is provided and valid
        if scope:
            # Validate scope is a proper Azure resource ID format
            if not scope.startswith("/"):
                logger.warning(
                    f"Role assignment has invalid scope format (must start with '/'): {scope}"
                )
                return None

            # Scope is valid - use it
            role_assignment_id = (
                f"{scope}/providers/Microsoft.Authorization/roleAssignments/{name}"
            )
            logger.debug(
                f"Role assignment scope source: explicit scope "
                f"(scope={scope[:50]}...)"  # Log first 50 chars to avoid huge logs
            )
            return role_assignment_id

        # Try resource group scope (no explicit scope provided)
        resource_group = resource_config.get("resource_group_name", "").strip()
        if resource_group:
            role_assignment_id = (
                f"/subscriptions/{subscription_id}/"
                f"resourceGroups/{resource_group}/"
                f"providers/Microsoft.Authorization/roleAssignments/{name}"
            )
            logger.debug(
                f"Role assignment scope source: resource group "
                f"(rg={resource_group}, sub={subscription_id[:8]}...)"
            )
            return role_assignment_id

        # Default to subscription scope (no scope, no resource group)
        role_assignment_id = (
            f"/subscriptions/{subscription_id}/"
            f"providers/Microsoft.Authorization/roleAssignments/{name}"
        )
        logger.debug(
            f"Role assignment scope source: subscription scope "
            f"(sub={subscription_id[:8]}...)"
        )
        return role_assignment_id

    def _build_association_id(
        self,
        tf_resource_type: str,
        resource_config: Dict[str, Any],
        subscription_id: str,
        original_id_map: Optional[Dict[str, str]] = None,
        source_subscription_id: Optional[str] = None,
    ) -> Optional[str]:
        """Build resource ID for association resources.

        IMPORTANT: Association resources are synthetic Terraform constructs that link
        two existing resources together. They are NOT standalone Azure resources and
        therefore CANNOT be imported.

        The resource_config contains Terraform interpolations (e.g.,
        "${azurerm_subnet.subnet_1.id}"), not Azure resource IDs. These interpolations
        are only resolved at Terraform apply time.

        Impact: 86 association resources (subnet-NSG + NIC-NSG)
        Decision: Return None to skip import blocks for all association types

        Args:
            tf_resource_type: Terraform resource type
            resource_config: Resource configuration dict (contains Terraform interpolations)
            subscription_id: Azure subscription ID (unused)

        Returns:
            None (associations cannot be imported, they must be created)
        """
        # Association resources are relationships, not importable resources
        # The config contains Terraform interpolations like "${azurerm_subnet.name.id}"
        # which cannot be used to construct Azure import IDs

        if tf_resource_type in [
            "azurerm_subnet_network_security_group_association",
            "azurerm_network_interface_security_group_association",
        ]:
            logger.debug(
                f"Skipping import block for association resource type: {tf_resource_type} "
                f"(associations are synthetic Terraform constructs, not importable Azure resources)"
            )
            return None

        logger.warning(str(f"Unknown association resource type: {tf_resource_type}"))
        return None
