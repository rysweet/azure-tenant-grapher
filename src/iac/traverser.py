"""Graph traversal functionality for IaC generation.

This module provides graph traversal and data structure definitions
for converting Neo4j tenant graphs into IaC representations.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

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

    async def traverse(self, filter_cypher: Optional[str] = None) -> TenantGraph:
        """Traverse and extract tenant graph data.

        Args:
            filter_cypher: Optional Cypher filter string

        Returns:
            TenantGraph instance with extracted data
        """
        logger.info("Starting graph traversal")

        def process_result(result, resources, relationships):
            for record in result:
                resource_node = record["r"]
                rels = record["rels"] if "rels" in record else []

                # Convert resource node to dict
                resource_dict = dict(resource_node)
                resources.append(resource_dict)

                # Process relationships
                for rel in rels:
                    if rel and rel.get("target"):  # Only add valid relationships
                        relationship_dict = {
                            "source": resource_node.get("id"),
                            "target": rel.get("target"),
                            "type": rel.get("type"),
                        }
                        relationships.append(relationship_dict)

        if filter_cypher:
            query = filter_cypher
        else:
            # Default query as specified
            query = """
            MATCH (r:Resource)
            OPTIONAL MATCH (r)-[rel]->(t:Resource)
            RETURN r, collect({type:type(rel), target:t.id}) AS rels
            """

        resources = []
        relationships = []

        try:
            with self.driver.session() as session:
                result = session.run(query)
                # Check if result is empty (consume iterator)
                result_list = list(result)
                if not result_list and not filter_cypher:
                    # Fallback query if no :Resource nodes found and not using a filter
                    fallback_query = """
                    MATCH (r)
                    WHERE r.type IS NOT NULL
                    OPTIONAL MATCH (r)-[rel]->(t)
                    RETURN r, collect({type:type(rel), target:t.id}) AS rels
                    """
                    logger.info(
                        "No :Resource nodes found, running fallback query for nodes with 'type' property"
                    )
                    result = session.run(fallback_query)
                    result_list = list(result)
                process_result(result_list, resources, relationships)
                logger.info(
                    f"Extracted {len(resources)} resources and {len(relationships)} relationships"
                )

        except Exception as e:
            logger.error(f"Error during graph traversal: {e}")
            raise

        return TenantGraph(resources=resources, relationships=relationships)
