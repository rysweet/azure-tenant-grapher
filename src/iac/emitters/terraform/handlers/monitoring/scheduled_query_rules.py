"""Scheduled Query Rules Alert handler for Terraform emission.

Handles: Microsoft.Insights/scheduledQueryRules
Emits: azurerm_monitor_scheduled_query_rules_alert_v2
"""

import logging
import re
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)

# Security: Maximum query length to prevent DoS attacks
MAX_QUERY_LENGTH = 10000


@handler
class ScheduledQueryRulesHandler(ResourceHandler):
    """Handler for Azure Monitor Scheduled Query Rules Alerts.

    Emits:
        - azurerm_monitor_scheduled_query_rules_alert_v2

    Note: Uses tenant suffix pattern for cross-tenant deployments (follows redis.py).
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Insights/scheduledQueryRules",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_monitor_scheduled_query_rules_alert_v2",
    }

    @staticmethod
    def _sanitize_for_logging(value: str) -> str:
        """Sanitize string for safe logging by removing control characters.

        Prevents log injection attacks where malicious resource names could
        inject fake log entries via newlines or ANSI escape codes.
        """
        if not isinstance(value, str):
            return str(value)
        # Remove control characters (0x00-0x1f, 0x7f-0x9f)
        return re.sub(r"[\x00-\x1f\x7f-\x9f]", "", value)

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Scheduled Query Rules Alert to Terraform configuration."""
        resource_name = resource.get("name")
        if not resource_name:
            logger.warning("Scheduled Query Rules Alert missing name, skipping")
            return None

        if not resource.get("location"):
            logger.warning(
                f"Scheduled Query Rules Alert '{self._sanitize_for_logging(resource_name)}' missing required location, skipping"
            )
            return None

        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)
        config = self.build_base_config(resource)

        # Alert name with tenant suffix for cross-tenant deployments
        # Follow redis.py pattern exactly
        abstracted_name = config["name"]

        # Add tenant-specific suffix for cross-tenant deployments
        if (
            context.target_tenant_id
            and context.source_tenant_id != context.target_tenant_id
        ):
            # Add target tenant suffix (last 6 chars of tenant ID, alphanumeric only)
            tenant_suffix = context.target_tenant_id[-6:].replace("-", "").lower()

            # Name already sanitized by ID Abstraction Service - just truncate if needed
            # Truncate to fit (253 - 7 = 246 chars for abstracted name + dash)
            if len(abstracted_name) > 246:
                abstracted_name = abstracted_name[:246]

            config["name"] = f"{abstracted_name}-{tenant_suffix}"
            logger.info(
                f"Cross-tenant deployment: Scheduled Query Rules Alert '{self._sanitize_for_logging(abstracted_name)}' → '{self._sanitize_for_logging(config['name'])}' (tenant suffix: {tenant_suffix})"
            )
        else:
            config["name"] = abstracted_name

        # Map simple properties
        simple_mappings = {
            "enabled": "enabled",
            "description": "description",
            "severity": "severity",
            "evaluationFrequency": "evaluation_frequency",
            "windowSize": "window_duration",
        }
        for azure_key, tf_key in simple_mappings.items():
            if azure_key in properties:
                config[tf_key] = properties[azure_key]

        # Scopes (required)
        scopes = properties.get("scopes", [])
        if not scopes:
            logger.warning(
                f"Scheduled Query Rules Alert '{self._sanitize_for_logging(resource_name)}' has empty scopes, skipping"
            )
            return None

        config["scopes"] = self._translate_subscription_ids(
            scopes, context.get_effective_subscription_id()
        )

        # Criteria (required)
        criteria_data = properties.get("criteria", {})
        if not criteria_data:
            logger.warning(
                f"Scheduled Query Rules Alert '{self._sanitize_for_logging(resource_name)}' missing criteria, skipping"
            )
            return None

        all_of = criteria_data.get("allOf", [])
        if not all_of:
            logger.warning(
                f"Scheduled Query Rules Alert '{self._sanitize_for_logging(resource_name)}' has empty criteria, skipping"
            )
            return None

        criteria = []
        for criterion in all_of:
            criterion_config = self._map_criterion_fields(criterion)
            criteria.append(criterion_config)

        config["criteria"] = criteria

        # Actions (optional)
        actions = properties.get("actions", {})
        if actions:
            action_groups = actions.get("actionGroups", [])
            action_config = {
                "action_groups": self._translate_subscription_ids(
                    action_groups, context.get_effective_subscription_id()
                )
            }

            if custom_props := actions.get("customProperties"):
                action_config["custom_properties"] = custom_props

            config["action"] = action_config

        # Optional properties
        optional_mappings = {
            "autoMitigate": "auto_mitigation_enabled",
            "skipQueryValidation": "skip_query_validation",
            "muteActionsDuration": "mute_actions_after_alert_duration",
        }
        for azure_key, tf_key in optional_mappings.items():
            if azure_key in properties:
                config[tf_key] = properties[azure_key]

        # Identity (optional)
        if identity := resource.get("identity"):
            if identity_type := identity.get("type"):
                config["identity"] = {"type": identity_type}

        logger.debug(
            f"Scheduled Query Rules Alert '{self._sanitize_for_logging(resource_name)}' emitted"
        )

        return "azurerm_monitor_scheduled_query_rules_alert_v2", safe_name, config

    def _translate_subscription_ids(
        self, resource_ids: list[str], target_sub_id: str
    ) -> list[str]:
        """Translate subscription IDs in resource IDs for cross-subscription deployment."""
        translated = []
        for resource_id in resource_ids:
            if "/subscriptions/" not in resource_id:
                translated.append(resource_id)
                continue

            parts = resource_id.split("/subscriptions/", 1)
            if len(parts) < 2:
                translated.append(resource_id)
                continue

            rest_parts = parts[1].split("/", 1)
            if len(rest_parts) > 1:
                translated.append(f"/subscriptions/{target_sub_id}/{rest_parts[1]}")
            else:
                translated.append(resource_id)

        return translated

    def _map_criterion_fields(self, criterion: Dict[str, Any]) -> Dict[str, Any]:
        """Map Azure criterion fields to Terraform format."""
        criterion_mappings = {
            "query": "query",
            "timeAggregation": "time_aggregation_method",
            "metricMeasureColumn": "metric_measure_column",
            "operator": "operator",
            "threshold": "threshold",
        }

        config = {
            tf_key: criterion[azure_key]
            for azure_key, tf_key in criterion_mappings.items()
            if azure_key in criterion
        }

        # Security: Validate query length to prevent DoS attacks
        if "query" in config and len(str(config["query"])) > MAX_QUERY_LENGTH:
            logger.warning(
                f"KQL query exceeds maximum length ({MAX_QUERY_LENGTH} chars): {len(config['query'])} chars. Skipping criterion."
            )
            return {}

        # Failing periods (optional nested structure)
        if failing_periods := criterion.get("failingPeriods"):
            failing_config = {
                "number_of_evaluation_periods": failing_periods.get(
                    "numberOfEvaluationPeriods"
                ),
                "min_failing_periods_to_alert": failing_periods.get(
                    "minFailingPeriodsToAlert"
                ),
            }
            # Only include if we have actual values
            if any(v is not None for v in failing_config.values()):
                config["failing_periods"] = {
                    k: v for k, v in failing_config.items() if v is not None
                }

        return config
