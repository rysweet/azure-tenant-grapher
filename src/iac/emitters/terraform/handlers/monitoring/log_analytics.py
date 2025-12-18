"""Log Analytics handlers for Terraform emission.

Handles: Microsoft.OperationalInsights/workspaces, solutions, queryPacks
Emits: azurerm_log_analytics_workspace, azurerm_log_analytics_solution
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class LogAnalyticsWorkspaceHandler(ResourceHandler):
    """Handler for Log Analytics Workspaces.

    Emits:
        - azurerm_log_analytics_workspace
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.OperationalInsights/workspaces",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_log_analytics_workspace",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Log Analytics Workspace to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        config = self.build_base_config(resource)

        # SKU - Fix #596: Normalize casing for Terraform
        sku = properties.get("sku", {})
        if sku and "name" in sku:
            sku_name = sku["name"]
            # Terraform requires PascalCase: PerGB2018, PerNode, Premium, Standalone, Standard, etc.
            # Azure returns lowercase: pergb2018, pernode, etc.
            sku_map = {
                "pergb2018": "PerGB2018",
                "pernode": "PerNode",
                "premium": "Premium",
                "standalone": "Standalone",
                "standard": "Standard",
                "capacityreservation": "CapacityReservation",
                "lacluster": "LACluster",
                "unlimited": "Unlimited",
            }
            config["sku"] = sku_map.get(sku_name.lower(), sku_name)

        # Retention
        retention = properties.get("retentionInDays")
        if retention:
            config["retention_in_days"] = retention

        logger.debug(f"Log Analytics Workspace '{resource_name}' emitted")

        return "azurerm_log_analytics_workspace", safe_name, config


@handler
class LogAnalyticsSolutionHandler(ResourceHandler):
    """Handler for Log Analytics Solutions.

    Emits:
        - azurerm_log_analytics_solution
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.OperationsManagement/solutions",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_log_analytics_solution",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Log Analytics Solution to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        config = self.build_base_config(resource)

        # Solution name
        config["solution_name"] = resource_name

        # Workspace resource ID
        workspace_id = properties.get("workspaceResourceId")
        if workspace_id:
            config["workspace_resource_id"] = workspace_id

        # Plan
        plan = properties.get("plan", {})
        if plan:
            config["plan"] = {
                "publisher": plan.get("publisher", "Microsoft"),
                "product": plan.get("product", "OMSGallery"),
            }

        logger.debug(f"Log Analytics Solution '{resource_name}' emitted")

        return "azurerm_log_analytics_solution", safe_name, config


@handler
class LogAnalyticsQueryPackHandler(ResourceHandler):
    """Handler for Log Analytics Query Packs.

    Emits:
        - azurerm_log_analytics_query_pack
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.OperationalInsights/queryPacks",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_log_analytics_query_pack",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Log Analytics Query Pack to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)

        config = self.build_base_config(resource)

        logger.debug(f"Log Analytics Query Pack '{resource_name}' emitted")

        return "azurerm_log_analytics_query_pack", safe_name, config
