"""Network Watcher handler for Terraform emission.

Handles: Microsoft.Network/networkWatchers
Emits: azurerm_network_watcher

Network Watchers are automatically created by Azure (one per region) in the
NetworkWatcherRG resource group. They should always be marked for import,
never created new.
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class NetworkWatcherHandler(ResourceHandler):
    """Handler for Azure Network Watchers.

    Network Watchers are regional resources that Azure creates automatically
    to support network monitoring and diagnostics. They are typically found
    in the NetworkWatcherRG resource group and should be imported rather
    than created.

    Emits:
        - azurerm_network_watcher
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Network/networkWatchers",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_network_watcher",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Network Watcher to Terraform configuration.

        Args:
            resource: Azure resource dictionary from graph
            context: Shared emitter context

        Returns:
            Tuple of (terraform_type, resource_name, config) or None if skipped
        """
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)

        # Build base configuration (name, location, resource_group_name)
        config = self.build_base_config(resource)

        logger.debug(
            f"Network Watcher '{resource_name}' emitted for region {config.get('location')}"
        )

        return "azurerm_network_watcher", safe_name, config
