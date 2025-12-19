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

        # Skip Azure-managed workspaces (auto-created by App Insights, AKS, etc.)
        # These have names starting with "managed-" or "DefaultWorkspace-" or containing system GUIDs
        if resource_name.startswith("managed-") or resource_name.startswith("DefaultWorkspace-"):
            logger.debug(f"Skipping Azure-managed Log Analytics Workspace: {resource_name}")
            return None

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

        # Remove 'name' field - azurerm_log_analytics_solution doesn't support it
        # Solution uses solution_name and workspace_name instead
        if "name" in config:
            del config["name"]

        # Extract solution name and workspace name from resource name
        # Format: "SolutionName(WorkspaceName)" e.g., "SecurityInsights(MyWorkspace)"
        if "(" in resource_name and ")" in resource_name:
            solution_name = resource_name.split("(")[0]
            workspace_name = resource_name.split("(")[1].rstrip(")")
            config["solution_name"] = solution_name
            config["workspace_name"] = workspace_name
        else:
            config["solution_name"] = resource_name
            # Try to extract workspace name from workspace_resource_id
            workspace_id = properties.get("workspaceResourceId", "")
            if workspace_id and "/workspaces/" in workspace_id:
                workspace_name = workspace_id.split("/workspaces/")[-1]
                config["workspace_name"] = workspace_name
            else:
                logger.warning(f"Cannot determine workspace_name for solution '{resource_name}', skipping")
                return None

        # Workspace resource ID
        workspace_id = properties.get("workspaceResourceId")
        if workspace_id:
            config["workspace_resource_id"] = workspace_id

        # Plan - REQUIRED
        plan = properties.get("plan", {})
        if plan:
            plan_config = {
                "publisher": plan.get("publisher", "Microsoft"),
                "product": plan.get("product", f"OMSGallery/{config['solution_name']}"),
            }
            config["plan"] = plan_config
        else:
            # Default plan for common solutions
            config["plan"] = {
                "publisher": "Microsoft",
                "product": f"OMSGallery/{config['solution_name']}",
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
