"""Diagnostic Settings handler for Terraform emission.

Handles: Microsoft.Insights/diagnosticSettings
Emits: azurerm_monitor_diagnostic_setting
"""

import logging
import re
from typing import Any, ClassVar, Dict, List, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class DiagnosticSettingHandler(ResourceHandler):
    """Handler for Azure Monitor Diagnostic Settings.

    Converts diagnostic settings from Neo4j graph to Terraform
    azurerm_monitor_diagnostic_setting resources.

    Emits:
        - azurerm_monitor_diagnostic_setting
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Insights/diagnosticSettings",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_monitor_diagnostic_setting",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Diagnostic Setting to Terraform configuration.

        Args:
            resource: Neo4j DiagnosticSetting node with properties:
                - id: Full ARM resource ID
                - name: Diagnostic setting name
                - type: "Microsoft.Insights/diagnosticSettings"
                - properties: Configuration dict
            context: Shared emitter context

        Returns:
            Tuple of ("azurerm_monitor_diagnostic_setting", safe_name, config)
            or None if resource should be skipped
        """
        resource_name = resource.get("name", "unknown")
        resource_id = resource.get("id", "")

        # Parse properties
        properties = self.parse_properties(resource)
        if not properties:
            logger.info(f"Skipping Diagnostic Setting '{resource_name}': no properties")
            return None

        # Extract target resource ID from diagnostic setting ARM ID
        target_resource_id = self._extract_target_resource_id(resource_id)
        if not target_resource_id:
            logger.warning(
                f"Cannot extract target resource from Diagnostic Setting ID '{resource_id}'"
            )
            return None

        # Check for at least one destination
        workspace_id = properties.get("workspaceId")
        storage_id = properties.get("storageAccountId")
        eventhub_rule_id = properties.get("eventHubAuthorizationRuleId")

        if not any([workspace_id, storage_id, eventhub_rule_id]):
            logger.info(
                f"Skipping Diagnostic Setting '{resource_name}': no destination configured"
            )
            return None

        # Build Terraform configuration
        safe_name = self.sanitize_name(resource_name)
        config = self.build_base_config(resource)

        # Target resource
        config["target_resource_id"] = target_resource_id

        # Destinations
        if workspace_id:
            config["log_analytics_workspace_id"] = workspace_id
        if storage_id:
            config["storage_account_id"] = storage_id
        if eventhub_rule_id:
            config["eventhub_authorization_rule_id"] = eventhub_rule_id

        # Enabled logs (filter to only enabled)
        logs = properties.get("logs", [])
        enabled_logs = self._process_logs(logs)
        if enabled_logs:
            config["enabled_log"] = enabled_logs

        # Metrics (include all with their enabled state)
        metrics = properties.get("metrics", [])
        processed_metrics = self._process_metrics(metrics)
        if processed_metrics:
            config["metric"] = processed_metrics

        logger.debug(
            f"Diagnostic Setting '{resource_name}' emitted for target '{target_resource_id}'"
        )

        return "azurerm_monitor_diagnostic_setting", safe_name, config

    def _extract_target_resource_id(self, diagnostic_setting_id: str) -> Optional[str]:
        """Extract target resource ID from diagnostic setting ARM ID.

        The diagnostic setting's ARM ID has the format:
        {resource-id}/providers/Microsoft.Insights/diagnosticSettings/{name}

        We need to extract {resource-id}.

        Args:
            diagnostic_setting_id: Full ARM ID of diagnostic setting

        Returns:
            Target resource ID or None if cannot be extracted
        """
        if not diagnostic_setting_id:
            return None

        # Pattern to match the diagnostic settings suffix
        pattern = r"^(.*)/providers/[Mm]icrosoft\.[Ii]nsights/diagnosticSettings/[^/]+$"
        match = re.match(pattern, diagnostic_setting_id)

        if match:
            return match.group(1)

        logger.warning(
            f"Invalid diagnostic setting ARM ID format: '{diagnostic_setting_id}'"
        )
        return None

    def _process_logs(self, logs: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Process log categories, filtering to only enabled logs.

        Azure format: [{"category": "X", "enabled": true, "retentionPolicy": {...}}, ...]
        Terraform format: [{"category": "X"}, ...]

        Args:
            logs: List of log category configurations from Azure

        Returns:
            List of enabled log configurations for Terraform
        """
        enabled_logs = []
        for log in logs:
            if log.get("enabled"):
                category = log.get("category")
                if category:
                    enabled_logs.append({"category": category})

        return enabled_logs

    def _process_metrics(self, metrics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process metric categories, including their enabled state.

        Azure format: [{"category": "X", "enabled": true/false, "retentionPolicy": {...}}, ...]
        Terraform format: [{"category": "X", "enabled": true/false}, ...]

        Args:
            metrics: List of metric configurations from Azure

        Returns:
            List of metric configurations for Terraform
        """
        processed_metrics = []
        for metric in metrics:
            category = metric.get("category")
            enabled = metric.get("enabled", True)
            if category:
                processed_metrics.append({"category": category, "enabled": enabled})

        return processed_metrics
