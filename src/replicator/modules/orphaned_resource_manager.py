"""
Orphaned Resource Manager Brick

Brick for finding and analyzing orphaned resource types (not covered by detected patterns).

Philosophy:
- Single Responsibility: Orphaned resource discovery and analysis
- Self-contained: Clear public contracts with injected dependencies
- Regeneratable: Stateless operations
- Zero-BS: All functions work, no stubs
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ...architecture_replication_constants import (
    MAX_INSTANCES_PER_STANDALONE_TYPE,
    STANDALONE_ORPHANED_BUDGET_FRACTION,
)

if TYPE_CHECKING:
    from neo4j import Session

    from ...architectural_pattern_analyzer import ArchitecturalPatternAnalyzer

logger = logging.getLogger(__name__)


class OrphanedResourceManager:
    """
    Manages orphaned resource types (not covered by detected patterns).

    This brick provides methods for:
    - Finding instances containing orphaned resource types
    - Analyzing orphaned node coverage
    - Suggesting improvements for orphaned resources

    Dependencies (injected):
        - analyzer: ArchitecturalPatternAnalyzer for type resolution

    Public Contract:
        - find_orphaned_instances(session, detected_patterns, ...) -> list[tuple]
        - analyze_orphaned_nodes(source_graph, target_graph, ...) -> dict
    """

    def __init__(self, analyzer: ArchitecturalPatternAnalyzer):
        """
        Initialize with injected dependencies.

        Args:
            analyzer: ArchitecturalPatternAnalyzer for resource type resolution
        """
        self.analyzer = analyzer

    def find_orphaned_instances(
        self,
        session: Session,
        detected_patterns: dict[str, dict[str, Any]],
        source_resource_type_counts: dict[str, int],
    ) -> list[tuple[str, list[dict[str, Any]]]]:
        """
        Find instances that contain orphaned node resource types.

        Orphaned nodes are resource types not covered by any detected pattern.
        This method finds actual resource instances containing these types,
        including both ResourceGroup-based and standalone resources.

        Args:
            session: Neo4j session for queries
            detected_patterns: All detected architectural patterns
            source_resource_type_counts: Resource type counts in source tenant

        Returns:
            List of (pseudo_pattern_name, instance) tuples for orphaned resources

        Examples:
            >>> manager = OrphanedResourceManager(analyzer)
            >>> orphaned = manager.find_orphaned_instances(
            ...     session,
            ...     detected_patterns={...},
            ...     source_resource_type_counts={"keyVaults": 5, "virtualMachines": 10}
            ... )
            >>> len(orphaned)
            7  # 5 RG-based + 2 standalone instances
        """
        orphaned_instances = []

        # Step 1: Query Neo4j for ALL resource types (full names)
        type_query = """
        MATCH (r:Resource:Original)
        RETURN DISTINCT r.type as full_type
        """
        type_result = session.run(type_query)
        all_full_types = [record["full_type"] for record in type_result]

        logger.info(
            f"[DEBUG] Found {len(all_full_types)} distinct resource types in Neo4j"
        )
        logger.info(
            f"[DEBUG] First 10 full types from Neo4j: {sorted(all_full_types)[:10]}"
        )

        # Step 2: Build mapping from simplified to full names
        simplified_to_full = {}
        for full_type in all_full_types:
            simplified = self.analyzer._get_resource_type_name(["Resource"], full_type)
            if simplified not in simplified_to_full:
                simplified_to_full[simplified] = []
            simplified_to_full[simplified].append(full_type)

        logger.info(
            f"[DEBUG] Built mapping for {len(simplified_to_full)} simplified types"
        )

        # Step 3: Get pattern types (simplified names)
        pattern_types_simplified = set()
        for pattern_info in detected_patterns.values():
            pattern_types_simplified.update(pattern_info["matched_resources"])

        logger.info(
            f"[DEBUG] Pattern types (simplified): {len(pattern_types_simplified)}"
        )
        logger.info(
            f"[DEBUG] First 10 pattern types: {sorted(pattern_types_simplified)[:10]}"
        )

        # Step 4: Compute orphaned types (simplified)
        orphaned_types_simplified = (
            set(source_resource_type_counts.keys()) - pattern_types_simplified
        )

        if not orphaned_types_simplified:
            logger.info("No orphaned resource types found in source graph")
            return []

        logger.info(
            f"[DEBUG] Orphaned types (simplified): {len(orphaned_types_simplified)}"
        )
        logger.info(
            f"[DEBUG] First 10 orphaned types: {sorted(orphaned_types_simplified)[:10]}"
        )

        # Step 5: Map orphaned simplified types to full names
        full_orphaned_types = []
        unmapped_types = []
        for simplified in orphaned_types_simplified:
            if simplified in simplified_to_full:
                full_orphaned_types.extend(simplified_to_full[simplified])
            else:
                unmapped_types.append(simplified)

        if unmapped_types:
            logger.info(
                f"[DEBUG] {len(unmapped_types)} orphaned types not in Neo4j (organizational/identity types): {sorted(unmapped_types)[:10]}"
            )

        if not full_orphaned_types:
            logger.info(
                "No orphaned types found in Neo4j (all simplified names unmapped)"
            )
            return []

        logger.info(f"[DEBUG] Mapped to {len(full_orphaned_types)} full orphaned types")
        logger.info(
            f"[DEBUG] First 10 full orphaned types: {sorted(full_orphaned_types)[:10]}"
        )

        # Step 6: Query Neo4j for ResourceGroup-based orphaned resources
        query = """
        MATCH (rg:ResourceGroup)-[:CONTAINS]->(r:Resource:Original)
        WHERE r.type IN $orphaned_types
        RETURN rg.id as rg_id,
               collect({id: r.id, type: r.type, name: r.name}) as resources
        """

        result = session.run(query, orphaned_types=full_orphaned_types)
        result_list = list(result)
        logger.info(f"[DEBUG] Query returned {len(result_list)} ResourceGroups")

        for record in result_list:
            resources = record["resources"]
            if resources:
                # Simplify resource types
                all_resources_simplified = []
                for r in resources:
                    simplified_type = self.analyzer._get_resource_type_name(
                        ["Resource"], r["type"]
                    )
                    all_resources_simplified.append(
                        {
                            "id": r["id"],
                            "type": simplified_type,
                            "name": r["name"],
                        }
                    )

                # Extract ONLY orphaned type resources
                orphaned_only_resources = [
                    r
                    for r in all_resources_simplified
                    if r["type"] in orphaned_types_simplified
                ]

                if orphaned_only_resources:
                    # Create a pseudo-pattern name for these orphaned instances
                    orphaned_in_instance = {r["type"] for r in orphaned_only_resources}
                    pseudo_pattern_name = (
                        f"Orphaned: {', '.join(sorted(list(orphaned_in_instance)[:3]))}"
                    )

                    orphaned_instances.append(
                        (pseudo_pattern_name, orphaned_only_resources)
                    )

        # Also search for standalone orphaned resources NOT in any ResourceGroup
        rg_instance_count = len(orphaned_instances)
        max_standalone = int(rg_instance_count * STANDALONE_ORPHANED_BUDGET_FRACTION)

        logger.info("=" * 80)
        logger.info("[STANDALONE] Searching for standalone orphaned resources")
        logger.info(
            f"[STANDALONE] Found {rg_instance_count} RG-based orphaned instances, "
            f"budget for standalone: {max_standalone}"
        )

        if max_standalone > 0:
            # Find standalone resources not in any ResourceGroup
            query_standalone = """
            MATCH (r:Resource:Original)
            WHERE r.type IN $orphaned_types
            AND NOT (r)<-[:CONTAINS]-(:ResourceGroup)
            RETURN r.id as id,
                   r.type as type,
                   r.name as name
            ORDER BY r.type
            """

            standalone_result = session.run(
                query_standalone, orphaned_types=list(full_orphaned_types)
            )

            # Track coverage to prioritize diverse types
            standalone_type_counts = {}
            standalone_added = 0

            for record in standalone_result:
                if standalone_added >= max_standalone:
                    break

                simplified_type = self.analyzer._get_resource_type_name(
                    ["Resource"], record["type"]
                )

                if simplified_type not in orphaned_types_simplified:
                    continue

                # Prioritize types we haven't seen yet
                type_count = standalone_type_counts.get(simplified_type, 0)

                if type_count < MAX_INSTANCES_PER_STANDALONE_TYPE:
                    singleton_instance = [
                        {
                            "id": record["id"],
                            "type": simplified_type,
                            "name": record["name"],
                        }
                    ]

                    pseudo_pattern_name = f"Orphaned (standalone): {simplified_type}"
                    orphaned_instances.append((pseudo_pattern_name, singleton_instance))

                    standalone_type_counts[simplified_type] = type_count + 1
                    standalone_added += 1

            logger.info(
                f"[STANDALONE] Added {standalone_added} standalone instances covering "
                f"{len(standalone_type_counts)} unique types"
            )

            if standalone_added > 0:
                logger.info(
                    f"[STANDALONE] Standalone types: {', '.join(sorted(standalone_type_counts.keys()))}"
                )
        else:
            logger.info(
                "[STANDALONE] Skipping standalone search (no RG-based instances found)"
            )

        logger.info(
            f"Found {len(orphaned_instances)} total orphaned instances "
            f"({len([i for i in orphaned_instances if 'standalone' in i[0]])} standalone)"
        )

        return orphaned_instances

    def analyze_orphaned_nodes(
        self,
        source_pattern_graph,
        target_pattern_graph,
        detected_patterns: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Analyze orphaned nodes in source and target graphs.

        Identifies resource types not covered by detected patterns and suggests
        new patterns or instances to improve coverage.

        Args:
            source_pattern_graph: Source pattern graph
            target_pattern_graph: Target pattern graph built from selected instances
            detected_patterns: All detected architectural patterns

        Returns:
            Dictionary with orphaned node analysis including:
            - source_orphaned: Orphaned nodes in source graph
            - target_orphaned: Orphaned nodes in target graph
            - missing_in_target: Nodes in source but not in target
            - suggested_patterns: Pattern suggestions to improve coverage
            - count metrics for each category

        Examples:
            >>> manager = OrphanedResourceManager(analyzer)
            >>> analysis = manager.analyze_orphaned_nodes(
            ...     source_graph,
            ...     target_graph,
            ...     detected_patterns={...}
            ... )
            >>> analysis["source_orphaned_count"]
            5
            >>> analysis["missing_count"]
            2
        """
        if not source_pattern_graph or not detected_patterns:
            raise RuntimeError("Must have source pattern graph and detected patterns")

        # Identify orphaned nodes in source graph
        source_orphaned = self.analyzer.identify_orphaned_nodes(
            source_pattern_graph, detected_patterns
        )

        # For target graph, detect which patterns it has
        target_resource_type_counts = dict(
            target_pattern_graph.nodes(data="count", default=0)
        )
        target_detected_patterns = self.analyzer.detect_patterns(
            target_pattern_graph, target_resource_type_counts
        )

        # Identify orphaned nodes in target graph
        target_orphaned = self.analyzer.identify_orphaned_nodes(
            target_pattern_graph, target_detected_patterns
        )

        # Find nodes that are in source but missing from target
        source_nodes = set(source_pattern_graph.nodes())
        target_nodes = set(target_pattern_graph.nodes())
        missing_in_target = source_nodes - target_nodes

        # Get suggested patterns for source orphaned nodes
        suggested_patterns = self.analyzer.suggest_new_patterns(
            source_orphaned, source_pattern_graph
        )

        logger.info(
            f"Orphaned node analysis: "
            f"{len(source_orphaned)} in source, "
            f"{len(target_orphaned)} in target, "
            f"{len(missing_in_target)} missing in target"
        )

        return {
            "source_orphaned": source_orphaned,
            "target_orphaned": target_orphaned,
            "missing_in_target": list(missing_in_target),
            "suggested_patterns": suggested_patterns,
            "source_orphaned_count": len(source_orphaned),
            "target_orphaned_count": len(target_orphaned),
            "missing_count": len(missing_in_target),
        }


__all__ = ["OrphanedResourceManager"]
