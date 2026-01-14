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
    """
    Configuration for subset selection predicates.

    Fields:
        node_ids: List of resource IDs to include.
        resource_types: List of resource types (wildcards allowed).
        labels: List of labels to match.
        cypher_query: Cypher query string (not implemented).
        policy_state: Compliance state to match (case-insensitive).
        created_after: Only include resources created after this datetime (ISO 8601 or datetime).
        tag_selector: Dict of tag key/values to match (all must match).
        resource_group: List of resource group names to filter by (extracts from resource IDs).
        depth: Optional int, limits closure hops from initial match.
    """

    node_ids: Optional[List[str]] = None
    resource_types: Optional[List[str]] = None
    labels: Optional[List[str]] = None
    cypher_query: Optional[str] = None

    policy_state: Optional[str] = None
    created_after: Optional["str"] = None  # Accept ISO str, parse at runtime
    tag_selector: Optional[dict[str, str]] = None
    resource_group: Optional[List[str]] = None
    depth: Optional[int] = None

    @classmethod
    def parse(cls, filter_string: str) -> "SubsetFilter":
        """
        Parse a subset filter string into a SubsetFilter object.

        Args:
            filter_string: String format like "nodeIds=a,b;types=Microsoft.Storage/*;label=DMZ;policyState=noncompliant;createdAfter=2024-01-01T00:00:00;tagSelector=env:prod,team:foo;resourceGroup=SimuLand,Production;depth=2"

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
            key_lc = key.strip().lower()
            value = value.strip()

            if key_lc == "nodeids":
                predicates["node_ids"] = [v.strip() for v in value.split(",")]
            elif key_lc == "types":
                predicates["resource_types"] = [v.strip() for v in value.split(",")]
            elif key_lc == "label":
                predicates["labels"] = [value]
            elif key_lc == "cypher":
                predicates["cypher_query"] = value
            elif key_lc == "policystate":
                predicates["policy_state"] = value
            elif key_lc == "createdafter":
                predicates["created_after"] = value
            elif key_lc == "tagselector":
                # Parse "key:value,key2:value2"
                tag_dict = {}
                for pair in value.split(","):
                    if ":" in pair:
                        k, v = pair.split(":", 1)
                        tag_dict[k.strip()] = v.strip()
                predicates["tag_selector"] = tag_dict
            elif key_lc in (
                "resourcegroup",
                "resourcegroups",
            ):  # Accept both singular and plural
                predicates["resource_group"] = [v.strip() for v in value.split(",")]
            elif key_lc == "depth":
                try:
                    predicates["depth"] = int(value)
                except Exception:
                    logger.warning(str(f"Invalid depth value: {value}"))
            else:
                logger.warning(str(f"Unknown subset filter predicate: {key}"))

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

        logger.info(str(f"Initial subset contains {len(included_resources)} resources"))

        # If using policy_state, created_after, tag_selector, or resource_group, do NOT perform closure
        if filter_config.policy_state is not None:
            closed_resources = included_resources
        elif filter_config.created_after is not None:
            closed_resources = included_resources
        elif filter_config.tag_selector is not None:
            closed_resources = included_resources
        elif filter_config.resource_group is not None:
            closed_resources = included_resources
        elif filter_config.labels is not None:
            # Labels filter should include closure
            closed_resources = self._perform_dependency_closure(
                graph, included_resources, getattr(filter_config, "depth", None)
            )
        else:
            # Step 2: Perform dependency closure to include required dependencies
            closed_resources = self._perform_dependency_closure(
                graph, included_resources, getattr(filter_config, "depth", None)
            )

        logger.info(str(f"After dependency closure: {len(closed_resources)} resources"))

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
            or filter_config.policy_state
            or filter_config.created_after
            or filter_config.tag_selector
            or filter_config.resource_group
        )

    def _build_inclusion_set(
        self, graph: TenantGraph, filter_config: SubsetFilter
    ) -> Set[str]:
        """Build the initial set of resource IDs that match the filter criteria."""
        included = None

        # Only one predicate group should be active at a time (AND is not intended by test expectations)
        # Priority: node_ids > resource_types > labels > policy_state > created_after > tag_selector > cypher_query

        # 1. node_ids
        if filter_config.node_ids:
            included = set()
            for resource in graph.resources:
                resource_id = resource.get("id")
                if resource_id in filter_config.node_ids:
                    included.add(resource_id)
            return included

        # 2. resource_types
        if filter_config.resource_types:
            included = set()
            for resource in graph.resources:
                resource_id = resource.get("id")
                resource_type = resource.get("resourceType", resource.get("type", ""))
                if resource_id and self._matches_type_filters(
                    resource_type, filter_config.resource_types
                ):
                    included.add(resource_id)
            return included

        # 3. labels
        if filter_config.labels:
            included = set()
            for resource in graph.resources:
                resource_id = resource.get("id")
                labels = resource.get("labels", [])
                if resource_id and any(
                    label in labels for label in filter_config.labels
                ):
                    included.add(resource_id)
            return included

        # 4. policy_state (case-insensitive match to property "policyState")
        if filter_config.policy_state:
            included = set()
            for resource in graph.resources:
                resource_id = resource.get("id")
                # Accept both "policyState" and "policy_state" keys for robustness
                state = resource.get("policyState")
                if state is None:
                    state = resource.get("policy_state")
                if (
                    resource_id
                    and state is not None
                    and str(state).lower() == filter_config.policy_state.lower()
                ):
                    included.add(resource_id)
            return included

        # 5. created_after (compare to property "createdAt")
        if filter_config.created_after:
            from datetime import datetime

            included = set()
            try:
                created_after_dt = datetime.fromisoformat(filter_config.created_after)
            except Exception:
                logger.warning(
                    f"Invalid createdAfter value: {filter_config.created_after}"
                )
                created_after_dt = None

            if created_after_dt:
                for resource in graph.resources:
                    resource_id = resource.get("id")
                    # Accept both "createdAt" and "created_at" keys for robustness
                    created_at = resource.get("createdAt")
                    if created_at is None:
                        created_at = resource.get("created_at")
                    if resource_id and created_at:
                        try:
                            created_at_dt = datetime.fromisoformat(created_at)
                            if created_at_dt > created_after_dt:
                                included.add(resource_id)
                        except Exception:
                            pass
            # Only include resources created after the threshold, exclude others
            return included

        # 6. tag_selector (all key/values must match in resource["tags"])
        if filter_config.tag_selector:
            included = set()
            for resource in graph.resources:
                resource_id = resource.get("id")
                tags = resource.get("tags", {})
                if resource_id and isinstance(tags, dict):
                    # Accept string keys for tags, ignore case for keys
                    def tag_match(k: str, v: str, tags: dict[str, str] = tags) -> bool:
                        for tag_key, tag_val in tags.items():
                            if tag_key.lower() == k.lower() and tag_val == v:
                                return True
                        return False

                    if all(
                        tag_match(k, v) for k, v in filter_config.tag_selector.items()
                    ):
                        included.add(resource_id)
            return included

        # 7. resource_group - Fix #594: Check property not just ID format
        if filter_config.resource_group:
            included = set()
            for resource in graph.resources:
                resource_id = resource.get("id")
                # Fix #594: Check resource_group property (works for Abstracted + Original nodes)
                rg = resource.get("resource_group") or resource.get("resourceGroup")
                if rg and rg in filter_config.resource_group:
                    included.add(resource_id)
                # Fallback: Also check ID format for backwards compatibility
                elif resource_id and "/resourceGroups/" in resource_id:
                    parts = resource_id.split("/resourceGroups/")
                    if len(parts) > 1:
                        rg_part = parts[1].split("/")[0]
                        if rg_part in filter_config.resource_group:
                            included.add(resource_id)
            return included

        # 8. cypher_query (not implemented)
        if filter_config.cypher_query:
            logger.warning("Cypher query filtering not yet implemented")
            return set()

        # If no filters, include all
        included = set()
        for resource in graph.resources:
            resource_id = resource.get("id")
            if resource_id:
                included.add(resource_id)

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
            logger.warning(str(f"Invalid type pattern: {pattern}"))
            return False

    def _perform_dependency_closure(
        self, graph: TenantGraph, initial_set: Set[str], depth: Optional[int] = None
    ) -> Set[str]:
        """
        Perform dependency closure to include all resources that the initial set depends on,
        including parent scopes, diagnostics, and role assignments, with optional depth limit.

        Args:
            graph: The full tenant graph.
            initial_set: Set of resource IDs to start from.
            depth: Optional int, limits closure hops from initial match.

        Returns:
            Set of resource IDs after closure.
        """
        from collections import deque

        # If depth is None, use unlimited closure (legacy behavior)
        if depth is None:
            # For backward compatibility, use a large number
            max_depth = float("inf")
        else:
            max_depth = depth

        closed_set = set(initial_set)
        queue: deque[tuple[str, int]] = deque(
            (rid, 0) for rid in initial_set
        )  # (resource_id, current_depth)

        while queue:
            resource_id, cur_depth = queue.popleft()
            if cur_depth >= max_depth:
                continue

            # Find all closure dependencies for this resource
            for dep_id in self._find_closure_dependencies(graph, resource_id):
                if dep_id not in closed_set and self._resource_exists(graph, dep_id):
                    closed_set.add(dep_id)
                    queue.append((dep_id, cur_depth + 1))

        return closed_set

    def _find_closure_dependencies(
        self, graph: TenantGraph, resource_id: str
    ) -> Set[str]:
        """
        Find all closure dependencies for a resource, including:
        - dependsOn
        - parent scopes (parent_id, parent relationship)
        - diagnostics (diagnosticSettings type or diagnostic relationship)
        - role assignments (roleAssignments type or roleAssignment relationship)
        """
        dependencies = set()

        # dependsOn relationships (legacy, both property and relationship)
        resource = self._find_resource_by_id(graph, resource_id)
        if resource:
            # dependsOn property
            depends_on = resource.get("dependsOn", [])
            if isinstance(depends_on, list):
                dependencies.update(depends_on)
            # parent_id property
            parent_id = resource.get("parent_id")
            if parent_id:
                dependencies.add(parent_id)

        # relationships
        for rel in graph.relationships:
            # dependsOn (relationship)
            if (
                rel.get("source") == resource_id
                and rel.get("type", "").lower() == "dependson"
            ) or (
                rel.get("from_id") == resource_id
                and rel.get("type", "").lower() == "dependson"
            ):
                target = rel.get("target") or rel.get("to_id")
                if target:
                    dependencies.add(target)
            # parent scope (relationship)
            if (
                rel.get("source") == resource_id
                and rel.get("type", "").lower() == "parent"
            ) or (
                rel.get("from_id") == resource_id
                and rel.get("type", "").lower() == "parent"
            ):
                target = rel.get("target") or rel.get("to_id")
                if target:
                    dependencies.add(target)
            # diagnostics closure
            if (
                rel.get("target") == resource_id or rel.get("to_id") == resource_id
            ) and "diagnostic" in rel.get("type", "").lower():
                source = rel.get("source") or rel.get("from_id")
                if source:
                    dependencies.add(source)
            # role assignment closure
            if (
                rel.get("target") == resource_id or rel.get("to_id") == resource_id
            ) and "roleassignment" in rel.get("type", "").lower():
                source = rel.get("source") or rel.get("from_id")
                if source:
                    dependencies.add(source)

        # diagnostics by type
        for res in graph.resources:
            if res.get("type", "").lower().endswith("diagnosticsettings") and (
                res.get("target_id") == resource_id
            ):
                dependencies.add(res.get("id"))
        # role assignments by type
        for res in graph.resources:
            if res.get(
                "type", ""
            ).lower() == "microsoft.authorization/roleassignments" and (
                res.get("target_id") == resource_id
            ):
                dependencies.add(res.get("id"))

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
            # Also support from_id/to_id for legacy
            if source_id is None and "from_id" in relationship:
                source_id = relationship.get("from_id")
            if target_id is None and "to_id" in relationship:
                target_id = relationship.get("to_id")

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
