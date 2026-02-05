"""
Orphaned Resource Handler for Architecture-Based Replication.

This module handles detection and management of orphaned resources - resources
that don't match any detected architectural pattern.
"""

import logging
from typing import Any, Dict, List, Set, Tuple

from neo4j import GraphDatabase

from .architecture_replication_constants import (
    ORPHANED_PATTERN_NAME,
    STANDALONE_ORPHANED_BUDGET_FRACTION,
    MAX_INSTANCES_PER_STANDALONE_TYPE,
)

logger = logging.getLogger(__name__)


class OrphanedResourceHandler:
    """
    Handles detection and selection of orphaned resources.
    
    Orphaned resources are resources that don't match any detected architectural
    pattern but should still be included for comprehensive tenant coverage.
    """
    
    def __init__(
        self,
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str,
        analyzer=None,
    ):
        """
        Initialize the orphaned resource handler.
        
        Args:
            neo4j_uri: Neo4j database URI
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
            analyzer: ArchitecturalPatternAnalyzer instance
        """
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.analyzer = analyzer
    
    def find_orphaned_node_instances(
        self,
        detected_patterns: Dict[str, Dict[str, Any]],
        source_resource_type_counts: Dict[str, int],
    ) -> List[Tuple[str, List[Dict[str, Any]]]]:
        """
        Find instances that contain orphaned node resource types.
        
        Orphaned nodes are resource types not covered by any detected pattern.
        This method finds actual resource instances containing these types.
        
        Args:
            detected_patterns: Dict of all detected patterns
            source_resource_type_counts: Dict of resource type counts in source
            
        Returns:
            List of (pseudo_pattern_name, instance) tuples for orphaned resources
        """
        if not self.analyzer:
            raise RuntimeError("Analyzer not set. Cannot find orphaned resources.")
        
        driver = GraphDatabase.driver(
            self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password)
        )
        
        orphaned_instances = []
        
        try:
            with driver.session() as session:
                # Step 1: Query Neo4j for ALL resource types (full names)
                type_query = """
                MATCH (r:Resource:Original)
                RETURN DISTINCT r.type as full_type
                """
                type_result = session.run(type_query)
                all_full_types = [record["full_type"] for record in type_result]
                
                logger.info(f"[DEBUG] Found {len(all_full_types)} distinct resource types in Neo4j")
                logger.info(f"[DEBUG] First 10 full types from Neo4j: {sorted(all_full_types)[:10]}")
                
                # Step 2: Build mapping from simplified to full names
                simplified_to_full = {}
                for full_type in all_full_types:
                    simplified = self.analyzer._get_resource_type_name(["Resource"], full_type)
                    if simplified not in simplified_to_full:
                        simplified_to_full[simplified] = []
                    simplified_to_full[simplified].append(full_type)
                
                logger.info(f"[DEBUG] Built mapping for {len(simplified_to_full)} simplified types")
                
                # Step 3: Get pattern types (simplified names)
                pattern_types_simplified = set()
                for pattern_info in detected_patterns.values():
                    pattern_types_simplified.update(pattern_info["matched_resources"])
                
                logger.info(f"[DEBUG] Pattern types (simplified): {len(pattern_types_simplified)}")
                logger.info(f"[DEBUG] First 10 pattern types: {sorted(list(pattern_types_simplified))[:10]}")
                
                # Step 4: Compute orphaned types (simplified)
                orphaned_types_simplified = set(source_resource_type_counts.keys()) - pattern_types_simplified
                
                if not orphaned_types_simplified:
                    logger.info("No orphaned resource types found in source graph")
                    return []
                
                logger.info(f"[DEBUG] Orphaned types (simplified): {len(orphaned_types_simplified)}")
                logger.info(f"[DEBUG] First 10 orphaned types: {sorted(list(orphaned_types_simplified))[:10]}")
                
                # Step 5: Map orphaned simplified types to full names
                full_orphaned_types = []
                unmapped_types = []
                for simplified in orphaned_types_simplified:
                    if simplified in simplified_to_full:
                        full_orphaned_types.extend(simplified_to_full[simplified])
                    else:
                        unmapped_types.append(simplified)
                
                if unmapped_types:
                    logger.info(f"[DEBUG] {len(unmapped_types)} orphaned types not in Neo4j (organizational/identity types): {sorted(unmapped_types)[:10]}")
                
                if not full_orphaned_types:
                    logger.info("No orphaned types found in Neo4j (all simplified names unmapped)")
                    return []
                
                logger.info(f"[DEBUG] Mapped to {len(full_orphaned_types)} full orphaned types")
                logger.info(f"[DEBUG] First 10 full orphaned types: {sorted(full_orphaned_types)[:10]}")
                
                # Step 6: Query Neo4j with CORRECT full names
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
                            r for r in all_resources_simplified
                            if r["type"] in orphaned_types_simplified
                        ]
                        
                        if orphaned_only_resources:
                            # Create a pseudo-pattern name for these orphaned instances
                            orphaned_in_instance = {
                                r["type"] for r in orphaned_only_resources
                            }
                            pseudo_pattern_name = f"Orphaned: {', '.join(sorted(list(orphaned_in_instance)[:3]))}"
                            
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
                            
                            pseudo_pattern_name = (
                                f"Orphaned (standalone): {simplified_type}"
                            )
                            orphaned_instances.append(
                                (pseudo_pattern_name, singleton_instance)
                            )
                            
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
        
        finally:
            driver.close()
        
        logger.info(
            f"Found {len(orphaned_instances)} total orphaned instances "
            f"({len([i for i in orphaned_instances if 'standalone' in i[0]])} standalone)"
        )
        
        return orphaned_instances


__all__ = ["OrphanedResourceHandler"]
