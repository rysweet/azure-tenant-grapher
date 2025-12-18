"""Role Assignment handler for Terraform emission.

Handles: Microsoft.Authorization/roleAssignments
Emits: azurerm_role_assignment
"""

import logging
import re
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class RoleAssignmentHandler(ResourceHandler):
    """Handler for Azure Role Assignments.

    Emits:
        - azurerm_role_assignment
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Authorization/roleAssignments",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_role_assignment",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Role Assignment to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        # Get scope and translate subscription ID for cross-tenant deployments
        scope = properties.get("scope", resource.get("scope", ""))

        # Translate subscription IDs in scope
        if context.target_subscription_id and scope:
            # Bug #59: Also replace ABSTRACT_SUBSCRIPTION placeholder
            scope = re.sub(
                r"/subscriptions/([a-f0-9-]+|ABSTRACT_SUBSCRIPTION)(/|$)",
                f"/subscriptions/{context.target_subscription_id}\\2",
                scope,
                flags=re.IGNORECASE,
            )
            logger.debug("Translated role assignment scope for cross-tenant deployment")

        # Translate role definition ID
        role_def_id = properties.get(
            "roleDefinitionId", resource.get("roleDefinitionId", "")
        )
        if context.target_subscription_id and role_def_id:
            role_def_id = re.sub(
                r"/subscriptions/([a-f0-9-]+|ABSTRACT_SUBSCRIPTION)/",
                f"/subscriptions/{context.target_subscription_id}/",
                role_def_id,
                flags=re.IGNORECASE,
            )

        principal_id = properties.get("principalId", resource.get("principalId", ""))

        # Bug #18/#93: Skip role assignments without identity mapping in cross-tenant mode ONLY
        # Detect same-tenant deployment (source and target are the same tenant)
        is_same_tenant = (
            context.source_tenant_id
            and context.target_tenant_id
            and context.source_tenant_id == context.target_tenant_id
        )

        # Bug #NEW: For same-tenant deployment, use original principal ID (not abstracted)
        if is_same_tenant and resource.get("original_properties"):
            import json

            try:
                original_props = json.loads(resource.get("original_properties", "{}"))
                original_principal_id = original_props.get("principalId")
                if original_principal_id and not original_principal_id.startswith(
                    "principal-"
                ):
                    logger.info(
                        f"Using original principal ID for same-tenant: {original_principal_id[:8]}..."
                    )
                    principal_id = original_principal_id
            except Exception as e:
                logger.warning(f"Could not parse original_properties: {e}")

        if (
            context.target_tenant_id
            and not context.identity_mapping
            and not is_same_tenant
        ):
            logger.warning(
                f"Skipping role assignment '{resource_name}' in cross-tenant mode: "
                f"No identity mapping provided. Principal ID '{principal_id}' from source "
                f"tenant cannot be validated in target tenant."
            )
            return None

        # Bug #67: Translate principal_id using identity mapping
        if context.identity_mapping and principal_id:
            principal_type = properties.get("principalType", "Unknown")
            translated_principal = self._translate_principal_id(
                principal_id, principal_type, resource_name, context
            )
            if translated_principal:
                logger.info(
                    f"Translated role assignment principal_id: {principal_id} -> {translated_principal}"
                )
                principal_id = translated_principal
            else:
                logger.warning(
                    f"Skipping role assignment '{resource_name}': "
                    f"Principal ID '{principal_id}' not found in identity mapping"
                )
                return None

        config = {
            "scope": scope,
            "role_definition_id": role_def_id,
            "principal_id": principal_id,
        }

        # Note: Role assignments don't have location

        logger.debug(f"Role Assignment '{resource_name}' emitted")

        return "azurerm_role_assignment", safe_name, config

    def _translate_principal_id(
        self,
        principal_id: str,
        principal_type: str,
        resource_name: str,
        context: EmitterContext,
    ) -> Optional[str]:
        """Translate principal ID using identity mapping.

        Args:
            principal_id: Source principal ID
            principal_type: Type of principal (User, Group, ServicePrincipal)
            resource_name: Resource name for logging
            context: Emitter context with identity mapping

        Returns:
            Translated principal ID or None if not found
        """
        if not context.identity_mapping:
            return None

        mapping = context.identity_mapping

        # Try direct lookup in various mapping keys
        for key in ["users", "groups", "servicePrincipals", "managedIdentities"]:
            if key in mapping:
                mapping_section = mapping[key]
                if principal_id in mapping_section:
                    return mapping_section[principal_id]

        # Try case-insensitive lookup
        for key in mapping:
            if isinstance(mapping[key], dict):
                for src_id, target_id in mapping[key].items():
                    if src_id.lower() == principal_id.lower():
                        return target_id

        return None
