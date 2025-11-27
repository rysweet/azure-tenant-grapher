"""Application Insights Workbooks handler for Terraform emission.

Handles: Microsoft.Insights/workbooks
Emits: azurerm_application_insights_workbook
"""

import json
import logging
import re
import uuid
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class WorkbooksHandler(ResourceHandler):
    """Handler for Application Insights Workbooks.

    Emits:
        - azurerm_application_insights_workbook
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Insights/workbooks",
        "microsoft.insights/workbooks",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_application_insights_workbook",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Application Insights Workbook to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        properties = self.parse_properties(resource)

        config = self.build_base_config(resource)

        # display_name is required (friendly name)
        display_name = properties.get("displayName") or resource_name
        config["display_name"] = display_name

        # data_json is required (workbook definition)
        # The serializedData property contains the workbook JSON
        workbook_data = (
            properties.get("serializedData") or properties.get("template") or {}
        )
        config["data_json"] = (
            json.dumps(workbook_data)
            if workbook_data
            else json.dumps({"version": "Notebook/1.0", "items": []})
        )

        # Name must be a GUID - use the resource ID hash or generate one
        resource_id = resource.get("id", "")
        if not re.match(
            r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$",
            resource_name,
            re.IGNORECASE,
        ):
            # Generate deterministic GUID from resource ID
            name_guid = str(uuid.uuid5(uuid.NAMESPACE_DNS, resource_id))
            logger.info(f"Workbook '{resource_name}' converted to GUID: {name_guid}")
            config["name"] = name_guid
        else:
            config["name"] = resource_name

        logger.debug(f"Application Insights Workbook '{resource_name}' emitted")

        return "azurerm_application_insights_workbook", config["name"], config
