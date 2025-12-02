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
                    criteria_config.append(
                        {
                            "metric_namespace": criterion.get("metricNamespace", ""),
                            "metric_name": criterion.get("metricName", ""),
                            "aggregation": criterion.get("timeAggregation", "Average"),
                            "operator": criterion.get("operator", "GreaterThan"),
                            "threshold": criterion.get("threshold", 0),
                        }
                    )
                if criteria_config:
                    config["criteria"] = criteria_config

        logger.debug(f"Metric Alert '{resource_name}' emitted")

        return "azurerm_monitor_metric_alert", safe_name, config
