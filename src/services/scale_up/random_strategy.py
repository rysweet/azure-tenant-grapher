"""
Random resource generation strategy for scale-up operations.

This module implements random resource and relationship generation based on
type distributions and density constraints. Useful for stress testing and
generating large synthetic datasets.

Philosophy:
- Self-contained strategy module
- Configurable distributions and constraints
- Reproducible with seed parameter
- Zero-BS: Full working implementation

Public API:
    generate_random_resources: Create resources by type distribution
    generate_random_relationships: Create relationships by density
"""

import logging
import random
from datetime import datetime
from typing import Callable, Dict, Optional

from src.services.scale_up import common
from src.utils.session_manager import Neo4jSessionManager
from src.utils.synthetic_id import generate_synthetic_id

logger = logging.getLogger(__name__)


async def generate_random_resources(
    session_manager: Neo4jSessionManager,
    tenant_id: str,
    operation_id: str,
    target_count: int,
    distribution: Dict[str, float],
    batch_size: int,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
    progress_start: int = 0,
    progress_end: int = 100,
) -> int:
    """
    Generate random resources based on type distribution.

    Args:
        session_manager: Neo4j session manager
        tenant_id: Azure tenant ID
        operation_id: Scale operation ID
        target_count: Number of resources to create
        distribution: Resource type to probability mapping
        batch_size: Batch size for insertions
        progress_callback: Optional progress callback
        progress_start: Progress start percentage
        progress_end: Progress end percentage

    Returns:
        Number of resources created

    Example:
        >>> created = await generate_random_resources(
        ...     session_manager,
        ...     "abc123",
        ...     "scale-op-1",
        ...     1000,
        ...     {
        ...         "Microsoft.Compute/virtualMachines": 0.4,
        ...         "Microsoft.Network/virtualNetworks": 0.3,
        ...         "Microsoft.Storage/storageAccounts": 0.3
        ...     },
        ...     500
        ... )
    """
    # Normalize distribution
    total_prob = sum(distribution.values())
    normalized = {k: v / total_prob for k, v in distribution.items()}

    generation_timestamp = datetime.now().isoformat()
    resources = []

    for i in range(target_count):
        # Select resource type based on distribution
        rand_val = random.random()
        cumulative = 0.0
        selected_type = next(iter(normalized.keys()))  # Default

        for resource_type, prob in normalized.items():
            cumulative += prob
            if rand_val <= cumulative:
                selected_type = resource_type
                break

        resource_id = generate_synthetic_id(selected_type)
        resource = {
            "id": resource_id,
            "type": selected_type,
            "props": {
                "id": resource_id,
                "name": f"random-{i + 1}",
                "type": selected_type,
                "tenant_id": tenant_id,
                "synthetic": True,
                "scale_operation_id": operation_id,
                "generation_strategy": "random",
                "generation_timestamp": generation_timestamp,
            },
        }
        resources.append(resource)

    # Insert in batches
    created_count = 0
    for i in range(0, len(resources), batch_size):
        batch = resources[i : i + batch_size]
        await common.insert_resource_batch(session_manager, batch)
        created_count += len(batch)

        if progress_callback:
            progress = progress_start + int(
                ((i + len(batch)) / len(resources)) * (progress_end - progress_start)
            )
            progress_callback(
                f"Created {created_count}/{target_count} resources...",
                progress,
                100,
            )

    return created_count


async def generate_random_relationships(
    session_manager: Neo4jSessionManager,
    tenant_id: str,
    operation_id: str,
    density: float,
    batch_size: int,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
    progress_start: int = 0,
    progress_end: int = 100,
) -> int:
    """
    Generate random relationships between synthetic resources.

    Args:
        session_manager: Neo4j session manager
        tenant_id: Azure tenant ID
        operation_id: Scale operation ID
        density: Relationship density (0.0-1.0)
        batch_size: Batch size for insertions
        progress_callback: Optional progress callback
        progress_start: Progress start percentage
        progress_end: Progress end percentage

    Returns:
        Number of relationships created

    Example:
        >>> created = await generate_random_relationships(
        ...     session_manager,
        ...     "abc123",
        ...     "scale-op-1",
        ...     0.3,
        ...     500
        ... )
    """
    # Get all synthetic resources for this operation
    query = """
    MATCH (r:Resource)
    WHERE NOT r:Original
      AND r.scale_operation_id = $operation_id
      AND r.synthetic = true
    RETURN r.id as id, r.type as type
    """

    resource_ids = []
    with session_manager.session() as session:
        result = session.run(query, {"operation_id": operation_id})
        resource_ids = [record["id"] for record in result]

    if len(resource_ids) < 2:
        return 0

    # Calculate number of relationships to create
    max_relationships = len(resource_ids) * (len(resource_ids) - 1)
    target_relationships = int(max_relationships * density)

    relationships = []
    relationship_types = ["CONNECTED_TO", "DEPENDS_ON", "CONTAINS"]

    for _ in range(target_relationships):
        source_id = random.choice(resource_ids)
        target_id = random.choice(resource_ids)

        if source_id != target_id:
            rel_type = random.choice(relationship_types)
            relationships.append(
                {
                    "source_id": source_id,
                    "target_id": target_id,
                    "rel_type": rel_type,
                    "rel_props": {},
                }
            )

    # Insert in batches
    created_count = 0
    for i in range(0, len(relationships), batch_size):
        batch = relationships[i : i + batch_size]
        await common.insert_relationship_batch(session_manager, batch)
        created_count += len(batch)

        if progress_callback:
            progress = progress_start + int(
                ((i + len(batch)) / len(relationships))
                * (progress_end - progress_start)
            )
            progress_callback(
                f"Created {created_count} relationships...", progress, 100
            )

    return created_count


__all__ = [
    "generate_random_relationships",
    "generate_random_resources",
]
