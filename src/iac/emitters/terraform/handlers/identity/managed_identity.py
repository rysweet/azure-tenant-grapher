"""Managed Identity handler for Terraform emission.

Handles: Microsoft.ManagedIdentity/userAssignedIdentities
Emits: azurerm_user_assigned_identity
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class ManagedIdentityHandler(ResourceHandler):
    """Handler for User Assigned Managed Identities.

    Emits:
        - azurerm_user_assigned_identity
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.ManagedIdentity/userAssignedIdentities",
        "Microsoft.ManagedIdentity/managedIdentities",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_user_assigned_identity",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Managed Identity to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)

        config = self.build_base_config(resource)

        logger.debug(f"Managed Identity '{resource_name}' emitted")

        return "azurerm_user_assigned_identity", safe_name, config
