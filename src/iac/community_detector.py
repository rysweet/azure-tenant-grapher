"""
Community Detection for Graph-based Terraform Splitting.

Detects connected components (communities) in the resource graph to enable:
- Per-community Terraform file generation
- Parallel deployment of independent communities
- Elimination of undeclared resource reference errors
"""

import logging
from collections import defaultdict
from typing import Any, Dict, List, Set

logger = logging.getLogger(__name__)


class CommunityDetector:
    """Detect communities (connected components) in resource graph."""

    def __init__(self, neo4j_driver):
        """Initialize with Neo4j driver."""
        self.driver = neo4j_driver

    def detect_communities(self) -> List[Set[str]]:
        """
        Detect communities using Neo4j graph algorithms.

        Returns:
            List of sets, where each set contains resource IDs in that community
        """
        with self.driver.session() as session:
            # Use Cypher to find weakly connected components
            # This groups resources that are connected by any path
            result = session.run("""
                MATCH (r:Resource)
                WHERE NOT r:Original  // Use abstracted nodes only

                // For each resource, find all resources connected to it
                OPTIONAL MATCH path = (r)-[*]-(connected:Resource)
                WHERE connected <> r AND NOT connected:Original

                WITH r.id AS resource_id,
                     collect(DISTINCT connected.id) AS connected_ids

                RETURN resource_id, connected_ids
                ORDER BY resource_id
            """)

            # Build adjacency list
            adjacency = defaultdict(set)
            all_resources = set()

            for record in result:
                resource_id = record["resource_id"]
                connected_ids = record["connected_ids"] or []

                all_resources.add(resource_id)
                for connected_id in connected_ids:
                    if connected_id:  # Skip None values
                        adjacency[resource_id].add(connected_id)
                        adjacency[connected_id].add(resource_id)
                        all_resources.add(connected_id)

            # Find connected components using DFS
            communities = []
            visited = set()

            for resource_id in all_resources:
                if resource_id not in visited:
                    # Start new community
                    community = set()
                    stack = [resource_id]

                    while stack:
                        current = stack.pop()
                        if current in visited:
                            continue

                        visited.add(current)
                        community.add(current)

                        # Add all connected resources to stack
                        for neighbor in adjacency.get(current, set()):
                            if neighbor not in visited:
                                stack.append(neighbor)

                    communities.append(community)

            # Sort communities by size (largest first)
            communities.sort(key=len, reverse=True)

            logger.info(
                f"Detected {len(communities)} communities. "
                f"Sizes: {[len(c) for c in communities[:10]]}"
            )

            return communities

    def get_community_metadata(self, community: Set[str]) -> Dict[str, Any]:
        """
        Get metadata about a community.

        Args:
            community: Set of resource IDs in the community

        Returns:
            Dict with resource counts by type, total size, etc.
        """
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (r:Resource)
                WHERE r.id IN $resource_ids AND NOT r:Original

                WITH r.type AS resource_type, count(*) AS count
                RETURN resource_type, count
                ORDER BY count DESC
            """,
                resource_ids=list(community),
            )

            type_counts = {}
            for record in result:
                type_counts[record["resource_type"]] = record["count"]

            return {
                "size": len(community),
                "type_counts": type_counts,
                "dominant_type": max(type_counts.items(), key=lambda x: x[1])[0]
                if type_counts
                else "unknown",
            }
