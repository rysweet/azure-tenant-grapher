"""Graph traversal functionality for IaC generation.

This module provides graph traversal and data structure definitions
for converting Neo4j tenant graphs into IaC representations.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, LiteralString, Optional, cast

from neo4j import Driver

logger = logging.getLogger(__name__)


@dataclass
class TenantGraph:
    """Data structure representing a tenant's infrastructure graph."""

    resources: List[Dict[str, Any]] = field(default_factory=list)
    relationships: List[Dict[str, Any]] = field(default_factory=list)


class GraphTraverser:
    """Traverses Neo4j graph data to extract tenant infrastructure."""

    def __init__(
        self, driver: Driver, transformation_rules: Optional[List[Any]] = None
    ) -> None:
        """Initialize graph traverser with Neo4j driver.

        Args:
            driver: Neo4j database driver instance
            transformation_rules: Optional transformation rules (for future use)
        """
        self.driver = driver
        self.transformation_rules = transformation_rules or []

    async def traverse(
        self, filter_cypher: Optional[str] = None, use_original_ids: bool = False
    ) -> TenantGraph:
        """Traverse and extract tenant graph data.

        Args:
            filter_cypher: Optional Cypher filter string
            use_original_ids: If True, query Original nodes; if False (default), query Abstracted nodes

        Returns:
            TenantGraph instance with extracted data
        """
        logger.info("Starting graph traversal")

        def process_result(
            result: list[Any],
            resources: list[dict[str, Any]],
            relationships: list[dict[str, Any]],
        ) -> None:
            for record in result:
                resource_node = record["r"]
                rels = record["rels"] if "rels" in record else []

                # Convert resource node to dict
                resource_dict = dict(resource_node)

                # Bug #15 fix: Add original_id from query result if available
                # This enables smart import comparison without querying Neo4j for each resource
                if record.get("original_id"):
                    resource_dict["original_id"] = record["original_id"]

                resources.append(resource_dict)

                # Process relationships
                for rel in rels:
                    if rel and rel.get("target"):  # Only add valid relationships
                        relationship_dict = {
                            "source": resource_node.get("id"),
                            "target": rel.get("target"),
                            "type": rel.get("type"),
                        }

                        # Add additional properties for GENERIC_RELATIONSHIP
                        if rel.get("type") == "GENERIC_RELATIONSHIP":
                            if rel.get("original_type"):
                                relationship_dict["original_type"] = rel.get(
                                    "original_type"
                                )
                            if rel.get("narrative_context"):
                                relationship_dict["narrative_context"] = rel.get(
                                    "narrative_context"
                                )

                        relationships.append(relationship_dict)

        if filter_cypher:
            query = filter_cypher
        else:
            # Default query - use abstracted nodes unless explicitly requesting original
            if use_original_ids:
                # Query Original nodes only (for legacy/debug purposes)
                query = """
                MATCH (r:Resource:Original)
                OPTIONAL MATCH (r)-[rel]->(t:Resource:Original)
                RETURN r, collect({
                    type: type(rel),
                    target: t.id,
                    original_type: rel.original_type,
                    narrative_context: rel.narrative_context
                }) AS rels
                """
            else:
                # Query ALL Resource nodes (both Original and Abstracted for IaC generation)
                # Priority: Abstracted nodes are preferred when both exist
                # This ensures we get all resources while using abstracted IDs when available
                # Bug #15 fix: Include original_id from SCAN_SOURCE_NODE relationship
                # for smart import comparison
                query = """
                MATCH (r:Resource)
                WHERE NOT EXISTS {
                    MATCH (abstracted:Resource)
                    WHERE NOT abstracted:Original
                    AND abstracted.original_id = r.id
                    AND r:Original
                }
                OPTIONAL MATCH (r)-[:SCAN_SOURCE_NODE]->(orig:Resource:Original)
                OPTIONAL MATCH (r)-[rel]->(t:Resource)
                WHERE NOT EXISTS {
                    MATCH (t_abstracted:Resource)
                    WHERE NOT t_abstracted:Original
                    AND t_abstracted.original_id = t.id
                    AND t:Original
                }
                RETURN r, orig.id AS original_id, orig.properties AS original_properties, collect({
                    type: type(rel),
                    target: t.id,
                    original_type: rel.original_type,
                    narrative_context: rel.original_type
                }) AS rels
                """

        resources = []
        relationships = []

        try:
            with self.driver.session() as session:
                result = session.run(cast("LiteralString", query))
                # Check if result is empty (consume iterator)
                result_list = list(result)
                if not result_list and not filter_cypher:
                    # Fallback query if no :Resource nodes found and not using a filter
                    # Respect use_original_ids flag in fallback too
                    if use_original_ids:
                        fallback_query = """
                        MATCH (r)
                        WHERE r.type IS NOT NULL
                        OPTIONAL MATCH (r)-[rel]->(t)
                        RETURN r, collect({
                            type: type(rel),
                            target: t.id,
                            original_type: rel.original_type,
                            narrative_context: rel.narrative_context
                        }) AS rels
                        """
                        logger.info(
                            "No :Resource:Original nodes found, running fallback query for any nodes with 'type' property"
                        )
                    else:
                        fallback_query = """
                        MATCH (r)
                        WHERE r.type IS NOT NULL AND NOT EXISTS {MATCH (r:Original)}
                        OPTIONAL MATCH (r)-[rel]->(t)
                        WHERE NOT EXISTS {MATCH (t:Original)}
                        RETURN r, collect({
                            type: type(rel),
                            target: t.id,
                            original_type: rel.original_type,
                            narrative_context: rel.narrative_context
                        }) AS rels
                        """
                        logger.info(
                            "No abstracted :Resource nodes found, running fallback query for non-Original nodes with 'type' property"
                        )
                    result = session.run(cast("LiteralString", fallback_query))
                    result_list = list(result)
                process_result(result_list, resources, relationships)
                logger.info(
                    f"Extracted {len(resources)} resources and {len(relationships)} relationships"
                )

        except Exception as e:
            logger.error(f"Error during graph traversal: {e}")
            raise

        return TenantGraph(resources=resources, relationships=relationships)
