"""AKS handler for Terraform emission.

Handles: Microsoft.ContainerService/managedClusters
Emits: azurerm_kubernetes_cluster
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class AKSHandler(ResourceHandler):
    """Handler for Azure Kubernetes Service clusters.

    Emits:
        - azurerm_kubernetes_cluster
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.ContainerService/managedClusters",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_kubernetes_cluster",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert AKS cluster to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        config = self.build_base_config(resource)

        # DNS prefix
        dns_prefix = properties.get("dnsPrefix", resource_name)
        config["dns_prefix"] = dns_prefix

        # Default node pool (required)
        agent_pool_profiles = properties.get("agentPoolProfiles", [])
        if agent_pool_profiles:
            pool = agent_pool_profiles[0]
            config["default_node_pool"] = {
                "name": pool.get("name", "default"),
                "node_count": pool.get("count", 1),
                "vm_size": pool.get("vmSize", "Standard_DS2_v2"),
            }
        else:
            config["default_node_pool"] = {
                "name": "default",
                "node_count": 1,
                "vm_size": "Standard_DS2_v2",
            }

        # Identity
        config["identity"] = {"type": "SystemAssigned"}

        logger.debug(f"AKS Cluster '{resource_name}' emitted")

        return "azurerm_kubernetes_cluster", safe_name, config
