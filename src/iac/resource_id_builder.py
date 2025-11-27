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
- Association Resources: NSG associations (86 resources)

Expected Impact: +1,369 import blocks (from 228 → 1,597)

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
            AzureResourceIdPattern, Callable[[str, Dict[str, Any], str], Optional[str]]
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
    ) -> Optional[str]:
        """Build Azure resource ID from Terraform resource config.

        Main entry point for ID construction. Detects pattern and dispatches to
        appropriate builder method.

        Args:
            tf_resource_type: Terraform resource type (e.g., "azurerm_storage_account")
            resource_config: Terraform resource configuration dict
            subscription_id: Azure subscription ID

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
            return builder_method(tf_resource_type, resource_config, subscription_id)
        except Exception as e:
            logger.warning(
                f"Failed to build resource ID for {tf_resource_type}: {e}",
                exc_info=True,
            )
            return None

    def _build_resource_group_level_id(
        self,
        tf_resource_type: str,
        resource_config: Dict[str, Any],
        subscription_id: str,
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
    ) -> Optional[str]:
        """Build resource ID for child resources nested under parents.

        Child resources are nested under parent resources in Azure's hierarchy.
        Phase 1 implementation focuses on subnets only.

        Args:
            tf_resource_type: Terraform resource type
            resource_config: Resource configuration dict
            subscription_id: Azure subscription ID

        Returns:
            Azure resource ID or None if cannot be constructed
        """
        # Dispatch to specific child resource builders
        if tf_resource_type == "azurerm_subnet":
            return self._build_subnet_id(resource_config, subscription_id)

        logger.warning(f"Child resource type not yet implemented: {tf_resource_type}")
        return None

    def _build_subnet_id(
        self,
        resource_config: Dict[str, Any],
        subscription_id: str,
    ) -> Optional[str]:
        """Build subnet ID.

        Subnets are child resources of Virtual Networks with this structure:
        /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Network/virtualNetworks/{vnet}/subnets/{subnet}

        Impact: 266 resources

        Args:
            resource_config: Subnet configuration dict
            subscription_id: Azure subscription ID

        Returns:
            Azure subnet resource ID or None if cannot be constructed
        """
        resource_name = resource_config.get("name")
        vnet_name = resource_config.get("virtual_network_name")
        resource_group = resource_config.get("resource_group_name")

        if not all([resource_name, vnet_name, resource_group]):
            logger.warning(
                f"Subnet missing required fields: "
                f"name={resource_name}, vnet={vnet_name}, rg={resource_group}"
            )
            return None

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
        scope = resource_config.get("scope", "")

        if not name:
            logger.warning("Role assignment missing 'name' field")
            return None

        # If scope provided, use it
        if scope and scope.startswith("/"):
            return f"{scope}/providers/Microsoft.Authorization/roleAssignments/{name}"

        # Try resource group scope
        resource_group = resource_config.get("resource_group_name")
        if resource_group:
            return (
                f"/subscriptions/{subscription_id}/"
                f"resourceGroups/{resource_group}/"
                f"providers/Microsoft.Authorization/roleAssignments/{name}"
            )

        # Default to subscription scope
        return (
            f"/subscriptions/{subscription_id}/"
            f"providers/Microsoft.Authorization/roleAssignments/{name}"
        )

    def _build_association_id(
        self,
        tf_resource_type: str,
        resource_config: Dict[str, Any],
        subscription_id: str,
    ) -> Optional[str]:
        """Build resource ID for association resources.

        Association resources link two other resources together.
        They use compound IDs with pipe separator: {resource1_id}|{resource2_id}

        Impact: 86 resources (subnet-NSG + NIC-NSG associations)

        Args:
            tf_resource_type: Terraform resource type
            resource_config: Resource configuration dict
            subscription_id: Azure subscription ID (unused for associations)

        Returns:
            Azure association resource ID or None if cannot be constructed
        """
        if tf_resource_type == "azurerm_subnet_network_security_group_association":
            subnet_id = resource_config.get("subnet_id", "")
            nsg_id = resource_config.get("network_security_group_id", "")

            if not subnet_id or not nsg_id:
                logger.warning(
                    f"Subnet NSG association missing IDs: "
                    f"subnet_id={bool(subnet_id)}, nsg_id={bool(nsg_id)}"
                )
                return None

            # These should already be full Azure resource IDs
            return f"{subnet_id}|{nsg_id}"

        elif tf_resource_type == "azurerm_network_interface_security_group_association":
            nic_id = resource_config.get("network_interface_id", "")
            nsg_id = resource_config.get("network_security_group_id", "")

            if not nic_id or not nsg_id:
                logger.warning(
                    f"NIC NSG association missing IDs: "
                    f"nic_id={bool(nic_id)}, nsg_id={bool(nsg_id)}"
                )
                return None

            return f"{nic_id}|{nsg_id}"

        logger.warning(
            f"Association resource type not yet implemented: {tf_resource_type}"
        )
        return None
