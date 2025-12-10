"""
Layer Statistics Operations Module

This module handles statistics and metrics operations for layers.
Extracted from layer_management_service.py as part of modular refactoring.

Philosophy:
- Single responsibility: Statistics and metrics only
- Thread-safe via Neo4j transactions
- Clear error handling
- Standard library only (no external dependencies beyond Neo4j)

Public API (the "studs"):
    LayerStatsOperations: Class handling statistics operations for layers
"""

import logging
from typing import Optional

from src.services.layer.models import LayerMetadata, LayerNotFoundError
from src.utils.session_manager import Neo4jSessionManager

logger = logging.getLogger(__name__)


class LayerStatsOperations:
    """
    Handles statistics and metrics operations for layers.

    Responsibilities:
    - Refresh layer statistics (node counts, relationship counts)
    - Calculate layer metrics
    - Update metadata with computed statistics

    Thread Safety: All methods are thread-safe via Neo4j transactions
    """

    def __init__(
        self,
        session_manager: Neo4jSessionManager,
        crud_operations: Optional[object] = None,
    ):
        """
        Initialize statistics operations handler.

        Args:
            session_manager: Neo4j session manager for database operations
            crud_operations: CRUD operations handler for getting layer metadata
        """
        self.session_manager = session_manager
        self.crud_operations = crud_operations
        self.logger = logging.getLogger(__name__)

    async def refresh_layer_stats(self, layer_id: str) -> LayerMetadata:
        """
        Recalculate node_count and relationship_count.

        Args:
            layer_id: Layer to refresh

        Returns:
            Updated LayerMetadata

        Raises:
            LayerNotFoundError: If layer doesn't exist
        """
        # Check if layer exists
        if self.crud_operations:
            layer = await self.crud_operations.get_layer(layer_id)
            if not layer:
                raise LayerNotFoundError(layer_id)

        with self.session_manager.session() as session:
            # Count nodes
            node_count = session.run(
                """
                MATCH (r:Resource)
                WHERE NOT r:Original AND r.layer_id = $layer_id
                RETURN count(r) as count
                """,
                {"layer_id": layer_id},
            ).single()["count"]

            # Count relationships
            rel_count = session.run(
                """
                MATCH (r1:Resource)-[rel]->(r2:Resource)
                WHERE NOT r1:Original AND NOT r2:Original
                  AND r1.layer_id = $layer_id
                  AND r2.layer_id = $layer_id
                  AND type(rel) <> 'SCAN_SOURCE_NODE'
                RETURN count(rel) as count
                """,
                {"layer_id": layer_id},
            ).single()["count"]

            # Update layer metadata
            session.run(
                """
                MATCH (l:Layer {layer_id: $layer_id})
                SET l.node_count = $node_count,
                    l.relationship_count = $rel_count,
                    l.updated_at = datetime()
                """,
                {
                    "layer_id": layer_id,
                    "node_count": node_count,
                    "rel_count": rel_count,
                },
            )

        self.logger.info(
            f"Refreshed stats for layer {layer_id}: {node_count} nodes, {rel_count} relationships"
        )

        # Return updated metadata if crud_operations available
        if self.crud_operations:
            return await self.crud_operations.get_layer(layer_id)

        # Otherwise create a minimal LayerMetadata with just the stats
        from datetime import datetime

        return LayerMetadata(
            layer_id=layer_id,
            name="",
            description="",
            created_at=datetime.utcnow(),
            node_count=node_count,
            relationship_count=rel_count,
        )


__all__ = ["LayerStatsOperations"]
