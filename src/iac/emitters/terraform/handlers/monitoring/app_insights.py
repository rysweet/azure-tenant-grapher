"""Application Insights handler for Terraform emission.

Handles: Microsoft.Insights/components
Emits: azurerm_application_insights
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class ApplicationInsightsHandler(ResourceHandler):
    """Handler for Application Insights.

    Emits:
        - azurerm_application_insights
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Insights/components",
        "microsoft.insights/components",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_application_insights",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Application Insights to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        config = self.build_base_config(resource)

        # Application type (required)
        app_type = properties.get("Application_Type", "web")
        config["application_type"] = app_type

        # Workspace ID (for workspace-based App Insights)
        workspace_id = properties.get("WorkspaceResourceId")
        if workspace_id:
            config["workspace_id"] = workspace_id

        # Retention
        retention = properties.get("RetentionInDays")
        if retention:
            config["retention_in_days"] = retention

        logger.debug(f"Application Insights '{resource_name}' emitted")

        return "azurerm_application_insights", safe_name, config
