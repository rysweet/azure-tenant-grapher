"""DevTest Lab handler for Terraform emission.

Handles: Microsoft.DevTestLab/labs
Emits: azurerm_dev_test_lab
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class DevTestLabHandler(ResourceHandler):
    """Handler for Azure DevTest Labs.

    Emits:
        - azurerm_dev_test_lab
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "microsoft.devtestlab/labs",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_dev_test_lab",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert DevTest Lab to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)

        config = self.build_base_config(resource)

        logger.debug(f"DevTest Lab '{resource_name}' emitted")

        return "azurerm_dev_test_lab", safe_name, config
