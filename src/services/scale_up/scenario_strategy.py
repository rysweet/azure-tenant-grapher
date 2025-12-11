"""
Scenario-based topology generation strategy for scale-up operations.

This module implements generation of realistic Azure topology patterns including
hub-spoke networks, multi-region deployments, and environment-based resource grouping.

Supported Scenarios:
- Hub-Spoke: Central hub VNet with multiple spoke VNets and resources
- Multi-Region: Resources distributed across Azure regions
- Dev-Test-Prod: Environment-based resource organization

Philosophy:
- Self-contained strategy module
- Realistic topology patterns
- Configurable parameters per scenario
- Zero-BS: Full working implementation

Public API:
    generate_hub_spoke: Create hub-spoke network topology
    generate_multi_region: Create multi-region deployment
    generate_dev_test_prod: Create dev/test/prod environments
"""

import logging
from datetime import datetime
from typing import Any, Callable, Dict, Optional, Tuple

from src.services.scale_up import common
from src.utils.session_manager import Neo4jSessionManager
from src.utils.synthetic_id import generate_synthetic_id

logger = logging.getLogger(__name__)


async def generate_hub_spoke(
    session_manager: Neo4jSessionManager,
    tenant_id: str,
    operation_id: str,
    params: Dict[str, Any],
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
) -> Tuple[int, int]:
    """
    Generate hub-spoke network topology.

    Creates a central hub VNet with multiple spoke VNets, each containing
    the specified number of resources. Hub and spokes are connected via
    CONNECTED_TO relationships representing VNet peering.

    Args:
        session_manager: Neo4j session manager
        tenant_id: Azure tenant ID
        operation_id: Scale operation ID
        params: Parameters including:
            - spoke_count: Number of spoke VNets (default: 3)
            - resources_per_spoke: Resources per spoke (default: 10)
        progress_callback: Optional progress callback

    Returns:
        Tuple of (resources_created, relationships_created)

    Example:
        >>> resources, relationships = await generate_hub_spoke(
        ...     session_manager,
        ...     "abc123",
        ...     "scale-op-1",
        ...     {"spoke_count": 5, "resources_per_spoke": 10}
        ... )
    """
    spoke_count = params.get("spoke_count", 3)
    resources_per_spoke = params.get("resources_per_spoke", 10)

    generation_timestamp = datetime.now().isoformat()
    resources_created = 0
    relationships_created = 0

    # Create hub VNet
    hub_id = generate_synthetic_id("Microsoft.Network/virtualNetworks")
    hub = {
        "id": hub_id,
        "type": "Microsoft.Network/virtualNetworks",
        "props": {
            "id": hub_id,
            "name": "hub-vnet",
            "type": "Microsoft.Network/virtualNetworks",
            "tenant_id": tenant_id,
            "synthetic": True,
            "scale_operation_id": operation_id,
            "generation_strategy": "scenario",
            "generation_timestamp": generation_timestamp,
            "scenario_name": "hub-spoke",
            "role": "hub",
        },
    }
    await common.insert_resource_batch(session_manager, [hub])
    resources_created += 1

    # Create spokes and connect to hub
    spoke_resources = []
    for i in range(spoke_count):
        spoke_id = generate_synthetic_id("Microsoft.Network/virtualNetworks")
        spoke = {
            "id": spoke_id,
            "type": "Microsoft.Network/virtualNetworks",
            "props": {
                "id": spoke_id,
                "name": f"spoke-{i + 1}-vnet",
                "type": "Microsoft.Network/virtualNetworks",
                "tenant_id": tenant_id,
                "synthetic": True,
                "scale_operation_id": operation_id,
                "generation_strategy": "scenario",
                "generation_timestamp": generation_timestamp,
                "scenario_name": "hub-spoke",
                "role": "spoke",
                "spoke_index": i,
            },
        }
        spoke_resources.append(spoke)

        # Add resources to spoke
        for j in range(resources_per_spoke):
            resource_id = generate_synthetic_id("Microsoft.Compute/virtualMachines")
            resource = {
                "id": resource_id,
                "type": "Microsoft.Compute/virtualMachines",
                "props": {
                    "id": resource_id,
                    "name": f"spoke-{i + 1}-vm-{j + 1}",
                    "type": "Microsoft.Compute/virtualMachines",
                    "tenant_id": tenant_id,
                    "synthetic": True,
                    "scale_operation_id": operation_id,
                    "generation_strategy": "scenario",
                    "generation_timestamp": generation_timestamp,
                    "scenario_name": "hub-spoke",
                    "spoke_index": i,
                },
            }
            spoke_resources.append(resource)

    await common.insert_resource_batch(session_manager, spoke_resources)
    resources_created += len(spoke_resources)

    # Create hub-spoke relationships
    hub_spoke_rels = []
    for spoke in spoke_resources:
        if spoke["type"] == "Microsoft.Network/virtualNetworks":
            hub_spoke_rels.append(
                {
                    "source_id": hub_id,
                    "target_id": spoke["id"],
                    "rel_type": "CONNECTED_TO",
                    "rel_props": {"connection_type": "peering"},
                }
            )

    await common.insert_relationship_batch(session_manager, hub_spoke_rels)
    relationships_created += len(hub_spoke_rels)

    return resources_created, relationships_created


