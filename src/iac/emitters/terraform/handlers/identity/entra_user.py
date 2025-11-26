"""Entra ID User handler for Terraform emission.

Handles: User, Microsoft.AAD/User, Microsoft.Graph/users
Emits: azuread_user
"""

import logging
import re
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class EntraUserHandler(ResourceHandler):
    """Handler for Entra ID (Azure AD) Users.

    Emits:
        - azuread_user
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "User",
        "Microsoft.AAD/User",
        "Microsoft.Graph/users",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azuread_user",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Entra ID user to Terraform configuration."""
        resource_name = resource.get("name", "unknown")

        # Get UPN with sanitization
        raw_upn = resource.get("userPrincipalName") or resource.get("name", "unknown")
        upn = self._sanitize_upn(raw_upn)

        safe_name = self.sanitize_name(resource_name)

        display_name = (
            resource.get("displayName") or resource.get("display_name") or upn
        )
        mail_nickname = (
            resource.get("mailNickname")
            or resource.get("mail_nickname")
            or upn.split("@")[0]
        )

        config = {
            "user_principal_name": upn,
            "display_name": display_name,
            "mail_nickname": mail_nickname,
            "password": f"var.azuread_user_password_{safe_name}",
            "force_password_change": True,
        }

        # Optional properties
        if resource.get("accountEnabled") is not None:
            config["account_enabled"] = resource.get("accountEnabled")

        logger.debug(f"Entra ID User '{upn}' emitted")

        return "azuread_user", safe_name, config

    @staticmethod
    def _sanitize_upn(upn: str) -> str:
        """Sanitize user principal name.

        Bug #32 fix: Remove spaces and normalize UPN.
        """
        upn = upn.strip()
        upn = re.sub(r"\s+", " ", upn)
        upn = upn.replace(" ", "_")
        return upn
