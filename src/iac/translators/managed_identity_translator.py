"""
Managed Identity Resource ID Translation for IaC Generation

Translates cross-subscription managed identity resource IDs when generating
IaC for a different target subscription.

For example:
- Source: /subscriptions/SOURCE-SUB/resourceGroups/rg1/providers/Microsoft.ManagedIdentity/userAssignedIdentities/id1
- Target: /subscriptions/TARGET-SUB/resourceGroups/rg1/providers/Microsoft.ManagedIdentity/userAssignedIdentities/id1

This prevents Terraform deployment failures when resources reference managed
identities from a different subscription than the deployment target.

Identity Types Handled:
- User-Assigned Identities: Resource IDs are translated
- System-Assigned Identities: Cannot be translated (resource-specific, auto-created)

Resources that use Managed Identities:
- Virtual Machines (Linux/Windows)
- Virtual Machine Scale Sets
- App Services (Web Apps, Function Apps)
- Azure Kubernetes Service (AKS)
- Container Instances
- Azure Data Factory
- Azure Logic Apps
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from .base_translator import BaseTranslator
from .registry import register_translator

logger = logging.getLogger(__name__)


@register_translator
class ManagedIdentityTranslator(BaseTranslator):
    """
    Translates managed identity resource IDs across subscriptions.

    This translator handles:
    1. User-assigned identity resource ID translation
    2. System-assigned identity documentation (cannot translate)
    3. Validation of identity existence in target subscription

    Key Concepts:
    - System-Assigned: Created automatically; uses Terraform interpolation
    - User-Assigned: Standalone resources; require resource ID translation

    Example Identity Block:
        {
            "identity": {
                "type": "UserAssigned",
                "user_assigned_identity_ids": [
                    "/subscriptions/src-sub/resourceGroups/rg/providers/Microsoft.ManagedIdentity/userAssignedIdentities/id1"
                ]
            }
        }
    """

    @property
    def supported_resource_types(self) -> List[str]:
        """Get list of resource types that use managed identities."""
        return [
            # User-assigned identity resource itself
            "azurerm_user_assigned_identity",
            # Virtual machines
            "azurerm_virtual_machine",
            "azurerm_linux_virtual_machine",
            "azurerm_windows_virtual_machine",
            # VM scale sets
            "azurerm_virtual_machine_scale_set",
            "azurerm_linux_virtual_machine_scale_set",
            "azurerm_windows_virtual_machine_scale_set",
            # App services
            "azurerm_app_service",
            "azurerm_linux_web_app",
            "azurerm_windows_web_app",
            # Function apps
            "azurerm_function_app",
            "azurerm_linux_function_app",
            "azurerm_windows_function_app",
            # Container services
            "azurerm_kubernetes_cluster",
            "azurerm_container_group",
            # Data services
            "azurerm_data_factory",
            # Logic apps
            "azurerm_logic_app_standard",
            "azurerm_logic_app_workflow",
        ]

    def can_translate(self, resource: Dict[str, Any]) -> bool:
        """
        Determine if this resource has managed identity references to translate.

        Args:
            resource: Resource dictionary from Neo4j

        Returns:
            True if resource has identity blocks with cross-subscription references
        """
        resource_type = resource.get("type", "")

        # Check if resource type is supported
        if resource_type not in self.supported_resource_types:
            return False

        # User-assigned identity resource itself
        if resource_type == "azurerm_user_assigned_identity":
            # Check if the identity resource ID needs translation
            resource_id = resource.get("id", "")
            if resource_id and self._is_cross_subscription_reference(resource_id):
                return True
            return False

        # Check for identity block in resource
        identity = resource.get("identity")
        if not identity or not isinstance(identity, dict):
            return False

        # Check for user-assigned identities
        user_assigned_ids = identity.get("user_assigned_identity_ids", [])
        if not user_assigned_ids:
            # Alternative field name
            user_assigned_ids = identity.get("identity_ids", [])

        # Check if any user-assigned identity IDs need translation
        if user_assigned_ids:
            for identity_id in user_assigned_ids:
                if isinstance(
                    identity_id, str
                ) and self._is_cross_subscription_reference(identity_id):
                    return True

        return False

    def translate(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """
        Translate managed identity resource IDs in a resource.

        Args:
            resource: Resource dictionary to translate

        Returns:
            Translated resource dictionary with updated identity references
        """
        # Make a copy to avoid modifying original
        resource = resource.copy()
        resource_type = resource.get("type", "")
        resource_name = resource.get("name", "Unknown")

        logger.debug(
            f"Translating managed identities for {resource_type}: {resource_name}"
        )

        # Handle user-assigned identity resource itself
        if resource_type == "azurerm_user_assigned_identity":
            resource_id = resource.get("id", "")
            if resource_id and self._is_cross_subscription_reference(resource_id):
                translated_id, warnings = self._translate_resource_id(
                    resource_id, "identity.id"
                )
                resource["id"] = translated_id

                self._add_result(
                    property_path="id",
                    original=resource_id,
                    translated=translated_id,
                    warnings=warnings,
                    resource_type=resource_type,
                    resource_name=resource_name,
                )
            return resource

        # Handle identity block in other resources
        identity = resource.get("identity")

        # Defensive type check: ensure identity is a dict
        if not isinstance(identity, dict):
            if identity is not None:
                logger.warning(
                    f"Identity block for {resource_type} '{resource_name}' is not a dict "
                    f"(got {type(identity).__name__}), skipping translation"
                )
            return resource

        if not identity:
            return resource

        # Make a copy of identity block
        identity = identity.copy()
        translated_identity, warnings = self._translate_identity_block(
            identity, resource_type, resource_name
        )

        resource["identity"] = translated_identity

        # Log any warnings about system-assigned identities
        if self._has_system_assigned_identity(identity):
            info_msg = (
                f"{resource_type} '{resource_name}' uses system-assigned managed identity. "
                "System-assigned identities are created automatically and cannot be "
                "pre-translated. Use Terraform interpolation like ${resource.identity[0].principal_id} "
                "to reference the identity after creation."
            )
            logger.info(info_msg)

        return resource

    def _translate_identity_block(
        self, identity: Dict[str, Any], resource_type: str, resource_name: str
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        Translate identity block with user-assigned identity IDs.

        Args:
            identity: Identity block dictionary
            resource_type: Type of parent resource
            resource_name: Name of parent resource

        Returns:
            Tuple of (translated_identity, warnings)
        """
        all_warnings: List[str] = []

        # Defensive type check: ensure identity is a dict (should be handled by caller, but double-check)
        if not isinstance(identity, dict):
            all_warnings.append(
                f"Identity block is not a dict (got {type(identity).__name__}), skipping translation"
            )
            return identity, all_warnings

        # Check for user_assigned_identity_ids field
        user_assigned_ids = identity.get("user_assigned_identity_ids", [])
        if not user_assigned_ids:
            # Try alternative field name
            user_assigned_ids = identity.get("identity_ids", [])
            field_name = "identity_ids"
        else:
            field_name = "user_assigned_identity_ids"

        if not user_assigned_ids:
            return identity, all_warnings

        # Translate each user-assigned identity ID
        translated_ids = []
        for identity_id in user_assigned_ids:
            if not isinstance(identity_id, str):
                translated_ids.append(identity_id)
                continue

            # Skip Terraform variables
            if "${" in identity_id or "var." in identity_id:
                translated_ids.append(identity_id)
                continue

            # Check if translation is needed
            if self._is_cross_subscription_reference(identity_id):
                translated_id, warnings = self._translate_resource_id(
                    identity_id, f"identity.{field_name}"
                )
                translated_ids.append(translated_id)
                all_warnings.extend(warnings)

                self._add_result(
                    property_path=f"identity.{field_name}[]",
                    original=identity_id,
                    translated=translated_id,
                    warnings=warnings,
                    resource_type=resource_type,
                    resource_name=resource_name,
                )
            else:
                translated_ids.append(identity_id)

        # Update identity block with translated IDs
        identity[field_name] = translated_ids

        return identity, all_warnings

    def _has_system_assigned_identity(self, identity: Dict[str, Any]) -> bool:
        """
        Check if identity block includes system-assigned identity.

        Args:
            identity: Identity block dictionary

        Returns:
            True if system-assigned identity is configured
        """
        identity_type = identity.get("type", "").lower()

        return (
            identity_type == "systemassigned"
            or identity_type == "systemassigned, userassigned"
            or identity_type == "userassigned, systemassigned"
        )

    def _azure_type_to_terraform_type(self, azure_type: str) -> Optional[str]:
        """
        Convert Azure resource type to Terraform resource type.

        Extended mapping for managed identity resources.

        Args:
            azure_type: Azure resource type

        Returns:
            Terraform resource type or None
        """
        # Start with base mapping
        base_mapping = super()._azure_type_to_terraform_type(azure_type)
        if base_mapping:
            return base_mapping

        # Add managed identity specific mappings
        identity_type_map = {
            "Microsoft.ManagedIdentity/userAssignedIdentities": "azurerm_user_assigned_identity",
            "Microsoft.ManagedIdentity/managedIdentities": "azurerm_user_assigned_identity",
            # Compute
            "Microsoft.Compute/virtualMachines": "azurerm_linux_virtual_machine",
            "Microsoft.Compute/virtualMachineScaleSets": "azurerm_linux_virtual_machine_scale_set",
            # App Services
            "Microsoft.Web/sites": "azurerm_linux_web_app",
            # Container
            "Microsoft.ContainerInstance/containerGroups": "azurerm_container_group",
            "Microsoft.ContainerService/managedClusters": "azurerm_kubernetes_cluster",
            # Data
            "Microsoft.DataFactory/factories": "azurerm_data_factory",
            # Logic Apps
            "Microsoft.Logic/workflows": "azurerm_logic_app_workflow",
        }

        return identity_type_map.get(azure_type)
