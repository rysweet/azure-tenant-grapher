"""DevTest Schedule handler for Terraform emission.

Handles: Microsoft.DevTestLab/schedules
Emits: azurerm_dev_test_schedule
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class DevTestScheduleHandler(ResourceHandler):
    """Handler for DevTest Lab Schedules.

    Emits:
        - azurerm_dev_test_schedule
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.DevTestLab/schedules",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_dev_test_schedule",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert DevTest Schedule to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        properties = self.parse_properties(resource)

        # Extract lab and schedule names
        full_name = resource_name
        parts = full_name.split("/")
        if len(parts) >= 3:
            lab_name = parts[0]
            schedule_name = parts[2]
        else:
            lab_name = "unknown-lab"
            schedule_name = full_name

        safe_name = self.sanitize_name(schedule_name)

        config = self.build_base_config(resource)
        config["name"] = schedule_name

        # Schedule properties
        task_type = properties.get("taskType", "LabVmsShutdownTask")
        time_zone_id = properties.get("timeZoneId", "UTC")
        daily_recurrence_time = properties.get("dailyRecurrence", {}).get(
            "time", "1900"
        )

        config.update(
            {
                "lab_name": lab_name,
                "task_type": task_type,
                "time_zone_id": time_zone_id,
                "daily_recurrence": {"time": daily_recurrence_time},
                "notification_settings": {
                    "time_in_minutes": properties.get("notificationSettings", {}).get(
                        "timeInMinutes", 30
                    ),
                },
            }
        )

        logger.debug(f"DevTest Schedule '{schedule_name}' emitted for lab '{lab_name}'")

        return "azurerm_dev_test_schedule", safe_name, config