async def generate_multi_region(
    session_manager: Neo4jSessionManager,
    tenant_id: str,
    operation_id: str,
    params: Dict[str, Any],
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
) -> Tuple[int, int]:
    """
    Generate multi-region deployment topology.

    Creates resources distributed across multiple Azure regions, each
    with the specified number of resources.

    Args:
        session_manager: Neo4j session manager
        tenant_id: Azure tenant ID
        operation_id: Scale operation ID
        params: Parameters including:
            - region_count: Number of regions (default: 3, max: 5)
            - resources_per_region: Resources per region (default: 20)
        progress_callback: Optional progress callback

    Returns:
        Tuple of (resources_created, relationships_created)

    Example:
        >>> resources, relationships = await generate_multi_region(
        ...     session_manager,
        ...     "abc123",
        ...     "scale-op-1",
        ...     {"region_count": 3, "resources_per_region": 20}
        ... )
    """
    region_count = params.get("region_count", 3)
    resources_per_region = params.get("resources_per_region", 20)
    regions = ["eastus", "westus", "centralus", "northeurope", "westeurope"]

    generation_timestamp = datetime.now().isoformat()
    resources_created = 0
    relationships_created = 0

    all_resources = []
    for i in range(min(region_count, len(regions))):
        region = regions[i]

        for j in range(resources_per_region):
            resource_id = generate_synthetic_id("Microsoft.Compute/virtualMachines")
            resource = {
                "id": resource_id,
                "type": "Microsoft.Compute/virtualMachines",
                "props": {
                    "id": resource_id,
                    "name": f"{region}-vm-{j + 1}",
                    "type": "Microsoft.Compute/virtualMachines",
                    "location": region,
                    "tenant_id": tenant_id,
                    "synthetic": True,
                    "scale_operation_id": operation_id,
                    "generation_strategy": "scenario",
                    "generation_timestamp": generation_timestamp,
                    "scenario_name": "multi-region",
                    "region": region,
                },
            }
            all_resources.append(resource)

    await common.insert_resource_batch(session_manager, all_resources)
    resources_created += len(all_resources)

    return resources_created, relationships_created


async def generate_dev_test_prod(
    session_manager: Neo4jSessionManager,
    tenant_id: str,
    operation_id: str,
    params: Dict[str, Any],
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
) -> Tuple[int, int]:
    """
    Generate dev/test/prod environment topology.

    Creates resources organized by environment (dev, test, prod), each with
    the specified number of resources.

    Args:
        session_manager: Neo4j session manager
        tenant_id: Azure tenant ID
        operation_id: Scale operation ID
        params: Parameters including:
            - resources_per_env: Resources per environment (default: 15)
        progress_callback: Optional progress callback

    Returns:
        Tuple of (resources_created, relationships_created)

    Example:
        >>> resources, relationships = await generate_dev_test_prod(
        ...     session_manager,
        ...     "abc123",
        ...     "scale-op-1",
        ...     {"resources_per_env": 15}
        ... )
    """
    resources_per_env = params.get("resources_per_env", 15)
    environments = ["dev", "test", "prod"]

    generation_timestamp = datetime.now().isoformat()
    resources_created = 0
    relationships_created = 0

    all_resources = []
    for env in environments:
        for j in range(resources_per_env):
            resource_id = generate_synthetic_id("Microsoft.Compute/virtualMachines")
            resource = {
                "id": resource_id,
                "type": "Microsoft.Compute/virtualMachines",
                "props": {
                    "id": resource_id,
                    "name": f"{env}-vm-{j + 1}",
                    "type": "Microsoft.Compute/virtualMachines",
                    "tenant_id": tenant_id,
                    "synthetic": True,
                    "scale_operation_id": operation_id,
                    "generation_strategy": "scenario",
                    "generation_timestamp": generation_timestamp,
                    "scenario_name": "dev-test-prod",
                    "environment": env,
                },
            }
            all_resources.append(resource)

    await common.insert_resource_batch(session_manager, all_resources)
    resources_created += len(all_resources)

    return resources_created, relationships_created


__all__ = [
    "generate_dev_test_prod",
    "generate_hub_spoke",
    "generate_multi_region",
]
