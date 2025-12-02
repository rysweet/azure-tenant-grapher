"""
Layer Validation and Comparison Operations Module

This module handles validation and comparison operations for layers.
Extracted from layer_management_service.py as part of modular refactoring.

Philosophy:
- Single responsibility: Validation and comparison only
- Thread-safe via Neo4j transactions
- Clear error handling
- Standard library only (no external dependencies beyond Neo4j)

Public API (the "studs"):
    LayerValidationOperations: Class handling validation and comparison for layers
"""

import logging
from datetime import datetime
from typing import Optional

from src.services.layer.models import (
    LayerDiff,
    LayerMetadata,
    LayerNotFoundError,
    LayerValidationReport,
)
from src.utils.session_manager import Neo4jSessionManager

logger = logging.getLogger(__name__)


class LayerValidationOperations:
    """
    Handles validation and comparison operations for layers.

    Responsibilities:
    - Validate layer integrity
    - Compare layers to find differences
    - Fix validation issues when requested

    Thread Safety: All methods are thread-safe via Neo4j transactions
    """

    def __init__(
        self,
        session_manager: Neo4jSessionManager,
        crud_operations: Optional[object] = None,
        stats_operations: Optional[object] = None,
    ):
        """
        Initialize validation operations handler.

        Args:
            session_manager: Neo4j session manager for database operations
            crud_operations: CRUD operations handler for getting layer metadata
            stats_operations: Stats operations handler for refreshing stats
        """
        self.session_manager = session_manager
        self.crud_operations = crud_operations
        self.stats_operations = stats_operations
        self.logger = logging.getLogger(__name__)

    async def compare_layers(
        self,
        layer_a_id: str,
        layer_b_id: str,
        detailed: bool = False,
        include_properties: bool = False,
    ) -> LayerDiff:
        """
        Compare two layers to find differences.

        Args:
            layer_a_id: Baseline layer
            layer_b_id: Comparison layer
            detailed: Include node IDs in results
            include_properties: Compare property values

        Returns:
            LayerDiff object with statistics

        Raises:
            LayerNotFoundError: If either layer doesn't exist
        """
        # Validate both layers exist
        if self.crud_operations:
            layer_a = await self.crud_operations.get_layer(layer_a_id)
            layer_b = await self.crud_operations.get_layer(layer_b_id)

            if not layer_a:
                raise LayerNotFoundError(layer_a_id)
            if not layer_b:
                raise LayerNotFoundError(layer_b_id)

        with self.session_manager.session() as session:
            # Count nodes in each layer
            nodes_a_result = session.run(
                """
                MATCH (r:Resource)
                WHERE NOT r:Original AND r.layer_id = $layer_id
                RETURN collect(r.id) as ids, count(r) as count
                """,
                {"layer_id": layer_a_id},
            )
            nodes_a_record = nodes_a_result.single()
            nodes_a_ids = set(nodes_a_record["ids"])
            nodes_a_count = nodes_a_record["count"]

            nodes_b_result = session.run(
                """
                MATCH (r:Resource)
                WHERE NOT r:Original AND r.layer_id = $layer_id
                RETURN collect(r.id) as ids, count(r) as count
                """,
                {"layer_id": layer_b_id},
            )
            nodes_b_record = nodes_b_result.single()
            nodes_b_ids = set(nodes_b_record["ids"])
            nodes_b_count = nodes_b_record["count"]

            # Calculate differences
            added_ids = nodes_b_ids - nodes_a_ids
            removed_ids = nodes_a_ids - nodes_b_ids
            common_ids = nodes_a_ids & nodes_b_ids

            # Count relationships
            rels_a = session.run(
                """
                MATCH (r1:Resource)-[rel]->(r2:Resource)
                WHERE NOT r1:Original AND NOT r2:Original
                  AND r1.layer_id = $layer_id
                  AND r2.layer_id = $layer_id
                  AND type(rel) <> 'SCAN_SOURCE_NODE'
                RETURN count(rel) as count
                """,
                {"layer_id": layer_a_id},
            ).single()["count"]

            rels_b = session.run(
                """
                MATCH (r1:Resource)-[rel]->(r2:Resource)
                WHERE NOT r1:Original AND NOT r2:Original
                  AND r1.layer_id = $layer_id
                  AND r2.layer_id = $layer_id
                  AND type(rel) <> 'SCAN_SOURCE_NODE'
                RETURN count(rel) as count
                """,
                {"layer_id": layer_b_id},
            ).single()["count"]

        # Calculate change percentage
        total_nodes = max(nodes_a_count, nodes_b_count)
        total_changes = len(added_ids) + len(removed_ids)
        change_percentage = (
            (total_changes / total_nodes * 100) if total_nodes > 0 else 0.0
        )

        return LayerDiff(
            layer_a_id=layer_a_id,
            layer_b_id=layer_b_id,
            compared_at=datetime.utcnow(),
            nodes_added=len(added_ids),
            nodes_removed=len(removed_ids),
            nodes_modified=0,  # Would need property comparison
            nodes_unchanged=len(common_ids),
            relationships_added=max(0, rels_b - rels_a),
            relationships_removed=max(0, rels_a - rels_b),
            relationships_modified=0,
            relationships_unchanged=min(rels_a, rels_b),
            added_node_ids=list(added_ids) if detailed else [],
            removed_node_ids=list(removed_ids) if detailed else [],
            total_changes=total_changes,
            change_percentage=change_percentage,
        )

    async def validate_layer_integrity(
        self, layer_id: str, fix_issues: bool = False
    ) -> LayerValidationReport:
        """
        Validate layer integrity and optionally fix issues.

        Args:
            layer_id: Layer to validate
            fix_issues: Attempt automatic fixes

        Returns:
            LayerValidationReport with findings

        Raises:
            LayerNotFoundError: If layer doesn't exist
        """
        # Check if layer exists
        layer = None
        if self.crud_operations:
            layer = await self.crud_operations.get_layer(layer_id)
            if not layer:
                raise LayerNotFoundError(layer_id)

        report = LayerValidationReport(
            layer_id=layer_id,
            validated_at=datetime.utcnow(),
            is_valid=True,
        )

        with self.session_manager.session() as session:
            # Check 1: All Resource nodes have SCAN_SOURCE_NODE links
            missing_scan_source = session.run(
                """
                MATCH (r:Resource)
                WHERE NOT r:Original AND r.layer_id = $layer_id
                  AND NOT (r)-[:SCAN_SOURCE_NODE]->()
                RETURN count(r) as count
                """,
                {"layer_id": layer_id},
            ).single()["count"]

            if missing_scan_source > 0:
                report.add_error(
                    "MISSING_SCAN_SOURCE",
                    f"{missing_scan_source} nodes missing SCAN_SOURCE_NODE",
                    {"count": missing_scan_source},
                )
                report.missing_scan_source_nodes = missing_scan_source

            # Check 2: No cross-layer relationships
            cross_layer_rels = session.run(
                """
                MATCH (r1:Resource)-[rel]->(r2:Resource)
                WHERE NOT r1:Original AND NOT r2:Original
                  AND r1.layer_id = $layer_id
                  AND r2.layer_id <> $layer_id
                  AND type(rel) <> 'SCAN_SOURCE_NODE'
                RETURN count(rel) as count
                """,
                {"layer_id": layer_id},
            ).single()["count"]

            if cross_layer_rels > 0:
                report.add_error(
                    "CROSS_LAYER_RELS",
                    f"{cross_layer_rels} cross-layer relationships found",
                    {"count": cross_layer_rels},
                )
                report.cross_layer_relationships = cross_layer_rels

                if fix_issues:
                    # Delete cross-layer relationships
                    session.run(
                        """
                        MATCH (r1:Resource)-[rel]->(r2:Resource)
                        WHERE NOT r1:Original AND NOT r2:Original
                          AND r1.layer_id = $layer_id
                          AND r2.layer_id <> $layer_id
                          AND type(rel) <> 'SCAN_SOURCE_NODE'
                        DELETE rel
                        """,
                        {"layer_id": layer_id},
                    )
                    report.add_warning(
                        "CROSS_LAYER_RELS_FIXED",
                        f"Deleted {cross_layer_rels} cross-layer relationships",
                    )

            # Check 3: Node count matches metadata (only if we have layer metadata)
            if layer:
                actual_node_count = session.run(
                    """
                    MATCH (r:Resource)
                    WHERE NOT r:Original AND r.layer_id = $layer_id
                    RETURN count(r) as count
                    """,
                    {"layer_id": layer_id},
                ).single()["count"]

                if actual_node_count != layer.node_count:
                    report.add_warning(
                        "NODE_COUNT_MISMATCH",
                        f"Metadata says {layer.node_count}, actual is {actual_node_count}",
                        {"expected": layer.node_count, "actual": actual_node_count},
                    )

                    if fix_issues and self.stats_operations:
                        await self.stats_operations.refresh_layer_stats(layer_id)
                        report.add_warning("NODE_COUNT_FIXED", "Updated metadata counts")

            # Mark passed checks
            if not report.issues:
                report.checks_passed = 3
            else:
                report.checks_passed = 3 - len(report.issues)

        return report


__all__ = ["LayerValidationOperations"]
