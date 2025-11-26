"""Service Principal handler for Terraform emission.

Handles: ServicePrincipal, Microsoft.AAD/ServicePrincipal, Microsoft.Graph/servicePrincipals
Emits: azuread_service_principal
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class ServicePrincipalHandler(ResourceHandler):
    """Handler for Entra ID Service Principals.

    Emits:
        - azuread_service_principal
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "ServicePrincipal",
        "Microsoft.AAD/ServicePrincipal",
        "Microsoft.Graph/servicePrincipals",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azuread_service_principal",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Service Principal to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)

        # Bug #43: Try multiple field names for appId
        app_id = (
            resource.get("appId")
            or resource.get("application_id")
            or resource.get("applicationId")
            or resource.get("client_id")
        )

        # Skip if no appId found
        if not app_id:
            logger.warning(
                f"Skipping Service Principal '{resource_name}': No appId found. "
                f"Available keys: {list(resource.keys())}"
            )
            return None

        display_name = (
            resource.get("displayName") or resource.get("display_name") or resource_name
        )

        config = {
            "client_id": app_id,
        }

        # Add display_name as a comment (azuread_service_principal only needs client_id)
        # The actual display_name comes from the linked application

        logger.debug(f"Service Principal '{display_name}' (appId: {app_id}) emitted")

        return "azuread_service_principal", safe_name, config
