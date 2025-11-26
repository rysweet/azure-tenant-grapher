"""Automation Runbook handler for Terraform emission.

Handles: Microsoft.Automation/automationAccounts/runbooks
Emits: azurerm_automation_runbook
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class AutomationRunbookHandler(ResourceHandler):
    """Handler for Azure Automation Runbooks.

    Emits:
        - azurerm_automation_runbook
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Automation/automationAccounts/runbooks",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_automation_runbook",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Automation Runbook to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        properties = self.parse_properties(resource)

        # Extract automation account name and runbook name
        full_name = resource_name
        if "/" in full_name:
            account_name = full_name.split("/")[0]
            runbook_name = full_name.split("/")[1]
        else:
            account_name = "unknown-account"
            runbook_name = full_name

        safe_name = self.sanitize_name(runbook_name)

        config = self.build_base_config(resource)
        config["name"] = runbook_name

        config.update(
            {
                "automation_account_name": account_name,
                "runbook_type": properties.get("runbookType", "PowerShell"),
                "log_progress": properties.get("logProgress", True),
                "log_verbose": properties.get("logVerbose", False),
            }
        )

        # Content link or content
        publish_content_link = properties.get("publishContentLink", {})
        if publish_content_link and "uri" in publish_content_link:
            config["publish_content_link"] = {"uri": publish_content_link["uri"]}
            if "version" in publish_content_link:
                config["publish_content_link"]["version"] = publish_content_link[
                    "version"
                ]
        else:
            logger.warning(
                f"Runbook '{runbook_name}' has no publishContentLink. "
                "Using placeholder content."
            )
            config["content"] = (
                "# Placeholder runbook content\n"
                "# Original runbook content not available in graph\n"
            )

        logger.debug(f"Automation Runbook '{runbook_name}' emitted")

        return "azurerm_automation_runbook", safe_name, config
