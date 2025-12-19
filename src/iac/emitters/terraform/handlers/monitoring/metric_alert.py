"""Metric Alert handler for Terraform emission.

Handles: Microsoft.Insights/metricAlerts
Emits: azurerm_monitor_metric_alert
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class MetricAlertHandler(ResourceHandler):
    """Handler for Monitor Metric Alerts.

    Emits:
        - azurerm_monitor_metric_alert
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "microsoft.insights/metricalerts",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_monitor_metric_alert",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Metric Alert to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        config = self.build_base_config(resource)

        # Remove location - metric alerts are global resources and don't support location field
        if "location" in config:
            del config["location"]

        # Scopes (required)
        scopes = properties.get("scopes", [])
        if scopes:
            config["scopes"] = scopes

        # Severity
        severity = properties.get("severity", 3)
        config["severity"] = severity

        # Enabled
        enabled = properties.get("enabled", True)
        config["enabled"] = enabled

        # Criteria
        criteria = properties.get("criteria", {})
        if criteria:
            all_of = criteria.get("allOf", [])
            if all_of:
                criteria_config = []
                for criterion in all_of:
                    # Skip criteria with missing required fields
                    metric_namespace = criterion.get("metricNamespace")
                    metric_name = criterion.get("metricName")
                    if not metric_namespace or not metric_name:
                        logger.warning(
                            f"Skipping metric alert criterion with empty namespace or name: "
                            f"namespace='{metric_namespace}', name='{metric_name}'"
                        )
                        continue

                    criteria_config.append(
                        {
                            "metric_namespace": metric_namespace,
                            "metric_name": metric_name,
                            "aggregation": criterion.get("timeAggregation", "Average"),
                            "operator": criterion.get("operator", "GreaterThan"),
                            "threshold": criterion.get("threshold", 0),
                        }
                    )
                if criteria_config:
                    config["criteria"] = criteria_config
                else:
                    # No valid criteria - cannot create metric alert without criteria
                    logger.warning(f"Metric alert '{resource_name}' has no valid criteria, skipping")
                    return None

        logger.debug(f"Metric Alert '{resource_name}' emitted")

        return "azurerm_monitor_metric_alert", safe_name, config
