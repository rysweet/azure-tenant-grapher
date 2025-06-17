"""
Subset selection and filtering for IaC generation.

This module provides functionality to filter tenant graph resources based on various
predicates and perform dependency closure to ensure complete resource sets.
"""

import logging
import re
from dataclasses import dataclass
from typing import List, Optional, Set

from .traverser import TenantGraph

logger = logging.getLogger(__name__)


@dataclass
class SubsetFilter:
    """Configuration for subset selection predicates."""

    node_ids: Optional[List[str]] = None
    resource_types: Optional[List[str]] = None
    labels: Optional[List[str]] = None
    cypher_query: Optional[str] = None

    @classmethod
    def parse(cls, filter_string: str) -> "SubsetFilter":
        """
        Parse a subset filter string into a SubsetFilter object.

        Args:
            filter_string: String format like "nodeIds=a,b;types=Microsoft.Storage/*;label=DMZ"

        Returns:
            SubsetFilter object with parsed predicates

        Raises:
            ValueError: If filter string format is invalid
        """
        if not filter_string:
            return cls()

        predicates = {}

        for clause in filter_string.split(";"):
            clause = clause.strip()
            if "=" not in clause:
                continue

            key, value = clause.split("=", 1)
            key = key.strip().lower()

            if key == "nodeids":
                predicates["node_ids"] = [v.strip() for v in value.split(",")]
            elif key == "types":
                predicates["resource_types"] = [v.strip() for v in value.split(",")]
            elif key == "label":
                predicates["labels"] = [value.strip()]
            elif key == "cypher":
                predicates["cypher_query"] = value.strip()
            else:
                logger.warning(f"Unknown subset filter predicate: {key}")

        return cls(**predicates)


