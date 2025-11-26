"""Entra ID Group handler for Terraform emission.

Handles: Group, Microsoft.AAD/Group, Microsoft.Graph/groups
Emits: azuread_group
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class EntraGroupHandler(ResourceHandler):
    """Handler for Entra ID (Azure AD) Groups.

    Emits:
        - azuread_group
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Group",
        "Microsoft.AAD/Group",
        "Microsoft.Graph/groups",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azuread_group",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Entra ID group to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)

        display_name = (
            resource.get("displayName") or resource.get("display_name") or resource_name
        )
        mail_enabled = resource.get("mailEnabled", False)
        security_enabled = resource.get("securityEnabled", True)

        config = {
            "display_name": display_name,
            "mail_enabled": mail_enabled,
            "security_enabled": security_enabled,
        }

        # Add description if present
        if resource.get("description"):
            config["description"] = resource.get("description")

        logger.debug(f"Entra ID Group '{display_name}' emitted")

        return "azuread_group", safe_name, config
