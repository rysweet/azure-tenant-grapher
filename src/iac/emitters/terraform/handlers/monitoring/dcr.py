"""Data Collection Rule handler for Terraform emission.

Handles: Microsoft.Insights/dataCollectionRules
Emits: azurerm_monitor_data_collection_rule
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class DataCollectionRuleHandler(ResourceHandler):
    """Handler for Monitor Data Collection Rules.

    Emits:
        - azurerm_monitor_data_collection_rule
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Insights/dataCollectionRules",
        "microsoft.insights/dataCollectionRules",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_monitor_data_collection_rule",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Data Collection Rule to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        config = self.build_base_config(resource)

        # Extract destinations
        destinations_prop = properties.get("destinations", {})
        destinations_config = {}

        # Log Analytics destinations
        if "logAnalytics" in destinations_prop:
            log_analytics_list = []
            for la_dest in destinations_prop["logAnalytics"]:
                workspace_resource_id = la_dest.get("workspaceResourceId", "")
                dest_name = la_dest.get("name", "default")
                if workspace_resource_id:
                    # Normalize resource ID casing
                    workspace_resource_id = self._normalize_resource_id(
                        workspace_resource_id
                    )

                    # Check if workspace exists in graph
                    if not self._workspace_exists_in_graph(
                        workspace_resource_id, context
                    ):
                        logger.warning(
                            f"DCR '{resource_name}' references non-existent "
                            f"Log Analytics workspace: {workspace_resource_id}. "
                            f"Skipping this DCR."
                        )
                        return None

                    log_analytics_list.append(
                        {
                            "workspace_resource_id": workspace_resource_id,
                            "name": dest_name,
                        }
                    )

            if log_analytics_list:
                destinations_config["log_analytics"] = log_analytics_list

        # Azure Monitor Metrics destinations
        if "azureMonitorMetrics" in destinations_prop:
            am_dest = destinations_prop["azureMonitorMetrics"]
            dest_name = am_dest.get("name", "azureMonitorMetrics-default")
            destinations_config["azure_monitor_metrics"] = {"name": dest_name}

        # Skip DCRs without destinations
        if not destinations_config:
            logger.warning(
                f"DCR '{resource_name}' has no destinations. "
                f"Skipping as it cannot be deployed."
            )
            return None

        config["destinations"] = destinations_config

        # Extract data flows
        data_flows_prop = properties.get("dataFlows", [])
        data_flows_config = []

        for flow in data_flows_prop:
            flow_config = {
                "streams": flow.get("streams", ["Microsoft-Perf"]),
                "destinations": flow.get("destinations", ["default"]),
            }
            if "outputStream" in flow:
                flow_config["output_stream"] = flow["outputStream"]
            if "transformKql" in flow:
                flow_config["transform_kql"] = flow["transformKql"]
            data_flows_config.append(flow_config)

        # Skip DCRs without data flows
        if not data_flows_config:
            logger.warning(
                f"DCR '{resource_name}' has no dataFlows. "
                f"Skipping as it cannot be deployed."
            )
            return None

        config["data_flow"] = data_flows_config

        logger.debug(f"Data Collection Rule '{resource_name}' emitted")

        return "azurerm_monitor_data_collection_rule", safe_name, config

    def _normalize_resource_id(self, resource_id: str) -> str:
        """Normalize resource ID casing."""
        # Fix common provider casing issues
        normalizations = [
            ("microsoft.operationalinsights", "Microsoft.OperationalInsights"),
            ("microsoft.insights", "Microsoft.Insights"),
        ]
        for old, new in normalizations:
            if old in resource_id.lower():
                import re

                resource_id = re.sub(old, new, resource_id, flags=re.IGNORECASE)
        return resource_id

    def _workspace_exists_in_graph(
        self,
        workspace_id: str,
        context: EmitterContext,
    ) -> bool:
        """Check if workspace exists in the graph."""
        if not context.graph:
            return True  # Assume exists if no graph reference

        # Extract workspace name from ID
        workspace_name = self.extract_name_from_id(workspace_id, "workspaces")
        if workspace_name == "unknown":
            return True  # Can't validate, assume exists

        workspace_safe = self.sanitize_name(workspace_name)
        return context.resource_exists(
            "azurerm_log_analytics_workspace", workspace_safe
        )