class SubsetSelector:
    """Handles subset selection and dependency closure for tenant graphs."""

    def __init__(self):
        """Initialize the subset selector."""
        pass

    def apply(self, graph: TenantGraph, filter_config: SubsetFilter) -> TenantGraph:
        """
        Apply subset filtering to a tenant graph.

        Args:
            graph: The full tenant graph
            filter_config: Subset filter configuration

        Returns:
            A new TenantGraph containing only the filtered resources and their dependencies
        """
        if not self.has_filters(filter_config):
            logger.info("No subset filters specified, returning full graph")
            return graph

        # Step 1: Build initial inclusion set based on predicates
        included_resources = self._build_inclusion_set(graph, filter_config)

        if not included_resources:
            logger.warning("No resources matched subset filter criteria")
            return TenantGraph(resources=[], relationships=[])

        logger.info(f"Initial subset contains {len(included_resources)} resources")

        # Step 2: Perform dependency closure to include required dependencies
        closed_resources = self._perform_dependency_closure(graph, included_resources)

        logger.info(f"After dependency closure: {len(closed_resources)} resources")

        # Step 3: Build filtered graph
        filtered_graph = self._build_filtered_graph(graph, closed_resources)

        return filtered_graph

    def has_filters(self, filter_config: SubsetFilter) -> bool:
        """Check if any filters are specified."""
        return bool(
            filter_config.node_ids
            or filter_config.resource_types
            or filter_config.labels
            or filter_config.cypher_query
        )

    def _build_inclusion_set(
        self, graph: TenantGraph, filter_config: SubsetFilter
    ) -> Set[str]:
        """Build the initial set of resource IDs that match the filter criteria."""
        included = set()

        # Filter by explicit node IDs
        if filter_config.node_ids:
            for resource in graph.resources:
                resource_id = resource.get("id")
                if resource_id in filter_config.node_ids:
                    included.add(resource_id)

        # Filter by resource types (with wildcard support)
        if filter_config.resource_types:
            for resource in graph.resources:
                resource_id = resource.get("id")
                resource_type = resource.get("resourceType", resource.get("type", ""))
                if resource_id and self._matches_type_filters(
                    resource_type, filter_config.resource_types
                ):
                    included.add(resource_id)

        # Filter by labels (if supported in graph structure)
        if filter_config.labels:
            for resource in graph.resources:
                resource_id = resource.get("id")
                labels = resource.get("labels", [])
                if resource_id and any(
                    label in labels for label in filter_config.labels
                ):
                    included.add(resource_id)

        # TODO: Support cypher_query filtering (requires Neo4j integration)
        if filter_config.cypher_query:
            logger.warning("Cypher query filtering not yet implemented")

        return included

    def _matches_type_filters(
        self, resource_type: str, type_filters: List[str]
    ) -> bool:
        """Check if a resource type matches any of the type filters (with wildcard support)."""
        for type_filter in type_filters:
            if self._matches_type_pattern(resource_type, type_filter):
                return True
        return False

    def _matches_type_pattern(self, resource_type: str, pattern: str) -> bool:
        """Check if a resource type matches a pattern (supporting * wildcards)."""
        # Convert wildcard pattern to regex
        regex_pattern = pattern.replace("*", ".*").replace("?", ".")
        regex_pattern = f"^{regex_pattern}$"

        try:
            return bool(re.match(regex_pattern, resource_type, re.IGNORECASE))
        except re.error:
            logger.warning(f"Invalid type pattern: {pattern}")
            return False

    def _perform_dependency_closure(
        self, graph: TenantGraph, initial_set: Set[str]
    ) -> Set[str]:
        """
        Perform dependency closure to include all resources that the initial set depends on.

        This ensures we don't create broken deployments by including resources that
        reference other resources not in the subset.
        """
        closed_set = initial_set.copy()
        changed = True

        while changed:
            changed = False
            new_dependencies = set()

            for resource_id in closed_set:
                # Find all resources this resource depends on
                dependencies = self._find_resource_dependencies(graph, resource_id)
                for dep_id in dependencies:
                    if dep_id not in closed_set and self._resource_exists(
                        graph, dep_id
                    ):
                        new_dependencies.add(dep_id)
                        changed = True

            closed_set.update(new_dependencies)

        return closed_set

    def _find_resource_dependencies(
        self, graph: TenantGraph, resource_id: str
    ) -> Set[str]:
        """Find all resources that the given resource depends on."""
        dependencies = set()

        # Check relationships for explicit dependencies
        for relationship in graph.relationships:
            if relationship.get("from_id") == resource_id:
                # This resource depends on the target
                to_id = relationship.get("to_id")
                if to_id:
                    dependencies.add(to_id)

        # Find the resource in the list
        resource = self._find_resource_by_id(graph, resource_id)
        if resource:
            # Check for parent-child relationships (scope dependencies)
            parent_id = resource.get("parent_id")
            if parent_id:
                dependencies.add(parent_id)

            # Check for explicit dependsOn references in resource properties
            depends_on = resource.get("dependsOn", [])
            if isinstance(depends_on, list):
                dependencies.update(depends_on)

        return dependencies

    def _build_filtered_graph(
        self, original_graph: TenantGraph, included_resources: Set[str]
    ) -> TenantGraph:
        """Build a new TenantGraph containing only the included resources and their relationships."""
        # Filter resources
        filtered_resources = []
        for resource in original_graph.resources:
            resource_id = resource.get("id")
            if resource_id in included_resources:
                filtered_resources.append(resource)

        # Filter relationships to only include those between included resources
        filtered_relationships = []
        for relationship in original_graph.relationships:
            source_id = relationship.get("source")
            target_id = relationship.get("target")

            if source_id in included_resources and target_id in included_resources:
                filtered_relationships.append(relationship)

        return TenantGraph(
            resources=filtered_resources, relationships=filtered_relationships
        )

    def _resource_exists(self, graph: TenantGraph, resource_id: str) -> bool:
        """Check if a resource with the given ID exists in the graph."""
        for resource in graph.resources:
            if resource.get("id") == resource_id:
                return True
        return False

    def _find_resource_by_id(
        self, graph: TenantGraph, resource_id: str
    ) -> Optional[dict[str, object]]:
        """Find a resource by ID in the graph."""
        for resource in graph.resources:
            if resource.get("id") == resource_id:
                return resource
        return None
